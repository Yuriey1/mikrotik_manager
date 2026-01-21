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
from netbox_client import NetBoxClient, NetBoxDevice  # Импорт NetBox

# Глобальные переменные
mikrotik_manager = None
tree_builder = None
current_device_name = None  # ← Добавим для отслеживания текущего устройства
netbox_client = None  # Клиент NetBox

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

    # В web_service.py - добавляем в метод do_DELETE()
    def do_DELETE(self):
        """Обработка DELETE запросов"""
        try:
            parsed = urlparse(self.path)
            path = parsed.path
    
            if path == '/api/forget_credentials':  # ← НОВЫЙ ENDPOINT
                query = parse_qs(parsed.query)
                device_name = query.get('device', [''])[0]
        
                if not device_name:
                    self._send_json({'error': 'Не указано устройство'}, 400)
                    return
        
                # Удаляем учетные данные
                ConfigManager.save_credentials(device_name, '', '')
        
                self._send_json({
                    'success': True,
                    'message': f'Учетные данные для {device_name} удалены'
                })
            elif path == '/api/forget_password':  # ← СТАРЫЙ ENDPOINT (для обратной совместимости)
                query = parse_qs(parsed.query)
                device_name = query.get('device', [''])[0]
        
                if not device_name:
                    self._send_json({'error': 'Не указано устройство'}, 400)
                    return
        
                # Удаляем пароль (старый метод)
                ConfigManager.save_password(device_name, '')
        
                self._send_json({
                    'success': True,
                    'message': f'Пароль для {device_name} удален'
                })
            else:
                self.send_error(404, "Not Found")
        
        except Exception as e:
            print(f"❌ Ошибка обработки DELETE запроса: {e}")
            self._send_json({'error': str(e)}, 500)
    
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


    def do_GET(self):
        """Обработка GET запросов"""
        try:
            parsed = urlparse(self.path)
            path = parsed.path
        
            if path == '/' or path == '/index.html':
                self._serve_html()
            elif path == '/api/devices':
                self._serve_devices_from_netbox()  # Изменено: получаем из NetBox
                """self._serve_devices()"""
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
            elif path == '/api/check_ip':  # ← НОВЫЙ ENDPOINT ДЛЯ ПРОВЕРКИ IP!
                self._check_ip_belongs(parsed)
            elif path == '/api/netbox/config':  # Получить настройки NetBox
                self._get_netbox_config()
            elif path == '/api/netbox/test':    # Тест соединения с NetBox
                self._test_netbox_connection(parsed)
            # =====  ЭТА СТРОКА ДЛЯ CSS/JS =====
            elif path.startswith('/static/'):
                self._serve_static_file(path)
            # =========================================
            elif path == '/api/find_dhcp_lease':
                self._find_dhcp_lease(parsed)
            elif path == '/api/free_ips':  # ← НОВЫЙ ENDPOINT ДЛЯ СВОБОДНЫХ IP!
                self._get_free_ips()
            else:
                self.send_error(404, "Not Found")
                
        except Exception as e:
            print(f"❌ Ошибка обработки GET запроса: {e}")
            self._send_json({'error': str(e)}, 500)

    def _initialize_netbox_client(self):
        """Инициализировать клиент NetBox"""
        global netbox_client
        try:
            netbox_config = ConfigManager.load_netbox_config()
            if netbox_config.get('url') and netbox_config.get('token'):
                netbox_client = NetBoxClient(
                    netbox_config['url'],
                    netbox_config['token'],
                    netbox_config.get('verify_ssl', True)
                )
                print(f"✅ NetBox клиент инициализирован")
            else:
                netbox_client = None
                print("⚠️  NetBox не настроен")
        except Exception as e:
            print(f"❌ Ошибка инициализации NetBox: {e}")
            netbox_client = None

    def _serve_devices_from_netbox(self):
        """Отдать список устройств из NetBox"""
        global netbox_client
        
        try:
            # Инициализируем клиент при первом запросе
            if netbox_client is None:
                self._initialize_netbox_client()
            
            if not netbox_client:
                self._send_json({
                    'devices': {},
                    'netbox_configured': False,
                    'error': 'NetBox не настроен'
                })
                return
            
            devices_list = netbox_client.get_devices()
            
            # Преобразуем в формат, ожидаемый фронтендом
            devices_dict = {}
            for device in devices_list:
                devices_dict[device.name] = {
                    'name': device.name,
                    'ip': device.ip_address,
                    'port': device.port,
                    'username': 'admin',
                    'password': '',  # Пароли не хранятся в NetBox
                    'description': f"{device.device_type} - {device.site} - {device.role}",
                    'device_type': device.device_type,
                    'site': device.site,
                    'role': device.role,
                    'comments': device.comments
                }
            
            self._send_json({
                'devices': devices_dict,
                'netbox_configured': True,
                'count': len(devices_dict)
            })
            
        except Exception as e:
            print(f"❌ Ошибка получения устройств из NetBox: {e}")
            self._send_json({
                'devices': {},
                'netbox_configured': False,
                'error': str(e)
            })

    def _get_netbox_config(self):
        """Получить настройки NetBox"""
        try:
            config = ConfigManager.load_netbox_config()
            self._send_json({
                'success': True,
                'config': config
            })
        except Exception as e:
            print(f"❌ Ошибка получения конфигурации NetBox: {e}")
            self._send_json({'error': str(e)}, 500)

    def _test_netbox_connection(self, parsed):
        """Проверить соединение с NetBox"""
        try:
            query = parse_qs(parsed.query)
            url = query.get('url', [''])[0]
            token = query.get('token', [''])[0]
            verify_ssl = query.get('verify_ssl', ['true'])[0].lower() == 'true'
            
            if not url or not token:
                self._send_json({
                    'success': False,
                    'error': 'Укажите URL и токен NetBox'
                })
                return
            
            # Создаем временного клиента для теста
            test_client = NetBoxClient(url, token, verify_ssl)
            
            if test_client.test_connection():
                self._send_json({
                    'success': True,
                    'message': 'Соединение с NetBox успешно установлено'
                })
            else:
                self._send_json({
                    'success': False,
                    'error': 'Не удалось подключиться к NetBox'
                })
                
        except Exception as e:
            print(f"❌ Ошибка тестирования соединения с NetBox: {e}")
            self._send_json({'error': str(e)}, 500)

    def _get_free_ips(self):
        """Получить список свободных IP адресов из DHCP пулов"""
        global mikrotik_manager
    
        if not mikrotik_manager or not mikrotik_manager.connected:
            self._send_json({'error': 'Не подключено к устройству'}, 400)
            return
    
        try:
            # Используем логику из DhcpAnalyzer
            free_ips = mikrotik_manager.get_free_dhcp_ips()
        
            self._send_json({
                'success': True,
                'free_ips': free_ips,
                'count': len(free_ips)
            })
        
        except Exception as e:
            print(f"❌ Ошибка получения свободных IP: {e}")
            traceback.print_exc()
            self._send_json({'error': str(e)}, 500)


    def _check_ip_belongs(self, parsed):
        """Проверить принадлежность IP к сетям микротика"""
        global mikrotik_manager
        
        query = parse_qs(parsed.query)
        ip = query.get('ip', [''])[0].strip()
        
        if not ip:
            self._send_json({'success': False, 'error': 'Не указан IP адрес'}, 400)
            return
            
        if not mikrotik_manager or not mikrotik_manager.connected:
            self._send_json({'success': False, 'error': 'Не подключено к устройству'}, 400)
            return
            
        try:
            # Проверяем формат IP
            ipaddress.ip_address(ip)
            
            # Используем метод из MikroTikManager для проверки
            belongs, interface = mikrotik_manager.is_ip_in_mikrotik_networks(ip)
            
            if belongs:
                self._send_json({
                    'success': True,
                    'message': f'IP {ip} принадлежит сетям микротика',
                    'interface': interface
                })
            else:
                self._send_json({
                    'success': False,
                    'error': f'IP {ip} не принадлежит сетям микротика'
                })
                
        except ValueError as e:
            self._send_json({'success': False, 'error': f'Неверный формат IP: {str(e)}'}, 400)
        except Exception as e:
            print(f"❌ Ошибка проверки IP: {e}")
            self._send_json({'success': False, 'error': str(e)}, 500)

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
            
            if path == '/api/netbox/save_config':  # Сохранить настройки NetBox
                self._save_netbox_config(data)
            elif path == '/api/add_device':
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

    def _save_netbox_config(self, data):
        """Сохранить настройки NetBox"""
        global netbox_client
        
        try:
            config = {
                'url': data.get('url', '').strip(),
                'token': data.get('token', '').strip(),
                'verify_ssl': data.get('verify_ssl', True)
            }
            
            if not config['url'] or not config['token']:
                self._send_json({
                    'success': False,
                    'error': 'Заполните URL и токен'
                })
                return
            
            # Сохраняем конфигурацию
            ConfigManager.save_netbox_config(config)
            
            # Переинициализируем клиент
            self._initialize_netbox_client()
            
            self._send_json({
                'success': True,
                'message': 'Настройки NetBox сохранены'
            })
            
        except Exception as e:
            print(f"❌ Ошибка сохранения конфигурации NetBox: {e}")
            self._send_json({'error': str(e)}, 500)

    
    def _serve_html(self):
        """Отдать HTML интерфейс"""
        html = self._get_html_template()
        self._set_headers('text/html')
        self.wfile.write(html.encode('utf-8'))
    
    # Метод _find_dhcp_lease:
    def _find_dhcp_lease(self, parsed):
        """Обработчик для /api/find_dhcp_lease"""
        global mikrotik_manager
        try:
            query = parse_qs(parsed.query)
            ip = query.get('ip', [''])[0]
    
            if not ip:
                self._send_json({"success": False, "error": "Не указан IP адрес"}, 400)
                return
    
            if mikrotik_manager is None or not mikrotik_manager.connected:
                self._send_json({"success": False, "error": "Не подключено к устройству"}, 400)
                return
    
            print(f"🔍 Поиск DHCP lease для IP: {ip}")
    
            lease = mikrotik_manager.find_dhcp_lease(ip=ip)
            print(f"🔍 Результат find_dhcp_lease: {lease}")
    
            if lease:
                # Ищем MAC адрес (может быть в разных полях)
                mac_address = None
            
                # Проверяем возможные названия полей
                for key in ['mac-address', 'mac_address', 'mac-address', 'mac.address', 'mac']:
                    if key in lease:
                        mac_address = lease[key]
                        break
            
                self._send_json({
                    "success": True,
                    "found": True,
                    "lease": lease,
                    "mac_address": mac_address
                })
            else:
                self._send_json({
                    "success": True,
                    "found": False,
                    "message": "DHCP lease не найден"
                })
        
        except Exception as e:
            print(f"❌ Ошибка в _find_dhcp_lease: {e}")
            import traceback
            traceback.print_exc()
            self._send_json({"success": False, "error": str(e)}, 500)

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
        """Подключиться к устройству из NetBox"""
        global mikrotik_manager, tree_builder, current_device_name, netbox_client

        query = parse_qs(parsed.query)
        device_name = query.get('device', [''])[0]
        username = query.get('username', [''])[0]  # ← НОВОЕ: получаем логин
        password = query.get('password', [''])[0]

        if not device_name:
            self._send_json({'error': 'Не указано устройство'}, 400)
            return

        try:
            # Проверяем, что NetBox клиент инициализирован
            if not netbox_client:
                self._send_json({'error': 'NetBox не настроен'}, 400)
                return

            print(f"🔗 Подключение к устройству: {device_name}")

            # Получаем все устройства из NetBox и ищем нужное
            nb_devices = netbox_client.get_devices()
            target_device = None
    
            for device in nb_devices:
                if device.name == device_name:
                    target_device = device
                    break

            if not target_device:
                self._send_json({'error': f'Устройство "{device_name}" не найдено в NetBox'}, 404)
                return

            # Получаем сохраненные учетные данные
            saved_creds = ConfigManager.get_credentials(device_name)
            default_username = ConfigManager.get_default_username()
        
            # Определяем финальные учетные данные
            final_username = username or saved_creds['username'] or default_username
            final_password = password or saved_creds['password']
        
            # Проверяем, что у нас есть пароль
            if not final_password:
                self._send_json({
                    'success': False,
                    'requires_credentials': True,  # ← ИЗМЕНЕНО: требует и логин, и пароль
                    'device': device_name,
                    'saved_username': saved_creds['username'] or default_username,
                    'message': 'Требуется ввод учетных данных'
                }, 401)
                return

            # Отключаемся от предыдущего устройства, если подключены
            if mikrotik_manager and mikrotik_manager.connected and current_device_name:
                print(f"🔌 Отключаемся от предыдущего устройства ({current_device_name})...")
                self._disconnect_current_device()

            # Создаем объект устройства для MikroTikManager
            device_dict = {
                'name': target_device.name,
                'ip': target_device.ip_address,
                'port': target_device.port,
                'username': final_username,  # ← ИЗМЕНЕНО: используем вычисленный логин
                'password': final_password,
                'description': f"{target_device.device_type} - {target_device.site}"
            }

            # Создаем MikroTik устройство
            device = MikroTikDevice.from_dict(device_dict)
            mikrotik_manager = MikroTikManager(device)

            # Пробуем подключиться
            if mikrotik_manager.connect():
                # Сохраняем учетные данные если подключение успешно
                if final_username or final_password:
                    ConfigManager.save_credentials(device_name, final_username, final_password)
                    print(f"💾 Учетные данные сохранены для {device_name}")
        
                current_device_name = device_name
        
                # Строим дерево очередей
                tree_builder = QueueTreeBuilder(mikrotik_manager)
                tree_builder.build_tree()
    
                self._send_json({
                    'success': True,
                    'device': device_name,
                    'message': f'Подключено к {device.ip}:{device.port}',
                    'action': 'connected',
                    'username': final_username  # ← НОВОЕ: возвращаем использованный логин
                })
            else:
                current_device_name = None
                self._send_json({
                    'success': False,
                    'error': 'Не удалось подключиться к устройству'
                })

        except Exception as e:
            print(f"❌ Ошибка подключения: {e}")
            traceback.print_exc()
            self._send_json({'error': str(e)}, 500)

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
        global tree_builder, mikrotik_manager
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
        """Найти очереди для IP или вернуть все очереди"""
        global tree_builder
        if not tree_builder:
            self._send_json({'success': False, 'error': 'Не подключено к устройству'}, 400)
            return

        query = parse_qs(parsed.query)
        ip = query.get('ip', [''])[0].strip()

        # ========= РЕЖИМ 1: БЕЗ IP - ВОЗВРАЩАЕМ ВСЕ ОЧЕРЕДИ =========
        if not ip:
            try:
                # Получаем все узлы из tree_builder
                all_nodes = list(tree_builder.nodes.values())
                all_dicts = []
            
                for node in all_nodes:
                    node_dict = node.to_dict()
                    all_dicts.append(node_dict)
            
                # Успешный ответ со всеми очередями
                self._send_json({
                    'success': True,
                    'queues': all_dicts,
                    'count': len(all_dicts)
                })
                return
            
            except Exception as e:
                print(f"❌ Ошибка получения всех очередей: {e}")
                self._send_json({'success': False, 'error': str(e)})
                return

    # ========= РЕЖИМ 2: С IP - ПОИСК ОЧЕРЕДЕЙ ДЛЯ КОНКРЕТНОГО IP =========
    # Проверка формата IP (существующая логика)
        try:
            if '/' in ip:
                ipaddress.ip_network(ip, strict=False)
            else:
                ipaddress.ip_address(ip)
        except ValueError:
            self._send_json({'success': False, 'error': 'Неверный формат IP'}, 400)
            return

        try:
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
                'ip': ip,
                'existing': existing,
                'queues': suitable_dicts,
                'count': len(suitable)
            })
        
        except Exception as e:
            print(f"❌ Ошибка поиска очередей для IP {ip}: {e}")
            self._send_json({'success': False, 'error': str(e)})
    
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
        """Добавить сотрудника (полный процесс) - ОБНОВЛЕННАЯ ВЕРСИЯ с опциональными очередями"""
        global mikrotik_manager, tree_builder

        print("\n" + "=" * 50)
        print("👤 ДОБАВЛЕНИЕ СОТРУДНИКА")
        print(f"📝 Полученные данные: {data}")
        print("=" * 50)

        if not mikrotik_manager:
            print("❌ Ошибка: mikrotik_manager не подключен")
            self._send_json({'error': 'Не подключено к устройству'}, 400)
            return

        try:
            # Начало процесса добавления сотрудника
            print("Начало операции добавления сотрудника")

            # Получаем данные
            full_name = data.get('full_name', '').strip()
            position = data.get('position', '').strip()
            ip = data.get('ip', '').strip()
            mac = data.get('mac', '').strip()
            internet_access = bool(data.get('internet_access', False))
        
            # Получаем МАССИВ очередей (может быть пустым)
            queues = data.get('queues', [])
            if isinstance(queues, str):
                queues = [queues] if queues.strip() else []

            print(f"🔍 Парсинг данных:")
            print(f"  ФИО: {full_name}")
            print(f"  Должность: {position}")
            print(f"  IP: {ip}")
            print(f"  MAC: {mac}")
            print(f"  Интернет доступ: {internet_access}")
            print(f"  Очереди: {queues} (количество: {len(queues)})")

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

            # Если MAC не указан, ищем в DHCP
            if not mac:
                print(f"🔍 MAC не указан, ищем в DHCP для IP {ip}...")
                try:
                    lease = mikrotik_manager.find_dhcp_lease(ip=ip)
                    if lease:
                        # Ищем MAC адрес в разных возможных полях
                        mac = lease.get('mac-address') or lease.get('mac_address') or lease.get('mac.address', '')
                        if mac:
                            print(f"✅ Найден MAC в DHCP: {mac}")
                        else:
                            print(f"⚠️  DHCP lease найден, но MAC не обнаружен в полях")
                    else:
                        print(f"⚠️  DHCP lease для {ip} не найден")
                except Exception as e:
                    print(f"⚠️  Ошибка поиска DHCP lease: {e}")

            # Проверяем формат MAC (если он есть)
            if mac:
                # Приводим к правильному формату перед проверкой
                mac = mac.lower().replace('-', ':').replace('.', ':')
                mac_pattern = re.compile(r'^([0-9a-f]{2}[:-]){5}([0-9a-f]{2})$')
                if not mac_pattern.match(mac):
                    error_msg = 'Неверный формат MAC'
                    print(f"❌ {error_msg}")
                    self._send_json({'error': error_msg}, 400)
                    return
                print(f"✅ MAC адрес валиден: {mac}")
            else:
                print(f"⚠️  MAC адрес не указан и не найден в DHCP")

            # Создаем комментарий
            comment = f"{position} - {full_name}"
            print(f"📝 Комментарий: {comment}")

            results = {
                'dhcp': False,
                'arp': False,
                'queues': [],  # Может быть пустым
                'firewall': False
            }

            # 1. DHCP Lease - создаем/обновляем статический lease
            # ВАЖНО: вызываем create_static_lease даже если нет MAC (для проверки существующего)
            print(f"\n🔧 ШАГ 1: Работа с DHCP lease для {ip}...")
            if mac:
                print(f"  Используем MAC: {mac}")
                results['dhcp'] = mikrotik_manager.create_static_lease(ip, mac, comment)
                print(f"  Результат DHCP: {results['dhcp']}")
            else:
                # Если нет MAC, пробуем найти существующий lease и сделать его статическим
                print(f"  Без MAC, проверяем существующий lease...")
                lease = mikrotik_manager.find_dhcp_lease(ip=ip)
                if lease:
                    print(f"  Найден существующий lease: {lease}")
                    lease_id = lease.get('.id')
                    if lease_id:
                        print(f"  Lease ID: {lease_id}")
                        
                        # Проверяем, динамический ли lease
                        is_dynamic = lease.get('dynamic') == 'true'
                        print(f"  Динамический: {is_dynamic}")
                        
                        try:
                            dhcp_cmd = mikrotik_manager.api.path('/ip/dhcp-server/lease')
                            
                            # Если lease динамический, делаем его статическим
                            if is_dynamic:
                                print(f"  🔄 Делаем динамический lease статическим...")
                                try:
                                    tuple(dhcp_cmd('make-static', **{'.id': lease_id}))
                                    print(f"  ✅ Lease сделан статическим через make-static")
                                except Exception as e:
                                    print(f"  ⚠️ Ошибка make-static: {e}")
                                    # Пробуем другой способ
                                    try:
                                        tuple(dhcp_cmd('set', **{
                                            '.id': lease_id,
                                            'dynamic': 'no'
                                        }))
                                        print(f"  ✅ Lease сделан статическим через set")
                                    except Exception as e2:
                                        print(f"  ❌ Ошибка set: {e2}")
                            
                            # Добавляем комментарий
                            from utils.helpers import russian_to_mikrotik_comment
                            mikrotik_comment = russian_to_mikrotik_comment(comment)
                            print(f"  📝 Добавляем комментарий: {comment}")
                            
                            try:
                                tuple(dhcp_cmd('comment', **{
                                    'numbers': lease_id,
                                    'comment': mikrotik_comment
                                }))
                                print(f"  ✅ Комментарий добавлен через comment")
                            except Exception as e:
                                print(f"  ⚠️ Ошибка comment, пробуем set: {e}")
                                try:
                                    tuple(dhcp_cmd('set', **{
                                        '.id': lease_id,
                                        'comment': mikrotik_comment
                                    }))
                                    print(f"  ✅ Комментарий добавлен через set")
                                except Exception as e2:
                                    print(f"  ❌ Ошибка добавления комментария: {e2}")
                            
                            results['dhcp'] = True
                            
                        except Exception as e:
                            print(f"  ❌ Ошибка обработки существующего lease: {e}")
                            results['dhcp'] = False
                    else:
                        print(f"  ❌ Не найден ID lease")
                        results['dhcp'] = False
                else:
                    print(f"  ⚠️  Нет существующего lease, пропускаем DHCP")
                    results['dhcp'] = True  # Пропускаем если нет MAC и нет существующего lease

            # 2. ARP таблица - только если есть MAC
            print(f"\n🔧 ШАГ 2: Работа с ARP таблицей...")
            if mac:
                print(f"  Добавление ARP записи для {ip} -> {mac}")
                results['arp'] = mikrotik_manager.add_static_arp(ip, mac, comment)
                print(f"  Результат ARP: {results['arp']}")
            else:
                results['arp'] = True
                print(f"  ⚠️  MAC не указан, пропускаем ARP")

            # 3. Очереди (ОПЦИОНАЛЬНО - если указаны)
            queue_results = []
            if queues:
                print(f"\n🔧 ШАГ 3: Поиск и добавление в {len(queues)} очередь(ей)...")
            
                for queue_name in queues:
                    print(f"  🔍 Поиск очереди '{queue_name}'...")
                    # Находим ID очереди
                    queue_id = None
                    for node in tree_builder.nodes.values():
                        if node.name == queue_name:
                            queue_id = node.id
                            break

                    if queue_id:
                        print(f"  🔧 Добавление IP {ip} в очередь {queue_name} (ID: {queue_id})")
                        queue_success = mikrotik_manager.add_ip_to_queue(queue_id, ip)
                        queue_results.append({
                            'name': queue_name,
                            'success': queue_success,
                            'id': queue_id
                        })
                        print(f"  ✅ Результат очереди {queue_name}: {queue_success}")
                    else:
                        print(f"  ❌ Очередь '{queue_name}' не найдена")
                        queue_results.append({
                            'name': queue_name,
                            'success': False,
                            'error': 'Очередь не найдена'
                        })
            
                results['queues'] = queue_results
                print(f"📊 Итог по очередям: {len([q for q in queue_results if q.get('success', False)])} из {len(queues)} успешно")
            else:
                print(f"\nℹ️  ШАГ 3: Очереди не указаны, сотрудник будет работать без ограничений очередей")
                results['queues'] = []

            # 4. Firewall Address List (интернет доступ)
            print(f"\n🔧 ШАГ 4: Работа с Firewall...")
            if internet_access:
                print(f"  Добавление {ip} в address-list 'internet_access'")
                results['firewall'] = mikrotik_manager.add_to_address_list(
                    'internet_access',
                    f"{ip}/32",
                    comment
                )
                print(f"  Результат firewall: {results['firewall']}")
            else:
                results['firewall'] = True
                print(f"  ℹ️  Интернет доступ отключен, пропускаем")

            # Завершение операции
            print("\n" + "=" * 50)
            print("✅ ЗАВЕРШЕНИЕ ОПЕРАЦИИ ДОБАВЛЕНИЯ СОТРУДНИКА")
            print("=" * 50)

            # Проверяем общий успех
            # Основные действия должны быть успешными, очереди - опциональны
            overall_success = results['dhcp'] and results['arp'] and results['firewall']
        
            # Если очереди указаны, проверяем что хотя бы одна добавлена успешно
            if queues:
                queue_success = any(q.get('success', False) for q in results['queues'])
                overall_success = overall_success and queue_success
            # Если очереди не указаны, проверяем только основные действия

            # Формируем сообщение
            if overall_success:
                if queues:
                    successful_queues = [q['name'] for q in results['queues'] if q.get('success', False)]
                    if successful_queues:
                        message = f'Сотрудник {full_name} успешно добавлен в {len(successful_queues)} очередь(ей)'
                    else:
                        message = f'Сотрудник {full_name} добавлен, но в очереди добавить не удалось'
                else:
                    message = f'Сотрудник {full_name} успешно добавлен (без ограничений очередей)'
            else:
                message = f'Ошибка добавления сотрудника {full_name}'

            # Готовим ответ клиенту
            response = {
                'success': overall_success,
                'message': message,
                'details': {
                    'dhcp': results['dhcp'],
                    'arp': results['arp'],
                    'firewall': results['firewall'],
                    'queues': results['queues']
                },
                'results': results
            }

            # Формируем детали для пользователя
            details_text = []
            details_text.append(f'✅ DHCP: {"успешно" if results["dhcp"] else "ошибка"}')
            details_text.append(f'✅ ARP: {"успешно" if results["arp"] else "ошибка"}')
        
            if queues:
                successful_count = sum(1 for q in results['queues'] if q.get('success', False))
                if successful_count > 0:
                    details_text.append(f'✅ Очереди: {successful_count} из {len(queues)} успешно')
                    for queue in results['queues']:
                        if queue.get('success', False):
                            details_text.append(f'  ✓ {queue["name"]}')
                        else:
                            details_text.append(f'  ✗ {queue["name"]} ({queue.get("error", "ошибка")})')
                else:
                    details_text.append(f'⚠️ Очереди: не удалось добавить ни в одну очередь')
            else:
                details_text.append('ℹ️  Очереди: не указаны (настройки по умолчанию)')
        
            details_text.append(f'✅ Firewall: {"успешно" if results["firewall"] else "ошибка"}')
        
            response['details_list'] = details_text

            print(f"📤 Отправка ответа: {response}")
            self._send_json(response)

        except Exception as e:
            print(f"❌ КРИТИЧЕСКАЯ Ошибка добавления сотрудника: {e}")
            traceback.print_exc()
            self._send_json({'error': f'Внутренняя ошибка сервера: {str(e)}'}, 500)
    
    def log_message(self, format, *args):
        """Кастомное логирование"""
        print(f"🌐 {self.address_string()} - {format % args}")

def start_server(port=8090, host='0.0.0.0'):
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
