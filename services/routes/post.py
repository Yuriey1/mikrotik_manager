"""
POST-обработчики маршрутов
"""

import json
import logging
import re
import ipaddress
import time

from config.config_manager import ConfigManager
from netbox_client import NetBoxClient
from utils.helpers import russian_to_mikrotik_comment

import services.state as state


# ── Helpers ───────────────────────────────────────────────────

def _init_netbox():
    if state.netbox_client is not None:
        return
    try:
        cfg = ConfigManager.load_netbox_config()
        if cfg.get('url') and cfg.get('token'):
            state.netbox_client = NetBoxClient(cfg['url'], cfg['token'], cfg.get('verify_ssl', True))
    except Exception:
        pass


# ══════════════════════════════════════════════════════════════
#  POST /api/netbox/save_config
# ══════════════════════════════════════════════════════════════

def handle_save_netbox(handler, data):
    try:
        cfg = {
            'url': data.get('url', '').strip(),
            'token': data.get('token', '').strip(),
            'verify_ssl': data.get('verify_ssl', True),
        }
        if not cfg['url'] or not cfg['token']:
            handler._send_json({'success': False, 'error': 'Заполните URL и токен'})
            return
        ConfigManager.save_netbox_config(cfg)
        state.netbox_client = None
        _init_netbox()
        handler._send_json({'success': True, 'message': 'Настройки NetBox сохранены'})
    except Exception as e:
        handler._send_json({'error': str(e)}, 500)


# ══════════════════════════════════════════════════════════════
#  POST /api/add_device
# ══════════════════════════════════════════════════════════════

def handle_add_device(handler, data):
    try:
        name = data.get('name', '').strip()
        ip = data.get('ip', '').strip()
        username = data.get('username', 'admin').strip()
        password = data.get('password', '').strip()
        description = data.get('description', '').strip()
        save_password = data.get('savePassword', False)

        if not name or not ip:
            handler._send_json({'error': 'Заполните имя и IP'}, 400)
            return

        encrypted = ''
        if password and save_password:
            encrypted = 'enc:' + ConfigManager.encrypt_password(password)

        devices = ConfigManager.load_devices()
        devices[name] = {
            'name': name, 'ip': ip, 'port': data.get('port', 8728),
            'username': username, 'password': encrypted, 'description': description,
        }
        ConfigManager.save_devices(devices)
        handler._send_json({'success': True, 'message': f'Устройство {name} добавлено'})
    except Exception as e:
        handler._send_json({'error': str(e)}, 500)


# ══════════════════════════════════════════════════════════════
#  POST /api/add_employee
# ══════════════════════════════════════════════════════════════

