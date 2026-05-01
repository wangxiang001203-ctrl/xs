from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Chapter, ChapterMemory, EntityProposal, Synopsis
from app.schemas.chapter import ChapterOut, SynopsisOut
from app.services.file_service import append_plot_summary, save_chapter_synopsis
from app.services.file_service import save_chapter_plot_summary
from app.services.review_service import (
    apply_proposal,
    build_chapter_memory,
    chapter_access_guard,
    collect_pending_proposals_for_chapter,
    mark_proposal_status,
    resolve_duplicate_create_proposals,
    save_all_proposals,
    serialize_proposal,
)
from app.services.entity_service import bootstrap_entities_from_existing, scan_chapter_mentions
from app.services.global_state_service import aggregate_snapshot

router = APIRouter(prefix="/api/projects/{novel_id}/review", tags=["review"])


class ProposalReviewBody(BaseModel):
    note: str | None = None


def _save_final_chapter_artifacts(novel_id: str, chapter: Chapter):
    if chapter.plot_summary:
        append_plot_summary(novel_id, chapter.chapter_number, chapter.title or "", chapter.plot_summary)
        save_chapter_plot_summary(novel_id, chapter.chapter_number, chapter.plot_summary)


def _try_create_snapshot(db: Session, novel_id: str, chapter: Chapter):
    """每10章定稿时自动触发 L1 快照聚合。"""
    if chapter.final_approved and chapter.chapter_number % 10 == 0:
        try:
            aggregate_snapshot(db, novel_id, chapter.chapter_number - 9, chapter.chapter_number)
        except Exception:
            pass  # 快照聚合失败不影响章节定稿


def _finalize_chapter_after_review(db: Session, novel_id: str, chapter_id: str) -> Chapter | None:
    chapter = db.query(Chapter).filter(Chapter.id == chapter_id, Chapter.novel_id == novel_id).first()
    if not chapter or chapter.final_approved:
        return chapter

    pending = collect_pending_proposals_for_chapter(db, novel_id, chapter_id)
    if pending:
        return chapter

    if chapter.status != "completed":
        return chapter

    chapter.final_approved = True
    chapter.final_approved_at = datetime.utcnow()
    chapter.final_approval_note = "设定提案已处理，章节定稿完成。"
    bootstrap_entities_from_existing(db, novel_id)
    scan_chapter_mentions(db, novel_id, chapter)
    _save_final_chapter_artifacts(novel_id, chapter)
    _try_create_snapshot(db, novel_id, chapter)
    db.commit()
    db.refresh(chapter)
    return chapter


@router.get("/proposals")
def list_proposals(
    novel_id: str,
    status: str | None = None,
    chapter_id: str | None = None,
    volume_id: str | None = None,
    db: Session = Depends(get_db),
):
    query = db.query(EntityProposal).filter(EntityProposal.novel_id == novel_id)
    if status:
        query = query.filter(EntityProposal.status == status)
    if chapter_id:
        query = query.filter(EntityProposal.chapter_id == chapter_id)
    if volume_id:
        query = query.filter(EntityProposal.volume_id == volume_id)
    proposals = query.order_by(EntityProposal.created_at.desc()).all()
    return [serialize_proposal(item) for item in proposals]


@router.post("/proposals/{proposal_id}/approve")
def approve_proposal(novel_id: str, proposal_id: str, body: ProposalReviewBody, db: Session = Depends(get_db)):
    proposal = db.query(EntityProposal).filter(
        EntityProposal.id == proposal_id,
        EntityProposal.novel_id == novel_id,
    ).first()
    if not proposal:
        raise HTTPException(404, "提案不存在")
    if proposal.status != "pending":
        raise HTTPException(400, "该提案已处理")

    apply_proposal(db, proposal)
    if body.note:
        proposal.reason = f"{proposal.reason or ''}\n审批备注：{body.note}".strip()
    mark_proposal_status(proposal, "approved")
    merged = resolve_duplicate_create_proposals(db, proposal)
    db.commit()
    save_all_proposals(db, novel_id)
    if proposal.chapter_id:
        _finalize_chapter_after_review(db, novel_id, proposal.chapter_id)
    for duplicate in merged:
        if duplicate.chapter_id and duplicate.chapter_id != proposal.chapter_id:
            _finalize_chapter_after_review(db, novel_id, duplicate.chapter_id)
    return serialize_proposal(proposal)


@router.post("/proposals/{proposal_id}/reject")
def reject_proposal(novel_id: str, proposal_id: str, body: ProposalReviewBody, db: Session = Depends(get_db)):
    proposal = db.query(EntityProposal).filter(
        EntityProposal.id == proposal_id,
        EntityProposal.novel_id == novel_id,
    ).first()
    if not proposal:
        raise HTTPException(404, "提案不存在")
    if proposal.status != "pending":
        raise HTTPException(400, "该提案已处理")
    if body.note:
        proposal.reason = f"{proposal.reason or ''}\n拒绝备注：{body.note}".strip()
    mark_proposal_status(proposal, "rejected")
    db.commit()
    save_all_proposals(db, novel_id)
    if proposal.chapter_id:
        _finalize_chapter_after_review(db, novel_id, proposal.chapter_id)
    return serialize_proposal(proposal)


