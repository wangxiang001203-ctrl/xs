import re
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from app.database import get_db
from app.models.volume import Volume
from app.models.chapter import Chapter
from app.models.entity_proposal import EntityProposal
from app.models.synopsis import Synopsis
from app.services.file_service import save_chapter_plot_summary, save_chapter_synopsis, save_volume_plan
from app.services.review_service import serialize_proposal

router = APIRouter(prefix="/api/projects/{novel_id}/volumes", tags=["volumes"])
DEFAULT_VOLUME_CHAPTER_COUNT = 12


def _normalize_volume_defaults(volume: Volume):
    if volume.target_words is None:
        volume.target_words = 0
    if volume.planned_chapter_count is None:
        volume.planned_chapter_count = 0
    if volume.review_status is None:
        volume.review_status = "draft"
    if volume.plan_data is None:
        volume.plan_data = {}


def _positive_int(value) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return 0
    return number if number > 0 else 0


def _extract_chapter_count_from_markdown(markdown: str | None) -> int:
    if not markdown:
        return 0
    patterns = [
        r"预计章节数\s*[：:]\s*(\d+)",
        r"本卷共\s*(\d+)\s*章",
        r"共\s*(\d+)\s*章",
    ]
    for pattern in patterns:
        match = re.search(pattern, markdown)
        if match:
            count = _positive_int(match.group(1))
            if count:
                return count
    return 0


def _effective_planned_chapter_count(volume: Volume, chapter_count: int = 0) -> int:
    plan_data = volume.plan_data or {}
    candidates = [
        volume.planned_chapter_count,
        plan_data.get("chapter_count"),
        plan_data.get("planned_chapter_count"),
        _extract_chapter_count_from_markdown(volume.plan_markdown),
        chapter_count,
    ]
    for candidate in candidates:
        count = _positive_int(candidate)
        if count:
            return max(count, chapter_count)
    return DEFAULT_VOLUME_CHAPTER_COUNT


class VolumeCreate(BaseModel):
    volume_number: int
    title: str
    description: Optional[str] = None
    target_words: Optional[int] = None
    planned_chapter_count: Optional[int] = None
    main_line: Optional[str] = None
    character_arc: Optional[str] = None
    ending_hook: Optional[str] = None
    plan_markdown: Optional[str] = None
    plan_data: Optional[dict] = None


class ChapterSynopsisDraft(BaseModel):
    chapter_id: str
    title: Optional[str] = None
    summary_line: Optional[str] = None
    content_md: str = ""


class VolumeUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    target_words: Optional[int] = None
    planned_chapter_count: Optional[int] = None
    main_line: Optional[str] = None
    character_arc: Optional[str] = None
    ending_hook: Optional[str] = None
    plan_markdown: Optional[str] = None
    plan_data: Optional[dict] = None
    review_status: Optional[str] = None
    chapter_synopses: Optional[list[ChapterSynopsisDraft]] = None


class VolumeOut(BaseModel):
    id: str
    novel_id: str
    volume_number: int
    title: str
    description: Optional[str]
    target_words: int = 0
    planned_chapter_count: int = 0
    main_line: Optional[str] = None
    character_arc: Optional[str] = None
    ending_hook: Optional[str] = None
    plan_markdown: Optional[str] = None
    plan_data: Optional[dict] = None
    synopsis_generated: bool
    review_status: str = "draft"
    approved_at: Optional[datetime] = None
    chapter_count: int = 0

    model_config = {"from_attributes": True}


class VolumeWorkspaceOut(BaseModel):
    volume: VolumeOut
    volume_synopsis_markdown: str = ""
    chapters: list[dict]
    pending_proposals: list[dict]


