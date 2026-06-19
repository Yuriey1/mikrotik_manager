"""
Менеджер работы с MikroTik API
"""

from librouteros import connect
import ipaddress
import logging
from typing import Dict, List, Optional, Tuple
import re

from models.device import MikroTikDevice
from config.config_manager import ConfigManager
from utils.helpers import russian_to_mikrotik_comment


DUMMY_IP = "192.168.100.5"

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

            logging.info("🔗 Подключение к %s (%s)...", self.device.name, self.device.ip)

            self.api = connect(
                username=self.device.username,
                password=password,
                host=self.device.ip,
                port=self.device.port,
                encoding="windows-1251",
            )
            self.connected = True
            logging.info("✅ Успешное подключение")
            return True

        except Exception as e:
            logging.error("Ошибка подключения: %s", e, exc_info=True)
            self.connected = False
            return False

    def disconnect(self):
        """Отключиться от устройства"""
        try:
            if self.api:
                logging.info("🔌 Закрываем соединение с %s...", self.device.name)
                self.api.close()
                self.api = None
                self.connected = False
                logging.info("✅ Соединение с %s закрыто", self.device.name)
        except Exception as e:
            logging.warning("⚠️  Ошибка при отключении: %s", e)

    # ========== ПРОВЕРКА IP ==========
    def is_ip_in_mikrotik_networks(self, ip: str) -> Tuple[bool, Optional[str]]:
        """
        Проверить, принадлежит ли IP сетям микротика

        Возвращает:
            (принадлежит, интерфейс) или (False, None) если не принадлежит
        """
        try:
            logging.debug("🔍 Проверка IP %s на принадлежность сетям микротика...", ip)

            # Получаем все адреса интерфейсов
            ipaddr_cmd = self.api.path("/ip/address")
            addresses = list(ipaddr_cmd)

            # Преобразуем IP в объект для проверки
            try:
                ip_obj = ipaddress.ip_address(ip)
            except ValueError:
                logging.error("Неверный формат IP: %s", ip)
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
                        logging.info(
                            "✅ IP %s принадлежит сети %s на интерфейсе '%s'",
                            ip, network, interface
                        )
                        return True, interface

                except (ValueError, KeyError) as e:
                    logging.warning("⚠️  Ошибка обработки адреса %s: %s", addr, e)
                    continue

            logging.error("❌ IP %s НЕ принадлежит ни одной сети микротика!", ip)
            logging.info("   Найдено сетей: %s", len(addresses))
            return False, None

        except Exception as e:
            logging.error("Ошибка проверки IP: %s", e, exc_info=True)
            return False, None

    # ========== DHCP LEASES ==========
    def find_dhcp_lease(self, ip: str, mac: Optional[str] = None) -> Optional[dict]:
        """Найти DHCP lease по IP адресу."""
        try:
            if not self.api:
                return None

            logging.debug("🔍 Поиск DHCP lease для IP: %s", ip)

            # Используем librouteros API - получаем все DHCP аренды
            leases = self.api.path("/ip/dhcp-server/lease")
            all_leases = list(leases)

            logging.debug("📊 Всего DHCP leases: %s", len(all_leases))

            # Проходим по всем записям и ищем match по IP
            for lease in all_leases:
                if lease.get("address") == ip:
                    logging.info(
                        "✅ Найден DHCP lease для %s, MAC: %s", ip, lease.get('mac-address', '')
                    )
                    return lease

            logging.warning("⚠️  DHCP lease для %s не найден среди %s записей", ip, len(all_leases))
            return None

        except Exception as e:
            logging.error("Ошибка поиска DHCP lease для %s: %s", ip, e, exc_info=True)
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
            
            logging.debug("🔍 Поиск DHCP сервера для IP %s", ip)
            logging.debug("   Найдено DHCP серверов: %s", len(servers))
            logging.debug("   Найдено адресов интерфейсов: %s", len(addresses))
            
            # Для каждого DHCP сервера проверяем, входит ли IP в его сеть
            for server in servers:
                server_name = server.get('name', '')
                interface = server.get('interface', '')
                
                logging.debug("   Проверяем сервер '%s' на интерфейсе '%s'", server_name, interface)
                
                # Ищем адрес интерфейса, к которому привязан DHCP сервер
                for addr in addresses:
                    if addr.get('interface') == interface:
                        network_str = addr.get('address', '')  # Формат: 192.168.1.1/24
                        try:
                            network = ipaddress.ip_network(network_str, strict=False)
                            if ip_obj in network:
                                logging.info("   ✅ IP %s принадлежит сети %s сервера '%s'", ip, network, server_name)
                                return server_name
                        except ValueError as e:
                            logging.warning("   ⚠️ Ошибка парсинга сети %s: %s", network_str, e)
                            continue
            
            logging.error("   ❌ Не найден DHCP сервер для IP %s", ip)
            return None
            
        except Exception as e:
            logging.error("Ошибка поиска DHCP сервера: %s", e, exc_info=True)
            return None

    def create_static_lease(self, ip: str, mac: str, comment: str = "") -> bool:
        """Создать/обновить статический DHCP lease"""
        try:
            logging.info("🔧 DHCP: Работа с %s -> %s", ip, mac)
        
            # Получаем объект пути
            dhcp_cmd = self.api.path('/ip/dhcp-server/lease')
        
            # 1. Определяем правильный DHCP сервер для этого IP
            logging.debug("🔍 DHCP: Определяем правильный DHCP сервер для %s...", ip)
            dhcp_server = self._find_dhcp_server_for_ip(ip)
            
            if not dhcp_server:
                logging.warning("⚠️ DHCP: Не найден подходящий DHCP сервер, используем 'all'")
                dhcp_server = 'all'
            else:
                logging.info("✅ DHCP: Найден DHCP сервер: %s", dhcp_server)
        
            # 2. Ищем существующий lease
            logging.debug("🔍 DHCP: Ищем существующий lease для %s", ip)
            leases = list(dhcp_cmd)
            lease = None
            lease_id = None
        
            for l in leases:
                if l.get('address') == ip:
                    lease = l
                    lease_id = l.get('.id')
                    logging.info("✅ DHCP: Найден существующий lease ID: %s", lease_id)
                    break
        
            # 3. Проверяем статус найденного lease
            if lease:
                flags = lease.get('flags', '')
                logging.debug("📊 DHCP: Поле 'flags': '%s'", flags)
                
                # Проверяем наличие флага D (DYNAMIC)
                is_dynamic = 'D' in flags
                
                # Также проверяем поле dynamic для совместимости
                dynamic_field = lease.get('dynamic', '')
                logging.debug("📊 DHCP: Поле 'dynamic': '%s'", dynamic_field)
                
                if isinstance(dynamic_field, bool):
                    is_dynamic = is_dynamic or dynamic_field
                elif isinstance(dynamic_field, str):
                    is_dynamic = is_dynamic or dynamic_field.lower() == 'true'
                
                is_disabled = lease.get('disabled') == 'true'
                current_mac = lease.get('mac-address', '')
                current_server = lease.get('server', 'all')
            
                logging.debug("📊 DHCP: Статус lease:")
                logging.debug("  - Динамический: %s", is_dynamic)
                logging.debug("  - Отключен: %s", is_disabled)
                logging.debug("  - MAC: %s", current_mac)
                logging.debug("  - Server: %s", current_server)
            
                # Проверяем MAC адрес
                if current_mac and current_mac.lower() != mac.lower():
                    logging.warning("⚠️ DHCP: MAC отличается! Обновляем...")
                    try:
                        tuple(dhcp_cmd('set', **{'.id': lease_id, 'mac-address': mac}))
                        logging.info("✅ DHCP: MAC обновлен")
                    except Exception as e:
                        logging.error("DHCP: Ошибка обновления MAC: %s", e)
            
                # Обновляем поле server если нужно
                if current_server != dhcp_server:
                    logging.info("🔄 DHCP: Обновляем поле server")
                    try:
                        tuple(dhcp_cmd('set', **{'.id': lease_id, 'server': dhcp_server}))
                        logging.info("✅ DHCP: Поле server обновлено")
                    except Exception as e:
                        logging.warning("⚠️ DHCP: Ошибка обновления server: %s", e)
            
                # Если lease динамический - делаем статическим
                if is_dynamic:
                    logging.info("🔄 DHCP: Делаем lease статическим...")
                    
                    try:
                        result = tuple(dhcp_cmd('make-static', **{'.id': lease_id}))
                        logging.info("✅ DHCP: Lease помечен как статический")
                        
                        # После make-static ID может измениться
                        leases = list(dhcp_cmd)
                        for l in leases:
                            if l.get('address') == ip:
                                new_lease_id = l.get('.id')
                                if new_lease_id:
                                    lease_id = new_lease_id
                                break
                                
                    except Exception as e:
                        logging.warning("⚠️ DHCP: Ошибка make-static: %s", e)
                        logging.info("  Пробуем set dynamic=no...")
                        
                        try:
                            tuple(dhcp_cmd('set', **{'.id': lease_id, 'dynamic': 'no'}))
                            logging.info("✅ DHCP: Lease помечен как статический")
                            
                        except Exception as e2:
                            logging.warning("⚠️ DHCP: Ошибка set dynamic=no: %s", e2)
                            logging.info("  Удаляем и создаем заново...")
                            
                            try:
                                tuple(dhcp_cmd('remove', **{'.id': lease_id}))
                                logging.info("✅ DHCP: Динамический lease удален")
                                
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
                                logging.info("✅ DHCP: Новый статический lease создан")
                                
                                leases = list(dhcp_cmd)
                                for l in leases:
                                    if l.get('address') == ip:
                                        lease_id = l.get('.id')
                                        break
                                        
                            except Exception as e3:
                                logging.error("DHCP: Ошибка удаления/создания: %s", e3)
                                return False
            
                # Если отключен - включаем
                if is_disabled:
                    logging.info("🔄 DHCP: Включаем lease")
                    try:
                        tuple(dhcp_cmd('set', **{'.id': lease_id, 'disabled': 'no'}))
                        logging.info("✅ DHCP: Lease включен")
                    except Exception as e:
                        logging.warning("⚠️ DHCP: Ошибка включения: %s", e)
        
            # 4. Если lease не найден - создаем новый
            else:
                logging.info("➕ DHCP: Создаем новый lease для %s -> %s", ip, mac)
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
                    logging.info("✅ DHCP: Новый статический lease создан")
                    
                    leases = list(dhcp_cmd)
                    for l in leases:
                        if l.get('address') == ip:
                            lease_id = l.get('.id')
                            break
        
                except Exception as e:
                    logging.error("DHCP: Ошибка создания lease: %s", e)
                    return False
        
            # 5. Добавляем/обновляем комментарий
            if lease_id and comment:
                logging.debug("📝 DHCP: Добавляем комментарий: %s", comment)
                mikrotik_comment = russian_to_mikrotik_comment(comment)

                try:
                    tuple(dhcp_cmd('comment', **{'numbers': lease_id, 'comment': mikrotik_comment}))
                    logging.info("✅ DHCP: Комментарий добавлен")
                except Exception as e:
                    logging.warning("⚠️ DHCP: Ошибка comment, пробуем set: %s", e)
                    try:
                        tuple(dhcp_cmd('set', **{'.id': lease_id, 'comment': mikrotik_comment}))
                        logging.info("✅ DHCP: Комментарий добавлен через set")
                    except Exception as e2:
                        logging.warning("⚠️ DHCP: Ошибка добавления комментария: %s", e2)

            # 5b. Авто-заполнение ClientID при наличии MAC
            if lease_id and mac:
                client_id = "1:" + mac.lower()
                logging.debug("📝 DHCP: Установка ClientID: %s", client_id)
                try:
                    tuple(dhcp_cmd('set', **{'.id': lease_id, 'client-id': client_id}))
                    logging.info("✅ DHCP: ClientID установлен")
                except Exception as e:
                    logging.warning("⚠️ DHCP: ошибка установки ClientID: %s", e)
        
            # 6. Финальная проверка
            logging.debug("🔍 DHCP: Финальная проверка...")
            if lease_id:
                leases = list(dhcp_cmd)
                for l in leases:
                    if l.get('address') == ip:
                        final_flags = l.get('flags', '')
                        
                        if 'D' in final_flags:
                            logging.warning("⚠️ DHCP: Lease все еще динамический!")
                            return False
                        else:
                            logging.info("✅ DHCP: Lease успешно статический")
                            return True
                        
                logging.error("DHCP: Не удалось найти lease после обновления")
                return False
            else:
                logging.error("DHCP: Не удалось получить/создать lease")
                return False
            
        except Exception as e:
            logging.error("DHCP: Критическая ошибка: %s", e, exc_info=True)
            return False

    # ========== ПРОВЕРКА MAC ==========
    def check_mac_exists(self, mac: str, exclude_ip: Optional[str] = None) -> Dict:
        """Проверить, существует ли MAC в DHCP лизах или ARP таблице"""
        try:
            mac_lower = mac.lower()
            result = {'exists': False, 'lease_ip': None, 'arp_ip': None}

            # Проверяем DHCP leases
            leases = self.get_dhcp_leases()
            for lease in leases:
                lease_mac = (lease.get('mac-address') or '').lower()
                lease_ip = lease.get('address', '')
                if lease_mac == mac_lower:
                    if exclude_ip and lease_ip == exclude_ip:
                        continue
                    result['exists'] = True
                    result['lease_ip'] = lease_ip
                    break

            # Проверяем ARP таблицу
            arp_entries = self.get_arp_table()
            for entry in arp_entries:
                arp_mac = (entry.get('mac-address') or '').lower()
                arp_ip = entry.get('address', '')
                if arp_mac == mac_lower:
                    if exclude_ip and arp_ip == exclude_ip:
                        continue
                    result['exists'] = True
                    result['arp_ip'] = arp_ip
                    break

            return result

        except Exception as e:
            logging.error("Ошибка проверки MAC %s: %s", mac, e, exc_info=True)
            return {'exists': False, 'lease_ip': None, 'arp_ip': None, 'error': str(e)}

    # ========== ARP ==========
    def add_static_arp(
        self, ip: str, mac: str, comment: str = "", interface: Optional[str] = None
    ) -> bool:
        """Добавить статическую ARP запись"""
        try:
            logging.info("🔧 ARP: Начинаем работу с %s -> %s", ip, mac)

            if interface is None:
                belongs, found_interface = self.is_ip_in_mikrotik_networks(ip)
                if not belongs:
                    raise ValueError(
                        f"IP {ip} не принадлежит сетям микротика! ARP запись не может быть добавлена."
                    )
                interface = found_interface

            arp_cmd = self.api.path("/ip/arp")

            # Проверяем существующую запись
            logging.debug("🔍 ARP: Проверяем существующие записи")
            arp_entries = list(arp_cmd)
            for entry in arp_entries:
                if entry.get("address") == ip:
                    logging.warning("⚠️ ARP: Запись для %s уже существует", ip)
                    return True

            # Добавляем новую запись
            logging.info("➕ ARP: Добавляем новую запись")
            logging.info("   📍 Интерфейс: %s", interface)
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
                logging.info("✅ ARP: Запись успешно добавлена")
                return True

            except Exception as e:
                logging.error("ARP: Ошибка добавления: %s", e)
                return False

        except ValueError as e:
            logging.error("ARP: %s", e)
            raise
        except Exception as e:
            logging.error("ARP: Критическая ошибка: %s", e, exc_info=True)
            return False

    # ========== FIREWALL ==========
    def add_to_address_list(
        self, list_name: str, address: str, comment: str = ""
    ) -> bool:
        """Добавить адрес в список"""
        try:
            logging.info("🔧 Firewall: Добавление %s в список '%s'", address, list_name)

            fw_cmd = self.api.path("/ip/firewall/address-list")

            # Проверяем существующую запись
            logging.debug("🔍 Firewall: Проверяем существующие записи")
            addresses = list(fw_cmd)

            for addr in addresses:
                if addr.get("list") == list_name and addr.get("address") == address:
                    logging.warning("⚠️ Firewall: Адрес %s уже в списке %s", address, list_name)
                    return True

            # Добавляем новую запись
            logging.info("➕ Firewall: Добавляем %s в список %s", address, list_name)
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
                logging.info("✅ Firewall: Адрес успешно добавлен")
                return True

            except Exception as e:
                logging.error("Firewall: Ошибка добавления: %s", e)
                return False

        except Exception as e:
            logging.error("Firewall: Критическая ошибка: %s", e, exc_info=True)
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
            
            logging.info("📋 Найдено %s IP с доступом в интернет", len(internet_ips))
            return internet_ips
            
        except Exception as e:
            logging.error("Ошибка получения internet_access: %s", e, exc_info=True)
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
            logging.error("Ошибка проверки доступа: %s", e)
            return False

    def add_internet_access(self, ip: str, comment: str = "") -> bool:
        """Добавить IP в список internet_access"""
        return self.add_to_address_list("internet_access", ip, comment)

    def remove_internet_access(self, ip: str) -> bool:
        """Удалить IP из списка internet_access"""
        try:
            logging.info("🔧 Удаление %s из internet_access...", ip)
            
            fw_cmd = self.api.path("/ip/firewall/address-list")
            addresses = list(fw_cmd)
            
            for addr in addresses:
                if addr.get("list") == "internet_access" and addr.get("address") == ip:
                    addr_id = addr.get(".id")
                    if addr_id:
                        tuple(fw_cmd("remove", **{".id": addr_id}))
                        logging.info("✅ IP %s удалён из internet_access", ip)
                        return True
            
            logging.warning("⚠️ IP %s не найден в internet_access", ip)
            return True  # Не ошибка, если уже нет в списке
            
        except Exception as e:
            logging.error("Ошибка удаления из internet_access: %s", e, exc_info=True)
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

    def remove_from_all_address_lists(self, ip: str) -> List[Dict]:
        """Удалить IP из всех firewall address-list'ов"""
        results = []
        try:
            logging.info("🔧 Firewall: удаление %s из всех address-list'ов", ip)
            fw_cmd = self.api.path("/ip/firewall/address-list")
            addresses = list(fw_cmd)

            ip_stripped = ip.split("/")[0]
            for addr in addresses:
                addr_ip = (addr.get("address") or "").split("/")[0]
                if addr_ip == ip_stripped:
                    addr_id = addr.get(".id")
                    list_name = addr.get("list", "?")
                    if addr_id:
                        try:
                            tuple(fw_cmd("remove", **{".id": addr_id}))
                            logging.info("   ✅ Удалён из списка '%s'", list_name)
                            results.append({
                                'list_name': list_name,
                                'success': True
                            })
                        except Exception as e:
                            logging.error("   ❌ Ошибка удаления из '%s': %s", list_name, e)
                            results.append({
                                'list_name': list_name,
                                'success': False,
                                'error': str(e)
                            })

            if not results:
                logging.warning("   ⚠️ IP %s не найден ни в одном address-list'е", ip)
            return results

        except Exception as e:
            logging.error("Ошибка удаления из address-list'ов: %s", e, exc_info=True)
            return results

    # ========== QUEUES ==========
    def get_queues(self) -> List[Dict]:
        """Получить все активные очереди"""
        try:
            logging.debug("📡 Получение очередей с MikroTik...")
            queues = list(self.api("/queue/simple/print"))
            logging.debug("📊 Получено %s очередей", len(queues))

            if not queues:
                logging.warning("⚠️ Очереди не найдены!")
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

            logging.info("✅ Активных: %s", len(active_queues))
            return active_queues

        except Exception as e:
            logging.error("Ошибка получения очередей: %s", e, exc_info=True)
            return []

    def _get_queue_targets(self, queue_id: str) -> List[str]:
        """Получить список target'ов очереди"""
        queue_cmd = self.api.path("/queue/simple")
        queues = list(queue_cmd)
        for queue in queues:
            if queue.get(".id") == queue_id:
                target_str = queue.get("target", "")
                if not target_str or not target_str.strip():
                    return []
                return [t.strip() for t in target_str.split(",") if t.strip()]
        return []

    def _set_queue_targets(self, queue_id: str, targets: List[str]) -> bool:
        """Записать список target'ов в очередь"""
        queue_cmd = self.api.path("/queue/simple")
        new_target = ",".join(targets)
        try:
            tuple(queue_cmd("set", **{".id": queue_id, "target": new_target}))
            return True
        except Exception as e:
            logging.error("Queue: ошибка set: %s", e)
            try:
                self.api("/queue/simple/set", **{".id": queue_id, "target": new_target})
                return True
            except Exception as e2:
                logging.error("Queue: ошибка alt set: %s", e2)
                return False

    def add_ip_to_queue(self, queue_id: str, ip: str) -> bool:
        """Добавить IP в очередь. Если в target уже есть интерфейс — не добавлять IP"""
        try:
            logging.info("🔧 Queue: Добавление IP %s в очередь ID: %s", ip, queue_id)

            targets = self._get_queue_targets(queue_id)
            logging.debug("   Текущие target'ы: %s", targets)

            # Если в target уже есть интерфейс (не IP-адрес) — не трогаем
            import re
            ip_pattern = re.compile(r'^\d+\.\d+\.\d+\.\d+')
            for t in targets:
                if t and not ip_pattern.match(t.strip()):
                    logging.info("   ℹ️  В target уже есть интерфейс '%s', IP добавлять не нужно", t)
                    return True

            if "/" in ip:
                ip_with_mask = ip
            else:
                ip_with_mask = f"{ip}/32"

            # Убираем dummy-IP если он есть
            if DUMMY_IP in targets:
                targets.remove(DUMMY_IP)
                logging.info("   🧹 Убран dummy-IP %s", DUMMY_IP)

            # Добавляем настоящий IP если его ещё нет
            if ip_with_mask not in targets:
                targets.append(ip_with_mask)
                logging.info("   ➕ Добавлен %s", ip_with_mask)
            else:
                logging.warning("   ⚠️ %s уже в target", ip_with_mask)

            if self._set_queue_targets(queue_id, targets):
                logging.info("✅ Queue: очередь обновлена")
                return True
            return False

        except Exception as e:
            logging.error("Queue: Критическая ошибка: %s", e, exc_info=True)
            return False

    def remove_ip_from_queue(self, queue_id: str, ip: str) -> bool:
        """Убрать IP из очереди. Если очередь опустеет — вставить DUMMY_IP"""
        try:
            logging.info("🔧 Queue: Удаление IP %s из очереди ID: %s", ip, queue_id)

            targets = self._get_queue_targets(queue_id)
            logging.debug("   Текущие target'ы: %s", targets)

            if "/" in ip:
                ip_with_mask = ip
            else:
                ip_with_mask = f"{ip}/32"

            if ip_with_mask in targets:
                targets.remove(ip_with_mask)
                logging.info("   ➖ Убран %s", ip_with_mask)
            else:
                logging.warning("   ⚠️ %s не найден в target", ip_with_mask)

            # Если опустела — вставляем dummy
            if not targets:
                targets.append(DUMMY_IP)
                logging.info("   🧹 Очередь опустела, добавлен dummy-IP %s", DUMMY_IP)

            if self._set_queue_targets(queue_id, targets):
                logging.info("✅ Queue: очередь обновлена")
                return True
            return False

        except Exception as e:
            logging.error("Queue: ошибка удаления IP из очереди: %s", e, exc_info=True)
            return False

    def remove_ip_from_all_queues(self, ip: str) -> List[Dict]:
        """Убрать IP из всех очередей, где он присутствует"""
        results = []
        try:
            queues = self.get_queues()
            for queue in queues:
                target_str = queue.get("target", "")
                ip_with_mask = f"{ip}/32"
                # Проверяем: IP/32 или просто IP в списке target
                targets = [t.strip() for t in target_str.split(",") if t.strip()]
                if ip_with_mask in targets or ip in targets:
                    queue_id = queue.get(".id")
                    queue_name = queue.get("name", queue_id)
                    logging.debug("🔍 Найден IP %s в очереди '%s'", ip, queue_name)
                    success = self.remove_ip_from_queue(queue_id, ip)
                    results.append({
                        'queue_name': queue_name,
                        'queue_id': queue_id,
                        'success': success
                    })
            return results
        except Exception as e:
            logging.error("Ошибка удаления IP из всех очередей: %s", e, exc_info=True)
            return results

    # ========== DHCP POOLS ==========
    def get_dhcp_pools(self) -> List[Dict]:
        """Получить DHCP пулы"""
        try:
            pools_cmd = self.api.path('/ip/pool')
            pools = list(pools_cmd)
            return pools
        except Exception as e:
            logging.error("Ошибка получения DHCP пулов: %s", e)
            return []

    def get_dhcp_leases(self) -> List[Dict]:
        """Получить все DHCP leases"""
        try:
            leases_cmd = self.api.path('/ip/dhcp-server/lease')
            leases = list(leases_cmd)
            return leases
        except Exception as e:
            logging.error("Ошибка получения DHCP leases: %s", e)
            return []

    def get_free_dhcp_ips(self, max_per_pool: int = 20) -> Dict[str, List[str]]:
        """Получить свободные IP адреса из DHCP пулов"""
        try:
            logging.debug("🔍 Поиск свободных IP адресов в DHCP пулах...")
            
            # Получаем все пулы
            pools = self.get_dhcp_pools()
            logging.debug("📊 Найдено пулов DHCP: %s", len(pools))
            
            # Получаем все leases
            leases = self.get_dhcp_leases()
            used_ips = {lease.get('address') for lease in leases if lease.get('address')}
            logging.debug("📊 Используется IP адресов: %s", len(used_ips))
            
            # Анализируем каждый пул
            free_ips_by_pool = {}
            
            for pool in pools:
                pool_name = pool.get('name', 'unknown')
                ranges = pool.get('ranges', '')
                
                if not ranges:
                    continue
                
                logging.debug("🔍 Анализ пула '%s': %s", pool_name, ranges)
                
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
                
                logging.debug("   📊 Свободно: %s/%s", len(free_ips), len(pool_ips))
            
            return free_ips_by_pool
            
        except Exception as e:
            logging.error("Ошибка поиска свободных IP: %s", e, exc_info=True)
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
                logging.warning("⚠️ Ошибка парсинга диапазона %s: %s", ip_range, e)
                return []
        elif '/' in ip_range:
            # Формат: 192.168.1.0/24
            try:
                network = ipaddress.IPv4Network(ip_range, strict=False)
                return [str(ip) for ip in network.hosts()]
            except ipaddress.AddressValueError as e:
                logging.warning("⚠️ Ошибка парсинга сети %s: %s", ip_range, e)
                return []
        else:
            # Одиночный IP
            try:
                ipaddress.IPv4Address(ip_range)
                return [ip_range]
            except ipaddress.AddressValueError as e:
                logging.warning("⚠️ Ошибка парсинга IP %s: %s", ip_range, e)
                return []

    # ========== MAC REPLACEMENT FUNCTIONALITY ==========
    
    def get_arp_table(self) -> List[Dict]:
        """Получить ARP таблицу"""
        try:
            arp_cmd = self.api.path('/ip/arp')
            arp_list = list(arp_cmd)
            return arp_list
        except Exception as e:
            logging.error("Ошибка получения ARP таблицы: %s", e)
            return []

    def delete_dhcp_lease(self, ip: str) -> bool:
        """Удалить DHCP lease по IP адресу"""
        try:
            # Находим lease по IP
            lease = self.find_dhcp_lease(ip=ip)
            if not lease:
                logging.warning("⚠️ DHCP lease для IP %s не найден", ip)
                return False
            
            lease_id = lease.get('.id')
            if not lease_id:
                logging.error("Не удалось получить ID lease для IP %s", ip)
                return False
            
            # Удаляем lease
            dhcp_cmd = self.api.path('/ip/dhcp-server/lease')
            tuple(dhcp_cmd('remove', **{'.id': lease_id}))
            logging.info("✅ DHCP lease для IP %s удален", ip)
            return True
            
        except Exception as e:
            logging.error("Ошибка удаления DHCP lease: %s", e, exc_info=True)
            return False

    def update_dhcp_lease(self, old_ip: str, new_mac: str, comment: str = "") -> bool:
        """Обновить DHCP lease - найти по старому IP, установить новый MAC"""
        try:
            # Находим lease по старому IP
            lease = self.find_dhcp_lease(ip=old_ip)
            if not lease:
                logging.warning("⚠️ DHCP lease для IP %s не найден", old_ip)
                return False
            
            lease_id = lease.get('.id')
            if not lease_id:
                logging.error("Не удалось получить ID lease для IP %s", old_ip)
                return False
            
            # Обновляем MAC и комментарий
            dhcp_cmd = self.api.path('/ip/dhcp-server/lease')
            update_data = {'.id': lease_id, 'mac-address': new_mac.lower()}
            if comment:
                update_data['comment'] = comment
            
            tuple(dhcp_cmd('set', **update_data))
            logging.info("✅ DHCP lease обновлен: IP=%s, MAC=%s", old_ip, new_mac)
            return True
            
        except Exception as e:
            logging.error("Ошибка обновления DHCP lease: %s", e, exc_info=True)
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
                logging.warning("⚠️ ARP запись для IP %s не найдена", ip)
                return False
            
            # Обновляем MAC
            tuple(arp_cmd('set', **{'.id': arp_id, 'mac-address': new_mac.lower()}))
            logging.info("✅ ARP запись обновлена: IP=%s, MAC=%s", ip, new_mac)
            return True
            
        except Exception as e:
            logging.error("Ошибка обновления ARP записи: %s", e, exc_info=True)
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
            logging.info("✅ ARP запись добавлена: IP=%s, MAC=%s", ip, mac)
            return True
            
        except Exception as e:
            logging.error("Ошибка добавления ARP записи: %s", e, exc_info=True)
            return False

    def delete_arp_entry(self, ip: str) -> bool:
        """Удалить ARP запись по IP"""
        try:
            logging.info("🔧 ARP: удаление записи для %s", ip)
            arp_cmd = self.api.path('/ip/arp')
            entries = list(arp_cmd)

            for entry in entries:
                if entry.get('address') == ip:
                    arp_id = entry.get('.id')
                    if arp_id:
                        tuple(arp_cmd('remove', **{'.id': arp_id}))
                        logging.info("✅ ARP запись для %s удалена", ip)
                        return True

            logging.warning("⚠️ ARP запись для %s не найдена", ip)
            return True

        except Exception as e:
            logging.error("Ошибка удаления ARP записи: %s", e, exc_info=True)
            return False

    def get_dhcp_subscribers(self, pool_name: str = None, include_all: bool = False) -> List[Dict]:
        """
        Получить список абонентов из DHCP leases
        Абоненты - это leases с непустыми комментариями (ФИО, должность)
        
        Args:
            pool_name: Имя DHCP пула для фильтрации (если None - все абоненты)
            include_all: Если True — вернуть все лизинги, включая без комментариев
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
                # Абонент - это lease с комментарием (там ФИО/должность)
                # При include_all=True включаем все лизинги
                if not include_all and not (comment and comment.strip()):
                    continue
                
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
                logging.info("✅ Найдено абонентов в пуле '%s': %s", pool_name, len(subscribers))
            else:
                logging.info("✅ Найдено абонентов: %s", len(subscribers))
            return subscribers
            
        except Exception as e:
            logging.error("Ошибка получения абонентов: %s", e, exc_info=True)
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
            
            logging.info("✅ Замена MAC завершена: %s → MAC %s", old_ip, new_mac)
            return result
            
        except Exception as e:
            result['error'] = f"Ошибка при замене MAC: {str(e)}"
            result['steps'].append(f"❌ Ошибка: {str(e)}")
            logging.error("Ошибка замены MAC: %s", e, exc_info=True)
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
            
            logging.info("✅ Ручная замена MAC завершена: %s → %s", ip, new_mac)
            return result
            
        except Exception as e:
            result['error'] = f"Ошибка при замене MAC: {str(e)}"
            result['steps'].append(f"❌ Ошибка: {str(e)}")
            logging.error("Ошибка ручной замены MAC: %s", e, exc_info=True)
            return result

    # ========== ОБНОВЛЕНИЕ АБОНЕНТА ==========
    def update_subscriber(self, old_ip: str, data: Dict) -> Dict:
        """Обновить данные абонента: comment, IP, MAC, очереди, интернет"""
        result = {
            'success': False,
            'steps': [],
            'error': None,
            'details': {'dhcp': False, 'arp': False, 'queues': [], 'firewall': False}
        }

        try:
            new_ip = data.get('ip', old_ip)
            new_mac = data.get('mac', '').strip()
            comment = data.get('comment', '')
            queues = data.get('queues', [])
            internet_access = data.get('internet_access', False)

            # --- DHCP: обновление комментария ---
            result['steps'].append("📝 DHCP: обновление комментария...")
            if comment:
                lease = self.find_dhcp_lease(ip=old_ip)
                if lease:
                    lease_id = lease.get('.id')
                    if lease_id:
                        try:
                            dhcp_cmd = self.api.path('/ip/dhcp-server/lease')
                            mikrotik_comment = russian_to_mikrotik_comment(comment)
                            tuple(dhcp_cmd('set', **{'.id': lease_id, 'comment': mikrotik_comment}))
                            result['steps'].append("   ✅ Комментарий обновлён")
                            result['details']['dhcp'] = True
                        except Exception as e:
                            result['steps'].append(f"   ⚠️ Ошибка обновления комментария: {e}")
                else:
                    result['steps'].append("   ⚠️ DHCP lease не найден")
            else:
                result['details']['dhcp'] = True

            # --- DHCP: обновление IP если изменился ---
            if new_ip != old_ip:
                result['steps'].append(f"📝 DHCP: смена IP {old_ip} → {new_ip}")
                lease = self.find_dhcp_lease(ip=old_ip)
                if lease:
                    lease_id = lease.get('.id')
                    if lease_id:
                        try:
                            dhcp_cmd = self.api.path('/ip/dhcp-server/lease')
                            tuple(dhcp_cmd('set', **{'.id': lease_id, 'address': new_ip}))
                            result['steps'].append("   ✅ IP обновлён")
                            result['details']['dhcp'] = True
                            # После смены IP обновляем old_ip для остальных операций
                            old_ip_for_rest = new_ip
                        except Exception as e:
                            result['steps'].append(f"   ❌ Ошибка смены IP: {e}")
                    else:
                        result['steps'].append("   ⚠️ Не найден ID lease")
                else:
                    result['steps'].append("   ⚠️ DHCP lease не найден для старого IP")
                    old_ip_for_rest = new_ip
            else:
                old_ip_for_rest = old_ip

            # --- DHCP: обновление MAC если изменился ---
            if new_mac:
                lease = self.find_dhcp_lease(ip=old_ip_for_rest)
                if lease:
                    current_mac = (lease.get('mac-address') or '').lower()
                    if current_mac != new_mac.lower():
                        result['steps'].append(f"📝 DHCP: обновление MAC {current_mac} → {new_mac}")
                        lease_id = lease.get('.id')
                        if lease_id:
                            try:
                                dhcp_cmd = self.api.path('/ip/dhcp-server/lease')
                                tuple(dhcp_cmd('set', **{'.id': lease_id, 'mac-address': new_mac}))
                                result['steps'].append("   ✅ MAC обновлён в DHCP")
                                # Авто-заполнение ClientID
                                try:
                                    client_id = "1:" + new_mac.lower()
                                    tuple(dhcp_cmd('set', **{'.id': lease_id, 'client-id': client_id}))
                                except Exception:
                                    pass
                                result['details']['dhcp'] = True
                            except Exception as e:
                                result['steps'].append(f"   ⚠️ Ошибка обновления MAC в DHCP: {e}")

            # --- ARP: обновление MAC ---
            if new_mac:
                result['steps'].append("📝 ARP: обновление...")
                arp_entries = self.get_arp_table()
                arp_id = None
                for entry in arp_entries:
                    if entry.get('address') == old_ip_for_rest:
                        arp_id = entry.get('.id')
                        break

                if arp_id:
                    try:
                        arp_cmd = self.api.path('/ip/arp')
                        tuple(arp_cmd('set', **{'.id': arp_id, 'mac-address': new_mac}))
                        result['steps'].append("   ✅ ARP обновлён")
                        result['details']['arp'] = True
                    except Exception as e:
                        result['steps'].append(f"   ⚠️ Ошибка обновления ARP: {e}")
                else:
                    # Нет ARP записи — пробуем добавить
                    try:
                        self.add_arp_entry(old_ip_for_rest, new_mac, comment=comment)
                        result['steps'].append("   ✅ ARP запись добавлена")
                        result['details']['arp'] = True
                    except Exception as e:
                        result['steps'].append(f"   ⚠️ Ошибка добавления ARP: {e}")
            else:
                result['details']['arp'] = True

            # --- Очереди: удалить из старых, добавить в новые ---
            if 'queues' in data:
                result['steps'].append("📝 Очереди: обновление...")
                # Удаляем IP из всех очередей где он есть
                self.remove_ip_from_all_queues(old_ip_for_rest)

                # Получаем все очереди для поиска по имени
                all_queues = self.get_queues()

                # Добавляем в указанные очереди
                for queue_name in queues:
                    queue_id = None
                    for q in all_queues:
                        if q.get('name') == queue_name:
                            queue_id = q.get('.id')
                            break

                    if queue_id:
                        success = self.add_ip_to_queue(queue_id, old_ip_for_rest)
                        result['details']['queues'].append({
                            'name': queue_name,
                            'success': success
                        })
                        if success:
                            result['steps'].append(f"   ✅ Добавлен в '{queue_name}'")
                        else:
                            result['steps'].append(f"   ❌ Ошибка добавления в '{queue_name}'")
                    else:
                        result['steps'].append(f"   ⚠️ Очередь '{queue_name}' не найдена")
                        result['details']['queues'].append({
                            'name': queue_name,
                            'success': False,
                            'error': 'Очередь не найдена'
                        })

            # --- Firewall: интернет доступ ---
            if internet_access:
                result['steps'].append("📝 Firewall: включение интернета...")
                fw_result = self.add_internet_access(old_ip_for_rest, comment)
                result['details']['firewall'] = fw_result
                result['steps'].append("   ✅ Доступ включён" if fw_result else "   ❌ Ошибка")
            else:
                result['steps'].append("📝 Firewall: отключение интернета...")
                fw_result = self.remove_internet_access(old_ip_for_rest)
                result['details']['firewall'] = fw_result
                result['steps'].append("   ✅ Доступ отключён" if fw_result else "   ⚠️ Ошибка")

            result['success'] = True
            result['message'] = f"Абонент {old_ip} обновлён"
            logging.info("✅ Обновление абонента завершено")

        except Exception as e:
            result['error'] = str(e)
            result['steps'].append(f"❌ Ошибка: {str(e)}")
            logging.error("Ошибка обновления абонента: %s", e, exc_info=True)

        return result

    # ========== АНАЛИЗ КАНАЛОВ ==========
    def get_interfaces(self) -> List[Dict]:
        """Получить список всех интерфейсов"""
        try:
            if not self.api:
                return []
            interfaces = list(self.api.path('/interface'))
            return [{'name': i.get('name', ''), 'type': i.get('type', ''), 'running': i.get('running', False), 'disabled': i.get('disabled', False)} for i in interfaces]
        except Exception as e:
            logging.error("Ошибка получения интерфейсов: %s", e)
            return []

    def get_ip_addresses(self) -> List[Dict]:
        """Получить все IP адреса интерфейсов"""
        try:
            if not self.api:
                return []
            addresses = list(self.api.path('/ip/address'))
            return [{'address': addr.get('address', ''), 'interface': addr.get('interface', ''), 'network': addr.get('network', '')} for addr in addresses]
        except Exception as e:
            logging.error("Ошибка получения IP адресов: %s", e)
            return []

    def get_routes(self) -> List[Dict]:
        """Получить таблицу маршрутизации"""
        try:
            if not self.api:
                return []
            routes = list(self.api.path('/ip/route'))
            return [{'dst_address': r.get('dst-address', ''), 'gateway': r.get('gateway', ''), 'interface': r.get('interface', ''), 'distance': int(r.get('distance', 255)), 'active': r.get('active', False)} for r in routes]
        except Exception as e:
            logging.error("Ошибка получения маршрутов: %s", e)
            return []

    def analyze_channels(self) -> Dict:
        """Анализ конфигурации каналов"""
        try:
            result = {'success': True, 'channels': [], 'primary_channel': None, 'backup_channel': None, 'interfaces': []}
            interfaces = self.get_interfaces()
            result['interfaces'] = interfaces
            ip_addresses = self.get_ip_addresses()
            routes = self.get_routes()
            default_routes = [r for r in routes if r['dst_address'] in ['0.0.0.0/0', '::/0']]
            if not default_routes:
                result['success'] = False
                result['error'] = 'Маршруты по умолчанию не найдены'
                return result
            default_routes.sort(key=lambda x: x['distance'])
            channels = []
            for idx, route in enumerate(default_routes):
                channel = {'name': route['interface'] or route['gateway'], 'interface': route['interface'], 'gateway': route['gateway'], 'distance': route['distance'], 'active': route['active'], 'type': 'primary' if idx == 0 else 'backup', 'ip_address': ''}
                for addr in ip_addresses:
                    if addr['interface'] == route['interface']:
                        channel['ip_address'] = addr['address']
                        break
                channels.append(channel)
            result['channels'] = channels
            result['primary_channel'] = channels[0] if channels else None
            result['backup_channel'] = channels[1] if len(channels) > 1 else None
            return result
        except Exception as e:
            logging.error("Ошибка анализа каналов: %s", e, exc_info=True)
            return {'success': False, 'error': str(e)}
