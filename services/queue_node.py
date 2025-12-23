#!/usr/bin/env python3
"""
Модель для представления узла дерева очередей MikroTik
"""
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
import json


@dataclass
class QueueNode:
    """Модель узла дерева очередей"""
    id: str
    name: str
    target: str = ""
    max_limit: str = "не задан"
    dst_address: str = ""
    disabled: bool = False
    parent: Optional[str] = None
    comment: str = ""
    children: List['QueueNode'] = field(default_factory=list)
    is_parent: bool = False
    is_selectable: bool = False  # Можно ли выбрать (дочерние очереди)
    
    def to_dict(self) -> Dict[str, Any]:
        """Преобразование в словарь для JSON сериализации"""
        return {
            'id': self.id,
            'name': self.name,
            'target': self.target,
            'max_limit': self.max_limit,
            'dst_address': self.dst_address,
            'disabled': self.disabled,
            'parent': self.parent,
            'comment': self.comment,
            'is_parent': self.is_parent,
            'is_selectable': self.is_selectable,
            'children': [child.to_dict() for child in self.children]
        }
    
    @classmethod
    def from_mikrotik_data(cls, queue_data: Dict[str, str]) -> 'QueueNode':
        """Создание узла из данных MikroTik API"""
        return cls(
            id=queue_data.get('.id', ''),
            name=queue_data.get('name', ''),
            target=queue_data.get('target', ''),
            max_limit=queue_data.get('max-limit', 'не задан'),
            dst_address=queue_data.get('dst-address', ''),
            disabled=queue_data.get('disabled', 'false') == 'true',
            parent=queue_data.get('parent', ''),
            comment=queue_data.get('comment', '')
        )
    
    @classmethod
    def build_tree_from_queues(cls, queues: List[Dict[str, str]]) -> List['QueueNode']:
        """Построение дерева из списка очередей MikroTik"""
        if not queues:
            return []
        
        # Создаем узлы и маппинг по имени
        nodes_by_name = {}
        for queue in queues:
            node = cls.from_mikrotik_data(queue)
            nodes_by_name[node.name] = node
        
        # Строим иерархию (сначала находим все родительские)
        root_nodes = []
        
        # Первый проход: добавляем детей к родителям
        for node in list(nodes_by_name.values()):
            parent_name = node.parent
            if parent_name and parent_name in nodes_by_name:
                parent_node = nodes_by_name[parent_name]
                parent_node.children.append(node)
                parent_node.is_parent = True
            else:
                root_nodes.append(node)
        
        # Второй проход: определяем, какие узлы можно выбирать
        for node in nodes_by_name.values():
            # Можно выбрать только дочерние очереди (не родительские) без своих детей
            node.is_selectable = not node.is_parent and len(node.children) == 0
        
        return root_nodes
    
    def find_node_by_id(self, node_id: str) -> Optional['QueueNode']:
        """Поиск узла по ID в дереве"""
        if self.id == node_id:
            return self
        
        for child in self.children:
            found = child.find_node_by_id(node_id)
            if found:
                return found
        
        return None
    
    def get_all_selectable_nodes(self) -> List['QueueNode']:
        """Получение всех выбираемых узлов в дереве"""
        selectable_nodes = []
        
        if self.is_selectable:
            selectable_nodes.append(self)
        
        for child in self.children:
            selectable_nodes.extend(child.get_all_selectable_nodes())
        
        return selectable_nodes
    
    def print_tree(self, level: int = 0, prefix: str = ""):
        """Вывод дерева в консоль (для отладки)"""
        indent = "    " * level
        node_type = "📁" if self.is_parent else "📄"
        status = "✅" if not self.disabled else "⛔"
        
        if level == 0:
            print(f"{node_type} {self.name} {status}")
        else:
            print(f"{prefix}{indent}├── {node_type} {self.name} {status}")
        
        new_prefix = prefix + ("│   " if level > 0 else "")
        for i, child in enumerate(self.children):
            is_last = i == len(self.children) - 1
            child_prefix = "└── " if is_last else "├── "
            child.print_tree(level + 1, new_prefix + child_prefix)
