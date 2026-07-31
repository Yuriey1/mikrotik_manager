"""API-эндпоинты аутентификации"""

import json
import logging
from services import auth as auth_service


def handle_login(handler, data):
    """POST /api/login {username, password}"""
    username = data.get('username', '').strip()
    password = data.get('password', '')
    if not username or not password:
        handler._send_json({'error': 'Укажите логин и пароль'}, 400)
        return

    result = auth_service.login(username, password)
    if result['success']:
        handler._send_json(result)
    else:
        handler._send_json(result, 401)


def handle_register(handler, data):
    """POST /api/register {username, password}"""
    username = data.get('username', '').strip()
    password = data.get('password', '')
    if not username or not password:
        handler._send_json({'error': 'Укажите логин и пароль'}, 400)
        return
    if len(password) < 4:
        handler._send_json({'error': 'Пароль должен быть не менее 4 символов'}, 400)
        return

    result = auth_service.register(username, password)
    if result['success']:
        handler._send_json(result)
    else:
        handler._send_json(result, 409)
