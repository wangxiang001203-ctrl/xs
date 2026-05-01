from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Character, EntityEvent, EntityMention, EntityRelation, StoryEntity
from app.schemas.character import CharacterCreate, CharacterUpdate, CharacterOut
from app.services.file_service import save_characters
from app.services.entity_service import get_or_create_entity

router = APIRouter(prefix="/api/projects/{novel_id}/characters", tags=["characters"])


def _sync_characters_file(novel_id: str, db: Session):
    chars = db.query(Character).filter(Character.novel_id == novel_id).all()
    data = [
        {
            "id": c.id, "name": c.name, "aliases": c.aliases or [],
            "role": c.role, "importance": c.importance,
            "gender": c.gender, "age": c.age,
            "race": c.race, "realm": c.realm, "realm_level": c.realm_level,
            "faction": c.faction, "techniques": c.techniques or [],
            "artifacts": c.artifacts or [], "appearance": c.appearance,
            "personality": c.personality, "background": c.background,
            "golden_finger": c.golden_finger, "motivation": c.motivation,
            "profile_md": c.profile_md,
            "relationships": c.relationships or [], "status": c.status,
            "first_appearance_chapter": c.first_appearance_chapter,
        }
        for c in chars
    ]
    save_characters(novel_id, data)


def _sync_character_entity(novel_id: str, char: Character, db: Session, previous_name: str | None = None):
    """角色页是用户维护入口，底层实体索引只跟随角色档案同步。"""
    entity = None
    if previous_name:
        entity = db.query(StoryEntity).filter(
            StoryEntity.novel_id == novel_id,
            StoryEntity.entity_type == "character",
            StoryEntity.name == previous_name,
        ).first()
    if entity and entity.name != char.name:
        duplicate = db.query(StoryEntity).filter(
            StoryEntity.novel_id == novel_id,
            StoryEntity.entity_type == "character",
            StoryEntity.name == char.name,
            StoryEntity.id != entity.id,
        ).first()
        if not duplicate:
            entity.name = char.name

    entity = entity or get_or_create_entity(
        db,
        novel_id=novel_id,
        entity_type="character",
        name=char.name,
    )
    entity.aliases = char.aliases or []
    entity.summary = char.motivation or char.role or entity.summary
    entity.body_md = char.profile_md or char.background or entity.body_md
    entity.tags = [item for item in [char.role, char.gender, char.race, char.faction] if item]
    entity.status = "active" if char.status != "dead" else "inactive"
    if char.first_appearance_chapter:
        entity.first_appearance_chapter = char.first_appearance_chapter
    db.flush()


def _find_character_entity(novel_id: str, char: Character, db: Session) -> StoryEntity | None:
    return db.query(StoryEntity).filter(
        StoryEntity.novel_id == novel_id,
        StoryEntity.entity_type == "character",
        StoryEntity.name == char.name,
    ).first()


def _entity_has_history(novel_id: str, entity: StoryEntity | None, db: Session) -> bool:
    if not entity:
        return False
    mention_exists = db.query(EntityMention.id).filter(
        EntityMention.novel_id == novel_id,
        EntityMention.entity_id == entity.id,
    ).first()
    event_exists = db.query(EntityEvent.id).filter(
        EntityEvent.novel_id == novel_id,
        EntityEvent.entity_id == entity.id,
    ).first()
    relation_exists = db.query(EntityRelation.id).filter(
        EntityRelation.novel_id == novel_id,
        (EntityRelation.source_entity_id == entity.id) | (EntityRelation.target_entity_id == entity.id),
    ).first()
    return bool(mention_exists or event_exists or relation_exists)


def _append_profile_note(char: Character, note: str):
    current = (char.profile_md or char.background or "").strip()
    if note not in current:
        char.profile_md = f"{current}\n\n{note}".strip()


@router.get("", response_model=list[CharacterOut])
def list_characters(novel_id: str, db: Session = Depends(get_db)):
    return db.query(Character).filter(Character.novel_id == novel_id).all()


@router.post("", response_model=CharacterOut)
def create_character(novel_id: str, data: CharacterCreate, db: Session = Depends(get_db)):
    # 同名校验
    exists = db.query(Character).filter(
        Character.novel_id == novel_id, Character.name == data.name
    ).first()
    if exists:
        raise HTTPException(400, f"角色「{data.name}」已存在")
    char = Character(novel_id=novel_id, **data.model_dump())
    db.add(char)
    db.flush()
    _sync_character_entity(novel_id, char, db)
    db.commit()
    db.refresh(char)
    _sync_characters_file(novel_id, db)
    return char


@router.get("/{char_id}", response_model=CharacterOut)
def get_character(novel_id: str, char_id: str, db: Session = Depends(get_db)):
    char = db.query(Character).filter(
        Character.id == char_id, Character.novel_id == novel_id
    ).first()
    if not char:
        raise HTTPException(404, "角色不存在")
    return char


@router.patch("/{char_id}", response_model=CharacterOut)
def update_character(novel_id: str, char_id: str, data: CharacterUpdate, db: Session = Depends(get_db)):
    char = db.query(Character).filter(
        Character.id == char_id, Character.novel_id == novel_id
    ).first()
    if not char:
        raise HTTPException(404, "角色不存在")
    previous_name = char.name
    for k, v in data.model_dump(exclude_none=True).items():
        setattr(char, k, v)
    db.flush()
    _sync_character_entity(novel_id, char, db, previous_name=previous_name)
    db.commit()
    db.refresh(char)
    _sync_characters_file(novel_id, db)
    return char


@router.delete("/{char_id}")
def delete_character(novel_id: str, char_id: str, db: Session = Depends(get_db)):
    char = db.query(Character).filter(
        Character.id == char_id, Character.novel_id == novel_id
    ).first()
    if not char:
        raise HTTPException(404, "角色不存在")

    entity = _find_character_entity(novel_id, char, db)
    if char.first_appearance_chapter or _entity_has_history(novel_id, entity, db):
        char.status = "unknown"
        _append_profile_note(
            char,
            "## 停用记录\n作者尝试删除该角色，但它已经拥有正文出现、事件或关系记录。系统已保留角色档案，避免破坏连续性。",
        )
        if entity:
            entity.status = "inactive"
            entity.current_state = {
                **(entity.current_state or {}),
                "状态": "停用保留",
                "原因": "已有正文/事件/关系记录，不能硬删除",
            }
        db.commit()
        db.refresh(char)
        _sync_characters_file(novel_id, db)
        return {"ok": True, "archived": True, "character": CharacterOut.model_validate(char).model_dump(mode="json")}

    if entity:
        db.delete(entity)
    db.delete(char)
    db.commit()
    _sync_characters_file(novel_id, db)
    return {"ok": True, "archived": False}
