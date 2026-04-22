import uuid
from datetime import datetime
from sqlalchemy import String, Text, Boolean, Integer, Enum, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


def gen_uuid() -> str:
    return str(uuid.uuid4())


class Novel(Base):
    __tablename__ = "novels"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    genre: Mapped[str] = mapped_column(String(50), default="玄幻修仙")
    idea: Mapped[str | None] = mapped_column(Text)
    synopsis: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(
        Enum("draft", "writing", "completed"), default="draft"
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    outlines: Mapped[list["Outline"]] = relationship(back_populates="novel", cascade="all, delete-orphan")
    characters: Mapped[list["Character"]] = relationship(back_populates="novel", cascade="all, delete-orphan")
    volumes: Mapped[list["Volume"]] = relationship(back_populates="novel", cascade="all, delete-orphan", order_by="Volume.volume_number")
    chapters: Mapped[list["Chapter"]] = relationship(back_populates="novel", cascade="all, delete-orphan", order_by="Chapter.chapter_number")


class Outline(Base):
    __tablename__ = "outlines"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    novel_id: Mapped[str] = mapped_column(String(36), ForeignKey("novels.id", ondelete="CASCADE"))
    
    # 结构化大纲字段
    title: Mapped[str | None] = mapped_column(String(200))
    synopsis: Mapped[str | None] = mapped_column(Text)
    selling_points: Mapped[str | None] = mapped_column(Text)
    main_plot: Mapped[str | None] = mapped_column(Text(length=4294967295)) # 极简主线大纲
    
    # 兼容旧字段，后续可逐步废弃
    content: Mapped[str | None] = mapped_column(Text(length=4294967295))  # LONGTEXT
    
    ai_generated: Mapped[bool] = mapped_column(Boolean, default=True)
    confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    novel: Mapped["Novel"] = relationship(back_populates="outlines")
