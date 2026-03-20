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
            if password.startswith("enc:"):
                password = ConfigManager.decrypt_password(password[4:])

            print(f"🔗 Подключение к {self.device.name} ({self.device.ip})...")

            self.api = connect(
                username=self.device.username,
                password=password,
                host=self.device.ip,
                port=self.device.port,
                encoding="windows-1251",
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

    # ========== ПРОВЕРКА IP ==========
    def is_ip_in_mikrotik_networks(self, ip: str) -> Tuple[bool, Optional[str]]:
        """
        Проверить, принадлежит ли IP сетям микротика

        Возвращает:
            (принадлежит, интерфейс) или (False, None) если не принадлежит
        """
        try:
            print(f"🔍 Проверка IP {ip} на принадлежность сетям микротика...")

            # Получаем все адреса интерфейсов
            ipaddr_cmd = self.api.path("/ip/address")
            addresses = list(ipaddr_cmd)

            # Преобразуем IP в объект для проверки
            try:
                ip_obj = ipaddress.ip_address(ip)
            except ValueError:
                print(f"❌ Неверный формат IP: {ip}")
                return False, None

            # Проверяем каждый адрес интерфейса
            for addr in addresses:
                try:
                    network_str = addr["address"]  # Формат: 192.168.1.1/24
                    interface = addr["interface"]

                    # Создаем объект сети
                    network = ipaddress.ip_network(network_str, strict=False)

                    # Проверяем принадлежность IP к сети
                    if ip_obj in network:
                        print(
                            f"✅ IP {ip} принадлежит сети {network} на интерфейсе '{interface}'"
                        )
                        return True, interface

                except (ValueError, KeyError) as e:
                    print(f"⚠️  Ошибка обработки адреса {addr}: {e}")
                    continue

            print(f"❌ IP {ip} НЕ принадлежит ни одной сети микротика!")
            print(f"   Найдено сетей: {len(addresses)}")
            return False, None

        except Exception as e:
            print(f"❌ Ошибка проверки IP: {e}")
            traceback.print_exc()
            return False, None

    # ========== DHCP LEASES ==========
    def find_dhcp_lease(self, ip: str, mac: Optional[str] = None) -> Optional[dict]:
        """Найти DHCP lease по IP адресу."""
        try:
            if not self.api:
                return None

            print(f"🔍 Поиск DHCP lease для IP: {ip}")

            # Используем librouteros API - получаем все DHCP аренды
            leases = self.api.path("/ip/dhcp-server/lease")
            all_leases = list(leases)

            print(f"📊 Всего DHCP leases: {len(all_leases)}")

            # Проходим по всем записям и ищем match по IP
            for lease in all_leases:
                if lease.get("address") == ip:
                    print(
                        f"✅ Найден DHCP lease для {ip}, MAC: {lease.get('mac-address', '')}"
                    )
                    return lease

            print(f"⚠️  DHCP lease для {ip} не найден среди {len(all_leases)} записей")
            return None

        except Exception as e:
            print(f"❌ Ошибка поиска DHCP lease для {ip}: {e}")
            traceback.print_exc()
            return None

    def _find_dhcp_server_for_ip(self, ip: str) -> Optional[str]:
        """Найти DHCP сервер, который обслуживает сеть с указанным IP"""
        try:
            # Преобразуем IP в объект
            ip_obj = ipaddress.ip_address(ip)
            
            # Получаем все DHCP серверы
            dhcp_servers_cmd = self.api.path('/ip/dhcp-server')
            servers = list(dhcp_servers_cmd)
            
            # Получаем все сети интерфейсов
            ipaddr_cmd = self.api.path('/ip/address')
            addresses = list(ipaddr_cmd)
            
            print(f"🔍 Поиск DHCP сервера для IP {ip}")
            print(f"   Найдено DHCP серверов: {len(servers)}")
            print(f"   Найдено адресов интерфейсов: {len(addresses)}")
            
            # Для каждого DHCP сервера проверяем, входит ли IP в его сеть
            for server in servers:
                server_name = server.get('name', '')
                interface = server.get('interface', '')
                
                print(f"   Проверяем сервер '{server_name}' на интерфейсе '{interface}'")
                
                # Ищем адрес интерфейса, к которому привязан DHCP сервер
                for addr in addresses:
                    if addr.get('interface') == interface:
                        network_str = addr.get('address', '')  # Формат: 192.168.1.1/24
                        try:
                            network = ipaddress.ip_network(network_str, strict=False)
                            if ip_obj in network:
                                print(f"   ✅ IP {ip} принадлежит сети {network} сервера '{server_name}'")
                                return server_name
                        except ValueError as e:
                            print(f"   ⚠️ Ошибка парсинга сети {network_str}: {e}")
                            continue
            
            print(f"   ❌ Не найден DHCP сервер для IP {ip}")
            return None
            
        except Exception as e:
            print(f"❌ Ошибка поиска DHCP сервера: {e}")
            traceback.print_exc()
            return None

    def create_static_lease(self, ip: str, mac: str, comment: str = "") -> bool:
        """Создать/обновить статический DHCP lease"""
        try:
            print(f"\n🔧 DHCP: Работа с {ip} -> {mac}")
        
            # Получаем объект пути
            dhcp_cmd = self.api.path('/ip/dhcp-server/lease')
        
            # 1. Определяем правильный DHCP сервер для этого IP
            print(f"🔍 DHCP: Определяем правильный DHCP сервер для {ip}...")
            dhcp_server = self._find_dhcp_server_for_ip(ip)
            
            if not dhcp_server:
                print(f"⚠️ DHCP: Не найден подходящий DHCP сервер, используем 'all'")
                dhcp_server = 'all'
            else:
                print(f"✅ DHCP: Найден DHCP сервер: {dhcp_server}")
        
            # 2. Ищем существующий lease
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
        
            # 3. Проверяем статус найденного lease
            if lease:
                flags = lease.get('flags', '')
                print(f"📊 DHCP: Поле 'flags': '{flags}'")
                
                # Проверяем наличие флага D (DYNAMIC)
                is_dynamic = 'D' in flags
                
                # Также проверяем поле dynamic для совместимости
                dynamic_field = lease.get('dynamic', '')
                print(f"📊 DHCP: Поле 'dynamic': '{dynamic_field}'")
                
                if isinstance(dynamic_field, bool):
                    is_dynamic = is_dynamic or dynamic_field
                elif isinstance(dynamic_field, str):
                    is_dynamic = is_dynamic or dynamic_field.lower() == 'true'
                
                is_disabled = lease.get('disabled') == 'true'
                current_mac = lease.get('mac-address', '')
                current_server = lease.get('server', 'all')
            
                print(f"📊 DHCP: Статус lease:")
                print(f"  - Динамический: {is_dynamic}")
                print(f"  - Отключен: {is_disabled}")
                print(f"  - MAC: {current_mac}")
                print(f"  - Server: {current_server}")
            
                # Проверяем MAC адрес
                if current_mac and current_mac.lower() != mac.lower():
                    print(f"⚠️ DHCP: MAC отличается! Обновляем...")
                    try:
                        tuple(dhcp_cmd('set', **{'.id': lease_id, 'mac-address': mac}))
                        print(f"✅ DHCP: MAC обновлен")
                    except Exception as e:
                        print(f"❌ DHCP: Ошибка обновления MAC: {e}")
            
                # Обновляем поле server если нужно
                if current_server != dhcp_server:
                    print(f"🔄 DHCP: Обновляем поле server")
                    try:
                        tuple(dhcp_cmd('set', **{'.id': lease_id, 'server': dhcp_server}))
                        print(f"✅ DHCP: Поле server обновлено")
                    except Exception as e:
                        print(f"⚠️ DHCP: Ошибка обновления server: {e}")
            
                # Если lease динамический - делаем статическим
                if is_dynamic:
                    print(f"🔄 DHCP: Делаем lease статическим...")
                    
                    try:
                        result = tuple(dhcp_cmd('make-static', **{'.id': lease_id}))
                        print(f"✅ DHCP: Lease помечен как статический")
                        
                        # После make-static ID может измениться
                        leases = list(dhcp_cmd)
                        for l in leases:
                            if l.get('address') == ip:
                                new_lease_id = l.get('.id')
                                if new_lease_id:
                                    lease_id = new_lease_id
                                break
                                
                    except Exception as e:
                        print(f"⚠️ DHCP: Ошибка make-static: {e}")
                        print(f"  Пробуем set dynamic=no...")
                        
                        try:
                            tuple(dhcp_cmd('set', **{'.id': lease_id, 'dynamic': 'no'}))
                            print(f"✅ DHCP: Lease помечен как статический")
                            
                        except Exception as e2:
                            print(f"⚠️ DHCP: Ошибка set dynamic=no: {e2}")
                            print(f"  Удаляем и создаем заново...")
                            
                            try:
                                tuple(dhcp_cmd('remove', **{'.id': lease_id}))
                                print(f"✅ DHCP: Динамический lease удален")
                                
                                import time
                                time.sleep(0.5)
                                
                                mikrotik_comment = russian_to_mikrotik_comment(comment) if comment else ""
                                
                                lease_data = {
                                    'address': ip,
                                    'mac-address': mac,
                                    'disabled': 'no',
                                    'comment': mikrotik_comment
                                }
                                
                                if dhcp_server != 'all':
                                    lease_data['server'] = dhcp_server
                                
                                tuple(dhcp_cmd('add', **lease_data))
                                print(f"✅ DHCP: Новый статический lease создан")
                                
                                leases = list(dhcp_cmd)
                                for l in leases:
                                    if l.get('address') == ip:
                                        lease_id = l.get('.id')
                                        break
                                        
                            except Exception as e3:
                                print(f"❌ DHCP: Ошибка удаления/создания: {e3}")
                                return False
            
                # Если отключен - включаем
                if is_disabled:
                    print(f"🔄 DHCP: Включаем lease")
                    try:
                        tuple(dhcp_cmd('set', **{'.id': lease_id, 'disabled': 'no'}))
                        print(f"✅ DHCP: Lease включен")
                    except Exception as e:
                        print(f"⚠️ DHCP: Ошибка включения: {e}")
        
            # 4. Если lease не найден - создаем новый
            else:
                print(f"➕ DHCP: Создаем новый lease для {ip} -> {mac}")
                try:
                    mikrotik_comment = russian_to_mikrotik_comment(comment) if comment else ""
                    
                    lease_data = {
                        'address': ip,
                        'mac-address': mac,
                        'disabled': 'no',
                        'comment': mikrotik_comment
                    }
                    
                    if dhcp_server != 'all':
                        lease_data['server'] = dhcp_server
                    
                    tuple(dhcp_cmd('add', **lease_data))
                    print(f"✅ DHCP: Новый статический lease создан")
                    
                    leases = list(dhcp_cmd)
                    for l in leases:
                        if l.get('address') == ip:
                            lease_id = l.get('.id')
                            break
        
                except Exception as e:
                    print(f"❌ DHCP: Ошибка создания lease: {e}")
                    return False
        
            # 5. Добавляем/обновляем комментарий
            if lease_id and comment:
                print(f"📝 DHCP: Добавляем комментарий: {comment}")
                mikrotik_comment = russian_to_mikrotik_comment(comment)
            
                try:
                    tuple(dhcp_cmd('comment', **{'numbers': lease_id, 'comment': mikrotik_comment}))
                    print(f"✅ DHCP: Комментарий добавлен")
                except Exception as e:
                    print(f"⚠️ DHCP: Ошибка comment, пробуем set: {e}")
                    try:
                        tuple(dhcp_cmd('set', **{'.id': lease_id, 'comment': mikrotik_comment}))
                        print(f"✅ DHCP: Комментарий добавлен через set")
                    except Exception as e2:
                        print(f"⚠️ DHCP: Ошибка добавления комментария: {e2}")
        
            # 6. Финальная проверка
            print(f"🔍 DHCP: Финальная проверка...")
            if lease_id:
                leases = list(dhcp_cmd)
                for l in leases:
                    if l.get('address') == ip:
                        final_flags = l.get('flags', '')
                        
                        if 'D' in final_flags:
                            print(f"⚠️ DHCP: Lease все еще динамический!")
                            return False
                        else:
                            print(f"✅ DHCP: Lease успешно статический")
                            return True
                        
                print(f"❌ DHCP: Не удалось найти lease после обновления")
                return False
            else:
                print(f"❌ DHCP: Не удалось получить/создать lease")
                return False
            
        except Exception as e:
            print(f"❌ DHCP: Критическая ошибка: {e}")
            traceback.print_exc()
            return False

    # ========== ARP ==========
    def add_static_arp(
        self, ip: str, mac: str, comment: str = "", interface: Optional[str] = None
    ) -> bool:
        """Добавить статическую ARP запись"""
        try:
            print(f"\n🔧 ARP: Начинаем работу с {ip} -> {mac}")

            if interface is None:
                belongs, found_interface = self.is_ip_in_mikrotik_networks(ip)
                if not belongs:
                    raise ValueError(
                        f"IP {ip} не принадлежит сетям микротика! ARP запись не может быть добавлена."
                    )
                interface = found_interface

            arp_cmd = self.api.path("/ip/arp")

            # Проверяем существующую запись
            print(f"🔍 ARP: Проверяем существующие записи")
            arp_entries = list(arp_cmd)
            for entry in arp_entries:
                if entry.get("address") == ip:
                    print(f"⚠️ ARP: Запись для {ip} уже существует")
                    return True

            # Добавляем новую запись
            print(f"➕ ARP: Добавляем новую запись")
            print(f"   📍 Интерфейс: {interface}")
            mikrotik_comment = russian_to_mikrotik_comment(comment) if comment else ""

            try:
                tuple(
                    arp_cmd(
                        "add",
                        **{
                            "address": ip,
                            "mac-address": mac,
                            "interface": interface,
                            "disabled": "no",
                            "comment": mikrotik_comment,
                        },
                    )
                )
                print(f"✅ ARP: Запись успешно добавлена")
                return True

            except Exception as e:
                print(f"❌ ARP: Ошибка добавления: {e}")
                return False

        except ValueError as e:
            print(f"❌ ARP: {e}")
            raise
        except Exception as e:
            print(f"❌ ARP: Критическая ошибка: {e}")
            traceback.print_exc()
            return False

    # ========== FIREWALL ==========
    def add_to_address_list(
        self, list_name: str, address: str, comment: str = ""
    ) -> bool:
        """Добавить адрес в список"""
        try:
            print(f"\n🔧 Firewall: Добавление {address} в список '{list_name}'")

            fw_cmd = self.api.path("/ip/firewall/address-list")

            # Проверяем существующую запись
            print(f"🔍 Firewall: Проверяем существующие записи")
            addresses = list(fw_cmd)

            for addr in addresses:
                if addr.get("list") == list_name and addr.get("address") == address:
                    print(f"⚠️ Firewall: Адрес {address} уже в списке {list_name}")
                    return True

            # Добавляем новую запись
            print(f"➕ Firewall: Добавляем {address} в список {list_name}")
            mikrotik_comment = russian_to_mikrotik_comment(comment) if comment else ""

            try:
                tuple(
                    fw_cmd(
                        "add",
                        **{
                            "list": list_name,
                            "address": address,
                            "comment": mikrotik_comment,
                            "disabled": "no",
                        },
                    )
                )
                print(f"✅ Firewall: Адрес успешно добавлен")
                return True

            except Exception as e:
                print(f"❌ Firewall: Ошибка добавления: {e}")
                return False

        except Exception as e:
            print(f"❌ Firewall: Критическая ошибка: {e}")
            traceback.print_exc()
            return False

    def get_internet_access_list(self) -> List[str]:
        """Получить список IP с доступом в интернет (из address-list internet_access)"""
        try:
            fw_cmd = self.api.path("/ip/firewall/address-list")
            addresses = list(fw_cmd)
            
            internet_ips = []
            for addr in addresses:
                if addr.get("list") == "internet_access" and not addr.get("disabled", False):
                    ip = addr.get("address", "")
                    if ip:
                        internet_ips.append(ip)
            
            print(f"📋 Найдено {len(internet_ips)} IP с доступом в интернет")
            return internet_ips
            
        except Exception as e:
            print(f"❌ Ошибка получения internet_access: {e}")
            traceback.print_exc()
            return []

    def check_internet_access(self, ip: str) -> bool:
        """Проверить, есть ли IP в списке internet_access"""
        try:
            fw_cmd = self.api.path("/ip/firewall/address-list")
            addresses = list(fw_cmd)
            
            for addr in addresses:
                if addr.get("list") == "internet_access" and addr.get("address") == ip:
                    return not addr.get("disabled", False)
            
            return False
            
        except Exception as e:
            print(f"❌ Ошибка проверки доступа: {e}")
            return False

    def add_internet_access(self, ip: str, comment: str = "") -> bool:
        """Добавить IP в список internet_access"""
        return self.add_to_address_list("internet_access", ip, comment)

    def remove_internet_access(self, ip: str) -> bool:
        """Удалить IP из списка internet_access"""
        try:
            print(f"🔧 Удаление {ip} из internet_access...")
            
            fw_cmd = self.api.path("/ip/firewall/address-list")
            addresses = list(fw_cmd)
            
            for addr in addresses:
                if addr.get("list") == "internet_access" and addr.get("address") == ip:
                    addr_id = addr.get(".id")
                    if addr_id:
                        tuple(fw_cmd("remove", **{".id": addr_id}))
                        print(f"✅ IP {ip} удалён из internet_access")
                        return True
            
            print(f"⚠️ IP {ip} не найден в internet_access")
            return True  # Не ошибка, если уже нет в списке
            
        except Exception as e:
            print(f"❌ Ошибка удаления из internet_access: {e}")
            traceback.print_exc()
            return False

    def toggle_internet_access(self, ip: str, enable: bool, comment: str = "") -> Dict:
        """Включить/выключить доступ в интернет для IP"""
        result = {
            'success': False,
            'ip': ip,
            'enabled': enable,
            'error': None
        }
        
        try:
            if enable:
                if self.add_internet_access(ip, comment):
                    result['success'] = True
                    result['message'] = f"Доступ в интернет включён для {ip}"
                else:
                    result['error'] = "Не удалось добавить в список"
            else:
                if self.remove_internet_access(ip):
                    result['success'] = True
                    result['message'] = f"Доступ в интернет выключен для {ip}"
                else:
                    result['error'] = "Не удалось удалить из списка"
                    
        except Exception as e:
            result['error'] = str(e)
            
        return result

    # ========== QUEUES ==========
    def get_queues(self) -> List[Dict]:
        """Получить все активные очереди"""
        try:
            print("📡 Получение очередей с MikroTik...")
            queues = list(self.api("/queue/simple/print"))
            print(f"📊 Получено {len(queues)} очередей")

            if not queues:
                print("⚠️ Очереди не найдены!")
                return []

            # Фильтруем отключенные очереди
            active_queues = []

            for queue in queues:
                flags = queue.get("flags", "")
                disabled_value = queue.get("disabled", "")

                disabled = False
                if isinstance(disabled_value, bool):
                    disabled = disabled_value
                elif isinstance(disabled_value, str):
                    disabled = disabled_value.lower() == "true"

                is_disabled_by_flags = "X" in flags

                if not disabled and not is_disabled_by_flags:
                    active_queues.append(queue)

            print(f"✅ Активных: {len(active_queues)}")
            return active_queues

        except Exception as e:
            print(f"❌ Ошибка получения очередей: {e}")
            traceback.print_exc()
            return []

    def add_ip_to_queue(self, queue_id: str, ip: str) -> bool:
        """Добавить IP в очередь"""
        try:
            print(f"\n🔧 Queue: Добавление IP {ip} в очередь ID: {queue_id}")

            queue_cmd = self.api.path("/queue/simple")

            # Получаем текущую очередь
            print(f"🔍 Queue: Получаем данные очереди")
            queues = list(queue_cmd)
            current_target = ""

            for queue in queues:
                if queue.get(".id") == queue_id:
                    current_target = queue.get("target", "")
                    print(f"✅ Queue: Найдена очередь, target: {current_target}")
                    break

            if not current_target:
                print(f"⚠️ Queue: Очередь не найдена или пустая")
                current_target = ""

            # Формируем новый target
            if "/" in ip:
                ip_with_mask = ip
            else:
                ip_with_mask = f"{ip}/32"

            if current_target:
                new_target = f"{current_target},{ip_with_mask}"
            else:
                new_target = ip_with_mask

            print(f"🔄 Queue: Новый target: {new_target}")

            # Обновляем очередь
            try:
                tuple(queue_cmd("set", **{".id": queue_id, "target": new_target}))
                print(f"✅ Queue: Очередь успешно обновлена")
                return True

            except Exception as e:
                print(f"❌ Queue: Ошибка обновления: {e}")
                try:
                    self.api("/queue/simple/set", **{".id": queue_id, "target": new_target})
                    print(f"✅ Queue: Очередь обновлена (альтернативным методом)")
                    return True
                except Exception as e2:
                    print(f"❌ Queue: Ошибка альтернативного метода: {e2}")
                    return False

        except Exception as e:
            print(f"❌ Queue: Критическая ошибка: {e}")
            traceback.print_exc()
            return False

    # ========== DHCP POOLS ==========
    def get_dhcp_pools(self) -> List[Dict]:
        """Получить DHCP пулы"""
        try:
            pools_cmd = self.api.path('/ip/pool')
            pools = list(pools_cmd)
            return pools
        except Exception as e:
            print(f"❌ Ошибка получения DHCP пулов: {e}")
            return []

    def get_dhcp_leases(self) -> List[Dict]:
        """Получить все DHCP leases"""
        try:
            leases_cmd = self.api.path('/ip/dhcp-server/lease')
            leases = list(leases_cmd)
            return leases
        except Exception as e:
            print(f"❌ Ошибка получения DHCP leases: {e}")
            return []

    def get_free_dhcp_ips(self, max_per_pool: int = 20) -> Dict[str, List[str]]:
        """Получить свободные IP адреса из DHCP пулов"""
        try:
            print(f"🔍 Поиск свободных IP адресов в DHCP пулах...")
            
            # Получаем все пулы
            pools = self.get_dhcp_pools()
            print(f"📊 Найдено пулов DHCP: {len(pools)}")
            
            # Получаем все leases
            leases = self.get_dhcp_leases()
            used_ips = {lease.get('address') for lease in leases if lease.get('address')}
            print(f"📊 Используется IP адресов: {len(used_ips)}")
            
            # Анализируем каждый пул
            free_ips_by_pool = {}
            
            for pool in pools:
                pool_name = pool.get('name', 'unknown')
                ranges = pool.get('ranges', '')
                
                if not ranges:
                    continue
                
                print(f"🔍 Анализ пула '{pool_name}': {ranges}")
                
                # Парсим диапазоны IP
                pool_ips = set()
                for ip_range in ranges.split(','):
                    if ip_range.strip():
                        ips = self._parse_ip_range(ip_range.strip())
                        pool_ips.update(ips)
                
                if not pool_ips:
                    continue
                
                # Находим свободные IP
                free_ips = sorted(
                    pool_ips - used_ips,
                    key=lambda x: [int(part) for part in x.split('.')]
                )
                
                # Ограничиваем количество для отображения
                display_ips = free_ips[:max_per_pool]
                
                free_ips_by_pool[pool_name] = {
                    'total_ips': len(pool_ips),
                    'used_ips': len(pool_ips.intersection(used_ips)),
                    'free_ips': len(free_ips),
                    'free_list': display_ips,
                    'has_more': len(free_ips) > max_per_pool,
                    'ranges': ranges
                }
                
                print(f"   📊 Свободно: {len(free_ips)}/{len(pool_ips)}")
            
            return free_ips_by_pool
            
        except Exception as e:
            print(f"❌ Ошибка поиска свободных IP: {e}")
            traceback.print_exc()
            return {}
    
    def _parse_ip_range(self, ip_range: str) -> List[str]:
        """Преобразовать диапазон IP в список адресов"""
        ip_range = ip_range.strip()
        
        if '-' in ip_range:
            # Формат: 192.168.1.100-192.168.1.200
            start_ip, end_ip = ip_range.split('-')
            try:
                start = ipaddress.IPv4Address(start_ip.strip())
                end = ipaddress.IPv4Address(end_ip.strip())
                return [str(ipaddress.IPv4Address(ip)) for ip in range(int(start), int(end) + 1)]
            except (ipaddress.AddressValueError, ValueError) as e:
                print(f"⚠️ Ошибка парсинга диапазона {ip_range}: {e}")
                return []
        elif '/' in ip_range:
            # Формат: 192.168.1.0/24
            try:
                network = ipaddress.IPv4Network(ip_range, strict=False)
                return [str(ip) for ip in network.hosts()]
            except ipaddress.AddressValueError as e:
                print(f"⚠️ Ошибка парсинга сети {ip_range}: {e}")
                return []
        else:
            # Одиночный IP
            try:
                ipaddress.IPv4Address(ip_range)
                return [ip_range]
            except ipaddress.AddressValueError as e:
                print(f"⚠️ Ошибка парсинга IP {ip_range}: {e}")
                return []

    # ========== MAC REPLACEMENT FUNCTIONALITY ==========
    
    def get_arp_table(self) -> List[Dict]:
        """Получить ARP таблицу"""
        try:
            arp_cmd = self.api.path('/ip/arp')
            arp_list = list(arp_cmd)
            return arp_list
        except Exception as e:
            print(f"❌ Ошибка получения ARP таблицы: {e}")
            return []

    def delete_dhcp_lease(self, ip: str) -> bool:
        """Удалить DHCP lease по IP адресу"""
        try:
            # Находим lease по IP
            lease = self.find_dhcp_lease(ip=ip)
            if not lease:
                print(f"⚠️ DHCP lease для IP {ip} не найден")
                return False
            
            lease_id = lease.get('.id')
            if not lease_id:
                print(f"❌ Не удалось получить ID lease для IP {ip}")
                return False
            
            # Удаляем lease
            dhcp_cmd = self.api.path('/ip/dhcp-server/lease')
            tuple(dhcp_cmd('remove', **{'.id': lease_id}))
            print(f"✅ DHCP lease для IP {ip} удален")
            return True
            
        except Exception as e:
            print(f"❌ Ошибка удаления DHCP lease: {e}")
            traceback.print_exc()
            return False

    def update_dhcp_lease(self, old_ip: str, new_mac: str, comment: str = "") -> bool:
        """Обновить DHCP lease - найти по старому IP, установить новый MAC"""
        try:
            # Находим lease по старому IP
            lease = self.find_dhcp_lease(ip=old_ip)
            if not lease:
                print(f"⚠️ DHCP lease для IP {old_ip} не найден")
                return False
            
            lease_id = lease.get('.id')
            if not lease_id:
                print(f"❌ Не удалось получить ID lease для IP {old_ip}")
                return False
            
            # Обновляем MAC и комментарий
            dhcp_cmd = self.api.path('/ip/dhcp-server/lease')
            update_data = {'.id': lease_id, 'mac-address': new_mac.lower()}
            if comment:
                update_data['comment'] = comment
            
            tuple(dhcp_cmd('set', **update_data))
            print(f"✅ DHCP lease обновлен: IP={old_ip}, MAC={new_mac}")
            return True
            
        except Exception as e:
            print(f"❌ Ошибка обновления DHCP lease: {e}")
            traceback.print_exc()
            return False

    def update_arp_entry(self, ip: str, new_mac: str) -> bool:
        """Обновить MAC адрес в ARP таблице"""
        try:
            # Находим ARP запись по IP
            arp_cmd = self.api.path('/ip/arp')
            arp_entries = list(arp_cmd)
            
            arp_id = None
            for entry in arp_entries:
                if entry.get('address') == ip:
                    arp_id = entry.get('.id')
                    break
            
            if not arp_id:
                print(f"⚠️ ARP запись для IP {ip} не найдена")
                return False
            
            # Обновляем MAC
            tuple(arp_cmd('set', **{'.id': arp_id, 'mac-address': new_mac.lower()}))
            print(f"✅ ARP запись обновлена: IP={ip}, MAC={new_mac}")
            return True
            
        except Exception as e:
            print(f"❌ Ошибка обновления ARP записи: {e}")
            traceback.print_exc()
            return False

    def add_arp_entry(self, ip: str, mac: str, interface: str = None, comment: str = "") -> bool:
        """Добавить статическую ARP запись"""
        try:
            arp_cmd = self.api.path('/ip/arp')
            
            arp_data = {
                'address': ip,
                'mac-address': mac.lower(),
                'comment': comment
            }
            
            if interface:
                arp_data['interface'] = interface
            
            tuple(arp_cmd('add', **arp_data))
            print(f"✅ ARP запись добавлена: IP={ip}, MAC={mac}")
            return True
            
        except Exception as e:
            print(f"❌ Ошибка добавления ARP записи: {e}")
            traceback.print_exc()
            return False

    def get_dhcp_subscribers(self, pool_name: str = None) -> List[Dict]:
        """
        Получить список абонентов из DHCP leases
        Абоненты - все leases (с комментарием или без)
    
        Args:
            pool_name: Имя DHCP пула для фильтрации (если None - все абоненты)
        """
        try:
            leases = self.get_dhcp_leases()
        
            # Получаем информацию о пулах если нужна фильтрация
            pool_ranges = {}
            if pool_name:
                pools = self.get_dhcp_pools()
                for pool in pools:
                    if pool.get('name') == pool_name:
                        ranges = pool.get('ranges', '')
                        if ranges:
                            # Парсим диапазоны пула
                            for range_str in ranges.split(','):
                                range_str = range_str.strip()
                                if '-' in range_str:
                                    try:
                                        start_ip, end_ip = range_str.split('-')
                                        pool_ranges[(start_ip.strip(), end_ip.strip())] = True
                                    except:
                                        pass
                        break
        
            subscribers = []
        
            for lease in leases:
                comment = lease.get('comment', '')
                ip = lease.get('address', '')
            
                # Если указан пул, проверяем принадлежность IP к диапазону пула
                if pool_name and pool_ranges:
                    ip_in_pool = False
                    try:
                        ip_obj = ipaddress.ip_address(ip.split('/')[0])
                        for (start, end) in pool_ranges.keys():
                            start_obj = ipaddress.ip_address(start)
                            end_obj = ipaddress.ip_address(end)
                            if start_obj <= ip_obj <= end_obj:
                                ip_in_pool = True
                                break
                    except:
                        pass
                
                    if not ip_in_pool:
                        continue
            
                subscriber = {
                    'ip': ip,
                    'mac': lease.get('mac-address', ''),
                    'comment': comment,
                    'host_name': lease.get('host-name', ''),
                    'dynamic': lease.get('dynamic') == 'true',
                    'disabled': lease.get('disabled') == 'true',
                    'server': lease.get('server', ''),
                    'id': lease.get('.id', '')
                }
                subscribers.append(subscriber)
        
            # Безопасная сортировка по IP
            def safe_ip_sort(item):
                try:
                    ip_str = item.get('ip', '')
                    if ip_str:
                        # Убираем маску если есть
                        ip_str = ip_str.split('/')[0]
                        return (0, ipaddress.ip_address(ip_str))
                    return (1, ipaddress.ip_address('0.0.0.0'))
                except:
                    return (2, ipaddress.ip_address('0.0.0.0'))
        
            subscribers.sort(key=safe_ip_sort)
        
            if pool_name:
                print(f"✅ Найдено абонентов в пуле '{pool_name}': {len(subscribers)}")
            else:
                print(f"✅ Найдено абонентов: {len(subscribers)}")
            return subscribers
        
        except Exception as e:
            print(f"❌ Ошибка получения абонентов: {e}")
            traceback.print_exc()
            return []

    def replace_mac_address(self, old_ip: str, new_ip: str) -> Dict:
        """
        Замена MAC адреса у абонента
        
        Сценарий: У абонента заменилось устройство. Старый IP сохраняем,
        а MAC и ClientID берём от нового устройства.
        
        Алгоритм:
        1. Получаем комментарий со старого IP
        2. Получаем MAC и ClientID с нового IP
        3. Удаляем lease старого IP
        4. На lease нового IP меняем IP на старый и добавляем комментарий
        5. Обновляем ARP таблицу
        
        Args:
            old_ip: IP адрес абонента (настройки которого сохраняем)
            new_ip: IP нового устройства (откуда берём MAC и ClientID)
        
        Возвращает результат операции
        """
        result = {
            'success': False,
            'steps': [],
            'error': None
        }
        
        try:
            # Шаг 1: Получаем данные со старого IP (сохраняем комментарий)
            result['steps'].append(f"📡 Получение данных со старого IP {old_ip}...")
            old_lease = self.find_dhcp_lease(ip=old_ip)
            if not old_lease:
                result['error'] = f"DHCP lease для IP {old_ip} не найден"
                return result
            
            old_comment = old_lease.get('comment', '')
            old_mac = old_lease.get('mac-address', '')
            result['steps'].append(f"   Комментарий: {old_comment or '(пусто)'}")
            result['steps'].append(f"   Старый MAC: {old_mac}")
            
            # Шаг 2: Получаем данные с нового IP (MAC и ClientID нового устройства)
            result['steps'].append(f"📡 Получение данных с нового IP {new_ip}...")
            new_lease = self.find_dhcp_lease(ip=new_ip)
            if not new_lease:
                result['error'] = f"DHCP lease для IP {new_ip} не найден. Новое устройство не подключено?"
                return result
            
            new_mac = new_lease.get('mac-address', '')
            new_client_id = new_lease.get('client-id', '')
            new_lease_id = new_lease.get('.id', '')
            
            if not new_mac:
                result['error'] = f"MAC адрес для IP {new_ip} не найден"
                return result
            
            result['steps'].append(f"   Новый MAC: {new_mac}")
            if new_client_id:
                result['steps'].append(f"   ClientID: {new_client_id}")
            
            # Шаг 3: Удаляем старый DHCP lease
            result['steps'].append(f"🗑️ Удаление старого DHCP lease ({old_ip})...")
            if not self.delete_dhcp_lease(old_ip):
                result['error'] = f"Не удалось удалить DHCP lease для IP {old_ip}"
                return result
            result['steps'].append(f"   ✅ Удалён")
            
            # Шаг 4: Обновляем lease нового IP - меняем IP на старый, добавляем комментарий
            result['steps'].append(f"📝 Обновление DHCP lease ({new_ip} → {old_ip})...")
            
            # Получаем свежий ID lease (после удаления старого)
            new_lease_fresh = self.find_dhcp_lease(ip=new_ip)
            if not new_lease_fresh:
                result['error'] = f"DHCP lease для IP {new_ip} исчез после удаления старого"
                return result
            
            lease_id = new_lease_fresh.get('.id')
            
            dhcp_cmd = self.api.path('/ip/dhcp-server/lease')
            update_data = {
                '.id': lease_id,
                'address': old_ip,
                'comment': old_comment
            }
            # MAC и ClientID остаются от нового устройства (не меняем)
            
            tuple(dhcp_cmd('set', **update_data))
            result['steps'].append(f"   ✅ IP изменён на {old_ip}")
            result['steps'].append(f"   ✅ Комментарий перенесён")
            result['steps'].append(f"   ✅ MAC: {new_mac} (от нового устройства)")
            if new_client_id:
                result['steps'].append(f"   ✅ ClientID сохранён")
            
            # Шаг 5: Обновляем ARP таблицу
            result['steps'].append(f"📝 Обновление ARP таблицы...")
            if self.update_arp_entry(old_ip, new_mac):
                result['steps'].append(f"   ✅ ARP обновлён: {old_ip} → {new_mac}")
            else:
                result['steps'].append(f"   ⚠️ ARP запись не обновлена (возможно отсутствует)")
            
            result['success'] = True
            result['message'] = f"MAC адрес успешно заменён. IP {old_ip} теперь привязан к MAC {new_mac}"
            
            print(f"✅ Замена MAC завершена: {old_ip} → MAC {new_mac}")
            return result
            
        except Exception as e:
            result['error'] = f"Ошибка при замене MAC: {str(e)}"
            result['steps'].append(f"❌ Ошибка: {str(e)}")
            print(f"❌ Ошибка замены MAC: {e}")
            traceback.print_exc()
            return result

    def replace_mac_manual(self, ip: str, new_mac: str, client_id: str = None) -> Dict:
        """
        Ручная замена MAC адреса на указанном IP
        
        Алгоритм:
        1. Находим lease по IP
        2. Обновляем MAC адрес
        3. Обновляем ClientID (если указан)
        4. Обновляем ARP таблицу
        
        Args:
            ip: IP адрес абонента
            new_mac: Новый MAC адрес
            client_id: Новый ClientID (опционально, формат: 1:aa:bb:cc:dd:ee:ff)
        
        Возвращает результат операции
        """
        result = {
            'success': False,
            'steps': [],
            'error': None
        }
        
        try:
            # Шаг 1: Получаем текущий lease
            result['steps'].append(f"📡 Поиск DHCP lease для IP {ip}...")
            lease = self.find_dhcp_lease(ip=ip)
            if not lease:
                result['error'] = f"DHCP lease для IP {ip} не найден"
                return result
            
            lease_id = lease.get('.id')
            old_mac = lease.get('mac-address', '')
            old_comment = lease.get('comment', '')
            
            result['steps'].append(f"   Найден lease ID: {lease_id}")
            result['steps'].append(f"   Текущий MAC: {old_mac}")
            result['steps'].append(f"   Комментарий: {old_comment or '(пусто)'}")
            
            # Шаг 2: Обновляем MAC и ClientID в lease
            result['steps'].append(f"📝 Обновление MAC адреса...")
            
            dhcp_cmd = self.api.path('/ip/dhcp-server/lease')
            update_data = {
                '.id': lease_id,
                'mac-address': new_mac.upper()  # RouterOS ожидает MAC в верхнем регистре
            }
            
            if client_id:
                update_data['client-id'] = client_id.lower()  # ClientID в нижнем регистре
                result['steps'].append(f"   Новый MAC: {new_mac}")
                result['steps'].append(f"   Новый ClientID: {client_id}")
            else:
                result['steps'].append(f"   Новый MAC: {new_mac}")
            
            tuple(dhcp_cmd('set', **update_data))
            result['steps'].append(f"   ✅ DHCP lease обновлён")
            
            # Шаг 3: Обновляем ARP таблицу
            result['steps'].append(f"📝 Обновление ARP таблицы...")
            if self.update_arp_entry(ip, new_mac):
                result['steps'].append(f"   ✅ ARP обновлён: {ip} → {new_mac}")
            else:
                result['steps'].append(f"   ⚠️ ARP запись не обновлена (возможно отсутствует)")
            
            result['success'] = True
            result['message'] = f"MAC адрес успешно изменён. IP {ip} теперь привязан к MAC {new_mac}"
            
            print(f"✅ Ручная замена MAC завершена: {ip} → {new_mac}")
            return result
            
        except Exception as e:
            result['error'] = f"Ошибка при замене MAC: {str(e)}"
            result['steps'].append(f"❌ Ошибка: {str(e)}")
            print(f"❌ Ошибка ручной замены MAC: {e}")
            traceback.print_exc()
            return result

    def remove_subscriber(self, ip_address: str) -> Dict:
        """
        Полное удаление абонента по IP из:
        - DHCP Leases
        - ARP таблицы
        - Firewall Address Lists
        - Simple Queues
        """
        result = {
            'success': False,
            'ip': ip_address,
            'dhcp_leases': [],
            'arp': [],
            'firewall_lists': [],
            'queues': [],
            'total_removed': 0,
            'steps': []
        }
        
        if not self.api:
            result['error'] = 'Нет соединения с MikroTik'
            return result
        
        try:
            ip_clean = ip_address.split('/')[0]
            result['steps'].append(f"🔍 Удаление абонента: {ip_clean}")
            
            # 1. Удаление из DHCP Lease
            result['steps'].append("📋 DHCP Leases:")
            try:
                for lease in self.api.path('/ip/dhcp-server/lease'):
                    lease_addr = lease.get('address', '')
                    if lease_addr == ip_address or lease_addr == ip_clean:
                        lease_id = lease.get('.id')
                        if lease_id:
                            self.api.path('/ip/dhcp-server/lease').remove(lease_id)
                            result['dhcp_leases'].append({
                                'address': lease_addr,
                                'mac': lease.get('mac-address', 'N/A')
                            })
                            result['steps'].append(f"   ✅ Удалён lease: {lease_addr}")
                            result['total_removed'] += 1
            except Exception as e:
                result['steps'].append(f"   ❌ Ошибка: {e}")
            
            # 2. Удаление из ARP таблицы
            result['steps'].append("📋 ARP таблица:")
            try:
                for arp in self.api.path('/ip/arp'):
                    if arp.get('address') == ip_clean:
                        arp_id = arp.get('.id')
                        if arp_id:
                            self.api.path('/ip/arp').remove(arp_id)
                            result['arp'].append({'address': ip_clean})
                            result['steps'].append(f"   ✅ Удалена ARP запись")
                            result['total_removed'] += 1
            except Exception as e:
                result['steps'].append(f"   ❌ Ошибка: {e}")
            
            # 3. Удаление из Firewall Address Lists
            result['steps'].append("📋 Firewall Address Lists:")
            try:
                for addr in self.api.path('/ip/firewall/address-list'):
                    addr_value = addr.get('address', '')
                    if addr_value == ip_address or addr_value == ip_clean:
                        addr_id = addr.get('.id')
                        if addr_id:
                            list_name = addr.get('list', 'N/A')
                            self.api.path('/ip/firewall/address-list').remove(addr_id)
                            result['firewall_lists'].append({
                                'list': list_name,
                                'address': addr_value
                            })
                            result['steps'].append(f"   ✅ Удалён из списка '{list_name}'")
                            result['total_removed'] += 1
            except Exception as e:
                result['steps'].append(f"   ❌ Ошибка: {e}")
            
            # 4. Обработка Simple Queues
            result['steps'].append("📋 Simple Queues:")
            try:
                for queue in self.api.path('/queue/simple'):
                    target = queue.get('target', '')
                    if target and ip_clean in target:
                        queue_id = queue.get('.id')
                        queue_name = queue.get('name', 'N/A')
                        
                        addresses = [a.strip() for a in target.split(',')]
                        new_addresses = [a for a in addresses if ip_clean not in a]
                        
                        if len(new_addresses) < len(addresses):
                            if new_addresses:
                                new_target = ','.join(new_addresses)
                                self.api.path('/queue/simple').update(**{
                                    '.id': queue_id, 
                                    'target': new_target
                                })
                                result['steps'].append(f"   ✅ Обновлена очередь '{queue_name}'")
                                result['queues'].append({
                                    'name': queue_name,
                                    'action': 'updated'
                                })
                            else:
                                self.api.path('/queue/simple').remove(queue_id)
                                result['steps'].append(f"   ✅ Удалена очередь '{queue_name}' (пустой target)")
                                result['queues'].append({
                                    'name': queue_name,
                                    'action': 'deleted'
                                })
                            result['total_removed'] += 1
            except Exception as e:
                result['steps'].append(f"   ❌ Ошибка: {e}")
            
            result['success'] = True
            result['message'] = f"Удалено элементов: {result['total_removed']}"
            print(f"✅ Удаление абонента {ip_clean} завершено. Всего: {result['total_removed']}")
            return result
            
        except Exception as e:
            result['error'] = str(e)
            result['steps'].append(f"❌ Критическая ошибка: {e}")
            print(f"❌ Ошибка удаления абонента: {e}")
            traceback.print_exc()
            return result
