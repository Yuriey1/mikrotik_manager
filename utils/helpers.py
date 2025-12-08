"""
Вспомогательные функции
"""

import ipaddress

def russian_to_mikrotik_comment(text):
    """
    Преобразует русские символы в формат MikroTik для комментариев.
    """
    result = []
    for char in text:
        if 'а' <= char.lower() <= 'я' or char == 'ё':
            result.append(char)
        else:
            result.append(char)
    return ''.join(result)

def ip_in_network(ip, network_addr, prefix):
    """Проверить принадлежность IP к сети"""
    try:
        network = ipaddress.ip_network(f"{network_addr}/{prefix}", strict=False)
        return ipaddress.ip_address(ip) in network
    except ValueError:
        return False
