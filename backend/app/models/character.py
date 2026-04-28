import uuid
from datetime import datetime
from sqlalchemy import String, Text, Integer, Enum, DateTime, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


def gen_uuid() -> str:
    return str(uuid.uuid4())


class Character(Base):
    __tablename__ = "characters"
    __table_args__ = {"comment": "人物设定表"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid, comment="人物ID")
    novel_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("novels.id", ondelete="CASCADE"), comment="所属小说ID"
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False, comment="人物名称")
    aliases: Mapped[list | None] = mapped_column(JSON, default=list, comment="别名/称号")
    role: Mapped[str | None] = mapped_column(String(50), comment="人物定位，如主角/反派")  # 主角/女主/反派/配角
    importance: Mapped[int] = mapped_column(Integer, default=3, comment="角色重要度，1-5")
    gender: Mapped[str | None] = mapped_column(String(10), comment="性别")
    age: Mapped[int | None] = mapped_column(Integer, comment="年龄")
    race: Mapped[str | None] = mapped_column(String(50), default="人族", comment="种族")
    realm: Mapped[str | None] = mapped_column(String(50), comment="当前境界名称")
    realm_level: Mapped[int] = mapped_column(Integer, default=0, comment="境界层级数值")
    faction: Mapped[str | None] = mapped_column(String(100), comment="所属势力")
    techniques: Mapped[list | None] = mapped_column(JSON, default=list, comment="功法/技能列表")
    artifacts: Mapped[list | None] = mapped_column(JSON, default=list, comment="法宝/装备列表")
    appearance: Mapped[str | None] = mapped_column(Text, comment="外貌特征")
    personality: Mapped[str | None] = mapped_column(Text, comment="性格描述")
    background: Mapped[str | None] = mapped_column(Text, comment="人物背景")
    golden_finger: Mapped[str | None] = mapped_column(Text, comment="金手指或特殊能力")  # 金手指/特殊能力
    motivation: Mapped[str | None] = mapped_column(Text, comment="核心动机或执念")  # 核心动机/执念
    profile_md: Mapped[str | None] = mapped_column(Text, comment="角色档案正文")
    relationships: Mapped[list | None] = mapped_column(JSON, default=list, comment="人物关系网")
    status: Mapped[str] = mapped_column(
        Enum("alive", "dead", "unknown"), default="alive", comment="生存状态"
    )
    first_appearance_chapter: Mapped[int | None] = mapped_column(Integer, comment="首次出场章节号")
    last_updated_chapter: Mapped[int | None] = mapped_column(Integer, comment="最近一次更新涉及章节号")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment="更新时间"
    )

    novel: Mapped["Novel"] = relationship(back_populates="characters")
