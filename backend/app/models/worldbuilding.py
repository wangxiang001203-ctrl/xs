import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


def gen_uuid() -> str:
    return str(uuid.uuid4())


class Worldbuilding(Base):
    __tablename__ = "worldbuilding"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    novel_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("novels.id", ondelete="CASCADE"), unique=True
    )
    power_system: Mapped[list | None] = mapped_column(JSON, default=list) # 力量/境界体系
    factions: Mapped[list | None] = mapped_column(JSON, default=list) # 势力/组织
    geography: Mapped[list | None] = mapped_column(JSON, default=list) # 地理/地点
    core_rules: Mapped[list | None] = mapped_column(JSON, default=list) # 核心法则/世界规则
    items: Mapped[list | None] = mapped_column(JSON, default=list) # 关键物品/资源
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
