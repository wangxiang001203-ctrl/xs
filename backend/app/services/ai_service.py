"""
豆包（火山方舟）AI服务封装
支持流式SSE输出，自动过滤思考链 reasoning_content
"""
import json
from typing import AsyncGenerator
import httpx
from app.config import get_settings
from app.services.workflow_config_service import get_active_model_config

settings = get_settings()


def _timeout() -> httpx.Timeout:
    read_timeout = float(max(settings.ai_timeout_seconds, 60))
    return httpx.Timeout(connect=20.0, read=read_timeout, write=60.0, pool=60.0)


def _resolve_runtime(model: str | None = None) -> tuple[str, str, str]:
    active = get_active_model_config()
    provider = active["provider"] or {}
    model_info = active["model"] or {}
    api_base = provider.get("api_base") or "https://ark.cn-beijing.volces.com/api/v3"
    model_id = model or model_info.get("id") or "ep-20260423202015-mbc68"
    api_key_source = provider.get("api_key_source") or "ark_api_key"
    api_key = getattr(settings, api_key_source, "") or settings.ark_api_key
    if not api_key:
        provider_name = provider.get("name") or provider.get("id") or "当前提供商"
        env_var_name = str(api_key_source).upper()
        raise RuntimeError(
            f"{provider_name} API Key 未配置，请先配置 {env_var_name}（推荐写入 backend/.env，根目录 .env 也兼容）"
        )
    return api_base, model_id, api_key


async def stream_generate(system_prompt: str, user_prompt: str, model: str | None = None) -> AsyncGenerator[str, None]:
    """流式生成，yield每个正文文本片段（过滤思考链）"""
    api_base, model_id, api_key = _resolve_runtime(model)
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    payload = {
        "model": model_id,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "stream": True,
        "max_tokens": 4096,
        "temperature": 0.7,
    }
    async with httpx.AsyncClient(timeout=_timeout()) as client:
        async with client.stream("POST", f"{api_base}/chat/completions", headers=headers, json=payload) as resp:
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


async def generate_once(system_prompt: str, user_prompt: str, model: str | None = None) -> str:
    """非流式，返回完整正文"""
    api_base, model_id, api_key = _resolve_runtime(model)
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    payload = {
        "model": model_id,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "stream": False,
        "max_tokens": 4096,
        "temperature": 0.7,
    }
    async with httpx.AsyncClient(timeout=_timeout()) as client:
        resp = await client.post(f"{api_base}/chat/completions", headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"].get("content") or ""


async def generate(system_prompt: str, user_prompt: str, model: str | None = None) -> str:
    """兼容旧调用名，统一走非流式生成。"""
    return await generate_once(system_prompt, user_prompt, model)


async def stream_generate_with_history(system_prompt: str, messages: list[dict], model: str | None = None) -> AsyncGenerator[str, None]:
    """多轮对话流式生成（用于AI对话框）"""
    api_base, model_id, api_key = _resolve_runtime(model)
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    payload = {
        "model": model_id,
        "messages": [{"role": "system", "content": system_prompt}] + messages,
        "stream": True,
        "max_tokens": 4096,
        "temperature": 0.7,
    }
    async with httpx.AsyncClient(timeout=_timeout()) as client:
        async with client.stream("POST", f"{api_base}/chat/completions", headers=headers, json=payload) as resp:
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
