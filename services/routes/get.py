"""
GET-обработчики маршрутов
"""

import json
import logging
import os
import re
import ipaddress
from urllib.parse import parse_qs

from config.config_manager import ConfigManager
from models.device import MikroTikDevice
from managers.mikrotik_manager import MikroTikManager
from services.queue_builder import QueueTreeBuilder
from netbox_client import NetBoxClient

import services.state as state


# ── NetBox utils ──────────────────────────────────────────────

def _init_netbox():
    if state.netbox_client is not None:
        return
    try:
        cfg = ConfigManager.load_netbox_config()
        if cfg.get('url') and cfg.get('token'):
            state.netbox_client = NetBoxClient(cfg['url'], cfg['token'], cfg.get('verify_ssl', True))
    except Exception:
        pass


# ── Device helpers ────────────────────────────────────────────

def _disconnect_current(ctx):
    try:
        if ctx.mikrotik_manager:
            ctx.mikrotik_manager.disconnect()
            ctx.mikrotik_manager = None
        ctx.tree_builder = None
        ctx.current_device_name = None
    except Exception:
        pass


# ══════════════════════════════════════════════════════════════
#  GET /api/devices
# ══════════════════════════════════════════════════════════════

def handle_devices(handler, parsed):
    ctx = handler.session_ctx
    _init_netbox()
    if not state.netbox_client:
        handler._send_json({'devices': {}, 'netbox_configured': False, 'error': 'NetBox не настроен'})
        return
    try:
        devices_list = state.netbox_client.get_devices()
        devices_dict = {}
        for d in devices_list:
            devices_dict[d.name] = {
                'name': d.name, 'ip': d.ip_address, 'port': d.port,
                'username': 'admin', 'password': '',
                'description': f"{d.device_type} - {d.site} - {d.role}",
                'device_type': d.device_type, 'site': d.site,
                'role': d.role, 'comments': d.comments,
            }
        handler._send_json({'devices': devices_dict, 'netbox_configured': True, 'count': len(devices_dict)})
    except Exception as e:
        handler._send_json({'devices': {}, 'netbox_configured': False, 'error': str(e)})


# ══════════════════════════════════════════════════════════════
#  GET /api/connect
# ══════════════════════════════════════════════════════════════

def handle_connect(handler, parsed):
    ctx = handler.session_ctx
    qs = parse_qs(parsed.query)
    device_name = qs.get('device', [''])[0]
    username = qs.get('username', [''])[0]
    password = qs.get('password', [''])[0]

    if not device_name:
        handler._send_json({'error': 'Не указано устройство'}, 400)
        return

    _init_netbox()
    if not state.netbox_client:
        handler._send_json({'error': 'NetBox не настроен'}, 400)
        return

    try:
        nb_devices = state.netbox_client.get_devices()
        target = None
        for d in nb_devices:
            if d.name == device_name:
                target = d
                break
        if not target:
            handler._send_json({'error': f'Устройство "{device_name}" не найдено в NetBox'}, 404)
            return

        saved = ConfigManager.get_credentials(device_name)
        default_user = ConfigManager.get_default_username()
        final_user = username or saved['username'] or default_user
        final_pass = password or saved['password']

        if not final_pass:
            handler._send_json({
                'success': False, 'requires_credentials': True,
                'device': device_name,
                'saved_username': saved['username'] or default_user,
                'message': 'Требуется ввод учетных данных',
            }, 401)
            return

        if ctx.mikrotik_manager and ctx.mikrotik_manager.connected and ctx.current_device_name:
            _disconnect_current(ctx)

        dev = MikroTikDevice.from_dict({
            'name': target.name, 'ip': target.ip_address, 'port': target.port,
            'username': final_user, 'password': final_pass,
            'description': f"{target.device_type} - {target.site}",
        })
        ctx.mikrotik_manager = MikroTikManager(dev)

        if ctx.mikrotik_manager.connect():
            if final_user or final_pass:
                ConfigManager.save_credentials(device_name, final_user, final_pass)
            ctx.current_device_name = device_name
            ctx.tree_builder = QueueTreeBuilder(ctx.mikrotik_manager)
            ctx.tree_builder.build_tree()
            handler._send_json({
                'success': True, 'device': device_name,
                'message': f"Подключено к {dev.ip}:{dev.port}",
                'action': 'connected', 'username': final_user,
            })
        else:
            ctx.current_device_name = None
            handler._send_json({'success': False, 'error': 'Не удалось подключиться к устройству'})
    except Exception as e:
        handler._send_json({'error': str(e)}, 500)


