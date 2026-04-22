from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Character
from app.schemas.character import CharacterCreate, CharacterUpdate, CharacterOut
from app.services.file_service import save_characters

router = APIRouter(prefix="/api/projects/{novel_id}/characters", tags=["characters"])


def _sync_characters_file(novel_id: str, db: Session):
    chars = db.query(Character).filter(Character.novel_id == novel_id).all()
    data = [
        {
            "id": c.id, "name": c.name, "gender": c.gender, "age": c.age,
            "race": c.race, "realm": c.realm, "realm_level": c.realm_level,
            "faction": c.faction, "techniques": c.techniques or [],
            "artifacts": c.artifacts or [], "appearance": c.appearance,
            "personality": c.personality, "background": c.background,
            "relationships": c.relationships or [], "status": c.status,
            "first_appearance_chapter": c.first_appearance_chapter,
        }
        for c in chars
    ]
    save_characters(novel_id, data)


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
    for k, v in data.model_dump(exclude_none=True).items():
        setattr(char, k, v)
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
    db.delete(char)
    db.commit()
    _sync_characters_file(novel_id, db)
    return {"ok": True}
