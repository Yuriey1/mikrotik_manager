"""Парсер заявок из сообщений Matrix (Element)"""

import re
import uuid
from typing import Dict, List, Optional

# Справочник известных площадок
SITES = [
    'Шалакит', 'Дражный', 'Магызы', 'Весёлый', 'Караган',
    'Караган РТ', 'Нелькан', 'Джигда', 'Чумикан', 'Аим',
]

# Ключевые фразы для определения типа доступа
FULL_ACCESS_PHRASES = [
    r'полный\s+доступ', r'доступ\s+в\s+интернет', r'интернет',
    r'инет\b', r'подключите\s+интернет', r'предоставить\s+интернет',
]

CORP_ACCESS_PHRASES = [
    r'корп[.\s]*ресы', r'корпоративные\s+ресурсы',
    r'бесплатный\s+доступ', r'\bmax\b',
]


def _find_mac(text: str) -> Optional[str]:
    """Извлечь MAC-адрес"""
    m = re.search(
        r'(?:mac[:\-\s]*(?:адрес)?[:\s]*)([0-9A-Fa-f]{2}(?:[:-]){5}[0-9A-Fa-f]{2})',
        text, re.IGNORECASE,
    )
    if not m:
        # Резервный поиск: просто MAC-паттерн без префикса
        m = re.search(r'([0-9A-Fa-f]{2}(?:[:-]){5}[0-9A-Fa-f]{2})', text)
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
    # a) По справочнику
    for site in SITES:
        if site.lower() in text.lower():
            return site
    # b) Паттерны: "на уч. X", "на X", "корп X", "уч. X"
    m = re.search(
        r'(?:на\s+уч[.\s]*|на\s+|корп[.\s]*|уч[.\s]+)([А-Яа-яЁё\w]+)',
        text, re.IGNORECASE,
    )
    return m.group(1).capitalize() if m else None


def _find_full_name(text: str) -> Optional[str]:
    """Извлечь ФИО (три слова с заглавных подряд)"""
    m = re.search(
        r'([А-ЯЁ][а-яё]+)\s+([А-ЯЁ][а-яё]+)\s+([А-ЯЁ][а-яё]+)',
        text,
    )
    if m:
        return f"{m.group(1)} {m.group(2)} {m.group(3)}"
    return None


def _find_position_org(text: str, full_name: Optional[str]) -> tuple:
    """Извлечь должность и организацию из остатка текста"""
    position = None
    org = None

    # Простейшая эвристика: после ФИО, до площадки/IP/MAC — должность и организация
    after_name = text
    if full_name:
        idx = text.find(full_name)
        if idx >= 0:
            after_name = text[idx + len(full_name):]

    # Ищем конструкцию "Организация Должность" или "Должность Организация"
    # ООО/ИП/etc + два-три слова с заглавной
    org_m = re.search(r'(ООО|ИП|АО|ЗАО|ПАО)\s+"?([^"]+?)"?\s*$', after_name)
    if org_m:
        org = f"{org_m.group(1)} {org_m.group(2).strip()}"

    # Должность: последние 1-3 слова перед площадкой или концом, не являющиеся ФИО
    pos_m = re.search(r'([А-ЯЁ][а-яё]+(?:\s+[а-яё]+){0,2})\s*$', after_name)
    if pos_m:
        candidate = pos_m.group(1).strip()
        if full_name and candidate not in full_name:
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
