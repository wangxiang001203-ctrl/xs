from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator


class StoryEntityBase(BaseModel):
    entity_type: str = Field(..., max_length=40)
    name: str = Field(..., max_length=160)
    aliases: list[str] = Field(default_factory=list)
    summary: str | None = None
    body_md: str | None = None
    tags: list[str] = Field(default_factory=list)
    current_state: dict[str, Any] = Field(default_factory=dict)
    status: str = "active"
    graph_role: str = Field(default="supporting", max_length=40)
    importance: int = Field(default=3, ge=1, le=5)
    graph_layer: int = Field(default=2, ge=0, le=9)
    graph_position: dict[str, Any] = Field(default_factory=dict)
    first_appearance_chapter: int | None = None

    @field_validator("aliases", "tags", mode="before")
    @classmethod
    def _list_default(cls, value: Any) -> list[str]:
        return value or []

    @field_validator("current_state", "graph_position", mode="before")
    @classmethod
    def _dict_default(cls, value: Any) -> dict[str, Any]:
        return value or {}

    @field_validator("graph_role", mode="before")
    @classmethod
    def _role_default(cls, value: Any) -> str:
        return value or "supporting"

    @field_validator("importance", mode="before")
    @classmethod
    def _importance_default(cls, value: Any) -> int:
        return value or 3

    @field_validator("graph_layer", mode="before")
    @classmethod
    def _layer_default(cls, value: Any) -> int:
        return 2 if value is None else value


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
    graph_role: str | None = Field(default=None, max_length=40)
    importance: int | None = Field(default=None, ge=1, le=5)
    graph_layer: int | None = Field(default=None, ge=0, le=9)
    graph_position: dict[str, Any] | None = None
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
    relation_strength: float = Field(default=1.0, ge=0.0, le=10.0)
    is_bidirectional: bool = False
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    start_chapter: int | None = None
    end_chapter: int | None = None
    properties: dict[str, Any] = Field(default_factory=dict)
    evidence_text: str | None = None
    status: str = "active"

    @field_validator("properties", mode="before")
    @classmethod
    def _properties_default(cls, value: Any) -> dict[str, Any]:
        return value or {}

    @field_validator("relation_strength", mode="before")
    @classmethod
    def _strength_default(cls, value: Any) -> float:
        return 1.0 if value is None else value

    @field_validator("confidence", mode="before")
    @classmethod
    def _confidence_default(cls, value: Any) -> float:
        return 1.0 if value is None else value


class EntityRelationCreate(EntityRelationBase):
    pass


class EntityRelationUpdate(BaseModel):
    source_entity_id: str | None = None
    target_entity_id: str | None = None
    target_name: str | None = None
    relation_type: str | None = Field(default=None, max_length=40)
    relation_strength: float | None = Field(default=None, ge=0.0, le=10.0)
    is_bidirectional: bool | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    start_chapter: int | None = None
    end_chapter: int | None = None
    properties: dict[str, Any] | None = None
    evidence_text: str | None = None
    status: str | None = None


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


class EntityGraphNode(BaseModel):
    id: str
    name: str
    entity_type: str
    graph_role: str
    importance: int
    graph_layer: int
    status: str
    summary: str | None = None
    current_state: dict[str, Any] = Field(default_factory=dict)
    graph_position: dict[str, Any] = Field(default_factory=dict)


class EntityGraphEdge(BaseModel):
    id: str
    source_entity_id: str
    target_entity_id: str | None = None
    target_name: str | None = None
    relation_type: str
    relation_strength: float
    is_bidirectional: bool
    confidence: float
    status: str
    evidence_text: str | None = None
    properties: dict[str, Any] = Field(default_factory=dict)


class EntityGraphData(BaseModel):
    center_entity_id: str | None = None
    nodes: list[EntityGraphNode]
    edges: list[EntityGraphEdge]
    implicit_edge_count: int = 0


class EntityGraphBootstrapResult(BaseModel):
    center_entity_id: str | None = None
    entity_count: int
    created_entities: int
    created_relations: int
