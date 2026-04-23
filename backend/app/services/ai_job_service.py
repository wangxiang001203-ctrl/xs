import json
from datetime import datetime
from typing import Any, Callable

from app.database import SessionLocal
from app.models import AIGenerationJob
from app.services import ai_service

PARTIAL_SAVE_INTERVAL = 240


def _serialize(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False)


def _deserialize(raw: str | None) -> Any:
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception:
        return raw


def create_job(
    *,
    db,
    job_type: str,
    novel_id: str,
    request_payload: dict[str, Any],
    chapter_id: str | None = None,
    volume_id: str | None = None,
) -> AIGenerationJob:
    job = AIGenerationJob(
        novel_id=novel_id,
        chapter_id=chapter_id,
        volume_id=volume_id,
        job_type=job_type,
        status="queued",
        request_payload=_serialize(request_payload),
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def get_job(job_id: str) -> AIGenerationJob | None:
    db = SessionLocal()
    try:
        return db.query(AIGenerationJob).filter(AIGenerationJob.id == job_id).first()
    finally:
        db.close()


def get_request_payload(job: AIGenerationJob) -> dict[str, Any]:
    payload = _deserialize(job.request_payload)
    return payload if isinstance(payload, dict) else {}


def to_response(job: AIGenerationJob) -> dict[str, Any]:
    return {
        "id": job.id,
        "novel_id": job.novel_id,
        "chapter_id": job.chapter_id,
        "volume_id": job.volume_id,
        "job_type": job.job_type,
        "status": job.status,
        "progress_message": job.progress_message,
        "result_payload": _deserialize(job.result_payload),
        "partial_text": job.partial_text,
        "error_message": job.error_message,
        "created_at": job.created_at,
        "started_at": job.started_at,
        "finished_at": job.finished_at,
        "updated_at": job.updated_at,
    }


def _update_job(job_id: str, **fields):
    db = SessionLocal()
    try:
        job = db.query(AIGenerationJob).filter(AIGenerationJob.id == job_id).first()
        if not job:
            return
        for key, value in fields.items():
            setattr(job, key, value)
        db.commit()
    finally:
        db.close()


def set_running(job_id: str, progress_message: str | None = None):
    now = datetime.utcnow()
    _update_job(
        job_id,
        status="running",
        progress_message=progress_message,
        started_at=now,
        error_message=None,
    )


def update_partial(job_id: str, partial_text: str, progress_message: str | None = None):
    payload: dict[str, Any] = {"partial_text": partial_text}
    if progress_message is not None:
        payload["progress_message"] = progress_message
    _update_job(job_id, **payload)


def complete_job(job_id: str, result_payload: Any, progress_message: str | None = None):
    _update_job(
        job_id,
        status="completed",
        progress_message=progress_message or "已完成",
        result_payload=_serialize(result_payload),
        finished_at=datetime.utcnow(),
    )


def fail_job(
    job_id: str,
    error_message: str,
    *,
    result_payload: Any = None,
    partial_text: str | None = None,
):
    fields: dict[str, Any] = {
        "status": "failed",
        "error_message": error_message,
        "finished_at": datetime.utcnow(),
    }
    if result_payload is not None:
        fields["result_payload"] = _serialize(result_payload)
    if partial_text is not None:
        fields["partial_text"] = partial_text
    _update_job(job_id, **fields)


async def collect_text(
    *,
    job_id: str,
    system_prompt: str,
    user_prompt: str,
    progress_message: str,
    on_partial: Callable[[str], None] | None = None,
) -> str:
    set_running(job_id, progress_message)
    accumulated = ""
    last_saved_length = 0
    try:
        async for chunk in ai_service.stream_generate(system_prompt, user_prompt):
            accumulated += chunk
            if len(accumulated) - last_saved_length >= PARTIAL_SAVE_INTERVAL:
                update_partial(job_id, accumulated, progress_message)
                if on_partial:
                    on_partial(accumulated)
                last_saved_length = len(accumulated)
        update_partial(job_id, accumulated, progress_message)
        if on_partial:
            on_partial(accumulated)
        return accumulated
    except Exception:
        if accumulated:
            update_partial(job_id, accumulated, "生成中断，已保留部分结果")
            if on_partial:
                on_partial(accumulated)
        raise
