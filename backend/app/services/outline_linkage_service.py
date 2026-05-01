"""
大纲 ↔ 设定联动机制：变更影响分析器。

当大纲被修改时：
1. 识别哪些字段发生了变化（简介、卖点、主线、核心冲突等）
2. 自动检测哪些分卷/章节细纲引用了这些内容
3. 给出变更影响评估
4. 用户确认后自动执行联动修改
"""
import re

from sqlalchemy.orm import Session

from app.models import Chapter, Outline, StoryEntity, Synopsis, Volume


STOP_WORDS = {
    "大纲", "主角", "角色", "一个", "这里", "这个", "需要", "通过", "进行", "开始", "之后", "以及", "但是", "因为", "所以",
    "第一", "第二", "第三", "本卷", "章节", "故事", "小说", "世界", "设定",
}


class ImpactReport:
    """大纲变更影响范围报告。"""

    def __init__(
        self,
        changed_fields: list[str],
        affected_volumes: list[dict],
        affected_chapters: list[dict],
        setting_conflicts: list[dict],
        needs_regeneration: list[dict],
    ):
        self.changed_fields = changed_fields
        self.affected_volumes = affected_volumes
        self.affected_chapters = affected_chapters
        self.setting_conflicts = setting_conflicts
        self.needs_regeneration = needs_regeneration

    def as_text(self) -> str:
        parts = [f"大纲变更涉及字段：{'、'.join(self.changed_fields)}"]
        if self.affected_volumes:
            vol_names = [f"第{v['volume_number']}卷《{v['title']}》" for v in self.affected_volumes]
            parts.append(f"可能影响分卷：{'、'.join(vol_names)}")
        if self.affected_chapters:
            chapter_nums = [c["chapter_number"] for c in self.affected_chapters]
            parts.append(f"可能影响章节：第{min(chapter_nums)}-{max(chapter_nums)}章（{len(chapter_nums)}章）")
        if self.setting_conflicts:
            parts.append(f"发现设定冲突：{len(self.setting_conflicts)}处")
            for conflict in self.setting_conflicts[:3]:
                parts.append(f"  - {conflict['description']}")
        if self.needs_regeneration:
            parts.append(f"建议重新生成：{', '.join(r['reason'] for r in self.needs_regeneration)}")
        return "\n".join(parts)

    def as_proposal_items(self) -> list[dict]:
        """转换为待确认提案列表。"""
        items = []
        for vol in self.affected_volumes:
            items.append({
                "type": "volume",
                "action": "check_and_revise",
                "target_id": vol["id"],
                "target_name": vol["title"],
                "reason": f"大纲变更可能影响第{vol['volume_number']}卷分卷规划",
            })
        for chapter in self.affected_chapters:
            items.append({
                "type": "chapter_synopsis",
                "action": "check_conflict",
                "target_id": chapter["id"],
                "target_name": f"第{chapter['chapter_number']}章细纲",
                "reason": f"大纲变更可能影响本章细纲",
            })
        for conflict in self.setting_conflicts:
            items.append({
                "type": "conflict",
                "action": "resolve",
                "description": conflict["description"],
                "details": conflict,
            })
        return items


def detect_outline_changes(old_outline: Outline | None, new_outline: Outline) -> list[str]:
    """识别哪些大纲字段发生了变化。"""
    changed = []
    outline_fields = ["title", "synopsis", "selling_points", "main_plot", "content"]
    if old_outline is None:
        return ["new"]  # 新建大纲

    for field in outline_fields:
        old_val = getattr(old_outline, field, None) or ""
        new_val = getattr(new_outline, field, None) or ""
        if old_val.strip() != new_val.strip():
            changed.append(field)
    return changed


def _keywords(text: str, limit: int = 40) -> list[str]:
    terms: list[str] = []
    for token in re.findall(r"[\u4e00-\u9fa5A-Za-z0-9]{2,12}", text or ""):
        if token in STOP_WORDS:
            continue
        if re.fullmatch(r"\d+", token):
            continue
        if token not in terms:
            terms.append(token)
    return terms[:limit]


def _changed_keywords(new_outline: Outline, changed_fields: list[str]) -> list[str]:
    chunks: list[str] = []
    for field in changed_fields:
        value = getattr(new_outline, field, None)
        if value:
            chunks.append(str(value))
    return _keywords("\n".join(chunks), 60)


