from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import EntityEvent, EntityMention, EntityRelation, Novel, StoryEntity
from app.schemas.entity import (
    EntityEventCreate,
    EntityEventOut,
    EntityMentionOut,
    EntityRelationCreate,
    EntityRelationOut,
    EntityScanRequest,
    EntityScanResult,
    StoryEntityCreate,
    StoryEntityOut,
    StoryEntityUpdate,
)
from app.services.entity_service import (
    bootstrap_entities_from_existing,
    create_entity_event,
    normalize_aliases,
    recompute_entity_state,
    scan_novel_mentions,
    state_at_chapter,
)

router = APIRouter(prefix="/api/projects/{novel_id}/entities", tags=["entities"])


def ensure_novel(db: Session, novel_id: str):
    novel = db.query(Novel).filter(Novel.id == novel_id).first()
    if not novel:
        raise HTTPException(404, "小说不存在")
    return novel


def get_entity_or_404(db: Session, novel_id: str, entity_id: str) -> StoryEntity:
    entity = db.query(StoryEntity).filter(
        StoryEntity.id == entity_id,
        StoryEntity.novel_id == novel_id,
    ).first()
    if not entity:
        raise HTTPException(404, "实体不存在")
    return entity


@router.post("/bootstrap")
def bootstrap_entities(novel_id: str, db: Session = Depends(get_db)):
    ensure_novel(db, novel_id)
    created = bootstrap_entities_from_existing(db, novel_id)
    db.commit()
    return {"created": created}


@router.get("", response_model=list[StoryEntityOut])
def list_entities(
    novel_id: str,
    entity_type: str | None = None,
    status: str | None = None,
    q: str | None = None,
    db: Session = Depends(get_db),
):
    ensure_novel(db, novel_id)
    query = db.query(StoryEntity).filter(StoryEntity.novel_id == novel_id)
    if entity_type:
        query = query.filter(StoryEntity.entity_type == entity_type)
    if status:
        query = query.filter(StoryEntity.status == status)
    if q:
        like = f"%{q.strip()}%"
        query = query.filter(StoryEntity.name.like(like))
    return query.order_by(StoryEntity.entity_type.asc(), StoryEntity.name.asc()).all()


@router.post("", response_model=StoryEntityOut)
def create_entity(novel_id: str, data: StoryEntityCreate, db: Session = Depends(get_db)):
    ensure_novel(db, novel_id)
    exists = db.query(StoryEntity).filter(
        StoryEntity.novel_id == novel_id,
        StoryEntity.entity_type == data.entity_type,
        StoryEntity.name == data.name.strip(),
    ).first()
    if exists:
        raise HTTPException(400, "同类型实体已存在，建议编辑现有实体或补记变化")

    entity = StoryEntity(
        novel_id=novel_id,
        entity_type=data.entity_type,
        name=data.name.strip(),
        aliases=normalize_aliases(data.aliases),
        summary=data.summary,
        body_md=data.body_md,
        tags=normalize_aliases(data.tags),
        current_state=data.current_state or {},
        status=data.status or "active",
        first_appearance_chapter=data.first_appearance_chapter,
    )
    db.add(entity)
    db.commit()
    db.refresh(entity)
    return entity


@router.patch("/{entity_id}", response_model=StoryEntityOut)
def update_entity(novel_id: str, entity_id: str, data: StoryEntityUpdate, db: Session = Depends(get_db)):
    ensure_novel(db, novel_id)
    entity = get_entity_or_404(db, novel_id, entity_id)
    patch = data.model_dump(exclude_unset=True)
    if "name" in patch and not str(patch["name"]).strip():
        raise HTTPException(400, "实体名称不能为空")
    for key, value in patch.items():
        if key in {"aliases", "tags"}:
            setattr(entity, key, normalize_aliases(value))
        elif key == "current_state":
            entity.current_state = value or {}
        else:
            setattr(entity, key, value)
    db.commit()
    db.refresh(entity)
    return entity


@router.get("/{entity_id}/state")
def get_entity_state(
    novel_id: str,
    entity_id: str,
    chapter_number: int | None = None,
    db: Session = Depends(get_db),
):
    ensure_novel(db, novel_id)
    entity = get_entity_or_404(db, novel_id, entity_id)
    return {
        "entity_id": entity.id,
        "chapter_number": chapter_number,
        "state": state_at_chapter(db, entity, chapter_number),
    }


@router.get("/{entity_id}/mentions", response_model=list[EntityMentionOut])
def list_mentions(novel_id: str, entity_id: str, db: Session = Depends(get_db)):
    ensure_novel(db, novel_id)
    get_entity_or_404(db, novel_id, entity_id)
    return db.query(EntityMention).filter(
        EntityMention.novel_id == novel_id,
        EntityMention.entity_id == entity_id,
    ).order_by(EntityMention.chapter_number.asc(), EntityMention.created_at.asc()).all()


@router.get("/{entity_id}/events", response_model=list[EntityEventOut])
def list_events(novel_id: str, entity_id: str, db: Session = Depends(get_db)):
    ensure_novel(db, novel_id)
    get_entity_or_404(db, novel_id, entity_id)
    return db.query(EntityEvent).filter(
        EntityEvent.novel_id == novel_id,
        EntityEvent.entity_id == entity_id,
    ).order_by(EntityEvent.chapter_number.asc(), EntityEvent.created_at.asc()).all()


@router.post("/{entity_id}/events", response_model=EntityEventOut)
def create_event(novel_id: str, entity_id: str, data: EntityEventCreate, db: Session = Depends(get_db)):
    ensure_novel(db, novel_id)
    entity = get_entity_or_404(db, novel_id, entity_id)
    event = create_entity_event(
        db,
        novel_id=novel_id,
        entity=entity,
        payload=data.model_dump(),
    )
    db.commit()
    db.refresh(event)
    return event


@router.post("/{entity_id}/recompute", response_model=StoryEntityOut)
def recompute_entity(novel_id: str, entity_id: str, db: Session = Depends(get_db)):
    ensure_novel(db, novel_id)
    entity = get_entity_or_404(db, novel_id, entity_id)
    recompute_entity_state(db, entity)
    db.commit()
    db.refresh(entity)
    return entity


@router.post("/scan", response_model=EntityScanResult)
def scan_mentions(novel_id: str, data: EntityScanRequest, db: Session = Depends(get_db)):
    ensure_novel(db, novel_id)
    scanned, created = scan_novel_mentions(db, novel_id, data.chapter_id)
    db.commit()
    return EntityScanResult(scanned_chapters=scanned, created_mentions=created)


@router.get("/relations", response_model=list[EntityRelationOut])
def list_relations(novel_id: str, entity_id: str | None = None, db: Session = Depends(get_db)):
    ensure_novel(db, novel_id)
    query = db.query(EntityRelation).filter(EntityRelation.novel_id == novel_id)
    if entity_id:
        query = query.filter(
            (EntityRelation.source_entity_id == entity_id) | (EntityRelation.target_entity_id == entity_id)
        )
    return query.order_by(EntityRelation.created_at.desc()).all()


@router.post("/relations", response_model=EntityRelationOut)
def create_relation(novel_id: str, data: EntityRelationCreate, db: Session = Depends(get_db)):
    ensure_novel(db, novel_id)
    get_entity_or_404(db, novel_id, data.source_entity_id)
    if data.target_entity_id:
        get_entity_or_404(db, novel_id, data.target_entity_id)
    relation = EntityRelation(novel_id=novel_id, **data.model_dump())
    db.add(relation)
    db.commit()
    db.refresh(relation)
    return relation
