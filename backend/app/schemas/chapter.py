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


class ChapterOut(BaseModel):
    id: str
    novel_id: str
    chapter_number: int
    title: Optional[str]
    word_count: int
    plot_summary: Optional[str]
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ChapterContentOut(ChapterOut):
    content: Optional[str]


class SynopsisCreate(BaseModel):
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
    plot_summary_update: Optional[str] = None


class SynopsisOut(SynopsisCreate):
    id: str
    chapter_id: str
    novel_id: str

    model_config = {"from_attributes": True}
