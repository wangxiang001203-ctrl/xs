from __future__ import annotations

from dataclasses import dataclass
from typing import Any, AsyncGenerator

import httpx

from app.config import get_settings
from app.services.workflow_config_service import get_active_model_config


settings = get_settings()


@dataclass(frozen=True)
class ModelRuntime:
    provider_id: str
    provider_name: str
    api_base: str
    api_key: str
    api_key_name: str
    model_id: str
    model_name: str


@dataclass
class GatewayResponse:
    content: str
    provider_id: str
    model_id: str
    raw: dict[str, Any]


def _timeout() -> httpx.Timeout:
    read_timeout = float(max(settings.ai_timeout_seconds, 60))
    return httpx.Timeout(connect=20.0, read=read_timeout, write=60.0, pool=60.0)


def resolve_runtime(model: str | None = None) -> ModelRuntime:
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
    return ModelRuntime(
        provider_id=provider.get("id") or "provider",
        provider_name=provider.get("name") or provider.get("id") or "提供商",
        api_base=api_base.rstrip("/"),
        api_key=api_key,
        api_key_name=api_key_source,
        model_id=model_id,
        model_name=model_info.get("name") or model_id,
    )


def runtime_descriptor(model: str | None = None) -> dict[str, str]:
    runtime = resolve_runtime(model)
    return {
        "provider_id": runtime.provider_id,
        "provider_name": runtime.provider_name,
        "model_id": runtime.model_id,
        "model_name": runtime.model_name,
    }


def _headers(runtime: ModelRuntime) -> dict[str, str]:
    return {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {runtime.api_key}",
    }


async def chat_completion(
    messages: list[dict[str, str]],
    *,
    model: str | None = None,
    temperature: float = 0.7,
    max_tokens: int = 4096,
    response_format: dict[str, Any] | None = None,
) -> GatewayResponse:
    runtime = resolve_runtime(model)
    payload: dict[str, Any] = {
        "model": runtime.model_id,
        "messages": messages,
        "stream": False,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    if response_format:
        payload["response_format"] = response_format

    async with httpx.AsyncClient(timeout=_timeout()) as client:
        resp = await client.post(f"{runtime.api_base}/chat/completions", headers=_headers(runtime), json=payload)
        if response_format and resp.status_code in {400, 422}:
            # Some OpenAI-compatible providers do not support response_format yet.
            # Keep the gateway provider-agnostic by retrying without that hint.
            payload.pop("response_format", None)
            resp = await client.post(f"{runtime.api_base}/chat/completions", headers=_headers(runtime), json=payload)
        resp.raise_for_status()
        data = resp.json()
    return GatewayResponse(
        content=data["choices"][0]["message"].get("content") or "",
        provider_id=runtime.provider_id,
        model_id=runtime.model_id,
        raw=data,
    )


async def generate_once(
    system_prompt: str,
    user_prompt: str,
    *,
    model: str | None = None,
    temperature: float = 0.7,
    max_tokens: int = 4096,
    response_format: dict[str, Any] | None = None,
) -> str:
    result = await chat_completion(
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        response_format=response_format,
    )
    return result.content


async def stream_chat_completion(
    messages: list[dict[str, str]],
    *,
    model: str | None = None,
    temperature: float = 0.7,
    max_tokens: int = 4096,
) -> AsyncGenerator[str, None]:
    runtime = resolve_runtime(model)
    payload = {
        "model": runtime.model_id,
        "messages": messages,
        "stream": True,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    async with httpx.AsyncClient(timeout=_timeout()) as client:
        async with client.stream("POST", f"{runtime.api_base}/chat/completions", headers=_headers(runtime), json=payload) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line.startswith("data:"):
                    continue
                raw = line[5:].strip()
                if raw == "[DONE]":
                    break
                try:
                    import json

                    chunk = json.loads(raw)
                    delta = chunk["choices"][0]["delta"]
                    text = delta.get("content") or ""
                    if text:
                        yield text
                except Exception:
                    continue
