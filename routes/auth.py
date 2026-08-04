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


def handle_get_profile(handler, parsed):
    """GET /api/profile — получить профиль текущего пользователя"""
    ctx = handler.session_ctx
    if not ctx.user:
        handler._send_json({'error': 'Не авторизован'}, 401)
        return
    result = auth_service.get_profile(ctx.user.username)
    handler._send_json(result)


def handle_save_profile(handler, data):
    """POST /api/profile — сохранить Matrix/LLM конфиг и перезапустить бота"""
    ctx = handler.session_ctx
    if not ctx.user:
        handler._send_json({'error': 'Не авторизован'}, 401)
        return
    result = auth_service.save_profile(ctx.user.username, data)
    # Перезапуск бота если Matrix включён
    if data.get('matrix_enabled'):
        try:
            from plugins.matrix_integration.plugin import restart
            import threading
            threading.Thread(target=restart, daemon=True).start()
        except Exception as e:
            logging.warning("Не удалось перезапустить Matrix-бота: %s", e)
    handler._send_json(result)


def handle_save_mikrotik_creds(handler, data):
    """POST /api/profile/creds — сохранить учётку микротика"""
    ctx = handler.session_ctx
    if not ctx.user:
        handler._send_json({'error': 'Не авторизован'}, 401)
        return
    device_name = data.get('device_name', '').strip()
    mk_username = data.get('mk_username', '').strip()
    mk_password = data.get('mk_password', '')
    if not device_name:
        handler._send_json({'error': 'Укажите device_name'}, 400)
        return
    auth_service.save_mikrotik_creds(
        ctx.user.username, device_name, mk_username,
        mk_password
    )
    handler._send_json({'success': True, 'message': f'Учётка для {device_name} сохранена'})


def handle_matrix_test(handler, data):
    """POST /api/matrix/test — проверить подключение к Matrix"""
    import asyncio
    token = data.get('token', '').strip()
    homeserver = data.get('homeserver', 'https://matrix.krasintegra.ru').strip()
    if not token:
        handler._send_json({'error': 'Укажите токен'}, 400)
        return

    async def _test():
        from nio import AsyncClient
        client = AsyncClient(homeserver, 'nur001')
        client.access_token = token
        resp = await client.whoami()
        await client.close()
        return resp

    try:
        result = asyncio.run(_test())
        from nio import WhoamiResponse
        if isinstance(result, WhoamiResponse):
            handler._send_json({'success': True, 'user_id': result.user_id, 'message': 'Подключение успешно'})
        else:
            handler._send_json({'success': False, 'error': str(result)})
    except Exception as e:
        handler._send_json({'success': False, 'error': str(e)})
