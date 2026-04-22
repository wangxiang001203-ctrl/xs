from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Novel
from app.models.worldbuilding import Worldbuilding
from app.schemas.project import NovelCreate, NovelUpdate, NovelOut

router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.get("", response_model=list[NovelOut])
def list_novels(db: Session = Depends(get_db)):
    return db.query(Novel).order_by(Novel.created_at.desc()).all()


@router.post("", response_model=NovelOut)
def create_novel(data: NovelCreate, db: Session = Depends(get_db)):
    novel = Novel(**data.model_dump())
    db.add(novel)
    db.flush()
    # 初始化世界观记录
    wb = Worldbuilding(novel_id=novel.id)
    db.add(wb)
    db.commit()
    db.refresh(novel)
    return novel


@router.get("/{novel_id}", response_model=NovelOut)
def get_novel(novel_id: str, db: Session = Depends(get_db)):
    novel = db.query(Novel).filter(Novel.id == novel_id).first()
    if not novel:
        raise HTTPException(404, "小说不存在")
    return novel


@router.patch("/{novel_id}", response_model=NovelOut)
def update_novel(novel_id: str, data: NovelUpdate, db: Session = Depends(get_db)):
    novel = db.query(Novel).filter(Novel.id == novel_id).first()
    if not novel:
        raise HTTPException(404, "小说不存在")
    for k, v in data.model_dump(exclude_none=True).items():
        setattr(novel, k, v)
    db.commit()
    db.refresh(novel)
    return novel


@router.delete("/{novel_id}")
def delete_novel(novel_id: str, db: Session = Depends(get_db)):
    novel = db.query(Novel).filter(Novel.id == novel_id).first()
    if not novel:
        raise HTTPException(404, "小说不存在")
    db.delete(novel)
    db.commit()
    return {"ok": True}
