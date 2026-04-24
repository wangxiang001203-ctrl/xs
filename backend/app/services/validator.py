"""
创作实体存在性校验
"""
from sqlalchemy.orm import Session

from app.models import Character, Worldbuilding
from app.services.worldbuilding_service import load_worldbuilding_document


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


def collect_worldbuilding_entities(db: Session, novel_id: str) -> dict[str, set[str]]:
    wb = db.query(Worldbuilding).filter(Worldbuilding.novel_id == novel_id).first()
    if not wb:
        return {
            "items": set(),
            "factions": set(),
            "locations": set(),
            "rules": set(),
            "realms": set(),
            "sections": set(),
        }

    document = load_worldbuilding_document(novel_id, wb)
    result = {
        "items": set(),
        "factions": set(),
        "locations": set(),
        "rules": set(),
        "realms": set(),
        "sections": set(),
    }

    for item in document.get("items") or []:
        name = str(item.get("name") or "").strip()
        if name:
            result["items"].add(name)
    for item in document.get("factions") or []:
        name = str(item.get("name") or "").strip()
        if name:
            result["factions"].add(name)
    for item in document.get("geography") or []:
        name = str(item.get("name") or "").strip()
        if name:
            result["locations"].add(name)
    for item in document.get("core_rules") or []:
        name = str(item.get("rule_name") or item.get("name") or "").strip()
        if name:
            result["rules"].add(name)
    for item in document.get("power_system") or []:
        name = str(item.get("name") or "").strip()
        if name:
            result["realms"].add(name)
    for section in document.get("sections") or []:
        section_name = str(section.get("name") or "").strip()
        if section_name:
            result["sections"].add(section_name)
        for entry in section.get("entries") or []:
            entry_name = str(entry.get("name") or "").strip()
            if not entry_name:
                continue
            result["items"].add(entry_name)
    return result


def validate_story_entities(db: Session, novel_id: str, references: dict | None) -> dict[str, list[str]]:
    references = references if isinstance(references, dict) else {}
    characters = validate_synopsis_characters(db, novel_id, references.get("characters") or [])
    world_entities = collect_worldbuilding_entities(db, novel_id)

    missing_world: dict[str, list[str]] = {}
    mapping = {
        "items": "items",
        "factions": "factions",
        "locations": "locations",
        "rules": "rules",
        "realms": "realms",
    }
    for ref_key, store_key in mapping.items():
        candidates = [str(item).strip() for item in (references.get(ref_key) or []) if str(item).strip()]
        missing = [name for name in candidates if name not in world_entities[store_key]]
        missing_world[ref_key] = missing

    return {
        "characters": characters["missing"],
        **missing_world,
    }
