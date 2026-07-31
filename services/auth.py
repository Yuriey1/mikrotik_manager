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
