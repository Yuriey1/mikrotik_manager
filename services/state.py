import time
import threading
import logging

log = logging.getLogger(__name__)

# Глобальный кэш (общий для всех сессий)
netbox_client = None

# Matrix-интеграция (плагин) — общий
pending_requests = []
matrix_available = False
matrix_verified = False
pending_verification = None  # {txn_id, from_device, emojis, desc}

# Сессионные данные — {token: session_dict}
session_data = {}


def create_session(token, user):
    """Создать сессию для пользователя"""
    session_data[token] = {
        'mikrotik_manager': None,
        'tree_builder': None,
        'current_device_name': None,
        'user': user,
        'last_access': time.time(),
    }


class SessionContext:
    """Прокси-объект для доступа к данным сессии через привычные атрибуты"""
    def __init__(self, data):
        self._data = data

    @property
    def mikrotik_manager(self): return self._data['mikrotik_manager']
    @mikrotik_manager.setter
    def mikrotik_manager(self, val): self._data['mikrotik_manager'] = val

    @property
    def tree_builder(self): return self._data['tree_builder']
    @tree_builder.setter
    def tree_builder(self, val): self._data['tree_builder'] = val

    @property
    def current_device_name(self): return self._data['current_device_name']
    @current_device_name.setter
    def current_device_name(self, val): self._data['current_device_name'] = val

    @property
    def user(self): return self._data.get('user')


def get_session_ctx(handler) -> SessionContext | None:
    """Получить контекст сессии по токену. Без токена → None."""
    token = handler.headers.get('X-Session-Token', '')
    if token and token in session_data:
        s = session_data[token]
        s['last_access'] = time.time()
        return SessionContext(s)
    return None


SESSION_TTL = 7200
CLEANUP_INTERVAL = 300


def _cleanup_sessions():
    while True:
        time.sleep(CLEANUP_INTERVAL)
        now = time.time()
        for token in list(session_data.keys()):
            s = session_data.get(token)
            if not s: continue
            if now - s.get('last_access', 0) > SESSION_TTL:
                try:
                    if s.get('mikrotik_manager'):
                        s['mikrotik_manager'].disconnect()
                except Exception: pass
                del session_data[token]
                log.info("🗑️ Session cleanup: удалена сессия %s", token[:8])


def start_cleanup():
    t = threading.Thread(target=_cleanup_sessions, daemon=True, name='session-cleanup')
    t.start()
