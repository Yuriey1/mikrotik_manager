"""Слушатель сообщений Matrix (Element/Synapse) с поддержкой E2EE"""

import asyncio
import datetime
import logging
import json
import os
import re
from typing import Dict

import services.state as state
from plugins.matrix_integration.parser import parse_message

log = logging.getLogger(__name__)
CONFIG_PATH = os.path.join(os.path.dirname(__file__), 'config.json')
STORE_PATH = os.path.join(os.path.dirname(__file__), '_matrix_store')

LLM_SYSTEM_PROMPT = """Извлеки из сообщения поля: mac, ip, full_name, position, site, internet_access.
null если нет.
mac: AA:BB:CC:DD:EE:FF
ip: полный (192.168.91.67 если "ип 91.67")
full_name: Фамилия Имя Отчество
position: должность
site: Шалакит,Дражный,Надежда,Магызы,Весёлый,Караган
internet_access: true(интернет,полный доступ) или false(корп.ресы,max)
Верни ТОЛЬКО JSON: {"mac":null,"ip":null,"full_name":null,"position":null,"site":null,"internet_access":false}"""

CLASSIFY_PROMPT = """Это заявка на подключение абонента к MikroTik? Ответь ТОЛЬКО "ДА" или "НЕТ".

ДА (заявка): подключите, пропишите, добавьте, mac-адрес, ip-адрес, ФИО, должность, площадка
НЕТ (не заявка): проверьте, не хватает, закончился, скиньте сессию, вопрос, согласовано, +

Сообщение: {text}"""


def _remove_replied_request(event):
    """Удалить pending-заявку, на которую пришёл ответ (через Matrix reply)"""
    reply_to = None
    content = getattr(event, 'source', {})
    if isinstance(content, dict):
        # Ищем m.relates_to на двух уровнях
        inner = content.get('content', {})
        if isinstance(inner, dict):
            relates = inner.get('m.relates_to', {})
        else:
            relates = {}
        # Если не нашли внутри content — ищем на верхнем уровне
        if not relates:
            relates = content.get('m.relates_to', {})
        if isinstance(relates, dict):
            # Формат 1: простой reply {event_id: ...}
            reply_to = relates.get('event_id')
            # Формат 2: Element rich reply {m.in_reply_to: {event_id: ...}}
            if not reply_to:
                in_reply = relates.get('m.in_reply_to', {})
                if isinstance(in_reply, dict):
                    reply_to = in_reply.get('event_id')
    if not reply_to:
        log.info("🔍 Matrix: reply не найден. top_keys=%s, inner_keys=%s, relates=%s",
                 list(content.keys())[:8] if isinstance(content, dict) else '?',
                 list(inner.keys())[:8] if isinstance(inner, dict) else '?',
                 json.dumps(relates, ensure_ascii=False)[:200] if relates else 'N/A')
        return False

    before = len(state.pending_requests)
    state.pending_requests = [
        r for r in state.pending_requests
        if r.get('event_id') != reply_to
    ]
    removed = before - len(state.pending_requests)
    if removed:
        fmt = 'event_id' if relates.get('event_id') else 'm.in_reply_to'
        log.info("🗑️ Matrix: удалена заявка по reply (fmt=%s, relates=%s) %s (%d шт.)",
                 fmt,
                 json.dumps(relates, ensure_ascii=False)[:100] if relates else '?',
                 reply_to[:20], removed)
    return removed > 0


def load_config() -> Dict:
    """Больше не используется — всё в БД"""
    return {}


