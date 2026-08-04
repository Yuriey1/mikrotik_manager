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
    # Ищем от длинного к короткому (Караган РТ → Караган)
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
        # Отрезаем от org_too_long_to_be_position (последние 1-2 слова = должность)
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
        # Аббревиатура
        abbr_m = re.search(r'(?:сотрудника\s+|должность\s+)?([А-ЯЁ]{2,4})\b', before_name)
        if abbr_m:
            position = abbr_m.group(1)
        # Роль в нижнем регистре (проверяющего, буровик, ...)
        if not position:
            lc_m = re.search(r'([а-яё]+(?:щего|щегося|теля|ика|ера|щика|чика|ющего))\b', before_name)
            if lc_m:
                position = lc_m.group(1).capitalize()

    # 2b. В тексте ПОСЛЕ ФИО
    if not position and full_name:
        remainder = re.sub(r'^[,.\-–—\s]+', '', after_name)
        # Убрать организацию если уже нашли
        if org:
            remainder = remainder.replace(org, '', 1)
        # Обрезать по IP/MAC/переводу строки
        before_tech = re.split(r'\n|(?:ip|ип)[:\-\s]|mac[:\-\s]|IP', remainder, maxsplit=1, flags=re.IGNORECASE)[0]
        before_tech = before_tech.strip(' ,.-–—()«»')
        # Убрать слова-паразиты
        before_tech = re.sub(r'\b(?:подключите|пропишите|добавьте)\b', '', before_tech, flags=re.IGNORECASE).strip()

        if before_tech:
            # Заглавное слово + 0-3 слова (должность)
            cap_m = re.search(r'([А-ЯЁ][а-яё]+(?:\s+\S+){0,3})', before_tech)
            if cap_m:
                candidate = cap_m.group(1).strip()
                if full_name not in candidate and not any(op in candidate for op in _ORG_PREFIXES):
                    position = candidate
            # Строчная должность (инженер ГСМ, машинист, буровик)
            if not position:
                # Два+ слова строчных подряд
                lc_m = re.search(r'([а-яё]+(?:\s+\S+){1,3})', before_tech)
                if lc_m:
                    candidate = lc_m.group(1).strip()
                    if full_name not in candidate and not any(op in candidate for op in _ORG_PREFIXES):
                        position = candidate
                # Одно длинное строчное слово (буровик, проверяющий)
                if not position:
                    lc1_m = re.search(r'([а-яё]{5,})', before_tech)
                    if lc1_m:
                        candidate = lc1_m.group(1).strip()
                        if candidate.lower() not in _NON_POSITION_WORDS and 'интернет' not in candidate.lower():
                            position = candidate

    return position, org


def parse_message(text: str) -> Dict:
    """Разобрать сообщение из Matrix на поля заявки"""
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
