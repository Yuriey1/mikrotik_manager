"""SQLite модели для многопользовательской архитектуры"""

import os
import datetime
from peewee import Model, CharField, BooleanField, ForeignKeyField, DateTimeField, SqliteDatabase

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'users.db')
db = SqliteDatabase(DB_PATH, pragmas={'journal_mode': 'wal', 'foreign_keys': 1})


class BaseModel(Model):
    class Meta:
        database = db


class User(BaseModel):
    """Пользователь веб-приложения"""
    username = CharField(unique=True, max_length=64)
    password = CharField(max_length=128)  # bcrypt hash
    created_at = DateTimeField(default=datetime.datetime.now)


class MikroTikCred(BaseModel):
    """Учётные данные микротиков (у каждого админа свои)"""
    user = ForeignKeyField(User, backref='mikrotik_creds')
    device_name = CharField(max_length=128)
    username = CharField(max_length=64, default='nur001')
    password = CharField(max_length=256, default='')  # base64 encrypted

    class Meta:
        indexes = (
            (('user', 'device_name'), True),  # UNIQUE
        )


class MatrixConfig(BaseModel):
    """Настройки Matrix + LLM (на пользователя)"""
    user = ForeignKeyField(User, backref='matrix_config', unique=True)
    enabled = BooleanField(default=False)
    token = CharField(max_length=256, default='')
    room_id = CharField(max_length=128, default='')
    matrix_user = CharField(max_length=64, default='')
    matrix_password = CharField(max_length=128, default='')
    homeserver = CharField(max_length=128, default='')
    llm_enabled = BooleanField(default=False)
    llm_key = CharField(max_length=256, default='')
    llm_url = CharField(max_length=256, default='')
    parsing_mode = CharField(max_length=16, default='regex')
    classify_enabled = BooleanField(default=False)


def init_db():
    """Создать таблицы если их нет"""
    db.connect()
    db.create_tables([User, MikroTikCred, MatrixConfig], safe=True)

    # Создать пользователя по умолчанию если таблица пуста
    if User.select().count() == 0:
        import bcrypt
        User.create(
            username='admin',
            password=bcrypt.hashpw('admin'.encode(), bcrypt.gensalt()).decode()
        )

    # Миграция: перенести учётки из device_passwords.json если таблица пуста
    if MikroTikCred.select().count() == 0:
        _migrate_from_json()

    db.close()


def _migrate_from_json():
    """Перенести учётки из device_passwords.json в БД"""
    import json
    path = os.path.join(os.path.dirname(__file__), '..', 'device_passwords.json')
    if not os.path.exists(path):
        return
    try:
        with open(path, encoding='utf-8') as f:
            creds = json.load(f)
        admin = User.get_or_none(User.username == 'admin')
        if not admin:
            return
        for device_name, data in creds.items():
            if isinstance(data, dict):
                MikroTikCred.create(
                    user=admin,
                    device_name=device_name,
                    username=data.get('username', 'nur001'),
                    password=data.get('password', ''),
                )
        print(f"Миграция: перенесено {len(creds)} учёток из device_passwords.json")
    except Exception as e:
        print(f"Миграция учёток не удалась: {e}")
