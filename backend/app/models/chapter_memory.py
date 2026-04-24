import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def gen_uuid() -> str:
    return str(uuid.uuid4())


class ChapterMemory(Base):
    __tablename__ = "chapter_memories"
    __table_args__ = {"comment": "章节动态记忆表"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid, comment="记忆ID")
    novel_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("novels.id", ondelete="CASCADE"), comment="所属小说ID"
    )
    chapter_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("chapters.id", ondelete="CASCADE"), unique=True, comment="所属章节ID"
    )
    chapter_number: Mapped[int] = mapped_column(Integer, nullable=False, comment="章节号")
    summary: Mapped[str | None] = mapped_column(Text, comment="本章动态记忆摘要")
    key_events: Mapped[list | None] = mapped_column(JSON, default=list, comment="关键事件")
    state_changes: Mapped[list | None] = mapped_column(JSON, default=list, comment="状态变化")
    inventory_changes: Mapped[list | None] = mapped_column(JSON, default=list, comment="物品变化")
    proposed_entities: Mapped[list | None] = mapped_column(JSON, default=list, comment="本章首次提及的新实体")
    open_threads: Mapped[list | None] = mapped_column(JSON, default=list, comment="未回收悬念")
    source_excerpt: Mapped[str | None] = mapped_column(Text, comment="用于生成记忆的来源摘要")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        comment="更新时间",
    )
