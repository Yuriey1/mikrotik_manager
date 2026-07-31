"""
Управление конфигурацией
"""

import configparser
import json
import os
import base64
import traceback
import logging

CONFIG_FILE = 'mikrotik_manager.conf'
NETBOX_CONFIG_FILE = 'netbox_config.json'


class ConfigManager:
    """Менеджер конфигурации"""
    
    @staticmethod
    def load_config():
        """Загрузить конфигурацию (старый формат)"""
        config = configparser.ConfigParser()
        if os.path.exists(CONFIG_FILE):
            config.read(CONFIG_FILE)
        else:
            config['DEFAULT'] = {
                'last_device': '',
                'auto_save_password': 'false',
                'default_username': 'nur001'
            }
            with open(CONFIG_FILE, 'w') as f:
                config.write(f)
        return config
    
    @staticmethod
    def get_default_username():
        """Получить имя пользователя по умолчанию"""
        config = ConfigManager.load_config()
        return config['DEFAULT'].get('default_username', 'nur001')
    
    @staticmethod
    def save_config(config):
        """Сохранить конфигурацию"""
        with open(CONFIG_FILE, 'w') as f:
            config.write(f)
    
    @staticmethod
    def load_netbox_config():
        """Загрузить конфигурацию NetBox"""
        default_config = {'url': 'http://localhost:8000', 'token': '', 'verify_ssl': True}
        if os.path.exists(NETBOX_CONFIG_FILE):
            try:
                with open(NETBOX_CONFIG_FILE, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    if content:
                        loaded_config = json.loads(content)
                        default_config.update(loaded_config)
            except Exception as e:
                logging.warning("⚠️  Ошибка загрузки конфигурации NetBox: %s", e)
        return default_config
    
    @staticmethod
    def save_netbox_config(config):
        """Сохранить конфигурацию NetBox"""
        try:
            with open(NETBOX_CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logging.error("❌ Ошибка сохранения конфигурации NetBox: %s", e)
    
    @staticmethod
    def encrypt_password(password):
        """Шифрование пароля"""
        if not password:
            return ''
        return base64.b64encode(password.encode()).decode()
    
    @staticmethod
    def decrypt_password(encrypted):
        """Расшифровка пароля"""
        if not encrypted:
            return ''
        try:
            return base64.b64decode(encrypted.encode()).decode()
        except:
            return ''

    @staticmethod
    def get_credentials(device_name, web_user=None):
        """Получить учётные данные устройства из БД"""
        default_user = ConfigManager.get_default_username()
        username = web_user or None
        if not username:
            return {'username': ConfigManager.get_default_username(), 'password': ''}
        try:
            from models.user import MikroTikCred, User
            user = User.get_or_none(User.username == username)
            if user:
                cred = MikroTikCred.get_or_none(
                    MikroTikCred.user == user,
                    MikroTikCred.device_name == device_name,
                )
                if cred and cred.password:
                    return {
                        'username': cred.username or default_user,
                        'password': ConfigManager.decrypt_password(cred.password)
                    }
        except Exception as e:
            logging.warning("DB creds lookup failed for %s/%s: %s", username, device_name, e)
        return {'username': default_user, 'password': ''}

    @staticmethod
    def save_credentials(device_name, username, password, web_user=None):
        """Сохранить учётные данные в БД"""
        web_user = web_user or None
        if not web_user:
            return
        try:
            from models.user import MikroTikCred, User
            user = User.get(User.username == web_user)
            if username or password:
                cred, created = MikroTikCred.get_or_create(
                    user=user, device_name=device_name,
                    defaults={'username': username or 'nur001', 'password': ''}
                )
                cred.username = username if username else cred.username
                cred.password = ConfigManager.encrypt_password(password) if password else cred.password
                cred.save()
            else:
                MikroTikCred.delete().where(
                    MikroTikCred.user == user,
                    MikroTikCred.device_name == device_name
                ).execute()
        except Exception as e:
            logging.warning("DB creds save failed: %s", e)
