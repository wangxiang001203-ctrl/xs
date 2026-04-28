import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Outline, Novel, Character, Worldbuilding, Volume, Chapter, OutlineChatMessage
from app.schemas.project import OutlineCreate, OutlineUpdate, OutlineOut
from app.services.file_service import (
    save_outline,
    save_outline_struct,
    save_synopsis,
    save_book_meta,
    save_characters,
    save_worldbuilding,
    save_volume_plan,
)
from app.services.worldbuilding_service import apply_worldbuilding_document, load_worldbuilding_document

router = APIRouter(prefix="/api/projects/{novel_id}/outline", tags=["outline"])
MAX_OUTLINE_ARCHIVES = 5


def _safe_text(value, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text or default


def _safe_int(value, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _load_outline_struct(outline: Outline) -> dict:
    if not outline.main_plot:
        return {}
    try:
        return json.loads(outline.main_plot)
    except Exception:
        return {}


def _volume_plan_markdown(item: dict) -> str:
    volume_no = _safe_int(item.get("volume_no"), 1)
    title = _safe_text(item.get("title"), f"第{volume_no}卷")
    target_words = _safe_int(item.get("target_words"), 30000)
    chapter_count = _safe_int(item.get("chapter_count"), 12)
    main_line = _safe_text(item.get("main_line"), "待补充")
    character_arc = _safe_text(item.get("character_arc"), "待补充")
    ending_hook = _safe_text(item.get("ending_hook"), "待补充")
    return (
        f"# 第{volume_no}卷 {title}\n\n"
        f"- 目标字数：{target_words}\n"
        f"- 预计章节数：{chapter_count}\n"
        f"- 本卷主线：{main_line}\n"
        f"- 人物成长：{character_arc}\n"
        f"- 卷末钩子：{ending_hook}\n"
    )


def _serialize_characters(chars: list[Character]) -> list[dict]:
    return [
        {
            "id": c.id,
            "name": c.name,
            "role": c.role,
            "gender": c.gender,
            "age": c.age,
            "race": c.race,
            "realm": c.realm,
            "realm_level": c.realm_level,
            "faction": c.faction,
            "techniques": c.techniques or [],
            "artifacts": c.artifacts or [],
            "appearance": c.appearance,
            "personality": c.personality,
            "background": c.background,
            "golden_finger": c.golden_finger,
            "motivation": c.motivation,
            "relationships": c.relationships or [],
            "status": c.status,
            "first_appearance_chapter": c.first_appearance_chapter,
        }
        for c in chars
    ]


def _sync_volumes_from_outline(novel_id: str, outline_struct: dict, db: Session):
    volumes_data = outline_struct.get("volumes") or []
    if not volumes_data:
        return

    existing = db.query(Volume).filter(Volume.novel_id == novel_id).all()
    existing_by_number = {v.volume_number: v for v in existing}
    chapter_counts = {
        v.id: db.query(Chapter).filter(Chapter.volume_id == v.id).count()
        for v in existing
    }

    desired_numbers: set[int] = set()
    for index, item in enumerate(volumes_data, start=1):
        volume_no = _safe_int(item.get("volume_no"), index)
        desired_numbers.add(volume_no)
        title = _safe_text(item.get("title"), f"第{volume_no}卷")
        description = "\n".join(
            [
                f"本卷主线：{_safe_text(item.get('main_line'), '待补充')}",
                f"人物成长：{_safe_text(item.get('character_arc'), '待补充')}",
                f"卷末钩子：{_safe_text(item.get('ending_hook'), '待补充')}",
            ]
        )

        volume = existing_by_number.get(volume_no)
        if volume:
            if chapter_counts.get(volume.id, 0) == 0:
                volume.title = title
                volume.description = description
                volume.target_words = _safe_int(item.get("target_words"), 30000)
                volume.planned_chapter_count = _safe_int(item.get("chapter_count"), 12)
                volume.main_line = _safe_text(item.get("main_line"), "待补充")
                volume.character_arc = _safe_text(item.get("character_arc"), "待补充")
                volume.ending_hook = _safe_text(item.get("ending_hook"), "待补充")
                volume.plan_markdown = _volume_plan_markdown(item)
                volume.plan_data = item
        else:
            volume = Volume(
                novel_id=novel_id,
                volume_number=volume_no,
                title=title,
                description=description,
                target_words=_safe_int(item.get("target_words"), 30000),
                planned_chapter_count=_safe_int(item.get("chapter_count"), 12),
                main_line=_safe_text(item.get("main_line"), "待补充"),
                character_arc=_safe_text(item.get("character_arc"), "待补充"),
                ending_hook=_safe_text(item.get("ending_hook"), "待补充"),
                plan_markdown=_volume_plan_markdown(item),
                plan_data=item,
            )
            db.add(volume)

        save_volume_plan(novel_id, volume_no, _volume_plan_markdown(item), item)

    for volume in existing:
        if chapter_counts.get(volume.id, 0) == 0 and volume.volume_number not in desired_numbers:
            db.delete(volume)


def _sync_characters_from_outline(novel_id: str, outline_struct: dict, db: Session):
    protagonist = outline_struct.get("protagonist") or {}
    seeds: list[dict] = []
    if protagonist.get("name"):
        seeds.append(
            {
                "name": protagonist.get("name"),
                "role": "主角",
                "personality": protagonist.get("personality"),
                "background": protagonist.get("background"),
                "golden_finger": protagonist.get("golden_finger"),
                "motivation": protagonist.get("motivation"),
                "realm": protagonist.get("realm"),
                "faction": protagonist.get("faction"),
            }
        )
    seeds.extend(outline_struct.get("core_cast") or [])

    if not seeds:
        return

    existing = db.query(Character).filter(Character.novel_id == novel_id).all()
    existing_by_name = {c.name: c for c in existing}

    for seed in seeds:
        name = _safe_text(seed.get("name"))
        if not name:
            continue
        char = existing_by_name.get(name)
        if not char:
            char = Character(
                novel_id=novel_id,
                name=name,
                role=_safe_text(seed.get("role"), "配角"),
                personality=_safe_text(seed.get("personality")),
                background=_safe_text(seed.get("background")),
                golden_finger=_safe_text(seed.get("golden_finger")),
                motivation=_safe_text(seed.get("motivation")),
                realm=_safe_text(seed.get("realm")),
                faction=_safe_text(seed.get("faction")),
            )
            db.add(char)
            existing_by_name[name] = char
            continue

        patch_map = {
            "role": _safe_text(seed.get("role")),
            "personality": _safe_text(seed.get("personality")),
            "background": _safe_text(seed.get("background")),
            "golden_finger": _safe_text(seed.get("golden_finger")),
            "motivation": _safe_text(seed.get("motivation")),
            "realm": _safe_text(seed.get("realm")),
            "faction": _safe_text(seed.get("faction")),
        }
        for field, value in patch_map.items():
            if value and not getattr(char, field):
                setattr(char, field, value)


def _sync_worldbuilding_from_outline(novel_id: str, outline_struct: dict, db: Session):
    world_seed = outline_struct.get("world_seed") or {}
    wb = db.query(Worldbuilding).filter(Worldbuilding.novel_id == novel_id).first()
    if not wb:
        wb = Worldbuilding(novel_id=novel_id)
        db.add(wb)
    current = load_worldbuilding_document(novel_id, wb)
    apply_worldbuilding_document(
        wb,
        {
            **current,
            "overview": current.get("overview") or "基于已确认大纲同步的世界观种子。",
            "power_system": current.get("power_system") or world_seed.get("cultivation_system") or [],
            "factions": current.get("factions") or world_seed.get("major_factions") or [],
            "geography": current.get("geography") or world_seed.get("major_regions") or [],
            "core_rules": current.get("core_rules") or world_seed.get("core_rules") or [],
            "items": current.get("items") or world_seed.get("treasures") or [],
        },
    )


def _sync_confirmed_outline(novel_id: str, outline: Outline, db: Session):
    novel = db.query(Novel).filter(Novel.id == novel_id).first()
    if not novel:
        raise HTTPException(404, "小说不存在")

    outline_struct = _load_outline_struct(outline)

    if outline.title:
        novel.title = outline.title
    if outline.synopsis:
        novel.synopsis = outline.synopsis

    _sync_volumes_from_outline(novel_id, outline_struct, db)
    _sync_characters_from_outline(novel_id, outline_struct, db)
    _sync_worldbuilding_from_outline(novel_id, outline_struct, db)
    db.commit()
    db.refresh(novel)

    save_book_meta(novel_id, novel.title, novel.synopsis)
    if novel.synopsis:
        save_synopsis(novel_id, novel.synopsis)
    if outline.content:
        save_outline(novel_id, outline.content)
    if outline_struct:
        save_outline_struct(novel_id, outline_struct)

    chars = db.query(Character).filter(Character.novel_id == novel_id).all()
    save_characters(novel_id, _serialize_characters(chars))

    wb = db.query(Worldbuilding).filter(Worldbuilding.novel_id == novel_id).first()
    if wb:
        save_worldbuilding(novel_id, load_worldbuilding_document(novel_id, wb))


@router.get("", response_model=list[OutlineOut])
def list_outlines(novel_id: str, db: Session = Depends(get_db)):
    return db.query(Outline).filter(Outline.novel_id == novel_id).order_by(Outline.version.desc()).all()


@router.get("/latest", response_model=OutlineOut)
def get_latest_outline(novel_id: str, db: Session = Depends(get_db)):
    outline = db.query(Outline).filter(Outline.novel_id == novel_id).order_by(Outline.version.desc()).first()
    if not outline:
        raise HTTPException(404, "大纲不存在")
    return outline


@router.post("", response_model=OutlineOut)
def create_outline(novel_id: str, data: OutlineCreate, db: Session = Depends(get_db)):
    # 版本号自增
    existing_count = db.query(Outline).filter(Outline.novel_id == novel_id).count()
    # 当前正在编辑的大纲不算历史存档，所以允许“当前草稿 + 5 个存档节点”。
    if existing_count >= MAX_OUTLINE_ARCHIVES + 1:
        raise HTTPException(400, "大纲最多保留 5 个存档节点。请先删除不需要的旧存档，再保存新存档。")
    last = db.query(Outline).filter(Outline.novel_id == novel_id).order_by(Outline.version.desc()).first()
    version = (last.version + 1) if last else 1
    outline = Outline(novel_id=novel_id, version=version, **data.model_dump())
    db.add(outline)
    db.commit()
    db.refresh(outline)
    return outline


@router.post("/reset")
def reset_outline(novel_id: str, db: Session = Depends(get_db)):
    novel = db.query(Novel).filter(Novel.id == novel_id).first()
    if not novel:
        raise HTTPException(404, "小说不存在")
    confirmed = db.query(Outline).filter(
        Outline.novel_id == novel_id,
        Outline.confirmed == True,
    ).first()
    if confirmed:
        raise HTTPException(400, "大纲已确认过，不能再清空重写。后续修改请通过大纲打磨和存档节点管理完成。")

    db.query(OutlineChatMessage).filter(OutlineChatMessage.novel_id == novel_id).delete(synchronize_session=False)
    db.query(Outline).filter(Outline.novel_id == novel_id).delete(synchronize_session=False)
    novel.idea = None
    db.commit()
    return {"status": "ok"}


@router.delete("/{outline_id}")
def delete_outline(novel_id: str, outline_id: str, db: Session = Depends(get_db)):
    outline = db.query(Outline).filter(
        Outline.id == outline_id,
        Outline.novel_id == novel_id,
    ).first()
    if not outline:
        raise HTTPException(404, "大纲存档不存在")
    if outline.confirmed:
        raise HTTPException(400, "已确认的大纲存档不能删除")
    db.delete(outline)
    db.commit()
    return {"status": "ok"}


@router.patch("/{outline_id}", response_model=OutlineOut)
def update_outline(novel_id: str, outline_id: str, data: OutlineUpdate, db: Session = Depends(get_db)):
    outline = db.query(Outline).filter(
        Outline.id == outline_id, Outline.novel_id == novel_id
    ).first()
    if not outline:
        raise HTTPException(404, "大纲不存在")
    changes = data.model_dump(exclude_none=True)
    should_confirm = changes.get("confirmed") is True and not outline.confirmed
    if should_confirm:
        existing_confirmed = db.query(Outline).filter(
            Outline.novel_id == novel_id,
            Outline.confirmed == True,
            Outline.id != outline_id,
        ).first()
        if existing_confirmed:
            raise HTTPException(400, "大纲已确认过，确认按钮只能使用一次。后续修改会保存为存档记录，不会重复确认。")

    for k, v in changes.items():
        setattr(outline, k, v)
    db.commit()
    db.refresh(outline)
    if should_confirm:
        _sync_confirmed_outline(novel_id, outline, db)
        db.refresh(outline)
    elif outline.confirmed and outline.content:
        save_outline(novel_id, outline.content)
    return outline
