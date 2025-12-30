"""
Управление конфигурацией
"""

import configparser
import json
import os
import base64
import traceback

CONFIG_FILE = 'mikrotik_manager.conf'
NETBOX_CONFIG_FILE = 'netbox_config.json'  # Новый файл только для настроек NetBox
PASSWORDS_FILE = 'device_passwords.json'

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
                'default_username': 'admin'
            }
            with open(CONFIG_FILE, 'w') as f:
                config.write(f)
        
        return config
    
    @staticmethod
    def save_config(config):
        """Сохранить конфигурацию (старый формат)"""
        with open(CONFIG_FILE, 'w') as f:
            config.write(f)
    
    @staticmethod
    def load_netbox_config():
        """Загрузить конфигурацию NetBox"""
        default_config = {
            'url': 'http://localhost:8000',
            'token': '',
            'verify_ssl': True
        }
        
        if os.path.exists(NETBOX_CONFIG_FILE):
            try:
                with open(NETBOX_CONFIG_FILE, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    if content:
                        loaded_config = json.loads(content)
                        default_config.update(loaded_config)
            except Exception as e:
                print(f"⚠️  Ошибка загрузки конфигурации NetBox: {e}")
        
        return default_config
    
    @staticmethod
    def save_netbox_config(config):
        """Сохранить конфигурацию NetBox"""
        try:
            with open(NETBOX_CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"❌ Ошибка сохранения конфигурации NetBox: {e}")
    
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
    def load_passwords():
        """Загрузить пароли устройств"""
        if os.path.exists(PASSWORDS_FILE):
            try:
                with open(PASSWORDS_FILE, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    if content:
                        return json.loads(content)
            except Exception as e:
                print(f"⚠️  Ошибка загрузки паролей: {e}")
        return {}

    @staticmethod
    def save_passwords(passwords):
        """Сохранить пароли устройств"""
        try:
            with open(PASSWORDS_FILE, 'w', encoding='utf-8') as f:
                json.dump(passwords, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"❌ Ошибка сохранения паролей: {e}")

    @staticmethod
    def get_password(device_name):
        """Получить пароль устройства"""
        passwords = ConfigManager.load_passwords()
        encrypted_password = passwords.get(device_name, '')
        if encrypted_password:
            return ConfigManager.decrypt_password(encrypted_password)
        return ''

    @staticmethod
    def save_password(device_name, password):
        """Сохранить пароль устройства"""
        passwords = ConfigManager.load_passwords()
        if password:
            passwords[device_name] = ConfigManager.encrypt_password(password)
        else:
            # Если пустой пароль - удаляем запись
            passwords.pop(device_name, None)
    
        ConfigManager.save_passwords(passwords)
