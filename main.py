#!/usr/bin/env python3
"""
MikroTik Device Manager - Главный файл запуска
"""

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
    print("\n" + "="*60)
    print("🚀 MIKROTIK DEVICE MANAGER - ЗАПУСК ПРИЛОЖЕНИЯ")
    print("="*60)
    
    # Установка обработчиков сигналов
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Запуск HTTP сервера
    try:
        start_server()
    except Exception as e:
        print(f"\n❌ Ошибка запуска сервера: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    main()
