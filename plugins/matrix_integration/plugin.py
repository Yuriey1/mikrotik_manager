"""Точка входа плагина Matrix-интеграции"""

import threading
from plugins.matrix_integration.listener import MatrixListener, load_config


def start():
    """Запустить Matrix-слушатель в фоновом потоке"""
    config = load_config()
    if not config.get('enabled', False):
        return
    listener = MatrixListener()
    t = threading.Thread(target=listener.start, daemon=True, name='matrix-listener')
    t.start()
