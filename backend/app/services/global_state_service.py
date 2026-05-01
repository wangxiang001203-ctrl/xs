"""
三层记忆架构服务：
  L0: 原始数据（Chapter, ChapterMemory, Character, EntityEvent 等）
  L1: 10章聚合快照（ChapterSnapshot）
  L2: 全局知识索引（NovelGlobalState）
"""
from datetime import datetime

from sqlalchemy.orm import Session

from app.models import (
    Chapter, ChapterMemory, ChapterSnapshot,
    Character, StoryEntity, EntityEvent, EntityRelation,
)
from app.schemas.global_state import (
    NovelGlobalState,
    ChapterSnapshotOut,
    GlobalCharacterStatus,
    GlobalItemStatus,
    GlobalLocationStatus,
    GlobalEventEntry,
    UnresolvedForeshadowing,
)


def build_global_state(db: Session, novel_id: str) -> NovelGlobalState:
    """构建 L2 全局知识索引。"""

    # L0 基础统计
    chapters = db.query(Chapter).filter(Chapter.novel_id == novel_id).order_by(Chapter.chapter_number).all()
    total_chapters = len(chapters)
    total_words = sum(c.word_count or 0 for c in chapters)
    approved_chapters = sum(1 for c in chapters if c.final_approved)
    latest_chapter_number = chapters[-1].chapter_number if chapters else 0

    # L1 聚合快照
    snapshots_raw = (
        db.query(ChapterSnapshot)
        .filter(ChapterSnapshot.novel_id == novel_id)
        .order_by(ChapterSnapshot.start_chapter)
        .all()
    )
    snapshots: list[ChapterSnapshotOut] = [
        ChapterSnapshotOut(
            id=s.id,
            novel_id=s.novel_id,
            start_chapter=s.start_chapter,
            end_chapter=s.end_chapter,
            summary=s.summary,
            key_events=s.key_events or [],
            character_arcs=s.character_arcs or [],
            item_changes=s.item_changes or [],
            open_threads=s.open_threads or [],
            foreshadowing=s.foreshadowing or [],
            created_at=s.created_at.isoformat() if s.created_at else "",
        )
        for s in snapshots_raw
    ]

    # L2 全局知识索引：角色状态
    characters_raw = db.query(Character).filter(Character.novel_id == novel_id).all()
    characters: list[GlobalCharacterStatus] = [
        GlobalCharacterStatus(
            character_id=c.id,
            name=c.name,
            current_realm=c.realm or "未设定",
            current_location="未知",
            current_faction=c.faction or "无",
            importance=c.importance or 0,
            status=c.status or "alive",
        )
        for c in characters_raw
    ]

    # 从实体中提取道具和地点
    entities = db.query(StoryEntity).filter(StoryEntity.novel_id == novel_id).all()

    items: list[GlobalItemStatus] = []
    locations: list[GlobalLocationStatus] = []
    for e in entities:
        if e.entity_type == "item" or e.entity_type == "artifact":
            items.append(GlobalItemStatus(
                item_id=e.id,
                name=e.name,
                grade=e.current_state.get("grade", "") if e.current_state else "",
                current_holder=e.current_state.get("holder_id", "") if e.current_state else "",
                holder_name=e.current_state.get("holder_name", "未知") if e.current_state else "未知",
                location=e.current_state.get("location", "") if e.current_state else "",
            ))
        elif e.entity_type == "location":
            locations.append(GlobalLocationStatus(
                location_id=e.id,
                name=e.name,
                type=e.current_state.get("type", "") if e.current_state else "",
                current_state=e.current_state.get("state", "正常") if e.current_state else "正常",
                significance=e.summary or "",
            ))

    # 从 EntityEvent 构建事件时间线
    events_raw = (
        db.query(EntityEvent)
        .filter(EntityEvent.novel_id == novel_id, EntityEvent.status == "confirmed")
        .order_by(EntityEvent.chapter_number)
        .all()
    )
    event_timeline: list[GlobalEventEntry] = [
        GlobalEventEntry(
            chapter_number=e.chapter_number or 0,
            title=e.title or e.event_type,
            event_type=e.event_type,
            entities_involved=[],
            description=e.from_state.get("description", "") if e.from_state else "",
        )
        for e in events_raw[-50:]  # 只取最近50个事件
    ]

    # 从 ChapterMemory 收集未回收伏笔
    all_memories = db.query(ChapterMemory).filter(ChapterMemory.novel_id == novel_id).all()
    open_threads: list[str] = []
    for mem in all_memories:
        open_threads.extend(mem.open_threads or [])

    # 去重并取最近20条
    open_threads = list(dict.fromkeys(open_threads))[:20]

    # 伏笔追踪
    unresolved_foreshadowing: list[UnresolvedForeshadowing] = []
    for mem in all_memories:
        for thread in (mem.open_threads or []):
            unresolved_foreshadowing.append(UnresolvedForeshadowing(
                thread=thread,
                introduced_chapter=mem.chapter_number,
                related_entities=[],
            ))

    return NovelGlobalState(
        total_chapters=total_chapters,
        total_words=total_words,
        approved_chapters=approved_chapters,
        latest_chapter_number=latest_chapter_number,
        snapshots=snapshots,
        characters=characters,
        items=items,
        locations=locations,
        event_timeline=event_timeline,
        open_threads=open_threads,
        unresolved_foreshadowing=unresolved_foreshadowing[:20],
        updated_at=datetime.utcnow().isoformat(),
    )


