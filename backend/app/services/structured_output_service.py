from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from app.services import model_gateway


T = TypeVar("T", bound=BaseModel)


class StructuredOutputError(RuntimeError):
    def __init__(self, message: str, *, raw: str = "", attempts: int = 0):
        super().__init__(message)
        self.raw = raw
        self.attempts = attempts


@dataclass
class StructuredResult:
    value: BaseModel
    raw: str
    attempts: int


def extract_json_text(text: str) -> str:
    raw = (text or "").strip()
    if not raw:
        return ""
    fenced = re.search(r"```(?:json)?\s*(\{.*?\}|\[.*?\])\s*```", raw, re.S | re.I)
    if fenced:
        return fenced.group(1).strip()
    starts = [index for index in [raw.find("{"), raw.find("[")] if index >= 0]
    if not starts:
        return raw
    start = min(starts)
    end_obj = raw.rfind("}")
    end_arr = raw.rfind("]")
    end = max(end_obj, end_arr)
    return raw[start:end + 1].strip() if end > start else raw[start:].strip()


def parse_model(model_cls: type[T], raw: str) -> T:
    json_text = extract_json_text(raw)
    parsed = json.loads(json_text)
    return model_cls.model_validate(parsed)


def json_schema_hint(model_cls: type[BaseModel]) -> str:
    return json.dumps(model_cls.model_json_schema(), ensure_ascii=False, indent=2)


async def generate_structured(
    model_cls: type[T],
    *,
    system_prompt: str,
    user_prompt: str,
    repair_context: str = "",
    max_retries: int = 3,
    temperature: float = 0.2,
) -> tuple[T, dict[str, Any]]:
    """Generate and validate structured JSON.

    The first call asks for JSON directly. If the model emits fenced JSON,
    broken keys, or extra prose, we run a repair pass up to max_retries.
    """

    schema = json_schema_hint(model_cls)
    strict_system = f"""{system_prompt}

你必须只输出一个可解析 JSON，不要 Markdown，不要解释。
JSON 必须符合这个 schema：
{schema}
"""
    raw = await model_gateway.generate_once(
        strict_system,
        user_prompt,
        temperature=temperature,
        response_format={"type": "json_object"},
    )
    last_error = ""

    for attempt in range(1, max_retries + 1):
        try:
            return parse_model(model_cls, raw), {"raw": raw, "attempts": attempt}
        except (json.JSONDecodeError, ValidationError, TypeError, ValueError) as exc:
            last_error = str(exc)
            if attempt >= max_retries:
                break
            repair_prompt = f"""
下面是 AI 输出的内容，但它不是合法 JSON 或不符合 schema。请只修复格式和字段，不要新增事实。

schema:
{schema}

错误：
{last_error}

上下文：
{repair_context or "无"}

原始输出：
{raw}
"""
            raw = await model_gateway.generate_once(
                "你是 JSON 修复器。只能输出合法 JSON，不要 Markdown，不要解释。",
                repair_prompt,
                temperature=0,
                response_format={"type": "json_object"},
            )

    preview = extract_json_text(raw)[:800]
    raise StructuredOutputError(
        f"AI 返回内容连续 {max_retries} 次无法解析，已停止写入。请调整提示或换模型后重试。",
        raw=f"最后错误：{last_error}\n\n最后输出：\n{preview}",
        attempts=max_retries,
    )
