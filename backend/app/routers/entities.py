from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import EntityEvent, EntityMention, EntityRelation, Novel, StoryEntity
from app.schemas.entity import (
    EntityEventCreate,
    EntityEventOut,
    EntityMentionOut,
    EntityRelationCreate,
    EntityGraphBootstrapResult,
    EntityGraphData,
    EntityGraphEdge,
    EntityGraphNode,
    EntityRelationOut,
    EntityRelationUpdate,
    EntityScanRequest,
    EntityScanResult,
    StoryEntityCreate,
    StoryEntityOut,
    StoryEntityUpdate,
)
from app.services.entity_service import (
    bootstrap_entities_from_existing,
    create_entity_event,
    ensure_protagonist_graph_links,
    get_graph_center_entity,
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


def get_relation_or_404(db: Session, novel_id: str, relation_id: str) -> EntityRelation:
    relation = db.query(EntityRelation).filter(
        EntityRelation.id == relation_id,
        EntityRelation.novel_id == novel_id,
    ).first()
    if not relation:
        raise HTTPException(404, "关系不存在")
    return relation


def _is_system_anchor(relation: EntityRelation) -> bool:
    properties = relation.properties if isinstance(relation.properties, dict) else {}
    return (
        relation.relation_type == "story_anchor"
        and properties.get("system") is True
        and properties.get("graph_usage") == "protagonist_hub"
    )


def _dedupe_relations_for_view(relations: list[EntityRelation]) -> list[EntityRelation]:
    """Hide duplicate generated hub edges without deleting user data."""
    seen_anchor_keys: set[tuple[str, str | None, str]] = set()
    result: list[EntityRelation] = []
    for relation in relations:
        if _is_system_anchor(relation):
            key = (relation.source_entity_id, relation.target_entity_id, relation.relation_type)
            if key in seen_anchor_keys:
                continue
            seen_anchor_keys.add(key)
        result.append(relation)
    return result


@router.post("/bootstrap")
def bootstrap_entities(novel_id: str, db: Session = Depends(get_db)):
    ensure_novel(db, novel_id)
    created = bootstrap_entities_from_existing(db, novel_id)
    _, created_relations = ensure_protagonist_graph_links(db, novel_id)
    db.commit()
    return {"created": created, "created_relations": created_relations}


@router.post("/graph/bootstrap", response_model=EntityGraphBootstrapResult)
def bootstrap_graph(novel_id: str, db: Session = Depends(get_db)):
    ensure_novel(db, novel_id)
    created_entities = bootstrap_entities_from_existing(db, novel_id)
    center, created_relations = ensure_protagonist_graph_links(db, novel_id)
    db.commit()
    entity_count = db.query(StoryEntity).filter(
        StoryEntity.novel_id == novel_id,
        StoryEntity.status != "deleted",
    ).count()
    return EntityGraphBootstrapResult(
        center_entity_id=center.id if center else None,
        entity_count=entity_count,
        created_entities=created_entities,
        created_relations=created_relations,
    )


@router.get("/graph-data", response_model=EntityGraphData)
def get_graph_data(novel_id: str, include_anchor: bool = True, db: Session = Depends(get_db)):
    ensure_novel(db, novel_id)
    center = get_graph_center_entity(db, novel_id)
    entities = db.query(StoryEntity).filter(
        StoryEntity.novel_id == novel_id,
        StoryEntity.status != "deleted",
    ).order_by(StoryEntity.graph_layer.asc(), StoryEntity.importance.desc(), StoryEntity.name.asc()).all()
    relations = db.query(EntityRelation).filter(
        EntityRelation.novel_id == novel_id,
        EntityRelation.status != "deleted",
    ).order_by(EntityRelation.relation_strength.desc(), EntityRelation.created_at.asc()).all()
    entity_ids = {entity.id for entity in entities}
    edges = _dedupe_relations_for_view([
        relation for relation in relations
        if relation.source_entity_id in entity_ids and (not relation.target_entity_id or relation.target_entity_id in entity_ids)
    ])
    implicit_edge_count = 0
    if include_anchor and center:
        linked_ids = {
            relation.target_entity_id
            for relation in edges
            if relation.source_entity_id == center.id and relation.target_entity_id
        }
        for entity in entities:
            if entity.id == center.id or entity.id in linked_ids:
                continue
            edges.append(EntityRelation(
                id=f"implicit:{center.id}:{entity.id}",
                novel_id=novel_id,
                source_entity_id=center.id,
                target_entity_id=entity.id,
                target_name=entity.name,
                relation_type="story_anchor",
                relation_strength=0.15,
                is_bidirectional=False,
                confidence=1.0,
                properties={"system": True, "virtual": True, "graph_usage": "protagonist_hub"},
                evidence_text="虚拟星图弱连接，执行 graph/bootstrap 后可落库。",
                status="active",
            ))
            implicit_edge_count += 1
    center_id = center.id if center else None

    return EntityGraphData(
        center_entity_id=center.id if center else None,
        nodes=[
            EntityGraphNode(
                id=entity.id,
                name=entity.name,
                entity_type=entity.entity_type,
                graph_role="protagonist" if entity.id == center_id else (entity.graph_role or "supporting"),
                importance=max(entity.importance or 3, 5) if entity.id == center_id else (entity.importance or 3),
                graph_layer=0 if entity.id == center_id else (entity.graph_layer or 2),
                status=entity.status,
                summary=entity.summary,
                current_state=entity.current_state or {},
                graph_position=entity.graph_position or {},
            )
            for entity in entities
        ],
        edges=[
            EntityGraphEdge(
                id=relation.id,
                source_entity_id=relation.source_entity_id,
                target_entity_id=relation.target_entity_id,
                target_name=relation.target_name,
                relation_type=relation.relation_type,
                relation_strength=relation.relation_strength or 1.0,
                is_bidirectional=bool(relation.is_bidirectional),
                confidence=relation.confidence or 1.0,
                status=relation.status,
                evidence_text=relation.evidence_text,
                properties=relation.properties or {},
            )
            for relation in edges
        ],
        implicit_edge_count=implicit_edge_count,
    )


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
        graph_role=data.graph_role or "supporting",
        importance=data.importance or 3,
        graph_layer=data.graph_layer if data.graph_layer is not None else 2,
        graph_position=data.graph_position or {},
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
    return _dedupe_relations_for_view(query.order_by(EntityRelation.created_at.desc()).all())


@router.post("/relations", response_model=EntityRelationOut)
def create_relation(novel_id: str, data: EntityRelationCreate, db: Session = Depends(get_db)):
    ensure_novel(db, novel_id)
    get_entity_or_404(db, novel_id, data.source_entity_id)
    if data.target_entity_id:
        get_entity_or_404(db, novel_id, data.target_entity_id)
    if not data.target_entity_id and not (data.target_name or "").strip():
        raise HTTPException(400, "关系必须选择目标实体，或填写未入库目标名称")
    relation = EntityRelation(novel_id=novel_id, **data.model_dump())
    db.add(relation)
    db.commit()
    db.refresh(relation)
    return relation


@router.patch("/relations/{relation_id}", response_model=EntityRelationOut)
def update_relation(novel_id: str, relation_id: str, data: EntityRelationUpdate, db: Session = Depends(get_db)):
    ensure_novel(db, novel_id)
    relation = get_relation_or_404(db, novel_id, relation_id)
    patch = data.model_dump(exclude_unset=True)
    if "source_entity_id" in patch and patch["source_entity_id"]:
        get_entity_or_404(db, novel_id, patch["source_entity_id"])
    if "target_entity_id" in patch and patch["target_entity_id"]:
        get_entity_or_404(db, novel_id, patch["target_entity_id"])
    next_target_id = patch.get("target_entity_id", relation.target_entity_id)
    next_target_name = patch.get("target_name", relation.target_name)
    if not next_target_id and not (next_target_name or "").strip():
        raise HTTPException(400, "关系必须选择目标实体，或填写未入库目标名称")
    for key, value in patch.items():
        setattr(relation, key, value)
    db.commit()
    db.refresh(relation)
    return relation


@router.delete("/relations/{relation_id}")
def delete_relation(novel_id: str, relation_id: str, db: Session = Depends(get_db)):
    ensure_novel(db, novel_id)
    relation = get_relation_or_404(db, novel_id, relation_id)
    db.delete(relation)
    db.commit()
    return {"ok": True}
