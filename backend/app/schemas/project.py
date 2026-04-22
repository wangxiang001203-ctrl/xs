from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class NovelCreate(BaseModel):
    title: str
    genre: str = "玄幻修仙"
    idea: Optional[str] = None


class NovelUpdate(BaseModel):
    title: Optional[str] = None
    genre: Optional[str] = None
    idea: Optional[str] = None
    status: Optional[str] = None


class NovelOut(BaseModel):
    id: str
    title: str
    genre: str
    idea: Optional[str]
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class OutlineCreate(BaseModel):
    content: str
    ai_generated: bool = True


class OutlineUpdate(BaseModel):
    content: Optional[str] = None
    confirmed: Optional[bool] = None


class OutlineOut(BaseModel):
    id: str
    novel_id: str
    content: Optional[str]
    ai_generated: bool
    confirmed: bool
    version: int
    created_at: datetime

    model_config = {"from_attributes": True}