def _build_volume_synopsis_markdown(volume: Volume, chapters: list[Chapter], synopsis_by_chapter: dict[str, Synopsis]) -> str:
    parts = [
        f"# 第{volume.volume_number}卷 {volume.title}",
        "",
        f"本卷共 {len(chapters)} 章。",
        "",
    ]
    if volume.main_line:
        parts.extend(["## 本卷主线", volume.main_line.strip(), ""])

    parts.append("## 章节细纲")
    parts.append("")
    for chapter in chapters:
        synopsis = synopsis_by_chapter.get(chapter.id)
        default_title = f"第{chapter.chapter_number}章"
        title = (chapter.title or "").strip()
        heading = default_title if not title or title == default_title else f"{default_title} {title}"
        parts.append(f"### {heading}")
        if synopsis and synopsis.content_md:
            parts.append(synopsis.content_md.strip())
        elif synopsis and synopsis.summary_line:
            parts.append(synopsis.summary_line.strip())
        elif synopsis and synopsis.plot_summary_update:
            parts.append(synopsis.plot_summary_update.strip())
        else:
            parts.append("（待生成）")
        parts.append("")
    return "\n".join(parts).strip()


def _chapter_has_started(chapter: Chapter) -> bool:
    return bool(
        (chapter.content or "").strip()
        or (chapter.word_count or 0) > 0
        or chapter.final_approved
        or chapter.status in ("writing", "completed")
    )


def _chapter_has_volume_material(chapter: Chapter, synopsis: Synopsis | None = None) -> bool:
    if _chapter_has_started(chapter):
        return True
    if synopsis is None:
        return False
    return bool(
        (synopsis.summary_line or "").strip()
        or (synopsis.content_md or "").strip()
        or (synopsis.plot_summary_update or "").strip()
        or (synopsis.opening_scene or "").strip()
        or (synopsis.development_events or [])
        or (synopsis.hard_constraints or [])
    )


_CN_DIGITS = {
    "零": 0,
    "〇": 0,
    "一": 1,
    "二": 2,
    "两": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
}


def _number_to_chinese(number: int) -> str:
    if number <= 0:
        return str(number)
    if number < 10:
        return next((key for key, value in _CN_DIGITS.items() if value == number and key not in ("两", "〇")), str(number))
    if number < 100:
        tens, ones = divmod(number, 10)
        prefix = "" if tens == 1 else _number_to_chinese(tens)
        return f"{prefix}十{_number_to_chinese(ones) if ones else ''}"
    if number < 1000:
        hundreds, rest = divmod(number, 100)
        middle = "零" if rest and rest < 10 else ""
        return f"{_number_to_chinese(hundreds)}百{middle}{_number_to_chinese(rest) if rest else ''}"
    thousands, rest = divmod(number, 1000)
    middle = "零" if rest and rest < 100 else ""
    return f"{_number_to_chinese(thousands)}千{middle}{_number_to_chinese(rest) if rest else ''}"


def _contains_chapter_heading(markdown: str, chapter_number: int) -> bool:
    compact = re.sub(r"\s+", "", markdown or "")
    return f"第{chapter_number}章" in compact or f"第{_number_to_chinese(chapter_number)}章" in compact


def _guard_volume_plan_keeps_started_chapters(db: Session, volume: Volume, next_markdown: str):
    started_chapters = db.query(Chapter).filter(
        Chapter.volume_id == volume.id,
    ).order_by(Chapter.chapter_number).all()
    missing = [
        chapter.chapter_number
        for chapter in started_chapters
        if _chapter_has_started(chapter) and not _contains_chapter_heading(next_markdown, chapter.chapter_number)
    ]
    if missing:
        chapter_labels = "、".join(f"第{number}章" for number in missing)
        raise HTTPException(400, f"{chapter_labels}已开始写作，不能从本卷细纲中删除")


