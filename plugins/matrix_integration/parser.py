"""Парсер заявок из сообщений Matrix (Element)"""

import re
import uuid
from typing import Dict, List, Optional

# Справочник известных площадок
SITES = [
    'Шалакит', 'Дражный', 'Магызы', 'Весёлый', 'Караган',
    'Караган РТ', 'Нелькан', 'Джигда', 'Чумикан', 'Аим',
    'Надежда', 'Горелая',
]

# Ключевые фразы для определения типа доступа
FULL_ACCESS_PHRASES = [
    r'полный\s+доступ', r'доступ\s+в\s+интернет', r'интернет',
    r'инет\b', r'подключите\s+интернет', r'предоставить\s+интернет',
    r'подключите\s+к\s+[Ии]нтернет', r'пропишите\s+.*интернет',
    r'доступ\s+к\s+сети\s+интернет',
]

CORP_ACCESS_PHRASES = [
    r'корп[.\s]*ресы', r'корпоративные\s+ресурсы',
    r'бесплатный\s+доступ', r'\bmax\b',
]

# Стеммы площадок для фильтрации ФИО (первые 4 символа)
_SITE_STEMS = {s.lower()[:4] for s in SITES if len(s) >= 4}
_COMPANY_STEMS = {'спец', 'евро', 'строй', 'горн', 'рудн', 'союз', 'вост'}
_ORG_PREFIXES = {'ООО', 'ИП', 'АО', 'ЗАО', 'ПАО'}

# Слова, не являющиеся должностью
_NON_POSITION_WORDS = {'подключите', 'пропишите', 'добавьте', 'доброе', 'утро', 'прошу'}


def _find_mac(text: str) -> Optional[str]:
    """Извлечь MAC-адрес"""
    m = re.search(
        r'(?:mac[:\-\s]*(?:адрес)?[:\s]*)([0-9A-Fa-f]{2}(?:[:-][0-9A-Fa-f]{2}){5})',
        text, re.IGNORECASE,
    )
    if not m:
        m = re.search(r'([0-9A-Fa-f]{2}(?:[:-][0-9A-Fa-f]{2}){5})', text)
    if m:
        return m.group(1).upper().replace('-', ':')
    return None


def _find_all_macs(text: str) -> list:
    """Извлечь все MAC-адреса"""
    macs = []
    for m in re.finditer(r'(?:mac[:\-\s]*(?:адрес)?[:\s]*)?([0-9A-Fa-f]{2}(?:[:-][0-9A-Fa-f]{2}){5})', text, re.IGNORECASE):
        macs.append(m.group(1).upper().replace('-', ':'))
    return macs


def _find_ip(text: str) -> Optional[str]:
    """Извлечь полный IP-адрес (4 октета)"""
    m = re.search(r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})', text)
    return m.group(1) if m else None


def _find_short_ip(text: str) -> Optional[str]:
    """Извлечь сокращённый IP вида 'ип 91.67'"""
    m = re.search(r'ип\s+(\d{1,3})\.(\d{1,3})', text, re.IGNORECASE)
    if m:
        return f"192.168.{m.group(1)}.{m.group(2)}"
    return None


def _find_access_type(text: str) -> Dict:
    """Определить тип доступа"""
    for phrase in FULL_ACCESS_PHRASES:
        if re.search(phrase, text, re.IGNORECASE):
            return {'internet_access': True, 'is_full_access': True}
    for phrase in CORP_ACCESS_PHRASES:
        if re.search(phrase, text, re.IGNORECASE):
            return {'internet_access': False, 'is_full_access': False}
    return {'internet_access': False, 'is_full_access': None}


