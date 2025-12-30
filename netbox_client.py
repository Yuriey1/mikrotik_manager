"""
Клиент для работы с NetBox API
"""

import requests
import ipaddress
from typing import List, Dict, Optional, Any
from dataclasses import dataclass
from urllib.parse import urljoin


@dataclass
class NetBoxDevice:
    """Структура устройства из NetBox"""
    name: str
    ip_address: str
    port: int = 8728
    device_type: str = ""
    site: str = ""
    role: str = ""
    comments: str = ""


class NetBoxClient:
    """Клиент для работы с NetBox API"""
    
    def __init__(self, base_url: str, api_token: str, verify_ssl: bool = True):
        self.base_url = base_url.rstrip('/')
        self.api_token = api_token
        self.verify_ssl = verify_ssl
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Token {api_token}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        })
        
    def get_devices(self, filters: Optional[Dict] = None) -> List[NetBoxDevice]:
        """Получить список устройств MikroTik из NetBox"""
        try:
            url = urljoin(self.base_url, '/api/dcim/devices/')
            params = {'limit': 1000}
            
            # Фильтры по умолчанию для MikroTik
            default_filters = {
                'manufacturer': 'Mikrotik',
                'has_primary_ip': 'true'
            }
            
            if filters:
                default_filters.update(filters)
            
            params.update(default_filters)
            
            response = self.session.get(url, params=params, verify=self.verify_ssl)
            response.raise_for_status()
            
            devices_data = response.json().get('results', [])
            devices = []
            
            for device_data in devices_data:
                # Получаем IP адрес
                ip_address = ""
                if device_data.get('primary_ip'):
                    primary_ip = device_data['primary_ip']
                    if 'address' in primary_ip:
                        ip_str = primary_ip['address'].split('/')[0]
                        try:
                            ipaddress.ip_address(ip_str)
                            ip_address = ip_str
                        except ValueError:
                            continue
                
                if not ip_address:
                    continue
                
                # Получаем дополнительные данные
                device_type = device_data.get('device_type', {}).get('model', 'Unknown')
                site = device_data.get('site', {}).get('name', 'Unknown')
                role = device_data.get('device_role', {}).get('name', 'Unknown')
                comments = device_data.get('comments', '')
                
                # Получаем порт из custom_fields или используем по умолчанию
                port = 8728
                custom_fields = device_data.get('custom_fields', {})
                if 'api_port' in custom_fields and custom_fields['api_port']:
                    try:
                        port = int(custom_fields['api_port'])
                    except (ValueError, TypeError):
                        pass
                
                device = NetBoxDevice(
                    name=device_data.get('name', ''),
                    ip_address=ip_address,
                    port=port,
                    device_type=device_type,
                    site=site,
                    role=role,
                    comments=comments
                )
                
                devices.append(device)
            
            # Сортируем по алфавиту
            devices.sort(key=lambda x: x.name.lower())
            
            return devices
            
        except requests.RequestException as e:
            print(f"❌ Ошибка получения устройств из NetBox: {e}")
            return []
    
    def test_connection(self) -> bool:
        """Проверить соединение с NetBox"""
        try:
            url = urljoin(self.base_url, '/api/status/')
            response = self.session.get(url, verify=self.verify_ssl, timeout=5)
            return response.status_code == 200
        except:
            return False
