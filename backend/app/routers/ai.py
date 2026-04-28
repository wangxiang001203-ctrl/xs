import json
import re
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import SessionLocal, get_db
from app.models import AIGenerationJob, Character, Novel, ChapterMemory, EntityProposal, OutlineChatMessage
from app.models.chapter import Chapter
from app.models.project import Outline
from app.models.synopsis import Synopsis
from app.models.volume import Volume
from app.models.worldbuilding import Worldbuilding
from app.schemas.ai_job import AIGenerationJobOut
from app.schemas.ai_request import (
    ChatRequest,
    CreateMissingCharactersRequest,
    GenerateBookSynopsisRequest,
    GenerateBookVolumesRequest,
    GenerateChapterRequest,
    GenerateChapterSegmentRequest,
    GenerateCharactersFromOutlineRequest,
    GenerateOutlineRequest,
    OutlineChatRequest,
    GenerateSynopsisRequest,
    GenerateTitlesRequest,
    GenerateVolumeSynopsisRequest,
    GenerateWorldbuildingRequest,
    ValidateSynopsisRequest,
)
from app.schemas.chapter import ChapterContentOut, SynopsisOut
from app.schemas.character import CharacterOut
from app.schemas.project import OutlineOut
from app.schemas.worldbuilding import WorldbuildingOut
from app.services import ai_job_service, ai_service, context_builder
from app.services.assistant_service import build_smart_chat_context, clarification_for
from app.services.file_service import (
    save_book_meta,
    save_chapter_content,
    save_chapter_plot_summary,
    save_chapter_synopsis,
    save_characters,
    save_synopsis,
    save_volume_plan,
    save_worldbuilding,
)
from app.services.review_service import (
    build_chapter_memory,
    chapter_access_guard,
    save_all_proposals,
    serialize_proposal,
    validate_and_prepare_proposals,
)
from app.services.validator import validate_synopsis_characters
from app.services.workflow_config_service import get_workflow_config
from app.services.worldbuilding_service import (
    apply_worldbuilding_document,
    load_worldbuilding_document,
    merge_worldbuilding_documents,
    normalize_worldbuilding_document,
)

router = APIRouter(prefix="/api/ai", tags=["ai"])

SYSTEM_NOVEL = "你是一位专业的玄幻/修仙小说作家，擅长构建宏大世界观、塑造鲜明人物、编写引人入胜的剧情。"
DEFAULT_VOLUME_CHAPTER_COUNT = 12
MAX_OUTLINE_VERSIONS = 5
AI_JSON_REPAIR_ATTEMPTS = 3
VAGUE_OUTLINE_ACTION_RE = re.compile(
    r"^(?:请|麻烦)?(?:帮|给|替)?我?(?:写|生成|创建|做|弄|起草|出)(?:一下|一个|一份|个|份)?"
    r"(?:小说|故事|作品)?(?:的)?(?:大纲|故事大纲|作品大纲|小说大纲)(?:吧|呗|可以吗|行吗)?[。.!！?？]*$",
    re.I,
)
OUTLINE_DETAIL_RE = re.compile(
    r"(玄幻|修仙|都市|历史|科幻|末世|悬疑|言情|女频|男频|主角|男主|女主|反派|废柴|重生|穿越|系统|"
    r"金手指|宗门|女帝|复仇|升级|爽点|目标|万字|百万|字|主线|冲突|世界|背景|设定|开局|结局)"
)


def _prompt_config() -> dict[str, str]:
    config = get_workflow_config()
    prompts = config.get("prompts") or {}
    return {
        "global_system": prompts.get("global_system") or SYSTEM_NOVEL,
        "outline_generation": prompts.get("outline_generation") or "请生成完整小说大纲。",
        "titles_generation": prompts.get("titles_generation") or "请输出10个标题候选。",
        "book_synopsis_generation": prompts.get("book_synopsis_generation") or "请输出小说简介。",
    }


class AIJsonFormatError(Exception):
    def __init__(self, detail: dict[str, Any]):
        self.detail = detail
        super().__init__(detail.get("message") or "AI 输出格式异常")


def _strip_json_fence(text: str) -> str:
    stripped = (text or "").strip()
    stripped = re.sub(r"^```(?:json)?\s*", "", stripped, flags=re.I)
    stripped = re.sub(r"\s*```$", "", stripped)
    return stripped.strip()


