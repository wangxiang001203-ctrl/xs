import uuid
from datetime import datetime
from sqlalchemy import String, Text, Integer, DateTime, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


def gen_uuid() -> str:
    return str(uuid.uuid4())


class Synopsis(Base):
    __tablename__ = "synopses"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    chapter_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("chapters.id", ondelete="CASCADE"), unique=True
    )
    novel_id: Mapped[str] = mapped_column(String(36), ForeignKey("novels.id", ondelete="CASCADE"))

    # 开头
    opening_scene: Mapped[str | None] = mapped_column(Text)
    opening_mood: Mapped[str | None] = mapped_column(String(200))
    opening_hook: Mapped[str | None] = mapped_column(Text)
    opening_characters: Mapped[list | None] = mapped_column(JSON, default=list)

    # 发展
    development_events: Mapped[list | None] = mapped_column(JSON, default=list)
    development_conflicts: Mapped[list | None] = mapped_column(JSON, default=list)
    development_characters: Mapped[list | None] = mapped_column(JSON, default=list)

    # 结尾
    ending_resolution: Mapped[str | None] = mapped_column(Text)
    ending_cliffhanger: Mapped[str | None] = mapped_column(Text)
    ending_next_hook: Mapped[str | None] = mapped_column(Text)

    # 汇总（校验用）
    all_characters: Mapped[list | None] = mapped_column(JSON, default=list)
    word_count_target: Mapped[int] = mapped_column(Integer, default=3000)

    # 本章剧情缩略（写完后填写）
    plot_summary_update: Mapped[str | None] = mapped_column(Text)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    chapter: Mapped["Chapter"] = relationship(back_populates="synopsis")
