import time

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
    return DefaultContext()
