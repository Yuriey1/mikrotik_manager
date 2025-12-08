"""
Модель устройства MikroTik
"""

from dataclasses import dataclass

@dataclass
class MikroTikDevice:
    """Устройство MikroTik"""
    name: str
    ip: str
    port: int = 8728
    username: str = "admin"
    password: str = ""
    description: str = ""
    
    def to_dict(self):
        """Преобразовать в словарь"""
        return {
            'name': self.name,
            'ip': self.ip,
            'port': self.port,
            'username': self.username,
            'password': self.password,
            'description': self.description
        }
    
    @classmethod
    def from_dict(cls, data):
        """Создать из словаря"""
        return cls(
            name=data['name'],
            ip=data['ip'],
            port=data.get('port', 8728),
            username=data.get('username', 'admin'),
            password=data.get('password', ''),
            description=data.get('description', '')
        )