def _serialize_synopsis_for_file(synopsis: Synopsis) -> dict:
    return {
        "id": synopsis.id,
        "chapter_id": synopsis.chapter_id,
        "novel_id": synopsis.novel_id,
        "summary_line": synopsis.summary_line or "",
        "content_md": synopsis.content_md or "",
        "opening_scene": synopsis.opening_scene or "",
        "opening_mood": synopsis.opening_mood or "",
        "opening_hook": synopsis.opening_hook or "",
        "opening_characters": synopsis.opening_characters or [],
        "development_events": synopsis.development_events or [],
        "development_conflicts": synopsis.development_conflicts or [],
        "development_characters": synopsis.development_characters or [],
        "ending_resolution": synopsis.ending_resolution or "",
        "ending_cliffhanger": synopsis.ending_cliffhanger or "",
        "ending_next_hook": synopsis.ending_next_hook or "",
        "all_characters": synopsis.all_characters or [],
        "word_count_target": synopsis.word_count_target or 3000,
        "hard_constraints": synopsis.hard_constraints or [],
        "referenced_entities": synopsis.referenced_entities or {},
        "review_status": synopsis.review_status or "draft",
        "approved_at": synopsis.approved_at.isoformat() if synopsis.approved_at else None,
        "plot_summary_update": synopsis.plot_summary_update or "",
    }


def _sync_chapter_synopsis_drafts(
    db: Session,
    novel_id: str,
    volume: Volume,
    drafts: list[ChapterSynopsisDraft],
) -> bool:
    chapters = {
        chapter.id: chapter
        for chapter in db.query(Chapter).filter(Chapter.volume_id == volume.id).all()
    }
    changed = False

    for draft in drafts:
        chapter = chapters.get(draft.chapter_id)
        if not chapter:
            raise HTTPException(400, "细纲里包含不属于当前分卷的章节")

        content = (draft.content_md or "").strip()
        if _chapter_has_started(chapter) and not content:
            raise HTTPException(400, f"第{chapter.chapter_number}章已开始写作，不能清空本章细纲")

        synopsis = db.query(Synopsis).filter(Synopsis.chapter_id == chapter.id).first()
        if not synopsis:
            synopsis = Synopsis(chapter_id=chapter.id, novel_id=novel_id)
            db.add(synopsis)

        if draft.title is not None:
            title = draft.title.strip()
            if title:
                chapter.title = title

        if draft.summary_line is not None:
            synopsis.summary_line = draft.summary_line.strip()

        if (synopsis.content_md or "").strip() != content:
            synopsis.content_md = content
            synopsis.review_status = "draft"
            synopsis.approved_at = None
            changed = True
        elif synopsis.review_status is None:
            synopsis.review_status = "draft"

    return changed


@router.get("/", response_model=list[VolumeOut])
def list_volumes(novel_id: str, db: Session = Depends(get_db)):
    volumes = db.query(Volume).filter(Volume.novel_id == novel_id).order_by(Volume.volume_number).all()
    result = []
    for v in volumes:
        _normalize_volume_defaults(v)
        count = db.query(Chapter).filter(Chapter.volume_id == v.id).count()
        out = VolumeOut.model_validate(v)
        out.chapter_count = count
        out.planned_chapter_count = _effective_planned_chapter_count(v, count)
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
    _normalize_volume_defaults(v)
    if v.plan_markdown or v.plan_data:
        save_volume_plan(
            novel_id,
            v.volume_number,
            v.plan_markdown or "",
            v.plan_data or {},
        )
    out = VolumeOut.model_validate(v)
    out.chapter_count = 0
    out.planned_chapter_count = _effective_planned_chapter_count(v, 0)
    return out


