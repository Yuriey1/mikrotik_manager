"""Универсальный LLM-парсер: текст + system_prompt → словарь"""

import logging
from plugins.llm.client import generate

log = logging.getLogger(__name__)


async def parse_with_llm(text: str, system_prompt: str,
                         api_key: str, model: str = None, timeout: int = 10) -> dict:
    """Распарсить текст через LLM, вернуть словарь."""
    full_prompt = f"{system_prompt}\n\nСообщение: {text}"
    return await generate(full_prompt, api_key=api_key, model=model, timeout=timeout)
