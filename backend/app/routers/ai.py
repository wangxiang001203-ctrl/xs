import json
import re

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import SessionLocal, get_db
from app.models import AIGenerationJob, Character, Novel, ChapterMemory, EntityProposal
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
    GenerateChapterRequest,
    GenerateChapterSegmentRequest,
    GenerateCharactersFromOutlineRequest,
    GenerateOutlineRequest,
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


def _prompt_config() -> dict[str, str]:
    config = get_workflow_config()
    prompts = config.get("prompts") or {}
    return {
        "global_system": prompts.get("global_system") or SYSTEM_NOVEL,
        "outline_generation": prompts.get("outline_generation") or "请生成完整小说大纲。",
        "titles_generation": prompts.get("titles_generation") or "请输出10个标题候选。",
        "book_synopsis_generation": prompts.get("book_synopsis_generation") or "请输出小说简介。",
    }


def _extract_json(text: str):
    m = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", text)
    if m:
        return m.group(1).strip()
    return text.strip()


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
            lines.append(f"- **{name}**：{desc}")
        else:
            lines.append(f"- {name or desc}")
    return lines


def _render_outline_markdown(title: str, synopsis: str, outline_struct: dict) -> str:
    protagonist = outline_struct.get("protagonist") or {}
    core_cast = outline_struct.get("core_cast") or []
    world_seed = outline_struct.get("world_seed") or {}
    selling_points = outline_struct.get("selling_points") or []
    volumes = outline_struct.get("volumes") or []

    parts = [f"# {title or '暂定书名'}", "", "## 简介", synopsis or "（待补充）", ""]

    parts.append("## 核心卖点")
    if selling_points:
        parts.extend([f"- {item}" for item in selling_points])
    else:
        parts.append("（待补充）")
    parts.append("")

    parts.append("## 故事定位")
    parts.append(f"- 类型：{outline_struct.get('genre') or '玄幻修仙'}")
    parts.append(f"- 一句话定位：{outline_struct.get('story_positioning') or '待补充'}")
    parts.append(f"- 核心冲突：{outline_struct.get('core_conflict') or '待补充'}")
    parts.append(f"- 目标总字数：{outline_struct.get('target_total_words') or 0}")
    parts.append("")

    parts.append("## 主角设定")
    parts.append(f"- 姓名：{protagonist.get('name') or '待定'}")
    parts.append(f"- 出身背景：{protagonist.get('background') or '待补充'}")
    parts.append(f"- 金手指：{protagonist.get('golden_finger') or '待补充'}")
    parts.append(f"- 核心动机：{protagonist.get('motivation') or '待补充'}")
    parts.append(f"- 当前境界：{protagonist.get('realm') or '待定'}")
    parts.append(f"- 所属阵营：{protagonist.get('faction') or '待定'}")
    parts.append(f"- 性格基调：{protagonist.get('personality') or '待补充'}")
    parts.append("")

    parts.append("## 核心角色")
    if core_cast:
        for item in core_cast:
            parts.append(f"### {item.get('name') or '待定角色'}")
            parts.append(f"- 定位：{item.get('role') or '配角'}")
            parts.append(f"- 性格：{item.get('personality') or '待补充'}")
            parts.append(f"- 背景：{item.get('background') or '待补充'}")
            parts.append(f"- 金手指/特殊点：{item.get('golden_finger') or '无'}")
            parts.append(f"- 动机：{item.get('motivation') or '待补充'}")
            parts.append(f"- 境界：{item.get('realm') or '待定'}")
            parts.append(f"- 阵营：{item.get('faction') or '待定'}")
            parts.append("")
    else:
        parts.append("（待补充）")
        parts.append("")

    parts.append("## 世界观种子")
    world_sections = [
        ("修炼体系", _render_named_list(world_seed.get("cultivation_system") or [])),
        ("主要势力", _render_named_list(world_seed.get("major_factions") or [], desc_key="description")),
        ("主要地域", _render_named_list(world_seed.get("major_regions") or [])),
        ("核心规则", _render_named_list(world_seed.get("core_rules") or [], name_key="rule_name", desc_key="description")),
        ("关键宝物", _render_named_list(world_seed.get("treasures") or [])),
    ]
    for section_name, lines in world_sections:
        parts.append(f"### {section_name}")
        parts.extend(lines or ["（待补充）"])
        parts.append("")

    parts.append("## 分卷规划")
    for item in volumes:
        parts.append(f"### 第{item.get('volume_no', 0)}卷 {item.get('title') or '待定卷名'}")
        parts.append(f"- 目标字数：{item.get('target_words') or 0}")
        parts.append(f"- 预计章节数：{item.get('chapter_count') or 0}")
        parts.append(f"- 本卷主线：{item.get('main_line') or '待补充'}")
        parts.append(f"- 人物成长：{item.get('character_arc') or '待补充'}")
        parts.append(f"- 卷末钩子：{item.get('ending_hook') or '待补充'}")
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

    prompt_cfg = _prompt_config()
    prompt = f"""{prompt_cfg['outline_generation']}

想法：{payload['idea']}
类型：{novel.genre}

你必须严格输出 JSON（不要解释）：
```json
{{
  "title_draft": "暂定书名",
  "book_synopsis_draft": "100-180字的读者向简介草稿",
  "outline_struct": {{
    "selling_points": [
      "卖点1（读者爽点）",
      "卖点2（冲突/反转）",
      "卖点3（差异化）"
    ],
    "story_positioning": "一句话定位（谁在什么世界完成什么目标）",
    "core_conflict": "主角长期冲突与终局对手",
    "target_total_words": 180000,
    "protagonist": {{
      "name": "主角名",
      "background": "主角出身与起点",
      "golden_finger": "主角的核心外挂/机缘",
      "motivation": "主角最核心的执念",
      "realm": "开局境界",
      "faction": "当前阵营/宗门",
      "personality": "性格基调"
    }},
    "core_cast": [
      {{
        "name": "角色名",
        "role": "主角/女主/反派/导师/配角",
        "personality": "性格特征",
        "background": "背景与立场",
        "golden_finger": "特殊能力，没有填无",
        "motivation": "核心动机",
        "realm": "大致境界",
        "faction": "所属阵营"
      }}
    ],
    "world_seed": {{
      "cultivation_system": [
        {{"name": "境界名", "description": "该境界的关键特征"}}
      ],
      "major_factions": [
        {{"name": "势力名", "description": "势力定位与作用"}}
      ],
      "major_regions": [
        {{"name": "地域名", "description": "地域特色与功能"}}
      ],
      "core_rules": [
        {{"rule_name": "规则名", "description": "规则限制与影响"}}
      ],
      "treasures": [
        {{"name": "宝物/资源名", "description": "作用与稀缺性"}}
      ]
    }},
    "volumes": [
      {{
        "volume_no": 1,
        "title": "卷名",
        "target_words": 30000,
        "chapter_count": 12,
        "main_line": "本卷主线目标",
        "character_arc": "本卷人物成长/关系变化",
        "ending_hook": "卷末留下的悬念"
      }}
    ]
  }}
}}
```"""

    response_text = await ai_job_service.collect_text(
        job_id=job_id,
        system_prompt=prompt_cfg["global_system"],
        user_prompt=prompt,
        progress_message="AI 正在推演大纲结构，请稍候...",
    )
    data = json.loads(_extract_json(response_text))
    outline_struct = _normalize_outline_struct(data, novel.genre)
    title_draft = _safe_text(data.get("title_draft"), novel.title or "暂定书名")
    synopsis_draft = _safe_text(data.get("book_synopsis_draft"), "（待补充）")
    selling_points_text = "\n".join([f"- {item}" for item in (outline_struct.get("selling_points") or [])])
    content_md = _render_outline_markdown(title_draft, synopsis_draft, outline_struct)

    last = db.query(Outline).filter(Outline.novel_id == payload["novel_id"]).order_by(Outline.version.desc()).first()
    version = (last.version + 1) if last else 1

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
    )
    db.add(outline)
    novel.idea = payload["idea"]
    db.commit()
    db.refresh(outline)
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
【当前书名】{novel.title}
【大纲摘要】
{outline.content[:2000]}

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
    titles = json.loads(_extract_json(full_text))
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
    data = json.loads(_extract_json(full_text))

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

    text = await ai_job_service.collect_text(
        job_id=job_id,
        system_prompt=SYSTEM_NOVEL,
        user_prompt=prompt,
        progress_message="AI 正在生成正文...",
        on_partial=lambda current: _persist_full_chapter_partial(payload["chapter_id"], current),
    )
    chapter.content = text
    chapter.word_count = len(text)
    if chapter.status == "draft":
        chapter.status = "writing"
    db.commit()
    db.refresh(chapter)
    save_chapter_content(payload["novel_id"], chapter.chapter_number, text)
    return _serialize_chapter(chapter)


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
    batch_size = 8

    for start in range(0, len(chapters), batch_size):
        batch = chapters[start:start + batch_size]
        prompt = context_builder.build_volume_synopsis_context(
            db,
            payload["novel_id"],
            payload["volume_id"],
            chapter_numbers=[chapter.chapter_number for chapter in batch],
        )
        if payload.get("extra_instruction"):
            prompt += f"\n\n额外要求：{payload['extra_instruction']}"

        full_text = await ai_job_service.collect_text(
            job_id=job_id,
            system_prompt=SYSTEM_NOVEL,
            user_prompt=prompt,
            progress_message=f"AI 正在生成本卷细纲（第{start + 1}-{start + len(batch)}章 / 共{len(chapters)}章）...",
        )
        synopsis_list = json.loads(_extract_json(full_text))

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

