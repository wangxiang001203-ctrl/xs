import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def gen_uuid() -> str:
    return str(uuid.uuid4())


class PromptSnippet(Base):
    __tablename__ = "prompt_snippets"
    __table_args__ = {"comment": "用户可复用提示词库"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    novel_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("novels.id", ondelete="CASCADE"))
    scope: Mapped[str] = mapped_column(String(20), default="common", comment="common/project")
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(String(255))
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
