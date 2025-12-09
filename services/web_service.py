"""
HTTP сервер и обработчики запросов
"""

from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import json
import traceback
import os
import re
import ipaddress
from typing import Optional

from config.config_manager import ConfigManager
from models.device import MikroTikDevice
from models.employee import Employee
from managers.mikrotik_manager import MikroTikManager
from services.queue_builder import QueueTreeBuilder
from utils.helpers import russian_to_mikrotik_comment

# Глобальные переменные
mikrotik_manager = None
tree_builder = None
current_device_name = None  # ← Добавим для отслеживания текущего устройства

class StoppableHTTPServer(HTTPServer):
    """HTTP сервер с возможностью корректной остановки"""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._is_running = True
    
    def serve_forever(self, poll_interval=0.5):
        """Переопределенный метод для корректной остановки"""
        while self._is_running:
            try:
                self.handle_request()
            except (KeyboardInterrupt, SystemExit):
                print("\n⚠️  Получен сигнал прерывания")
                self._is_running = False
                break
            except Exception as e:
                if self._is_running:
                    print(f"⚠️  Ошибка обработки запроса: {e}")
    
    def shutdown(self):
        """Остановка сервера"""
        self._is_running = False
        try:
            self.socket.close()
        except:
            pass

class MikroTikManagerHandler(BaseHTTPRequestHandler):
    def _set_headers(self, content_type='text/html'):
        """Установить заголовки ответа"""
        self.send_response(200)
        self.send_header('Content-Type', f'{content_type}; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS, PUT, DELETE')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization, X-Requested-With')
        self.send_header('Access-Control-Allow-Credentials', 'true')
        self.end_headers()
    
    def do_OPTIONS(self):
        """Обработка OPTIONS запросов для CORS"""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
    
    def do_GET(self):
        """Обработка GET запросов"""
        try:
            parsed = urlparse(self.path)
            path = parsed.path
        
            if path == '/' or path == '/index.html':
                self._serve_html()
            elif path == '/api/devices':
                self._serve_devices()
            elif path == '/api/connect':
                self._connect_device(parsed)
            elif path == '/api/disconnect':  # ← НОВЫЙ ENDPOINT!
                self._disconnect_api()
            elif path == '/api/tree':
                self._serve_tree()
            elif path == '/api/stats':
                self._serve_stats()
            elif path == '/api/find_queues':
                self._find_queues(parsed)
            elif path == '/api/check_dhcp':
                self._check_dhcp(parsed)
            # =====  ЭТА СТРОКА ДЛЯ CSS/JS =====
            elif path.startswith('/static/'):
                self._serve_static_file(path)
            # =========================================
            else:
                self.send_error(404, "Not Found")
                
        except Exception as e:
            print(f"❌ Ошибка обработки GET запроса: {e}")
            self._send_json({'error': str(e)}, 500)

    def _disconnect_api(self):
        """API метод для отключения"""
        global current_device_name
    
        if not current_device_name:
            self._send_json({
                'success': True,
                'message': 'Нет активных подключений',
                'action': 'already_disconnected'
            })
            return
    
        device_name_to_disconnect = current_device_name
        self._disconnect_current_device()
    
        self._send_json({
            'success': True,
            'message': f'Отключено от {device_name_to_disconnect}',
            'action': 'disconnected'
        })
    
    def do_POST(self):
        """Обработка POST запросов"""
        try:
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))
            
            parsed = urlparse(self.path)
            path = parsed.path
            
            if path == '/api/add_device':
                self._add_device(data)
            elif path == '/api/add_employee':
                self._add_employee(data)
            elif path == '/api/save_config':
                self._save_config(data)
            else:
                self.send_error(404, "Not Found")
                
        except Exception as e:
            print(f"❌ Ошибка обработки POST запроса: {e}")
            self._send_json({'error': str(e)}, 500)
    
    def _serve_html(self):
        """Отдать HTML интерфейс"""
        html = self._get_html_template()
        self._set_headers('text/html')
        self.wfile.write(html.encode('utf-8'))
    
    def _serve_devices(self):
        """Отдать список устройств"""
        try:
            devices = ConfigManager.load_devices()
            print(f"📊 Загружено устройств: {len(devices)}")
            
            # Не отправляем пароли клиенту
            safe_devices = {}
            for name, device in devices.items():
                safe_device = device.copy()
                if 'password' in safe_device:
                    safe_device['password'] = ''  # Не отправляем пароль клиенту
                safe_devices[name] = safe_device
            
            self._send_json({'devices': safe_devices})
        except Exception as e:
            print(f"❌ Ошибка в _serve_devices: {e}")
            traceback.print_exc()
            self._send_json({'error': str(e)}, 500)
    
    def _connect_device(self, parsed):
        """Подключиться к устройству (с отключением от предыдущего)"""
        global mikrotik_manager, tree_builder, current_device_name
    
        query = parse_qs(parsed.query)
        device_name = query.get('device', [''])[0]
    
        if not device_name:
            self._send_json({'error': 'Не указано устройство'}, 400)
            return
    
        devices = ConfigManager.load_devices()
        device_data = devices.get(device_name)
    
        if not device_data:
            self._send_json({'error': 'Устройство не найдено'}, 404)
            return
    
        # Проверяем, не пытаемся ли подключиться к уже подключенному устройству
        if current_device_name == device_name and mikrotik_manager and mikrotik_manager.connected:
            print(f"⚠️  Уже подключены к {device_name}, отключаем...")
            self._disconnect_current_device()
            self._send_json({
                'success': True,
                'device': '',
                'message': f'Отключено от {device_name}',
                'action': 'disconnected'
            })
            return
    
        # Отключаемся от предыдущего устройства, если подключены
        if mikrotik_manager and mikrotik_manager.connected:
            print(f"🔌 Отключаемся от предыдущего устройства ({current_device_name})...")
            self._disconnect_current_device()
    
        # Создаем менеджер и подключаемся
        device = MikroTikDevice.from_dict(device_data)
        mikrotik_manager = MikroTikManager(device)
    
        if mikrotik_manager.connect():
            # Сохраняем имя текущего устройства
            current_device_name = device_name
        
            # Строим дерево очередей
            tree_builder = QueueTreeBuilder(mikrotik_manager)
            tree_builder.build_tree()
        
            self._send_json({
                'success': True,
                'device': device_name,
                'message': f'Подключено к {device.ip}',
                'action': 'connected'
            })
        else:
            current_device_name = None
            self._send_json({
                'success': False,
                'error': 'Не удалось подключиться'
            })


    def _disconnect_current_device(self):
        """Отключиться от текущего устройства"""
        global mikrotik_manager, tree_builder, current_device_name
    
        try:
            if mikrotik_manager:
                print(f"🔌 Отключение от {current_device_name}...")
                mikrotik_manager.disconnect()
                mikrotik_manager = None
        
            if tree_builder:
                tree_builder = None
        
            current_device_name = None
            print("✅ Успешно отключено")
        
        except Exception as e:
            print(f"⚠️  Ошибка при отключении: {e}")
    
    def _serve_tree(self):
        """Отдать дерево очередей"""
        global tree_builder
        if not tree_builder or not mikrotik_manager or not mikrotik_manager.connected:
            self._send_json({'error': 'Не подключено к устройству'}, 400)
            return
    
        tree_data = tree_builder.get_tree_json()
        stats = tree_builder.get_stats()
    
        self._send_json({
            'success': True,
            'tree': tree_data,
            'stats': stats
        })

    def _serve_stats(self):
        """Отдать статистику"""
        global tree_builder
        if not tree_builder or not mikrotik_manager or not mikrotik_manager.connected:
            self._send_json({'error': 'Не подключено к устройству'}, 400)
            return
    
        stats = tree_builder.get_stats()
        self._send_json(stats)
    
    def _find_queues(self, parsed):
        """Найти очереди для IP"""
        global tree_builder
        if not tree_builder:
            self._send_json({'error': 'Не подключено к устройству'}, 400)
            return
        
        query = parse_qs(parsed.query)
        ip = query.get('ip', [''])[0].strip()
        
        if not ip:
            self._send_json({'error': 'IP не указан'}, 400)
            return
        
        try:
            if '/' in ip:
                ipaddress.ip_network(ip, strict=False)
            else:
                ipaddress.ip_address(ip)
        except ValueError:
            self._send_json({'error': 'Неверный формат IP'}, 400)
            return
        
        # Находим очереди, где уже есть IP
        existing = []
        for node in tree_builder.nodes.values():
            if node.has_ip(ip):
                existing.append(node.name)
        
        # Находим подходящие очереди
        suitable = tree_builder.find_suitable_queues_for_ip(ip)
        suitable_dicts = [node.to_dict() for node in suitable]
        
        self._send_json({
            'success': True,
            'existing': existing,
            'queues': suitable_dicts,
            'count': len(suitable)
        })
    
    def _check_dhcp(self, parsed):
        """Проверить DHCP lease"""
        global mikrotik_manager
        if not mikrotik_manager:
            self._send_json({'error': 'Не подключено к устройству'}, 400)
            return
        
        query = parse_qs(parsed.query)
        ip = query.get('ip', [''])[0].strip()
        mac = query.get('mac', [''])[0].strip()
        
        if not ip and not mac:
            self._send_json({'error': 'Укажите IP или MAC'}, 400)
            return
        
        lease = mikrotik_manager.find_dhcp_lease(ip=ip, mac=mac)
        
        if lease:
            self._send_json({
                'success': True,
                'found': True,
                'lease': {
                    'ip': lease.get('address'),
                    'mac': lease.get('mac-address'),
                    'status': 'dynamic' if lease.get('dynamic') == 'true' else 'static',
                    'comment': lease.get('comment', '')
                }
            })
        else:
            self._send_json({
                'success': True,
                'found': False
            })
    
    def _serve_static_file(self, path):
        """Отдать статический файл (CSS, JS)"""
        try:
            # Убираем ведущий слеш
            if path.startswith('/'):
                path = path[1:]
        
            # Проверяем существование файла
            if not os.path.exists(path):
                self.send_error(404, f"File not found: {path}")
                return
        
            # Определяем Content-Type
            content_type = 'text/plain'
            if path.endswith('.css'):
                content_type = 'text/css; charset=utf-8'
            elif path.endswith('.js'):
                content_type = 'application/javascript; charset=utf-8'
            elif path.endswith('.png'):
                content_type = 'image/png'
        
            # Читаем файл
            with open(path, 'rb') as f:
                content = f.read()
        
            # Отправляем
            self.send_response(200)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        
        except Exception as e:
            print(f"❌ Ошибка отдачи статического файла {path}: {e}")
            self.send_error(500, str(e))

    def _add_device(self, data):
        """Добавить устройство"""
        try:
            name = data.get('name', '').strip()
            ip = data.get('ip', '').strip()
            username = data.get('username', 'admin').strip()
            password = data.get('password', '').strip()
            description = data.get('description', '').strip()
            save_password = data.get('savePassword', False)
            
            if not name or not ip:
                self._send_json({'error': 'Заполните имя и IP'}, 400)
                return
            
            # Шифруем пароль если он есть и нужно сохранять
            encrypted_password = ''
            if password and save_password:
                encrypted_password = 'enc:' + ConfigManager.encrypt_password(password)
            
            # Загружаем существующие устройства
            devices = ConfigManager.load_devices()
            
            # Добавляем новое устройство
            devices[name] = {
                'name': name,
                'ip': ip,
                'port': data.get('port', 8728),
                'username': username,
                'password': encrypted_password,
                'description': description
            }
            
            # Сохраняем
            ConfigManager.save_devices(devices)
            
            self._send_json({
                'success': True,
                'message': f'Устройство {name} добавлено'
            })
            
        except Exception as e:
            self._send_json({'error': str(e)}, 500)
    
    def _add_employee(self, data):
        """Добавить сотрудника (полный процесс)"""
        global mikrotik_manager, tree_builder
    
        print(f"\n" + "="*50)
        print("👤 ДОБАВЛЕНИЕ СОТРУДНИКА")
        print(f"📝 Полученные данные: {data}")
        print("="*50)
    
        if not mikrotik_manager:
            print("❌ Ошибка: mikrotik_manager не подключен")
            self._send_json({'error': 'Не подключено к устройству'}, 400)
            return
    
        try:
            # Получаем данные
            full_name = data.get('full_name', '').strip()
            position = data.get('position', '').strip()
            ip = data.get('ip', '').strip()
            mac = data.get('mac', '').strip()
            internet_access = bool(data.get('internet_access', False))
            queue_name = data.get('queue', '').strip()
        
            print(f"🔍 Парсинг данных:")
            print(f"  ФИО: {full_name}")
            print(f"  Должность: {position}")
            print(f"  IP: {ip}")
            print(f"  MAC: {mac}")
            print(f"  Интернет доступ: {internet_access}")
            print(f"  Очередь: {queue_name}")
        
            if not full_name or not position or not ip:
                error_msg = 'Заполните обязательные поля'
                print(f"❌ {error_msg}")
                self._send_json({'error': error_msg}, 400)
                return
        
            # Проверяем формат IP
            try:
                ipaddress.ip_address(ip)
                print(f"✅ IP адрес валиден: {ip}")
            except ValueError:
                error_msg = 'Неверный формат IP'
                print(f"❌ {error_msg}")
                self._send_json({'error': error_msg}, 400)
                return
        
            # Проверяем формат MAC
            if mac:
                mac_pattern = re.compile(r'^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$')
                if not mac_pattern.match(mac):
                    error_msg = 'Неверный формат MAC'
                    print(f"❌ {error_msg}")
                    self._send_json({'error': error_msg}, 400)
                    return
                # Приводим к формату MikroTik (через двоеточие)
                mac = ':'.join(mac.replace('-', ':').split(':')).lower()
                print(f"✅ MAC адрес приведен: {mac}")
        
            # Создаем комментарий
            comment = f"{position} - {full_name}"
            print(f"📝 Комментарий: {comment}")
        
            results = {
                'dhcp': False,
                'arp': False,
                'queue': False,
                'firewall': False
            }
        
            # 1. DHCP Lease
            if mac:
                print(f"🔧 Создание DHCP lease для {ip} -> {mac}")
                results['dhcp'] = mikrotik_manager.create_static_lease(ip, mac, comment)
                print(f"   Результат DHCP: {results['dhcp']}")
            else:
                results['dhcp'] = True  # Пропускаем если нет MAC
                print(f"⚠️  MAC не указан, пропускаем DHCP")
        
            # 2. ARP таблица
            if mac:
                print(f"🔧 Добавление ARP записи для {ip} -> {mac}")
                results['arp'] = mikrotik_manager.add_static_arp(ip, mac, comment)
                print(f"   Результат ARP: {results['arp']}")
            else:
                results['arp'] = True
                print(f"⚠️  MAC не указан, пропускаем ARP")
        
            # 3. Очередь
            if queue_name:
                print(f"🔧 Поиск очереди '{queue_name}'...")
                # Находим ID очереди
                queue_id = None
                for node in tree_builder.nodes.values():
                    if node.name == queue_name:
                        queue_id = node.id
                        break
            
                if queue_id:
                    print(f"🔧 Добавление IP {ip} в очередь {queue_name} (ID: {queue_id})")
                    results['queue'] = mikrotik_manager.add_ip_to_queue(queue_id, ip)
                    print(f"   Результат очереди: {results['queue']}")
                else:
                    print(f"❌ Очередь '{queue_name}' не найдена")
                    results['queue'] = False
            else:
                results['queue'] = True
                print(f"⚠️  Очередь не указана, пропускаем")
        
            # 4. Firewall Address List (интернет доступ)
            if internet_access:
                print(f"🔧 Добавление {ip} в address-list 'internet_access'")
                results['firewall'] = mikrotik_manager.add_to_address_list(
                    'internet_access', 
                    f"{ip}/32", 
                    comment
                )
                print(f"   Результат firewall: {results['firewall']}")
            else:
                results['firewall'] = True
                print(f"⚠️  Интернет доступ отключен, пропускаем")
        
            # 5. Создаем запись о сотруднике
            employee = Employee(
                full_name=full_name,
                position=position,
                ip_address=ip,
                mac_address=mac,
                internet_access=internet_access,
                queue_assigned=queue_name
            )
        
            # Перестраиваем дерево очередей
            if tree_builder:
                print("🔄 Перестраиваем дерево очередей...")
                tree_builder.build_tree()
        
            success = all(results.values())
        
            response = {
                'success': success,
                'message': f'Сотрудник {full_name} добавлен' if success else f'Сотрудник {full_name} добавлен с ошибками',
                'results': results,
                'employee': employee.to_dict()
            }
        
            print(f"📤 Отправка ответа: {response}")
            self._send_json(response)
        
        except Exception as e:
            print(f"❌ КРИТИЧЕСКАЯ Ошибка добавления сотрудника: {e}")
            traceback.print_exc()
            self._send_json({'error': f'Внутренняя ошибка сервера: {str(e)}'}, 500)
    
    def _save_config(self, data):
        """Сохранить настройки"""
        try:
            config = ConfigManager.load_config()
            
            if 'last_device' in data:
                config['DEFAULT']['last_device'] = data['last_device']
            
            if 'auto_save_password' in data:
                config['DEFAULT']['auto_save_password'] = str(data['auto_save_password']).lower()
            
            if 'default_username' in data:
                config['DEFAULT']['default_username'] = data['default_username']
            
            ConfigManager.save_config(config)
            
            self._send_json({'success': True, 'message': 'Настройки сохранены'})
            
        except Exception as e:
            self._send_json({'error': str(e)}, 500)
    
    def _send_json(self, data, status=200):
        """Отправить JSON ответ"""
        json_data = json.dumps(data, ensure_ascii=False, indent=2)
        
        print(f"📤 JSON для отправки (первые 500 символов):")
        print(json_data[:500])
        print(f"📤 Полная длина: {len(json_data)} символов")
        
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Content-Length', str(len(json_data.encode('utf-8'))))
        self.end_headers()
        
        # Отправляем как bytes
        self.wfile.write(json_data.encode('utf-8'))
    
    def _get_html_template(self):
        """Вернуть HTML шаблон из файла"""
        try:
            with open('index.html', 'r', encoding='utf-8') as f:
                return f.read()
        except:
            # Фолбэк на минимальный HTML если файл не найден
            return '''
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>MikroTik Device Manager</title>
    <style>
        body { font-family: Arial; padding: 20px; }
        .container { max-width: 800px; margin: 0 auto; }
        .card { background: #f5f5f5; padding: 20px; margin: 20px 0; border-radius: 10px; }
        .btn { background: #3498db; color: white; padding: 10px 20px; border: none; border-radius: 5px; cursor: pointer; }
    </style>
</head>
<body>
    <div class="container">
        <h1>MikroTik Device Manager</h1>
        <div class="card">
            <p>Загрузите полный файл index.html в ту же папку</p>
            <p>Скопируйте HTML код из сообщения и сохраните как index.html</p>
        </div>
    </div>
</body>
</html>
            '''
    
    def log_message(self, format, *args):
        """Кастомное логирование"""
        print(f"🌐 {self.address_string()} - {format % args}")

def start_server(port=8080, host='0.0.0.0'):
    """Запуск HTTP сервера"""
    try:
        server_address = (host, port)
        http_server = StoppableHTTPServer(server_address, MikroTikManagerHandler)
        
        print("\n" + "="*60)
        print("🌐 Запуск веб-интерфейса...")
        print(f"   Адрес: http://localhost:{port}")
        print(f"   Или:   http://ваш_IP_адрес:{port}")
        print("\n📱 Откройте браузер для работы с приложением")
        print("="*60)
        print("Для остановки нажмите Ctrl+C")
        print("="*60)
        
        http_server.serve_forever()
        
    except KeyboardInterrupt:
        print("\n👋 Приложение завершено пользователем")
    except Exception as e:
        print(f"\n❌ Ошибка запуска сервера: {e}")
        traceback.print_exc()
    finally:
        print("\n👋 До свидания!")
