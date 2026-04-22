from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.project import Outline
from app.schemas.project import OutlineCreate, OutlineUpdate, OutlineOut
from app.services.file_service import save_outline

router = APIRouter(prefix="/api/projects/{novel_id}/outline", tags=["outline"])


@router.get("", response_model=list[OutlineOut])
def list_outlines(novel_id: str, db: Session = Depends(get_db)):
    return db.query(Outline).filter(Outline.novel_id == novel_id).order_by(Outline.version.desc()).all()


@router.get("/latest", response_model=OutlineOut)
def get_latest_outline(novel_id: str, db: Session = Depends(get_db)):
    outline = db.query(Outline).filter(Outline.novel_id == novel_id).order_by(Outline.version.desc()).first()
    if not outline:
        raise HTTPException(404, "大纲不存在")
    return outline


@router.post("", response_model=OutlineOut)
def create_outline(novel_id: str, data: OutlineCreate, db: Session = Depends(get_db)):
    # 版本号自增
    last = db.query(Outline).filter(Outline.novel_id == novel_id).order_by(Outline.version.desc()).first()
    version = (last.version + 1) if last else 1
    outline = Outline(novel_id=novel_id, version=version, **data.model_dump())
    db.add(outline)
    db.commit()
    db.refresh(outline)
    return outline


@router.patch("/{outline_id}", response_model=OutlineOut)
def update_outline(novel_id: str, outline_id: str, data: OutlineUpdate, db: Session = Depends(get_db)):
    outline = db.query(Outline).filter(
        Outline.id == outline_id, Outline.novel_id == novel_id
    ).first()
    if not outline:
        raise HTTPException(404, "大纲不存在")
    for k, v in data.model_dump(exclude_none=True).items():
        setattr(outline, k, v)
    db.commit()
    db.refresh(outline)
    # 确认后同步文件
    if outline.confirmed and outline.content:
        save_outline(novel_id, outline.content)
    return outline
