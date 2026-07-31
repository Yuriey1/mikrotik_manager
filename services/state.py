import time
import threading
import logging

log = logging.getLogger(__name__)

# Глобальный кэш (общий для всех сессий)
netbox_client = None

# Matrix-интеграция (плагин) — общий
pending_requests = []
matrix_available = False

# Старые переменные — обратная совместимость (default-сессия)
mikrotik_manager = None
tree_builder = None
current_device_name = None

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
    def mikrotik_manager(self):
        return self._data['mikrotik_manager']
    @mikrotik_manager.setter
    def mikrotik_manager(self, val):
        self._data['mikrotik_manager'] = val

    @property
    def tree_builder(self):
        return self._data['tree_builder']
    @tree_builder.setter
    def tree_builder(self, val):
        self._data['tree_builder'] = val

    @property
    def current_device_name(self):
        return self._data['current_device_name']
    @current_device_name.setter
    def current_device_name(self, val):
        self._data['current_device_name'] = val

    @property
    def user(self):
        return self._data.get('user')


def get_session_ctx(handler) -> SessionContext:
    """
    Получить контекст сессии.
    Если есть X-Session-Token → вернуть сессионный.
    Если нет → вернуть контекст default-сессии (глобальные переменные).
    """
    token = handler.headers.get('X-Session-Token', '')
    if token and token in session_data:
        s = session_data[token]
        s['last_access'] = time.time()
        return SessionContext(s)
    # Default-сессия: прокси к глобальным переменным
    import sys
    mod = sys.modules[__name__]
    class DefaultContext:
        @property
        def mikrotik_manager(self): return mod.mikrotik_manager
        @mikrotik_manager.setter
        def mikrotik_manager(self, v): setattr(mod, 'mikrotik_manager', v)
        @property
        def tree_builder(self): return mod.tree_builder
        @tree_builder.setter
        def tree_builder(self, v): setattr(mod, 'tree_builder', v)
        @property
        def current_device_name(self): return mod.current_device_name
        @current_device_name.setter
        def current_device_name(self, v): setattr(mod, 'current_device_name', v)
        @property
        def user(self): return None  # default-сессия не имеет пользователя
    return DefaultContext()


SESSION_TTL = 7200  # 2 часа простоя → удаление сессии
CLEANUP_INTERVAL = 300  # проверка каждые 5 минут


def _cleanup_sessions():
    """Фоновый поток: удаление старых сессий"""
    while True:
        time.sleep(CLEANUP_INTERVAL)
        now = time.time()
        for token in list(session_data.keys()):
            s = session_data.get(token)
            if not s:
                continue
            age = now - s.get('last_access', 0)
            if age > SESSION_TTL:
                try:
                    if s.get('mikrotik_manager'):
                        s['mikrotik_manager'].disconnect()
                except Exception:
                    pass
                del session_data[token]
                log.info("🗑️ Session cleanup: удалена сессия %s (возраст %.0f мин)", token[:8], age / 60)


def start_cleanup():
    """Запустить фоновый поток очистки сессий"""
    t = threading.Thread(target=_cleanup_sessions, daemon=True, name='session-cleanup')
    t.start()
