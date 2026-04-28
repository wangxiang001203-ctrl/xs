from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import Character, Chapter, EntityEvent, EntityMention, EntityRelation, StoryEntity, Worldbuilding
from app.services.validator import collect_worldbuilding_entities
from app.services.worldbuilding_service import load_worldbuilding_document


ENTITY_TYPE_LABELS = {
    "character": "角色",
    "location": "地点",
    "faction": "势力",
    "item": "道具",
    "resource": "资源",
    "technique": "功法",
    "realm": "境界",
    "rule": "规则",
    "creature": "灵兽",
}

SECTION_ENTITY_TYPES = {
    "power_system": "realm",
    "techniques": "technique",
    "items": "item",
    "geography": "location",
    "factions": "faction",
    "core_rules": "rule",
}


def safe_text(value, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text or default


def normalize_aliases(values) -> list[str]:
    if not values:
        return []
    if isinstance(values, str):
        values = values.splitlines()
    result: list[str] = []
    for item in values:
        text = safe_text(item)
        if text and text not in result:
            result.append(text)
    return result


def entity_terms(entity: StoryEntity) -> list[tuple[str, str, float]]:
    terms: list[tuple[str, str, float]] = []
    if entity.name:
        terms.append((entity.name, "exact_match", 1.0))
    for alias in normalize_aliases(entity.aliases):
        if alias != entity.name:
            terms.append((alias, "alias_match", 0.95))
    return terms


def evidence_excerpt(content: str, term: str, radius: int = 80) -> str:
    index = content.find(term)
    if index < 0:
        return ""
    start = max(0, index - radius)
    end = min(len(content), index + len(term) + radius)
    return content[start:end].strip()


def get_or_create_entity(
    db: Session,
    *,
    novel_id: str,
    entity_type: str,
    name: str,
    aliases: list[str] | None = None,
    summary: str | None = None,
    body_md: str | None = None,
    first_appearance_chapter: int | None = None,
) -> StoryEntity:
    clean_name = safe_text(name)
    entity = db.query(StoryEntity).filter(
        StoryEntity.novel_id == novel_id,
        StoryEntity.entity_type == entity_type,
        StoryEntity.name == clean_name,
    ).first()
    if entity:
        next_aliases = normalize_aliases([*(entity.aliases or []), *(aliases or [])])
        entity.aliases = next_aliases
        if summary and not entity.summary:
            entity.summary = summary
        if body_md and not entity.body_md:
            entity.body_md = body_md
        if first_appearance_chapter and not entity.first_appearance_chapter:
            entity.first_appearance_chapter = first_appearance_chapter
        return entity

    entity = StoryEntity(
        novel_id=novel_id,
        entity_type=entity_type,
        name=clean_name,
        aliases=normalize_aliases(aliases),
        summary=safe_text(summary) or None,
        body_md=safe_text(body_md) or None,
        first_appearance_chapter=first_appearance_chapter,
        current_state={},
        status="active",
    )
    db.add(entity)
    db.flush()
    return entity


def bootstrap_entities_from_existing(db: Session, novel_id: str) -> int:
    before = db.query(StoryEntity).filter(StoryEntity.novel_id == novel_id).count()

    characters = db.query(Character).filter(Character.novel_id == novel_id).all()
    for char in characters:
        get_or_create_entity(
            db,
            novel_id=novel_id,
            entity_type="character",
            name=char.name,
            aliases=char.aliases or [],
            summary=char.motivation or char.personality,
            body_md=char.profile_md or char.background,
            first_appearance_chapter=char.first_appearance_chapter,
        )

    wb = db.query(Worldbuilding).filter(Worldbuilding.novel_id == novel_id).first()
    if wb:
        document = load_worldbuilding_document(novel_id, wb)
        section_type_map = {
            "power_system": "realm",
            "techniques": "technique",
            "items": "item",
            "geography": "location",
            "factions": "faction",
            "core_rules": "rule",
        }
        legacy_entities = collect_worldbuilding_entities(db, novel_id)
        for name in legacy_entities.get("items", set()):
            get_or_create_entity(db, novel_id=novel_id, entity_type="item", name=name)
        for name in legacy_entities.get("locations", set()):
            get_or_create_entity(db, novel_id=novel_id, entity_type="location", name=name)
        for name in legacy_entities.get("factions", set()):
            get_or_create_entity(db, novel_id=novel_id, entity_type="faction", name=name)
        for name in legacy_entities.get("realms", set()):
            get_or_create_entity(db, novel_id=novel_id, entity_type="realm", name=name)
        for name in legacy_entities.get("rules", set()):
            get_or_create_entity(db, novel_id=novel_id, entity_type="rule", name=name)

        for section in document.get("sections") or []:
            entity_type = section_type_map.get(safe_text(section.get("id")), "custom")
            section_name = safe_text(section.get("name"))
            if section_name and entity_type == "custom":
                lowered = section_name.lower()
                if "灵兽" in section_name or "creature" in lowered:
                    entity_type = "creature"
                elif "功法" in section_name or "技能" in section_name:
                    entity_type = "technique"
                elif "道具" in section_name or "资源" in section_name:
                    entity_type = "item"
            for entry in section.get("entries") or []:
                name = safe_text(entry.get("name"))
                if not name:
                    continue
                get_or_create_entity(
                    db,
                    novel_id=novel_id,
                    entity_type=entity_type,
                    name=name,
                    summary=safe_text(entry.get("summary")),
                    body_md=safe_text(entry.get("details")),
                )

    db.flush()
    after = db.query(StoryEntity).filter(StoryEntity.novel_id == novel_id).count()
    return max(after - before, 0)


def sync_worldbuilding_entities(db: Session, novel_id: str, document: dict) -> int:
    """世界观分类页是用户入口，底层实体索引只跟随结构化条目同步。"""
    changed = 0
    for section in document.get("sections") or []:
        section_id = safe_text(section.get("id"))
        entity_type = SECTION_ENTITY_TYPES.get(section_id, "custom")
        if entity_type == "custom":
            section_name = safe_text(section.get("name"))
            if "灵兽" in section_name:
                entity_type = "creature"
            elif "地点" in section_name or "地图" in section_name:
                entity_type = "location"
            elif "势力" in section_name or "组织" in section_name:
                entity_type = "faction"
            elif "道具" in section_name or "资源" in section_name:
                entity_type = "item"
            elif "功法" in section_name or "技能" in section_name:
                entity_type = "technique"

        for entry in section.get("entries") or []:
            name = safe_text(entry.get("name"))
            if not name:
                continue
            entity = get_or_create_entity(
                db,
                novel_id=novel_id,
                entity_type=entity_type,
                name=name,
            )
            before = {
                "summary": entity.summary,
                "body_md": entity.body_md,
                "tags": entity.tags,
                "current_state": entity.current_state,
            }
            entity.summary = safe_text(entry.get("summary")) or entity.summary
            entity.body_md = safe_text(entry.get("details")) or entity.body_md
            entity.tags = normalize_aliases(entry.get("tags") or [])
            attributes = entry.get("attributes") if isinstance(entry.get("attributes"), dict) else {}
            if attributes:
                state = dict(entity.current_state or {})
                state.update({key: value for key, value in attributes.items() if safe_text(value)})
                entity.current_state = state
            after = {
                "summary": entity.summary,
                "body_md": entity.body_md,
                "tags": entity.tags,
                "current_state": entity.current_state,
            }
            if before != after:
                changed += 1
    db.flush()
    return changed


def scan_chapter_mentions(db: Session, novel_id: str, chapter: Chapter) -> int:
    content = chapter.content or ""
    if not content.strip():
        return 0
    entities = db.query(StoryEntity).filter(
        StoryEntity.novel_id == novel_id,
        StoryEntity.status != "deleted",
    ).all()
    created = 0
    for entity in entities:
        for term, source, confidence in entity_terms(entity):
            if not term or term not in content:
                continue
            exists = db.query(EntityMention).filter(
                EntityMention.novel_id == novel_id,
                EntityMention.entity_id == entity.id,
                EntityMention.chapter_id == chapter.id,
                EntityMention.mention_text == term,
                EntityMention.source == source,
            ).first()
            if exists:
                continue
            mention = EntityMention(
                novel_id=novel_id,
                entity_id=entity.id,
                chapter_id=chapter.id,
                chapter_number=chapter.chapter_number,
                mention_text=term,
                source=source,
                confidence=confidence,
                evidence_text=evidence_excerpt(content, term),
            )
            db.add(mention)
            created += 1
            if not entity.first_appearance_chapter or chapter.chapter_number < entity.first_appearance_chapter:
                entity.first_appearance_chapter = chapter.chapter_number
            break
    db.flush()
    return created


def scan_novel_mentions(db: Session, novel_id: str, chapter_id: str | None = None) -> tuple[int, int]:
    query = db.query(Chapter).filter(Chapter.novel_id == novel_id)
    if chapter_id:
        query = query.filter(Chapter.id == chapter_id)
    chapters = query.order_by(Chapter.chapter_number.asc()).all()
    created = 0
    for chapter in chapters:
        created += scan_chapter_mentions(db, novel_id, chapter)
    return len(chapters), created


def recompute_entity_state(db: Session, entity: StoryEntity) -> dict:
    events = db.query(EntityEvent).filter(
        EntityEvent.entity_id == entity.id,
        EntityEvent.status == "active",
    ).order_by(
        EntityEvent.chapter_number.is_(None),
        EntityEvent.chapter_number.asc(),
        EntityEvent.created_at.asc(),
    ).all()
    state: dict = {}
    for event in events:
        if isinstance(event.to_state, dict):
            state.update(event.to_state)
        if isinstance(event.delta, dict):
            state.update(event.delta)
    entity.current_state = state
    db.flush()
    return state


def state_at_chapter(db: Session, entity: StoryEntity, chapter_number: int | None) -> dict:
    query = db.query(EntityEvent).filter(
        EntityEvent.entity_id == entity.id,
        EntityEvent.status == "active",
    )
    if chapter_number is not None:
        query = query.filter(
            (EntityEvent.chapter_number == None) | (EntityEvent.chapter_number <= chapter_number)  # noqa: E711
        )
    events = query.order_by(
        EntityEvent.chapter_number.is_(None),
        EntityEvent.chapter_number.asc(),
        EntityEvent.created_at.asc(),
    ).all()
    state: dict = {}
    for event in events:
        if isinstance(event.to_state, dict):
            state.update(event.to_state)
        if isinstance(event.delta, dict):
            state.update(event.delta)
    return state


def create_entity_event(db: Session, *, novel_id: str, entity: StoryEntity, payload: dict) -> EntityEvent:
    event = EntityEvent(
        novel_id=novel_id,
        entity_id=entity.id,
        event_type=safe_text(payload.get("event_type"), "manual_fix"),
        chapter_id=payload.get("chapter_id"),
        chapter_number=payload.get("chapter_number"),
        title=safe_text(payload.get("title")) or None,
        from_state=payload.get("from_state") or {},
        to_state=payload.get("to_state") or {},
        delta=payload.get("delta") or {},
        source=safe_text(payload.get("source"), "manual"),
        confidence=float(payload.get("confidence", 1.0) or 1.0),
        evidence_text=safe_text(payload.get("evidence_text")) or None,
        reason=safe_text(payload.get("reason")) or None,
        status=safe_text(payload.get("status"), "active"),
    )
    db.add(event)
    db.flush()
    recompute_entity_state(db, entity)
    if event.chapter_number and (not entity.first_appearance_chapter or event.chapter_number < entity.first_appearance_chapter):
        entity.first_appearance_chapter = event.chapter_number
    return event


def close_relation(db: Session, relation: EntityRelation, end_chapter: int | None = None):
    relation.status = "ended"
    relation.end_chapter = end_chapter
    db.flush()
