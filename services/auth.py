"""Аутентификация: вход, регистрация, управление сессиями"""

import uuid
import time
import bcrypt
from models.user import User, init_db, db

# Инициализация БД при импорте
init_db()


def register(username: str, password: str) -> dict:
    """Зарегистрировать пользователя"""
    if User.select().where(User.username == username).exists():
        return {'success': False, 'error': 'Пользователь уже существует'}
    User.create(
        username=username,
        password=bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    )
    return {'success': True, 'message': f'Пользователь {username} создан'}


def login(username: str, password: str) -> dict:
    """Войти и получить токен сессии"""
    user = User.get_or_none(User.username == username)
    if not user:
        return {'success': False, 'error': 'Неверный логин или пароль'}
    if not bcrypt.checkpw(password.encode(), user.password.encode()):
        return {'success': False, 'error': 'Неверный логин или пароль'}

    token = str(uuid.uuid4())
    import services.state as state
    state.create_session(token, user)
    return {'success': True, 'token': token, 'username': user.username}


def get_mikrotik_creds(username: str, device_name: str) -> dict:
    """Получить учётные данные микротика для пользователя"""
    from models.user import MikroTikCred
    cred = MikroTikCred.get_or_none(
        MikroTikCred.user.username == username,
        MikroTikCred.device_name == device_name,
    )
    if cred:
        return {'username': cred.username, 'password': cred.password}
    return {'username': 'nur001', 'password': ''}


def save_mikrotik_creds(username: str, device_name: str, mk_username: str, mk_password: str):
    """Сохранить учётные данные микротика"""
    from models.user import MikroTikCred
    user = User.get(User.username == username)
    cred, created = MikroTikCred.get_or_create(
        user=user, device_name=device_name,
        defaults={'username': mk_username, 'password': mk_password}
    )
    if not created:
        cred.username = mk_username
        cred.password = mk_password
        cred.save()


def list_users() -> dict:
    """Список всех пользователей"""
    users = []
    for u in User.select():
        users.append({
            'username': u.username,
            'created_at': u.created_at.strftime('%Y-%m-%d %H:%M') if u.created_at else '',
        })
    return {'success': True, 'users': users}


def delete_user(username: str) -> dict:
    """Удалить пользователя"""
    if username == 'admin':
        return {'success': False, 'error': 'Нельзя удалить администратора'}
    user = User.get_or_none(User.username == username)
    if not user:
        return {'success': False, 'error': 'Пользователь не найден'}
    user.delete_instance()
    return {'success': True, 'message': f'Пользователь {username} удалён'}


def change_password(username: str, password: str) -> dict:
    """Сменить пароль пользователя"""
    user = User.get_or_none(User.username == username)
    if not user:
        return {'success': False, 'error': 'Пользователь не найден'}
    user.password = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    user.save()
    return {'success': True, 'message': f'Пароль для {username} изменён'}


def get_profile(username: str) -> dict:
    """Получить профиль пользователя (Matrix/LLM конфиг + учётки микротиков)"""
    from models.user import MatrixConfig, MikroTikCred
    user = User.get(User.username == username)

    mc, _ = MatrixConfig.get_or_create(user=user)
    matrix = {
        'enabled': mc.enabled, 'token': mc.token, 'room_id': mc.room_id,
        'homeserver': mc.homeserver, 'matrix_user': mc.matrix_user or '',
        'llm_enabled': mc.llm_enabled, 'llm_key': mc.llm_key,
        'llm_url': mc.llm_url, 'parsing_mode': mc.parsing_mode, 'classify_enabled': mc.classify_enabled,
    }

    creds = []
    for c in MikroTikCred.select().where(MikroTikCred.user == user):
        creds.append({'device_name': c.device_name, 'username': c.username})

    return {'success': True, 'username': username, 'matrix': matrix, 'mikrotik_creds': creds}


def save_profile(username: str, data: dict) -> dict:
    """Сохранить Matrix/LLM конфиг пользователя"""
    from models.user import MatrixConfig
    user = User.get(User.username == username)
    mc, _ = MatrixConfig.get_or_create(user=user)

    if 'matrix_enabled' in data:
        mc.enabled = bool(data['matrix_enabled'])
    if 'matrix_token' in data:
        mc.token = data['matrix_token']
    if 'matrix_room' in data:
        mc.room_id = data['matrix_room']
    if 'matrix_homeserver' in data:
        mc.homeserver = data['matrix_homeserver']
    if 'llm_enabled' in data:
        mc.llm_enabled = bool(data['llm_enabled'])
    if 'llm_key' in data:
        mc.llm_key = data['llm_key']
    if 'llm_url' in data:
        mc.llm_url = data['llm_url']
    if 'parsing_mode' in data:
        mc.parsing_mode = data['parsing_mode']
    if 'classify_enabled' in data:
        mc.classify_enabled = bool(data['classify_enabled'])
    if 'matrix_user' in data:
        mc.matrix_user = data['matrix_user']
    if 'matrix_password' in data:
        mc.matrix_password = data['matrix_password']

    # Если пароль указан, а токена нет — логинимся в Matrix
    if mc.matrix_password and not mc.token:
        try:
            import asyncio
            async def _login():
                from nio import AsyncClient, LoginResponse
                client = AsyncClient(mc.homeserver or 'https://matrix.krasintegra.ru', mc.matrix_user or 'nur001')
                resp = await client.login(mc.matrix_password, device_name='mikrotik-manager')
                await client.close()
                return resp
            resp = asyncio.run(_login())
            from nio import LoginResponse
            if isinstance(resp, LoginResponse):
                mc.token = resp.access_token
                mc.matrix_password = ''  # очищаем пароль после успешного входа
        except Exception:
            pass  # оставляем пароль для повторной попытки

    mc.save()
    return {'success': True, 'message': 'Профиль сохранён'}