# ══════════════════════════════════════════════════════════════
#  GET /api/disconnect
# ══════════════════════════════════════════════════════════════

def handle_disconnect(handler, parsed):
    ctx = handler.session_ctx
    if not ctx.current_device_name:
        handler._send_json({'success': True, 'message': 'Нет активных подключений', 'action': 'already_disconnected'})
        return
    name = ctx.current_device_name
    _disconnect_current()
    handler._send_json({'success': True, 'message': f'Отключено от {name}', 'action': 'disconnected'})


# ══════════════════════════════════════════════════════════════
#  GET /api/tree
# ══════════════════════════════════════════════════════════════

def handle_tree(handler, parsed):
    ctx = handler.session_ctx
    if not ctx.tree_builder or not ctx.mikrotik_manager or not ctx.mikrotik_manager.connected:
        handler._send_json({'error': 'Не подключено к устройству'}, 400)
        return
    handler._send_json({
        'success': True,
        'tree': ctx.tree_builder.get_tree_json(),
        'stats': ctx.tree_builder.get_stats(),
    })


# ══════════════════════════════════════════════════════════════
#  GET /api/stats
# ══════════════════════════════════════════════════════════════

def handle_stats(handler, parsed):
    ctx = handler.session_ctx
    if not ctx.tree_builder or not ctx.mikrotik_manager or not ctx.mikrotik_manager.connected:
        handler._send_json({'error': 'Не подключено к устройству'}, 400)
        return
    handler._send_json(ctx.tree_builder.get_stats())


# ══════════════════════════════════════════════════════════════
#  GET /api/sync
# ══════════════════════════════════════════════════════════════

def handle_sync(handler, parsed):
    ctx = handler.session_ctx
    if not ctx.mikrotik_manager or not ctx.mikrotik_manager.connected:
        handler._send_json({'error': 'Не подключено к устройству'}, 400)
        return
    try:
        resp = {'success': True}
        if ctx.tree_builder:
            resp['queue_tree'] = ctx.tree_builder.get_tree_json()
            resp['queue_stats'] = ctx.tree_builder.get_stats()
            resp['all_queues'] = [n.to_dict() for n in ctx.tree_builder.nodes.values()]
        else:
            resp['queue_tree'] = []; resp['queue_stats'] = {}; resp['all_queues'] = []

        resp['dhcp_pools'] = []
        try:
            pools = ctx.mikrotik_manager.get_dhcp_pools()
            resp['dhcp_pools'] = [{'name': p.get('name',''), 'ranges': p.get('ranges',''), 'id': p.get('.id','')} for p in pools]
        except Exception as e:
            logging.warning("⚠️ sync dhcp_pools: %s", e)

        resp['subscribers'] = []
        try:
            resp['subscribers'] = ctx.mikrotik_manager.get_dhcp_subscribers(include_all=True)
        except Exception as e:
            logging.warning("⚠️ sync subscribers: %s", e)

        resp['internet_access'] = []
        resp['internet_timeouts'] = {}
        try:
            entries = ctx.mikrotik_manager.get_internet_access_list()
            resp['internet_access'] = [e['ip'] for e in entries]
            resp['internet_timeouts'] = {e['ip']: e['timeout'] for e in entries}
        except Exception as e:
            logging.warning("⚠️ sync internet_access: %s", e)

        resp['channels'] = None
        try:
            resp['channels'] = ctx.mikrotik_manager.analyze_channels()
        except Exception as e:
            logging.warning("⚠️ sync channels: %s", e)

        resp['interfaces'] = []
        try:
            resp['interfaces'] = ctx.mikrotik_manager.get_interfaces()
        except Exception as e:
            logging.warning("⚠️ sync interfaces: %s", e)

        handler._send_json(resp)
    except Exception as e:
        logging.error("Ошибка синхронизации: %s", e, exc_info=True)
        handler._send_json({'success': False, 'error': str(e)}, 500)


