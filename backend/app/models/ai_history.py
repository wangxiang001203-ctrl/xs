import uuid
from datetime import datetime
from sqlalchemy import String, Text, Integer, Enum, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


def gen_uuid() -> str:
    return str(uuid.uuid4())


class AIContextSnapshot(Base):
    __tablename__ = "ai_context_snapshots"
    __table_args__ = {"comment": "AI上下文快照表"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid, comment="快照ID")
    novel_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("novels.id", ondelete="CASCADE"), comment="所属小说ID"
    )
    chapter_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("chapters.id", ondelete="SET NULL"), comment="关联章节ID"
    )
    snapshot_type: Mapped[str] = mapped_column(
        Enum("outline", "chapter", "synopsis", "worldbuilding"), nullable=False, comment="快照类型"
    )
    compressed_summary: Mapped[str | None] = mapped_column(Text(length=4294967295), comment="压缩后的上下文摘要")
    token_count: Mapped[int] = mapped_column(Integer, default=0, comment="摘要token数")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, comment="创建时间")