def handle_add_employee(handler, data):
    if not state.mikrotik_manager or not state.mikrotik_manager.connected:
        handler._send_json({'error': 'Не подключено к устройству'}, 400)
        return

    try:
        full_name = data.get('full_name', '').strip()
        position = data.get('position', '').strip()
        ip = data.get('ip', '').strip()
        mac = data.get('mac', '').strip()
        internet_access = bool(data.get('internet_access', False))
        internet_timeout = data.get('internet_timeout', '').strip()

        queues = data.get('queues', [])
        if isinstance(queues, str):
            queues = [queues] if queues.strip() else []

        if not full_name or not position or not ip:
            handler._send_json({'error': 'Заполните обязательные поля'}, 400)
            return

        try:
            ipaddress.ip_address(ip)
        except ValueError:
            handler._send_json({'error': 'Неверный формат IP'}, 400)
            return

        if not mac:
            try:
                lease = state.mikrotik_manager.find_dhcp_lease(ip=ip)
                if lease:
                    mac = lease.get('mac-address') or lease.get('mac_address') or lease.get('mac.address', '')
            except Exception:
                pass

        if mac:
            mac = mac.upper().replace('-', ':').replace('.', ':')
            mac_pattern = re.compile(r'^([0-9A-F]{2}[:-]){5}([0-9A-F]{2})$', re.IGNORECASE)
            if not mac_pattern.match(mac):
                handler._send_json({'error': 'Неверный формат MAC'}, 400)
                return
            mac_check = state.mikrotik_manager.check_mac_exists(mac, exclude_ip=ip)
            if mac_check['exists']:
                conflict_ip = mac_check.get('lease_ip') or mac_check.get('arp_ip')
                handler._send_json({
                    'success': False, 'error': f'MAC {mac} уже используется! Занят на IP {conflict_ip}',
                    'mac_conflict': True, 'conflict_ip': conflict_ip,
                }, 409)
                return

        comment = f"{position} - {full_name}"

        results = {'dhcp': False, 'arp': False, 'queues': [], 'firewall': False}

        # 1. DHCP
        if mac:
            results['dhcp'] = state.mikrotik_manager.create_static_lease(ip, mac, comment)
        else:
            lease = state.mikrotik_manager.find_dhcp_lease(ip=ip)
            if lease:
                lease_id = lease.get('.id')
                if lease_id:
                    is_dynamic = lease.get('dynamic') == 'true'
                    dhcp_cmd = state.mikrotik_manager.api.path('/ip/dhcp-server/lease')
                    if is_dynamic:
                        try:
                            tuple(dhcp_cmd('make-static', **{'.id': lease_id}))
                        except Exception:
                            try:
                                tuple(dhcp_cmd('set', **{'.id': lease_id, 'dynamic': 'no'}))
                            except Exception:
                                pass
                    mikrotik_comment = russian_to_mikrotik_comment(comment)
                    try:
                        tuple(dhcp_cmd('comment', **{'numbers': lease_id, 'comment': mikrotik_comment}))
                    except Exception:
                        try:
                            tuple(dhcp_cmd('set', **{'.id': lease_id, 'comment': mikrotik_comment}))
                        except Exception:
                            pass
                    results['dhcp'] = True
            else:
                results['dhcp'] = True

        # 2. ARP
        if mac:
            results['arp'] = state.mikrotik_manager.add_static_arp(ip, mac, comment)
        else:
            results['arp'] = True

        # 3. Queues
        queue_results = []
        if 'queues' in data:
            for queue_name in queues:
                queue_id = None
                for node in state.tree_builder.nodes.values():
                    if node.name == queue_name:
                        queue_id = node.id
                        break
                if queue_id:
                    success = state.mikrotik_manager.add_ip_to_queue(queue_id, ip)
                    queue_results.append({'name': queue_name, 'success': success, 'id': queue_id})
                else:
                    queue_results.append({'name': queue_name, 'success': False, 'error': 'Очередь не найдена'})
            results['queues'] = queue_results
        else:
            results['queues'] = []

        if state.tree_builder and state.mikrotik_manager.connected:
            try:
                state.tree_builder.build_tree()
            except Exception:
                pass

        # 4. Firewall
        if internet_access:
            results['firewall'] = state.mikrotik_manager.add_to_address_list('internet_access', f"{ip}/32", comment, internet_timeout)
        else:
            results['firewall'] = True

        overall_success = results['dhcp'] and results['arp'] and results['firewall']
        if queues:
            queue_success = any(q.get('success', False) for q in results['queues'])
            overall_success = overall_success and queue_success

        if overall_success:
            if queues:
                ok = [q['name'] for q in results['queues'] if q.get('success')]
                message = f'Сотрудник {full_name} успешно добавлен в {len(ok)} очередь(ей)' if ok else f'Сотрудник {full_name} добавлен, но в очереди добавить не удалось'
            else:
                message = f'Сотрудник {full_name} успешно добавлен (без ограничений очередей)'
        else:
            message = f'Ошибка добавления сотрудника {full_name}'

        response = {
            'success': overall_success, 'message': message,
            'details': {'dhcp': results['dhcp'], 'arp': results['arp'], 'firewall': results['firewall'], 'queues': results['queues']},
            'results': results,
        }
        handler._send_json(response)
    except Exception as e:
        logging.error("Ошибка добавления сотрудника: %s", e, exc_info=True)
        handler._send_json({'error': f'Внутренняя ошибка сервера: {str(e)}'}, 500)


# ══════════════════════════════════════════════════════════════
#  POST /api/replace_mac
# ══════════════════════════════════════════════════════════════

