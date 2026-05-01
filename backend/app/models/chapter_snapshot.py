import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def gen_uuid() -> str:
    return str(uuid.uuid4())


class ChapterSnapshot(Base):
    """
    L1 聚合快照：每10章自动聚合一次，包含：
      - 核心剧情走向摘要
      - 角色状态变化里程碑
      - 关键道具/地点变更
      - 未解决的伏笔清单
    """
    __tablename__ = "chapter_snapshots"
    __table_args__ = {"comment": "10章聚合快照表"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid, comment="快照ID")
    novel_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("novels.id", ondelete="CASCADE"), comment="所属小说ID"
    )
    start_chapter: Mapped[int] = mapped_column(Integer, nullable=False, comment="起始章节号")
    end_chapter: Mapped[int] = mapped_column(Integer, nullable=False, comment="结束章节号")
    summary: Mapped[str | None] = mapped_column(Text, comment="聚合摘要")
    key_events: Mapped[list | None] = mapped_column(JSON, default=list, comment="关键事件")
    character_arcs: Mapped[list | None] = mapped_column(JSON, default=list, comment="角色成长弧")
    item_changes: Mapped[list | None] = mapped_column(JSON, default=list, comment="道具变更")
    open_threads: Mapped[list | None] = mapped_column(JSON, default=list, comment="未回收伏笔")
    foreshadowing: Mapped[list | None] = mapped_column(JSON, default=list, comment="本章埋下伏笔")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, comment="创建时间")
