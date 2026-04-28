import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def gen_uuid() -> str:
    return str(uuid.uuid4())


class StoryEntity(Base):
    __tablename__ = "story_entities"
    __table_args__ = {"comment": "通用设定实体表"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid, comment="实体ID")
    novel_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("novels.id", ondelete="CASCADE"), index=True, comment="所属小说ID"
    )
    entity_type: Mapped[str] = mapped_column(String(40), index=True, comment="实体类型")
    name: Mapped[str] = mapped_column(String(160), index=True, comment="实体名称")
    aliases: Mapped[list | None] = mapped_column(JSON, default=list, comment="别名/称呼")
    summary: Mapped[str | None] = mapped_column(Text, comment="一句话设定")
    body_md: Mapped[str | None] = mapped_column(Text(length=4294967295), comment="作者自由设定正文")
    tags: Mapped[list | None] = mapped_column(JSON, default=list, comment="标签")
    current_state: Mapped[dict | None] = mapped_column(JSON, default=dict, comment="由事件流重算出的当前状态")
    status: Mapped[str] = mapped_column(String(24), default="active", index=True, comment="实体状态")
    first_appearance_chapter: Mapped[int | None] = mapped_column(Integer, comment="首次出现章节")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment="更新时间"
    )


class EntityMention(Base):
    __tablename__ = "entity_mentions"
    __table_args__ = {"comment": "实体章节出现索引表"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid, comment="出现记录ID")
    novel_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("novels.id", ondelete="CASCADE"), index=True, comment="所属小说ID"
    )
    entity_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("story_entities.id", ondelete="CASCADE"), index=True, comment="实体ID"
    )
    chapter_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("chapters.id", ondelete="SET NULL"), index=True, comment="章节ID"
    )
    chapter_number: Mapped[int | None] = mapped_column(Integer, index=True, comment="章节号")
    mention_text: Mapped[str] = mapped_column(String(160), comment="命中文本")
    source: Mapped[str] = mapped_column(String(32), default="exact_match", comment="来源")
    confidence: Mapped[float] = mapped_column(Float, default=1.0, comment="置信度")
    evidence_text: Mapped[str | None] = mapped_column(Text, comment="证据片段")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, comment="创建时间")


class EntityEvent(Base):
    __tablename__ = "entity_events"
    __table_args__ = {"comment": "实体状态变化事件表"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid, comment="事件ID")
    novel_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("novels.id", ondelete="CASCADE"), index=True, comment="所属小说ID"
    )
    entity_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("story_entities.id", ondelete="CASCADE"), index=True, comment="实体ID"
    )
    event_type: Mapped[str] = mapped_column(String(40), index=True, comment="事件类型")
    chapter_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("chapters.id", ondelete="SET NULL"), index=True, comment="关联章节ID"
    )
    chapter_number: Mapped[int | None] = mapped_column(Integer, index=True, comment="生效章节")
    title: Mapped[str | None] = mapped_column(String(200), comment="事件标题")
    from_state: Mapped[dict | None] = mapped_column(JSON, default=dict, comment="变化前状态")
    to_state: Mapped[dict | None] = mapped_column(JSON, default=dict, comment="变化后状态")
    delta: Mapped[dict | None] = mapped_column(JSON, default=dict, comment="补充变化")
    source: Mapped[str] = mapped_column(String(32), default="manual", comment="来源")
    confidence: Mapped[float] = mapped_column(Float, default=1.0, comment="置信度")
    evidence_text: Mapped[str | None] = mapped_column(Text, comment="证据片段")
    reason: Mapped[str | None] = mapped_column(Text, comment="补录或修改原因")
    status: Mapped[str] = mapped_column(String(24), default="active", index=True, comment="事件状态")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment="更新时间"
    )


class EntityRelation(Base):
    __tablename__ = "entity_relations"
    __table_args__ = {"comment": "实体关系表"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid, comment="关系ID")
    novel_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("novels.id", ondelete="CASCADE"), index=True, comment="所属小说ID"
    )
    source_entity_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("story_entities.id", ondelete="CASCADE"), index=True, comment="源实体ID"
    )
    target_entity_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("story_entities.id", ondelete="SET NULL"), index=True, comment="目标实体ID"
    )
    target_name: Mapped[str | None] = mapped_column(String(160), comment="未入库目标名称")
    relation_type: Mapped[str] = mapped_column(String(40), index=True, comment="关系类型")
    start_chapter: Mapped[int | None] = mapped_column(Integer, comment="关系开始章节")
    end_chapter: Mapped[int | None] = mapped_column(Integer, comment="关系结束章节")
    properties: Mapped[dict | None] = mapped_column(JSON, default=dict, comment="关系属性")
    evidence_text: Mapped[str | None] = mapped_column(Text, comment="证据片段")
    status: Mapped[str] = mapped_column(String(24), default="active", index=True, comment="关系状态")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment="更新时间"
    )