def handle_replace_mac(handler, data):
    if not state.mikrotik_manager or not state.mikrotik_manager.connected:
        handler._send_json({'error': 'Не подключено к устройству'}, 400)
        return

    mode = data.get('mode', 'by-ip')
    try:
        if mode == 'by-ip':
            old_ip = data.get('old_ip', '').strip()
            new_ip = data.get('new_ip', '').strip()
            if not old_ip or not new_ip:
                handler._send_json({'error': 'Укажите старый и новый IP адреса'}, 400)
                return
            try:
                ipaddress.ip_address(old_ip)
                ipaddress.ip_address(new_ip)
            except ValueError as e:
                handler._send_json({'error': f'Неверный формат IP: {e}'}, 400)
                return
            result = state.mikrotik_manager.replace_mac_address(old_ip, new_ip)
        elif mode == 'by-mac':
            ip = data.get('ip', '').strip()
            new_mac = data.get('new_mac', '').strip()
            client_id = data.get('client_id', '').strip() or None
            if not ip or not new_mac:
                handler._send_json({'error': 'Укажите IP и новый MAC адрес'}, 400)
                return
            try:
                ipaddress.ip_address(ip)
            except ValueError as e:
                handler._send_json({'error': f'Неверный формат IP: {e}'}, 400)
                return
            mac_re = re.compile(r'^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$')
            if not mac_re.match(new_mac):
                handler._send_json({'error': 'Неверный формат MAC. Используйте AA:BB:CC:DD:EE:FF'}, 400)
                return
            result = state.mikrotik_manager.replace_mac_manual(ip, new_mac, client_id)
        else:
            handler._send_json({'error': f'Неизвестный режим: {mode}'}, 400)
            return

        if result['success']:
            handler._send_json({'success': True, 'message': result.get('message', 'MAC успешно заменен'), 'steps': result.get('steps', [])})
        else:
            handler._send_json({'success': False, 'error': result.get('error', 'Неизвестная ошибка'), 'steps': result.get('steps', [])})
    except Exception as e:
        logging.error("Ошибка замены MAC: %s", e, exc_info=True)
        handler._send_json({'error': str(e)}, 500)


# ══════════════════════════════════════════════════════════════
#  POST /api/internet_access/toggle
# ══════════════════════════════════════════════════════════════

def handle_toggle_internet(handler, data):
    if not state.mikrotik_manager or not state.mikrotik_manager.connected:
        handler._send_json({'error': 'Не подключено к устройству'}, 400)
        return

    ip = data.get('ip', '').strip()
    enable = data.get('enable', False)
    comment = data.get('comment', '').strip()
    timeout = data.get('timeout', '').strip()

    if not ip:
        handler._send_json({'error': 'Не указан IP адрес'}, 400)
        return

    try:
        ipaddress.ip_address(ip)
        result = state.mikrotik_manager.toggle_internet_access(ip, enable, comment, timeout)
        if result['success']:
            handler._send_json({'success': True, 'message': result.get('message', 'Статус изменён'), 'ip': ip, 'enabled': enable})
        else:
            handler._send_json({'success': False, 'error': result.get('error', 'Неизвестная ошибка')})
    except ValueError as e:
        handler._send_json({'error': f'Неверный формат IP: {e}'}, 400)
    except Exception as e:
        logging.error("Ошибка переключения интернета: %s", e, exc_info=True)
        handler._send_json({'error': str(e)}, 500)


# ══════════════════════════════════════════════════════════════
#  POST /api/delete_subscriber
# ══════════════════════════════════════════════════════════════

def handle_delete_subscriber(handler, data):
    if not state.mikrotik_manager or not state.mikrotik_manager.connected:
        handler._send_json({'error': 'Не подключено к устройству'}, 400)
        return

    ip = data.get('ip', '').strip()
    if not ip:
        handler._send_json({'error': 'Не указан IP адрес'}, 400)
        return

    steps = []
    details = {'dhcp': False, 'arp': False, 'queues': [], 'firewall': []}

    try:
        dhcp_ok = state.mikrotik_manager.delete_dhcp_lease(ip)
        details['dhcp'] = dhcp_ok
        steps.append(f"{'✅' if dhcp_ok else '⚠️'} DHCP: {'удалён' if dhcp_ok else 'не найден'}")

        arp_ok = state.mikrotik_manager.delete_arp_entry(ip)
        details['arp'] = arp_ok
        steps.append(f"{'✅' if arp_ok else '⚠️'} ARP: {'удалён' if arp_ok else 'не найден'}")

        qr = state.mikrotik_manager.remove_ip_from_all_queues(ip)
        details['queues'] = qr
        if qr:
            for q in qr:
                icon = '✅' if q.get('success') else '❌'
                steps.append(f"{icon} Очередь '{q['queue_name']}': {'убран' if q.get('success') else 'ошибка'}")
        else:
            steps.append("ℹ️ Очереди: IP не найден в очередях")

        fw = state.mikrotik_manager.remove_from_all_address_lists(ip)
        details['firewall'] = fw
        if fw:
            for fr in fw:
                icon = '✅' if fr.get('success') else '❌'
                steps.append(f"{icon} Address-list '{fr['list_name']}': {'убран' if fr.get('success') else 'ошибка'}")
        else:
            steps.append("ℹ️ Firewall: IP не найден в address-list'ах")

        if state.tree_builder and state.mikrotik_manager.connected:
            try:
                state.tree_builder.build_tree()
            except Exception:
                pass

        handler._send_json({'success': True, 'ip': ip, 'message': f'Абонент {ip} полностью удалён', 'steps': steps, 'details': details})
    except Exception as e:
        logging.error("Ошибка удаления абонента: %s", e, exc_info=True)
        handler._send_json({'success': False, 'error': str(e), 'steps': steps}, 500)


