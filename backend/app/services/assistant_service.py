from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.models import Character, Chapter, ChapterMemory, Novel, Outline, Synopsis, Volume, Worldbuilding
from app.services.workflow_config_service import get_workflow_config
from app.services.worldbuilding_service import load_worldbuilding_document, summarize_worldbuilding_document


@dataclass
class AssistantFile:
    id: str
    label: str
    path: str
    kind: str
    content: str


VAGUE_PATTERNS = [
    r"^帮我写个?大纲$",
    r"^帮我写一个大纲$",
    r"^生成大纲$",
    r"^写大纲$",
    r"^(?:请|麻烦)?(?:帮|给|替)?我?(?:写|生成|创建|做|弄|起草|出)(?:一下|一个|一份|个|份)?(?:小说|故事|作品)?(?:的)?(?:大纲|故事大纲|作品大纲|小说大纲)(?:吧|呗|可以吗|行吗)?[。.!！?？]*$",
    r"^继续$",
    r"^改一下$",
    r"^优化一下$",
    r"^润色一下$",
    r"^补一下$",
    r"^搞一下$",
]


def _text(value: Any, limit: int | None = None) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if limit and len(text) > limit:
        return f"{text[:limit]}..."
    return text


def _chapter_dir(number: int | None) -> str:
    return f"chapter_{int(number or 0):03d}"


def _outline_content(outline: Outline | None) -> str:
    if not outline:
        return ""
    return "\n\n".join(
        item
        for item in [
            f"标题：{outline.title or ''}",
            f"简介：{outline.synopsis or ''}",
            f"卖点：{outline.selling_points or ''}",
            f"主线：{outline.main_plot or ''}",
            outline.content or "",
        ]
        if item.strip()
    )


def _characters_content(characters: list[Character]) -> str:
    parts: list[str] = []
    for char in characters:
        parts.append(
            "\n".join(
                item
                for item in [
                    f"## {char.name}",
                    f"定位：{char.role or '未知'}；状态：{char.status or '未知'}；能力：{char.realm or '未记录'}；势力：{char.faction or '未记录'}",
                    f"别名：{'、'.join(char.aliases or [])}" if char.aliases else "",
                    char.motivation or "",
                    char.profile_md or char.background or "",
                ]
                if item.strip()
            )
        )
    return "\n\n".join(parts)


def _worldbuilding_section_content(section: dict) -> str:
    entries = []
    for entry in section.get("entries") or []:
        attrs = entry.get("attributes") if isinstance(entry.get("attributes"), dict) else {}
        attr_text = "；".join(f"{key}={value}" for key, value in attrs.items() if _text(value))
        entries.append(
            "\n".join(
                item
                for item in [
                    f"## {_text(entry.get('name'), 120)}",
                    _text(entry.get("summary")),
                    attr_text,
                    _text(entry.get("details")),
                ]
                if item.strip()
            )
        )
    return "\n\n".join(
        item
        for item in [
            _text(section.get("description")),
            _text(section.get("content")),
            "\n\n".join(entries),
        ]
        if item.strip()
    )