def _find_site(text: str) -> Optional[str]:
    """Извлечь площадку"""
    for site in sorted(SITES, key=lambda s: -len(s)):
        if site.lower() in text.lower():
            return site
    words = re.findall(r'[А-Яа-яЁё\w]+', text)
    for w in words:
        for site in SITES:
            if len(w) >= 4 and (w.lower().startswith(site.lower()[:4]) or site.lower().startswith(w.lower()[:4])):
                return site

    # "Site - Name" (в начале строки, перед тире)
    m = re.search(r'^([А-ЯЁ][А-Яа-яЁё]{3,})\s*[-–—]', text)
    if m:
        candidate = m.group(1).capitalize()
        for site in SITES:
            if candidate.lower().startswith(site.lower()[:4]):
                return site

    # "уч. X", "на уч. X", "корп X"
    m = re.search(
        r'(?:уч[.\s]+|на\s+уч[.\s]*|корп[.\s]*)([А-Яа-яЁё]{4,})',
        text, re.IGNORECASE,
    )
    if m:
        candidate = m.group(1).capitalize()
        prefix = m.group(0)[:m.start(1) - m.start(0)]
        if re.search(r'корп', prefix, re.IGNORECASE):
            if candidate.lower() not in [s.lower() for s in SITES]:
                pass
            else:
                return candidate
        elif candidate.lower() not in ('отправ', 'провер', 'закон', 'добав', 'очеред'):
            return candidate

    # "на X"
    m = re.search(r'на\s+([А-Яа-яЁё]{4,})', text, re.IGNORECASE)
    if m:
        candidate = m.group(1).capitalize()
        for site in SITES:
            if candidate.lower().startswith(site.lower()[:4]):
                return site
    return None


def _find_full_name(text: str) -> Optional[str]:
    """Извлечь ФИО — три заглавных кириллических слова подряд, исключая площадки/компании"""
    words = text.split()
    for i in range(len(words) - 2):
        w1 = words[i].strip(' ,.-–—()[]«»"\'')
        w2 = words[i + 1].strip(' ,.-–—()[]«»"\'')
        w3 = words[i + 2].strip(' ,.-–—()[]«»"\'')
        if not (re.match(r'^[А-ЯЁ][а-яё]+$', w1) and
                re.match(r'^[А-ЯЁ][а-яё]+$', w2) and
                re.match(r'^[А-ЯЁ][а-яё]+$', w3)):
            continue
        if any(w1.lower().startswith(s) for s in _SITE_STEMS):
            continue
        if any(w1.lower().startswith(p) for p in _COMPANY_STEMS):
            continue
        return f"{w1} {w2} {w3}"
    return None


def _find_all_full_names(text: str) -> list:
    """Найти все ФИО в тексте (для детекта мульти-заявок), без перекрытий"""
    names = []
    words = text.split()
    last_end = 0
    for i in range(len(words) - 2):
        if i < last_end:
            continue  # перекрывается с предыдущим результатом
        w1 = words[i].strip(' ,.-–—()[]«»"\'')
        w2 = words[i + 1].strip(' ,.-–—()[]«»"\'')
        w3 = words[i + 2].strip(' ,.-–—()[]«»"\'')
        if not (re.match(r'^[А-ЯЁ][а-яё]+$', w1) and
                re.match(r'^[А-ЯЁ][а-яё]+$', w2) and
                re.match(r'^[А-ЯЁ][а-яё]+$', w3)):
            continue
        if any(w1.lower().startswith(s) for s in _SITE_STEMS):
            continue
        if any(w1.lower().startswith(p) for p in _COMPANY_STEMS):
            continue
        names.append((i, f"{w1} {w2} {w3}"))
        last_end = i + 3  # не даём перекрываться
    return names


