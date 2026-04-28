from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.worldbuilding import Worldbuilding
from app.schemas.worldbuilding import WorldbuildingUpdate, WorldbuildingOut
from app.services.file_service import save_worldbuilding
from app.services.worldbuilding_service import (
    apply_worldbuilding_document,
    load_worldbuilding_document,
    normalize_worldbuilding_document,
)
from app.services.entity_service import sync_worldbuilding_entities

router = APIRouter(prefix="/api/projects/{novel_id}/worldbuilding", tags=["worldbuilding"])


@router.get("", response_model=WorldbuildingOut)
def get_worldbuilding(novel_id: str, db: Session = Depends(get_db)):
    wb = db.query(Worldbuilding).filter(Worldbuilding.novel_id == novel_id).first()
    if not wb:
        raise HTTPException(404, "世界观设定不存在")
    return load_worldbuilding_document(novel_id, wb)


@router.put("", response_model=WorldbuildingOut)
def upsert_worldbuilding(novel_id: str, data: WorldbuildingUpdate, db: Session = Depends(get_db)):
    wb = db.query(Worldbuilding).filter(Worldbuilding.novel_id == novel_id).first()
    if not wb:
        wb = Worldbuilding(novel_id=novel_id)
        db.add(wb)
    normalized = apply_worldbuilding_document(
        wb,
        {
            **load_worldbuilding_document(novel_id, wb),
            **data.model_dump(exclude_none=True),
            "novel_id": novel_id,
            "id": getattr(wb, "id", None),
        },
    )
    sync_worldbuilding_entities(db, novel_id, normalized)
    db.commit()
    db.refresh(wb)
    serialized = normalize_worldbuilding_document(
        {
            "id": wb.id,
            "novel_id": wb.novel_id,
            "overview": wb.overview,
            "sections": wb.sections,
            "power_system": wb.power_system,
            "factions": wb.factions,
            "geography": wb.geography,
            "core_rules": wb.core_rules,
            "items": wb.items,
        },
        fallback_id=wb.id,
        novel_id=wb.novel_id,
    )
    # 同步文件
    save_worldbuilding(novel_id, serialized)
    return serialized
