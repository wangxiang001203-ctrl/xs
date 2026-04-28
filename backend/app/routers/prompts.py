from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import PromptSnippet
from app.schemas.prompt_snippet import PromptSnippetCreate, PromptSnippetOut, PromptSnippetUpdate

router = APIRouter(prefix="/api/prompts", tags=["prompts"])


def _normalize_scope(scope: str | None) -> str:
    return "project" if scope == "project" else "common"


@router.get("", response_model=list[PromptSnippetOut])
def list_prompts(
    novel_id: str | None = None,
    scope: str | None = None,
    db: Session = Depends(get_db),
):
    query = db.query(PromptSnippet)
    if scope:
        query = query.filter(PromptSnippet.scope == _normalize_scope(scope))
    elif novel_id:
        query = query.filter(or_(
            PromptSnippet.scope == "common",
            and_(PromptSnippet.scope == "project", PromptSnippet.novel_id == novel_id),
        ))
    else:
        query = query.filter(PromptSnippet.scope == "common")
    return query.order_by(PromptSnippet.scope.asc(), PromptSnippet.updated_at.desc()).all()


@router.post("", response_model=PromptSnippetOut)
def create_prompt(payload: PromptSnippetCreate, db: Session = Depends(get_db)):
    scope = _normalize_scope(payload.scope)
    if scope == "project" and not payload.novel_id:
        raise HTTPException(400, "项目提示词必须绑定小说")
    item = PromptSnippet(
        scope=scope,
        novel_id=payload.novel_id if scope == "project" else None,
        title=payload.title.strip(),
        description=(payload.description or "").strip() or None,
        content=payload.content.strip(),
    )
    if not item.title or not item.content:
        raise HTTPException(400, "提示词简称和内容不能为空")
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.patch("/{prompt_id}", response_model=PromptSnippetOut)
def update_prompt(prompt_id: str, payload: PromptSnippetUpdate, db: Session = Depends(get_db)):
    item = db.query(PromptSnippet).filter(PromptSnippet.id == prompt_id).first()
    if not item:
        raise HTTPException(404, "提示词不存在")
    data = payload.model_dump(exclude_unset=True)
    if "scope" in data:
        item.scope = _normalize_scope(data["scope"])
    if "novel_id" in data:
        item.novel_id = data["novel_id"] if item.scope == "project" else None
    if "title" in data:
        item.title = (data["title"] or "").strip()
    if "description" in data:
        item.description = (data["description"] or "").strip() or None
    if "content" in data:
        item.content = (data["content"] or "").strip()
    if item.scope == "project" and not item.novel_id:
        raise HTTPException(400, "项目提示词必须绑定小说")
    if not item.title or not item.content:
        raise HTTPException(400, "提示词简称和内容不能为空")
    db.commit()
    db.refresh(item)
    return item


@router.delete("/{prompt_id}")
def delete_prompt(prompt_id: str, db: Session = Depends(get_db)):
    item = db.query(PromptSnippet).filter(PromptSnippet.id == prompt_id).first()
    if not item:
        raise HTTPException(404, "提示词不存在")
    db.delete(item)
    db.commit()
    return {"status": "ok"}