def _find_position_org(text: str, full_name: Optional[str]) -> tuple:
    """Извлечь должность и организацию из остатка текста"""
    position = None
    org = None

    after_name = text
    before_name = ''
    if full_name:
        idx = text.find(full_name)
        if idx >= 0:
            after_name = text[idx + len(full_name):]
            before_name = text[:idx]

    # --- 1. Организация (ООО/ИП/АО) ---
    org_text = after_name if after_name else text
    org_m = re.search(r'(ООО|ИП|АО|ЗАО|ПАО)\s+["\'\\]*([^"\')\n]{2,})', org_text)
    if org_m:
        raw = f"{org_m.group(1)} {org_m.group(2).strip().rstrip('.')}"
        parts = raw.split()
        if len(parts) >= 5:
            position = ' '.join(parts[-2:])
            org = ' '.join(parts[:-2])
        elif len(parts) == 4:
            position = parts[-1]
            org = ' '.join(parts[:-1])
        else:
            org = raw

    # --- 2. Должность ---
    # 2a. В тексте ДО ФИО
    if not position and before_name:
        abbr_m = re.search(r'(?:сотрудника\s+|должность\s+)?([А-ЯЁ]{2,4})\b', before_name)
        if abbr_m:
            position = abbr_m.group(1)
        if not position:
            lc_m = re.search(r'([а-яё]+(?:щего|щегося|теля|ика|ера|щика|чика|ющего))\b', before_name)
            if lc_m:
                position = lc_m.group(1).capitalize()

    # 2b. В тексте ПОСЛЕ ФИО
    if not position and full_name:
        remainder = re.sub(r'^[,.\-–—\s]+', '', after_name)
        if org:
            remainder = remainder.replace(org, '', 1)
        before_tech = re.split(r'\n|(?:ip|ип)[:\-\s]|mac[:\-\s]|IP', remainder, maxsplit=1, flags=re.IGNORECASE)[0]
        before_tech = before_tech.strip(' ,.-–—()«»')
        before_tech = re.sub(r'\b(?:подключите|пропишите|добавьте)\b', '', before_tech, flags=re.IGNORECASE).strip()

        if before_tech:
            cap_m = re.search(r'([А-ЯЁ][а-яё]+(?:\s+\S+){0,3})', before_tech)
            if cap_m:
                candidate = cap_m.group(1).strip()
                if full_name not in candidate and not any(op in candidate for op in _ORG_PREFIXES):
                    position = candidate
            if not position:
                lc_m = re.search(r'([а-яё]+(?:\s+\S+){1,3})', before_tech)
                if lc_m:
                    candidate = lc_m.group(1).strip()
                    if full_name not in candidate and not any(op in candidate for op in _ORG_PREFIXES):
                        position = candidate
                if not position:
                    lc1_m = re.search(r'([а-яё]{5,})', before_tech)
                    if lc1_m:
                        candidate = lc1_m.group(1).strip()
                        if candidate.lower() not in _NON_POSITION_WORDS and 'интернет' not in candidate.lower():
                            position = candidate

    return position, org


def _split_multi(text: str) -> list:
    """Разбить сообщение с несколькими абонентами на отдельные сегменты"""
    names = _find_all_full_names(text)
    if len(names) <= 1:
        return [text.strip()]

    words = text.split()

    # Извлекаем «шапку» — всё до первого ФИО
    header_end = words[:names[0][0]]
    header = ' '.join(header_end).strip() if header_end else ''

    segments = []
    for idx, (pos, name) in enumerate(names):
        # Граница следующего ФИО (или конец текста)
        if idx + 1 < len(names):
            next_pos = names[idx + 1][0]
            body = ' '.join(words[pos:next_pos])
        else:
            body = ' '.join(words[pos:])

        segment = (header + ' ' + body).strip() if header else body.strip()
        segments.append(segment)

    # Если IP/MAC общие на всё сообщение — добавляем к каждому сегменту
    macs = _find_all_macs(text)
    if macs and not any(_find_mac(s) for s in segments):
        # MAC только в шапке — добавляем к первому сегменту
        pass  # MAC уже в header который мы добавили

    return segments


def parse_message(text: str) -> Dict:
    """Разобрать сообщение из Matrix на поля заявки (один абонент)"""
    text = text.strip()
    result = {
        'id': str(uuid.uuid4()),
        'mac': None,
        'ip': None,
        'full_name': None,
        'position': None,
        'org': None,
        'site': None,
        'internet_access': False,
        'is_full_access': None,
        'raw_message': text,
    }

    result['mac'] = _find_mac(text)

    ip = _find_ip(text)
    if not ip:
        ip = _find_short_ip(text)
    result['ip'] = ip

    access = _find_access_type(text)
    result.update(access)

    result['site'] = _find_site(text)
    result['full_name'] = _find_full_name(text)

    pos, org = _find_position_org(text, result['full_name'])
    result['position'] = pos
    result['org'] = org

    return result


def parse_all(text: str) -> list:
    """Разобрать сообщение — может вернуть несколько заявок"""
    segments = _split_multi(text)
    results = []
    for seg in segments:
        r = parse_message(seg)
        if r.get('mac') or r.get('ip') or r.get('full_name'):
            results.append(r)
    return results if results else [parse_message(text)]
