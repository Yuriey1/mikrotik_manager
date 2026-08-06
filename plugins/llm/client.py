"""LLM-клиент: DeepSeek API (OpenAI Chat Completions)"""

import json
import httpx


async def generate(prompt: str, api_key: str, model: str = "deepseek-chat",
                   url: str = "https://api.deepseek.com/v1/chat/completions",
                   timeout: int = 30) -> dict:
    """Отправить запрос в LLM и вернуть JSON-ответ"""
    if not api_key:
        raise ValueError("LLM API key required")

    body = {
        'model': model,
        'messages': [
            {'role': 'system', 'content': 'Ты парсер. Верни ТОЛЬКО JSON, без пояснений.'},
            {'role': 'user', 'content': prompt},
        ],
        'temperature': 0,
        'response_format': {'type': 'json_object'},
    }

    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(url, headers={
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json',
        }, json=body)
        resp.raise_for_status()
        data = resp.json()
        return json.loads(data['choices'][0]['message']['content'])
