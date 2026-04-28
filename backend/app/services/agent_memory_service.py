from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import AIWorkflowRun, Character, Chapter, ChapterMemory, Novel, Outline, Worldbuilding
from app.services.agent_contracts import AgentFileRef, MemoryPack
from app.services.assistant_service import build_file_catalog, extract_search_terms, file_matches
from app.services.worldbuilding_service import load_worldbuilding_document, summarize_worldbuilding_document


def build_memory_pack(
    db: Session,
    *,
    novel_id: str,
    query: str,
    context_type: str,
    selected_file_ids: list[str] | None = None,
    limit_files: int = 12,
) -> MemoryPack:
    """Build product-owned long memory.

    This intentionally does not depend on any model provider's hidden memory.
    Confirmed files, cards and chapter memories remain the source of truth.
    """

    selected_file_ids = selected_file_ids or []
    terms = extract_search_terms(query)
    catalog = build_file_catalog(db, novel_id)
    files = []
    selected = set(selected_file_ids)

    for file in catalog:
        if file.id in selected or file.kind in selected:
            files.append(file)

    priority_kinds = {
        "outline": {"outline"},
        "synopsis": {"outline", "synopsis"},
        "characters": {"outline", "characters"},
        "worldbuilding": {"outline", "characters", "worldbuilding", "worldbuilding_section"},
        "chapter": {"outline", "volume", "chapter_synopsis", "chapter_memory", "characters", "worldbuilding", "worldbuilding_section"},
    }.get(context_type, {"outline", "characters", "worldbuilding", "worldbuilding_section"})
    for file in catalog:
        if file.kind in priority_kinds and file not in files:
            files.append(file)

    for term in terms:
        for file in catalog:
            if file not in files and file_matches(file, term):
                files.append(file)

    facts: list[str] = []
    novel = db.query(Novel).filter(Novel.id == novel_id).first()
    if novel:
        facts.append(f"作品名：{novel.title}；类型：{novel.genre or '未设置'}；状态：{novel.status or 'draft'}")

    outline = db.query(Outline).filter(Outline.novel_id == novel_id).order_by(Outline.version.desc()).first()
    if outline:
        facts.append(f"最新大纲：v{outline.version}，{'已确认' if outline.confirmed else '未确认'}")
        if outline.title:
            facts.append(f"大纲标题草案：{outline.title}")
        if outline.synopsis:
            facts.append(f"大纲内简介：{outline.synopsis[:180]}")

    characters = db.query(Character).filter(Character.novel_id == novel_id).limit(20).all()
    for char in characters:
        facts.append(f"角色：{char.name}｜{char.role or '未定'}｜状态 {char.status or '未知'}｜境界 {char.realm or '未记录'}")

    wb = db.query(Worldbuilding).filter(Worldbuilding.novel_id == novel_id).first()
    if wb:
        doc = load_worldbuilding_document(novel_id, wb)
        overview = summarize_worldbuilding_document(doc)
        if overview:
            facts.append(f"世界观摘要：{overview[:260]}")

    chapter_memories: list[str] = []
    memories = (
        db.query(ChapterMemory, Chapter)
        .join(Chapter, Chapter.id == ChapterMemory.chapter_id)
        .filter(Chapter.novel_id == novel_id)
        .order_by(Chapter.chapter_number.desc())
        .limit(20)
        .all()
    )
    for memory, chapter in memories:
        bits = [memory.summary or ""]
        if memory.key_events:
            bits.append("事件：" + "；".join(memory.key_events[:4]))
        if memory.state_changes:
            bits.append("状态：" + "；".join(memory.state_changes[:4]))
        if memory.inventory_changes:
            bits.append("归属：" + "；".join(memory.inventory_changes[:4]))
        text = "；".join(item for item in bits if item)
        if text:
            chapter_memories.append(f"第{chapter.chapter_number}章：{text}")

    recent_runs: list[str] = []
    runs = (
        db.query(AIWorkflowRun)
        .filter(AIWorkflowRun.novel_id == novel_id)
        .order_by(AIWorkflowRun.created_at.desc())
        .limit(8)
        .all()
    )
    for run in runs:
        summary = (run.result_summary or run.intent or "").strip()
        if summary:
            recent_runs.append(f"{run.context_type}｜{run.intent or 'unknown'}｜{summary[:160]}")

    return MemoryPack(
        source_files=[
            AgentFileRef(id=file.id, label=file.label, path=file.path, kind=file.kind)
            for file in files[:limit_files]
        ],
        facts=facts[:30],
        chapter_memories=chapter_memories[:20],
        recent_runs=recent_runs,
        search_terms=terms,
    )
