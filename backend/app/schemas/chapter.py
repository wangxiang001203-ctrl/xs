from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class ChapterCreate(BaseModel):
    chapter_number: int
    title: Optional[str] = None


class ChapterUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    plot_summary: Optional[str] = None
    status: Optional[str] = None
    final_approved: Optional[bool] = None
    final_approval_note: Optional[str] = None


class ChapterOut(BaseModel):
    id: str
    novel_id: str
    volume_id: Optional[str] = None
    chapter_number: int
    title: Optional[str]
    word_count: int
    plot_summary: Optional[str]
    status: str
    final_approved: bool = False
    final_approval_note: Optional[str] = None
    final_approved_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ChapterContentOut(ChapterOut):
    content: Optional[str]


class SynopsisCreate(BaseModel):
    summary_line: Optional[str] = None
    content_md: Optional[str] = None
    opening_scene: Optional[str] = None
    opening_mood: Optional[str] = None
    opening_hook: Optional[str] = None
    opening_characters: list = []
    development_events: list = []
    development_conflicts: list = []
    development_characters: list = []
    ending_resolution: Optional[str] = None
    ending_cliffhanger: Optional[str] = None
    ending_next_hook: Optional[str] = None
    all_characters: list = []
    word_count_target: int = 3000
    hard_constraints: list = []
    referenced_entities: dict = {}
    review_status: Optional[str] = None
    plot_summary_update: Optional[str] = None


class SynopsisOut(SynopsisCreate):
    id: str
    chapter_id: str
    novel_id: str
    approved_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