# ══════════════════════════════════════════════════════════════
#  GET /api/find_queues
# ══════════════════════════════════════════════════════════════

def handle_find_queues(handler, parsed):
    ctx = handler.session_ctx
    if not ctx.tree_builder:
        handler._send_json({'success': False, 'error': 'Не подключено к устройству'}, 400)
        return
    qs = parse_qs(parsed.query)
    ip = qs.get('ip', [''])[0].strip()
    if not ip:
        try:
            nodes = list(ctx.tree_builder.nodes.values())
            handler._send_json({'success': True, 'queues': [n.to_dict() for n in nodes], 'count': len(nodes)})
        except Exception as e:
            handler._send_json({'success': False, 'error': str(e)})
        return
    try:
        if '/' in ip:
            ipaddress.ip_network(ip, strict=False)
        else:
            ipaddress.ip_address(ip)
    except ValueError:
        handler._send_json({'success': False, 'error': 'Неверный формат IP'}, 400)
        return
    try:
        existing = []
        for node in ctx.tree_builder.nodes.values():
            if node.has_ip(ip):
                existing.append(node.name)
        suitable = ctx.tree_builder.find_suitable_queues_for_ip(ip)
        handler._send_json({
            'success': True, 'ip': ip,
            'existing': existing,
            'queues': [n.to_dict() for n in suitable],
            'count': len(suitable),
        })
    except Exception as e:
        handler._send_json({'success': False, 'error': str(e)})


# ══════════════════════════════════════════════════════════════
#  GET /api/check_ip
# ══════════════════════════════════════════════════════════════

def handle_check_ip(handler, parsed):
    ctx = handler.session_ctx
    if not ctx.mikrotik_manager or not ctx.mikrotik_manager.connected:
        handler._send_json({'success': False, 'error': 'Не подключено к устройству'}, 400)
        return
    qs = parse_qs(parsed.query)
    ip = qs.get('ip', [''])[0].strip()
    if not ip:
        handler._send_json({'success': False, 'error': 'Не указан IP адрес'}, 400)
        return
    try:
        ipaddress.ip_address(ip)
    except ValueError as e:
        handler._send_json({'success': False, 'error': f'Неверный формат IP: {e}'}, 400)
        return
    try:
        belongs, iface = ctx.mikrotik_manager.is_ip_in_mikrotik_networks(ip)
        if belongs:
            handler._send_json({'success': True, 'message': f'IP {ip} принадлежит сетям микротика', 'interface': iface})
        else:
            handler._send_json({'success': False, 'error': f'IP {ip} не принадлежит сетям микротика'})
    except Exception as e:
        handler._send_json({'success': False, 'error': str(e)}, 500)


# ══════════════════════════════════════════════════════════════
#  GET /api/netbox/config
# ══════════════════════════════════════════════════════════════

def handle_netbox_config(handler, parsed):
    ctx = handler.session_ctx
    try:
        cfg = ConfigManager.load_netbox_config()
        handler._send_json({'success': True, 'config': cfg})
    except Exception as e:
        handler._send_json({'error': str(e)}, 500)


# ══════════════════════════════════════════════════════════════
#  GET /api/netbox/test
# ══════════════════════════════════════════════════════════════

