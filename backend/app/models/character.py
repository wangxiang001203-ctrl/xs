import uuid
from datetime import datetime
from sqlalchemy import String, Text, Integer, Enum, DateTime, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


def gen_uuid() -> str:
    return str(uuid.uuid4())


class Character(Base):
    __tablename__ = "characters"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    novel_id: Mapped[str] = mapped_column(String(36), ForeignKey("novels.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    gender: Mapped[str | None] = mapped_column(String(10))
    age: Mapped[int | None] = mapped_column(Integer)
    race: Mapped[str | None] = mapped_column(String(50), default="人族")
    realm: Mapped[str | None] = mapped_column(String(50))
    realm_level: Mapped[int] = mapped_column(Integer, default=0)
    faction: Mapped[str | None] = mapped_column(String(100))
    techniques: Mapped[list | None] = mapped_column(JSON, default=list)
    artifacts: Mapped[list | None] = mapped_column(JSON, default=list)
    appearance: Mapped[str | None] = mapped_column(Text)
    personality: Mapped[str | None] = mapped_column(Text)
    background: Mapped[str | None] = mapped_column(Text)
    relationships: Mapped[list | None] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(
        Enum("alive", "dead", "unknown"), default="alive"
    )
    first_appearance_chapter: Mapped[int | None] = mapped_column(Integer)
    last_updated_chapter: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    novel: Mapped["Novel"] = relationship(back_populates="characters")
