"""
HTTP сервер и обработчики запросов
"""

from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse
import json
import traceback
import os

# ── Route handlers ────────────────────────────────────────────
from services.routes import get as get_routes
from services.routes import post as post_routes
from services.routes import delete as delete_routes


# ══════════════════════════════════════════════════════════════
#  HTTP Server
# ══════════════════════════════════════════════════════════════

class StoppableHTTPServer(HTTPServer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._is_running = True

    def serve_forever(self, poll_interval=0.5):
        while self._is_running:
            try:
                self.handle_request()
            except (KeyboardInterrupt, SystemExit):
                self._is_running = False
                break
            except Exception as e:
                if self._is_running:
                    print(f"⚠️  Ошибка обработки запроса: {e}")

    def shutdown(self):
        self._is_running = False
        try:
            self.socket.close()
        except Exception:
            pass


# ══════════════════════════════════════════════════════════════
#  Route maps
# ══════════════════════════════════════════════════════════════

GET_ROUTES = {
    '/api/devices':           get_routes.handle_devices,
    '/api/connect':           get_routes.handle_connect,
    '/api/disconnect':        get_routes.handle_disconnect,
    '/api/tree':              get_routes.handle_tree,
    '/api/stats':             get_routes.handle_stats,
    '/api/sync':              get_routes.handle_sync,
    '/api/find_queues':       get_routes.handle_find_queues,
    '/api/check_ip':          get_routes.handle_check_ip,
    '/api/netbox/config':     get_routes.handle_netbox_config,
    '/api/netbox/test':       get_routes.handle_netbox_test,
    '/api/find_dhcp_lease':   get_routes.handle_find_dhcp_lease,
    '/api/free_ips':          get_routes.handle_free_ips,
    '/api/dhcp_pools':        get_routes.handle_dhcp_pools,
    '/api/dhcp_subscribers':  get_routes.handle_dhcp_subscribers,
    '/api/internet_access':   get_routes.handle_internet_access,
    '/api/analyze_channels':  get_routes.handle_analyze_channels,
    '/api/check_mac':         get_routes.handle_check_mac,
}

POST_ROUTES = {
    '/api/netbox/save_config':     post_routes.handle_save_netbox,
    '/api/add_device':             post_routes.handle_add_device,
    '/api/add_employee':           post_routes.handle_add_employee,
    '/api/replace_mac':            post_routes.handle_replace_mac,
    '/api/internet_access/toggle': post_routes.handle_toggle_internet,
    '/api/delete_subscriber':      post_routes.handle_delete_subscriber,
    '/api/edit_subscriber':        post_routes.handle_edit_subscriber,
}

DELETE_ROUTES = {
    '/api/forget_credentials': delete_routes.handle_forget_credentials,
    '/api/forget_password':    delete_routes.handle_forget_password,
}


# ══════════════════════════════════════════════════════════════
#  Request handler
# ══════════════════════════════════════════════════════════════

class MikroTikManagerHandler(BaseHTTPRequestHandler):

    # ── CORS and headers ──────────────────────────────────────

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def _set_headers(self, content_type='text/html'):
        self.send_response(200)
        self.send_header('Content-Type', f'{content_type}; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS, PUT, DELETE')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization, X-Requested-With')
        self.send_header('Access-Control-Allow-Credentials', 'true')
        self.end_headers()

    def _send_json(self, data, status=200):
        json_data = json.dumps(data, ensure_ascii=False, indent=2)
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Content-Length', str(len(json_data.encode('utf-8'))))
        self.end_headers()
        self.wfile.write(json_data.encode('utf-8'))

    # ── Static & HTML ─────────────────────────────────────────

    def _get_html_template(self):
        try:
            with open('index.html', 'r', encoding='utf-8') as f:
                return f.read()
        except Exception:
            return '<!DOCTYPE html><html><head><meta charset="UTF-8"><title>MikroTik Device Manager</title></head><body><p>index.html не найден</p></body></html>'

    def _serve_html(self):
        html = self._get_html_template()
        self._set_headers('text/html')
        self.wfile.write(html.encode('utf-8'))

    def _serve_static_file(self, path):
        path = path.lstrip('/')
        if not os.path.exists(path):
            self.send_error(404, f"File not found: {path}")
            return
        ct = 'text/plain'
        if path.endswith('.css'):
            ct = 'text/css; charset=utf-8'
        elif path.endswith('.js'):
            ct = 'application/javascript; charset=utf-8'
        elif path.endswith('.png'):
            ct = 'image/png'
        with open(path, 'rb') as f:
            content = f.read()
        self.send_response(200)
        self.send_header('Content-Type', ct)
        self.send_header('Content-Length', str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def _serve_favicon(self):
        try:
            with open('favicon.ico', 'rb') as f:
                self.send_response(200)
                self.send_header('Content-type', 'image/x-icon')
                self.end_headers()
                self.wfile.write(f.read())
        except FileNotFoundError:
            self.send_error(404, "File not found")

    # ── Route dispatchers ─────────────────────────────────────

    def do_DELETE(self):
        try:
            parsed = urlparse(self.path)
            path = parsed.path
            if path in DELETE_ROUTES:
                DELETE_ROUTES[path](self, parsed)
            else:
                self.send_error(404, "Not Found")
        except Exception as e:
            print(f"❌ Ошибка DELETE: {e}")
            self._send_json({'error': str(e)}, 500)

    def do_GET(self):
        try:
            parsed = urlparse(self.path)
            path = parsed.path

            if path == '/' or path == '/index.html':
                self._serve_html()
            elif path == '/favicon.ico':
                self._serve_favicon()
            elif path.startswith('/static/'):
                self._serve_static_file(path)
            elif path in GET_ROUTES:
                GET_ROUTES[path](self, parsed)
            else:
                self.send_error(404, "Not Found")
        except Exception as e:
            print(f"❌ Ошибка GET: {e}")
            self._send_json({'error': str(e)}, 500)

    def do_POST(self):
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))

            parsed = urlparse(self.path)
            path = parsed.path

            if path in POST_ROUTES:
                POST_ROUTES[path](self, data)
            else:
                self.send_error(404, "Not Found")
        except Exception as e:
            print(f"❌ Ошибка POST: {e}")
            self._send_json({'error': str(e)}, 500)

    # ── Logging ───────────────────────────────────────────────

    def log_message(self, format, *args):
        print(f"🌐 {self.address_string()} - {format % args}")


# ══════════════════════════════════════════════════════════════
#  Entry point
# ══════════════════════════════════════════════════════════════

def start_server(port=8090, host='0.0.0.0'):
    try:
        server_address = (host, port)
        http_server = StoppableHTTPServer(server_address, MikroTikManagerHandler)

        print("\n" + "=" * 60)
        print("🌐 Запуск веб-интерфейса...")
        print(f"   Адрес: http://localhost:{port}")
        print(f"   Или:   http://ваш_IP_адрес:{port}")
        print("\n📱 Откройте браузер для работы с приложением")
        print("=" * 60)
        print("Для остановки нажмите Ctrl+C")
        print("=" * 60)

        http_server.serve_forever()

    except KeyboardInterrupt:
        print("\n👋 Приложение завершено пользователем")
    except Exception as e:
        print(f"\n❌ Ошибка запуска сервера: {e}")
        traceback.print_exc()
    finally:
        print("\n👋 До свидания!")
