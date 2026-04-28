from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class StoryEntityBase(BaseModel):
    entity_type: str = Field(..., max_length=40)
    name: str = Field(..., max_length=160)
    aliases: list[str] = Field(default_factory=list)
    summary: str | None = None
    body_md: str | None = None
    tags: list[str] = Field(default_factory=list)
    current_state: dict[str, Any] = Field(default_factory=dict)
    status: str = "active"
    first_appearance_chapter: int | None = None


class StoryEntityCreate(StoryEntityBase):
    pass


class StoryEntityUpdate(BaseModel):
    entity_type: str | None = Field(default=None, max_length=40)
    name: str | None = Field(default=None, max_length=160)
    aliases: list[str] | None = None
    summary: str | None = None
    body_md: str | None = None
    tags: list[str] | None = None
    current_state: dict[str, Any] | None = None
    status: str | None = None
    first_appearance_chapter: int | None = None


class StoryEntityOut(StoryEntityBase):
    id: str
    novel_id: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class EntityMentionOut(BaseModel):
    id: str
    novel_id: str
    entity_id: str
    chapter_id: str | None
    chapter_number: int | None
    mention_text: str
    source: str
    confidence: float
    evidence_text: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class EntityEventBase(BaseModel):
    event_type: str = Field(..., max_length=40)
    chapter_id: str | None = None
    chapter_number: int | None = None
    title: str | None = None
    from_state: dict[str, Any] = Field(default_factory=dict)
    to_state: dict[str, Any] = Field(default_factory=dict)
    delta: dict[str, Any] = Field(default_factory=dict)
    source: str = "manual"
    confidence: float = 1.0
    evidence_text: str | None = None
    reason: str | None = None
    status: str = "active"


class EntityEventCreate(EntityEventBase):
    pass


class EntityEventOut(EntityEventBase):
    id: str
    novel_id: str
    entity_id: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class EntityRelationBase(BaseModel):
    source_entity_id: str
    target_entity_id: str | None = None
    target_name: str | None = None
    relation_type: str = Field(..., max_length=40)
    start_chapter: int | None = None
    end_chapter: int | None = None
    properties: dict[str, Any] = Field(default_factory=dict)
    evidence_text: str | None = None
    status: str = "active"


class EntityRelationCreate(EntityRelationBase):
    pass


class EntityRelationOut(EntityRelationBase):
    id: str
    novel_id: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class EntityScanRequest(BaseModel):
    chapter_id: str | None = None


class EntityScanResult(BaseModel):
    scanned_chapters: int
    created_mentions: int
