from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.worldbuilding import Worldbuilding
from app.schemas.worldbuilding import WorldbuildingUpdate, WorldbuildingOut
from app.services.file_service import save_worldbuilding

router = APIRouter(prefix="/api/projects/{novel_id}/worldbuilding", tags=["worldbuilding"])


@router.get("", response_model=WorldbuildingOut)
def get_worldbuilding(novel_id: str, db: Session = Depends(get_db)):
    wb = db.query(Worldbuilding).filter(Worldbuilding.novel_id == novel_id).first()
    if not wb:
        raise HTTPException(404, "世界观设定不存在")
    return wb


@router.put("", response_model=WorldbuildingOut)
def upsert_worldbuilding(novel_id: str, data: WorldbuildingUpdate, db: Session = Depends(get_db)):
    wb = db.query(Worldbuilding).filter(Worldbuilding.novel_id == novel_id).first()
    if not wb:
        wb = Worldbuilding(novel_id=novel_id)
        db.add(wb)
    for k, v in data.model_dump(exclude_none=True).items():
        setattr(wb, k, v)
    db.commit()
    db.refresh(wb)
    # 同步文件
    save_worldbuilding(novel_id, data.model_dump())
    return wb
