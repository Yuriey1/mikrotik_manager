"""Точка входа плагина Matrix-интеграции"""

import threading
from plugins.matrix_integration.listener import MatrixListener

_bot_thread = None
_stop_event = threading.Event()
_listener_obj = None


def start():
    """Запустить Matrix-слушатель в фоновом потоке"""
    global _bot_thread, _listener_obj, _stop_event
    restart()


def restart():
    """Перезапустить бота (остановить старый, запустить новый)"""
    global _bot_thread, _listener_obj, _stop_event

    # Остановить старый поток
    if _bot_thread and _bot_thread.is_alive():
        _stop_event.set()
        _bot_thread.join(timeout=5)

    _stop_event.clear()
    _listener_obj = MatrixListener()
    if not _listener_obj.enabled:
        return
    _bot_thread = threading.Thread(target=_listener_obj.start, daemon=True, name='matrix-listener')
    _bot_thread.start()