def handle_netbox_test(handler, parsed):
    ctx = handler.session_ctx
    try:
        qs = parse_qs(parsed.query)
        url = qs.get('url', [''])[0]
        token = qs.get('token', [''])[0]
        verify_ssl = qs.get('verify_ssl', ['true'])[0].lower() == 'true'
        if not url or not token:
            handler._send_json({'success': False, 'error': 'Укажите URL и токен NetBox'})
            return
        tc = NetBoxClient(url, token, verify_ssl)
        if tc.test_connection():
            handler._send_json({'success': True, 'message': 'Соединение с NetBox успешно установлено'})
        else:
            handler._send_json({'success': False, 'error': 'Не удалось подключиться к NetBox'})
    except Exception as e:
        handler._send_json({'error': str(e)}, 500)


# ══════════════════════════════════════════════════════════════
#  GET /api/find_dhcp_lease
# ══════════════════════════════════════════════════════════════

def handle_find_dhcp_lease(handler, parsed):
    ctx = handler.session_ctx
    if not ctx.mikrotik_manager or not ctx.mikrotik_manager.connected:
        handler._send_json({'success': False, 'error': 'Не подключено к устройству'}, 400)
        return
    try:
        qs = parse_qs(parsed.query)
        ip = qs.get('ip', [''])[0]
        if not ip:
            handler._send_json({'success': False, 'error': 'Не указан IP адрес'}, 400)
            return
        lease = ctx.mikrotik_manager.find_dhcp_lease(ip=ip)
        if lease:
            mac = None
            for key in ['mac-address', 'mac_address', 'mac.address', 'mac']:
                if key in lease:
                    mac = lease[key]
                    break
            handler._send_json({'success': True, 'found': True, 'lease': lease, 'mac_address': mac})
        else:
            handler._send_json({'success': True, 'found': False, 'message': 'DHCP lease не найден'})
    except Exception as e:
        logging.error("Ошибка поиска DHCP lease: %s", e, exc_info=True)
        handler._send_json({'success': False, 'error': str(e)}, 500)


# ══════════════════════════════════════════════════════════════
#  GET /api/free_ips
# ══════════════════════════════════════════════════════════════

def handle_free_ips(handler, parsed):
    ctx = handler.session_ctx
    if not ctx.mikrotik_manager or not ctx.mikrotik_manager.connected:
        handler._send_json({'error': 'Не подключено к устройству'}, 400)
        return
    try:
        free = ctx.mikrotik_manager.get_free_dhcp_ips()
        handler._send_json({'success': True, 'free_ips': free, 'count': len(free)})
    except Exception as e:
        logging.error("Ошибка получения свободных IP: %s", e, exc_info=True)
        handler._send_json({'error': str(e)}, 500)


# ══════════════════════════════════════════════════════════════
#  GET /api/dhcp_pools
# ══════════════════════════════════════════════════════════════

def handle_dhcp_pools(handler, parsed):
    ctx = handler.session_ctx
    if not ctx.mikrotik_manager or not ctx.mikrotik_manager.connected:
        handler._send_json({'error': 'Не подключено к устройству'}, 400)
        return
    try:
        pools = ctx.mikrotik_manager.get_dhcp_pools()
        pools_list = [{'name': p.get('name',''), 'ranges': p.get('ranges',''), 'id': p.get('.id','')} for p in pools]
        handler._send_json({'success': True, 'pools': pools_list, 'count': len(pools_list)})
    except Exception as e:
        handler._send_json({'error': str(e)}, 500)


# ══════════════════════════════════════════════════════════════
#  GET /api/dhcp_subscribers
# ══════════════════════════════════════════════════════════════

def handle_dhcp_subscribers(handler, parsed):
    ctx = handler.session_ctx
    if not ctx.mikrotik_manager or not ctx.mikrotik_manager.connected:
        handler._send_json({'error': 'Не подключено к устройству'}, 400)
        return
    try:
        qs = parse_qs(parsed.query)
        pool_name = qs.get('pool', [''])[0] or None
        include_all = qs.get('all', [''])[0].lower() == 'true'
        subs = ctx.mikrotik_manager.get_dhcp_subscribers(pool_name=pool_name, include_all=include_all)
        handler._send_json({'success': True, 'subscribers': subs, 'count': len(subs)})
    except Exception as e:
        logging.error("Ошибка получения абонентов: %s", e, exc_info=True)
        handler._send_json({'error': str(e)}, 500)