@router.post("/chapters/{chapter_id}/approve-synopsis", response_model=SynopsisOut)
def approve_synopsis(novel_id: str, chapter_id: str, db: Session = Depends(get_db)):
    chapter = db.query(Chapter).filter(Chapter.id == chapter_id, Chapter.novel_id == novel_id).first()
    if not chapter:
        raise HTTPException(404, "章节不存在")
    synopsis = db.query(Synopsis).filter(Synopsis.chapter_id == chapter_id).first()
    if not synopsis:
        raise HTTPException(404, "细纲不存在")
    if not synopsis.content_md:
        raise HTTPException(400, "请先生成或填写完整细纲")
    pending = collect_pending_proposals_for_chapter(db, novel_id, chapter_id)
    if pending:
        raise HTTPException(400, "本章还有待处理的新实体提案，先审阅通过或拒绝后再批准细纲")

    synopsis.review_status = "approved"
    synopsis.approved_at = datetime.utcnow()
    db.commit()
    db.refresh(synopsis)
    save_chapter_synopsis(novel_id, chapter.chapter_number, SynopsisOut.model_validate(synopsis).model_dump(mode="json"))
    return synopsis


@router.post("/chapters/{chapter_id}/approve-final", response_model=ChapterOut)
async def approve_final_chapter(novel_id: str, chapter_id: str, db: Session = Depends(get_db)):
    chapter = db.query(Chapter).filter(Chapter.id == chapter_id, Chapter.novel_id == novel_id).first()
    if not chapter:
        raise HTTPException(404, "章节不存在")
    if chapter.final_approved:
        raise HTTPException(400, "本章已经定稿")
    synopsis = db.query(Synopsis).filter(Synopsis.chapter_id == chapter_id).first()
    if not synopsis or synopsis.review_status != "approved":
        raise HTTPException(400, "本章细纲尚未审批通过")
    guard = chapter_access_guard(db, chapter)
    if not guard["ok"]:
        raise HTTPException(400, guard["reason"])
    pending = collect_pending_proposals_for_chapter(db, novel_id, chapter_id)
    if pending:
        raise HTTPException(400, "本章还有待审阅的新实体提案，不能定稿")
    if not chapter.content or not chapter.content.strip():
        raise HTTPException(400, "请先完成正文")

    memory = await build_chapter_memory(db, chapter, synopsis)

    chapter.status = "completed"
    chapter.plot_summary = synopsis.plot_summary_update or chapter.plot_summary
    pending_after_memory = collect_pending_proposals_for_chapter(db, novel_id, chapter_id)
    if pending_after_memory:
        chapter.final_approved = False
        chapter.final_approved_at = None
        chapter.final_approval_note = f"已生成 {len(pending_after_memory)} 条设定更新提案，处理完成后自动定稿。"
        db.commit()
        db.refresh(chapter)
        return chapter

    chapter.final_approved = True
    chapter.final_approved_at = datetime.utcnow()
    chapter.final_approval_note = "未发现待审设定提案，章节定稿完成。"
    bootstrap_entities_from_existing(db, novel_id)
    scan_chapter_mentions(db, novel_id, chapter)
    _save_final_chapter_artifacts(novel_id, chapter)
    _try_create_snapshot(db, novel_id, chapter)
    db.commit()
    db.refresh(chapter)
    return chapter


@router.get("/chapters/{chapter_id}/memory")
def get_chapter_memory(novel_id: str, chapter_id: str, db: Session = Depends(get_db)):
    chapter = db.query(Chapter).filter(Chapter.id == chapter_id, Chapter.novel_id == novel_id).first()
    if not chapter:
        raise HTTPException(404, "章节不存在")
    memory = db.query(ChapterMemory).filter(ChapterMemory.chapter_id == chapter_id).first()
    if not memory:
        raise HTTPException(404, "章节记忆不存在")
    return {
        "id": memory.id,
        "novel_id": memory.novel_id,
        "chapter_id": memory.chapter_id,
        "chapter_number": memory.chapter_number,
        "summary": memory.summary,
        "key_events": memory.key_events or [],
        "state_changes": memory.state_changes or [],
        "inventory_changes": memory.inventory_changes or [],
        "proposed_entities": memory.proposed_entities or [],
        "open_threads": memory.open_threads or [],
        "source_excerpt": memory.source_excerpt,
        "created_at": memory.created_at,
        "updated_at": memory.updated_at,
    }
