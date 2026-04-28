import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Float, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def gen_uuid() -> str:
    return str(uuid.uuid4())


class AIWorkflowRun(Base):
    __tablename__ = "ai_workflow_runs"
    __table_args__ = {"comment": "AI 工作流执行记录"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    novel_id: Mapped[str] = mapped_column(String(36), ForeignKey("novels.id", ondelete="CASCADE"), index=True)
    job_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("ai_generation_jobs.id", ondelete="SET NULL"), index=True)
    context_type: Mapped[str] = mapped_column(String(50), default="outline")
    context_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    user_message: Mapped[str] = mapped_column(Text)
    intent: Mapped[str | None] = mapped_column(String(80))
    confidence: Mapped[float | None] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(20), default="running")
    result_summary: Mapped[str | None] = mapped_column(Text)
    payload: Mapped[dict | None] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)


class AIWorkflowStep(Base):
    __tablename__ = "ai_workflow_steps"
    __table_args__ = {"comment": "AI 工作流步骤日志"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    run_id: Mapped[str] = mapped_column(String(36), ForeignKey("ai_workflow_runs.id", ondelete="CASCADE"), index=True)
    step_order: Mapped[int] = mapped_column(default=1)
    title: Mapped[str] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(20), default="done")
    detail: Mapped[str | None] = mapped_column(Text)
    files: Mapped[list | None] = mapped_column(JSON, default=list)
    payload: Mapped[dict | None] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)