class MatrixListener:
    def __init__(self):
        # Читаем настройки из БД (MatrixConfig для nur001)
        self.enabled = False
        try:
            from models.user import MatrixConfig, User
            user = User.get_or_none(User.username == 'nur001')
            if user:
                mc = MatrixConfig.get_or_none(MatrixConfig.user == user)
                if mc and mc.enabled and mc.token and mc.room_id:
                    self.enabled = True
                    self.homeserver = mc.homeserver or 'https://matrix.krasintegra.ru'
                    self.username = mc.matrix_user or 'nur001'
                    self.access_token = mc.token
                    self.user_id = mc.matrix_user or '@nur001:matrix.krasintegra.ru'
                    self.room_id = mc.room_id
                    log.info("Matrix: конфиг загружен из БД для %s", self.username)
        except Exception as e:
            log.warning("Matrix: не удалось загрузить конфиг из БД — %s", e)

        if not self.enabled:
            log.info("Matrix-интеграция отключена (нет конфига в БД)")
            return

        self.client = None

    async def _on_to_device(self, event):
        """Авто-верификация через SAS (эмодзи)"""
        import nio
        try:
            txn_id = getattr(event, 'transaction_id', None)
            etype = type(event).__name__

            # Dedup по типу+txn — защита от повторных синков
            if txn_id:
                if not hasattr(self, '_seen_verify'):
                    self._seen_verify = {}
                key = f"{etype}:{txn_id}"
                if key in self._seen_verify:
                    return
                self._seen_verify[key] = True

            if isinstance(event, nio.UnknownToDeviceEvent):
                raw = getattr(event, 'type', '')
                if raw == 'm.key.verification.request':
                    txn = event.source.get('content', {}).get('transaction_id', '')
                    fdev = event.source.get('content', {}).get('from_device', '')
                    if txn and fdev:
                        await self.client.to_device(nio.ToDeviceMessage(
                            type='m.key.verification.ready',
                            recipient=event.sender,
                            recipient_device=fdev,
                            content={'transaction_id': txn, 'methods': ['m.sas.v1'],
                                     'from_device': self.client.device_id},
                        ))
                return

            if isinstance(event, nio.KeyVerificationStart):
                resp = await self.client.accept_key_verification(event.transaction_id)
                if isinstance(resp, nio.ToDeviceError):
                    log.warning("⚠️ Matrix: ошибка accept — %s", resp)
                    return
                sas = self.client.key_verifications[event.transaction_id]
                await self.client.to_device(sas.share_key())
                log.info("🔐 Matrix: верификация принята txn=%s", event.transaction_id[:12])

            elif isinstance(event, nio.KeyVerificationKey):
                try:
                    await self.client.confirm_short_auth_string(event.transaction_id)
                    log.info("🔑 Matrix: ключ подтверждён")
                except Exception as e:
                    log.warning("⚠️ Matrix: ошибка confirm — %s", e)

            elif isinstance(event, nio.KeyVerificationMac):
                log.info("🎉 Matrix: верификация ЗАВЕРШЕНА!")
                import services.state as state
                state.matrix_verified = True
                sas = self.client.key_verifications.get(event.transaction_id)
                if sas:
                    try:
                        await self.client.to_device(sas.get_mac())
                    except Exception:
                        pass

        except Exception as e:
            log.warning("⚠️ Matrix: ошибка в _on_to_device — %s", e)

    async def _on_room_event(self, room, event):
        """Обработка комнатных сообщений (заявки) — вызывается из sync_forever"""
        body = getattr(event, 'body', None)
        if not body or not body.strip():
            return
        if room.room_id != self.room_id:
            return

        body_stripped = body.strip()
        event_id = getattr(event, 'event_id', None)

        # Любой reply на заявку = удаляем её из pending (кроме "согласовано")
        body_lower = body_stripped.lower()
        if not body_lower.startswith('согласовано'):
            if _remove_replied_request(event):
                return

        # Пропускаем подтверждения (+ / лс)
        clean = re.sub(r'^[*>\s]+', '', body_stripped)
        if clean.startswith('+') or clean.lower().startswith('лс'):
            if not _remove_replied_request(event):
                if len(state.pending_requests) == 1:
                    removed = state.pending_requests.pop()
                    log.info("🗑️ Matrix: удалена заявка по '+' (единственная) %s", removed.get('id', '?')[:8])
            return

        log.info("📩 Matrix: новое сообщение от %s — %s", event.sender, body[:80])

        # Этап 1: LLM-классификация
        looks_like_request = True
        if self.classify_enabled and self.llm_api_key:
            try:
                looks_like_request = await asyncio.wait_for(
                    self._classify_request(body), timeout=10
                )
                if not looks_like_request:
                    return
            except Exception:
                pass
        elif not self.classify_enabled:
            has_mac = re.search(r'([0-9A-Fa-f]{2}:[0-9A-Fa-f]{2})', body)
            has_ip = re.search(r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}|ип\s+\d{1,3})', body)
            has_name = re.search(r'[А-ЯЁ][а-яё]+\s+[А-ЯЁ][а-яё]+', body)
            looks_like_request = bool(has_mac or has_ip or has_name)

        if not looks_like_request:
            return

        # Этап 2: парсинг
        parsed = None
        use_llm = self.parsing_mode in ('hybrid', 'llm') and self.llm_api_key
        if use_llm:
            try:
                from plugins.llm.parser import parse_with_llm
                parsed = await asyncio.wait_for(
                    parse_with_llm(body, LLM_SYSTEM_PROMPT, api_key=self.llm_api_key, timeout=None), timeout=120
                )
            except Exception as e:
                log.warning("🤖 Matrix: LLM ошибка (%s: %s), использую regex", type(e).__name__, e)

        if not parsed or self.parsing_mode == 'regex':
            from plugins.matrix_integration.parser import parse_all
            parsed_list = parse_all(body)
        else:
            parsed_list = [parsed] if parsed else []

        for parsed in parsed_list:
            if not parsed.get('id'):
                import uuid
                parsed['id'] = str(uuid.uuid4())
            if not parsed.get('mac') and not parsed.get('ip') and not parsed.get('full_name'):
                continue
            parsed['event_id'] = event_id
            parsed['sender'] = event.sender
            src = getattr(event, 'source', {}) or {}
            origin_ts = src.get('origin_server_ts', 0)
            parsed['received_at'] = (
                datetime.datetime.fromtimestamp(origin_ts / 1000).isoformat()
                if origin_ts else datetime.datetime.now().isoformat()
            )
            state.pending_requests.append(parsed)
            log.info("📋 Заявка добавлена: ID=%s, ФИО=%s, IP=%s, MAC=%s",
                     parsed['id'], parsed.get('full_name'),
                     parsed.get('ip'), parsed.get('mac'))

    async def _connect(self):
        try:
            import nio
        except ImportError:
            log.error("matrix-nio не установлен. pip install matrix-nio")
            return False

        os.makedirs(STORE_PATH, exist_ok=True)
        full_user = '@' + self.username + ':matrix.krasintegra.ru'
        config = nio.AsyncClientConfig(encryption_enabled=True)
        self.client = nio.AsyncClient(
            self.homeserver, full_user,
            store_path=STORE_PATH, config=config,
        )

        if not self.access_token:
            log.error("❌ Matrix: не указан токен доступа")
            return False

        self.client.access_token = self.access_token
        self.client.user_id = full_user

        # Узнаём device_id у сервера (whoami)
        try:
            who = await self.client.whoami()
            self.client.device_id = who.device_id
            log.info("📱 Matrix: device_id=%s (подтверждён сервером)", who.device_id)

            # Если хранилище уже есть, проверим что оно от того же устройства
            import glob
            dbs = glob.glob(os.path.join(STORE_PATH, '*.db'))
            if dbs:
                name = os.path.basename(dbs[0]).replace('.db', '')
                parts = name.rsplit('_', 1)
                stored_dev = parts[1] if len(parts) == 2 else None
                if stored_dev and stored_dev != who.device_id:
                    log.warning("⚠️ Matrix: device_id в хранилище (%s) != сервер (%s), очищаю", stored_dev, who.device_id)
                    import shutil
                    shutil.rmtree(STORE_PATH)
                    os.makedirs(STORE_PATH, exist_ok=True)
        except Exception as e:
            log.warning("⚠️ Matrix: не удалось получить device_id — %s", e)

        log.info("✅ Matrix: подключён по токену как %s", self.user_id)

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

        except Exception as e:
            log.warning("⚠️ Matrix: ошибка инициализации E2EE — %s", e)

        # Проверка LLM (всегда, даже если E2EE не загрузился)
        self._check_llm()

        return True

    def _check_llm(self):
        """Проверить Matrix/LLM из БД для пользователя nur001"""
        try:
            from models.user import MatrixConfig, User
            user = User.get_or_none(User.username == 'nur001')
            if user:
                mc = MatrixConfig.get_or_none(MatrixConfig.user == user)
                if mc and mc.enabled:
                    # Колокольчик активен даже без LLM (режим regex)
                    state.matrix_available = True
                    self.llm_api_key = mc.llm_key if mc.llm_enabled and mc.llm_key else None
                    self.matrix_user = mc.matrix_user or 'nur001'
                    self.llm_url = mc.llm_url or 'https://api.deepseek.com/v1/chat/completions'
                    self.parsing_mode = mc.parsing_mode or 'regex'
                    self.classify_enabled = bool(mc.classify_enabled)
                    log.info("✅ Matrix: активен (mode=%s, classify=%s, llm=%s)",
                             self.parsing_mode, self.classify_enabled, bool(self.llm_api_key))
                    return
        except Exception as e:
            log.warning("Matrix: ошибка чтения из БД — %s", e)

        state.matrix_available = False
        self.llm_api_key = None
        self.matrix_user = 'nur001'
        self.parsing_mode = 'regex'
        self.classify_enabled = False
        log.info("🔕 Matrix: недоступен, колокольчик отключён")

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

    async def _classify_request(self, text: str) -> bool:
        """Этап 1: быстрая классификация — похоже ли сообщение на заявку?"""
        try:
            from plugins.llm.client import generate
            prompt = CLASSIFY_PROMPT.format(text=text)
            result = await generate(prompt, api_key=self.llm_api_key)
            # DeepSeek возвращает JSON, извлекаем ответ
            answer = str(result).strip().upper()
            is_request = 'ДА' in answer and len(answer) < 10
            log.info("🔍 Matrix: классификация → %s", 'ЗАЯВКА' if is_request else 'НЕТ')
            return is_request
        except Exception as e:
            log.warning("🔍 Matrix: ошибка классификации (%s), пропускаю", e)
            return False

    async def _listen(self, stop_event=None):
        import nio
        if not self.client:
            return

        log.info("🔔 Matrix: начинаю слушать комнату %s", self.room_id)

        self.client.add_event_callback(self._on_room_event, nio.RoomMessageText)

        # Первый синк — вручную с таймаутом (sync_forever использует timeout=0)
        try:
            first = await self.client.sync(timeout=30000)
            if isinstance(first, nio.SyncError):
                log.error("Matrix: ошибка первого синка — %s", first.message)
                return
            await self.client.run_response_callbacks([first])
            await self.client.send_to_device_messages()
            log.info("✅ Matrix: первый синк завершён")

            # Авто-доверие после первого синка
            log.info("🤝 Matrix: выполняю авто-доверие устройств...")
            try:
                await self.client.keys_query()
                await self._auto_trust_devices()
            except Exception as e:
                log.warning("⚠️ Matrix: ошибка авто-доверия — %s", e)
        except Exception as e:
            log.error("Matrix: ошибка первого синка — %s", e, exc_info=True)
            return

        # Запускаем sync_forever для последующих циклов
        async def _stop_watcher():
            while stop_event and not stop_event.is_set():
                await asyncio.sleep(1)
            log.info("🛑 Matrix: остановка бота по сигналу")
            self.client.stop_sync_forever()

        watcher = asyncio.create_task(_stop_watcher())
        try:
            await self.client.sync_forever(timeout=30000)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            log.error("Matrix: ошибка sync_forever — %s", e, exc_info=True)
        finally:
            self.client.stop_sync_forever()
            watcher.cancel()
            log.info("🛑 Matrix: sync_forever остановлен")

    async def _run(self, stop_event=None):
        if not self.enabled:
            return
        if not await self._connect():
            return
        await self._listen(stop_event)

    def start(self):
        if not self.enabled:
            return
        log.info("🚀 Matrix-слушатель запускается...")
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        # Настроить проверку stop_event
        import plugins.matrix_integration.plugin as plugin
        loop.call_soon_threadsafe(lambda: None)
        loop.run_until_complete(self._run(plugin._stop_event))
