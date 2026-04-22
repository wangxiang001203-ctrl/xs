from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from app.database import get_db
from app.models.volume import Volume
from app.models.chapter import Chapter

router = APIRouter(prefix="/api/projects/{novel_id}/volumes", tags=["volumes"])


class VolumeCreate(BaseModel):
    volume_number: int
    title: str
    description: Optional[str] = None


class VolumeUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None


class VolumeOut(BaseModel):
    id: str
    novel_id: str
    volume_number: int
    title: str
    description: Optional[str]
    synopsis_generated: bool
    chapter_count: int = 0

    model_config = {"from_attributes": True}


@router.get("/", response_model=list[VolumeOut])
def list_volumes(novel_id: str, db: Session = Depends(get_db)):
    volumes = db.query(Volume).filter(Volume.novel_id == novel_id).order_by(Volume.volume_number).all()
    result = []
    for v in volumes:
        count = db.query(Chapter).filter(Chapter.volume_id == v.id).count()
        out = VolumeOut.model_validate(v)
        out.chapter_count = count
        result.append(out)
    return result


@router.post("/", response_model=VolumeOut)
def create_volume(novel_id: str, body: VolumeCreate, db: Session = Depends(get_db)):
    existing = db.query(Volume).filter(
        Volume.novel_id == novel_id,
        Volume.volume_number == body.volume_number,
    ).first()
    if existing:
        raise HTTPException(400, f"第{body.volume_number}卷已存在")
    v = Volume(novel_id=novel_id, **body.model_dump())
    db.add(v)
    db.commit()
    db.refresh(v)
    out = VolumeOut.model_validate(v)
    out.chapter_count = 0
    return out


@router.patch("/{volume_id}", response_model=VolumeOut)
def update_volume(novel_id: str, volume_id: str, body: VolumeUpdate, db: Session = Depends(get_db)):
    v = db.query(Volume).filter(Volume.id == volume_id, Volume.novel_id == novel_id).first()
    if not v:
        raise HTTPException(404, "卷不存在")
    for k, val in body.model_dump(exclude_none=True).items():
        setattr(v, k, val)
    db.commit()
    db.refresh(v)
    count = db.query(Chapter).filter(Chapter.volume_id == v.id).count()
    out = VolumeOut.model_validate(v)
    out.chapter_count = count
    return out


@router.delete("/{volume_id}")
def delete_volume(novel_id: str, volume_id: str, db: Session = Depends(get_db)):
    v = db.query(Volume).filter(Volume.id == volume_id, Volume.novel_id == novel_id).first()
    if not v:
        raise HTTPException(404, "卷不存在")
    # 解除章节关联，不删除章节
    db.query(Chapter).filter(Chapter.volume_id == volume_id).update({"volume_id": None})
    db.delete(v)
    db.commit()
    return {"ok": True}


@router.post("/{volume_id}/assign-chapter/{chapter_id}")
def assign_chapter(novel_id: str, volume_id: str, chapter_id: str, db: Session = Depends(get_db)):
    """将章节分配到指定卷"""
    v = db.query(Volume).filter(Volume.id == volume_id, Volume.novel_id == novel_id).first()
    if not v:
        raise HTTPException(404, "卷不存在")
    ch = db.query(Chapter).filter(Chapter.id == chapter_id, Chapter.novel_id == novel_id).first()
    if not ch:
        raise HTTPException(404, "章节不存在")
    ch.volume_id = volume_id
    db.commit()
    return {"ok": True}
