from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import SessionLocal, get_db
from app.models import AIGenerationJob, AIWorkflowRun, AIWorkflowStep, Novel
from app.schemas.ai_job import AIGenerationJobOut
from app.schemas.assistant import AssistantRunRequest, AssistantWorkflowRunOut, AssistantWorkflowStepOut
from app.services import ai_job_service
from app.services.ai_workflow_service import execute_assistant_workflow

router = APIRouter(prefix="/api/assistant", tags=["assistant"])


def _error_message(exc: Exception) -> str:
    if isinstance(exc, HTTPException):
        detail = exc.detail
        if isinstance(detail, dict):
            return str(detail.get("message") or detail.get("reason") or "AI 工作流失败")
        return str(detail)
    return str(exc)


async def _process_assistant_job(job_id: str):
    db = SessionLocal()
    try:
        job = db.query(AIGenerationJob).filter(AIGenerationJob.id == job_id).first()
        if not job:
            return
        payload = ai_job_service.get_request_payload(job)
        result = await execute_assistant_workflow(db, payload, job_id)
        ai_job_service.complete_job(job_id, result, "AI 工作流已完成")
    except Exception as exc:
        current_job = ai_job_service.get_job(job_id)
        ai_job_service.fail_job(
            job_id,
            _error_message(exc),
            result_payload={"message": _error_message(exc)},
            partial_text=current_job.partial_text if current_job else None,
        )
    finally:
        db.close()


@router.post("/run", response_model=AIGenerationJobOut)
async def run_assistant_workflow(
    req: AssistantRunRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    novel = db.query(Novel).filter(Novel.id == req.novel_id).first()
    if not novel:
        raise HTTPException(404, "小说不存在")
    job = ai_job_service.create_job(
        db=db,
        job_type="assistant_workflow",
        novel_id=req.novel_id,
        request_payload=req.model_dump(),
    )
    background_tasks.add_task(_process_assistant_job, job.id)
    return ai_job_service.to_response(job)


@router.get("/runs", response_model=list[AssistantWorkflowRunOut])
def list_runs(novel_id: str, limit: int = 30, db: Session = Depends(get_db)):
    safe_limit = max(min(limit, 100), 1)
    return db.query(AIWorkflowRun).filter(
        AIWorkflowRun.novel_id == novel_id,
    ).order_by(AIWorkflowRun.created_at.desc()).limit(safe_limit).all()


@router.get("/runs/{run_id}/steps", response_model=list[AssistantWorkflowStepOut])
def list_run_steps(run_id: str, db: Session = Depends(get_db)):
    run = db.query(AIWorkflowRun).filter(AIWorkflowRun.id == run_id).first()
    if not run:
        raise HTTPException(404, "工作流不存在")
    return db.query(AIWorkflowStep).filter(
        AIWorkflowStep.run_id == run_id,
    ).order_by(AIWorkflowStep.step_order.asc()).all()
