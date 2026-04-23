from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel


class AIGenerationJobOut(BaseModel):
    id: str
    novel_id: str
    chapter_id: Optional[str] = None
    volume_id: Optional[str] = None
    job_type: str
    status: str
    progress_message: Optional[str] = None
    result_payload: Optional[Any] = None
    partial_text: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    updated_at: datetime
