"""
DELETE-обработчики маршрутов
"""

from urllib.parse import parse_qs

from config.config_manager import ConfigManager


# ══════════════════════════════════════════════════════════════
#  DELETE /api/forget_credentials
# ══════════════════════════════════════════════════════════════

def handle_forget_credentials(handler, parsed):
    qs = parse_qs(parsed.query)
    device_name = qs.get('device', [''])[0]
    if not device_name:
        handler._send_json({'error': 'Не указано устройство'}, 400)
        return
    ConfigManager.save_credentials(device_name, '', '')
    handler._send_json({'success': True, 'message': f'Учетные данные для {device_name} удалены'})


# ══════════════════════════════════════════════════════════════
#  DELETE /api/forget_password
# ══════════════════════════════════════════════════════════════

def handle_forget_password(handler, parsed):
    qs = parse_qs(parsed.query)
    device_name = qs.get('device', [''])[0]
    if not device_name:
        handler._send_json({'error': 'Не указано устройство'}, 400)
        return
    ConfigManager.save_password(device_name, '')
    handler._send_json({'success': True, 'message': f'Пароль для {device_name} удален'})
