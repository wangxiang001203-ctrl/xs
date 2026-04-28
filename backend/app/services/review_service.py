import json
from datetime import datetime

from sqlalchemy.orm import Session

from app.models import Character, Chapter, ChapterMemory, EntityProposal, Synopsis, Volume, Worldbuilding
from app.services import ai_service
from app.services.file_service import save_chapter_memory, save_characters, save_entity_proposals, save_worldbuilding
from app.services.validator import validate_story_entities
from app.services.worldbuilding_service import apply_worldbuilding_document, load_worldbuilding_document
from app.services.entity_service import bootstrap_entities_from_existing, get_or_create_entity, scan_chapter_mentions


PROPOSAL_SECTION_MAP = {
    "item": "items",
    "artifact": "items",
    "treasure": "items",
    "faction": "factions",
    "location": "geography",
    "rule": "core_rules",
    "realm": "power_system",
}


def _safe_text(value, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text or default


def _apply_character_updates(db: Session, novel_id: str, chapter_number: int, character_updates: list[dict]):
    """根据章节记忆自动更新角色状态"""
    for update in character_updates:
        name = _safe_text(update.get("name"))
        if not name:
            continue

        character = db.query(Character).filter(
            Character.novel_id == novel_id,
            Character.name == name,
        ).first()

        if not character:
            continue

        # 更新境界
        if update.get("realm"):
            character.realm = _safe_text(update.get("realm"))
        if update.get("realm_level"):
            character.realm_level = _safe_text(update.get("realm_level"))

        # 更新技能（追加不重复）
        new_techniques = update.get("techniques") or []
        if new_techniques:
            existing_techniques = character.techniques or []
            character.techniques = list(set(existing_techniques + new_techniques))

        # 更新法宝（追加不重复）
        new_artifacts = update.get("artifacts") or []
        if new_artifacts:
            existing_artifacts = character.artifacts or []
            character.artifacts = list(set(existing_artifacts + new_artifacts))

        # 更新状态
        if update.get("status"):
            character.status = _safe_text(update.get("status"))

        # 更新关系（追加）
        relationships_changed = update.get("relationships_changed") or []
        if relationships_changed:
            existing_relationships = character.relationships or []
            character.relationships = existing_relationships + [
                {"chapter": chapter_number, "change": rel} for rel in relationships_changed
            ]

    db.flush()
    # 保存更新后的角色列表
    all_characters = db.query(Character).filter(Character.novel_id == novel_id).all()
    save_characters(
        novel_id,
        [
            {
                "id": item.id,
                "name": item.name,
                "role": item.role,
                "gender": item.gender,
                "age": item.age,
                "race": item.race,
                "realm": item.realm,
                "realm_level": item.realm_level,
                "faction": item.faction,
                "techniques": item.techniques or [],
                "artifacts": item.artifacts or [],
                "appearance": item.appearance,
                "personality": item.personality,
                "background": item.background,
                "golden_finger": item.golden_finger,
                "motivation": item.motivation,
                "relationships": item.relationships or [],
                "status": item.status,
                "first_appearance_chapter": item.first_appearance_chapter,
            }
            for item in all_characters
        ],
    )


def serialize_proposal(proposal: EntityProposal) -> dict:
    return {
        "id": proposal.id,
        "novel_id": proposal.novel_id,
        "chapter_id": proposal.chapter_id,
        "volume_id": proposal.volume_id,
        "entity_type": proposal.entity_type,
        "action": proposal.action,
        "entity_name": proposal.entity_name,
        "status": proposal.status,
        "reason": proposal.reason,
        "payload": proposal.payload or {},
        "created_at": proposal.created_at,
        "updated_at": proposal.updated_at,
        "resolved_at": proposal.resolved_at,
    }


def save_all_proposals(db: Session, novel_id: str):
    proposals = db.query(EntityProposal).filter(EntityProposal.novel_id == novel_id).order_by(EntityProposal.created_at.desc()).all()
    save_entity_proposals(novel_id, [serialize_proposal(item) for item in proposals])


def create_entity_proposals(
    db: Session,
    *,
    novel_id: str,
    chapter_id: str | None,
    volume_id: str | None,
    missing_entities: dict[str, list[str]],
    proposal_candidates: list[dict] | None,
) -> list[EntityProposal]:
    proposal_candidates = proposal_candidates or []
    by_name = {
        (_safe_text(item.get("entity_type")), _safe_text(item.get("name"))): item
        for item in proposal_candidates
        if _safe_text(item.get("name"))
    }
    created: list[EntityProposal] = []

    for entity_type, names in missing_entities.items():
        normalized_type = "character" if entity_type == "characters" else entity_type.rstrip("s")
        for name in names:
            clean_name = _safe_text(name)
            if not clean_name:
                continue
            exists = db.query(EntityProposal).filter(
                EntityProposal.novel_id == novel_id,
                EntityProposal.chapter_id == chapter_id,
                EntityProposal.volume_id == volume_id,
                EntityProposal.entity_type == normalized_type,
                EntityProposal.entity_name == clean_name,
                EntityProposal.status == "pending",
            ).first()
            if exists:
                continue
            candidate = by_name.get((normalized_type, clean_name)) or {}
            proposal = EntityProposal(
                novel_id=novel_id,
                chapter_id=chapter_id,
                volume_id=volume_id,
                entity_type=normalized_type,
                action=_safe_text(candidate.get("action"), "create"),
                entity_name=clean_name,
                status="pending",
                reason=_safe_text(candidate.get("reason"), "AI 首次提及，等待作者确认是否入库。"),
                payload={
                    "target_section": _safe_text(candidate.get("target_section")),
                    "entry": candidate.get("entry") or {
                        "name": clean_name,
                        "summary": _safe_text(candidate.get("summary")),
                        "details": _safe_text(candidate.get("details")),
                    },
                },
            )
            db.add(proposal)
            created.append(proposal)
    return created


def collect_pending_proposals_for_chapter(db: Session, novel_id: str, chapter_id: str) -> list[EntityProposal]:
    return db.query(EntityProposal).filter(
        EntityProposal.novel_id == novel_id,
        EntityProposal.chapter_id == chapter_id,
        EntityProposal.status == "pending",
    ).order_by(EntityProposal.created_at.asc()).all()


def _append_worldbuilding_entry(document: dict, proposal: EntityProposal):
    payload = proposal.payload or {}
    entry = payload.get("entry") or {"name": proposal.entity_name}
    target_section = _safe_text(payload.get("target_section"))
    normalized_type = proposal.entity_type

    legacy_field = PROPOSAL_SECTION_MAP.get(normalized_type, target_section)
    if legacy_field in {"items", "factions", "geography", "core_rules", "power_system"}:
        entries = list(document.get(legacy_field) or [])
        item_name = _safe_text(entry.get("name"), proposal.entity_name)
        if legacy_field == "core_rules":
            exists = next((item for item in entries if _safe_text(item.get("rule_name")) == item_name), None)
            if not exists:
                entries.append({
                    "rule_name": item_name,
                    "description": _safe_text(entry.get("summary") or entry.get("details")),
                })
        else:
            exists = next((item for item in entries if _safe_text(item.get("name")) == item_name), None)
            if not exists:
                entries.append({
                    "name": item_name,
                    "description": _safe_text(entry.get("summary") or entry.get("details")),
                })
        document[legacy_field] = entries
        return

    sections = list(document.get("sections") or [])
    section_id = target_section or f"custom_{normalized_type}"
    section = next((item for item in sections if _safe_text(item.get("id")) == section_id), None)
    if not section:
        section = {
            "id": section_id,
            "name": target_section or proposal.entity_type,
            "description": "由实体提案自动补录",
            "generation_hint": "",
            "entries": [],
        }
        sections.append(section)
    section_entries = list(section.get("entries") or [])
    item_name = _safe_text(entry.get("name"), proposal.entity_name)
    if not next((item for item in section_entries if _safe_text(item.get("name")) == item_name), None):
        section_entries.append({
            "name": item_name,
            "summary": _safe_text(entry.get("summary")),
            "details": _safe_text(entry.get("details")),
            "tags": entry.get("tags") or [],
            "attributes": entry.get("attributes") or {},
        })
    section["entries"] = section_entries
    document["sections"] = sections


def apply_proposal(db: Session, proposal: EntityProposal):
    if proposal.entity_type == "character":
        payload = proposal.payload or {}
        entry = payload.get("entry") or {}
        character = db.query(Character).filter(
            Character.novel_id == proposal.novel_id,
            Character.name == proposal.entity_name,
        ).first()
        if not character:
            character = Character(
                novel_id=proposal.novel_id,
                name=proposal.entity_name,
                role=_safe_text(entry.get("role"), "配角"),
                personality=_safe_text(entry.get("summary")),
                background=_safe_text(entry.get("details"), "由提案补录。"),
                status="alive",
            )
            db.add(character)
        else:
            if not character.personality:
                character.personality = _safe_text(entry.get("summary"))
            if not character.background:
                character.background = _safe_text(entry.get("details"))
        db.flush()
        get_or_create_entity(
            db,
            novel_id=proposal.novel_id,
            entity_type="character",
            name=proposal.entity_name,
            aliases=entry.get("aliases") or [],
            summary=_safe_text(entry.get("summary") or entry.get("role")),
            body_md=_safe_text(entry.get("details")),
            first_appearance_chapter=character.first_appearance_chapter,
        )
        all_characters = db.query(Character).filter(Character.novel_id == proposal.novel_id).all()
        save_characters(
            proposal.novel_id,
            [
                {
                    "id": item.id,
                    "name": item.name,
                    "role": item.role,
                    "gender": item.gender,
                    "age": item.age,
                    "race": item.race,
                    "realm": item.realm,
                    "realm_level": item.realm_level,
                    "faction": item.faction,
                    "techniques": item.techniques or [],
                    "artifacts": item.artifacts or [],
                    "appearance": item.appearance,
                    "personality": item.personality,
                    "background": item.background,
                    "golden_finger": item.golden_finger,
                    "motivation": item.motivation,
                    "relationships": item.relationships or [],
                    "status": item.status,
                    "first_appearance_chapter": item.first_appearance_chapter,
                }
                for item in all_characters
            ],
        )
        return

    wb = db.query(Worldbuilding).filter(Worldbuilding.novel_id == proposal.novel_id).first()
    if not wb:
        wb = Worldbuilding(novel_id=proposal.novel_id)
        db.add(wb)
        db.flush()
    document = load_worldbuilding_document(proposal.novel_id, wb)
    _append_worldbuilding_entry(document, proposal)
    apply_worldbuilding_document(wb, document)
    payload = proposal.payload or {}
    entry = payload.get("entry") or {}
    normalized_type = proposal.entity_type
    if normalized_type in {"artifact", "treasure"}:
        normalized_type = "item"
    elif normalized_type == "location":
        normalized_type = "location"
    elif normalized_type == "realm":
        normalized_type = "realm"
    get_or_create_entity(
        db,
        novel_id=proposal.novel_id,
        entity_type=normalized_type,
        name=proposal.entity_name,
        aliases=entry.get("aliases") or [],
        summary=_safe_text(entry.get("summary")),
        body_md=_safe_text(entry.get("details")),
    )
    save_worldbuilding(proposal.novel_id, load_worldbuilding_document(proposal.novel_id, wb))


async def build_chapter_memory(db: Session, chapter: Chapter, synopsis: Synopsis | None) -> ChapterMemory:
    existing = db.query(ChapterMemory).filter(ChapterMemory.chapter_id == chapter.id).first()
    if not existing:
        existing = ChapterMemory(
            novel_id=chapter.novel_id,
            chapter_id=chapter.id,
            chapter_number=chapter.chapter_number,
        )
        db.add(existing)

    referenced = synopsis.referenced_entities if synopsis and isinstance(synopsis.referenced_entities, dict) else {}
    fallback_summary = synopsis.plot_summary_update if synopsis and synopsis.plot_summary_update else chapter.plot_summary or ""
    fallback_events = list(synopsis.development_events or []) if synopsis else []
    fallback_threads = []
    if synopsis and synopsis.ending_next_hook:
        fallback_threads.append(synopsis.ending_next_hook)
    if synopsis and synopsis.ending_cliffhanger:
        fallback_threads.append(synopsis.ending_cliffhanger)

    content = chapter.content or ""
    source_excerpt = content[:4000]
    memory_payload = None

    if content.strip():
        prompt = f"""你是长篇玄幻修仙小说的连续性编辑。请只依据给定章节正文与细纲，抽取本章已经真实发生且能影响后续写作的事实。

输出 JSON：
```json
{{
  "summary": "80-180字总结本章核心剧情",
  "key_events": ["事件1：具体发生了什么", "事件2：..."],
  "state_changes": [
    "角色A：境界从XX突破到XX",
    "角色B：获得了XX身份/地位",
    "角色C：与角色D的关系变为XX"
  ],
  "inventory_changes": [
    "获得：XX道具/功法/资源（来源：XX）",
    "失去：XX道具/资源（原因：XX）",
    "消耗：XX资源用于XX"
  ],
  "open_threads": [
    "悬念1：XX事件尚未解决",
    "伏笔1：XX提到的XX还未揭晓"
  ],
  "character_updates": [
    {{
      "name": "角色名",
      "realm": "当前境界",
      "realm_level": "境界层级",
      "techniques": ["新获得的功法/技能"],
      "artifacts": ["新获得的法宝/道具"],
      "status": "当前状态（如：受伤/闭关/追杀中）",
      "relationships_changed": ["与XX的关系变为XX"]
    }}
  ]
}}
```

要求：
1. 只能写正文里已经真实发生的事实，不能脑补
2. 如果正文没有明确写到突破、获得道具、关系变化，就不要编造
3. state_changes要具体，包含变化前后的状态
4. inventory_changes要注明来源和用途
5. character_updates用于后续自动更新角色库
6. 只输出 JSON"""
        if synopsis and synopsis.content_md:
            prompt += f"\n\n【本章细纲】\n{synopsis.content_md[:1800]}"
        prompt += f"\n\n【本章正文】\n{content[:6000]}"
        try:
            response = await ai_service.generate_once("你是严格的小说事实抽取器。", prompt)
            memory_payload = json.loads(response.strip().removeprefix("```json").removesuffix("```").strip())
        except Exception:
            memory_payload = None

    existing.summary = _safe_text((memory_payload or {}).get("summary"), fallback_summary)
    existing.key_events = (memory_payload or {}).get("key_events") or fallback_events
    existing.state_changes = (memory_payload or {}).get("state_changes") or []
    existing.inventory_changes = (memory_payload or {}).get("inventory_changes") or []
    existing.proposed_entities = [
        *[{"type": key, "name": name} for key, values in referenced.items() for name in (values or []) if key != "characters"],
    ]
    existing.open_threads = (memory_payload or {}).get("open_threads") or fallback_threads
    existing.source_excerpt = source_excerpt
    db.flush()

    # 自动更新角色状态
    character_updates = (memory_payload or {}).get("character_updates") or []
    if character_updates:
        _apply_character_updates(db, chapter.novel_id, chapter.chapter_number, character_updates)

    save_chapter_memory(
        chapter.novel_id,
        chapter.chapter_number,
        {
            "summary": existing.summary,
            "key_events": existing.key_events or [],
            "state_changes": existing.state_changes or [],
            "inventory_changes": existing.inventory_changes or [],
            "proposed_entities": existing.proposed_entities or [],
            "open_threads": existing.open_threads or [],
            "source_excerpt": existing.source_excerpt or "",
        },
    )
    return existing


def chapter_access_guard(db: Session, chapter: Chapter) -> dict:
    previous = db.query(Chapter).filter(
        Chapter.novel_id == chapter.novel_id,
        Chapter.chapter_number == chapter.chapter_number - 1,
    ).first()
    if previous and not previous.final_approved:
        return {
            "ok": False,
            "reason": f"第{previous.chapter_number}章尚未人工定稿，不能进入下一章。",
        }

    if chapter.volume_id:
        volume = db.query(Volume).filter(Volume.id == chapter.volume_id).first()
        if volume and volume.review_status != "approved":
            return {
                "ok": False,
                "reason": f"《{volume.title}》分卷节奏尚未审批通过，请先确认本卷细纲。",
            }

    synopsis = db.query(Synopsis).filter(Synopsis.chapter_id == chapter.id).first()
    if not synopsis:
        return {
            "ok": False,
            "reason": "本章还没有已确认的细纲，请先生成并审批细纲。",
        }
    if synopsis.review_status != "approved":
        return {
            "ok": False,
            "reason": "本章细纲尚未审批通过，请先确认细纲。",
        }
    return {"ok": True, "reason": ""}


def validate_and_prepare_proposals(db: Session, novel_id: str, referenced_entities: dict | None, proposal_candidates: list[dict] | None, chapter_id: str | None = None, volume_id: str | None = None) -> tuple[dict[str, list[str]], list[EntityProposal]]:
    missing_entities = validate_story_entities(db, novel_id, referenced_entities)
    created = create_entity_proposals(
        db,
        novel_id=novel_id,
        chapter_id=chapter_id,
        volume_id=volume_id,
        missing_entities=missing_entities,
        proposal_candidates=proposal_candidates,
    )
    return missing_entities, created


def mark_proposal_status(proposal: EntityProposal, status: str):
    proposal.status = status
    proposal.resolved_at = datetime.utcnow()