@router.patch("/{volume_id}", response_model=VolumeOut)
def update_volume(novel_id: str, volume_id: str, body: VolumeUpdate, db: Session = Depends(get_db)):
    v = db.query(Volume).filter(Volume.id == volume_id, Volume.novel_id == novel_id).first()
    if not v:
        raise HTTPException(404, "卷不存在")
    update_data = body.model_dump(exclude_none=True, exclude={"chapter_synopses"})
    if "plan_markdown" in update_data:
        incoming_plan = (update_data["plan_markdown"] or "").strip()
        current_plan = (v.plan_markdown or "").strip()
        if v.review_status == "approved" and incoming_plan != current_plan:
            raise HTTPException(400, "本卷细纲已经确认，不能直接改写。请先通过后续改稿/补录流程处理。")
        _guard_volume_plan_keeps_started_chapters(db, v, update_data["plan_markdown"] or "")
    for k, val in update_data.items():
        setattr(v, k, val)
    synopsis_changed = False
    if body.chapter_synopses is not None:
        synopsis_changed = _sync_chapter_synopsis_drafts(db, novel_id, v, body.chapter_synopses)
    if synopsis_changed and body.review_status != "approved":
        v.review_status = "draft"
        v.approved_at = None
        v.synopsis_generated = True
    if body.review_status == "approved":
        v.approved_at = datetime.utcnow()
    elif body.review_status and body.review_status != "approved":
        v.approved_at = None
    db.commit()
    db.refresh(v)
    _normalize_volume_defaults(v)
    if v.plan_markdown or v.plan_data:
        save_volume_plan(
            novel_id,
            v.volume_number,
            v.plan_markdown or "",
            v.plan_data or {},
        )
    if body.chapter_synopses is not None:
        chapters = db.query(Chapter).filter(Chapter.volume_id == v.id).order_by(Chapter.chapter_number).all()
        synopsis_by_chapter = {
            item.chapter_id: item
            for item in db.query(Synopsis).filter(Synopsis.chapter_id.in_([chapter.id for chapter in chapters])).all()
        } if chapters else {}
        for chapter in chapters:
            synopsis = synopsis_by_chapter.get(chapter.id)
            if not synopsis:
                continue
            save_chapter_synopsis(novel_id, chapter.chapter_number, _serialize_synopsis_for_file(synopsis))
            save_chapter_plot_summary(novel_id, chapter.chapter_number, synopsis.plot_summary_update or "")
    count = db.query(Chapter).filter(Chapter.volume_id == v.id).count()
    out = VolumeOut.model_validate(v)
    out.chapter_count = count
    out.planned_chapter_count = _effective_planned_chapter_count(v, count)
    return out


@router.delete("/{volume_id}")
def delete_volume(novel_id: str, volume_id: str, db: Session = Depends(get_db)):
    v = db.query(Volume).filter(Volume.id == volume_id, Volume.novel_id == novel_id).first()
    if not v:
        raise HTTPException(404, "卷不存在")
    chapters = db.query(Chapter).filter(Chapter.volume_id == volume_id).order_by(Chapter.chapter_number).all()
    synopsis_by_chapter = {
        item.chapter_id: item
        for item in db.query(Synopsis).filter(Synopsis.chapter_id.in_([chapter.id for chapter in chapters])).all()
    } if chapters else {}
    material_chapters = [
        chapter
        for chapter in chapters
        if _chapter_has_volume_material(chapter, synopsis_by_chapter.get(chapter.id))
    ]
    pending = db.query(EntityProposal).filter(
        EntityProposal.novel_id == novel_id,
        EntityProposal.volume_id == volume_id,
        EntityProposal.status == "pending",
    ).count()
    if chapters or material_chapters or pending or (v.plan_markdown or "").strip():
        if material_chapters:
            first = material_chapters[0]
            raise HTTPException(400, f"第{first.chapter_number}章已经有细纲、正文或定稿记录，本卷不能删除")
        if chapters:
            raise HTTPException(400, "本卷已经创建章节，不能删除。请保留卷顺序，必要时只调整标题和细纲内容。")
        if pending:
            raise HTTPException(400, "本卷还有待审阅提案，不能删除")
        raise HTTPException(400, "本卷已经有细纲内容，不能删除")

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


