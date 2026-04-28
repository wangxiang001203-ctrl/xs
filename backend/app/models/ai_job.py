import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def gen_uuid() -> str:
    return str(uuid.uuid4())


class AIGenerationJob(Base):
    __tablename__ = "ai_generation_jobs"
    __table_args__ = {"comment": "AI生成任务表"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid, comment="任务ID")
    novel_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("novels.id", ondelete="CASCADE"), comment="所属小说ID"
    )
    chapter_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("chapters.id", ondelete="SET NULL"), nullable=True, comment="关联章节ID"
    )
    volume_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("volumes.id", ondelete="SET NULL"), nullable=True, comment="关联卷ID"
    )
    job_type: Mapped[str] = mapped_column(
        Enum(
            "outline",
            "titles",
            "book_synopsis",
            "book_volumes",
            "characters",
            "worldbuilding",
            "chapter_synopsis",
            "chapter_content",
            "volume_synopsis",
            "chapter_segment",
            "chat",
            "assistant_workflow",
        ),
        nullable=False,
        comment="任务类型",
    )
    status: Mapped[str] = mapped_column(
        Enum("queued", "running", "completed", "failed"),
        default="queued",
        nullable=False,
        comment="任务状态",
    )
    progress_message: Mapped[str | None] = mapped_column(String(255), comment="进度提示")
    request_payload: Mapped[str | None] = mapped_column(Text(length=4294967295), comment="任务请求载荷")
    result_payload: Mapped[str | None] = mapped_column(Text(length=4294967295), comment="任务结果载荷")
    partial_text: Mapped[str | None] = mapped_column(Text(length=4294967295), comment="中途已保存的原始输出")
    error_message: Mapped[str | None] = mapped_column(Text, comment="错误信息")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, comment="创建时间")
    started_at: Mapped[datetime | None] = mapped_column(DateTime, comment="开始时间")
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, comment="结束时间")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        comment="更新时间",
    )
