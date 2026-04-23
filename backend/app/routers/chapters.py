from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Chapter, Synopsis
from app.schemas.chapter import (
    ChapterCreate, ChapterUpdate, ChapterOut, ChapterContentOut,
    SynopsisCreate, SynopsisOut,
)
from app.services.file_service import save_chapter_content, save_chapter_synopsis, append_plot_summary
from app.services.validator import validate_synopsis_characters

router = APIRouter(prefix="/api/projects/{novel_id}/chapters", tags=["chapters"])


@router.get("", response_model=list[ChapterOut])
def list_chapters(novel_id: str, db: Session = Depends(get_db)):
    return db.query(Chapter).filter(Chapter.novel_id == novel_id).order_by(Chapter.chapter_number).all()


@router.post("", response_model=ChapterOut)
def create_chapter(novel_id: str, data: ChapterCreate, db: Session = Depends(get_db)):
    exists = db.query(Chapter).filter(
        Chapter.novel_id == novel_id, Chapter.chapter_number == data.chapter_number
    ).first()
    if exists:
        raise HTTPException(400, f"第{data.chapter_number}章已存在")
    chapter = Chapter(novel_id=novel_id, **data.model_dump())
    db.add(chapter)
    db.commit()
    db.refresh(chapter)
    return chapter


@router.get("/{chapter_id}", response_model=ChapterContentOut)
def get_chapter(novel_id: str, chapter_id: str, db: Session = Depends(get_db)):
    chapter = db.query(Chapter).filter(
        Chapter.id == chapter_id, Chapter.novel_id == novel_id
    ).first()
    if not chapter:
        raise HTTPException(404, "章节不存在")
    return chapter


@router.patch("/{chapter_id}", response_model=ChapterOut)
def update_chapter(novel_id: str, chapter_id: str, data: ChapterUpdate, db: Session = Depends(get_db)):
    chapter = db.query(Chapter).filter(
        Chapter.id == chapter_id, Chapter.novel_id == novel_id
    ).first()
    if not chapter:
        raise HTTPException(404, "章节不存在")

    update_data = data.model_dump(exclude_none=True)

    # 自动计算字数
    if "content" in update_data:
        update_data["word_count"] = len(update_data["content"])
        save_chapter_content(novel_id, chapter.chapter_number, update_data["content"])

    # 完成章节时追加主线剧情
    if update_data.get("status") == "completed" and chapter.plot_summary:
        append_plot_summary(novel_id, chapter.chapter_number, chapter.title or "", chapter.plot_summary)

    for k, v in update_data.items():
        setattr(chapter, k, v)
    db.commit()
    db.refresh(chapter)
    return chapter


@router.delete("/{chapter_id}")
def delete_chapter(novel_id: str, chapter_id: str, db: Session = Depends(get_db)):
    chapter = db.query(Chapter).filter(
        Chapter.id == chapter_id, Chapter.novel_id == novel_id
    ).first()
    if not chapter:
        raise HTTPException(404, "章节不存在")
    db.delete(chapter)
    db.commit()
    return {"ok": True}


# ── 细纲 ──────────────────────────────────────────────────────────────────────

@router.get("/{chapter_id}/synopsis", response_model=SynopsisOut)
def get_synopsis(novel_id: str, chapter_id: str, db: Session = Depends(get_db)):
    synopsis = db.query(Synopsis).filter(Synopsis.chapter_id == chapter_id).first()
    if not synopsis:
        raise HTTPException(404, "细纲不存在")
    return synopsis


@router.put("/{chapter_id}/synopsis", response_model=SynopsisOut)
def upsert_synopsis(
    novel_id: str, chapter_id: str, data: SynopsisCreate, db: Session = Depends(get_db)
):
    # 校验人物
    all_chars = list(set(
        (data.opening_characters or []) +
        (data.development_characters or []) +
        (data.all_characters or [])
    ))
    validation = validate_synopsis_characters(db, novel_id, all_chars)
    if not validation["valid"]:
        raise HTTPException(
            422,
            f"细纲中存在未定义角色：{', '.join(validation['missing'])}，请先在角色库中创建"
        )

    synopsis = db.query(Synopsis).filter(Synopsis.chapter_id == chapter_id).first()
    if not synopsis:
        synopsis = Synopsis(chapter_id=chapter_id, novel_id=novel_id)
        db.add(synopsis)

    for k, v in data.model_dump().items():
        setattr(synopsis, k, v)

    # 汇总所有出场人物
    synopsis.all_characters = list(set(all_chars))

    db.commit()
    db.refresh(synopsis)
    chapter = db.query(Chapter).filter(
        Chapter.id == chapter_id, Chapter.novel_id == novel_id
    ).first()
    if chapter:
        save_chapter_synopsis(novel_id, chapter.chapter_number, SynopsisOut.model_validate(synopsis).model_dump(mode="json"))
    return synopsis
