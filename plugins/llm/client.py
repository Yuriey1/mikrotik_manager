"""Низкоуровневый клиент Ollama API"""

import json
import logging
import os

import httpx

log = logging.getLogger(__name__)
CONFIG_PATH = os.path.join(os.path.dirname(__file__), 'config.json')


def load_config():
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)


async def generate(prompt: str, model: str = None, timeout: int = None) -> dict:
    """Отправить запрос в Ollama и вернуть JSON-ответ"""
    config = load_config()
    model = model or config.get('model', 'qwen2.5:3b')
    timeout = timeout or config.get('timeout', 10)
    url = config.get('url', 'http://localhost:11434') + '/api/generate'

    async with httpx.AsyncClient() as client:
        resp = await client.post(url, json={
            'model': model,
            'prompt': prompt,
            'stream': False,
            'format': 'json',
        }, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
        return json.loads(data['response'])
