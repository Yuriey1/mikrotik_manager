"""
Менеджер работы с MikroTik API
"""

from librouteros import connect
import ipaddress
import traceback
from typing import Dict, List, Optional, Tuple
import re

from models.device import MikroTikDevice
from config.config_manager import ConfigManager
from utils.helpers import russian_to_mikrotik_comment

class MikroTikManager:
    """Менеджер работы с MikroTik"""
    
    def __init__(self, device: MikroTikDevice):
        self.device = device
        self.api = None
        self.connected = False
    
    def connect(self) -> bool:
        """Подключиться к устройству"""
        try:
            # Расшифровываем пароль если нужно
            password = self.device.password
            if password.startswith('enc:'):
                password = ConfigManager.decrypt_password(password[4:])
            
            print(f"🔗 Подключение к {self.device.name} ({self.device.ip})...")
            
            self.api = connect(
                username=self.device.username,
                password=password,
                host=self.device.ip,
                port=self.device.port,
                encoding='windows-1251'
            )
            self.connected = True
            print(f"✅ Успешное подключение")
            return True
            
        except Exception as e:
            print(f"❌ Ошибка подключения: {e}")
            traceback.print_exc()
            self.connected = False
            return False
    
    def disconnect(self):
        """Отключиться от устройства"""
        try:
            if self.api:
                print(f"🔌 Закрываем соединение с {self.device.name}...")
                self.api.close()
                self.api = None
                self.connected = False
                print(f"✅ Соединение с {self.device.name} закрыто")
        except Exception as e:
            print(f"⚠️  Ошибка при отключении: {e}")
    
    # ========== DHCP LEASES ==========
    def find_dhcp_lease(self, ip: str, mac: Optional[str] = None) -> Optional[dict]:
        """Найти DHCP lease по IP адресу."""
        try:
            if not self.api:
                return None
        
            print(f"🔍 Поиск DHCP lease для IP: {ip}")
        
            # Используем librouteros API - получаем все DHCP аренды
            leases = self.api.path('/ip/dhcp-server/lease')
            all_leases = list(leases)
        
            print(f"📊 Всего DHCP leases: {len(all_leases)}")
        
            # Проходим по всем записям и ищем match по IP
            for lease in all_leases:
                if lease.get('address') == ip:
                    print(f"✅ Найден DHCP lease для {ip}, MAC: {lease.get('mac-address', '')}")
                    return lease
        
            print(f"⚠️  DHCP lease для {ip} не найден среди {len(all_leases)} записей")
            return None
        
        except Exception as e:
            print(f"❌ Ошибка поиска DHCP lease для {ip}: {e}")
            traceback.print_exc()
            return None
    
    def create_static_lease(self, ip: str, mac: str, comment: str = "") -> bool:
        """Создать/обновить статический DHCP lease (УМНАЯ ЛОГИКА)"""
        try:
            print(f"\n🔧 DHCP: Работа с {ip} -> {mac}")
        
            # Получаем объект пути
            dhcp_cmd = self.api.path('/ip/dhcp-server/lease')
        
            # 1. Ищем существующий lease
            print(f"🔍 DHCP: Ищем существующий lease для {ip}")
            leases = list(dhcp_cmd)
            lease = None
            lease_id = None
        
            for l in leases:
                if l.get('address') == ip:
                    lease = l
                    lease_id = l.get('.id')
                    print(f"✅ DHCP: Найден существующий lease ID: {lease_id}")
                    break
        
            # 2. Проверяем статус найденного lease
            if lease:
                is_dynamic = lease.get('dynamic') == 'true'
                is_disabled = lease.get('disabled') == 'true'
                current_mac = lease.get('mac-address', '')
                current_comment = lease.get('comment', '')
            
                print(f"📊 DHCP: Статус lease:")
                print(f"  - Динамический: {is_dynamic}")
                print(f"  - Отключен: {is_disabled}")
                print(f"  - MAC: {current_mac}")
                print(f"  - Комментарий: {current_comment}")
            
                # 2a. Проверяем MAC адрес
                if current_mac and current_mac.lower() != mac.lower():
                    print(f"⚠️ DHCP: MAC адрес отличается! Существующий: {current_mac}, Новый: {mac}")
                    print(f"🔄 DHCP: Обновляем MAC адрес")
                    try:
                        tuple(dhcp_cmd('set', **{
                            '.id': lease_id,
                            'mac-address': mac
                        }))
                        print(f"✅ DHCP: MAC адрес обновлен")
                    except Exception as e:
                        print(f"❌ DHCP: Ошибка обновления MAC: {e}")
            
                # 2b. Если lease динамический - делаем статическим
                if is_dynamic:
                    print(f"🔄 DHCP: Делаем динамический lease статическим")
                    try:
                        tuple(dhcp_cmd('make-static', **{'.id': lease_id}))
                        print(f"✅ DHCP: Lease помечен как статический")
                    except Exception as e:
                        print(f"⚠️ DHCP: Ошибка make-static, пробуем set: {e}")
                        try:
                            tuple(dhcp_cmd('set', **{
                                '.id': lease_id,
                                'dynamic': 'no'
                            }))
                        except Exception as e2:
                            print(f"❌ DHCP: Ошибка установки static: {e2}")
            
                # 2c. Если отключен - включаем
                if is_disabled:
                    print(f"🔄 DHCP: Включаем отключенный lease")
                    try:
                        tuple(dhcp_cmd('set', **{
                            '.id': lease_id,
                            'disabled': 'no'
                        }))
                        print(f"✅ DHCP: Lease включен")
                    except Exception as e:
                        print(f"⚠️ DHCP: Ошибка включения lease: {e}")
        
            # 3. Если lease не найден - создаем новый
            else:
                print(f"➕ DHCP: Создаем новый lease для {ip} -> {mac}")
                try:
                    # Сначала создаем
                    tuple(dhcp_cmd('add', **{
                        'address': ip,
                        'mac-address': mac,
                        'disabled': 'no'
                    }))
                
                    # Находим ID созданного lease
                    leases = list(dhcp_cmd)
                    for l in leases:
                        if l.get('address') == ip:
                            lease_id = l.get('.id')
                            print(f"✅ DHCP: Новый lease создан, ID: {lease_id}")
                            break
                
                    # Делаем его сразу статическим
                    if lease_id:
                        print(f"🔄 DHCP: Делаем новый lease статическим")
                        try:
                            tuple(dhcp_cmd('make-static', **{'.id': lease_id}))
                            print(f"✅ DHCP: Новый lease помечен как статический")
                        except Exception as e:
                            print(f"⚠️ DHCP: Ошибка make-static для нового lease: {e}")
                            try:
                                tuple(dhcp_cmd('set', **{
                                    '.id': lease_id,
                                    'dynamic': 'no'
                                }))
                            except:
                                pass
            
                except Exception as e:
                    print(f"❌ DHCP: Ошибка создания нового lease: {e}")
                    return False
        
            # 4. Добавляем/обновляем комментарий (если lease_id найден)
            if lease_id and comment:
                print(f"📝 DHCP: Добавляем/обновляем комментарий: {comment}")
                mikrotik_comment = russian_to_mikrotik_comment(comment)
            
                try:
                    # Пробуем команду comment
                    tuple(dhcp_cmd('comment', **{
                        'numbers': lease_id,
                        'comment': mikrotik_comment
                    }))
                    print(f"✅ DHCP: Комментарий добавлен/обновлен")
                
                except Exception as e:
                    print(f"⚠️ DHCP: Ошибка команды comment, пробуем set: {e}")
                    try:
                        tuple(dhcp_cmd('set', **{
                            '.id': lease_id,
                            'comment': mikrotik_comment
                        }))
                        print(f"✅ DHCP: Комментарий добавлен через set")
                    except Exception as e2:
                        print(f"❌ DHCP: Ошибка добавления комментария: {e2}")
        
            # 5. Проверяем, что все ок
            if lease_id:
                print(f"✅ DHCP: Работа с {ip} завершена успешно")
                return True
            else:
                print(f"❌ DHCP: Не удалось получить/создать lease для {ip}")
                return False
            
        except Exception as e:
            print(f"❌ DHCP: Критическая ошибка: {e}")
            traceback.print_exc()
            return False
    
    def add_static_arp(self, ip: str, mac: str, comment: str = "") -> bool:
        """Добавить статическую ARP запись"""
        try:
            print(f"\n🔧 ARP: Начинаем работу с {ip} -> {mac}")
            
            # Получаем объект пути
            arp_cmd = self.api.path('/ip/arp')
            
            # 1. Ищем интерфейс
            print(f"🔍 ARP: Ищем интерфейс для IP {ip}")
            interface = self._find_interface_for_ip(ip)
            print(f"✅ ARP: Найден интерфейс: {interface}")
            
            # 2. Проверяем существующую запись
            print(f"🔍 ARP: Проверяем существующие ARP записи")
            arp_entries = list(arp_cmd)
            for entry in arp_entries:
                if entry.get('address') == ip:
                    print(f"⚠️ ARP: Запись для {ip} уже существует")
                    return True
            
            # 3. Добавляем новую запись
            print(f"➕ ARP: Добавляем новую запись")
            mikrotik_comment = russian_to_mikrotik_comment(comment) if comment else ""
            
            try:
                tuple(arp_cmd('add', **{
                    'address': ip,
                    'mac-address': mac,
                    'interface': interface,
                    'disabled': 'no',
                    'comment': mikrotik_comment
                }))
                print(f"✅ ARP: Запись успешно добавлена")
                return True
                
            except Exception as e:
                print(f"❌ ARP: Ошибка добавления: {e}")
                return False
            
        except Exception as e:
            print(f"❌ ARP: Критическая ошибка: {e}")
            traceback.print_exc()
            return False

    def _find_interface_for_ip(self, ip: str) -> str:
        """Найти интерфейс для IP"""
        try:
            print(f"🔍 Interface: Ищем интерфейс для IP {ip}")
            
            # Получаем объект пути
            ipaddr_cmd = self.api.path('/ip/address')
            addresses = list(ipaddr_cmd)
            
            for addr in addresses:
                try:
                    network_addr, prefix = addr['address'].split('/')
                    interface = addr['interface']
                    
                    if self._ip_in_network(ip, network_addr, int(prefix)):
                        print(f"✅ Interface: Найден интерфейс '{interface}' для IP {ip}")
                        return interface
                except (ValueError, KeyError):
                    continue
            
            print(f"⚠️ Interface: Интерфейс не найден, использую 'bridge-local'")
            return 'bridge-local'
            
        except Exception as e:
            print(f"⚠️ Interface: Ошибка поиска интерфейса: {e}")
            return 'bridge-local'

    def _ip_in_network(self, ip: str, network_addr: str, prefix: int) -> bool:
        """Проверить принадлежность IP к сети"""
        try:
            network = ipaddress.ip_network(f"{network_addr}/{prefix}", strict=False)
            return ipaddress.ip_address(ip) in network
        except ValueError:
            return False
    
    def add_to_address_list(self, list_name: str, address: str, comment: str = "") -> bool:
        """Добавить адрес в список"""
        try:
            print(f"\n🔧 Firewall: Добавление {address} в список '{list_name}'")
            
            # Получаем объект пути
            fw_cmd = self.api.path('/ip/firewall/address-list')
            
            # 1. Проверяем существующую запись
            print(f"🔍 Firewall: Проверяем существующие записи в списке '{list_name}'")
            addresses = list(fw_cmd)
            
            for addr in addresses:
                if addr.get('list') == list_name and addr.get('address') == address:
                    print(f"⚠️ Firewall: Адрес {address} уже в списке {list_name}")
                    return True
            
            # 2. Добавляем новую запись
            print(f"➕ Firewall: Добавляем {address} в список {list_name}")
            mikrotik_comment = russian_to_mikrotik_comment(comment) if comment else ""
            
            try:
                tuple(fw_cmd('add', **{
                    'list': list_name,
                    'address': address,
                    'comment': mikrotik_comment,
                    'disabled': 'no'
                }))
                print(f"✅ Firewall: Адрес успешно добавлен")
                return True
                
            except Exception as e:
                print(f"❌ Firewall: Ошибка добавления: {e}")
                return False
            
        except Exception as e:
            print(f"❌ Firewall: Критическая ошибка: {e}")
            traceback.print_exc()
            return False
    
    def get_queues(self) -> List[Dict]:
        """Получить все очереди"""
        try:
            return list(self.api('/queue/simple/print'))
        except Exception as e:
            print(f"❌ Ошибка получения очередей: {e}")
            return []
    
    def add_ip_to_queue(self, queue_id: str, ip: str) -> bool:
        """Добавить IP в очередь (ВАШ СТИЛЬ)"""
        try:
            print(f"\n🔧 Queue: Добавление IP {ip} в очередь ID: {queue_id}")
        
            # Получаем объект пути
            queue_cmd = self.api.path('/queue/simple')
        
            # 1. Получаем текущую очередь
            print(f"🔍 Queue: Получаем данные очереди")
            queues = list(queue_cmd)
            current_target = ""
        
            for queue in queues:
                if queue.get('.id') == queue_id:
                    current_target = queue.get('target', '')
                    print(f"✅ Queue: Найдена очередь, текущий target: {current_target}")
                    break
        
            if not current_target:
                print(f"⚠️ Queue: Очередь не найдена или пустая")
                current_target = ""
        
            # 2. Формируем новый target
            if '/' in ip:
                ip_with_mask = ip
            else:
                ip_with_mask = f"{ip}/32"
        
            if current_target:
                new_target = f"{current_target},{ip_with_mask}"
            else:
                new_target = ip_with_mask
        
            print(f"🔄 Queue: Новый target: {new_target}")
        
            # 3. Обновляем очередь
            try:
                tuple(queue_cmd('set', **{
                    '.id': queue_id,
                    'target': new_target
                }))
                print(f"✅ Queue: Очередь успешно обновлена")
                return True
            
            except Exception as e:
                print(f"❌ Queue: Ошибка обновления: {e}")
                # Пробуем альтернативный способ
                try:
                    self.api('/queue/simple/set', **{
                        '.id': queue_id,
                        'target': new_target
                    })
                    print(f"✅ Queue: Очередь обновлена (альтернативным методом)")
                    return True
                except Exception as e2:
                    print(f"❌ Queue: Ошибка альтернативного метода: {e2}")
                    return False
        
        except Exception as e:
            print(f"❌ Queue: Критическая ошибка: {e}")
            traceback.print_exc()
            return False
