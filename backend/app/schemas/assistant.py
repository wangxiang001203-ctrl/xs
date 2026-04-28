from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel


class AssistantRunRequest(BaseModel):
    novel_id: str
    context_type: str = "outline"
    context_id: Optional[str] = None
    messages: list[dict[str, str]] = []
    user_message: str
    current_file: Optional[dict[str, Any]] = None
    context_files: list[str] = []


class AssistantWorkflowStepOut(BaseModel):
    id: str
    step_order: int
    title: str
    status: str
    detail: Optional[str] = None
    files: list[Any] = []
    payload: dict[str, Any] = {}
    created_at: datetime
    finished_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class AssistantWorkflowRunOut(BaseModel):
    id: str
    novel_id: str
    job_id: Optional[str] = None
    context_type: str
    context_id: Optional[str] = None
    user_message: str
    intent: Optional[str] = None
    confidence: Optional[float] = None
    status: str
    result_summary: Optional[str] = None
    payload: dict[str, Any] = {}
    created_at: datetime
    updated_at: datetime
    finished_at: Optional[datetime] = None

    class Config:
        from_attributes = True