def aggregate_snapshot(db: Session, novel_id: str, start_chapter: int, end_chapter: int) -> ChapterSnapshot:
    """每10章结束时自动触发：将10章的 ChapterMemory 聚合成一个快照。"""
    memories = (
        db.query(ChapterMemory)
        .filter(
            ChapterMemory.novel_id == novel_id,
            ChapterMemory.chapter_number >= start_chapter,
            ChapterMemory.chapter_number <= end_chapter,
        )
        .order_by(ChapterMemory.chapter_number)
        .all()
    )

    if not memories:
        # 没有记忆时，尝试从各章内容中生成一个简单摘要
        chapters = (
            db.query(Chapter)
            .filter(
                Chapter.novel_id == novel_id,
                Chapter.chapter_number >= start_chapter,
                Chapter.chapter_number <= end_chapter,
            )
            .order_by(Chapter.chapter_number)
            .all()
        )
        summary = f"第{start_chapter}-{end_chapter}章，共{sum(c.word_count or 0 for c in chapters)}字"
        key_events: list[str] = []
        character_arcs: list[str] = []
        item_changes: list[str] = []
        open_threads: list[str] = []
        foreshadowing: list[str] = []
    else:
        # 聚合所有记忆
        summary_parts = [m.summary for m in memories if m.summary]
        summary = " / ".join(summary_parts[:3]) if summary_parts else f"第{start_chapter}-{end_chapter}章"

        key_events = list(dict.fromkeys(e for m in memories for e in (m.key_events or [])))[:10]
        character_arcs = []
        item_changes = list(dict.fromkeys(i for m in memories for i in (m.inventory_changes or [])))[:5]
        open_threads = list(dict.fromkeys(t for m in memories for t in (m.open_threads or [])))
        foreshadowing = list(dict.fromkeys(f for m in memories for f in (m.open_threads or [])))

    snapshot = ChapterSnapshot(
        novel_id=novel_id,
        start_chapter=start_chapter,
        end_chapter=end_chapter,
        summary=summary[:1000],
        key_events=key_events,
        character_arcs=character_arcs,
        item_changes=item_changes,
        open_threads=open_threads,
        foreshadowing=foreshadowing,
    )
    db.add(snapshot)
    db.commit()
    db.refresh(snapshot)
    return snapshot
