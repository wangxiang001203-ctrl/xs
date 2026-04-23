import json
from pathlib import Path
from typing import Any

from app.config import get_settings

settings = get_settings()

KNOWN_MODEL_LABELS = {
    "ep-20260423202015-mbc68": "Doubao-1.5-lite-32k",
    "ep-20260421221056-qvrjw": "Doubao-Seed-2.0-pro",
}


DEFAULT_CONFIG: dict[str, Any] = {
    "flow": [
        {"id": "idea", "name": "输入创意", "next": "outline"},
        {"id": "outline", "name": "生成大纲", "next": "outline_confirm"},
        {"id": "outline_confirm", "name": "确认大纲", "next": "characters"},
        {"id": "characters", "name": "角色设定", "next": "worldbuilding"},
        {"id": "worldbuilding", "name": "世界观设定", "next": "chapters"},
        {"id": "chapters", "name": "章节创作", "next": ""},
    ],
    "prompts": {
        "global_system": "你是一位专业的玄幻/修仙小说作家，擅长构建宏大世界观、塑造鲜明人物、编写引人入胜的剧情。",
        "outline_generation": (
            "你是一位资深玄幻修仙编辑，请输出可直接用于立项和连载的完整小说企划。\n"
            "重点：书名草案、简介草案、读者卖点、主角与核心角色、世界观种子、分卷推进、总字数与分卷字数分配。"
        ),
        "titles_generation": (
            "你是一位网文编辑。请基于已确认大纲输出10个中文书名候选。\n"
            "要求网文感强、辨识度高、避免雷同。输出JSON数组。"
        ),
        "book_synopsis_generation": (
            "你是一位网文运营编辑。请基于已确认大纲生成小说简介。\n"
            "要求100-180字，强调主角、核心冲突和爽点。"
        ),
    },
    "model_config": {
        "active_provider": "doubao",
        "active_model": "ep-20260423202015-mbc68",
        "providers": [
            {
                "id": "doubao",
                "name": "豆包",
                "api_base": "https://ark.cn-beijing.volces.com/api/v3",
                "api_key_source": "ark_api_key",
                "models": [
                    {"id": "ep-20260423202015-mbc68", "name": KNOWN_MODEL_LABELS["ep-20260423202015-mbc68"]},
                    {"id": "ep-20260421221056-qvrjw", "name": KNOWN_MODEL_LABELS["ep-20260421221056-qvrjw"]},
                ],
            }
        ],
    },
}


def _config_path() -> Path:
    return Path(settings.storage_path) / "_system" / "workflow_config.json"


def get_workflow_config() -> dict[str, Any]:
    path = _config_path()
    if not path.exists():
        return DEFAULT_CONFIG
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return _normalize_config(data)
    except Exception:
        return DEFAULT_CONFIG


def save_workflow_config(data: dict[str, Any]) -> dict[str, Any]:
    path = _config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    normalized = _normalize_config(data)
    path.write_text(json.dumps(normalized, ensure_ascii=False, indent=2), encoding="utf-8")
    return normalized


def _normalize_model_config(data: dict[str, Any] | None) -> dict[str, Any]:
    default_model_config = DEFAULT_CONFIG["model_config"]
    incoming = data or {}
    providers = incoming.get("providers")
    if not isinstance(providers, list) or not providers:
        providers = default_model_config["providers"]

    normalized_providers: list[dict[str, Any]] = []
    for item in providers:
        if not isinstance(item, dict):
            continue
        models = item.get("models")
        if not isinstance(models, list) or not models:
            continue
        normalized_providers.append(
            {
                "id": item.get("id") or "provider",
                "name": item.get("name") or item.get("id") or "提供商",
                "api_base": item.get("api_base") or default_model_config["providers"][0]["api_base"],
                "api_key_source": item.get("api_key_source") or "ark_api_key",
                "models": [
                    {
                        "id": model.get("id") or "",
                        "name": KNOWN_MODEL_LABELS.get(
                            model.get("id") or "",
                            model.get("name") or model.get("id") or "模型",
                        ),
                    }
                    for model in models
                    if isinstance(model, dict) and model.get("id")
                ],
            }
        )

    if not normalized_providers:
        normalized_providers = default_model_config["providers"]

    active_provider = incoming.get("active_provider") or default_model_config["active_provider"]
    provider = next((item for item in normalized_providers if item["id"] == active_provider), normalized_providers[0])

    active_model = incoming.get("active_model") or default_model_config["active_model"]
    model = next((item for item in provider["models"] if item["id"] == active_model), provider["models"][0])

    return {
        "active_provider": provider["id"],
        "active_model": model["id"],
        "providers": normalized_providers,
    }


def _normalize_config(data: dict[str, Any]) -> dict[str, Any]:
    return {
        "flow": data.get("flow") or DEFAULT_CONFIG["flow"],
        "prompts": data.get("prompts") or DEFAULT_CONFIG["prompts"],
        "model_config": _normalize_model_config(data.get("model_config")),
    }


def get_active_model_config() -> dict[str, Any]:
    model_config = get_workflow_config()["model_config"]
    providers = model_config.get("providers") or DEFAULT_CONFIG["model_config"]["providers"]
    provider = next(
        (item for item in providers if item.get("id") == model_config.get("active_provider")),
        providers[0],
    )
    models = provider.get("models") or []
    model = next(
        (item for item in models if item.get("id") == model_config.get("active_model")),
        models[0],
    )
    return {
        "provider": provider,
        "model": model,
        "active_provider": provider.get("id"),
        "active_model": model.get("id"),
    }
