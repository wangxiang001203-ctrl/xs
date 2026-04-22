import uuid
from datetime import datetime
from sqlalchemy import String, Text, Integer, Enum, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


def gen_uuid() -> str:
    return str(uuid.uuid4())


class AIContextSnapshot(Base):
    __tablename__ = "ai_context_snapshots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    novel_id: Mapped[str] = mapped_column(String(36), ForeignKey("novels.id", ondelete="CASCADE"))
    chapter_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("chapters.id", ondelete="SET NULL"))
    snapshot_type: Mapped[str] = mapped_column(
        Enum("outline", "chapter", "synopsis", "worldbuilding"), nullable=False
    )
    compressed_summary: Mapped[str | None] = mapped_column(Text(length=4294967295))
    token_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
