import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, ForeignKey, JSON, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


def gen_uuid() -> str:
    return str(uuid.uuid4())


class Worldbuilding(Base):
    __tablename__ = "worldbuilding"
    __table_args__ = {"comment": "世界观设定表"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid, comment="世界观ID")
    novel_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("novels.id", ondelete="CASCADE"), unique=True, comment="所属小说ID（唯一）"
    )
    overview: Mapped[str | None] = mapped_column(Text, comment="世界总述")
    sections: Mapped[list | None] = mapped_column(JSON, default=list, comment="开放式设定栏目")
    power_system: Mapped[list | None] = mapped_column(JSON, default=list, comment="力量或境界体系")  # 力量/境界体系
    factions: Mapped[list | None] = mapped_column(JSON, default=list, comment="势力组织设定")  # 势力/组织
    geography: Mapped[list | None] = mapped_column(JSON, default=list, comment="地理与关键地点")  # 地理/地点
    core_rules: Mapped[list | None] = mapped_column(JSON, default=list, comment="世界核心规则")  # 核心法则/世界规则
    items: Mapped[list | None] = mapped_column(JSON, default=list, comment="关键物品与资源")  # 关键物品/资源
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment="更新时间"
    )
