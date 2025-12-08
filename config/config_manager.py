"""
Управление конфигурацией и хранение данных
"""

import configparser
import json
import os
import base64
import traceback

CONFIG_FILE = 'mikrotik_manager.conf'
DEVICES_FILE = 'devices.json'
EMPLOYEES_FILE = 'employees.json'

class ConfigManager:
    """Менеджер конфигурации"""
    
    @staticmethod
    def load_config():
        """Загрузить конфигурацию"""
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
        """Сохранить конфигурацию"""
        with open(CONFIG_FILE, 'w') as f:
            config.write(f)
    
    @staticmethod
    def load_devices():
        """Загрузить список устройств"""
        if os.path.exists(DEVICES_FILE):
            try:
                with open(DEVICES_FILE, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    if content:
                        return json.loads(content)
                    else:
                        return {}
            except Exception as e:
                print(f"❌ Ошибка загрузки файла устройств: {e}")
                traceback.print_exc()
                return {}
        return {}
    
    @staticmethod
    def save_devices(devices):
        """Сохранить список устройств"""
        with open(DEVICES_FILE, 'w', encoding='utf-8') as f:
            json.dump(devices, f, ensure_ascii=False, indent=2)
    
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
