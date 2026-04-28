import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def gen_uuid() -> str:
    return str(uuid.uuid4())


class OutlineChatMessage(Base):
    __tablename__ = "outline_chat_messages"
    __table_args__ = {"comment": "大纲多轮打磨对话表"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid, comment="消息ID")
    novel_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("novels.id", ondelete="CASCADE"), index=True, comment="所属小说ID"
    )
    outline_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("outlines.id", ondelete="SET NULL"), nullable=True, comment="关联大纲版本ID"
    )
    role: Mapped[str] = mapped_column(
        Enum("user", "assistant", "system"),
        nullable=False,
        comment="消息角色",
    )
    content: Mapped[str] = mapped_column(Text(length=4294967295), nullable=False, comment="消息内容")
    metadata_json: Mapped[str | None] = mapped_column(Text(length=4294967295), comment="附加元数据")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, comment="创建时间")
