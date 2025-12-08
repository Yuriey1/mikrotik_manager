"""
Модель сотрудника
"""

from dataclasses import dataclass
from datetime import datetime

@dataclass
class Employee:
    """Сотрудник"""
    full_name: str
    position: str
    ip_address: str
    mac_address: str = ""
    internet_access: bool = False
    queue_assigned: str = ""
    
    def to_dict(self):
        """Преобразовать в словарь"""
        return {
            'full_name': self.full_name,
            'position': self.position,
            'ip_address': self.ip_address,
            'mac_address': self.mac_address,
            'internet_access': self.internet_access,
            'queue_assigned': self.queue_assigned,
            'date_added': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
