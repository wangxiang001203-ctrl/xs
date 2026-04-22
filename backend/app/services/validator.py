"""
细纲人物存在性校验
"""
from sqlalchemy.orm import Session
from app.models import Character


def validate_synopsis_characters(
    db: Session, novel_id: str, character_names: list[str]
) -> dict:
    """
    校验细纲中出现的人物是否都在角色库中存在
    返回 {"valid": bool, "missing": list[str]}
    """
    if not character_names:
        return {"valid": True, "missing": []}

    existing = db.query(Character.name).filter(
        Character.novel_id == novel_id
    ).all()
    existing_names = {row.name for row in existing}

    missing = [name for name in character_names if name not in existing_names]
    return {"valid": len(missing) == 0, "missing": missing}
