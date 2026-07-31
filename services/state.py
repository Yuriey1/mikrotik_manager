import time

# Глобальный кэш (общий для всех сессий)
netbox_client = None

# Matrix-интеграция (плагин) — общий
pending_requests = []
matrix_available = False

# Старые переменные — используются default-сессией для обратной совместимости
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


def get_session_ctx(handler) -> dict:
    """
    Получить контекст сессии.
    Если есть X-Session-Token → вернуть сессионный контекст.
    Если нет → обновить глобальные переменные и вернуть None (signals old code).
    """
    token = handler.headers.get('X-Session-Token', '')
    if token and token in session_data:
        s = session_data[token]
        s['last_access'] = time.time()
        return s
    return None  # Обратная совместимость: используем глобальные переменные
