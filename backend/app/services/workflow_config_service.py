import json
from pathlib import Path
from typing import Any

from app.config import get_settings

settings = get_settings()

KNOWN_MODEL_LABELS = {
    # 豆包（字节跳动）
    "ep-20260423202015-mbc68": "Doubao-1.5-lite-32k",
    "ep-20260421221056-qvrjw": "Doubao-Seed-2.0-pro",
    "ep-20260430223827-rncs2": "DeepSeek-V3.2（火山 Ark Responses）",
    
    # OpenAI（2025最新）
    "gpt-5.5": "GPT-5.5",
    "gpt-5": "GPT-5",
    "gpt-4-turbo": "GPT-4 Turbo",
    "gpt-4o": "GPT-4o",
    "gpt-4o-mini": "GPT-4o Mini",
    "gpt-3.5-turbo": "GPT-3.5 Turbo",
    
    # Anthropic Claude（2025最新）
    "claude-4.7": "Claude 4.7",
    "claude-4": "Claude 4",
    "claude-3-5-sonnet-20241022": "Claude 3.5 Sonnet",
    "claude-3-opus-20240229": "Claude 3 Opus",
    "claude-3-sonnet-20240229": "Claude 3 Sonnet",
    "claude-3-haiku-20240307": "Claude 3 Haiku",
    
    # Google Gemini（2025最新）
    "gemini-3.1-pro": "Gemini 3.1 Pro",
    "gemini-3-pro": "Gemini 3 Pro",
    "gemini-2-ultra": "Gemini 2 Ultra",
    "gemini-1.5-pro": "Gemini 1.5 Pro",
    "gemini-1.5-flash": "Gemini 1.5 Flash",
    
    # 通义千问（阿里）
    "qwen-max": "通义千问 Max",
    "qwen-plus": "通义千问 Plus",
    "qwen-turbo": "通义千问 Turbo",
    
    # 文心一言（百度）
    "ernie-4.0": "文心一言 4.0",
    "ernie-3.5": "文心一言 3.5",
    "ernie-turbo": "文心一言 Turbo",
    
    # 智谱AI（清华）
    "glm-4": "智谱 GLM-4",
    "glm-4-plus": "智谱 GLM-4 Plus",
    "glm-3-turbo": "智谱 GLM-3 Turbo",
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
            "重点：书名草案、简介草案、读者卖点、主角与核心角色、世界观种子、分卷推进、总字数与分卷字数分配。\n"
            "如果当前作品名是默认占位名，不要参考作品名，只根据作者输入的想法生成。"
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
        "active_model": "ep-20260430223827-rncs2",
        "providers": [
            # 国内模型
            {
                "id": "doubao",
                "name": "豆包（字节跳动）",
                "region": "china",
                "api_base": "https://ark.cn-beijing.volces.com/api/v3",
                "api_key_source": "ark_api_key",
                "api_type": "openai_compatible",
                "models": [
                    {"id": "ep-20260423202015-mbc68", "name": "Doubao-1.5-lite-32k", "context_length": 32000},
                    {"id": "ep-20260421221056-qvrjw", "name": "Doubao-Seed-2.0-pro", "context_length": 32000},
                    {
                        "id": "ep-20260430223827-rncs2",
                        "name": "DeepSeek-V3.2（火山 Ark Responses）",
                        "context_length": 128000,
                        "api_type": "ark_responses",
                        "tools": [{"type": "web_search", "max_keyword": 3}],
                    },
                ],
            },
            {
                "id": "qwen",
                "name": "通义千问（阿里）",
                "region": "china",
                "api_base": "https://dashscope.aliyuncs.com/compatible-mode/v1",
                "api_key_source": "qwen_api_key",
                "api_type": "openai_compatible",
                "models": [
                    {"id": "qwen-max", "name": "通义千问 Max", "context_length": 30000},
                    {"id": "qwen-plus", "name": "通义千问 Plus", "context_length": 30000},
                    {"id": "qwen-turbo", "name": "通义千问 Turbo", "context_length": 8000},
                ],
            },
            {
                "id": "ernie",
                "name": "文心一言（百度）",
                "region": "china",
                "api_base": "https://aip.baidubce.com/rpc/2.0/ai_custom/v1/wenxinworkshop/chat",
                "api_key_source": "ernie_api_key",
                "api_type": "ernie",
                "models": [
                    {"id": "ernie-4.0", "name": "文心一言 4.0", "context_length": 20000},
                    {"id": "ernie-3.5", "name": "文心一言 3.5", "context_length": 20000},
                    {"id": "ernie-turbo", "name": "文心一言 Turbo", "context_length": 11200},
                ],
            },
            {
                "id": "zhipu",
                "name": "智谱AI（清华）",
                "region": "china",
                "api_base": "https://open.bigmodel.cn/api/paas/v4",
                "api_key_source": "zhipu_api_key",
                "api_type": "openai_compatible",
                "models": [
                    {"id": "glm-4", "name": "智谱 GLM-4", "context_length": 128000},
                    {"id": "glm-4-plus", "name": "智谱 GLM-4 Plus", "context_length": 128000},
                    {"id": "glm-3-turbo", "name": "智谱 GLM-3 Turbo", "context_length": 128000},
                ],
            },
            
            # 国外模型
            {
                "id": "openai",
                "name": "OpenAI",
                "region": "global",
                "api_base": "https://api.openai.com/v1",
                "api_key_source": "openai_api_key",
                "api_type": "openai_compatible",
                "models": [
                    {"id": "gpt-4-turbo", "name": "GPT-4 Turbo", "context_length": 128000},
                    {"id": "gpt-4o", "name": "GPT-4o", "context_length": 128000},
                    {"id": "gpt-4o-mini", "name": "GPT-4o Mini", "context_length": 128000},
                    {"id": "gpt-3.5-turbo", "name": "GPT-3.5 Turbo", "context_length": 16000},
                ],
            },
            {
                "id": "anthropic",
                "name": "Anthropic Claude",
                "region": "global",
                "api_base": "https://api.anthropic.com/v1",
                "api_key_source": "anthropic_api_key",
                "api_type": "anthropic",
                "models": [
                    {"id": "claude-3-5-sonnet-20241022", "name": "Claude 3.5 Sonnet", "context_length": 200000},
                    {"id": "claude-3-opus-20240229", "name": "Claude 3 Opus", "context_length": 200000},
                    {"id": "claude-3-sonnet-20240229", "name": "Claude 3 Sonnet", "context_length": 200000},
                    {"id": "claude-3-haiku-20240307", "name": "Claude 3 Haiku", "context_length": 200000},
                ],
            },
            {
                "id": "google",
                "name": "Google Gemini",
                "region": "global",
                "api_base": "https://generativelanguage.googleapis.com/v1beta",
                "api_key_source": "google_api_key",
                "api_type": "google",
                "models": [
                    {"id": "gemini-1.5-pro", "name": "Gemini 1.5 Pro", "context_length": 1000000},
                    {"id": "gemini-1.5-flash", "name": "Gemini 1.5 Flash", "context_length": 1000000},
                    {"id": "gemini-pro", "name": "Gemini Pro", "context_length": 32000},
                ],
            },
        ],
    },
    "assistant_policy": {
        "agent_engine": {
            "runtime": "langgraph_optional",
            "model_gateway": "openai_compatible",
            "structured_output": "pydantic_with_repair",
            "memory_source": "project_owned_files",
        },
        "require_approval_before_write": True,
        "allow_delete": False,
        "default_read_kinds": {
            "outline": ["outline"],
            "worldbuilding": ["outline", "characters", "worldbuilding", "worldbuilding_section"],
            "chapter": ["chapter_synopsis", "chapter_content", "chapter_memory", "characters", "worldbuilding", "worldbuilding_section", "volume"],
        },
        "default_write_targets": {
            "outline": ["outline_draft"],
            "worldbuilding": ["current_worldbuilding_section_draft"],
            "chapter": ["chapter_content_draft", "entity_proposals", "chapter_memory_after_approval"],
        },
        "after_final_chapter_updates": [
            "chapter_memory",
            "entity_mentions",
            "character_state_events",
            "item_ownership_events",
            "open_threads",
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
                "api_type": item.get("api_type") or "openai_compatible",
                "models": [
                    {
                        "id": model.get("id") or "",
                        "name": KNOWN_MODEL_LABELS.get(
                            model.get("id") or "",
                            model.get("name") or model.get("id") or "模型",
                        ),
                        **({"api_type": model.get("api_type")} if model.get("api_type") else {}),
                        **({"tools": model.get("tools")} if isinstance(model.get("tools"), list) else {}),
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
        "assistant_policy": data.get("assistant_policy") or DEFAULT_CONFIG["assistant_policy"],
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
