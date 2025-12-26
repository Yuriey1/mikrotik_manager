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

    # ========== НОВЫЕ МЕТОДЫ ДЛЯ ПРОВЕРКИ IP ==========
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

    def get_mac_from_dhcp(self, ip: str) -> Optional[str]:
        """Получить MAC адрес из DHCP по IP"""
        try:
            print(f"🔍 Поиск MAC для IP {ip} в DHCP...")

            lease = self.find_dhcp_lease(ip)
            if lease and "mac-address" in lease:
                mac = lease["mac-address"]
                print(f"✅ MAC найден в DHCP: {mac}")
                return mac
            else:
                print(f"⚠️ MAC для IP {ip} не найден в DHCP")
                return None

        except Exception as e:
            print(f"❌ Ошибка поиска MAC в DHCP: {e}")
            return None

    def get_all_queues(self) -> List[Dict]:
        """Получить все очереди микротика"""
        try:
            print("🔍 Получение списка очередей...")
            queues = list(self.api("/queue/simple/print"))
            print(f"✅ Получено {len(queues)} очередей")
            return queues
        except Exception as e:
            print(f"❌ Ошибка получения очередей: {e}")
            return []

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

    def update_dhcp_server_field(self, ip: str) -> bool:
        """Обновить поле server у существующего DHCP lease"""
        try:
            print(f"\n🔧 DHCP: Обновление поля server для {ip}")
            
            dhcp_cmd = self.api.path('/ip/dhcp-server/lease')
            
            # Находим существующий lease
            leases = list(dhcp_cmd)
            lease_id = None
            current_server = None
            
            for lease in leases:
                if lease.get('address') == ip:
                    lease_id = lease.get('.id')
                    current_server = lease.get('server', 'all')
                    print(f"🔍 Найден lease ID: {lease_id}, текущий server: '{current_server}'")
                    break
            
            if not lease_id:
                print(f"⚠️ Lease для {ip} не найден")
                return False
            
            # Определяем правильный DHCP сервер
            dhcp_server = self._find_dhcp_server_for_ip(ip)
            if not dhcp_server:
                print(f"⚠️ Не найден подходящий DHCP сервер, оставляем как есть")
                return True
            
            print(f"✅ Правильный DHCP сервер: {dhcp_server}")
            
            # Если server уже правильный, ничего не делаем
            if current_server == dhcp_server:
                print(f"✅ Поле server уже правильное")
                return True
            
            # Обновляем поле server
            try:
                tuple(dhcp_cmd('set', **{
                    '.id': lease_id,
                    'server': dhcp_server
                }))
                print(f"✅ Поле server обновлено с '{current_server}' на '{dhcp_server}'")
                return True
            except Exception as e:
                print(f"❌ Ошибка обновления поля server: {e}")
                return False
                
        except Exception as e:
            print(f"❌ Ошибка обновления DHCP server: {e}")
            traceback.print_exc()
            return False

    def create_static_lease(self, ip: str, mac: str, comment: str = "") -> bool:
        """Создать/обновить статический DHCP lease (УМНАЯ ЛОГИКА)"""
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
                # В MikroTik динамические leases имеют флаг 'D' в поле flags
                flags = lease.get('flags', '')
                print(f"📊 DHCP: Поле 'flags': '{flags}'")
                
                # Проверяем наличие флага D (DYNAMIC)
                is_dynamic = 'D' in flags
                
                # Также проверяем поле dynamic для совместимости
                dynamic_field = lease.get('dynamic', '')
                print(f"📊 DHCP: Поле 'dynamic': '{dynamic_field}'")
                
                # Если поле dynamic есть, тоже учитываем его
                if isinstance(dynamic_field, bool):
                    is_dynamic = is_dynamic or dynamic_field
                elif isinstance(dynamic_field, str):
                    is_dynamic = is_dynamic or dynamic_field.lower() == 'true'
                
                is_disabled = lease.get('disabled') == 'true'
                current_mac = lease.get('mac-address', '')
                current_comment = lease.get('comment', '')
                current_server = lease.get('server', 'all')
            
                print(f"📊 DHCP: Статус lease:")
                print(f"  - Динамический (по флагу D): {'D' in flags}")
                print(f"  - Динамический (определено): {is_dynamic}")
                print(f"  - Отключен: {is_disabled}")
                print(f"  - MAC: {current_mac}")
                print(f"  - Server: {current_server}")
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
            
                # 2b. Обновляем поле server если нужно
                if current_server != dhcp_server:
                    print(f"🔄 DHCP: Обновляем поле server с '{current_server}' на '{dhcp_server}'")
                    try:
                        tuple(dhcp_cmd('set', **{
                            '.id': lease_id,
                            'server': dhcp_server
                        }))
                        print(f"✅ DHCP: Поле server обновлено")
                    except Exception as e:
                        print(f"⚠️ DHCP: Ошибка обновления server: {e}")
            
                # 2c. Если lease динамический - делаем статическим
                if is_dynamic:
                    print(f"🔄 DHCP: Делаем динамический lease статическим")
                    print(f"  Метод 1: Пробуем make-static...")
                    
                    try:
                        # Метод 1: make-static - самый правильный способ
                        result = tuple(dhcp_cmd('make-static', **{'.id': lease_id}))
                        print(f"✅ DHCP: Lease помечен как статический через make-static")
                        print(f"  Результат make-static: {result}")
                        
                        # После make-static ID может измениться, перезагружаем
                        leases = list(dhcp_cmd)
                        new_lease_id = None
                        for l in leases:
                            if l.get('address') == ip:
                                new_lease_id = l.get('.id')
                                new_flags = l.get('flags', '')
                                print(f"🔄 DHCP: Обновленный lease ID: {new_lease_id}, флаги: {new_flags}")
                                # Обновляем lease_id для дальнейшего использования
                                if new_lease_id:
                                    lease_id = new_lease_id
                                break
                                
                    except Exception as e:
                        print(f"⚠️ DHCP: Ошибка make-static: {e}")
                        print(f"  Метод 2: Пробуем set dynamic=no...")
                        
                        try:
                            # Метод 2: set dynamic=no
                            tuple(dhcp_cmd('set', **{
                                '.id': lease_id,
                                'dynamic': 'no'
                            }))
                            print(f"✅ DHCP: Lease помечен как статический через set dynamic=no")
                            
                        except Exception as e2:
                            print(f"⚠️ DHCP: Ошибка set dynamic=no: {e2}")
                            print(f"  Метод 3: Удаляем и создаем заново...")
                            
                            try:
                                # Метод 3: Удаляем и создаем статический заново
                                # Сначала удаляем динамический
                                tuple(dhcp_cmd('remove', **{'.id': lease_id}))
                                print(f"✅ DHCP: Динамический lease удален")
                                
                                # Ждем немного
                                import time
                                time.sleep(0.5)
                                
                                # Создаем новый статический
                                mikrotik_comment = russian_to_mikrotik_comment(comment) if comment else ""
                                
                                lease_data = {
                                    'address': ip,
                                    'mac-address': mac,
                                    'disabled': 'no',
                                    'comment': mikrotik_comment
                                }
                                
                                # Добавляем server только если это не 'all'
                                if dhcp_server != 'all':
                                    lease_data['server'] = dhcp_server
                                
                                tuple(dhcp_cmd('add', **lease_data))
                                print(f"✅ DHCP: Новый статический lease создан")
                                
                                # Получаем новый ID
                                leases = list(dhcp_cmd)
                                for l in leases:
                                    if l.get('address') == ip:
                                        lease_id = l.get('.id')
                                        break
                                        
                            except Exception as e3:
                                print(f"❌ DHCP: Ошибка удаления/создания: {e3}")
                                return False
            
                # 2d. Если отключен - включаем
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
        
            # 4. Если lease не найден - создаем новый
            else:
                print(f"➕ DHCP: Создаем новый lease для {ip} -> {mac}")
                print(f"   DHCP сервер: {dhcp_server}")
                try:
                    # Создаем с указанием сервера
                    mikrotik_comment = russian_to_mikrotik_comment(comment) if comment else ""
                    
                    lease_data = {
                        'address': ip,
                        'mac-address': mac,
                        'disabled': 'no',
                        'comment': mikrotik_comment
                    }
                    
                    # Добавляем server только если это не 'all'
                    if dhcp_server != 'all':
                        lease_data['server'] = dhcp_server
                    
                    tuple(dhcp_cmd('add', **lease_data))
                    print(f"✅ DHCP: Новый статический lease создан")
                    
                    # Находим ID созданного lease
                    leases = list(dhcp_cmd)
                    for l in leases:
                        if l.get('address') == ip:
                            lease_id = l.get('.id')
                            print(f"✅ DHCP: Lease ID: {lease_id}")
                            break
        
                except Exception as e:
                    print(f"❌ DHCP: Ошибка создания нового lease: {e}")
                    return False
        
            # 5. Добавляем/обновляем комментарий (если lease_id найден и comment не пустой)
            if lease_id and comment:
                print(f"📝 DHCP: Добавляем/обновляем комментарий: {comment}")
                mikrotik_comment = russian_to_mikrotik_comment(comment)
            
                try:
                    # Пробуем команду comment
                    tuple(dhcp_cmd('comment', **{
                        'numbers': lease_id,
                        'comment': mikrotik_comment
                    }))
                    print(f"✅ DHCP: Комментарий добавлен/обновлен через comment")
                
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
                        # Не считаем это критической ошибкой
        
            # 6. Финальная проверка - убеждаемся, что lease статический
            print(f"🔍 DHCP: Финальная проверка статуса lease...")
            if lease_id:
                leases = list(dhcp_cmd)
                for l in leases:
                    if l.get('address') == ip:
                        final_flags = l.get('flags', '')
                        final_dynamic = l.get('dynamic', '')
                        final_server = l.get('server', 'all')
                        final_comment = l.get('comment', '')
                        
                        print(f"📊 DHCP: Финальный статус:")
                        print(f"  - Флаги: '{final_flags}' (D = динамический)")
                        print(f"  - Dynamic: '{final_dynamic}'")
                        print(f"  - Server: '{final_server}'")
                        print(f"  - Комментарий: '{final_comment}'")
                        
                        # Проверяем, что флаг D исчез
                        if 'D' in final_flags:
                            print(f"⚠️ DHCP: ВНИМАНИЕ! Lease все еще имеет флаг D (динамический)")
                            return False
                        else:
                            print(f"✅ DHCP: Lease успешно сделан статическим (нет флага D)")
                            return True
                        
                print(f"❌ DHCP: Не удалось найти lease после обновления")
                return False
            else:
                print(f"❌ DHCP: Не удалось получить/создать lease для {ip}")
                return False
            
        except Exception as e:
            print(f"❌ DHCP: Критическая ошибка: {e}")
            traceback.print_exc()
            return False

    def _force_make_static_lease(self, ip: str, mac: str, comment: str = "") -> bool:
        """Принудительно сделать lease статическим (альтернативный метод)"""
        try:
            print(
                f"\n🔧 DHCP Форсированный: Принудительно делаем lease статическим для {ip}"
            )

            dhcp_cmd = self.api.path("/ip/dhcp-server/lease")

            # Сначала находим все leases для этого IP
            leases = list(dhcp_cmd)
            lease_ids = []

            for lease in leases:
                if lease.get("address") == ip:
                    lease_id = lease.get(".id")
                    if lease_id:
                        lease_ids.append(lease_id)
                        print(f"🔍 DHCP Форсированный: Найден lease ID: {lease_id}")

            if not lease_ids:
                print(f"➕ DHCP Форсированный: Создаем новый статический lease")
                mikrotik_comment = (
                    russian_to_mikrotik_comment(comment) if comment else ""
                )
                tuple(
                    dhcp_cmd(
                        "add",
                        **{
                            "address": ip,
                            "mac-address": mac,
                            "disabled": "no",
                            "comment": mikrotik_comment,
                        },
                    )
                )
                return True

            # Удаляем все существующие leases для этого IP
            for lease_id in lease_ids:
                print(f"🗑️ DHCP Форсированный: Удаляем lease ID: {lease_id}")
                try:
                    tuple(dhcp_cmd("remove", **{".id": lease_id}))
                except Exception as e:
                    print(f"⚠️ DHCP Форсированный: Ошибка удаления {lease_id}: {e}")

            # Ждем
            import time

            time.sleep(1)

            # Создаем новый статический lease
            print(f"➕ DHCP Форсированный: Создаем новый статический lease")
            mikrotik_comment = russian_to_mikrotik_comment(comment) if comment else ""
            tuple(
                dhcp_cmd(
                    "add",
                    **{
                        "address": ip,
                        "mac-address": mac,
                        "disabled": "no",
                        "comment": mikrotik_comment,
                    },
                )
            )

            # Проверяем результат
            time.sleep(0.5)
            leases = list(dhcp_cmd)
            for lease in leases:
                if lease.get("address") == ip:
                    flags = lease.get("flags", "")
                    if "D" not in flags:
                        print(
                            f"✅ DHCP Форсированный: Успешно создан статический lease"
                        )
                        return True
                    else:
                        print(
                            f"❌ DHCP Форсированный: Lease все еще динамический (флаг D)"
                        )
                        return False

            print(f"❌ DHCP Форсированный: Не удалось создать lease")
            return False

        except Exception as e:
            print(f"❌ DHCP Форсированный: Критическая ошибка: {e}")
            traceback.print_exc()
            return False

    def add_static_arp(
        self, ip: str, mac: str, comment: str = "", interface: Optional[str] = None
    ) -> bool:
        """Добавить статическую ARP запись"""
        try:
            print(f"\n🔧 ARP: Начинаем работу с {ip} -> {mac}")

            # 1. Проверяем принадлежность IP к сетям микротика
            if interface is None:
                belongs, found_interface = self.is_ip_in_mikrotik_networks(ip)
                if not belongs:
                    raise ValueError(
                        f"IP {ip} не принадлежит сетям микротика! ARP запись не может быть добавлена."
                    )
                interface = found_interface

            # Получаем объект пути
            arp_cmd = self.api.path("/ip/arp")

            # 2. Проверяем существующую запись
            print(f"🔍 ARP: Проверяем существующие ARP записи")
            arp_entries = list(arp_cmd)
            for entry in arp_entries:
                if entry.get("address") == ip:
                    print(f"⚠️ ARP: Запись для {ip} уже существует")
                    return True

            # 3. Добавляем новую запись
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
            raise  # Пробрасываем наружу для обработки в UI
        except Exception as e:
            print(f"❌ ARP: Критическая ошибка: {e}")
            traceback.print_exc()
            return False

    def _find_interface_for_ip(self, ip: str) -> str:
        """Найти интерфейс для IP (старая версия - оставлена для совместимости)"""
        try:
            print(f"🔍 Interface: Ищем интерфейс для IP {ip}")

            # Используем новую функцию проверки
            belongs, interface = self.is_ip_in_mikrotik_networks(ip)

            if belongs and interface:
                print(f"✅ Interface: Найден интерфейс '{interface}' для IP {ip}")
                return interface
            else:
                raise ValueError(f"IP {ip} не принадлежит сетям микротика!")

        except ValueError as e:
            print(f"❌ Interface: {e}")
            raise  # Пробрасываем ошибку
        except Exception as e:
            print(f"⚠️ Interface: Ошибка поиска интерфейса: {e}")
            raise ValueError(f"Ошибка поиска интерфейса для IP {ip}: {e}")

    def _ip_in_network(self, ip: str, network_addr: str, prefix: int) -> bool:
        """Проверить принадлежность IP к сети"""
        try:
            network = ipaddress.ip_network(f"{network_addr}/{prefix}", strict=False)
            return ipaddress.ip_address(ip) in network
        except ValueError:
            return False

    def add_to_address_list(
        self, list_name: str, address: str, comment: str = ""
    ) -> bool:
        """Добавить адрес в список"""
        try:
            print(f"\n🔧 Firewall: Добавление {address} в список '{list_name}'")

            # Получаем объект пути
            fw_cmd = self.api.path("/ip/firewall/address-list")

            # 1. Проверяем существующую запись
            print(f"🔍 Firewall: Проверяем существующие записи в списке '{list_name}'")
            addresses = list(fw_cmd)

            for addr in addresses:
                if addr.get("list") == list_name and addr.get("address") == address:
                    print(f"⚠️ Firewall: Адрес {address} уже в списке {list_name}")
                    return True

            # 2. Добавляем новую запись
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

    def get_queues(self) -> List[Dict]:
        """Получить все активные очереди - УПРОЩЕННАЯ ВЕРСИЯ"""
        try:
            print("📡 DEBUG: Получение очередей с MikroTik...")
            queues = list(self.api("/queue/simple/print"))
            print(f"📊 DEBUG: Получено {len(queues)} очередей")

            if not queues:
                print("⚠️ DEBUG: Очереди не найдены!")
                return []

            # Фильтруем отключенные очереди
            active_queues = []

            for queue in queues:
                flags = queue.get("flags", "")
                disabled_value = queue.get("disabled", "")

                # Проверяем disabled
                disabled = False
                if isinstance(disabled_value, bool):
                    disabled = disabled_value
                elif isinstance(disabled_value, str):
                    disabled = disabled_value.lower() == "true"

                # Проверяем флаги
                is_disabled_by_flags = "X" in flags

                if not disabled and not is_disabled_by_flags:
                    active_queues.append(queue)

            print(f"✅ DEBUG: Активных: {len(active_queues)}")

            # ВОЗВРАЩАЕМ БЕЗ СОРТИРОВКИ - пусть queue_builder сортирует
            return active_queues

        except Exception as e:
            print(f"❌ DEBUG: Ошибка получения очередей: {e}")
            traceback.print_exc()
            return []

    def add_ip_to_queue(self, queue_id: str, ip: str) -> bool:
        """Добавить IP в очередь (ВАШ СТИЛЬ)"""
        try:
            print(f"\n🔧 Queue: Добавление IP {ip} в очередь ID: {queue_id}")

            # Получаем объект пути
            queue_cmd = self.api.path("/queue/simple")

            # 1. Получаем текущую очередь
            print(f"🔍 Queue: Получаем данные очереди")
            queues = list(queue_cmd)
            current_target = ""

            for queue in queues:
                if queue.get(".id") == queue_id:
                    current_target = queue.get("target", "")
                    print(
                        f"✅ Queue: Найдена очередь, текущий target: {current_target}"
                    )
                    break

            if not current_target:
                print(f"⚠️ Queue: Очередь не найдена или пустая")
                current_target = ""

            # 2. Формируем новый target
            if "/" in ip:
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
                tuple(queue_cmd("set", **{".id": queue_id, "target": new_target}))
                print(f"✅ Queue: Очередь успешно обновлена")
                return True

            except Exception as e:
                print(f"❌ Queue: Ошибка обновления: {e}")
                # Пробуем альтернативный способ
                try:
                    self.api(
                        "/queue/simple/set", **{".id": queue_id, "target": new_target}
                    )
                    print(f"✅ Queue: Очередь обновлена (альтернативным методом)")
                    return True
                except Exception as e2:
                    print(f"❌ Queue: Ошибка альтернативного метода: {e2}")
                    return False

        except Exception as e:
            print(f"❌ Queue: Критическая ошибка: {e}")
            traceback.print_exc()
            return False
