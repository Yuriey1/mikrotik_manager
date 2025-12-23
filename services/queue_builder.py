"""
Построитель дерева очередей
"""

from collections import defaultdict
from typing import Dict, List, Optional, Any
import ipaddress
import traceback
import re

from models.queue_node import QueueNode

class QueueTreeBuilder:
    def __init__(self, mikrotik_manager):
        self.manager = mikrotik_manager
        self.nodes: Dict[str, QueueNode] = {}
        self.root_nodes: List[QueueNode] = []
        self.queue_order: Dict[str, int] = {}  # Для сохранения порядка
        
    def build_tree(self) -> bool:
        """Построить дерево очередей"""
        try:
            print("📡 Загрузка очередей с MikroTik...")
            queues_raw = self.manager.get_queues()
            print(f"✅ Загружено {len(queues_raw)} очередей")
            
            # Сохраняем порядок как он пришел с устройства
            for index, queue_data in enumerate(queues_raw):
                queue_name = queue_data.get('name', '')
                if queue_name:
                    self.queue_order[queue_name] = index
            
            # Создаем все узлы
            for queue_data in queues_raw:
                self._create_node(queue_data)
            
            # Строим иерархию
            self._build_hierarchy()
            
            return True
            
        except Exception as e:
            print(f"❌ Ошибка построения дерева: {e}")
            traceback.print_exc()
            return False
    
    def _create_node(self, data: Dict) -> Optional[QueueNode]:
        """Создать узел из данных очереди"""
        try:
            name = data.get('name', '')
            if not name:
                return None
            
            # Парсим target
            target_raw = data.get('target', '')
            targets = []
            if isinstance(target_raw, str):
                for item in target_raw.split(','):
                    item = item.strip()
                    if item:
                        targets.append(item)
            else:
                targets = [str(target_raw)]
            
            # Считаем отдельные IP адреса
            ip_count = 0
            for target in targets:
                if '/' in target:
                    try:
                        network = ipaddress.ip_network(target, strict=False)
                        if network.prefixlen == 32:
                            ip_count += 1
                    except:
                        pass
            
            # Создаем узел
            node = QueueNode(
                id=data.get('.id', ''),
                name=name,
                enabled='X' not in data.get('flags', ''),
                target=targets,
                dst=data.get('dst', ''),
                parent=data.get('parent', 'none'),
                priority=data.get('priority', '8/8'),
                max_limit=data.get('max-limit', '0/0'),
                comment=data.get('comment', ''),
                packet_marks=data.get('packet-marks', ''),
                queue_type=data.get('queue', ''),
                ip_count=ip_count
            )
            
            self.nodes[name] = node
            return node
            
        except Exception as e:
            print(f"⚠️ Ошибка создания узла: {e}")
            traceback.print_exc()
            return None
    
    def _build_hierarchy(self):
        """Построить иерархию родитель-потомок"""
        # Группируем по родителям
        parent_map = defaultdict(list)
        for node in self.nodes.values():
            if node.parent and node.parent != 'none':
                parent_map[node.parent].append(node)
        
        # Сортируем детей по порядку их создания (как они идут в конфигурации)
        for parent_name, children in parent_map.items():
            # Сортируем по порядку, сохраненному при загрузке
            children.sort(key=lambda x: self.queue_order.get(x.name, 9999))
            parent_map[parent_name] = children
        
        # Строим дерево
        self.root_nodes = []
        
        # Находим корневые узлы (без родителей) и сортируем их по порядку
        root_candidates = []
        for node in self.nodes.values():
            if node.parent == 'none':
                root_candidates.append(node)
        
        # Сортируем корневые узлы по порядку
        root_candidates.sort(key=lambda x: self.queue_order.get(x.name, 9999))
        self.root_nodes = root_candidates
        
        # Рекурсивно устанавливаем уровни и детей
        for root in self.root_nodes:
            root.level = 0
            self._set_children_and_levels(root, parent_map, 0)
    
    def _set_children_and_levels(self, node: QueueNode, parent_map: Dict, level: int):
        """Рекурсивно установить детей и уровни"""
        if node.name in parent_map:
            children = parent_map[node.name]  # Уже отсортировано в _build_hierarchy
            for child in children:
                child.level = level + 1
                node.children.append(child)
                self._set_children_and_levels(child, parent_map, level + 1)
    
    def get_stats(self) -> Dict[str, Any]:
        """Получить статистику"""
        enabled_count = sum(1 for n in self.nodes.values() if n.enabled)
        total_ips = sum(n.ip_count for n in self.nodes.values())
        
        return {
            'total_queues': len(self.nodes),
            'enabled_queues': enabled_count,
            'disabled_queues': len(self.nodes) - enabled_count,
            'root_queues': len(self.root_nodes),
            'total_ips': total_ips
        }
    
    def get_tree_json(self) -> List[Dict]:
        """Получить дерево в формате JSON"""
        return [node.to_dict() for node in self.root_nodes]
    
    def find_suitable_queues_for_ip(self, ip: str) -> List[QueueNode]:
        """Найти подходящие очереди для IP"""
        suitable = []
        
        # Проверяем формат IP
        try:
            if '/' in ip:
                ipaddress.ip_network(ip, strict=False)
            else:
                ipaddress.ip_address(ip)
        except ValueError:
            return []
        
        # Проверяем все узлы в порядке их следования в конфигурации
        # Сортируем узлы по порядку
        sorted_nodes = sorted(self.nodes.values(), 
                            key=lambda x: self.queue_order.get(x.name, 9999))
        
        for node in sorted_nodes:
            if not node.enabled:
                continue
            
            # Проверяем, нет ли уже IP
            if node.has_ip(ip):
                continue
            
            # Если узел имеет детей, проверяем их тоже
            has_ip_in_children = False
            stack = list(node.children)
            while stack:
                child = stack.pop()
                if child.has_ip(ip):
                    has_ip_in_children = True
                    break
                stack.extend(child.children)
            
            if not has_ip_in_children:
                suitable.append(node)
        
        return suitable
