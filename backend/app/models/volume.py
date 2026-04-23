import uuid
from datetime import datetime
from sqlalchemy import String, Text, Integer, Boolean, DateTime, ForeignKey
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
    synopsis_generated: Mapped[bool] = mapped_column(Boolean, default=False, comment="是否已生成分卷细纲")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, comment="创建时间")

    novel: Mapped["Novel"] = relationship(back_populates="volumes")
    chapters: Mapped[list["Chapter"]] = relationship(back_populates="volume", order_by="Chapter.chapter_number")