# ══════════════════════════════════════════════════════════════
#  GET /api/internet_access
# ══════════════════════════════════════════════════════════════

def handle_internet_access(handler, parsed):
    ctx = handler.session_ctx
    if not ctx.mikrotik_manager or not ctx.mikrotik_manager.connected:
        handler._send_json({'error': 'Не подключено к устройству'}, 400)
        return
    try:
        entries = ctx.mikrotik_manager.get_internet_access_list()
        ips = [e['ip'] for e in entries]
        timeouts = {e['ip']: e['timeout'] for e in entries}
        handler._send_json({'success': True, 'ips': ips, 'entries': entries, 'timeouts': timeouts, 'count': len(ips)})
    except Exception as e:
        logging.error("Ошибка получения internet_access: %s", e, exc_info=True)
        handler._send_json({'error': str(e)}, 500)


# ══════════════════════════════════════════════════════════════
#  GET /api/analyze_channels
# ══════════════════════════════════════════════════════════════

def handle_analyze_channels(handler, parsed):
    ctx = handler.session_ctx
    if not ctx.mikrotik_manager or not ctx.mikrotik_manager.connected:
        handler._send_json({'success': False, 'error': 'Не подключено к устройству'}, 400)
        return
    try:
        result = ctx.mikrotik_manager.analyze_channels()
        handler._send_json(result)
    except Exception as e:
        logging.error("Ошибка анализа каналов: %s", e, exc_info=True)
        handler._send_json({'success': False, 'error': str(e)}, 500)


# ══════════════════════════════════════════════════════════════
#  GET /api/check_mac
# ══════════════════════════════════════════════════════════════

def handle_check_mac(handler, parsed):
    ctx = handler.session_ctx
    if not ctx.mikrotik_manager or not ctx.mikrotik_manager.connected:
        handler._send_json({'success': False, 'error': 'Не подключено к устройству'}, 400)
        return
    qs = parse_qs(parsed.query)
    mac = qs.get('mac', [''])[0].strip()
    exclude_ip = qs.get('exclude_ip', [''])[0].strip() or None
    if not mac:
        handler._send_json({'success': False, 'error': 'Не указан MAC адрес'}, 400)
        return
    try:
        result = ctx.mikrotik_manager.check_mac_exists(mac, exclude_ip)
        handler._send_json({
            'success': True, 'exists': result['exists'],
            'lease_ip': result.get('lease_ip'), 'arp_ip': result.get('arp_ip'),
            'message': f"MAC уже используется на IP {result['lease_ip']}" if result['exists'] else 'MAC свободен',
        })
    except Exception as e:
        logging.error("Ошибка проверки MAC: %s", e, exc_info=True)
        handler._send_json({'success': False, 'error': str(e)}, 500)


# ══════════════════════════════════════════════════════════════
#  GET /api/old_leases
# ══════════════════════════════════════════════════════════════

def handle_old_leases(handler, parsed):
    ctx = handler.session_ctx
    if not ctx.mikrotik_manager or not ctx.mikrotik_manager.connected:
        handler._send_json({'error': 'Не подключено к устройству'}, 400)
        return
    qs = parse_qs(parsed.query)
    include_never = qs.get('include_never', ['false'])[0].lower() == 'true'
    if include_never:
        age = 0
    else:
        try:
            age = int(qs.get('age', ['30'])[0])
        except (ValueError, TypeError):
            age = 30
    try:
        old = ctx.mikrotik_manager.get_old_leases(age, include_never=include_never)
        handler._send_json({'success': True, 'leases': old, 'count': len(old), 'age_days': age})
    except Exception as e:
        logging.error("Ошибка поиска устаревших лизов: %s", e, exc_info=True)
        handler._send_json({'success': False, 'error': str(e)}, 500)
