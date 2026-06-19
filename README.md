# MikroTik Device Manager

Веб-приложение для управления устройствами **MikroTik RouterOS** через API. Позволяет управлять DHCP-абонентами, деревом очередей, доступом в интернет и ARP-таблицей. Список устройств загружается из **NetBox**.

## Возможности

- Просмотр и управление DHCP-абонентами (добавление, редактирование, удаление)
- Визуализация прохождения трафика от канала до абонента через дерево очередей
- Назначение абонентов в очереди (Simple Queues) с подбором подходящей очереди
- Управление доступом в интернет (firewall address-list `internet_access`)
- Замена MAC-адреса абонента (по IP или вручную)
- Просмотр дерева очередей с иерархией и статистикой
- Поиск свободных IP в DHCP-пулах
- Интеграция с NetBox — список устройств, роли, сайты

## Требования

- Python 3.10+
- Доступ до MikroTik API (порт 8728)
- Настроенный NetBox (опционально, для списка устройств)

## Установка

```bash
git clone <repo-url>
cd mikrotik_manager
pip install -r requirements.txt
```

## Запуск

```bash
python3 main.py --port 8090 --host 0.0.0.0
```

Параметры:
- `--port`, `-p` — порт (по умолчанию 8090)
- `--host` — хост для привязки (по умолчанию 0.0.0.0)

Откройте в браузере `http://<IP-сервера>:8090`.

## Настройка NetBox

1. В веб-интерфейсе нажмите ⚙️ в панели «Устройства»
2. Укажите URL NetBox и API-токен
3. Нажмите «Проверить», затем «Сохранить»

Устройства фильтруются по производителю `Mikrotik` и наличию основного IP.

## Архитектура

```
main.py                         # Точка входа, логирование, сигналы
services/
├── web_service.py              # HTTP-сервер (244 строки)
├── state.py                    # Общие глобальные переменные
├── queue_builder.py            # Построитель дерева очередей
└── routes/
    ├── get.py                  # GET-обработчики (17 эндпоинтов)
    ├── post.py                 # POST-обработчики (7 эндпоинтов)
    └── delete.py               # DELETE-обработчики (2 эндпоинта)
managers/
└── mikrotik_manager.py         # Клиент MikroTik API (DHCP, ARP, queues, firewall)
models/
├── device.py                   # MikroTikDevice
├── employee.py                 # Employee
└── queue_node.py               # QueueNode (дерево очередей)
config/
└── config_manager.py           # Конфигурация, учётные данные, NetBox
netbox_client.py                # Клиент NetBox API
utils/
└── helpers.py                  # Вспомогательные функции
static/
├── css/style.css
└── js/
    ├── store.js                # Vue 3 reactive store
    ├── api.js                  # API-клиент + buildTrafficChains
    └── app.js                  # Vue 3 компоненты и логика
index.html                      # SPA (все шаблоны Vue)
```

## API

### GET

| Эндпоинт | Назначение |
|----------|-----------|
| `/api/devices` | Список устройств из NetBox |
| `/api/connect` | Подключение к MikroTik |
| `/api/disconnect` | Отключение от устройства |
| `/api/sync` | Все данные одним запросом (очереди, абоненты, каналы, интерфейсы) |
| `/api/tree` | Дерево очередей |
| `/api/stats` | Статистика очередей |
| `/api/find_queues` | Поиск очередей по IP |
| `/api/free_ips` | Свободные IP в DHCP-пулах |
| `/api/internet_access` | Список IP с доступом в интернет |
| `/api/analyze_channels` | Анализ каналов трафика |
| `/api/check_mac` | Проверка занятости MAC |
| `/api/check_ip` | Принадлежность IP к сетям MikroTik |
| `/api/find_dhcp_lease` | Поиск DHCP-лизинга по IP |
| `/api/dhcp_pools` | Список DHCP-пулов |
| `/api/dhcp_subscribers` | Список DHCP-абонентов |
| `/api/netbox/config` | Текущие настройки NetBox |
| `/api/netbox/test` | Проверка соединения с NetBox |

### POST

| Эндпоинт | Назначение |
|----------|-----------|
| `/api/netbox/save_config` | Сохранить настройки NetBox |
| `/api/add_employee` | Добавить абонента (DHCP + ARP + очереди + firewall) |
| `/api/edit_subscriber` | Редактировать абонента |
| `/api/delete_subscriber` | Полное удаление абонента |
| `/api/replace_mac` | Замена MAC-адреса |
| `/api/internet_access/toggle` | Вкл/выкл доступ в интернет |
| `/api/add_device` | Добавить устройство (legacy) |

### DELETE

| Эндпоинт | Назначение |
|----------|-----------|
| `/api/forget_credentials` | Удалить сохранённые учётные данные |
| `/api/forget_password` | Удалить пароль устройства (legacy) |

## Логирование

Логи пишутся в два потока одновременно:
- **Консоль** — уровень INFO (при запуске вручную)
- **`mikrotik_manager.log`** — уровень DEBUG (все сообщения, включая отладочные)

Формат: `ЧЧ:ММ:СС  LEVEL   сообщение`

## Файлы с чувствительными данными

Следующие файлы не должны попадать в репозиторий (добавлены в `.gitignore`):
- `netbox_config.json` — URL и токен NetBox
- `device_passwords.json` — учётные данные устройств
- `mikrotik_manager.log` — лог-файл с отладочной информацией

## Лицензия

Проект создан как эксперимент с AI-генерацией кода (Deepseek + GigaChat). Используйте на свой страх и риск.
