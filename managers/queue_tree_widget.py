from PyQt5 import QtCore, QtWidgets
from PyQt5.QtWidgets import (QTreeWidget, QTreeWidgetItem, QHeaderView, 
                             QMenu, QAction, QMessageBox)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont, QBrush, QColor
import librouteros


class QueueTreeWidget(QTreeWidget):
    """Виджет для отображения очередей MikroTik в виде дерева"""
    
    # Сигнал при выборе очереди
    queueSelected = pyqtSignal(list)  # Список выбранных ID
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        self.api = None
        
    def setup_ui(self):
        """Настройка внешнего вида виджета"""
        self.setHeaderLabels(['Очередь', 'Target/Интерфейс', 'Лимит', 'Статус', 'ID'])
        self.setColumnWidth(0, 250)
        self.setColumnWidth(1, 150)
        self.setColumnWidth(2, 120)
        self.setColumnWidth(3, 80)
        self.setColumnWidth(4, 0)  # Скрываем ID колонку
        
        # Настройка выбора
        self.setSelectionMode(QTreeWidget.MultiSelection)
        self.setAlternatingRowColors(True)
        
        # Настройка заголовков
        header = self.header()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        
        # Контекстное меню
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)
        
    def set_api_connection(self, api):
        """Установка соединения с API"""
        self.api = api
        
    def load_queues(self):
        """Загрузка очередей из MikroTik"""
        if not self.api:
            QMessageBox.warning(self, "Ошибка", "Нет соединения с MikroTik")
            return
            
        self.clear()
        
        try:
            # Получаем все simple queues
            queues = list(self.api.path('/queue/simple'))
            
            # Создаем структуру для древовидного отображения
            queue_dict = {}
            root_queues = []
            
            # Сначала создаем все элементы
            for queue in queues:
                queue_id = queue.get('.id', '')
                queue_name = queue.get('name', '')
                parent_name = queue.get('parent', '')
                
                item = QTreeWidgetItem()
                item.setText(0, queue_name)
                item.setText(1, queue.get('target', ''))
                item.setText(2, queue.get('max-limit', 'не задан'))
                item.setText(3, 'Активна' if queue.get('disabled', 'false') == 'false' else 'Отключена')
                item.setText(4, queue_id)  # ID в скрытой колонке
                
                # Настройка цвета в зависимости от статуса
                if queue.get('disabled', 'false') == 'true':
                    item.setForeground(3, QBrush(QColor(255, 0, 0)))
                else:
                    item.setForeground(3, QBrush(QColor(0, 150, 0)))
                
                # Добавляем чекбокс только для НЕродительских очередей
                # Определяем, является ли очередь родительской (имеет дочерние)
                has_children = any(q.get('parent') == queue_name for q in queues)
                
                if not has_children:
                    item.setCheckState(0, Qt.Unchecked)
                    item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                else:
                    # Для родительских очередей делаем жирный шрифт
                    font = item.font(0)
                    font.setBold(True)
                    item.setFont(0, font)
                    item.setBackground(0, QBrush(QColor(240, 240, 240)))
                    item.setFlags(item.flags() & ~Qt.ItemIsUserCheckable)
                
                queue_dict[queue_name] = {
                    'item': item,
                    'parent': parent_name,
                    'children': []
                }
            
            # Строим иерархию
            for queue_name, data in queue_dict.items():
                parent_name = data['parent']
                if parent_name and parent_name in queue_dict:
                    queue_dict[parent_name]['children'].append(data['item'])
                else:
                    root_queues.append(data['item'])
            
            # Добавляем элементы в дерево
            for root_item in root_queues:
                self.addTopLevelItem(root_item)
                self._add_children(root_item, queue_dict)
            
            # Разворачиваем все элементы для наглядности
            self.expandAll()
            
            # Обновляем список выбранных
            self._update_selection()
            
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось загрузить очереди: {str(e)}")
    
    def _add_children(self, parent_item, queue_dict):
        """Рекурсивно добавляет дочерние элементы"""
        queue_name = parent_item.text(0)
        if queue_name in queue_dict:
            for child_item in queue_dict[queue_name]['children']:
                parent_item.addChild(child_item)
                # Рекурсивно добавляем детей детей
                self._add_children(child_item, queue_dict)
    
    def get_selected_queues(self):
        """Возвращает список выбранных очередей"""
        selected_queues = []
        
        def traverse(item):
            # Проверяем, есть ли чекбокс и выбран ли он
            if item.flags() & Qt.ItemIsUserCheckable and item.checkState(0) == Qt.Checked:
                queue_info = {
                    'id': item.text(4),
                    'name': item.text(0),
                    'target': item.text(1),
                    'limit': item.text(2),
                    'status': item.text(3)
                }
                selected_queues.append(queue_info)
            
            # Рекурсивно проверяем детей
            for i in range(item.childCount()):
                traverse(item.child(i))
        
        # Начинаем с корневых элементов
        root = self.invisibleRootItem()
        for i in range(root.childCount()):
            traverse(root.child(i))
        
        return selected_queues
    
    def _update_selection(self):
        """Обновляет сигнал с выбранными очередями"""
        selected = self.get_selected_queues()
        self.queueSelected.emit([q['id'] for q in selected])
    
    def show_context_menu(self, position):
        """Показывает контекстное меню"""
        menu = QMenu()
        
        # Получаем элемент под курсором
        item = self.itemAt(position)
        if item:
            queue_id = item.text(4)
            queue_name = item.text(0)
            
            # Действия для конкретной очереди
            enable_action = QAction(f"Включить {queue_name}", self)
            disable_action = QAction(f"Отключить {queue_name}", self)
            remove_action = QAction(f"Удалить {queue_name}", self)
            info_action = QAction(f"Информация о {queue_name}", self)
            
            menu.addAction(info_action)
            menu.addSeparator()
            menu.addAction(enable_action)
            menu.addAction(disable_action)
            menu.addSeparator()
            menu.addAction(remove_action)
            
            # Подключаем действия
            enable_action.triggered.connect(lambda: self._toggle_queue(queue_id, True))
            disable_action.triggered.connect(lambda: self._toggle_queue(queue_id, False))
            remove_action.triggered.connect(lambda: self._remove_queue(queue_id))
            info_action.triggered.connect(lambda: self._show_queue_info(item))
        
        # Общие действия
        menu.addSeparator()
        select_all_action = QAction("Выбрать все доступные", self)
        deselect_all_action = QAction("Снять все выделения", self)
        refresh_action = QAction("Обновить список", self)
        
        menu.addAction(select_all_action)
        menu.addAction(deselect_all_action)
        menu.addSeparator()
        menu.addAction(refresh_action)
        
        select_all_action.triggered.connect(self.select_all_queues)
        deselect_all_action.triggered.connect(self.deselect_all_queues)
        refresh_action.triggered.connect(self.load_queues)
        
        menu.exec_(self.viewport().mapToGlobal(position))
    
    def select_all_queues(self):
        """Выбирает все доступные для выбора очереди"""
        def traverse(item):
            if item.flags() & Qt.ItemIsUserCheckable:
                item.setCheckState(0, Qt.Checked)
            for i in range(item.childCount()):
                traverse(item.child(i))
        
        root = self.invisibleRootItem()
        for i in range(root.childCount()):
            traverse(root.child(i))
        
        self._update_selection()
    
    def deselect_all_queues(self):
        """Снимает выделение со всех очередей"""
        def traverse(item):
            if item.flags() & Qt.ItemIsUserCheckable:
                item.setCheckState(0, Qt.Unchecked)
            for i in range(item.childCount()):
                traverse(item.child(i))
        
        root = self.invisibleRootItem()
        for i in range(root.childCount()):
            traverse(root.child(i))
        
        self._update_selection()
    
    def _toggle_queue(self, queue_id, enable):
        """Включение/выключение очереди"""
        if not self.api:
            return
            
        try:
            if enable:
                self.api.path('/queue/simple').remove(queue_id)
                self.api.path('/queue/simple').add(**{'.id': queue_id, 'disabled': 'no'})
            else:
                self.api.path('/queue/simple').remove(queue_id)
                self.api.path('/queue/simple').add(**{'.id': queue_id, 'disabled': 'yes'})
            
            self.load_queues()  # Перезагружаем список
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось изменить статус: {str(e)}")
    
    def _remove_queue(self, queue_id):
        """Удаление очереди"""
        if not self.api:
            return
            
        reply = QMessageBox.question(
            self, 'Подтверждение',
            'Вы уверены, что хотите удалить эту очередь?',
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                self.api.path('/queue/simple').remove(queue_id)
                self.load_queues()  # Перезагружаем список
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось удалить очередь: {str(e)}")
    
    def _show_queue_info(self, item):
        """Показывает подробную информацию об очереди"""
        info_text = f"""
        <b>Информация об очереди:</b><br><br>
        <b>Имя:</b> {item.text(0)}<br>
        <b>Target/Интерфейс:</b> {item.text(1)}<br>
        <b>Лимит:</b> {item.text(2)}<br>
        <b>Статус:</b> {item.text(3)}<br>
        <b>ID:</b> {item.text(4)}<br>
        """
        
        QMessageBox.information(self, "Информация об очереди", info_text)
