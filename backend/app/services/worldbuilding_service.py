import json
import uuid
from pathlib import Path
from typing import Any

from app.services.file_service import get_project_dir

DEFAULT_SECTION_SPECS = [
    {
        "id": "power_system",
        "name": "力量/境界体系",
        "description": "解释这个世界如何修炼、如何变强、代价是什么、上限在哪里。",
        "aliases": {"力量/境界体系", "力量体系", "境界体系", "修炼体系", "能力体系"},
        "legacy_field": "power_system",
        "name_key": "name",
    },
    {
        "id": "factions",
        "name": "势力/组织",
        "description": "记录宗门、王朝、联盟、世家、魔门等核心势力及其关系。",
        "aliases": {"势力/组织", "势力", "组织", "门派", "宗门"},
        "legacy_field": "factions",
        "name_key": "name",
    },
    {
        "id": "geography",
        "name": "地理/地点",
        "description": "记录大陆、城池、秘境、禁地、山脉等关键地点与空间格局。",
        "aliases": {"地理/地点", "地理", "地点", "地域", "地图"},
        "legacy_field": "geography",
        "name_key": "name",
    },
    {
        "id": "core_rules",
        "name": "核心法则",
        "description": "记录世界运行规则、禁忌、约束、突破边界与长期法则。",
        "aliases": {"核心法则", "法则", "规则", "世界规则"},
        "legacy_field": "core_rules",
        "name_key": "rule_name",
    },
    {
        "id": "items",
        "name": "关键物品",
        "description": "记录宝物、资源、遗物、法器、丹药、钥匙等关键设定物。",
        "aliases": {"关键物品", "物品", "资源", "法宝", "宝物", "关键资源"},
        "legacy_field": "items",
        "name_key": "name",
    },
]

SECTION_SPECS_BY_ID = {item["id"]: item for item in DEFAULT_SECTION_SPECS}


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for item in value:
        text = _text(item)
        if text:
            result.append(text)
    return result


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def _find_spec(section_id: str, section_name: str) -> dict[str, Any] | None:
    if section_id and section_id in SECTION_SPECS_BY_ID:
        return SECTION_SPECS_BY_ID[section_id]
    name = _text(section_name)
    for spec in DEFAULT_SECTION_SPECS:
        if name and name in spec["aliases"]:
            return spec
    return None


def _normalize_entry(raw: Any) -> dict[str, Any] | None:
    if isinstance(raw, str):
        name = _text(raw)
        if not name:
            return None
        return {
            "id": _new_id("entry"),
            "name": name,
            "summary": "",
            "details": "",
            "tags": [],
            "attributes": {},
        }

    if not isinstance(raw, dict):
        return None

    known_name = _text(raw.get("name") or raw.get("title") or raw.get("rule_name"))
    known_summary = _text(raw.get("summary") or raw.get("description") or raw.get("desc"))
    known_details = _text(raw.get("details") or raw.get("notes"))
    attributes = _dict(raw.get("attributes")).copy()
    for key, value in raw.items():
        if key in {"id", "name", "title", "rule_name", "summary", "description", "desc", "details", "notes", "tags", "attributes"}:
            continue
        attributes[key] = value

    if not (known_name or known_summary or known_details):
        return None

    return {
        "id": _text(raw.get("id")) or _new_id("entry"),
        "name": known_name or "未命名设定",
        "summary": known_summary,
        "details": known_details,
        "tags": _string_list(raw.get("tags")),
        "attributes": attributes,
    }


def _normalize_section(raw: Any) -> dict[str, Any] | None:
    raw_dict = _dict(raw)
    if not raw_dict:
        return None

    section_id = _text(raw_dict.get("id"))
    section_name = _text(raw_dict.get("name"))
    spec = _find_spec(section_id, section_name)
    normalized_entries = [entry for entry in (_normalize_entry(item) for item in raw_dict.get("entries", [])) if entry]

    if not (section_name or normalized_entries or _text(raw_dict.get("description")) or _text(raw_dict.get("generation_hint"))):
        return None

    return {
        "id": section_id or (spec["id"] if spec else _new_id("section")),
        "name": section_name or (spec["name"] if spec else "未命名栏目"),
        "description": _text(raw_dict.get("description")) or (spec["description"] if spec else ""),
        "generation_hint": _text(raw_dict.get("generation_hint")),
        "entries": normalized_entries,
    }


