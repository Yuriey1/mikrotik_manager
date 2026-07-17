"""Слушатель сообщений Matrix (Element/Synapse) с поддержкой E2EE"""

import asyncio
import datetime
import logging
import json
import os
from typing import Dict

import services.state as state
from plugins.matrix_integration.parser import parse_message

log = logging.getLogger(__name__)
CONFIG_PATH = os.path.join(os.path.dirname(__file__), 'config.json')
STORE_PATH = os.path.join(os.path.dirname(__file__), '_matrix_store')

LLM_SYSTEM_PROMPT = """Извлеки из сообщения данные для подключения абонента к MikroTik.
Верни ТОЛЬКО JSON, без пояснений:
{
  "mac": "AA:BB:CC:DD:EE:FF или null",
  "ip": "192.168.x.x или null",
  "full_name": "Фамилия Имя Отчество или null",
  "position": "должность или null",
  "site": "площадка или null",
  "internet_access": true или false,
  "is_full_access": true или false или null
}
Площадки (site): Шалакит, Дражный, Надежда, Магызы, Весёлый, Караган, Нелькан, Джигда, Чумикан, Аим.
internet_access=true если "полный доступ", "интернет", "подключите интернет", "инет".
internet_access=false если "корп.ресы", "корпоративные ресурсы", "бесплатный доступ", "max".
is_full_access=true если "полный доступ" или "интернет".
is_full_access=false если "корп.ресы" или "max".
is_full_access=null если непонятно.
Если IP сокращённый (ип 91.67) — восстанови до полного: 192.168.XX.YY.
MAC всегда в верхнем регистре через двоеточие."""


def _remove_replied_request(event):
    """Удалить pending-заявку, на которую пришёл ответ + или лс (через Matrix reply)"""
    reply_to = None
    content = getattr(event, 'source', {})
    if isinstance(content, dict):
        content = content.get('content', {})
    if isinstance(content, dict):
        relates = content.get('m.relates_to', {})
        if isinstance(relates, dict):
            reply_to = relates.get('event_id')

    if not reply_to:
        return False

    before = len(state.pending_requests)
    state.pending_requests = [
        r for r in state.pending_requests
        if r.get('event_id') != reply_to
    ]
    removed = before - len(state.pending_requests)
    if removed:
        log.info("🗑️ Matrix: удалена заявка по reply %s (%d шт.)", reply_to[:20], removed)
    return removed > 0


def load_config() -> Dict:
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)