def _extract_balanced_json(text: str) -> str:
    source = _strip_json_fence(text)
    starts = [(pos, char) for char in ("{", "[") if (pos := source.find(char)) != -1]
    if not starts:
        return source

    start, opening = min(starts, key=lambda item: item[0])
    closing = {"{": "}", "[": "]"}
    stack = [closing[opening]]
    in_string = False
    escaped = False

    for index in range(start + 1, len(source)):
        char = source[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
            continue
        if char in "{[":
            stack.append(closing[char])
            continue
        if stack and char == stack[-1]:
            stack.pop()
            if not stack:
                return source[start:index + 1].strip()

    # 没有闭合时也返回从第一个 JSON 起始符开始的内容，交给 repair/retry 处理。
    return source[start:].strip()


def _extract_json(text: str):
    m = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", text or "", flags=re.I)
    if m:
        return m.group(1).strip()
    return _extract_balanced_json(text or "")


def _repair_json_text(text: str) -> str:
    repaired = text.strip()
    # Common LLM typo: {"description): "xxx"} should be {"description": "xxx"}.
    repaired = re.sub(r'"([A-Za-z_][A-Za-z0-9_]*)\)\s*:\s*"', r'"\1": "', repaired)
    # Common markdown bleed: "chapter_count**: 12 or "**chapter_count**": 12.
    repaired = re.sub(r'"\*\*([A-Za-z_][A-Za-z0-9_]*)\*\*"\s*:', r'"\1":', repaired)
    repaired = re.sub(r'"([A-Za-z_][A-Za-z0-9_]*)\*+\s*:\s*', r'"\1": ', repaired)
    repaired = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", repaired)
    repaired = re.sub(r",\s*([}\]])", r"\1", repaired)
    return repaired


def _loads_json_with_repair(text: str):
    candidate = _extract_json(text)
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        repaired = _repair_json_text(candidate)
        if repaired == candidate:
            raise
        return json.loads(repaired)


def _json_error_context(text: str, error: json.JSONDecodeError | Exception) -> str:
    if isinstance(error, json.JSONDecodeError):
        return text[max(0, error.pos - 80):min(len(text), error.pos + 80)]
    return text[:160]


def _clip_raw_text(text: str, limit: int = 12000) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n\n……已截断，原始长度 {len(text)} 字符。"


def _build_ai_json_error_detail(
    *,
    label: str,
    attempts: list[dict[str, Any]],
    raw_text: str,
) -> dict[str, Any]:
    last = attempts[-1] if attempts else {}
    return {
        "message": f"{label}失败：AI 连续 {AI_JSON_REPAIR_ATTEMPTS} 次返回了无法解析的 JSON。请稍后重试，或切换更稳定的模型。",
        "reason": last.get("error") or "AI 输出不是合法 JSON",
        "attempts": attempts,
        "raw_excerpt": _clip_raw_text(raw_text, 1200),
        "raw_text": _clip_raw_text(raw_text),
    }


async def _loads_ai_json_with_retries(
    *,
    job_id: str,
    label: str,
    response_text: str,
    json_contract: str,
    expected_root: tuple[type, ...] = (dict,),
) -> Any:
    current_text = response_text or ""
    attempts: list[dict[str, Any]] = []
    if expected_root == (dict,):
        root_instruction = "一个合法 JSON 对象"
    elif expected_root == (list,):
        root_instruction = "一个合法 JSON 数组"
    else:
        root_instruction = "一个合法 JSON 对象或数组"

    for attempt in range(AI_JSON_REPAIR_ATTEMPTS + 1):
        json_text = _extract_json(current_text)
        try:
            data = _loads_json_with_repair(json_text)
            if not isinstance(data, expected_root):
                expected = " 或 ".join(item.__name__ for item in expected_root)
                raise AIJsonFormatError({
                    "message": f"{label}失败：AI 返回的 JSON 顶层必须是 {expected}。",
                    "reason": f"实际类型：{type(data).__name__}",
                    "attempts": attempts,
                    "raw_excerpt": _clip_raw_text(current_text, 1200),
                    "raw_text": _clip_raw_text(current_text),
                })
            return data
        except AIJsonFormatError:
            raise
        except json.JSONDecodeError as exc:
            attempts.append({
                "round": attempt + 1,
                "error": str(exc),
                "context": _json_error_context(json_text, exc),
            })
            if attempt >= AI_JSON_REPAIR_ATTEMPTS:
                raise AIJsonFormatError(_build_ai_json_error_detail(
                    label=label,
                    attempts=attempts,
                    raw_text=current_text,
                ))

            ai_job_service.update_partial(
                job_id,
                _clip_raw_text(current_text, 4000),
                f"AI 输出格式异常，正在自动修复 JSON（第 {attempt + 1}/{AI_JSON_REPAIR_ATTEMPTS} 次）...",
            )
            repair_prompt = f"""下面这段内容不是合法 JSON。请你只做格式修复，不要新增解释，不要使用 Markdown 代码块。

必须满足：
1. 只输出{root_instruction}。
2. 顶层和字段结构必须符合契约。
3. 保留原有中文内容，不能擅自删减剧情信息。
4. 不要输出 ```json，不要输出任何说明文字。

JSON 契约：
{json_contract}

解析错误：
{str(exc)}

待修复内容：
{current_text}
"""
            current_text = await ai_service.generate_once(
                "你是严格的 JSON 修复器，只输出合法 JSON。",
                repair_prompt,
            )

    raise AIJsonFormatError(_build_ai_json_error_detail(
        label=label,
        attempts=attempts,
        raw_text=current_text,
    ))


def _error_message_from_detail(detail: Any) -> str:
    if isinstance(detail, dict):
        return _safe_text(detail.get("message") or detail.get("reason"), "AI任务失败")
    return str(detail)


def _extract_requested_character_name(text: str) -> str:
    normalized = re.sub(r"\s+", "", text or "")
    patterns = [
        r"(?:创建|新增|加)(?:一个|一名|个)?(?:角色|人物)(?:叫|名叫|名为|名字叫|名称为)([\u4e00-\u9fa5A-Za-z0-9·]{2,16})",
        r"(?:角色|人物)(?:叫|名叫|名为|名字叫|名称为)([\u4e00-\u9fa5A-Za-z0-9·]{2,16})",
    ]
    for pattern in patterns:
        match = re.search(pattern, normalized)
        if match:
            return match.group(1).strip("，。,. ")
    return ""


def _role_from_text(text: str) -> str:
    for role in ["男主", "女主", "反派", "男配", "女配", "导师", "伙伴", "亲族", "路人"]:
        if role in text:
            return role
    return "未知"


def _chat_entity_proposal(db: Session, payload: dict) -> dict | None:
    user_message = _safe_text(payload.get("user_message"))
    wants_character = bool(re.search(r"(创建|新增|加).*(角色|人物)|(角色|人物).*(创建|新增|加)", user_message))
    if not wants_character:
        return None

    name = _extract_requested_character_name(user_message)
    if not name:
        return {
            "message": "可以，我先确认几个角色关键信息，确认后再生成待审阅角色卡。",
            "mode": "clarify",
            "questions": [
                {"question": "角色名字叫什么？", "options": ["先让 AI 起名", "我来输入名字", "沿用大纲里已有角色"]},
                {"question": "角色定位是什么？", "options": ["男主/女主", "反派", "伙伴", "路人/群像"]},
                {"question": "是否需要立刻入库？", "options": ["生成待确认卡片", "只给我文本参考"]},
            ],
            "context_files": [],
            "pending_proposals": [],
        }

    existing_pending = db.query(EntityProposal).filter(
        EntityProposal.novel_id == payload["novel_id"],
        EntityProposal.entity_type == "character",
        EntityProposal.entity_name == name,
        EntityProposal.status == "pending",
    ).first()
    if existing_pending:
        proposal = existing_pending
    else:
        existing_character = db.query(Character).filter(
            Character.novel_id == payload["novel_id"],
            Character.name == name,
        ).first()
        entry = {
            "name": name,
            "role": _role_from_text(user_message),
            "summary": "由 AI 对话创建的待确认角色卡。",
            "details": user_message,
            "source": "assistant_chat",
        }
        proposal = EntityProposal(
            novel_id=payload["novel_id"],
            chapter_id=payload.get("chapter_id") or None,
            volume_id=payload.get("volume_id") or None,
            entity_type="character",
            action="update" if existing_character else "create",
            entity_name=name,
            status="pending",
            reason="AI 根据对话识别到角色创建/更新意图，等待作者确认后才会写入角色库。",
            payload={
                "entry": entry,
                "before": {
                    "name": existing_character.name,
                    "role": existing_character.role,
                    "realm": existing_character.realm,
                    "faction": existing_character.faction,
                    "profile_md": existing_character.profile_md,
                } if existing_character else None,
                "after": entry,
            },
        )
        db.add(proposal)
        db.commit()
        db.refresh(proposal)
        save_all_proposals(db, payload["novel_id"])

    return {
        "message": f"已生成「{name}」的待确认角色卡。它现在只是提案，不会进入正式角色库；通过审批后才会写入。",
        "mode": "proposal",
        "context_files": [
            {"id": "characters", "label": "角色设定", "path": "characters/characters.json", "kind": "characters"}
        ],
        "changed_files": [
            {"id": "characters", "label": "角色设定", "path": "characters/characters.json", "kind": "characters", "status": "pending"}
        ],
        "pending_proposals": [serialize_proposal(proposal)],
    }


def _safe_text(value, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text or default


def _safe_int(value, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_list(value) -> list:
    if isinstance(value, list):
        return value
    return []


def _validate_outline_idea(idea: str, *, allow_short: bool = False) -> str:
    text = (idea or "").strip()
    normalized = re.sub(r"\s+", " ", text)
    hint = "先说说你想写什么类型的小说，比如：玄幻修仙、废柴逆袭、目标百万字、主线是复仇和登仙。"
    if len(normalized) < (2 if allow_short else 4):
        raise HTTPException(400, hint)
    if not re.search(r"[\u4e00-\u9fa5A-Za-z]", normalized):
        raise HTTPException(400, hint)
    if re.fullmatch(r"(你好|hi|hello|test|测试|随便|不知道|无|没有|写一个|小说)", normalized, flags=re.I):
        raise HTTPException(400, hint)
    if VAGUE_OUTLINE_ACTION_RE.fullmatch(normalized):
        raise HTTPException(400, hint)
    if len(normalized) <= 14 and re.search(r"(大纲|写|生成|创建|做|弄|起草)", normalized) and not OUTLINE_DETAIL_RE.search(normalized):
        raise HTTPException(400, hint)

    unsafe_patterns = [
        r"(教我|如何|怎么|教程|方法).*(制毒|炸药|爆炸|杀人|诈骗|盗号|恐袭|自杀)",
        r"(报复社会|恐怖袭击|炸学校|伤害现实|屠杀现实)",
    ]
    if any(re.search(pattern, normalized) for pattern in unsafe_patterns):
        raise HTTPException(400, "这个想法涉及现实伤害或反社会内容。可以改成纯虚构的修仙冲突、门派斗争或反派阴谋。")
    return normalized


def _outline_chat_payload(message: OutlineChatMessage) -> dict:
    metadata = {}
    if message.metadata_json:
        try:
            metadata = json.loads(message.metadata_json)
        except Exception:
            metadata = {}
    return {
        "id": message.id,
        "novel_id": message.novel_id,
        "outline_id": message.outline_id,
        "role": message.role,
        "content": message.content,
        "metadata": metadata,
        "created_at": message.created_at.isoformat() if message.created_at else None,
    }


def _add_outline_chat_message(
    db: Session,
    *,
    novel_id: str,
    role: str,
    content: str,
    outline_id: str | None = None,
    metadata: dict | None = None,
) -> OutlineChatMessage:
    message = OutlineChatMessage(
        novel_id=novel_id,
        outline_id=outline_id,
        role=role,
        content=content,
        metadata_json=json.dumps(metadata or {}, ensure_ascii=False),
    )
    db.add(message)
    db.commit()
    db.refresh(message)
    return message


def _normalize_outline_struct(payload: dict, genre: str) -> dict:
    outline_struct = payload.get("outline_struct") or {}
    protagonist = outline_struct.get("protagonist") or {}
    world_seed = outline_struct.get("world_seed") or {}

    volumes = []
    for index, item in enumerate(_safe_list(outline_struct.get("volumes")), start=1):
        volumes.append(
            {
                "volume_no": _safe_int(item.get("volume_no"), index),
                "title": _safe_text(item.get("title"), f"第{index}卷"),
                "target_words": _safe_int(item.get("target_words"), 30000),
                "chapter_count": _safe_int(item.get("chapter_count"), 12),
                "main_line": _safe_text(item.get("main_line"), "待补充"),
                "character_arc": _safe_text(item.get("character_arc"), "待补充"),
                "ending_hook": _safe_text(item.get("ending_hook"), "待补充"),
            }
        )
    if not volumes:
        volumes = [
            {
                "volume_no": 1,
                "title": "第一卷",
                "target_words": 30000,
                "chapter_count": 12,
                "main_line": "待补充",
                "character_arc": "待补充",
                "ending_hook": "待补充",
            }
        ]

    return {
        "genre": genre,
        "selling_points": [_safe_text(item) for item in _safe_list(outline_struct.get("selling_points")) if _safe_text(item)],
        "story_positioning": _safe_text(outline_struct.get("story_positioning")),
        "core_conflict": _safe_text(outline_struct.get("core_conflict")),
        "target_total_words": _safe_int(outline_struct.get("target_total_words"), sum(v["target_words"] for v in volumes)),
        "protagonist": {
            "name": _safe_text(protagonist.get("name"), "待定"),
            "background": _safe_text(protagonist.get("background"), "待补充"),
            "golden_finger": _safe_text(protagonist.get("golden_finger"), "待补充"),
            "motivation": _safe_text(protagonist.get("motivation"), "待补充"),
            "realm": _safe_text(protagonist.get("realm"), "待定"),
            "faction": _safe_text(protagonist.get("faction"), "待定"),
            "personality": _safe_text(protagonist.get("personality"), "待补充"),
        },
        "core_cast": [
            {
                "name": _safe_text(item.get("name"), f"角色{idx}"),
                "role": _safe_text(item.get("role"), "配角"),
                "personality": _safe_text(item.get("personality"), "待补充"),
                "background": _safe_text(item.get("background"), "待补充"),
                "golden_finger": _safe_text(item.get("golden_finger"), "无"),
                "motivation": _safe_text(item.get("motivation"), "待补充"),
                "realm": _safe_text(item.get("realm"), "待定"),
                "faction": _safe_text(item.get("faction"), "待定"),
            }
            for idx, item in enumerate(_safe_list(outline_struct.get("core_cast")), start=1)
            if _safe_text(item.get("name"))
        ],
        "world_seed": {
            "cultivation_system": _safe_list(world_seed.get("cultivation_system")),
            "major_factions": _safe_list(world_seed.get("major_factions")),
            "major_regions": _safe_list(world_seed.get("major_regions")),
            "core_rules": _safe_list(world_seed.get("core_rules")),
            "treasures": _safe_list(world_seed.get("treasures")),
        },
        "volumes": volumes,
    }


def _render_named_list(items: list[dict], name_key: str = "name", desc_key: str = "description") -> list[str]:
    lines: list[str] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        name = _safe_text(item.get(name_key))
        desc = _safe_text(item.get(desc_key))
        if not name and not desc:
            continue
        if name and desc:
            lines.append(f"· {name}：{desc}")
        else:
            lines.append(f"· {name or desc}")
    return lines


def _render_outline_markdown(title: str, synopsis: str, outline_struct: dict) -> str:
    protagonist = outline_struct.get("protagonist") or {}
    core_cast = outline_struct.get("core_cast") or []
    world_seed = outline_struct.get("world_seed") or {}
    selling_points = outline_struct.get("selling_points") or []
    volumes = outline_struct.get("volumes") or []

    parts = [title or "暂定书名", "", "【简介】", synopsis or "（待补充）", ""]

    parts.append("【核心卖点】")
    if selling_points:
        parts.extend([f"{index}. {item}" for index, item in enumerate(selling_points, start=1)])
    else:
        parts.append("（待补充）")
    parts.append("")

    parts.append("【故事定位】")
    parts.append(f"类型：{outline_struct.get('genre') or '玄幻修仙'}")
    parts.append(f"一句话定位：{outline_struct.get('story_positioning') or '待补充'}")
    parts.append(f"核心冲突：{outline_struct.get('core_conflict') or '待补充'}")
    parts.append(f"目标总字数：{outline_struct.get('target_total_words') or 0}")
    parts.append("")

    parts.append("【主角设定】")
    parts.append(f"姓名：{protagonist.get('name') or '待定'}")
    parts.append(f"出身背景：{protagonist.get('background') or '待补充'}")
    parts.append(f"金手指：{protagonist.get('golden_finger') or '待补充'}")
    parts.append(f"核心动机：{protagonist.get('motivation') or '待补充'}")
    parts.append(f"当前境界：{protagonist.get('realm') or '待定'}")
    parts.append(f"所属阵营：{protagonist.get('faction') or '待定'}")
    parts.append(f"性格基调：{protagonist.get('personality') or '待补充'}")
    parts.append("")

    parts.append("【核心角色】")
    if core_cast:
        for index, item in enumerate(core_cast, start=1):
            parts.append(f"{index}. {item.get('name') or '待定角色'}（{item.get('role') or '配角'}）")
            parts.append(f"   性格：{item.get('personality') or '待补充'}")
            parts.append(f"   背景：{item.get('background') or '待补充'}")
            parts.append(f"   金手指/特殊点：{item.get('golden_finger') or '无'}")
            parts.append(f"   动机：{item.get('motivation') or '待补充'}")
            parts.append(f"   境界：{item.get('realm') or '待定'}")
            parts.append(f"   阵营：{item.get('faction') or '待定'}")
            parts.append("")
    else:
        parts.append("（待补充）")
        parts.append("")

    parts.append("【世界观种子】")
    world_sections = [
        ("修炼体系", _render_named_list(world_seed.get("cultivation_system") or [])),
        ("主要势力", _render_named_list(world_seed.get("major_factions") or [], desc_key="description")),
        ("主要地域", _render_named_list(world_seed.get("major_regions") or [])),
        ("核心规则", _render_named_list(world_seed.get("core_rules") or [], name_key="rule_name", desc_key="description")),
        ("关键宝物", _render_named_list(world_seed.get("treasures") or [])),
    ]
    for section_name, lines in world_sections:
        parts.append(f"{section_name}：")
        parts.extend(lines or ["（待补充）"])
        parts.append("")

    parts.append("【分卷规划】")
    for item in volumes:
        parts.append(f"第{item.get('volume_no', 0)}卷：{item.get('title') or '待定卷名'}")
        parts.append(f"目标字数：{item.get('target_words') or 0}")
        parts.append(f"预计章节数：{item.get('chapter_count') or 0}")
        parts.append(f"本卷主线：{item.get('main_line') or '待补充'}")
        parts.append(f"人物成长：{item.get('character_arc') or '待补充'}")
        parts.append(f"卷末钩子：{item.get('ending_hook') or '待补充'}")
        parts.append("")

    return "\n".join(parts).strip()


def _serialize_outline(outline: Outline) -> dict:
    return OutlineOut.model_validate(outline).model_dump(mode="json")


def _serialize_characters(characters: list[Character]) -> list[dict]:
    return [CharacterOut.model_validate(item).model_dump(mode="json") for item in characters]


def _serialize_worldbuilding(worldbuilding: Worldbuilding) -> dict:
    return WorldbuildingOut.model_validate(
        load_worldbuilding_document(worldbuilding.novel_id, worldbuilding)
    ).model_dump(mode="json")


def _serialize_synopsis(synopsis: Synopsis) -> dict:
    return SynopsisOut.model_validate(synopsis).model_dump(mode="json")


def _serialize_chapter(chapter: Chapter) -> dict:
    return ChapterContentOut.model_validate(chapter).model_dump(mode="json")


def _book_plan_status(volume: Volume) -> str:
    plan_data = volume.plan_data or {}
    return _safe_text(plan_data.get("book_plan_status"), "draft")


def _single_volume_book_plan_markdown(volume: Volume) -> str:
    plan_data = volume.plan_data or {}
    saved = _safe_text(plan_data.get("book_plan_markdown"))
    if saved:
        return saved
    lines = [
        f"## 第{volume.volume_number}卷 {volume.title}",
        f"目标字数：{volume.target_words or 0}",
        f"预计章节数：{volume.planned_chapter_count or 0}",
    ]
    if volume.description:
        lines.append(f"本卷定位：{volume.description.strip()}")
    if volume.main_line:
        lines.append(f"本卷主线：{volume.main_line.strip()}")
    if volume.character_arc:
        lines.append(f"人物成长：{volume.character_arc.strip()}")
    if volume.ending_hook:
        lines.append(f"卷末钩子：{volume.ending_hook.strip()}")
    return "\n".join(lines).strip()


def _book_volume_plan_markdown(volumes: list[Volume]) -> str:
    if not volumes:
        return ""
    parts = ["# 全书分卷", "", "这份文档只定义整本书的卷级推进。章节细纲需要进入具体卷后单独生成和审批。", ""]
    for volume in sorted(volumes, key=lambda item: item.volume_number):
        parts.append(_single_volume_book_plan_markdown(volume))
        parts.append("")
    return "\n".join(parts).strip()


def _serialize_volume_for_plan(db: Session, volume: Volume) -> dict:
    count = db.query(Chapter).filter(Chapter.volume_id == volume.id).count()
    return {
        "id": volume.id,
        "novel_id": volume.novel_id,
        "volume_number": volume.volume_number,
        "title": volume.title,
        "description": volume.description,
        "target_words": volume.target_words or 0,
        "planned_chapter_count": volume.planned_chapter_count or count or 0,
        "main_line": volume.main_line,
        "character_arc": volume.character_arc,
        "ending_hook": volume.ending_hook,
        "plan_markdown": volume.plan_markdown,
        "plan_data": volume.plan_data or {},
        "synopsis_generated": bool(volume.synopsis_generated),
        "review_status": volume.review_status or "draft",
        "approved_at": volume.approved_at.isoformat() if volume.approved_at else None,
        "created_at": volume.created_at.isoformat() if volume.created_at else None,
        "chapter_count": count,
    }


def _serialize_memory(memory: ChapterMemory) -> dict:
    return {
        "id": memory.id,
        "novel_id": memory.novel_id,
        "chapter_id": memory.chapter_id,
        "chapter_number": memory.chapter_number,
        "summary": memory.summary,
        "key_events": memory.key_events or [],
        "state_changes": memory.state_changes or [],
        "inventory_changes": memory.inventory_changes or [],
        "proposed_entities": memory.proposed_entities or [],
        "open_threads": memory.open_threads or [],
        "source_excerpt": memory.source_excerpt,
        "created_at": memory.created_at,
        "updated_at": memory.updated_at,
    }


def _get_latest_outline(db: Session, novel_id: str, outline_id: str | None = None) -> Outline:
    if outline_id:
        outline = db.query(Outline).filter(Outline.id == outline_id, Outline.novel_id == novel_id).first()
    else:
        outline = db.query(Outline).filter(Outline.novel_id == novel_id).order_by(Outline.version.desc()).first()
    if not outline:
        raise HTTPException(400, "请先生成并保存大纲")
    return outline


def _load_outline_struct(outline: Outline | None) -> dict:
    if not outline or not outline.main_plot:
        return {}
    try:
        return json.loads(outline.main_plot)
    except Exception:
        return {}


def _positive_int(value) -> int:
    number = _safe_int(value, 0)
    return number if number > 0 else 0


def _extract_chapter_count_from_markdown(markdown: str | None) -> int:
    if not markdown:
        return 0
    patterns = [
        r"预计章节数\s*[：:]\s*(\d+)",
        r"本卷共\s*(\d+)\s*章",
        r"共\s*(\d+)\s*章",
    ]
    for pattern in patterns:
        match = re.search(pattern, markdown)
        if match:
            count = _positive_int(match.group(1))
            if count:
                return count
    return 0


def _resolve_volume_target_count(volume: Volume, volume_spec: dict | None, existing_count: int) -> int:
    plan_data = volume.plan_data or {}
    candidates = [
        volume.planned_chapter_count,
        plan_data.get("chapter_count"),
        plan_data.get("planned_chapter_count"),
        (volume_spec or {}).get("chapter_count"),
        _extract_chapter_count_from_markdown(volume.plan_markdown),
    ]
    for candidate in candidates:
        count = _positive_int(candidate)
        if count:
            return max(count, existing_count)
    return max(existing_count, DEFAULT_VOLUME_CHAPTER_COUNT)


def _clean_chapter_title(chapter_number: int, title: str | None) -> str:
    clean = _safe_text(title, f"第{chapter_number}章")
    clean = re.sub(rf"^第\s*{chapter_number}\s*章\s*[：:、\-—]?\s*", "", clean).strip()
    return clean or f"第{chapter_number}章"


def _create_missing_characters(db: Session, novel_id: str, names: list[str]) -> list[str]:
    created: list[str] = []
    for name in names:
        clean_name = _safe_text(name)
        if not clean_name:
            continue
        exists = db.query(Character).filter(
            Character.novel_id == novel_id,
            Character.name == clean_name,
        ).first()
        if exists:
            continue
        char = Character(
            novel_id=novel_id,
            name=clean_name,
            role="配角",
            personality="待补充",
            background="由 AI 细纲自动补录，待完善。",
            status="alive",
        )
        db.add(char)
        created.append(clean_name)
    return created


def _ensure_volume_chapters(db: Session, novel_id: str, volume: Volume) -> list[Chapter]:
    chapters = db.query(Chapter).filter(Chapter.volume_id == volume.id).order_by(Chapter.chapter_number).all()
    outline = db.query(Outline).filter(
        Outline.novel_id == novel_id,
        Outline.confirmed == True,
    ).order_by(Outline.version.desc()).first()
    outline_struct = _load_outline_struct(outline)
    volume_spec = next(
        (
            item for item in (outline_struct.get("volumes") or [])
            if _safe_int(item.get("volume_no"), 0) == volume.volume_number
        ),
        None,
    )
    target_count = _resolve_volume_target_count(volume, volume_spec, len(chapters))
    if _positive_int(volume.planned_chapter_count) != target_count:
        volume.planned_chapter_count = target_count
    if len(chapters) >= target_count:
        db.commit()
        return chapters

    max_number = db.query(Chapter.chapter_number).filter(Chapter.novel_id == novel_id).order_by(Chapter.chapter_number.desc()).first()
    next_number = _safe_int(max_number[0] if max_number else 0, 0) + 1
    missing_count = target_count - len(chapters)
    for index in range(missing_count):
        chapter_number = next_number + index
        chapter = Chapter(
            novel_id=novel_id,
            volume_id=volume.id,
            chapter_number=chapter_number,
            title=f"第{chapter_number}章",
            status="draft",
        )
        db.add(chapter)
        chapters.append(chapter)

    db.commit()
    return db.query(Chapter).filter(Chapter.volume_id == volume.id).order_by(Chapter.chapter_number).all()


def _build_volume_synopsis_markdown(db: Session, volume: Volume) -> str:
    chapters = db.query(Chapter).filter(Chapter.volume_id == volume.id).order_by(Chapter.chapter_number).all()
    parts = [
        f"# 第{volume.volume_number}卷 {volume.title}",
        "",
        f"本卷共 {len(chapters)} 章。",
        "",
    ]
    if volume.main_line:
        parts.extend(["## 本卷主线", volume.main_line.strip(), ""])

    parts.append("## 章节细纲")
    parts.append("")
    for chapter in chapters:
        synopsis = db.query(Synopsis).filter(Synopsis.chapter_id == chapter.id).first()
        default_title = f"第{chapter.chapter_number}章"
        title = (chapter.title or "").strip()
        heading = default_title if not title or title == default_title else f"{default_title} {title}"
        parts.append(f"### {heading}")
        if synopsis and synopsis.content_md:
            parts.append(synopsis.content_md.strip())
        elif synopsis and synopsis.summary_line:
            parts.append(synopsis.summary_line.strip())
        else:
            parts.append("（待生成）")
        parts.append("")
    return "\n".join(parts).strip()


def _combine_segment_content(base_content: str, segment: str, generated_text: str) -> str:
    if segment == "opening":
        return generated_text.strip()
    if not base_content.strip():
        return generated_text.strip()
    return f"{base_content.rstrip()}\n\n{generated_text.strip()}".strip()


def _persist_segment_partial(chapter_id: str, segment: str, base_content: str, generated_text: str):
    db = SessionLocal()
    try:
        chapter = db.query(Chapter).filter(Chapter.id == chapter_id).first()
        if not chapter:
            return
        merged = _combine_segment_content(base_content, segment, generated_text)
        chapter.content = merged
        chapter.word_count = len(merged)
        if chapter.status == "draft":
            chapter.status = "writing"
        db.commit()
        save_chapter_content(chapter.novel_id, chapter.chapter_number, merged)
    finally:
        db.close()


def _persist_full_chapter_partial(chapter_id: str, generated_text: str):
    db = SessionLocal()
    try:
        chapter = db.query(Chapter).filter(Chapter.id == chapter_id).first()
        if not chapter:
            return
        chapter.content = generated_text
        chapter.word_count = len(generated_text)
        if chapter.status == "draft":
            chapter.status = "writing"
        db.commit()
        save_chapter_content(chapter.novel_id, chapter.chapter_number, generated_text)
    finally:
        db.close()


async def _execute_outline_job(db: Session, payload: dict, job_id: str) -> dict:
    novel = db.query(Novel).filter(Novel.id == payload["novel_id"]).first()
    if not novel:
        raise HTTPException(404, "小说不存在")
    last = db.query(Outline).filter(Outline.novel_id == payload["novel_id"]).order_by(Outline.version.desc()).first()
    is_outline_chat = bool(payload.get("outline_chat"))
    is_revision = bool(is_outline_chat and last and last.content)
    mode = _safe_text(payload.get("mode"), "revise")
    rewrite_mode = mode == "rewrite"
    idea = _validate_outline_idea(payload.get("idea", ""), allow_short=is_revision)

    prompt_cfg = _prompt_config()
    json_contract = """你必须严格输出 JSON（不要解释）。所有键名必须和示例完全一致，不能给键名增加括号或其他符号，例如只能写 "description"，不能写 "description)"：
```json
{
  "title_draft": "暂定书名",
  "book_synopsis_draft": "100-180字的读者向简介草稿",
  "outline_struct": {
    "selling_points": [
      "卖点1（读者爽点）",
      "卖点2（冲突/反转）",
      "卖点3（差异化）"
    ],
    "story_positioning": "一句话定位（谁在什么世界完成什么目标）",
    "core_conflict": "主角长期冲突与终局对手",
    "target_total_words": 180000,
    "protagonist": {
      "name": "主角名",
      "background": "主角出身与起点",
      "golden_finger": "主角的核心外挂/机缘",
      "motivation": "主角最核心的执念",
      "realm": "开局境界",
      "faction": "当前阵营/宗门",
      "personality": "性格基调"
    },
    "core_cast": [
      {
        "name": "角色名",
        "role": "主角/女主/反派/导师/配角",
        "personality": "性格特征",
        "background": "背景与立场",
        "golden_finger": "特殊能力，没有填无",
        "motivation": "核心动机",
        "realm": "大致境界",
        "faction": "所属阵营"
      }
    ],
    "world_seed": {
      "cultivation_system": [
        {"name": "境界名", "description": "该境界的关键特征"}
      ],
      "major_factions": [
        {"name": "势力名", "description": "势力定位与作用"}
      ],
      "major_regions": [
        {"name": "地域名", "description": "地域特色与功能"}
      ],
      "core_rules": [
        {"rule_name": "规则名", "description": "规则限制与影响"}
      ],
      "treasures": [
        {"name": "宝物/资源名", "description": "作用与稀缺性"}
      ]
    },
    "volumes": [
      {
        "volume_no": 1,
        "title": "卷名",
        "target_words": 30000,
        "chapter_count": 12,
        "main_line": "本卷主线目标",
        "character_arc": "本卷人物成长/关系变化",
        "ending_hook": "卷末留下的悬念"
      }
    ]
  }
}
```"""

    if is_revision:
        recent_messages = db.query(OutlineChatMessage).filter(
            OutlineChatMessage.novel_id == payload["novel_id"],
        ).order_by(OutlineChatMessage.created_at.desc()).limit(8).all()
        history = "\n".join(
            f"{item.role}：{item.content}" for item in reversed(recent_messages)
        )
        revision_goal = (
            "作者想舍弃当前方案重做。请基于本轮新想法重新设计一个完整大纲；当前版本只用于了解已有作品方向，不能机械沿用。"
            if rewrite_mode
            else "请基于“当前大纲版本”和“本轮修改要求”生成一个新的完整大纲版本，不要只输出局部修改。"
        )
        continuity_rule = (
            "可以大幅重构角色、世界观和分卷，但必须保证新方案完整、自洽、适合后续展开。"
            if rewrite_mode
            else "必须保留合理的既有设定，只修正作者不满意的地方。"
        )
        prompt = f"""{prompt_cfg['outline_generation']}

你正在帮助作者打磨小说大纲。{revision_goal}

类型：{novel.genre}

当前大纲版本 v{last.version}：
{last.content}

最近对话：
{history or "（暂无）"}

本轮修改要求：
{idea}

要求：
1. {continuity_rule}
2. 如果作者要求调整节奏、角色、冲突、分卷，就同步修订对应段落，保证新版本自洽。
3. 这是待确认修改稿，不代表已经定稿；输出仍要是完整大纲，方便作者在编辑器内审阅每处修改。
4. 不得参考或沿用数据库中的默认占位书名，只根据大纲内容生成书名草案。
5. 所有面向作者阅读的文本字段都按普通 txt 写法输出，不要使用 Markdown 标记（不要 #、##、**、代码块）。

{json_contract}"""
    else:
        prompt = f"""{prompt_cfg['outline_generation']}

想法：{idea}
类型：{novel.genre}

要求：
1. 这是第一版大纲，请从作者想法推导书名草案、简介、核心角色、世界观种子和分卷规划。
2. 不得参考或沿用数据库中的默认占位书名，只根据“想法”和“类型”生成。
3. 所有面向作者阅读的文本字段都按普通 txt 写法输出，不要使用 Markdown 标记（不要 #、##、**、代码块）。

{json_contract}"""

    response_text = await ai_job_service.collect_text(
        job_id=job_id,
        system_prompt=prompt_cfg["global_system"],
        user_prompt=prompt,
        progress_message="AI 正在生成待确认的大纲修改稿，请稍候..." if is_revision else "AI 正在生成第一版大纲，请稍候...",
    )

    try:
        data = await _loads_ai_json_with_retries(
            job_id=job_id,
            label="大纲生成",
            response_text=response_text,
            json_contract=json_contract,
        )
    except AIJsonFormatError as exc:
        raise HTTPException(400, exc.detail)

    outline_struct = _normalize_outline_struct(data, novel.genre)
    title_draft = _safe_text(data.get("title_draft"), "暂定书名")
    synopsis_draft = _safe_text(data.get("book_synopsis_draft"), "（待补充）")
    selling_points_text = "\n".join([f"- {item}" for item in (outline_struct.get("selling_points") or [])])
    content_md = _render_outline_markdown(title_draft, synopsis_draft, outline_struct)

    version = (last.version + 1) if last else 1

    if is_revision and last:
        draft_outline = {
            "title": title_draft,
            "synopsis": synopsis_draft,
            "selling_points": selling_points_text,
            "main_plot": json.dumps(outline_struct, ensure_ascii=False),
            "content": content_md,
            "base_outline_id": last.id,
            "base_version": last.version,
            "target_version": version,
            "mode": "rewrite" if rewrite_mode else "revise",
        }
        novel.idea = idea
        db.commit()
        _add_outline_chat_message(
            db,
            novel_id=payload["novel_id"],
            outline_id=last.id,
            role="assistant",
            content=f"已生成待确认修改稿。请在大纲编辑器里逐处接受或拒绝 AI 建议，确认满意后再手动保存为 v{version}。",
            metadata={
                "status": "pending_draft",
                "draft_outline": draft_outline,
                "base_outline_id": last.id,
                "base_version": last.version,
                "target_version": version,
                "mode": "rewrite" if rewrite_mode else "revise",
            },
        )
        return {"saved": False, "draft_outline": draft_outline}

    existing_count = db.query(Outline).filter(Outline.novel_id == payload["novel_id"]).count()
    if existing_count >= MAX_OUTLINE_VERSIONS:
        raise HTTPException(400, "大纲最多保留 5 个版本。请先删除不需要的旧版本，再保存新版本。")

    outline = Outline(
        novel_id=payload["novel_id"],
        title=title_draft,
        synopsis=synopsis_draft,
        selling_points=selling_points_text,
        main_plot=json.dumps(outline_struct, ensure_ascii=False),
        content=content_md,
        ai_generated=True,
        confirmed=False,
        version=version,
        version_note="AI 生成初版" if is_outline_chat else None,
    )
    db.add(outline)
    novel.idea = idea
    db.commit()
    db.refresh(outline)
    if is_outline_chat:
        _add_outline_chat_message(
            db,
            novel_id=payload["novel_id"],
            outline_id=outline.id,
            role="assistant",
            content=f"已生成大纲 v{outline.version}。你可以继续说哪里不满意，我会基于这一版继续改。",
            metadata={"outline_version": outline.version, "outline_id": outline.id},
        )
        return {"saved": True, "outline": _serialize_outline(outline)}
    return _serialize_outline(outline)


async def _execute_titles_job(db: Session, payload: dict, job_id: str) -> dict:
    novel = db.query(Novel).filter(Novel.id == payload["novel_id"]).first()
    if not novel:
        raise HTTPException(404, "小说不存在")

    outline = db.query(Outline).filter(
        Outline.novel_id == payload["novel_id"],
        Outline.confirmed == True,
    ).order_by(Outline.version.desc()).first()
    if not outline or not outline.content:
        raise HTTPException(400, "请先确认大纲")

    prompt_cfg = _prompt_config()
    prompt = f"""{prompt_cfg['titles_generation']}

【类型】{novel.genre}
【大纲摘要】
{outline.content[:2000]}

注意：数据库里的当前书名可能只是“默认书名1”这类占位名，生成候选书名时不要参考当前书名，只参考已确认大纲和用户额外偏好。

输出要求：
1. 必须输出JSON数组，长度为10
2. 每个元素是字符串（书名）
3. 风格偏网文，辨识度高，避免雷同
4. 不要输出任何额外说明
"""
    if payload.get("extra_instruction"):
        prompt += f"\n额外要求：{payload['extra_instruction']}\n"

    full_text = await ai_job_service.collect_text(
        job_id=job_id,
        system_prompt=prompt_cfg["global_system"],
        user_prompt=prompt,
        progress_message="AI 正在生成标题候选...",
    )
    try:
        titles = await _loads_ai_json_with_retries(
            job_id=job_id,
            label="标题生成",
            response_text=full_text,
            json_contract="JSON 数组，长度为 10，数组元素必须是字符串书名。",
            expected_root=(list,),
        )
    except AIJsonFormatError as exc:
        raise HTTPException(400, exc.detail)
    if not isinstance(titles, list):
        raise ValueError("标题结果格式错误")
    return {"titles": [str(t).strip() for t in titles if str(t).strip()][:10]}


async def _execute_book_synopsis_job(db: Session, payload: dict, job_id: str) -> dict:
    novel = db.query(Novel).filter(Novel.id == payload["novel_id"]).first()
    if not novel:
        raise HTTPException(404, "小说不存在")

    outline = db.query(Outline).filter(
        Outline.novel_id == payload["novel_id"],
        Outline.confirmed == True,
    ).order_by(Outline.version.desc()).first()
    if not outline or not outline.content:
        raise HTTPException(400, "请先确认大纲")

    prompt_cfg = _prompt_config()
    prompt = f"""{prompt_cfg['book_synopsis_generation']}

【书名】{novel.title}
【类型】{novel.genre}
【大纲摘要】
{outline.content[:2200]}

输出要求：
1. 100-180字
2. 强调主角、核心冲突和爽点
3. 读者导向，适合详情页展示
4. 仅输出简介正文，不要加标题和说明
"""
    if payload.get("extra_instruction"):
        prompt += f"\n额外要求：{payload['extra_instruction']}\n"

    full_text = await ai_job_service.collect_text(
        job_id=job_id,
        system_prompt=prompt_cfg["global_system"],
        user_prompt=prompt,
        progress_message="AI 正在生成简介...",
    )
    synopsis = full_text.strip()
    if payload.get("dry_run"):
        return {"synopsis": synopsis, "dry_run": True}
    novel.synopsis = synopsis
    db.commit()
    save_synopsis(payload["novel_id"], synopsis)
    save_book_meta(payload["novel_id"], novel.title, synopsis)
    return {"synopsis": synopsis}


async def _execute_chapter_synopsis_job(db: Session, payload: dict, job_id: str) -> dict:
    prompt = context_builder.build_synopsis_context(db, payload["novel_id"], payload["chapter_number"])
    if payload.get("extra_instruction"):
        prompt += f"\n\n额外要求：{payload['extra_instruction']}"

    full_text = await ai_job_service.collect_text(
        job_id=job_id,
        system_prompt=SYSTEM_NOVEL,
        user_prompt=prompt,
        progress_message="AI 正在生成章节细纲...",
    )
    try:
        data = await _loads_ai_json_with_retries(
            job_id=job_id,
            label="章节细纲生成",
            response_text=full_text,
            json_contract="JSON 对象，包含 title、opening、development、ending、referenced_entities、proposal_candidates 等字段。",
            expected_root=(dict,),
        )
    except AIJsonFormatError as exc:
        raise HTTPException(400, exc.detail)

    chapter = db.query(Chapter).filter(Chapter.id == payload["chapter_id"]).first()
    if not chapter:
        raise HTTPException(404, "章节不存在")

    if data.get("title"):
        chapter.title = data.get("title")

    opening = data.get("opening", {})
    development = data.get("development", {})
    ending = data.get("ending", {})
    all_chars = list(set(opening.get("characters", []) + development.get("characters", [])))
    referenced_entities = data.get("referenced_entities") or {}
    if not referenced_entities.get("characters"):
        referenced_entities["characters"] = all_chars
    proposal_candidates = data.get("proposal_candidates") or []
    missing_entities, created_proposals = validate_and_prepare_proposals(
        db,
        payload["novel_id"],
        referenced_entities,
        proposal_candidates,
        chapter_id=payload["chapter_id"],
        volume_id=chapter.volume_id,
    )

    synopsis = db.query(Synopsis).filter(Synopsis.chapter_id == payload["chapter_id"]).first()
    if not synopsis:
        synopsis = Synopsis(chapter_id=payload["chapter_id"], novel_id=payload["novel_id"])
        db.add(synopsis)

    synopsis.opening_scene = opening.get("scene", "")
    synopsis.opening_mood = opening.get("mood", "")
    synopsis.opening_hook = opening.get("hook", "")
    synopsis.opening_characters = opening.get("characters", [])
    synopsis.development_events = development.get("events", [])
    synopsis.development_conflicts = development.get("conflicts", [])
    synopsis.development_characters = development.get("characters", [])
    synopsis.ending_resolution = ending.get("resolution", "")
    synopsis.ending_cliffhanger = ending.get("cliffhanger", "")
    synopsis.ending_next_hook = ending.get("next_chapter_hook", "")
    synopsis.all_characters = all_chars
    synopsis.word_count_target = data.get("word_count_target", 3000)
    synopsis.summary_line = data.get("summary_line", "")
    synopsis.content_md = data.get("content_md", "")
    synopsis.hard_constraints = data.get("hard_constraints") or []
    synopsis.referenced_entities = referenced_entities
    synopsis.review_status = "needs_review" if created_proposals else "draft"
    synopsis.approved_at = None
    synopsis.plot_summary_update = data.get("plot_summary_update", "")
    db.commit()
    db.refresh(synopsis)
    save_chapter_synopsis(payload["novel_id"], chapter.chapter_number, _serialize_synopsis(synopsis))
    save_chapter_plot_summary(payload["novel_id"], chapter.chapter_number, synopsis.plot_summary_update or "")
    if created_proposals:
        save_all_proposals(db, payload["novel_id"])
    return {
        "status": "ok",
        "summary_line": synopsis.summary_line,
        "missing_entities": missing_entities,
        "pending_proposals": [serialize_proposal(item) for item in created_proposals],
    }


async def _execute_full_chapter_job(db: Session, payload: dict, job_id: str) -> dict:
    chapter = db.query(Chapter).filter(Chapter.id == payload["chapter_id"], Chapter.novel_id == payload["novel_id"]).first()
    if not chapter:
        raise HTTPException(404, "章节不存在")

    guard = chapter_access_guard(db, chapter)
    if not guard["ok"]:
        raise HTTPException(400, guard["reason"])

    prompt = context_builder.build_chapter_context(db, payload["novel_id"], payload["chapter_id"])
    if payload.get("extra_instruction"):
        prompt += f"\n\n额外要求：{payload['extra_instruction']}"

    dry_run = bool(payload.get("dry_run"))
    text = await ai_job_service.collect_text(
        job_id=job_id,
        system_prompt=SYSTEM_NOVEL,
        user_prompt=prompt,
        progress_message="AI 正在生成正文...",
        on_partial=None if dry_run else lambda current: _persist_full_chapter_partial(payload["chapter_id"], current),
    )

    # 提取实体引用并检测幻觉
    synopsis = db.query(Synopsis).filter(Synopsis.chapter_id == chapter.id).first()
    referenced_entities = synopsis.referenced_entities if synopsis and isinstance(synopsis.referenced_entities, dict) else {}

    # 从生成的正文中提取实体引用（简单实现，可以后续优化为AI提取）
    # 这里先使用细纲中的referenced_entities作为基准
    _, proposals = validate_and_prepare_proposals(
        db,
        payload["novel_id"],
        referenced_entities,
        [],  # 正文生成时暂不自动提取新实体，依赖细纲阶段的提案
        chapter_id=chapter.id,
        volume_id=chapter.volume_id,
    )

    if dry_run:
        return {
            "chapter_id": chapter.id,
            "chapter_number": chapter.chapter_number,
            "title": chapter.title,
            "content": text,
            "word_count": len(text),
            "dry_run": True,
            "proposals_created": len(proposals),
            "pending_proposals": [serialize_proposal(item) for item in proposals],
        }

    chapter.content = text
    chapter.word_count = len(text)
    if chapter.status == "draft":
        chapter.status = "writing"
    db.commit()
    db.refresh(chapter)
    save_chapter_content(payload["novel_id"], chapter.chapter_number, text)

    return {
        **_serialize_chapter(chapter),
        "proposals_created": len(proposals),
    }


async def _execute_book_volumes_job(db: Session, payload: dict, job_id: str) -> dict:
    novel = db.query(Novel).filter(Novel.id == payload["novel_id"]).first()
    if not novel:
        raise HTTPException(404, "小说不存在")

    outline = db.query(Outline).filter(
        Outline.novel_id == payload["novel_id"],
        Outline.confirmed == True,
    ).order_by(Outline.version.desc()).first()
    if not outline:
        raise HTTPException(400, "请先确认大纲。全书分卷必须建立在已确认大纲上。")

    existing_volumes = db.query(Volume).filter(Volume.novel_id == payload["novel_id"]).order_by(Volume.volume_number).all()
    blocked = [
        volume
        for volume in existing_volumes
        if db.query(Chapter).filter(Chapter.volume_id == volume.id).count() > 0
    ]
    if blocked:
        first = blocked[0]
        raise HTTPException(
            400,
            f"《{first.title}》已经生成了章节细纲或正文，不能一键重生成全书分卷。请在现有全书分卷上审批或调整未开写的卷。",
        )

    prompt = f"""请基于已确认的大纲，生成“全书分卷”规划。

要求：
1. 只做卷级规划，不要生成章节细纲，不要输出正文。
2. 每一卷必须说明：本卷目标、核心冲突、主角状态变化、重要人物推进、关键地点/势力/道具、结尾钩子。
3. 预计章节数要适合网文长篇节奏；如果用户没有指定，每卷可按 30-50 章规划。
4. 分卷之间要连续推进，不能出现主角从 B 地区升级后又无理由回到 A 地区重新升级这类倒退矛盾。
5. 只输出合法 JSON，不要 Markdown 代码块，不要解释。

JSON 契约：
{{
  "volumes": [
    {{
      "volume_number": 1,
      "title": "卷名",
      "target_words": 120000,
      "planned_chapter_count": 40,
      "description": "本卷定位，一两句话",
      "main_line": "本卷主线",
      "core_conflict": "核心冲突",
      "character_arc": "主角和核心人物的推进",
      "ending_hook": "卷末钩子",
      "key_settings": ["地点/势力/道具/规则"],
      "book_plan_markdown": "## 第一卷 卷名\\n目标字数：...\\n预计章节数：...\\n本卷目标：...\\n核心冲突：...\\n人物推进：...\\n关键设定：...\\n卷末钩子：..."
    }}
  ]
}}

作品标题：{novel.title}
作品简介：{novel.synopsis or "（暂无）"}

已确认大纲：
{outline.content or outline.main_plot or "（暂无大纲正文）"}
"""
    if payload.get("extra_instruction"):
        prompt += f"\n\n额外要求：{payload['extra_instruction']}"

    full_text = await ai_job_service.collect_text(
        job_id=job_id,
        system_prompt=SYSTEM_NOVEL,
        user_prompt=prompt,
        progress_message="AI 正在生成全书分卷规划...",
    )
    try:
        data = await _loads_ai_json_with_retries(
            job_id=job_id,
            label="全书分卷生成",
            response_text=full_text,
            json_contract="JSON 对象，必须包含 volumes 数组；每个元素是一卷规划，不允许包含章节正文。",
            expected_root=(dict,),
        )
    except AIJsonFormatError as exc:
        raise HTTPException(400, exc.detail)

    volume_items = data.get("volumes") or []
    if not isinstance(volume_items, list) or not volume_items:
        raise HTTPException(400, "AI 没有返回可用的分卷列表，请补充大纲信息后重试。")

    for volume in existing_volumes:
        db.delete(volume)
    db.flush()

    created: list[Volume] = []
    for index, item in enumerate(volume_items, start=1):
        if not isinstance(item, dict):
            continue
        volume_number = _positive_int(item.get("volume_number") or item.get("volume_no") or index) or index
        title = _safe_text(item.get("title"), f"第{volume_number}卷")
        target_words = _positive_int(item.get("target_words")) or 120000
        planned_count = _positive_int(item.get("planned_chapter_count") or item.get("chapter_count")) or 40
        description = _safe_text(item.get("description") or item.get("summary") or item.get("positioning"))
        main_line = _safe_text(item.get("main_line"))
        character_arc = _safe_text(item.get("character_arc"))
        ending_hook = _safe_text(item.get("ending_hook"))
        single_markdown = _safe_text(item.get("book_plan_markdown"))
        if not single_markdown:
            key_settings = "、".join(str(value) for value in _safe_list(item.get("key_settings")) if str(value).strip())
            single_markdown = "\n".join([
                f"## 第{volume_number}卷 {title}",
                f"目标字数：{target_words}",
                f"预计章节数：{planned_count}",
                f"本卷目标：{description or main_line or '待补充'}",
                f"核心冲突：{_safe_text(item.get('core_conflict'), '待补充')}",
                f"人物推进：{character_arc or '待补充'}",
                f"关键设定：{key_settings or '待补充'}",
                f"卷末钩子：{ending_hook or '待补充'}",
            ])

        volume = Volume(
            novel_id=payload["novel_id"],
            volume_number=volume_number,
            title=title,
            description=description,
            target_words=target_words,
            planned_chapter_count=planned_count,
            main_line=main_line,
            character_arc=character_arc,
            ending_hook=ending_hook,
            plan_markdown=single_markdown,
            plan_data={
                **item,
                "book_plan_status": "draft",
                "book_plan_markdown": single_markdown,
            },
            review_status="draft",
            synopsis_generated=False,
        )
        db.add(volume)
        created.append(volume)

    if not created:
        raise HTTPException(400, "AI 返回的分卷数据无法入库，请重试。")

    db.commit()
    refreshed = db.query(Volume).filter(Volume.novel_id == payload["novel_id"]).order_by(Volume.volume_number).all()
    for volume in refreshed:
        save_volume_plan(payload["novel_id"], volume.volume_number, volume.plan_markdown or "", volume.plan_data or {})

    return {
        "status": "ok",
        "volume_count": len(refreshed),
        "approved": all(_book_plan_status(volume) == "approved" for volume in refreshed),
        "book_plan_markdown": _book_volume_plan_markdown(refreshed),
        "volumes": [_serialize_volume_for_plan(db, volume) for volume in refreshed],
    }


async def _execute_volume_synopsis_job(db: Session, payload: dict, job_id: str) -> dict:
    volume = db.query(Volume).filter(
        Volume.id == payload["volume_id"],
        Volume.novel_id == payload["novel_id"],
    ).first()
    if not volume:
        raise HTTPException(404, "卷不存在")

    chapters = _ensure_volume_chapters(db, payload["novel_id"], volume)
    ch_map = {c.chapter_number: c for c in chapters}
    created_proposals: list[EntityProposal] = []

    # 一次性生成整卷细纲（不再分批）
    prompt = context_builder.build_volume_synopsis_context(
        db,
        payload["novel_id"],
        payload["volume_id"],
    )
    if payload.get("extra_instruction"):
        prompt += f"\n\n额外要求：{payload['extra_instruction']}"

    full_text = await ai_job_service.collect_text(
        job_id=job_id,
        system_prompt=SYSTEM_NOVEL,
        user_prompt=prompt,
        progress_message=f"AI 正在生成本卷细纲（共{len(chapters)}章）...",
    )
    try:
        data = await _loads_ai_json_with_retries(
            job_id=job_id,
            label="分卷细纲生成",
            response_text=full_text,
            json_contract="JSON 对象或数组。对象时必须包含 chapters 数组；数组时每个元素是一章细纲。",
            expected_root=(dict, list),
        )
    except AIJsonFormatError as exc:
        raise HTTPException(400, exc.detail)
    synopsis_list = data.get("chapters", []) if isinstance(data, dict) else data

    for item in synopsis_list:
        ch_num = _safe_int(item.get("chapter_number"), 0)
        ch = ch_map.get(ch_num)
        if not ch:
            continue
        opening = item.get("opening", {})
        development = item.get("development", {})
        ending = item.get("ending", {})
        all_chars = list(set(opening.get("characters", []) + development.get("characters", [])))
        referenced_entities = item.get("referenced_entities") or {}
        if not referenced_entities.get("characters"):
            referenced_entities["characters"] = all_chars
        _, proposals = validate_and_prepare_proposals(
            db,
            payload["novel_id"],
            referenced_entities,
            item.get("proposal_candidates") or [],
            chapter_id=ch.id,
            volume_id=payload["volume_id"],
        )
        created_proposals.extend(proposals)

        existing = db.query(Synopsis).filter(Synopsis.chapter_id == ch.id).first()
        if not existing:
            existing = Synopsis(chapter_id=ch.id, novel_id=payload["novel_id"])
            db.add(existing)

        existing.opening_scene = opening.get("scene", "")
        existing.opening_mood = opening.get("mood", "")
        existing.opening_hook = opening.get("hook", "")
        existing.opening_characters = opening.get("characters", [])
        existing.development_events = development.get("events", [])
        existing.development_conflicts = development.get("conflicts", [])
        existing.development_characters = development.get("characters", [])
        existing.ending_resolution = ending.get("resolution", "")
        existing.ending_cliffhanger = ending.get("cliffhanger", "")
        existing.ending_next_hook = ending.get("next_chapter_hook", "")
        existing.all_characters = all_chars
        existing.word_count_target = item.get("word_count_target", 3000)
        existing.summary_line = item.get("summary_line", "")
        existing.content_md = item.get("content_md", "")
        existing.hard_constraints = item.get("hard_constraints") or []
        existing.referenced_entities = referenced_entities
        existing.review_status = "needs_review" if proposals else "draft"
        existing.approved_at = None
        existing.plot_summary_update = item.get("plot_summary_update", "")
        if item.get("title"):
            ch.title = _clean_chapter_title(ch.chapter_number, item.get("title"))

    db.commit()

    volume.synopsis_generated = True
    volume.review_status = "draft"
    volume.approved_at = None
    db.commit()

    refreshed_chapters = db.query(Chapter).filter(Chapter.volume_id == payload["volume_id"]).order_by(Chapter.chapter_number).all()
    for ch in refreshed_chapters:
        synopsis = db.query(Synopsis).filter(Synopsis.chapter_id == ch.id).first()
        if synopsis:
            save_chapter_synopsis(payload["novel_id"], ch.chapter_number, _serialize_synopsis(synopsis))
            save_chapter_plot_summary(payload["novel_id"], ch.chapter_number, synopsis.plot_summary_update or "")
    volume.plan_markdown = _build_volume_synopsis_markdown(db, volume)
    volume.plan_data = {
        **(volume.plan_data or {}),
        "synopsis_chapter_count": len(refreshed_chapters),
    }
    db.commit()
    save_volume_plan(payload["novel_id"], volume.volume_number, volume.plan_markdown or "", volume.plan_data or {})
    if created_proposals:
        save_all_proposals(db, payload["novel_id"])
    return {
        "status": "ok",
        "chapter_count": len(refreshed_chapters),
        "pending_proposals": [serialize_proposal(item) for item in created_proposals],
    }


async def _execute_characters_job(db: Session, payload: dict, job_id: str) -> dict:
    novel = db.query(Novel).filter(Novel.id == payload["novel_id"]).first()
    if not novel:
        raise HTTPException(404, "小说不存在")

    outline = _get_latest_outline(db, payload["novel_id"], payload.get("outline_id"))
    prompt = f"""你是一个资深网文架构师。请仔细阅读以下小说大纲：

【书名】：{outline.title or novel.title}
【简介】：{outline.synopsis or novel.synopsis}
【主线大纲】：
{outline.main_plot or outline.content}

请根据大纲的背景和剧情，提取并生成这部小说中最核心的 3-8 个人物。
角色定位必须尽量通用，便于后续扩展到修仙、现代、科幻、悬疑等不同题材。
你必须严格按照以下 JSON 格式输出，不要输出任何额外的废话：
```json
[
  {{
    "name": "姓名",
    "aliases": ["别名或称号"],
    "role": "男主/女主/男配/女配/反派/导师/伙伴/亲族/势力人物/路人/群像角色/未知",
    "importance": 5,
    "gender": "男/女/未知/其他",
    "race": "人族/妖族/普通人/AI/未知等",
    "realm": "当前能力层级或社会身份，没有就填空字符串",
    "faction": "所属势力、组织、公司、宗门、家族，没有就填空字符串",
    "personality": "性格特征（如：杀伐果断、腹黑）",
    "appearance": "外貌描写",
    "background": "身世背景",
    "golden_finger": "金手指/特殊能力（如果不是主角可填无）",
    "motivation": "核心动机/执念（他为什么做这些事）",
    "profile_md": "## 核心设定\\n...\\n\\n## 背景\\n...\\n\\n## 关系与秘密\\n...\\n\\n## 当前状态\\n..."
  }}
]
```"""

    response_text = await ai_job_service.collect_text(
        job_id=job_id,
        system_prompt=SYSTEM_NOVEL,
        user_prompt=prompt,
        progress_message="AI 正在提取核心角色...",
    )
    try:
        data = await _loads_ai_json_with_retries(
            job_id=job_id,
            label="角色生成",
            response_text=response_text,
            json_contract="JSON 数组，每个元素是角色对象，包含 name、role、importance、profile_md 等字段。",
            expected_root=(list,),
        )
    except AIJsonFormatError as exc:
        raise HTTPException(400, exc.detail)

    def normalize_character(raw: dict) -> dict:
        aliases = raw.get("aliases") or []
        if isinstance(aliases, str):
            aliases = [item.strip() for item in aliases.replace("，", ",").split(",") if item.strip()]
        if not isinstance(aliases, list):
            aliases = []
        importance = raw.get("importance", 3)
        try:
            importance = max(1, min(5, int(importance)))
        except (TypeError, ValueError):
            importance = 3
        profile_md = (raw.get("profile_md") or "").strip()
        if not profile_md:
            profile_parts = [
                f"## 核心动机\n{raw.get('motivation')}" if raw.get("motivation") else "",
                f"## 背景\n{raw.get('background')}" if raw.get("background") else "",
                f"## 性格与说话方式\n{raw.get('personality')}" if raw.get("personality") else "",
                f"## 特殊能力\n{raw.get('golden_finger')}" if raw.get("golden_finger") else "",
                f"## 外貌辨识\n{raw.get('appearance')}" if raw.get("appearance") else "",
            ]
            profile_md = "\n\n".join(item for item in profile_parts if item)
        status = raw.get("status") or "alive"
        if status not in {"alive", "dead", "unknown"}:
            status = "alive"
        return {
            "name": str(raw.get("name") or "").strip(),
            "aliases": aliases,
            "role": raw.get("role") or "未知",
            "importance": importance,
            "gender": raw.get("gender") or None,
            "race": raw.get("race") or None,
            "realm": raw.get("realm") or None,
            "faction": raw.get("faction") or None,
            "personality": raw.get("personality") or None,
            "appearance": raw.get("appearance") or None,
            "background": raw.get("background") or None,
            "golden_finger": raw.get("golden_finger") or None,
            "motivation": raw.get("motivation") or None,
            "profile_md": profile_md,
            "status": status,
        }

    normalized_characters = [
        item for item in (normalize_character(raw) for raw in data if isinstance(raw, dict))
        if item["name"]
    ]

    if payload.get("dry_run"):
        return {"characters": normalized_characters, "dry_run": True}

    created_characters = []
    for char_data in normalized_characters:
        existing = db.query(Character).filter(
            Character.novel_id == payload["novel_id"],
            Character.name == char_data.get("name"),
        ).first()
        if existing:
            continue
        char = Character(
            novel_id=payload["novel_id"],
            name=char_data.get("name"),
            aliases=char_data.get("aliases") or [],
            role=char_data.get("role", "未知"),
            importance=char_data.get("importance", 3),
            gender=char_data.get("gender"),
            race=char_data.get("race"),
            realm=char_data.get("realm"),
            faction=char_data.get("faction"),
            personality=char_data.get("personality"),
            appearance=char_data.get("appearance"),
            background=char_data.get("background"),
            golden_finger=char_data.get("golden_finger"),
            motivation=char_data.get("motivation"),
            profile_md=char_data.get("profile_md"),
            status=char_data.get("status") or "alive",
        )
        db.add(char)
        created_characters.append(char)

    db.commit()
    for char in created_characters:
        db.refresh(char)
    all_characters = db.query(Character).filter(Character.novel_id == payload["novel_id"]).all()
    save_characters(payload["novel_id"], _serialize_characters(all_characters))
    return {"characters": _serialize_characters(created_characters)}


async def _execute_worldbuilding_job(db: Session, payload: dict, job_id: str) -> dict:
    novel = db.query(Novel).filter(Novel.id == payload["novel_id"]).first()
    if not novel:
        raise HTTPException(404, "小说不存在")

    outline = _get_latest_outline(db, payload["novel_id"], payload.get("outline_id"))
    current_worldbuilding = normalize_worldbuilding_document(
        payload.get("current_worldbuilding") or load_worldbuilding_document(payload["novel_id"], db.query(Worldbuilding).filter(Worldbuilding.novel_id == payload["novel_id"]).first()),
        novel_id=payload["novel_id"],
    )
    prompt = f"""你是一位擅长长篇玄幻修仙项目的设定编辑。请仔细阅读以下小说信息，并输出一份可持续维护的世界设定文件。

【书名】：{outline.title or novel.title}
【简介】：{outline.synopsis or novel.synopsis}
【卖点】：{outline.selling_points}
【主线大纲】：
{outline.main_plot or outline.content}

【当前世界观（如果有，请优先保留栏目结构并在此基础上补全）】：
{json.dumps(current_worldbuilding, ensure_ascii=False, indent=2)}

设计要求：
1. 这不是固定表单，但凡是地点、势力、道具、功法、境界、灵兽等会被正文反复引用的内容，必须写入 sections[].entries[] 结构化条目。
2. content 只写本栏目的整体备注或通用规则，不要把所有条目堆进 content。
3. 如果用户已经写了自定义栏目或 generation_hint，必须优先保留并补全，不要随意删掉。
4. entries[].attributes 用来保存可被程序读取的字段，例如 owner/current_location/present_characters/base_location/grade/status 等。
5. 可以新增例如“血脉体系”“宗门戒律”“秘境生态”“历史谜团”“禁忌”“职业体系”等自定义栏目，但不要覆盖用户没有要求修改的栏目。

你必须严格按照以下 JSON 格式输出，不要输出任何额外的废话：
```json
{{
  "overview": "80-180字的世界总述，说明这个世界最核心的运行逻辑与戏剧张力",
  "sections": [
    {{
      "id": "power_system",
      "name": "力量/境界体系",
      "description": "这个栏目回答什么问题",
      "generation_hint": "若用户已有提示，请沿用；没有可留空",
      "content": "这一类设定的整体备注或通用规则，不要把条目正文都堆在这里。",
      "entries": [
        {{
          "name": "设定名",
          "summary": "一句话定义",
          "details": "补充限制、代价、与剧情关系",
          "tags": ["可选标签"],
          "attributes": {{"type": "可选扩展字段", "owner": "归属/掌握者/控制方", "location": "当前位置或关联地点", "status": "当前状态"}}
        }}
      ]
    }}
  ]
}}
```"""
    if payload.get("extra_instruction"):
        prompt += f"\n\n额外要求：{payload['extra_instruction']}"

    response_text = await ai_job_service.collect_text(
        job_id=job_id,
        system_prompt=SYSTEM_NOVEL,
        user_prompt=prompt,
        progress_message="AI 正在推演世界观...",
    )
    try:
        data = await _loads_ai_json_with_retries(
            job_id=job_id,
            label="世界观生成",
            response_text=response_text,
            json_contract="JSON 对象，包含 overview 和 sections。sections 是数组，每个 section 包含 id、name、description、generation_hint、content、entries。",
            expected_root=(dict,),
        )
    except AIJsonFormatError as exc:
        raise HTTPException(400, exc.detail)

    if payload.get("dry_run"):
        return merge_worldbuilding_documents(current_worldbuilding, data)

    wb = db.query(Worldbuilding).filter(Worldbuilding.novel_id == payload["novel_id"]).first()
    if not wb:
        wb = Worldbuilding(novel_id=payload["novel_id"])
        db.add(wb)

    merged = merge_worldbuilding_documents(current_worldbuilding, data)
    apply_worldbuilding_document(wb, merged)
    db.commit()
    db.refresh(wb)

    serialized = _serialize_worldbuilding(wb)
    save_worldbuilding(payload["novel_id"], serialized)
    return serialized


async def _execute_chapter_segment_job(db: Session, payload: dict, job_id: str) -> dict:
    segment = payload["segment"]
    if segment not in ("opening", "middle", "ending"):
        raise HTTPException(400, "segment 必须是 opening/middle/ending")

    chapter = db.query(Chapter).filter(
        Chapter.id == payload["chapter_id"],
        Chapter.novel_id == payload["novel_id"],
    ).first()
    if not chapter:
        raise HTTPException(404, "章节不存在")

    guard = chapter_access_guard(db, chapter)
    if not guard["ok"]:
        raise HTTPException(400, guard["reason"])

    base_content = chapter.content or ""
    prompt = context_builder.build_chapter_segment_context(
        db,
        payload["novel_id"],
        payload["chapter_id"],
        segment,
        payload.get("prev_segment_text") or "",
    )
    if payload.get("extra_instruction"):
        prompt += f"\n\n额外要求：{payload['extra_instruction']}"

    dry_run = bool(payload.get("dry_run"))
    text = await ai_job_service.collect_text(
        job_id=job_id,
        system_prompt=SYSTEM_NOVEL,
        user_prompt=prompt,
        progress_message="AI 正在生成正文片段...",
        on_partial=None if dry_run else lambda current: _persist_segment_partial(payload["chapter_id"], segment, base_content, current),
    )

    merged = _combine_segment_content(base_content, segment, text)
    if dry_run:
        return {
            "content": text,
            "full_content": merged,
            "dry_run": True,
        }

    chapter.content = merged
    chapter.word_count = len(merged)
    if chapter.status == "draft":
        chapter.status = "writing"
    db.commit()
    db.refresh(chapter)
    save_chapter_content(payload["novel_id"], chapter.chapter_number, merged)
    return {"content": text, "full_content": merged}


async def _execute_chat_job(db: Session, payload: dict, job_id: str) -> dict:
    proposal_result = _chat_entity_proposal(db, payload)
    if proposal_result:
        ai_job_service.set_running(job_id, "AI 已识别为待审阅卡片操作...")
        ai_job_service.update_partial(job_id, proposal_result["message"], "已生成待确认提案")
        return proposal_result

    clarification = clarification_for(payload.get("user_message") or "", payload.get("context_type") or "")
    if clarification:
        ai_job_service.set_running(job_id, "AI 正在澄清需求...")
        ai_job_service.update_partial(job_id, clarification["message"], "AI 已生成澄清问题")
        return {
            "message": clarification["message"],
            "mode": "clarify",
            "questions": clarification.get("questions") or [],
            "context_files": [],
        }

    base_context = context_builder.build_chat_context(
        db,
        payload["novel_id"],
        payload["context_type"],
        payload.get("context_id"),
    )
    smart_context = build_smart_chat_context(
        db,
        novel_id=payload["novel_id"],
        context_type=payload["context_type"],
        context_id=payload.get("context_id"),
        user_message=payload.get("user_message") or "",
        selected_file_ids=payload.get("context_files") or [],
        base_context=base_context,
    )
    system_prompt = smart_context["system_prompt"]
    messages = payload.get("messages") or []
    messages = [{"role": item["role"], "content": item["content"]} for item in messages]
    messages.append({"role": "user", "content": payload["user_message"]})

    ai_job_service.set_running(job_id, "AI 正在检索资料并组织回复...")
    accumulated = ""
    last_saved_length = 0
    try:
        async for chunk in ai_service.stream_generate_with_history(system_prompt, messages):
            accumulated += chunk
            if len(accumulated) - last_saved_length >= ai_job_service.PARTIAL_SAVE_INTERVAL:
                ai_job_service.update_partial(job_id, accumulated, "AI 正在组织回复...")
                last_saved_length = len(accumulated)
        ai_job_service.update_partial(job_id, accumulated, "AI 回复已生成，等待作者确认")

        # 检测是否包含大纲生成标记
        import re
        outline_match = re.search(r'<GENERATE_OUTLINE>(.*?)</GENERATE_OUTLINE>', accumulated, re.DOTALL)
        if outline_match and payload["context_type"] == "outline":
            idea = outline_match.group(1).strip()
            # 触发大纲生成
            novel = db.query(Novel).filter(Novel.id == payload["novel_id"]).first()
            if novel and idea:
                # 调用大纲生成逻辑
                outline_result = await _execute_outline_job(db, {"novel_id": payload["novel_id"], "idea": idea}, job_id)
                return {
                    "message": accumulated,
                    "outline_generated": True,
                    "outline": outline_result,
                    "context_files": smart_context["context_files"],
                    "mode": "answer",
                }

        return {
            "message": accumulated,
            "context_files": smart_context["context_files"],
            "search_terms": smart_context["terms"],
            "mode": "answer",
        }
    except Exception:
        if accumulated:
            ai_job_service.update_partial(job_id, accumulated, "AI 对话中断，已保留部分结果")
        raise


async def _process_job(job_id: str):
    db = SessionLocal()
    payload: dict = {}
    try:
        job = db.query(AIGenerationJob).filter(AIGenerationJob.id == job_id).first()
        if not job:
            return
        payload = ai_job_service.get_request_payload(job)
        result = None

        if job.job_type == "outline":
            result = await _execute_outline_job(db, payload, job_id)
        elif job.job_type == "titles":
            result = await _execute_titles_job(db, payload, job_id)
        elif job.job_type == "book_synopsis":
            result = await _execute_book_synopsis_job(db, payload, job_id)
        elif job.job_type == "book_volumes":
            result = await _execute_book_volumes_job(db, payload, job_id)
        elif job.job_type == "chapter_synopsis":
            result = await _execute_chapter_synopsis_job(db, payload, job_id)
        elif job.job_type == "chapter_content":
            result = await _execute_full_chapter_job(db, payload, job_id)
        elif job.job_type == "volume_synopsis":
            result = await _execute_volume_synopsis_job(db, payload, job_id)
        elif job.job_type == "characters":
            result = await _execute_characters_job(db, payload, job_id)
        elif job.job_type == "worldbuilding":
            result = await _execute_worldbuilding_job(db, payload, job_id)
        elif job.job_type == "chapter_segment":
            result = await _execute_chapter_segment_job(db, payload, job_id)
        elif job.job_type == "chat":
            result = await _execute_chat_job(db, payload, job_id)
        else:
            raise HTTPException(400, f"未知任务类型：{job.job_type}")

        ai_job_service.complete_job(job_id, result)
    except HTTPException as exc:
        current_job = ai_job_service.get_job(job_id)
        message_text = _error_message_from_detail(exc.detail)
        error_metadata = exc.detail if isinstance(exc.detail, dict) else {"message": message_text}
        if payload.get("outline_chat"):
            _add_outline_chat_message(
                db,
                novel_id=payload["novel_id"],
                role="system",
                content=message_text,
                metadata={"job_id": job_id, "status": "failed", "error_detail": error_metadata},
            )
        ai_job_service.fail_job(
            job_id,
            message_text,
            result_payload=exc.detail if isinstance(exc.detail, dict) else None,
            partial_text=current_job.partial_text if current_job else None,
        )
    except Exception as exc:
        current_job = ai_job_service.get_job(job_id)
        if payload.get("outline_chat"):
            _add_outline_chat_message(
                db,
                novel_id=payload["novel_id"],
                role="system",
                content=str(exc),
                metadata={"job_id": job_id, "status": "failed"},
            )
        ai_job_service.fail_job(
            job_id,
            str(exc),
            partial_text=current_job.partial_text if current_job else None,
        )
    finally:
        db.close()


def _queue_job(
    *,
    background_tasks: BackgroundTasks,
    db: Session,
    job_type: str,
    novel_id: str,
    request_payload: dict,
    chapter_id: str | None = None,
    volume_id: str | None = None,
) -> dict:
    job = ai_job_service.create_job(
        db=db,
        job_type=job_type,
        novel_id=novel_id,
        request_payload=request_payload,
        chapter_id=chapter_id,
        volume_id=volume_id,
    )
    background_tasks.add_task(_process_job, job.id)
    return ai_job_service.to_response(job)


@router.get("/jobs/{job_id}", response_model=AIGenerationJobOut)
def get_job_status(job_id: str, db: Session = Depends(get_db)):
    job = db.query(AIGenerationJob).filter(AIGenerationJob.id == job_id).first()
    if not job:
        raise HTTPException(404, "任务不存在")
    return ai_job_service.to_response(job)


@router.get("/jobs")
def list_jobs(novel_id: str, limit: int = 20, db: Session = Depends(get_db)):
    safe_limit = max(min(limit, 100), 1)
    jobs = db.query(AIGenerationJob).filter(
        AIGenerationJob.novel_id == novel_id
    ).order_by(AIGenerationJob.created_at.desc()).limit(safe_limit).all()
    return [ai_job_service.to_response(item) for item in jobs]


@router.get("/outline/messages")
def list_outline_messages(novel_id: str, db: Session = Depends(get_db)):
    messages = db.query(OutlineChatMessage).filter(
        OutlineChatMessage.novel_id == novel_id,
    ).order_by(OutlineChatMessage.created_at.asc()).all()
    return [_outline_chat_payload(item) for item in messages]


@router.post("/outline/chat", response_model=AIGenerationJobOut)
async def outline_chat(
    req: OutlineChatRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    novel = db.query(Novel).filter(Novel.id == req.novel_id).first()
    if not novel:
        raise HTTPException(404, "小说不存在")
    latest_outline = db.query(Outline).filter(Outline.novel_id == req.novel_id).order_by(Outline.version.desc()).first()
    message_text = _validate_outline_idea(req.message, allow_short=bool(latest_outline))
    _add_outline_chat_message(
        db,
        novel_id=req.novel_id,
        role="user",
        content=message_text,
        outline_id=latest_outline.id if latest_outline else None,
        metadata={"outline_version": latest_outline.version if latest_outline else None},
    )
    return _queue_job(
        background_tasks=background_tasks,
        db=db,
        job_type="outline",
        novel_id=req.novel_id,
        request_payload={
            "novel_id": req.novel_id,
            "idea": message_text,
            "outline_chat": True,
            "mode": req.mode or "revise",
        },
    )


@router.post("/generate/outline", response_model=AIGenerationJobOut)
async def generate_outline(
    req: GenerateOutlineRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    payload = req.model_dump()
    payload["idea"] = _validate_outline_idea(payload.get("idea", ""))
    return _queue_job(
        background_tasks=background_tasks,
        db=db,
        job_type="outline",
        novel_id=req.novel_id,
        request_payload=payload,
    )


@router.post("/generate/titles", response_model=AIGenerationJobOut)
async def generate_titles(
    req: GenerateTitlesRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    return _queue_job(
        background_tasks=background_tasks,
        db=db,
        job_type="titles",
        novel_id=req.novel_id,
        request_payload=req.model_dump(),
    )


@router.post("/generate/book-synopsis", response_model=AIGenerationJobOut)
async def generate_book_synopsis(
    req: GenerateBookSynopsisRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    return _queue_job(
        background_tasks=background_tasks,
        db=db,
        job_type="book_synopsis",
        novel_id=req.novel_id,
        request_payload=req.model_dump(),
    )


@router.post("/generate/book-volumes", response_model=AIGenerationJobOut)
async def generate_book_volumes(
    req: GenerateBookVolumesRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    return _queue_job(
        background_tasks=background_tasks,
        db=db,
        job_type="book_volumes",
        novel_id=req.novel_id,
        request_payload=req.model_dump(),
    )


@router.post("/generate/synopsis", response_model=AIGenerationJobOut)
async def generate_synopsis(
    req: GenerateSynopsisRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    return _queue_job(
        background_tasks=background_tasks,
        db=db,
        job_type="chapter_synopsis",
        novel_id=req.novel_id,
        request_payload=req.model_dump(),
        chapter_id=req.chapter_id,
    )


@router.post("/synopsis/create-missing-characters")
def create_missing_characters(req: CreateMissingCharactersRequest, db: Session = Depends(get_db)):
    raise HTTPException(410, "已停用自动补录角色，请通过待审阅提案手动确认新增角色")


@router.post("/generate/chapter", response_model=AIGenerationJobOut)
async def generate_chapter(
    req: GenerateChapterRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    return _queue_job(
        background_tasks=background_tasks,
        db=db,
        job_type="chapter_content",
        novel_id=req.novel_id,
        request_payload=req.model_dump(),
        chapter_id=req.chapter_id,
    )


@router.post("/generate/volume-synopsis", response_model=AIGenerationJobOut)
async def generate_volume_synopsis(
    req: GenerateVolumeSynopsisRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    return _queue_job(
        background_tasks=background_tasks,
        db=db,
        job_type="volume_synopsis",
        novel_id=req.novel_id,
        request_payload=req.model_dump(),
        volume_id=req.volume_id,
    )


@router.post("/generate/characters", response_model=AIGenerationJobOut)
async def generate_characters(
    req: GenerateCharactersFromOutlineRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    return _queue_job(
        background_tasks=background_tasks,
        db=db,
        job_type="characters",
        novel_id=req.novel_id,
        request_payload=req.model_dump(),
    )


@router.post("/generate/worldbuilding", response_model=AIGenerationJobOut)
async def generate_worldbuilding(
    req: GenerateWorldbuildingRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    return _queue_job(
        background_tasks=background_tasks,
        db=db,
        job_type="worldbuilding",
        novel_id=req.novel_id,
        request_payload=req.model_dump(),
    )


@router.post("/generate/chapter-segment", response_model=AIGenerationJobOut)
async def generate_chapter_segment(
    req: GenerateChapterSegmentRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    return _queue_job(
        background_tasks=background_tasks,
        db=db,
        job_type="chapter_segment",
        novel_id=req.novel_id,
        request_payload=req.model_dump(),
        chapter_id=req.chapter_id,
    )


@router.post("/chat", response_model=AIGenerationJobOut)
async def ai_chat(
    req: ChatRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    return _queue_job(
        background_tasks=background_tasks,
        db=db,
        job_type="chat",
        novel_id=req.novel_id,
        request_payload=req.model_dump(mode="json"),
        chapter_id=req.context_id if req.context_type == "chapter" else None,
    )


@router.post("/validate/synopsis-characters")
def validate_characters(req: ValidateSynopsisRequest, db: Session = Depends(get_db)):
    return validate_synopsis_characters(db, req.novel_id, req.characters_in_synopsis)
