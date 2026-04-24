import uuid
from datetime import datetime
from sqlalchemy import String, Text, Integer, Boolean, DateTime, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


def gen_uuid() -> str:
    return str(uuid.uuid4())


class Volume(Base):
    __tablename__ = "volumes"
    __table_args__ = {"comment": "分卷信息表"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid, comment="分卷ID")
    novel_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("novels.id", ondelete="CASCADE"), comment="所属小说ID"
    )
    volume_number: Mapped[int] = mapped_column(Integer, nullable=False, comment="分卷序号")
    title: Mapped[str] = mapped_column(String(200), nullable=False, comment="分卷标题")
    description: Mapped[str | None] = mapped_column(Text, comment="分卷简介")
    target_words: Mapped[int] = mapped_column(Integer, default=0, comment="计划目标字数")
    planned_chapter_count: Mapped[int] = mapped_column(Integer, default=0, comment="计划章节数")
    main_line: Mapped[str | None] = mapped_column(Text, comment="本卷主线")
    character_arc: Mapped[str | None] = mapped_column(Text, comment="人物成长弧线")
    ending_hook: Mapped[str | None] = mapped_column(Text, comment="卷末钩子")
    plan_markdown: Mapped[str | None] = mapped_column(Text(length=4294967295), comment="卷计划Markdown")
    plan_data: Mapped[dict | None] = mapped_column(JSON, default=dict, comment="卷计划结构化数据")
    synopsis_generated: Mapped[bool] = mapped_column(Boolean, default=False, comment="是否已生成分卷细纲")
    review_status: Mapped[str] = mapped_column(String(20), default="draft", comment="分卷审批状态")
    approved_at: Mapped[datetime | None] = mapped_column(DateTime, comment="分卷批准时间")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, comment="创建时间")

    novel: Mapped["Novel"] = relationship(back_populates="volumes")
    chapters: Mapped[list["Chapter"]] = relationship(back_populates="volume", order_by="Chapter.chapter_number")