# ══════════════════════════════════════════════════════════════
#  POST /api/edit_subscriber
# ══════════════════════════════════════════════════════════════

def handle_edit_subscriber(handler, data):
    if not state.mikrotik_manager or not state.mikrotik_manager.connected:
        handler._send_json({'error': 'Не подключено к устройству'}, 400)
        return

    old_ip = data.get('old_ip', '').strip()
    if not old_ip:
        handler._send_json({'error': 'Не указан IP абонента'}, 400)
        return

    try:
        result = state.mikrotik_manager.update_subscriber(old_ip, data)

        if state.tree_builder and state.mikrotik_manager.connected:
            try:
                state.tree_builder.build_tree()
            except Exception:
                pass

        if result['success']:
            handler._send_json({'success': True, 'message': result.get('message', f'Абонент {old_ip} обновлён'), 'steps': result.get('steps', []), 'details': result.get('details', {})})
        else:
            handler._send_json({'success': False, 'error': result.get('error', 'Ошибка обновления'), 'steps': result.get('steps', [])})
    except Exception as e:
        logging.error("Ошибка редактирования абонента: %s", e, exc_info=True)
        handler._send_json({'success': False, 'error': str(e)}, 500)


# ══════════════════════════════════════════════════════════════
#  POST /api/move_ip
# ══════════════════════════════════════════════════════════════

def handle_move_ip(handler, data):
    if not state.mikrotik_manager or not state.mikrotik_manager.connected:
        handler._send_json({'error': 'Не подключено к устройству'}, 400)
        return

    ip = data.get('ip', '').strip()
    from_queue_id = data.get('from_queue_id', '').strip()
    to_queue_id = data.get('to_queue_id', '').strip()

    if not ip or not from_queue_id or not to_queue_id:
        handler._send_json({'error': 'Укажите ip, from_queue_id, to_queue_id'}, 400)
        return

    try:
        result = state.mikrotik_manager.move_ip_between_queues(from_queue_id, to_queue_id, ip)

        if state.tree_builder and state.mikrotik_manager.connected:
            try:
                state.tree_builder.build_tree()
            except Exception:
                pass

        if result['success']:
            handler._send_json({'success': True, 'message': f'IP {ip} перемещён'})
        else:
            handler._send_json({'success': False, 'error': result.get('error', 'Ошибка перемещения')})
    except Exception as e:
        logging.error("Ошибка перемещения IP: %s", e, exc_info=True)
        handler._send_json({'success': False, 'error': str(e)}, 500)


# ══════════════════════════════════════════════════════════════
#  POST /api/reset_queue_traffic
# ══════════════════════════════════════════════════════════════

def handle_reset_queue_traffic(handler, data):
    if not state.mikrotik_manager or not state.mikrotik_manager.connected:
        handler._send_json({'error': 'Не подключено к устройству'}, 400)
        return

    queue_id = data.get('queue_id', '').strip()
    new_value = data.get('new_value', 0)

    if not queue_id:
        handler._send_json({'error': 'Укажите queue_id'}, 400)
        return

    try:
        result = state.mikrotik_manager.reset_queue_traffic(queue_id, int(new_value))

        if state.tree_builder and state.mikrotik_manager.connected:
            try:
                state.tree_builder.build_tree()
            except Exception:
                pass

        if result['success']:
            handler._send_json({
                'success': True,
                'message': 'Счётчик трафика сброшен',
                'previous': result.get('previous'),
                'new_comment': result.get('new_comment')
            })
        else:
            handler._send_json({'success': False, 'error': result.get('error', 'Ошибка сброса трафика')})
    except Exception as e:
        logging.error("Ошибка сброса трафика: %s", e, exc_info=True)
        handler._send_json({'success': False, 'error': str(e)}, 500)


# ══════════════════════════════════════════════════════════════
#  POST /api/save_credentials
# ══════════════════════════════════════════════════════════════

def handle_save_credentials(handler, data):
    device = data.get('device', '').strip()
    username = data.get('username', '').strip()
    password = data.get('password', '')

    if not device:
        handler._send_json({'error': 'Не указано устройство'}, 400)
        return

    try:
        from config.config_manager import ConfigManager
        ConfigManager.save_credentials(device, username, password)
        handler._send_json({'success': True, 'message': f'Учётные данные для {device} сохранены'})
    except Exception as e:
        logging.error("Ошибка сохранения учётных данных: %s", e, exc_info=True)
        handler._send_json({'success': False, 'error': str(e)}, 500)
