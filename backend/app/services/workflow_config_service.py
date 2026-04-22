import json
from pathlib import Path
from typing import Any

from app.config import get_settings

settings = get_settings()


DEFAULT_CONFIG: dict[str, Any] = {
    "flow": [
        {"id": "idea", "name": "输入创意", "next": "outline"},
        {"id": "outline", "name": "生成大纲", "next": "outline_confirm"},
        {"id": "outline_confirm", "name": "确认大纲", "next": "titles"},
        {"id": "titles", "name": "生成标题(10选1)", "next": "synopsis"},
        {"id": "synopsis", "name": "生成简介", "next": "characters"},
        {"id": "characters", "name": "角色设定", "next": "worldbuilding"},
        {"id": "worldbuilding", "name": "世界观设定", "next": "chapters"},
        {"id": "chapters", "name": "章节创作", "next": ""},
    ],
    "prompts": {
        "global_system": "你是一位专业的玄幻/修仙小说作家，擅长构建宏大世界观、塑造鲜明人物、编写引人入胜的剧情。",
        "outline_generation": (
            "你是一位专业的玄幻/修仙小说策划编辑。请根据用户创意生成完整小说大纲。\n"
            "要求包含：故事背景、主角设定、核心矛盾、分阶段规划、关键事件、字数规模。"
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
}


def _config_path() -> Path:
    return Path(settings.storage_path) / "_system" / "workflow_config.json"


def get_workflow_config() -> dict[str, Any]:
    path = _config_path()
    if not path.exists():
        return DEFAULT_CONFIG
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return DEFAULT_CONFIG


def save_workflow_config(data: dict[str, Any]) -> dict[str, Any]:
    path = _config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return data