@router.get("/{volume_id}/workspace", response_model=VolumeWorkspaceOut)
def get_volume_workspace(novel_id: str, volume_id: str, db: Session = Depends(get_db)):
    volume = db.query(Volume).filter(Volume.id == volume_id, Volume.novel_id == novel_id).first()
    if not volume:
        raise HTTPException(404, "卷不存在")

    chapters = db.query(Chapter).filter(Chapter.volume_id == volume_id).order_by(Chapter.chapter_number).all()
    synopsis_by_chapter = {
        item.chapter_id: item
        for item in db.query(Synopsis).filter(Synopsis.chapter_id.in_([chapter.id for chapter in chapters])).all()
    } if chapters else {}
    chapter_payload: list[dict] = []
    for chapter in chapters:
        synopsis = synopsis_by_chapter.get(chapter.id)
        content_preview = ""
        if synopsis and synopsis.content_md:
            lines = [line.strip() for line in synopsis.content_md.splitlines() if line.strip()]
            content_preview = " ".join(lines[:3])[:220]
        elif synopsis and synopsis.plot_summary_update:
            content_preview = synopsis.plot_summary_update.strip()[:220]
        chapter_payload.append(
            {
                "id": chapter.id,
                "chapter_number": chapter.chapter_number,
                "title": chapter.title,
                "status": chapter.status,
                "final_approved": chapter.final_approved,
                "synopsis_review_status": synopsis.review_status if synopsis else "draft",
                "summary_line": synopsis.summary_line if synopsis else "",
                "plot_summary_update": synopsis.plot_summary_update if synopsis else "",
                "content_md": synopsis.content_md if synopsis else "",
                "content_preview": content_preview,
            }
        )

    proposals = db.query(EntityProposal).filter(
        EntityProposal.novel_id == novel_id,
        EntityProposal.volume_id == volume_id,
        EntityProposal.status == "pending",
    ).order_by(EntityProposal.created_at.asc()).all()

    out = VolumeOut.model_validate(volume)
    out.chapter_count = len(chapter_payload)
    out.planned_chapter_count = _effective_planned_chapter_count(volume, len(chapter_payload))
    return VolumeWorkspaceOut(
        volume=out,
        volume_synopsis_markdown=volume.plan_markdown or _build_volume_synopsis_markdown(volume, chapters, synopsis_by_chapter),
        chapters=chapter_payload,
        pending_proposals=[serialize_proposal(item) for item in proposals],
    )


@router.post("/{volume_id}/approve", response_model=VolumeOut)
def approve_volume(novel_id: str, volume_id: str, db: Session = Depends(get_db)):
    volume = db.query(Volume).filter(Volume.id == volume_id, Volume.novel_id == novel_id).first()
    if not volume:
        raise HTTPException(404, "卷不存在")

    chapters = db.query(Chapter).filter(Chapter.volume_id == volume_id).order_by(Chapter.chapter_number.asc()).all()
    if not chapters:
        raise HTTPException(400, "本卷还没有章节，无法审批")
    synopses: list[Synopsis] = []
    for chapter in chapters:
        synopsis = db.query(Synopsis).filter(Synopsis.chapter_id == chapter.id).first()
        if not synopsis or not synopsis.content_md:
            raise HTTPException(400, f"第{chapter.chapter_number}章尚未生成完整细纲")
        synopses.append(synopsis)

    pending = db.query(EntityProposal).filter(
        EntityProposal.novel_id == novel_id,
        EntityProposal.volume_id == volume_id,
        EntityProposal.status == "pending",
    ).count()
    if pending:
        raise HTTPException(400, "本卷还有待审阅的新实体提案，处理后才能通过卷节奏审批")

    approved_at = datetime.utcnow()
    for synopsis in synopses:
        synopsis.review_status = "approved"
        synopsis.approved_at = approved_at
    volume.review_status = "approved"
    volume.approved_at = approved_at
    db.commit()
    db.refresh(volume)
    for chapter, synopsis in zip(chapters, synopses):
        save_chapter_synopsis(novel_id, chapter.chapter_number, _serialize_synopsis_for_file(synopsis))
        save_chapter_plot_summary(novel_id, chapter.chapter_number, synopsis.plot_summary_update or "")
    out = VolumeOut.model_validate(volume)
    out.chapter_count = len(chapters)
    out.planned_chapter_count = _effective_planned_chapter_count(volume, len(chapters))
    return out
