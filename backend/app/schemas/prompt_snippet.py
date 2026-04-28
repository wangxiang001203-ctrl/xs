from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class PromptSnippetBase(BaseModel):
    scope: str = "common"
    novel_id: Optional[str] = None
    title: str
    description: Optional[str] = None
    content: str


class PromptSnippetCreate(PromptSnippetBase):
    pass


class PromptSnippetUpdate(BaseModel):
    scope: Optional[str] = None
    novel_id: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    content: Optional[str] = None


class PromptSnippetOut(PromptSnippetBase):
    id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
