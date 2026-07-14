#!/usr/bin/env python3
"""
MikroTik Device Manager - Главный файл запуска
"""

import argparse
import logging
import signal
import sys
from services.web_service import start_server
import traceback


def setup_logging():
    fmt = logging.Formatter('%(asctime)s %(levelname)-7s %(message)s', datefmt='%H:%M:%S')

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(fmt)
    console.setLevel(logging.INFO)

    file_handler = logging.FileHandler('mikrotik_manager.log', encoding='utf-8')
    file_handler.setFormatter(fmt)
    file_handler.setLevel(logging.DEBUG)

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    root.addHandler(console)
    root.addHandler(file_handler)

    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('requests').setLevel(logging.WARNING)


def signal_handler(signum, frame):
    """Обработчик сигналов для корректного завершения"""
    try:
        from services.state import mikrotik_manager, current_device_name
        if mikrotik_manager and mikrotik_manager.connected:
            logging.info("Отключаемся от %s...", current_device_name)
            mikrotik_manager.disconnect()
    except Exception:
        pass
    logging.warning("Получен сигнал %s, завершаю работу...", signum)
    sys.exit(0)

def main():
    """Основная функция запуска приложения"""

    setup_logging()
    # Парсинг аргументов командной строки
    parser = argparse.ArgumentParser(description='MikroTik Device Manager')
    parser.add_argument('--port', '-p', type=int, default=8090,
                        help='Порт для запуска сервера (по умолчанию: 8090)')
    parser.add_argument('--host', type=str, default='0.0.0.0',
                        help='Хост для привязки сервера (по умолчанию: 0.0.0.0)')
    args = parser.parse_args()
    
    print("=" * 60)
    print("MIKROTIK DEVICE MANAGER")
    print("=" * 60)
    
    # Установка обработчиков сигналов
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Запуск плагинов
    import os
    if os.path.isdir('plugins/matrix_integration'):
        try:
            from plugins.matrix_integration.plugin import start as start_matrix_plugin
            start_matrix_plugin()
        except Exception:
            logging.warning("⚠️ Не удалось загрузить плагин Matrix", exc_info=True)

    # Запуск HTTP сервера
    start_server(port=args.port, host=args.host)

if __name__ == "__main__":
    main()