def _section_from_legacy(spec: dict[str, Any], items: Any) -> dict[str, Any] | None:
    normalized_entries: list[dict[str, Any]] = []
    for raw in items or []:
        entry = _normalize_entry(raw)
        if not entry and isinstance(raw, dict):
            name = _text(raw.get(spec["name_key"]))
            if name:
                entry = {
                    "id": _new_id("entry"),
                    "name": name,
                    "summary": _text(raw.get("description") or raw.get("desc")),
                    "details": "",
                    "tags": [],
                    "attributes": {k: v for k, v in raw.items() if k not in {spec["name_key"], "description", "desc"}},
                }
        if entry:
            normalized_entries.append(entry)

    if not normalized_entries:
        return None

    return {
        "id": spec["id"],
        "name": spec["name"],
        "description": spec["description"],
        "generation_hint": "",
        "entries": normalized_entries,
    }


def default_worldbuilding_sections() -> list[dict[str, Any]]:
    return [
        {
            "id": spec["id"],
            "name": spec["name"],
            "description": spec["description"],
            "generation_hint": "",
            "entries": [],
        }
        for spec in DEFAULT_SECTION_SPECS
    ]


def merge_sections(base_sections: list[dict[str, Any]], incoming_sections: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    incoming_map: dict[str, dict[str, Any]] = {}
    used_keys: set[str] = set()

    for section in incoming_sections:
        key = section["id"] or section["name"]
        incoming_map[key] = section

    for base in base_sections:
        key = base["id"] or base["name"]
        current = incoming_map.get(key)
        if current:
            merged.append(
                {
                    **base,
                    **current,
                    "generation_hint": current.get("generation_hint") or base.get("generation_hint") or "",
                    "description": current.get("description") or base.get("description") or "",
                    "entries": current.get("entries") or base.get("entries") or [],
                }
            )
            used_keys.add(key)
        else:
            merged.append(base)

    for incoming in incoming_sections:
        key = incoming["id"] or incoming["name"]
        if key in used_keys:
            continue
        merged.append(incoming)

    return merged


def legacy_fields_from_sections(sections: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    legacy = {
        "power_system": [],
        "factions": [],
        "geography": [],
        "core_rules": [],
        "items": [],
    }

    for section in sections:
        spec = _find_spec(_text(section.get("id")), _text(section.get("name")))
        if not spec:
            continue
        output_items: list[dict[str, Any]] = []
        for entry in section.get("entries") or []:
            name = _text(entry.get("name"))
            summary = _text(entry.get("summary"))
            details = _text(entry.get("details"))
            text = summary
            if details:
                text = f"{summary}\n{details}".strip()
            attributes = _dict(entry.get("attributes")).copy()
            if spec["legacy_field"] == "core_rules":
                payload = {"rule_name": name, "description": text}
            else:
                payload = {"name": name, "description": text}
            payload.update(attributes)
            if name or text:
                output_items.append(payload)
        legacy[spec["legacy_field"]] = output_items

    return legacy


def normalize_worldbuilding_document(
    raw: dict[str, Any] | None,
    *,
    fallback_id: str | None = None,
    novel_id: str | None = None,
) -> dict[str, Any]:
    payload = _dict(raw).copy()
    raw_sections = payload.get("sections") or []
    normalized_sections = [section for section in (_normalize_section(item) for item in raw_sections) if section]

    legacy_sections: list[dict[str, Any]] = []
    for spec in DEFAULT_SECTION_SPECS:
        section = _section_from_legacy(spec, payload.get(spec["legacy_field"]))
        if section:
            legacy_sections.append(section)

    if normalized_sections:
        sections = merge_sections(legacy_sections, normalized_sections)
    elif legacy_sections:
        sections = merge_sections(default_worldbuilding_sections(), legacy_sections)
    else:
        sections = default_worldbuilding_sections()

    legacy = legacy_fields_from_sections(sections)

    return {
        "id": _text(payload.get("id")) or fallback_id or _new_id("world"),
        "novel_id": _text(payload.get("novel_id")) or novel_id or "",
        "overview": _text(payload.get("overview")),
        "sections": sections,
        "power_system": legacy["power_system"],
        "factions": legacy["factions"],
        "geography": legacy["geography"],
        "core_rules": legacy["core_rules"],
        "items": legacy["items"],
    }


def merge_worldbuilding_documents(base_doc: dict[str, Any], generated_doc: dict[str, Any]) -> dict[str, Any]:
    base = normalize_worldbuilding_document(base_doc, fallback_id=base_doc.get("id"), novel_id=base_doc.get("novel_id"))
    generated = normalize_worldbuilding_document(generated_doc, fallback_id=base.get("id"), novel_id=base.get("novel_id"))
    merged_sections = merge_sections(base.get("sections") or [], generated.get("sections") or [])
    return normalize_worldbuilding_document(
        {
            **base,
            **generated,
            "overview": generated.get("overview") or base.get("overview") or "",
            "sections": merged_sections,
        },
        fallback_id=generated.get("id") or base.get("id"),
        novel_id=generated.get("novel_id") or base.get("novel_id"),
    )


def apply_worldbuilding_document(worldbuilding, document: dict[str, Any]):
    normalized = normalize_worldbuilding_document(
        document,
        fallback_id=getattr(worldbuilding, "id", None),
        novel_id=getattr(worldbuilding, "novel_id", None),
    )
    worldbuilding.overview = normalized["overview"]
    worldbuilding.sections = normalized["sections"]
    worldbuilding.power_system = normalized["power_system"]
    worldbuilding.factions = normalized["factions"]
    worldbuilding.geography = normalized["geography"]
    worldbuilding.core_rules = normalized["core_rules"]
    worldbuilding.items = normalized["items"]
    return normalized


def _worldbuilding_file_candidates(novel_id: str) -> list[Path]:
    project_dir = get_project_dir(novel_id)
    return [
        project_dir / "world" / "worldbuilding.json",
        project_dir / "worldbuilding.json",
    ]


def load_worldbuilding_document(novel_id: str, worldbuilding=None) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    if worldbuilding is not None:
        payload = {
            "id": getattr(worldbuilding, "id", ""),
            "novel_id": getattr(worldbuilding, "novel_id", novel_id),
            "overview": getattr(worldbuilding, "overview", "") or "",
            "sections": getattr(worldbuilding, "sections", None) or [],
            "power_system": getattr(worldbuilding, "power_system", None) or [],
            "factions": getattr(worldbuilding, "factions", None) or [],
            "geography": getattr(worldbuilding, "geography", None) or [],
            "core_rules": getattr(worldbuilding, "core_rules", None) or [],
            "items": getattr(worldbuilding, "items", None) or [],
        }

    file_payload: dict[str, Any] = {}
    for path in _worldbuilding_file_candidates(novel_id):
        if not path.exists():
            continue
        try:
            file_payload = json.loads(path.read_text(encoding="utf-8"))
            break
        except Exception:
            continue

    if file_payload:
        payload = {**payload, **file_payload}

    return normalize_worldbuilding_document(payload, fallback_id=payload.get("id"), novel_id=novel_id)


def summarize_worldbuilding_document(document: dict[str, Any]) -> str:
    doc = normalize_worldbuilding_document(document, fallback_id=document.get("id"), novel_id=document.get("novel_id"))
    parts: list[str] = []
    overview = _text(doc.get("overview"))
    if overview:
        parts.append(f"世界总述：{overview}")

    for section in doc.get("sections") or []:
        names = [_text(item.get("name")) for item in section.get("entries") or []]
        names = [name for name in names if name][:5]
        if names:
            parts.append(f"{section.get('name') or '设定栏目'}：{', '.join(names)}")

    return "\n".join(parts) if parts else "暂无设定"
