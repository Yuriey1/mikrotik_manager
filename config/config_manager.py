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
                'default_username': 'nur001'  # ← ИЗМЕНЕНО: теперь nur001 по умолчанию
            }
            with open(CONFIG_FILE, 'w') as f:
                config.write(f)
        
        return config
    
    @staticmethod
    def get_default_username():
        """Получить имя пользователя по умолчанию из конфига"""
        config = ConfigManager.load_config()
        return config['DEFAULT'].get('default_username', 'nur001')
    
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
    def load_credentials():
        """Загрузить логины и пароли устройств"""
        if os.path.exists(PASSWORDS_FILE):
            try:
                with open(PASSWORDS_FILE, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    if content:
                        data = json.loads(content)
                        
                        # Проверяем старый формат (только пароли в виде строк)
                        if isinstance(data, dict) and all(isinstance(v, str) for v in data.values()):
                            # Конвертируем старый формат в новый
                            new_data = {}
                            default_username = ConfigManager.get_default_username()
                            
                            for device_name, password in data.items():
                                new_data[device_name] = {
                                    'username': default_username,
                                    'password': password
                                }
                            
                            # Сохраняем в новом формате
                            ConfigManager.save_credentials_dict(new_data)
                            print(f"🔄 Конвертирован старый формат паролей в новый (логины: {default_username})")
                            return new_data
                        
                        return data
            except Exception as e:
                print(f"⚠️  Ошибка загрузки учетных данных: {e}")
                traceback.print_exc()
        return {}
    
    @staticmethod
    def save_credentials_dict(credentials):
        """Сохранить словарь учетных данных"""
        try:
            with open(PASSWORDS_FILE, 'w', encoding='utf-8') as f:
                json.dump(credentials, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"❌ Ошибка сохранения учетных данных: {e}")
    
    @staticmethod
    def get_credentials(device_name):
        """Получить логин и пароль устройства"""
        credentials = ConfigManager.load_credentials()
        device_creds = credentials.get(device_name, {'username': '', 'password': ''})
        
        # Если нашли учетные данные
        if device_creds:
            return {
                'username': device_creds.get('username', ConfigManager.get_default_username()),
                'password': ConfigManager.decrypt_password(device_creds.get('password', ''))
            }
        
        # Если ничего не нашли
        return {
            'username': ConfigManager.get_default_username(),
            'password': ''
        }
    
    @staticmethod
    def save_credentials(device_name, username, password):
        """Сохранить логин и пароль устройства"""
        credentials = ConfigManager.load_credentials()
        
        if username or password:
            credentials[device_name] = {
                'username': username if username else ConfigManager.get_default_username(),
                'password': ConfigManager.encrypt_password(password) if password else ''
            }
        else:
            # Если оба пустые - удаляем запись
            credentials.pop(device_name, None)
        
        ConfigManager.save_credentials_dict(credentials)
        print(f"💾 Сохранены учетные данные для {device_name}: логин={username}")
    
    # ↓↓↓ Старые методы для обратной совместимости ↓↓↓
    
    @staticmethod
    def load_passwords():
        """Загрузить пароли устройств (старый метод для обратной совместимости)"""
        credentials = ConfigManager.load_credentials()
        passwords = {}
        
        for device_name, creds in credentials.items():
            passwords[device_name] = creds.get('password', '')
        
        return passwords
    
    @staticmethod
    def save_passwords(passwords):
        """Сохранить пароли устройств (старый метод для обратной совместимости)"""
        credentials = ConfigManager.load_credentials()
        default_username = ConfigManager.get_default_username()
        
        for device_name, password in passwords.items():
            if device_name in credentials:
                # Обновляем только пароль
                credentials[device_name]['password'] = password
            else:
                # Создаем новую запись с дефолтным логином
                credentials[device_name] = {
                    'username': default_username,
                    'password': password
                }
        
        ConfigManager.save_credentials_dict(credentials)
    
    @staticmethod
    def get_password(device_name):
        """Получить пароль устройства (старый метод для обратной совместимости)"""
        creds = ConfigManager.get_credentials(device_name)
        return creds['password']
    
    @staticmethod
    def save_password(device_name, password):
        """Сохранить пароль устройства (старый метод для обратной совместимости)"""
        creds = ConfigManager.get_credentials(device_name)
        ConfigManager.save_credentials(device_name, creds['username'], password)