class MatrixListener:
    def __init__(self):
        self.config = load_config()
        if not self.config.get('enabled', False):
            log.info("Matrix-интеграция отключена в конфиге")
            return

        self.homeserver = self.config['homeserver_url']
        self.username = self.config['username']
        self.password = self.config.get('password', '')
        self.access_token = self.config.get('access_token', '')
        self.user_id = self.config.get(
            'user_id',
            f"@{self.username}:{self.homeserver.replace('https://', '').replace('http://', '')}"
        )
        self.room_id = self.config['room_id']
        self.client = None

    async def _on_to_device(self, event):
        """Обработка to-device событий — авто-подтверждение верификации"""
        import nio
        log.info("📨 _on_to_device: %s from %s", type(event).__name__, getattr(event, 'sender', '?'))
        try:
            if isinstance(event, nio.KeyVerificationStart):
                log.info("🔐 Matrix: запрос верификации от %s (txn %s)", event.sender, event.transaction_id)

                resp = await self.client.accept_key_verification(event.transaction_id)
                if isinstance(resp, nio.ToDeviceError):
                    log.warning("⚠️ Matrix: ошибка accept_key_verification — %s", resp)
                    return
                log.info("✅ Matrix: верификация принята")

                sas = self.client.key_verifications[event.transaction_id]
                todevice_msg = sas.share_key()
                await self.client.to_device(todevice_msg)
                log.info("🔑 Matrix: ключ отправлен")

            elif isinstance(event, nio.KeyVerificationKey):
                log.info("🔑 Matrix: получен ключ верификации (txn %s), подтверждаю", event.transaction_id)
                resp = await self.client.confirm_short_auth_string(event.transaction_id)
                if isinstance(resp, nio.ToDeviceError):
                    log.warning("⚠️ Matrix: ошибка confirm — %s", resp)

            elif isinstance(event, nio.KeyVerificationMac):
                log.info("✅ Matrix: верификация завершена (txn %s)", event.transaction_id)
                sas = self.client.key_verifications.get(event.transaction_id)
                if sas:
                    todevice_msg = sas.get_mac()
                    await self.client.to_device(todevice_msg)

            elif isinstance(event, nio.KeyVerificationCancel):
                log.warning("⚠️ Matrix: верификация отменена — %s: %s",
                            getattr(event, 'code', '?'), getattr(event, 'reason', '?'))

        except Exception as e:
            log.warning("⚠️ Matrix: ошибка в _on_to_device — %s", e)

    async def _connect(self):
        try:
            import nio
        except ImportError:
            log.error("matrix-nio не установлен. pip install matrix-nio")
            return False

        os.makedirs(STORE_PATH, exist_ok=True)
        config = nio.AsyncClientConfig(encryption_enabled=True)
        self.client = nio.AsyncClient(
            self.homeserver, self.username,
            store_path=STORE_PATH, config=config,
        )

        if self.access_token:
            self.client.access_token = self.access_token
            self.client.user_id = self.user_id
            if self.config.get('device_id'):
                self.client.device_id = self.config['device_id']
            log.info("✅ Matrix: подключён по токену как %s", self.user_id)
        else:
            password = self.password
            if not password:
                log.error("❌ Matrix: не указан ни токен, ни пароль")
                return False
            resp = await self.client.login(password, device_name="mikrotik-manager")
            if isinstance(resp, nio.LoginResponse):
                log.info("✅ Matrix: вход выполнен как %s", resp.user_id)
            else:
                log.error("❌ Matrix: ошибка входа — %s", resp)
                return False

        log.info("🔐 Matrix: загружаю хранилище ключей...")
        try:
            self.client.load_store()
            log.info("✅ Matrix: хранилище ключей загружено")

            # Регистрируем обработчик to-device событий
            self.client.add_to_device_callback(self._on_to_device, None)
            log.info("✅ Matrix: обработчик верификации зарегистрирован")

            log.info("🔑 Matrix: загружаю ключи устройства...")
            try:
                await self.client.keys_upload()
                log.info("✅ Matrix: ключи устройства загружены")
            except Exception:
                log.info("ℹ️ Matrix: ключи уже загружены (пропускаю)")

            # Авто-доверие: отложим до первого sync в _listen()
            log.info("🤝 Matrix: авто-доверие будет выполнено после первого sync")

        except Exception as e:
            log.warning("⚠️ Matrix: ошибка инициализации E2EE — %s", e)

        return True

    async def _auto_trust_devices(self):
        """Авто-доверие всех устройств этого же пользователя"""
        try:
            store = getattr(self.client, 'device_store', None)
            if not store:
                log.warning("⚠️ Matrix: device_store не доступен")
                return

            try:
                my_devices = store[self.client.user_id]
            except (KeyError, TypeError):
                log.warning("⚠️ Matrix: нет устройств для %s", self.client.user_id)
                return

            log.info("🤝 Matrix: найдено %s устройств для %s", len(my_devices), self.client.user_id)
            for dev_id, olm_dev in my_devices.items():
                if dev_id == self.client.device_id:
                    continue
                try:
                    self.client.verify_device(olm_dev)
                    log.info("✅ Matrix: устройство %s помечено как доверенное", dev_id)
                except Exception as e:
                    log.warning("⚠️ Matrix: не удалось доверить %s — %s", dev_id, e)
        except Exception as e:
            log.warning("⚠️ Matrix: ошибка авто-доверия — %s", e)

    async def _listen(self):
        if not self.client:
            return

        log.info("🔔 Matrix: начинаю слушать комнату %s", self.room_id)
        since_token = None
        first_sync = True

        while True:
            try:
                resp = await self.client.sync(timeout=30000, since=since_token)
                since_token = resp.next_batch

                # Авто-доверие после первого sync
                if first_sync:
                    first_sync = False
                    log.info("🤝 Matrix: выполняю авто-доверие устройств...")
                    try:
                        await self.client.keys_query()
                        await self._auto_trust_devices()
                    except Exception as e:
                        log.warning("⚠️ Matrix: ошибка авто-доверия — %s", e)

                # Авто-обработка верификаций: проверяем pending вручную
                import nio
                verifications = getattr(self.client, 'key_verifications', None)
                if verifications:
                    for txn_id, v in list(verifications.items()):
                        st = str(getattr(v, 'state', ''))
                        if 'request' in st.lower() or 'start' in st.lower():
                            log.info("🔐 Matrix: принимаю верификацию txn=%s state=%s", txn_id, st)
                            try:
                                r = await self.client.accept_key_verification(txn_id)
                                if not isinstance(r, nio.ToDeviceError):
                                    sas = self.client.key_verifications[txn_id]
                                    msg = sas.share_key()
                                    await self.client.to_device(msg)
                                    log.info("✅ Matrix: ключ отправлен")
                            except Exception as e:
                                log.warning("accept error: %s", e)

                if self.room_id not in resp.rooms.join:
                    continue

                room = resp.rooms.join[self.room_id]
                for event in room.timeline.events:
                    body = getattr(event, 'body', None)
                    if not body or not body.strip():
                        continue

                    body_stripped = body.strip()
                    event_id = getattr(event, 'event_id', None)

                    # Любой reply на заявку = удаляем её из pending
                    # Кроме "согласовано" — это не закрытие, а аппрув
                    body_lower = body_stripped.lower()
                    if not body_lower.startswith('согласовано'):
                        if _remove_replied_request(event):
                            continue

                    # Пропускаем подтверждения (+ / лс) — не заявки
                    if body_stripped.startswith('+') or body_stripped.lower().startswith('лс'):
                        continue

                    log.info("📩 Matrix: новое сообщение от %s — %s", event.sender, body[:80])

                    # LLM-парсер (если включен) → regex fallback
                    parsed = None
                    if self.config.get('llm_enabled', False):
                        try:
                            from plugins.llm.parser import parse_with_llm
                            parsed = await asyncio.wait_for(
                                parse_with_llm(body, LLM_SYSTEM_PROMPT), timeout=10
                            )
                            log.debug("Matrix: LLM парсинг успешен")
                        except Exception:
                            log.debug("Matrix: LLM ошибка, использую regex")

                    if not parsed:
                        parsed = parse_message(body)

                    # Пропускаем сообщения без полезных данных (не заявки)
                    if not parsed.get('mac') and not parsed.get('ip') and not parsed.get('full_name'):
                        log.debug("Matrix: сообщение не является заявкой, пропускаю")
                        continue

                    parsed['event_id'] = event_id
                    parsed['sender'] = event.sender
                    parsed['received_at'] = datetime.datetime.now().isoformat()
                    state.pending_requests.append(parsed)
                    log.info("📋 Заявка добавлена: ID=%s, ФИО=%s, IP=%s, MAC=%s",
                             parsed['id'], parsed.get('full_name'),
                             parsed.get('ip'), parsed.get('mac'))

            except asyncio.CancelledError:
                break
            except Exception as e:
                log.error("Matrix: ошибка sync — %s", e, exc_info=True)
                await asyncio.sleep(10)

    async def _run(self):
        if not self.config.get('enabled', False):
            return
        if not await self._connect():
            return
        await self._listen()

    def start(self):
        if not self.config.get('enabled', False):
            return
        log.info("🚀 Matrix-слушатель запускается...")
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self._run())
