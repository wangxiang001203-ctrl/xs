"""
AI service compatibility layer.

All model calls now go through model_gateway so future providers, fallback,
cost accounting and cache metadata can be added in one place.
"""
from __future__ import annotations

from typing import AsyncGenerator

from app.services import model_gateway


async def stream_generate(system_prompt: str, user_prompt: str, model: str | None = None) -> AsyncGenerator[str, None]:
    # Compatibility shim only. Product policy is non-streaming AI; callers
    # should use generate_once/generate_once_with_history.
    yield await generate_once(system_prompt, user_prompt, model)


async def generate_once(system_prompt: str, user_prompt: str, model: str | None = None) -> str:
    return await model_gateway.generate_once(system_prompt, user_prompt, model=model)


async def generate(system_prompt: str, user_prompt: str, model: str | None = None) -> str:
    return await generate_once(system_prompt, user_prompt, model)


async def generate_once_with_history(system_prompt: str, messages: list[dict], model: str | None = None) -> str:
    normalized = [
        {"role": item.get("role", "user"), "content": item.get("content", "")}
        for item in messages
        if isinstance(item, dict)
    ]
    result = await model_gateway.chat_completion(
        [{"role": "system", "content": system_prompt}] + normalized,
        model=model,
    )
    return result.content


async def stream_generate_with_history(system_prompt: str, messages: list[dict], model: str | None = None) -> AsyncGenerator[str, None]:
    # Compatibility shim only. Product policy is non-streaming AI.
    yield await generate_once_with_history(system_prompt, messages, model)
