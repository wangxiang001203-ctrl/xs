import uuid
from datetime import datetime
from sqlalchemy import String, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


def gen_uuid() -> str:
    return str(uuid.uuid4())


class BookVolumePlanning(Base):
    """全书分卷规划表 - AI动态规划全书结构"""
    __tablename__ = "book_volume_planning"
    __table_args__ = {"comment": "全书分卷规划"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid, comment="规划ID")
    novel_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("novels.id", ondelete="CASCADE"), comment="所属小说ID"
    )
    
    # AI生成的全书分卷规划长文本
    content: Mapped[str] = mapped_column(
        Text(length=4294967295), comment="分卷规划内容（Markdown格式）"
    )
    
    # 版本管理
    version: Mapped[int] = mapped_column(default=1, comment="规划版本号")
    
    # 确认状态
    confirmed: Mapped[bool] = mapped_column(Boolean, default=False, comment="是否已确认")
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime, comment="确认时间")
    
    # 时间戳
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment="更新时间"
    )
