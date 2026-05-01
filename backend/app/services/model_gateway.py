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
    api_type: str
    model_id: str
    model_name: str
    tools: list[dict[str, Any]] | None = None


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
    api_type = model_info.get("api_type") or provider.get("api_type") or "openai_compatible"
    tools = model_info.get("tools") if isinstance(model_info.get("tools"), list) else None
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
        api_type=api_type,
        model_id=model_id,
        model_name=model_info.get("name") or model_id,
        tools=tools,
    )


def runtime_descriptor(model: str | None = None) -> dict[str, str]:
    runtime = resolve_runtime(model)
    return {
        "provider_id": runtime.provider_id,
        "provider_name": runtime.provider_name,
        "model_id": runtime.model_id,
        "model_name": runtime.model_name,
        "api_type": runtime.api_type,
    }


def _headers(runtime: ModelRuntime) -> dict[str, str]:
    return {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {runtime.api_key}",
    }


def _message_text(message: dict[str, Any]) -> str:
    content = message.get("content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text = item.get("text") or item.get("content")
                if text:
                    parts.append(str(text))
        return "\n".join(parts)
    return str(content or "")


def _responses_input(messages: list[dict[str, str]], *, inline_system: bool = False) -> tuple[list[dict[str, Any]], str]:
    instructions: list[str] = []
    input_items: list[dict[str, Any]] = []
    for message in messages:
        role = message.get("role") or "user"
        text = _message_text(message).strip()
        if not text:
            continue
        if role == "system":
            instructions.append(text)
            continue
        input_items.append({
            "role": "assistant" if role == "assistant" else "user",
            "content": [{"type": "input_text", "text": text}],
        })

    instruction_text = "\n\n".join(instructions).strip()
    if inline_system and instruction_text:
        if input_items:
            first_content = input_items[0].setdefault("content", [])
            if first_content and isinstance(first_content[0], dict):
                first_content[0]["text"] = f"{instruction_text}\n\n{first_content[0].get('text') or ''}".strip()
        else:
            input_items.append({
                "role": "user",
                "content": [{"type": "input_text", "text": instruction_text}],
            })
        instruction_text = ""

    if not input_items:
        input_items.append({
            "role": "user",
            "content": [{"type": "input_text", "text": instruction_text or "请继续。"}],
        })
        instruction_text = "" if instruction_text else instruction_text
    return input_items, instruction_text


def _responses_payload(
    runtime: ModelRuntime,
    messages: list[dict[str, str]],
    *,
    temperature: float,
    max_tokens: int,
    inline_system: bool = False,
) -> dict[str, Any]:
    input_items, instructions = _responses_input(messages, inline_system=inline_system)
    payload: dict[str, Any] = {
        "model": runtime.model_id,
        "stream": False,
        "input": input_items,
        "max_output_tokens": max_tokens,
        "temperature": temperature,
    }
    if instructions:
        payload["instructions"] = instructions
    if runtime.tools:
        payload["tools"] = runtime.tools
    return payload


def _extract_responses_text(data: dict[str, Any]) -> str:
    if isinstance(data.get("output_text"), str):
        return data["output_text"]
    if isinstance(data.get("choices"), list) and data["choices"]:
        message = data["choices"][0].get("message") or {}
        if isinstance(message.get("content"), str):
            return message["content"]

    parts: list[str] = []
    for output in data.get("output") or []:
        if not isinstance(output, dict):
            continue
        content = output.get("content")
        if isinstance(content, str):
            parts.append(content)
            continue
        if not isinstance(content, list):
            continue
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str):
                    parts.append(text)
    return "\n".join(part for part in parts if part).strip()


async def responses_completion(
    messages: list[dict[str, str]],
    *,
    model: str | None = None,
    temperature: float = 0.7,
    max_tokens: int = 4096,
) -> GatewayResponse:
    runtime = resolve_runtime(model)
    payload = _responses_payload(
        runtime,
        messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )

    async with httpx.AsyncClient(timeout=_timeout()) as client:
        url = f"{runtime.api_base}/responses"
        resp = await client.post(url, headers=_headers(runtime), json=payload)
        
        if resp.status_code in {400, 422} and payload.get("instructions"):
            payload = _responses_payload(
                runtime,
                messages,
                temperature=temperature,
                max_tokens=max_tokens,
                inline_system=True,
            )
            resp = await client.post(url, headers=_headers(runtime), json=payload)
            
        if resp.status_code in {400, 422} and ("temperature" in payload or "max_output_tokens" in payload):
            payload.pop("temperature", None)
            payload.pop("max_output_tokens", None)
            resp = await client.post(url, headers=_headers(runtime), json=payload)
            
        resp.raise_for_status()
        data = resp.json()

    return GatewayResponse(
        content=_extract_responses_text(data),
        provider_id=runtime.provider_id,
        model_id=runtime.model_id,
        raw=data,
    )


async def chat_completion(
    messages: list[dict[str, str]],
    *,
    model: str | None = None,
    temperature: float = 0.7,
    max_tokens: int = 4096,
    response_format: dict[str, Any] | None = None,
) -> GatewayResponse:
    runtime = resolve_runtime(model)
    if runtime.api_type in {"ark_responses", "responses"}:
        return await responses_completion(
            messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )

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
    # Compatibility shim only. The product uses job polling and non-streaming
    # model calls so every AI path has a single complete response to audit.
    result = await chat_completion(
        messages,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    yield result.content
