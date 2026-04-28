import uuid
from datetime import datetime
from sqlalchemy import String, Text, Boolean, Integer, Enum, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


def gen_uuid() -> str:
    return str(uuid.uuid4())


class Novel(Base):
    __tablename__ = "novels"
    __table_args__ = {"comment": "小说基础信息表"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid, comment="小说ID")
    title: Mapped[str] = mapped_column(String(200), nullable=False, comment="小说标题")
    genre: Mapped[str] = mapped_column(String(50), default="玄幻修仙", comment="小说题材")
    idea: Mapped[str | None] = mapped_column(Text, comment="创作灵感或初始想法")
    synopsis: Mapped[str | None] = mapped_column(Text, comment="小说简介")
    status: Mapped[str] = mapped_column(
        Enum("draft", "writing", "completed"), default="draft", comment="创作状态"
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment="更新时间"
    )

    outlines: Mapped[list["Outline"]] = relationship(back_populates="novel", cascade="all, delete-orphan")
    characters: Mapped[list["Character"]] = relationship(back_populates="novel", cascade="all, delete-orphan")
    volumes: Mapped[list["Volume"]] = relationship(back_populates="novel", cascade="all, delete-orphan", order_by="Volume.volume_number")
    chapters: Mapped[list["Chapter"]] = relationship(back_populates="novel", cascade="all, delete-orphan", order_by="Chapter.chapter_number")


class Outline(Base):
    __tablename__ = "outlines"
    __table_args__ = {"comment": "小说大纲表"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid, comment="大纲ID")
    novel_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("novels.id", ondelete="CASCADE"), comment="所属小说ID"
    )
    
    # 结构化大纲字段
    title: Mapped[str | None] = mapped_column(String(200), comment="大纲标题")
    synopsis: Mapped[str | None] = mapped_column(Text, comment="故事简介（大纲层）")
    selling_points: Mapped[str | None] = mapped_column(Text, comment="卖点设定")
    main_plot: Mapped[str | None] = mapped_column(
        Text(length=4294967295), comment="主线剧情规划"
    )  # 极简主线大纲
    
    # 兼容旧字段，后续可逐步废弃
    content: Mapped[str | None] = mapped_column(
        Text(length=4294967295), comment="兼容旧版的大纲正文"
    )  # LONGTEXT
    
    ai_generated: Mapped[bool] = mapped_column(Boolean, default=True, comment="是否由AI生成")
    confirmed: Mapped[bool] = mapped_column(Boolean, default=False, comment="是否已确认采用")
    version: Mapped[int] = mapped_column(Integer, default=1, comment="大纲版本号")
    version_note: Mapped[str | None] = mapped_column(String(255), comment="版本备注")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, comment="创建时间")

    novel: Mapped["Novel"] = relationship(back_populates="outlines")
