from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class NovelCreate(BaseModel):
    title: str
    genre: str = "玄幻修仙"
    idea: Optional[str] = None
    synopsis: Optional[str] = None


class NovelUpdate(BaseModel):
    title: Optional[str] = None
    genre: Optional[str] = None
    idea: Optional[str] = None
    synopsis: Optional[str] = None
    status: Optional[str] = None


class NovelOut(BaseModel):
    id: str
    title: str
    genre: str
    idea: Optional[str]
    synopsis: Optional[str]
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class OutlineCreate(BaseModel):
    title: Optional[str] = None
    synopsis: Optional[str] = None
    selling_points: Optional[str] = None
    main_plot: Optional[str] = None
    content: Optional[str] = None
    ai_generated: bool = True
    version_note: Optional[str] = None


class OutlineUpdate(BaseModel):
    title: Optional[str] = None
    synopsis: Optional[str] = None
    selling_points: Optional[str] = None
    main_plot: Optional[str] = None
    content: Optional[str] = None
    confirmed: Optional[bool] = None
    version_note: Optional[str] = None


class OutlineOut(BaseModel):
    id: str
    novel_id: str
    title: Optional[str]
    synopsis: Optional[str]
    selling_points: Optional[str]
    main_plot: Optional[str]
    content: Optional[str]
    ai_generated: bool
    confirmed: bool
    version: int
    version_note: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}
