import uuid
from datetime import datetime
from sqlalchemy import String, Text, Integer, DateTime, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


def gen_uuid() -> str:
    return str(uuid.uuid4())


class Synopsis(Base):
    __tablename__ = "synopses"
    __table_args__ = {"comment": "章节细纲表"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid, comment="细纲ID")
    chapter_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("chapters.id", ondelete="CASCADE"), unique=True, comment="所属章节ID（唯一）"
    )
    novel_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("novels.id", ondelete="CASCADE"), comment="所属小说ID"
    )

    # 开头
    opening_scene: Mapped[str | None] = mapped_column(Text, comment="开场场景")
    opening_mood: Mapped[str | None] = mapped_column(String(200), comment="开场氛围")
    opening_hook: Mapped[str | None] = mapped_column(Text, comment="开场钩子")
    opening_characters: Mapped[list | None] = mapped_column(JSON, default=list, comment="开场出场人物")

    # 发展
    development_events: Mapped[list | None] = mapped_column(JSON, default=list, comment="发展阶段关键事件")
    development_conflicts: Mapped[list | None] = mapped_column(JSON, default=list, comment="发展阶段冲突")
    development_characters: Mapped[list | None] = mapped_column(JSON, default=list, comment="发展阶段涉及人物")

    # 结尾
    ending_resolution: Mapped[str | None] = mapped_column(Text, comment="结尾收束")
    ending_cliffhanger: Mapped[str | None] = mapped_column(Text, comment="章末悬念")
    ending_next_hook: Mapped[str | None] = mapped_column(Text, comment="下一章钩子")

    # 汇总（校验用）
    all_characters: Mapped[list | None] = mapped_column(JSON, default=list, comment="本章涉及人物全集")
    word_count_target: Mapped[int] = mapped_column(Integer, default=3000, comment="目标字数")

    # 本章剧情缩略（写完后填写）
    plot_summary_update: Mapped[str | None] = mapped_column(Text, comment="写作后剧情回填摘要")

    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment="更新时间"
    )

    chapter: Mapped["Chapter"] = relationship(back_populates="synopsis")
