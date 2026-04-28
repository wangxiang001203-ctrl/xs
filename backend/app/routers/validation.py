from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database import get_db
from app.services.validator import validate_chapter_content_entities

router = APIRouter(prefix="/api/projects/{novel_id}/validation", tags=["validation"])


class ValidateContentRequest(BaseModel):
    chapter_id: str
    content: str


@router.post("/validate-content")
def validate_content(novel_id: str, data: ValidateContentRequest, db: Session = Depends(get_db)):
    """
    验证章节正文是否存在幻觉（引用不存在的实体）
    """
    result = validate_chapter_content_entities(db, novel_id, data.chapter_id, data.content)
    return result
