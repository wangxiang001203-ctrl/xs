import uuid
from datetime import datetime
from sqlalchemy import String, Text, Integer, Enum, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


def gen_uuid() -> str:
    return str(uuid.uuid4())


class Chapter(Base):
    __tablename__ = "chapters"
    __table_args__ = {"comment": "章节正文表"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid, comment="章节ID")
    novel_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("novels.id", ondelete="CASCADE"), comment="所属小说ID"
    )
    volume_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("volumes.id", ondelete="SET NULL"), nullable=True, comment="所属卷ID"
    )
    chapter_number: Mapped[int] = mapped_column(Integer, nullable=False, comment="章节序号")
    title: Mapped[str | None] = mapped_column(String(200), comment="章节标题")
    content: Mapped[str | None] = mapped_column(Text(length=4294967295), comment="章节正文")
    word_count: Mapped[int] = mapped_column(Integer, default=0, comment="章节字数")
    plot_summary: Mapped[str | None] = mapped_column(Text, comment="章节剧情摘要")
    status: Mapped[str] = mapped_column(
        Enum("draft", "writing", "completed"), default="draft", comment="章节状态"
    )
    final_approved: Mapped[bool] = mapped_column(Boolean, default=False, comment="是否已人工定稿")
    final_approval_note: Mapped[str | None] = mapped_column(Text, comment="定稿备注")
    final_approved_at: Mapped[datetime | None] = mapped_column(DateTime, comment="定稿时间")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment="更新时间"
    )

    novel: Mapped["Novel"] = relationship(back_populates="chapters")
    volume: Mapped["Volume | None"] = relationship(back_populates="chapters")
    synopsis: Mapped["Synopsis | None"] = relationship(back_populates="chapter", cascade="all, delete-orphan", uselist=False)
