import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def gen_uuid() -> str:
    return str(uuid.uuid4())


class EntityProposal(Base):
    __tablename__ = "entity_proposals"
    __table_args__ = {"comment": "实体新增或更新提案表"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid, comment="提案ID")
    novel_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("novels.id", ondelete="CASCADE"), comment="所属小说ID"
    )
    chapter_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("chapters.id", ondelete="SET NULL"), comment="关联章节ID"
    )
    volume_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("volumes.id", ondelete="SET NULL"), comment="关联分卷ID"
    )
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False, comment="实体类型")
    action: Mapped[str] = mapped_column(String(20), default="create", comment="动作类型")
    entity_name: Mapped[str] = mapped_column(String(200), nullable=False, comment="实体名称")
    status: Mapped[str] = mapped_column(String(20), default="pending", comment="审批状态")
    reason: Mapped[str | None] = mapped_column(Text, comment="提案理由")
    payload: Mapped[dict | None] = mapped_column(JSON, default=dict, comment="提案载荷")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        comment="更新时间",
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, comment="处理时间")
