from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Chapter, EntityProposal, Synopsis
from app.schemas.chapter import (
    ChapterCreate, ChapterUpdate, ChapterOut, ChapterContentOut,
    SynopsisCreate, SynopsisOut,
)
from app.services.file_service import save_chapter_content, save_chapter_plot_summary, save_chapter_synopsis
from app.services.validator import validate_story_entities, validate_synopsis_characters, validate_chapter_content_entities

router = APIRouter(prefix="/api/projects/{novel_id}/chapters", tags=["chapters"])


def _normalize_chapter_defaults(chapter: Chapter):
    if chapter.final_approved is None:
        chapter.final_approved = False


@router.get("", response_model=list[ChapterOut])
def list_chapters(novel_id: str, db: Session = Depends(get_db)):
    chapters = db.query(Chapter).filter(Chapter.novel_id == novel_id).order_by(Chapter.chapter_number).all()
    for chapter in chapters:
        _normalize_chapter_defaults(chapter)
    return chapters


@router.post("", response_model=ChapterOut)
def create_chapter(novel_id: str, data: ChapterCreate, db: Session = Depends(get_db)):
    pending_proposal = db.query(EntityProposal).filter(
        EntityProposal.novel_id == novel_id,
        EntityProposal.status == "pending",
    ).first()
    if pending_proposal:
        raise HTTPException(
            400,
            "当前作品还有待确认的 AI 角色/设定改动，请先在右侧 AI 工作详情中通过或放弃后再新建下一章。",
        )

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
    _normalize_chapter_defaults(chapter)
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
        content = update_data["content"]
        update_data["word_count"] = len(content)

        # 幻觉检测：验证正文中引用的实体是否存在
        validation_result = validate_chapter_content_entities(db, novel_id, chapter_id, content)
        if validation_result["has_hallucination"]:
            # 不阻止保存，但记录警告
            chapter.plot_summary = f"[警告] {'; '.join(validation_result['warnings'])}"

        save_chapter_content(novel_id, chapter.chapter_number, content)

    for k, v in update_data.items():
        setattr(chapter, k, v)
    db.commit()
    db.refresh(chapter)
    _normalize_chapter_defaults(chapter)
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
    entity_refs = data.referenced_entities or {}
    if all_chars and not entity_refs.get("characters"):
        entity_refs["characters"] = all_chars
    entity_validation = validate_story_entities(db, novel_id, entity_refs)
    missing_non_characters = []
    for key, values in entity_validation.items():
        if key == "characters":
            continue
        missing_non_characters.extend(values)
    if missing_non_characters:
        raise HTTPException(
            422,
            f"细纲中引用了未入库设定：{', '.join(missing_non_characters)}，请先通过提案补录或修改细纲"
        )

    synopsis = db.query(Synopsis).filter(Synopsis.chapter_id == chapter_id).first()
    if not synopsis:
        synopsis = Synopsis(chapter_id=chapter_id, novel_id=novel_id)
        db.add(synopsis)

    for k, v in data.model_dump().items():
        setattr(synopsis, k, v)

    # 汇总所有出场人物
    synopsis.all_characters = list(set(all_chars))
    synopsis.review_status = data.review_status or synopsis.review_status or "draft"
    synopsis.referenced_entities = entity_refs

    db.commit()
    db.refresh(synopsis)
    chapter = db.query(Chapter).filter(
        Chapter.id == chapter_id, Chapter.novel_id == novel_id
    ).first()
    if chapter:
        save_chapter_synopsis(novel_id, chapter.chapter_number, SynopsisOut.model_validate(synopsis).model_dump(mode="json"))
        save_chapter_plot_summary(novel_id, chapter.chapter_number, synopsis.plot_summary_update or "")
    return synopsis