def build_file_catalog(db: Session, novel_id: str) -> list[AssistantFile]:
    novel = db.query(Novel).filter(Novel.id == novel_id).first()
    title = novel.title if novel else "当前作品"
    files: list[AssistantFile] = []

    outline = db.query(Outline).filter(Outline.novel_id == novel_id).order_by(Outline.version.desc()).first()
    if outline:
        files.append(AssistantFile("outline", "总大纲", "outline/outline.md", "outline", _outline_content(outline)))
        if outline.synopsis:
            files.append(AssistantFile("book_synopsis", "作品简介", "book/synopsis.md", "synopsis", outline.synopsis))

    characters = db.query(Character).filter(Character.novel_id == novel_id).all()
    if characters:
        files.append(AssistantFile("characters", "角色设定", "characters/characters.json", "characters", _characters_content(characters)))

    wb = db.query(Worldbuilding).filter(Worldbuilding.novel_id == novel_id).first()
    if wb:
        doc = load_worldbuilding_document(novel_id, wb)
        files.append(AssistantFile("worldbuilding", "世界观总览", "world/worldbuilding.json", "worldbuilding", summarize_worldbuilding_document(doc)))
        for section in doc.get("sections") or []:
            section_id = _text(section.get("id")) or _text(section.get("name"))
            files.append(
                AssistantFile(
                    f"worldbuilding:{section_id}",
                    f"设定 · {_text(section.get('name'), 80)}",
                    f"world/sections/{section_id or 'section'}.json",
                    "worldbuilding_section",
                    _worldbuilding_section_content(section),
                )
            )

    volumes = db.query(Volume).filter(Volume.novel_id == novel_id).order_by(Volume.volume_number.asc()).all()
    for volume in volumes:
        content = "\n".join(
            item
            for item in [
                f"第{volume.volume_number}卷：{volume.title}",
                volume.description or "",
                volume.main_line or "",
                volume.character_arc or "",
                volume.ending_hook or "",
                volume.plan_markdown or "",
            ]
            if item.strip()
        )
        files.append(
            AssistantFile(
                f"volume:{volume.id}",
                f"第{volume.volume_number}卷细纲",
                f"volumes/volume_{volume.volume_number:02d}/plan.md",
                "volume",
                content,
            )
        )

    chapters = db.query(Chapter).filter(Chapter.novel_id == novel_id).order_by(Chapter.chapter_number.asc()).all()
    for chapter in chapters:
        number = chapter.chapter_number
        synopsis = db.query(Synopsis).filter(Synopsis.chapter_id == chapter.id).first()
        if synopsis:
            synopsis_content = "\n".join(
                item
                for item in [
                    synopsis.summary_line or "",
                    synopsis.content_md or "",
                    synopsis.plot_summary_update or "",
                    "、".join(synopsis.development_events or []),
                ]
                if item.strip()
            )
            files.append(
                AssistantFile(
                    f"chapter_synopsis:{chapter.id}",
                    f"第{number}章细纲",
                    f"chapters/{_chapter_dir(number)}/synopsis.json",
                    "chapter_synopsis",
                    synopsis_content,
                )
            )
        if chapter.content:
            files.append(
                AssistantFile(
                    f"chapter_content:{chapter.id}",
                    f"第{number}章正文",
                    f"chapters/{_chapter_dir(number)}/content.md",
                    "chapter_content",
                    chapter.content,
                )
            )
        memory = db.query(ChapterMemory).filter(ChapterMemory.chapter_id == chapter.id).first()
        if memory:
            memory_content = "\n".join(
                item
                for item in [
                    memory.summary or "",
                    "关键事件：" + "；".join(memory.key_events or []),
                    "状态变化：" + "；".join(memory.state_changes or []),
                    "物品变化：" + "；".join(memory.inventory_changes or []),
                    "未回收：" + "；".join(memory.open_threads or []),
                ]
                if item.strip()
            )
            files.append(
                AssistantFile(
                    f"chapter_memory:{chapter.id}",
                    f"第{number}章记忆",
                    f"chapters/{_chapter_dir(number)}/memory.json",
                    "chapter_memory",
                    memory_content,
                )
            )

    if not files:
        files.append(AssistantFile("book", title, "book", "book", f"作品：{title}"))
    return files


def extract_search_terms(text: str) -> list[str]:
    terms: list[str] = []
    for number in re.findall(r"第\s*(\d+)\s*章", text):
        terms.extend([f"第{number}章", number])
    for quoted in re.findall(r"[“\"'「『](.+?)[”\"'」』]", text):
        if len(quoted.strip()) >= 2:
            terms.append(quoted.strip())
    for token in re.findall(r"[\u4e00-\u9fa5A-Za-z0-9]{2,}", text):
        if token in {"帮我", "参考", "内容", "完成", "修改", "生成", "设定", "大纲", "正文"}:
            continue
        terms.append(token)
    result: list[str] = []
    for term in terms:
        if term not in result:
            result.append(term)
    return result[:12]


def file_matches(file: AssistantFile, term: str) -> bool:
    haystack = f"{file.label}\n{file.path}\n{file.content}"
    return term in haystack


def excerpt(content: str, term: str, radius: int = 120) -> str:
    if not content:
        return ""
    index = content.find(term)
    if index < 0:
        return _text(content, 280)
    start = max(0, index - radius)
    end = min(len(content), index + len(term) + radius)
    return content[start:end].strip()


