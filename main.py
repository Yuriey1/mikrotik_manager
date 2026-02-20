#!/usr/bin/env python3
"""
MikroTik Device Manager - Главный файл запуска
"""

import argparse
import signal
import sys
from services.web_service import start_server
import traceback

def signal_handler(signum, frame):
    """Обработчик сигналов для корректного завершения"""
    print(f"\n⚠️  Получен сигнал {signum}, завершаю работу...")
    sys.exit(0)

def main():
    """Основная функция запуска приложения"""
    
    # Парсинг аргументов командной строки
    parser = argparse.ArgumentParser(description='MikroTik Device Manager')
    parser.add_argument('--port', '-p', type=int, default=8090,
                        help='Порт для запуска сервера (по умолчанию: 8090)')
    parser.add_argument('--host', type=str, default='0.0.0.0',
                        help='Хост для привязки сервера (по умолчанию: 0.0.0.0)')
    args = parser.parse_args()
    
    print("\n" + "="*60)
    print("🚀 MIKROTIK DEVICE MANAGER - ЗАПУСК ПРИЛОЖЕНИЯ")
    print("="*60)
    
    # Установка обработчиков сигналов
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Запуск HTTP сервера
    try:
        start_server(port=args.port, host=args.host)
    except Exception as e:
        print(f"\n❌ Ошибка запуска сервера: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    main()
