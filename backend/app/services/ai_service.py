"""
豆包（火山方舟）AI服务封装
支持流式SSE输出，自动过滤思考链 reasoning_content
"""
import json
from typing import AsyncGenerator
import httpx
from app.config import get_settings

settings = get_settings()

ARK_BASE = "https://ark.cn-beijing.volces.com/api/v3"
DEFAULT_MODEL = "ep-20260421221056-qvrjw"


async def stream_generate(system_prompt: str, user_prompt: str, model: str = DEFAULT_MODEL) -> AsyncGenerator[str, None]:
    """流式生成，yield每个正文文本片段（过滤思考链）"""
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {settings.ark_api_key}",
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "stream": True,
        "max_tokens": 4096,
        "temperature": 0.7,
    }
    async with httpx.AsyncClient(timeout=120) as client:
        async with client.stream("POST", f"{ARK_BASE}/chat/completions", headers=headers, json=payload) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line.startswith("data:"):
                    continue
                raw = line[5:].strip()
                if raw == "[DONE]":
                    break
                try:
                    chunk = json.loads(raw)
                    delta = chunk["choices"][0]["delta"]
                    # 只输出正文，跳过思考链
                    text = delta.get("content") or ""
                    if text:
                        yield text
                except Exception:
                    continue


async def generate_once(system_prompt: str, user_prompt: str, model: str = DEFAULT_MODEL) -> str:
    """非流式，返回完整正文"""
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {settings.ark_api_key}",
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "stream": False,
        "max_tokens": 4096,
        "temperature": 0.7,
    }
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(f"{ARK_BASE}/chat/completions", headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"].get("content") or ""


async def stream_generate_with_history(system_prompt: str, messages: list[dict], model: str = DEFAULT_MODEL) -> AsyncGenerator[str, None]:
    """多轮对话流式生成（用于AI对话框）"""
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {settings.ark_api_key}",
    }
    payload = {
        "model": model,
        "messages": [{"role": "system", "content": system_prompt}] + messages,
        "stream": True,
        "max_tokens": 4096,
        "temperature": 0.7,
    }
    async with httpx.AsyncClient(timeout=120) as client:
        async with client.stream("POST", f"{ARK_BASE}/chat/completions", headers=headers, json=payload) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line.startswith("data:"):
                    continue
                raw = line[5:].strip()
                if raw == "[DONE]":
                    break
                try:
                    chunk = json.loads(raw)
                    delta = chunk["choices"][0]["delta"]
                    text = delta.get("content") or ""
                    if text:
                        yield text
                except Exception:
                    continue