def select_context_files(
    files: list[AssistantFile],
    *,
    user_message: str,
    selected_file_ids: list[str] | None,
    context_type: str,
    limit: int = 8,
) -> list[AssistantFile]:
    selected_file_ids = selected_file_ids or []
    selected: list[AssistantFile] = []
    id_set = set(selected_file_ids)

    for file in files:
        if file.id in id_set or file.kind in id_set:
            selected.append(file)

    policy = get_workflow_config().get("assistant_policy") or {}
    configured = (policy.get("default_read_kinds") or {}).get(context_type)
    default_kinds = set(configured) if isinstance(configured, list) and configured else {
        "outline": {"outline"},
        "characters": {"characters", "outline"},
        "worldbuilding": {"worldbuilding", "worldbuilding_section", "outline", "characters"},
        "chapter": {"chapter_synopsis", "chapter_content", "chapter_memory", "characters", "worldbuilding", "worldbuilding_section", "volume"},
    }.get(context_type, {"outline", "characters", "worldbuilding"})
    for file in files:
        if file.kind in default_kinds and file not in selected:
            selected.append(file)

    terms = extract_search_terms(user_message)
    for term in terms:
        for file in files:
            if file in selected:
                continue
            if file_matches(file, term):
                selected.append(file)
                break

    return selected[:limit]


def clarification_for(user_message: str, context_type: str) -> dict | None:
    normalized = user_message.strip().replace(" ", "")
    if not normalized:
        return None
    is_vague = len(normalized) <= 8 or any(re.search(pattern, normalized) for pattern in VAGUE_PATTERNS)
    if not is_vague:
        return None

    if context_type == "outline" and "大纲" in normalized:
        questions = [
            {"question": "你想写什么类型？", "options": ["玄幻修仙", "都市异能", "科幻末世", "古言权谋"]},
            {"question": "主角开局是什么状态？", "options": ["废柴逆袭", "天才被废", "重生归来", "普通人误入修行"]},
            {"question": "核心爽点想放在哪？", "options": ["升级突破", "复仇打脸", "宗门争霸", "探索秘境"]},
        ]
    else:
        questions = [
            {"question": "你希望我做哪类事？", "options": ["生成新内容", "修改当前内容", "检查逻辑/连续性", "补充设定"]},
            {"question": "要参考哪些范围？", "options": ["当前文件", "当前章节", "指定章节", "全书设定"]},
            {"question": "结果怎么处理？", "options": ["只给建议", "生成待确认草稿", "列出需要修改的文件"]},
        ]
    lines = ["我需要先确认几个点，避免直接写歪："]
    for index, item in enumerate(questions, 1):
        lines.append(f"{index}. {item['question']}（{' / '.join(item['options'])}）")
    lines.append("你可以直接选项组合回复，比如：玄幻修仙 + 废柴逆袭 + 升级突破。")
    return {"message": "\n".join(lines), "questions": questions}


def build_smart_chat_context(
    db: Session,
    *,
    novel_id: str,
    context_type: str,
    context_id: str | None,
    user_message: str,
    selected_file_ids: list[str] | None,
    base_context: str,
) -> dict:
    files = build_file_catalog(db, novel_id)
    selected = select_context_files(
        files,
        user_message=user_message,
        selected_file_ids=selected_file_ids,
        context_type=context_type,
    )
    terms = extract_search_terms(user_message)
    context_blocks = []
    for file in selected:
        matched_term = next((term for term in terms if file_matches(file, term)), "")
        snippet = excerpt(file.content, matched_term) if matched_term else _text(file.content, 900)
        context_blocks.append(f"### {file.label}\n路径：{file.path}\n类型：{file.kind}\n片段：\n{snippet}")

    capability_prompt = f"""

【小说 AI 助手工作协议】
你不是单纯聊天机器人，而是小说创作工作台助手。你可以：
1. 先判断用户意图，不清楚时先提 2-4 个可选择问题，不要硬写。
2. 根据用户提到的章节号、角色名、设定名和关键词，参考系统提供的资料片段。
3. 如果需要修改内容，只能提出“待确认改动方案”，不能声称已经写入、删除或覆盖文件。
4. 必须列出“已参考资料”和“建议影响文件”。如果没有充分依据，要明确说需要作者确认。
5. 对已定稿章节、已出现设定、角色状态变化要保守处理，只能做追加或提出补录建议。
6. 输出尽量结构化：先给判断，再给方案/草稿，再列待确认改动。

【本次自动检索到的参考资料】
{chr(10).join(context_blocks) if context_blocks else "暂无可用资料。"}
"""
    return {
        "system_prompt": base_context + capability_prompt,
        "context_files": [
            {"id": file.id, "label": file.label, "path": file.path, "kind": file.kind}
            for file in selected
        ],
        "terms": terms,
    }
