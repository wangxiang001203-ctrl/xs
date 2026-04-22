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
    realm_system: Mapped[dict | None] = mapped_column(JSON)
    currency: Mapped[dict | None] = mapped_column(JSON)
    artifacts: Mapped[list | None] = mapped_column(JSON, default=list)
    techniques: Mapped[list | None] = mapped_column(JSON, default=list)
    factions: Mapped[list | None] = mapped_column(JSON, default=list)
    geography: Mapped[list | None] = mapped_column(JSON, default=list)
    custom_rules: Mapped[list | None] = mapped_column(JSON, default=list)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
