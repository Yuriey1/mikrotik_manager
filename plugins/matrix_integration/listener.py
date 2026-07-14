"""Слушатель сообщений Matrix (Element/Synapse)"""

import asyncio
import logging
import json
import os
from typing import Dict

import services.state as state
from plugins.matrix_integration.parser import parse_message

log = logging.getLogger(__name__)
CONFIG_PATH = os.path.join(os.path.dirname(__file__), 'config.json')


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

    async def _connect(self):
        try:
            from nio import AsyncClient, LoginResponse
        except ImportError:
            log.error("matrix-nio не установлен. pip install matrix-nio")
            return False

        self.client = AsyncClient(self.homeserver, self.username)

        if self.access_token:
            self.client.access_token = self.access_token
            self.client.user_id = self.user_id
            log.info("✅ Matrix: подключён по токену как %s", self.user_id)
            return True

        # Парольный вход (если нет токена)
        password = self.password
        if not password:
            log.error("❌ Matrix: не указан ни токен, ни пароль")
            return False

        resp = await self.client.login(password, device_name="mikrotik-manager")
        if isinstance(resp, LoginResponse):
            log.info("✅ Matrix: вход выполнен как %s", resp.user_id)
            return True
        else:
            log.error("❌ Matrix: ошибка входа — %s", resp)
            return False

    async def _listen(self):
        if not self.client:
            return

        log.info("🔔 Matrix: начинаю слушать комнату %s", self.room_id)
        since_token = None

        while True:
            try:
                resp = await self.client.sync(timeout=30000, since=since_token)
                since_token = resp.next_batch

                if self.room_id not in resp.rooms.join:
                    continue

                room = resp.rooms.join[self.room_id]
                for event in room.timeline.events:
                    if event.sender == self.client.user_id:
                        continue

                    body = getattr(event, 'body', None)
                    if not body or not body.strip():
                        continue

                    log.info("📩 Matrix: новое сообщение от %s — %s", event.sender, body[:80])
                    parsed = parse_message(body)
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