请根据大纲的背景和剧情，提取并生成这部小说中最核心的 3-5 个人物（例如：男主、女主、主要反派、核心导师）。
你必须严格按照以下 JSON 格式输出，不要输出任何额外的废话：
```json
[
  {{
    "name": "姓名",
    "role": "主角/女主/反派/配角",
    "personality": "性格特征（如：杀伐果断、腹黑）",
    "appearance": "外貌描写",
    "background": "身世背景",
    "golden_finger": "金手指/特殊能力（如果不是主角可填无）",
    "motivation": "核心动机/执念（他为什么做这些事）"
  }}
]
```"""

    response_text = await ai_job_service.collect_text(
        job_id=job_id,
        system_prompt=SYSTEM_NOVEL,
        user_prompt=prompt,
        progress_message="AI 正在提取核心角色...",
    )
    data = json.loads(_extract_json(response_text))

    created_characters = []
    for char_data in data:
        existing = db.query(Character).filter(
            Character.novel_id == payload["novel_id"],
            Character.name == char_data.get("name"),
        ).first()
        if existing:
            continue
        char = Character(
            novel_id=payload["novel_id"],
            name=char_data.get("name"),
            role=char_data.get("role", "配角"),
            personality=char_data.get("personality"),
            appearance=char_data.get("appearance"),
            background=char_data.get("background"),
            golden_finger=char_data.get("golden_finger"),
            motivation=char_data.get("motivation"),
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
1. 这不是固定表单，栏目可以自由增删，但要围绕长篇写作真正会反复引用的设定来组织。
2. 如果故事明显涉及修炼、势力、地域、规则、关键物品，优先保留或补齐这些栏目。
3. 如果用户已经写了自定义栏目或 generation_hint，必须优先保留并补全，不要随意删掉。
4. 每个栏目下的 entries 只写对后续大纲、细纲、正文有帮助的内容，不要空泛凑字。
5. 可以新增例如“血脉体系”“宗门戒律”“秘境生态”“历史谜团”“禁忌”“职业体系”等自定义栏目。

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
      "entries": [
        {{
          "name": "设定名",
          "summary": "一句话定义",
          "details": "补充限制、代价、与剧情关系",
          "tags": ["可选标签"],
          "attributes": {{"type": "可选扩展字段"}}
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
    data = json.loads(_extract_json(response_text))

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

    text = await ai_job_service.collect_text(
        job_id=job_id,
        system_prompt=SYSTEM_NOVEL,
        user_prompt=prompt,
        progress_message="AI 正在生成正文片段...",
        on_partial=lambda current: _persist_segment_partial(payload["chapter_id"], segment, base_content, current),
    )

    merged = _combine_segment_content(base_content, segment, text)
    chapter.content = merged
    chapter.word_count = len(merged)
    if chapter.status == "draft":
        chapter.status = "writing"
    db.commit()
    db.refresh(chapter)
    save_chapter_content(payload["novel_id"], chapter.chapter_number, merged)
    return {"content": text, "full_content": merged}


async def _execute_chat_job(db: Session, payload: dict, job_id: str) -> dict:
    system_prompt = context_builder.build_chat_context(
        db,
        payload["novel_id"],
        payload["context_type"],
        payload.get("context_id"),
    )
    messages = payload.get("messages") or []
    messages = [{"role": item["role"], "content": item["content"]} for item in messages]
    messages.append({"role": "user", "content": payload["user_message"]})

    ai_job_service.set_running(job_id, "AI 正在回复...")
    accumulated = ""
    last_saved_length = 0
    try:
        async for chunk in ai_service.stream_generate_with_history(system_prompt, messages):
            accumulated += chunk
            if len(accumulated) - last_saved_length >= ai_job_service.PARTIAL_SAVE_INTERVAL:
                ai_job_service.update_partial(job_id, accumulated, "AI 正在回复...")
                last_saved_length = len(accumulated)
        ai_job_service.update_partial(job_id, accumulated, "AI 正在回复...")
        return {"message": accumulated}
    except Exception:
        if accumulated:
            ai_job_service.update_partial(job_id, accumulated, "AI 对话中断，已保留部分结果")
        raise


async def _process_job(job_id: str):
    db = SessionLocal()
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
        ai_job_service.fail_job(
            job_id,
            str(exc.detail),
            result_payload=exc.detail if isinstance(exc.detail, dict) else None,
            partial_text=current_job.partial_text if current_job else None,
        )
    except Exception as exc:
        current_job = ai_job_service.get_job(job_id)
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


@router.post("/generate/outline", response_model=AIGenerationJobOut)
async def generate_outline(
    req: GenerateOutlineRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    return _queue_job(
        background_tasks=background_tasks,
        db=db,
        job_type="outline",
        novel_id=req.novel_id,
        request_payload=req.model_dump(),
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
