"""
Модель узла дерева очередей
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any
import ipaddress

@dataclass
class QueueNode:
    """Узел дерева очередей"""
    id: str
    name: str
    enabled: bool
    target: List[str] = field(default_factory=list)
    dst: str = ""
    parent: str = ""
    priority: str = ""
    max_limit: str = ""
    comment: str = ""
    packet_marks: str = ""
    queue_type: str = ""
    ip_count: int = 0
    children: List['QueueNode'] = field(default_factory=list)
    level: int = 0
    
    @property
    def short_target(self) -> str:
        """Краткое отображение target"""
        if not self.target:
            return ""
        result = []
        for t in self.target:
            if len(t) > 30:
                result.append(t[:27] + "...")
            else:
                result.append(t)
        return ", ".join(result)
    
    @property
    def short_dst(self) -> str:
        """Краткое отображение dst"""
        if not self.dst:
            return ""
        if len(self.dst) > 30:
            return self.dst[:27] + "..."
        return self.dst
    
    def to_dict(self) -> Dict[str, Any]:
        """Преобразовать узел в словарь для JSON"""
        return {
            'id': self.id,
            'name': self.name,
            'enabled': self.enabled,
            'target': self.target,
            'short_target': self.short_target,
            'dst': self.dst,
            'short_dst': self.short_dst,
            'parent': self.parent,
            'priority': self.priority,
            'max_limit': self.max_limit,
            'comment': self.comment,
            'packet_marks': self.packet_marks,
            'queue_type': self.queue_type,
            'ip_count': self.ip_count,
            'level': self.level,
            'has_children': len(self.children) > 0,
            'children': [child.to_dict() for child in self.children]
        }
    
    def has_ip(self, ip: str) -> bool:
        """Проверить, есть ли IP в узле"""
        for target_str in self.target:
            for item in target_str.split(','):
                item = item.strip()
                if not item or '/' not in item:
                    continue
                
                try:
                    if '/' in ip:
                        if ipaddress.ip_network(ip, strict=False).subnet_of(
                            ipaddress.ip_network(item, strict=False)):
                            return True
                    else:
                        if ipaddress.ip_address(ip) in ipaddress.ip_network(item, strict=False):
                            return True
                except:
                    continue
        return False
