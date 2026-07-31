"""API-эндпоинты аутентификации и управления пользователями"""

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


def handle_list_users(handler, parsed):
    """GET /api/users — список пользователей (только admin)"""
    result = auth_service.list_users()
    handler._send_json(result)


def handle_delete_user(handler, data):
    """POST /api/users/delete {username} — удалить пользователя"""
    username = data.get('username', '').strip()
    if not username:
        handler._send_json({'error': 'Укажите username'}, 400)
        return
    result = auth_service.delete_user(username)
    if result['success']:
        handler._send_json(result)
    else:
        handler._send_json(result, 400)


def handle_change_password(handler, data):
    """POST /api/users/password {username, password} — сменить пароль"""
    username = data.get('username', '').strip()
    password = data.get('password', '')
    if not username or not password:
        handler._send_json({'error': 'Укажите username и password'}, 400)
        return
    if len(password) < 4:
        handler._send_json({'error': 'Пароль должен быть не менее 4 символов'}, 400)
        return
    result = auth_service.change_password(username, password)
    handler._send_json(result)