def find_affected_volumes(db: Session, novel_id: str, changed_fields: list[str]) -> list[dict]:
    """查找哪些分卷引用了被修改的大纲内容。"""
    affected = []
    volumes = db.query(Volume).filter(Volume.novel_id == novel_id).order_by(Volume.volume_number).all()

    outline = db.query(Outline).filter(Outline.novel_id == novel_id).order_by(Outline.version.desc()).first()
    if not outline:
        return affected

    keywords = _changed_keywords(outline, changed_fields)
    if not keywords:
        return affected

    for vol in volumes:
        vol_text = "\n".join([
            vol.title or "",
            vol.description or "",
            vol.main_line or "",
            vol.plan_markdown or "",
        ])
        if vol_text:
            matched = [word for word in keywords if word in vol_text]
            if matched:
                affected.append({
                    "id": vol.id,
                    "title": vol.title,
                    "volume_number": vol.volume_number,
                    "matched_keywords": matched[:8],
                    "status": vol.review_status,
                })

    return affected


def find_affected_chapters(db: Session, novel_id: str, changed_fields: list[str]) -> list[dict]:
    """查找哪些章节细纲引用了被修改的大纲内容。"""
    affected = []
    outline = db.query(Outline).filter(Outline.novel_id == novel_id).order_by(Outline.version.desc()).first()
    if not outline:
        return affected

    outline_keywords = set(_changed_keywords(outline, changed_fields))

    chapters = db.query(Chapter).filter(Chapter.novel_id == novel_id).order_by(Chapter.chapter_number).all()
    for chapter in chapters:
        if chapter.final_approved:
            continue  # 已定稿章节跳过检查
        synopsis = db.query(Synopsis).filter(Synopsis.chapter_id == chapter.id).first()
        if not synopsis:
            continue

        synopsis_text = "\n".join([
            synopsis.summary_line or "",
            synopsis.content_md or "",
            "、".join(synopsis.development_events or []),
        ])

        matched = [kw for kw in outline_keywords if kw in synopsis_text]
        if matched:
            affected.append({
                "id": chapter.id,
                "chapter_number": chapter.chapter_number,
                "synopsis_status": synopsis.review_status,
                "matched_keywords": matched[:5],
            })

    return affected


def detect_setting_conflicts(db: Session, novel_id: str, changed_fields: list[str]) -> list[dict]:
    """
    检测设定与大纲之间的矛盾。
    例如：大纲说主角在 A 城，但关系网显示主角已迁移到 B 城。
    """
    conflicts = []

    if any(field in changed_fields for field in ("main_plot", "content", "synopsis")):
        outline = db.query(Outline).filter(Outline.novel_id == novel_id).order_by(Outline.version.desc()).first()
        outline_text = "\n".join([outline.synopsis or "", outline.main_plot or "", outline.content or ""]) if outline else ""
        active_locations = db.query(StoryEntity).filter(
            StoryEntity.novel_id == novel_id,
            StoryEntity.entity_type == "location",
            StoryEntity.status == "active",
        ).limit(80).all()
        mentioned = [loc.name for loc in active_locations if loc.name and loc.name in outline_text]
        protagonist = db.query(StoryEntity).filter(
            StoryEntity.novel_id == novel_id,
            StoryEntity.entity_type == "character",
            StoryEntity.graph_role == "protagonist",
        ).first()
        current_location = (protagonist.current_state or {}).get("location") if protagonist else None
        if current_location and mentioned and current_location not in mentioned:
            conflicts.append({
                "type": "location_mismatch",
                "description": f"大纲提到地点 {'、'.join(mentioned[:5])}，但主角当前状态记录在「{current_location}」，需要确认是否迁移或补录事件。",
                "current_location": current_location,
                "mentioned_locations": mentioned[:10],
            })

    return conflicts


def analyze_outline_change_impact(db: Session, novel_id: str, old_outline: Outline | None, new_outline: Outline) -> ImpactReport:
    """
    分析大纲变更对全书的影响范围。
    这是大纲 ↔ 设定联动机制的核心函数。
    """
    changed_fields = detect_outline_changes(old_outline, new_outline)

    if not changed_fields or changed_fields == ["new"]:
        return ImpactReport(
            changed_fields=changed_fields,
            affected_volumes=[],
            affected_chapters=[],
            setting_conflicts=[],
            needs_regeneration=[],
        )

    affected_volumes = find_affected_volumes(db, novel_id, changed_fields)
    affected_chapters = find_affected_chapters(db, novel_id, changed_fields)
    setting_conflicts = detect_setting_conflicts(db, novel_id, changed_fields)

    # 判断哪些需要重新生成
    needs_regeneration = []
    for vol in affected_volumes:
        if vol["status"] != "approved":
            needs_regeneration.append({
                "reason": f"第{vol['volume_number']}卷分卷规划（状态：{vol['status']}）建议检查后重新生成",
                "target": f"volume:{vol['id']}",
            })

    return ImpactReport(
        changed_fields=changed_fields,
        affected_volumes=affected_volumes,
        affected_chapters=affected_chapters,
        setting_conflicts=setting_conflicts,
        needs_regeneration=needs_regeneration,
    )
