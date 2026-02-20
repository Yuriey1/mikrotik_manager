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
            
            pools = self.get_dhcp_pools()
            print(f"📊 Найдено пулов DHCP: {len(pools)}")
            
            leases = self.get_dhcp_leases()
            used_ips = {lease.get('address') for lease in leases if lease.get('address')}
            print(f"📊 Используется IP адресов: {len(used_ips)}")
            
            free_ips_by_pool = {}
            
            for pool in pools:
                pool_name = pool.get('name', 'unknown')
                ranges = pool.get('ranges', '')
                
                if not ranges:
                    continue
                
                # Парсим диапазоны
                free_ips = []
                for range_str in ranges.split(','):
                    range_str = range_str.strip()
                    if '-' in range_str:
                        try:
                            start_ip, end_ip = range_str.split('-')
                            start = ipaddress.ip_address(start_ip.strip())
                            end = ipaddress.ip_address(end_ip.strip())
                            
                            # Перебираем IP в диапазоне
                            current = start
                            count = 0
                            while current <= end and count < max_per_pool:
                                ip_str = str(current)
                                if ip_str not in used_ips:
                                    free_ips.append(ip_str)
                                    count += 1
                                current += 1
                        except Exception as e:
                            print(f"⚠️ Ошибка парсинга диапазона {range_str}: {e}")
                            continue
                
                if free_ips:
                    free_ips_by_pool[pool_name] = free_ips
            
            print(f"✅ Найдено свободных IP: {sum(len(ips) for ips in free_ips_by_pool.values())}")
            return free_ips_by_pool
            
        except Exception as e:
            print(f"❌ Ошибка поиска свободных IP: {e}")
            traceback.print_exc()
            return {}
