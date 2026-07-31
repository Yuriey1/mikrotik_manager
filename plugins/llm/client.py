"""LLM-клиент: DeepSeek API"""

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
    """Отправить запрос в DeepSeek и вернуть JSON-ответ"""
    config = load_config()
    timeout_val = timeout if timeout is not None else config.get('timeout', 30)

    api_key = config.get('api_key', '')
    url = config.get('url', 'https://api.deepseek.com/v1/chat/completions')
    model = model or config.get('model', 'deepseek-chat')

    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json',
    }
    body = {
        'model': model,
        'messages': [
            {'role': 'system', 'content': 'Ты парсер. Верни ТОЛЬКО JSON, без пояснений.'},
            {'role': 'user', 'content': prompt},
        ],
        'temperature': 0,
        'response_format': {'type': 'json_object'},
    }

    async with httpx.AsyncClient(timeout=timeout_val) as client:
        resp = await client.post(url, headers=headers, json=body)
        resp.raise_for_status()
        data = resp.json()
        content = data['choices'][0]['message']['content']
        return json.loads(content)
