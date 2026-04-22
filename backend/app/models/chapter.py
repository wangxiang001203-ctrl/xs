import uuid
from datetime import datetime
from sqlalchemy import String, Text, Integer, Enum, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


def gen_uuid() -> str:
    return str(uuid.uuid4())


class Chapter(Base):
    __tablename__ = "chapters"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    novel_id: Mapped[str] = mapped_column(String(36), ForeignKey("novels.id", ondelete="CASCADE"))
    volume_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("volumes.id", ondelete="SET NULL"), nullable=True)
    chapter_number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str | None] = mapped_column(String(200))
    content: Mapped[str | None] = mapped_column(Text(length=4294967295))
    word_count: Mapped[int] = mapped_column(Integer, default=0)
    plot_summary: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(
        Enum("draft", "writing", "completed"), default="draft"
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    novel: Mapped["Novel"] = relationship(back_populates="chapters")
    volume: Mapped["Volume | None"] = relationship(back_populates="chapters")
    synopsis: Mapped["Synopsis | None"] = relationship(back_populates="chapter", cascade="all, delete-orphan", uselist=False)
