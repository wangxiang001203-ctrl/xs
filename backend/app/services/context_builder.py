"""
AI上下文构建器 — 核心模块
负责为每次AI调用组装最优上下文，平衡信息完整性与token消耗
"""
from sqlalchemy.orm import Session
from app.models import Novel, Character, Chapter, Synopsis
from app.models.worldbuilding import Worldbuilding
from app.models.project import Outline
from app.models.volume import Volume
from app.services.worldbuilding_service import load_worldbuilding_document, summarize_worldbuilding_document


# 每次AI调用注入的最大token预算（为输出留空间）
CONTEXT_TOKEN_BUDGET = 6000


def build_outline_context(novel: Novel, idea: str) -> str:
    """生成大纲时的prompt上下文"""
    return f"""你是一位专业的玄幻/修仙小说策划编辑。请根据以下创意，生成一份完整的小说大纲。

【创意】
{idea}

【大纲要求】
1. 包含故事背景、世界观简介
2. 主角设定（姓名、出身、特殊能力/灵根）
3. 核心矛盾与主线剧情
4. 分卷/分阶段规划（至少3个阶段）
5. 每个阶段的主要事件（3-5个）
6. 预计总字数规模

请用Markdown格式输出，结构清晰。"""


def build_synopsis_context(db: Session, novel_id: str, chapter_number: int) -> str:
    """生成细纲时的prompt上下文"""
    novel = db.query(Novel).filter(Novel.id == novel_id).first()
    outline = db.query(Outline).filter(
        Outline.novel_id == novel_id, Outline.confirmed == True
    ).order_by(Outline.version.desc()).first()
    worldbuilding = db.query(Worldbuilding).filter(Worldbuilding.novel_id == novel_id).first()
    characters = db.query(Character).filter(Character.novel_id == novel_id).all()

    # 获取前3章的剧情缩略（连贯性保障）
    prev_chapters = db.query(Chapter).filter(
        Chapter.novel_id == novel_id,
        Chapter.chapter_number < chapter_number,
        Chapter.plot_summary.isnot(None),
    ).order_by(Chapter.chapter_number.desc()).limit(3).all()

    # 获取上一章细纲（衔接用）
    prev_synopsis = None
    if chapter_number > 1:
        prev_ch = db.query(Chapter).filter(
            Chapter.novel_id == novel_id,
            Chapter.chapter_number == chapter_number - 1,
        ).first()
        if prev_ch:
            prev_synopsis = db.query(Synopsis).filter(Synopsis.chapter_id == prev_ch.id).first()

    parts = [f"# 小说：{novel.title}\n"]

    if outline:
        # 大纲只取前1500字，避免token爆炸
        outline_excerpt = outline.content[:1500] if outline.content else ""
        parts.append(f"## 大纲摘要\n{outline_excerpt}\n")

    if worldbuilding:
        wb_summary = _summarize_worldbuilding(worldbuilding)
        parts.append(f"## 世界观设定\n{wb_summary}\n")

    if characters:
        char_summary = _summarize_characters(characters)
        parts.append(f"## 角色列表（必须从此列表选取出场人物）\n{char_summary}\n")

    if prev_chapters:
        prev_chapters.reverse()
        summaries = "\n".join(
            f"- 第{c.chapter_number}章《{c.title or ''}》：{c.plot_summary}" for c in prev_chapters
        )
        parts.append(f"## 近期剧情回顾\n{summaries}\n")

    if prev_synopsis:
        parts.append(
            f"## 上一章结尾钩子\n{prev_synopsis.ending_next_hook or '无'}\n"
            f"上一章悬念：{prev_synopsis.ending_cliffhanger or '无'}\n"
        )

    parts.append(f"""## 任务
请为第{chapter_number}章生成细纲，必须包含以下JSON结构：

```json
{{
  "title": "章节标题",
  "word_count_target": 3000,
  "opening": {{
    "scene": "开场场景描述",
    "mood": "基调/氛围",
    "hook": "开头钩子/吸引点",
        "characters": ["角色名"]
  }},
  "development": {{
    "events": ["事件1", "事件2"],
    "conflicts": ["冲突1"],
    "characters": ["角色名"]
  }},
  "ending": {{
    "resolution": "本章结局",
    "cliffhanger": "悬念",
    "next_chapter_hook": "引出下章的钩子"
  }},
  "plot_summary_update": "一句话概括本章主要事件（用于主线剧情记录）"
}}
```

注意：
1. 优先使用已有角色列表中的人物名
2. 如果确实需要新增临时人物，可以直接写人物名，系统会在后续流程中补录角色卡""")

    return "\n".join(parts)


def build_chapter_context(db: Session, novel_id: str, chapter_id: str) -> str:
    """生成正文时的prompt上下文"""
    novel = db.query(Novel).filter(Novel.id == novel_id).first()
    chapter = db.query(Chapter).filter(Chapter.id == chapter_id).first()
    synopsis = db.query(Synopsis).filter(Synopsis.chapter_id == chapter_id).first()
    worldbuilding = db.query(Worldbuilding).filter(Worldbuilding.novel_id == novel_id).first()

    # 只取本章出场角色的详细信息
    all_char_names = []
    if synopsis and synopsis.all_characters:
        all_char_names = synopsis.all_characters

    characters = []
    if all_char_names:
        characters = db.query(Character).filter(
            Character.novel_id == novel_id,
            Character.name.in_(all_char_names),
        ).all()

    # 上一章结尾（最后500字，保持文风衔接）
    prev_chapter = None
    if chapter and chapter.chapter_number > 1:
        prev_chapter = db.query(Chapter).filter(
            Chapter.novel_id == novel_id,
            Chapter.chapter_number == chapter.chapter_number - 1,
        ).first()

    parts = [f"# 小说：{novel.title}\n"]

    if worldbuilding:
        wb_summary = _summarize_worldbuilding(worldbuilding)
        parts.append(f"## 世界观设定\n{wb_summary}\n")

    if characters:
        for c in characters:
            parts.append(_character_card(c))

    if prev_chapter and prev_chapter.content:
        tail = prev_chapter.content[-500:]
        parts.append(f"## 上一章结尾（保持文风衔接）\n...{tail}\n")

    if synopsis:
        parts.append(f"""## 本章细纲
**标题**：{chapter.title or f'第{chapter.chapter_number}章'}
**目标字数**：{synopsis.word_count_target}字

**开头**
- 场景：{synopsis.opening_scene or ''}
- 基调：{synopsis.opening_mood or ''}
- 钩子：{synopsis.opening_hook or ''}

**发展**
- 事件：{', '.join(synopsis.development_events or [])}
- 冲突：{', '.join(synopsis.development_conflicts or [])}

**结尾**
- 解决：{synopsis.ending_resolution or ''}
- 悬念：{synopsis.ending_cliffhanger or ''}
- 下章钩子：{synopsis.ending_next_hook or ''}
""")

    parts.append(f"""## 写作要求
1. 严格按照细纲展开，不得擅自增减主要情节
2. 人物性格、境界、道具必须与角色卡一致
3. 世界观规则（灵石、境界等）必须与设定一致
4. 目标字数约{synopsis.word_count_target if synopsis else 3000}字
5. 文风：东方玄幻，文笔流畅，有代入感
6. 直接输出正文，不要输出任何说明或标注""")

    return "\n".join(parts)


def _summarize_worldbuilding(wb: Worldbuilding) -> str:
    if not wb:
        return "暂无设定"
    novel_id = getattr(wb, "novel_id", "")
    document = load_worldbuilding_document(novel_id, wb) if novel_id else {}
    return summarize_worldbuilding_document(document)


def _summarize_characters(characters: list) -> str:
    lines = []
    for c in characters:
        line = f"- **{c.name}**（{c.gender or ''}，{c.realm or '未知境界'}，{c.faction or '无门派'}）"
        if c.personality:
            line += f"：{c.personality[:30]}"
        lines.append(line)
    return "\n".join(lines)


def _character_card(c: Character) -> str:
    techniques = "、".join(c.techniques or []) or "无"
    artifacts = "、".join(
        a.get("name", "") if isinstance(a, dict) else a for a in (c.artifacts or [])
    ) or "无"
    return f"""### 角色卡：{c.name}
- 性别：{c.gender or '未知'} | 种族：{c.race or '人族'} | 境界：{c.realm or '未知'}
- 阵营：{c.faction or '无'} | 状态：{c.status}
- 功法：{techniques}
- 道具：{artifacts}
- 性格：{c.personality or '未设定'}
- 背景：{(c.background or '')[:100]}
"""


def build_volume_synopsis_context(
    db: Session,
    novel_id: str,
    volume_id: str,
    chapter_numbers: list[int] | None = None,
) -> str:
    """生成整卷所有章节细纲的prompt（一次性批量生成）"""
    novel = db.query(Novel).filter(Novel.id == novel_id).first()
    volume = db.query(Volume).filter(Volume.id == volume_id).first()
    outline = db.query(Outline).filter(
        Outline.novel_id == novel_id, Outline.confirmed == True
    ).order_by(Outline.version.desc()).first()
    worldbuilding = db.query(Worldbuilding).filter(Worldbuilding.novel_id == novel_id).first()
    characters = db.query(Character).filter(Character.novel_id == novel_id).all()

    # 本卷所有章节（按章号排序）
    chapter_query = db.query(Chapter).filter(Chapter.volume_id == volume_id)
    if chapter_numbers:
        chapter_query = chapter_query.filter(Chapter.chapter_number.in_(chapter_numbers))
    chapters = chapter_query.order_by(Chapter.chapter_number).all()

    # 上一卷最后3章的剧情缩略（连贯性）
    first_ch_num = chapters[0].chapter_number if chapters else 1
    prev_chapters = db.query(Chapter).filter(
        Chapter.novel_id == novel_id,
        Chapter.chapter_number < first_ch_num,
        Chapter.plot_summary.isnot(None),
    ).order_by(Chapter.chapter_number.desc()).limit(3).all()

    parts = [f"# 小说：{novel.title}\n## 当前卷：{volume.title}\n"]

    if volume.description:
        parts.append(f"**本卷简介**：{volume.description}\n")

    if outline:
        outline_excerpt = outline.content[:2000] if outline.content else ""
        parts.append(f"## 大纲摘要\n{outline_excerpt}\n")

    if worldbuilding:
        wb_summary = _summarize_worldbuilding(worldbuilding)
        parts.append(f"## 世界观设定\n{wb_summary}\n")

    if characters:
        char_summary = _summarize_characters(characters)
        parts.append(f"## 角色列表（优先使用已有角色）\n{char_summary}\n")

    if prev_chapters:
        prev_chapters.reverse()
        summaries = "\n".join(
            f"- 第{c.chapter_number}章《{c.title or ''}》：{c.plot_summary}" for c in prev_chapters
        )
        parts.append(f"## 前情回顾\n{summaries}\n")

    chapter_list = "\n".join(
        f"- 第{c.chapter_number}章：{c.title or f'第{c.chapter_number}章'}" for c in chapters
    )
    parts.append(f"## 本次待生成章节列表\n{chapter_list}\n")

    parts.append(f"""## 任务
请为本次列出的章节批量生成细纲，输出一个JSON数组，每个元素对应一章：

```json
[
  {{
    "chapter_number": 1,
    "title": "章节标题",
    "word_count_target": 3000,
    "opening": {{
      "scene": "开场场景",
      "mood": "基调氛围",
      "hook": "开头钩子",
      "characters": ["角色名"]
    }},
    "development": {{
      "events": ["事件1", "事件2"],
      "conflicts": ["冲突1"],
      "characters": ["角色名"]
    }},
    "ending": {{
      "resolution": "本章结局",
      "cliffhanger": "悬念",
      "next_chapter_hook": "引出下章的钩子"
    }},
    "plot_summary_update": "一句话概括本章主要事件"
  }}
]
```

要求：
1. 数组长度必须等于本次章节数（{len(chapters)}章）
2. chapter_number 与章节列表一一对应
3. 章节间剧情要连贯，前一章的 next_chapter_hook 要与下一章的 opening 呼应
4. 优先使用角色列表中的人物；如果剧情确实需要新增临时人物，可以直接写人物名，系统会后补角色占位
5. 只输出JSON，不要输出任何说明文字""")

    return "\n".join(parts)


def build_characters_from_synopsis_context(db: Session, novel_id: str) -> str:
    """根据大纲和细纲生成角色卡列表的prompt"""
    novel = db.query(Novel).filter(Novel.id == novel_id).first()
    outline = db.query(Outline).filter(
        Outline.novel_id == novel_id, Outline.confirmed == True
    ).order_by(Outline.version.desc()).first()
    worldbuilding = db.query(Worldbuilding).filter(Worldbuilding.novel_id == novel_id).first()

    # 收集所有细纲中出现的人物名
    synopses = db.query(Synopsis).filter(Synopsis.novel_id == novel_id).all()
    all_char_names: set[str] = set()
    for s in synopses:
        for name in (s.all_characters or []):
            all_char_names.add(name)
        for name in (s.opening_characters or []):
            all_char_names.add(name)
        for name in (s.development_characters or []):
            all_char_names.add(name)

    parts = [f"# 小说：{novel.title}\n"]

    if outline:
        outline_excerpt = outline.content[:2000] if outline.content else ""
        parts.append(f"## 大纲\n{outline_excerpt}\n")

    if worldbuilding:
        wb_summary = _summarize_worldbuilding(worldbuilding)
        parts.append(f"## 世界观设定\n{wb_summary}\n")

    if all_char_names:
        parts.append(f"## 细纲中出现的人物\n{', '.join(sorted(all_char_names))}\n")

    parts.append(f"""## 任务
请根据大纲和世界观，为上述人物生成详细角色卡，输出JSON数组：

```json
[
  {{
    "name": "角色名",
    "gender": "男/女",
    "age": 18,
    "race": "人族",
    "realm": "练气期",
    "realm_level": 1,
    "faction": "所属门派/势力",
    "techniques": ["功法1", "功法2"],
    "artifacts": [{{"name": "法宝名", "grade": "品级", "desc": "描述"}}],
    "appearance": "外貌描述",
    "personality": "性格描述",
    "background": "背景故事",
    "relationships": [{{"name": "关联角色", "relation": "关系描述"}}],
    "status": "alive"
  }}
]
```

要求：
1. 境界必须符合世界观中的境界体系
2. 主角要有详细背景，配角可以简略
3. 只输出JSON，不要输出任何说明文字""")

    return "\n".join(parts)


def build_worldbuilding_from_outline_context(db: Session, novel_id: str) -> str:
    """根据大纲和角色完善世界观的prompt"""
    novel = db.query(Novel).filter(Novel.id == novel_id).first()
    outline = db.query(Outline).filter(
        Outline.novel_id == novel_id, Outline.confirmed == True
    ).order_by(Outline.version.desc()).first()
    characters = db.query(Character).filter(Character.novel_id == novel_id).all()
    existing_wb = db.query(Worldbuilding).filter(Worldbuilding.novel_id == novel_id).first()

    parts = [f"# 小说：{novel.title}\n"]

    if outline:
        outline_excerpt = outline.content[:2000] if outline.content else ""
        parts.append(f"## 大纲\n{outline_excerpt}\n")

    if characters:
        char_summary = _summarize_characters(characters)
        parts.append(f"## 已有角色\n{char_summary}\n")

    if existing_wb:
        parts.append(f"## 现有世界观设定（请在此基础上完善）\n{_summarize_worldbuilding(existing_wb)}\n")

    parts.append("""## 任务
请根据大纲和角色信息，生成完整的世界观设定，输出JSON：

```json
{
  "realm_system": {
    "levels": [
      {"name": "练气期", "description": "修炼初阶，感知灵气", "sub_levels": 9}
    ],
    "description": "境界体系总体说明"
  },
  "currency": {
    "units": ["下品灵石", "中品灵石", "上品灵石", "极品灵石"],
    "exchange_rate": [100, 100, 100],
    "note": "货币说明"
  },
  "factions": [
    {"name": "门派名", "type": "宗门/散修/魔道", "location": "所在地", "desc": "简介"}
  ],
  "artifacts": [
    {"name": "法宝名", "grade": "品级", "type": "类型", "desc": "描述"}
  ],
  "techniques": [
    {"name": "功法名", "grade": "品级", "type": "类型", "desc": "描述"}
  ],
  "geography": [
    {"name": "地名", "type": "大陆/秘境/城市", "desc": "描述"}
  ],
  "custom_rules": [
    {"name": "规则名", "desc": "规则描述"}
  ]
}
```

要求：
1. 境界体系要与大纲中提到的境界一致
2. 至少包含3个主要势力
3. 只输出JSON，不要输出任何说明文字""")

    return "\n".join(parts)


def build_chapter_segment_context(db: Session, novel_id: str, chapter_id: str, segment: str, prev_segment_text: str = "") -> str:
    """分段生成正文的prompt（segment: opening/middle/ending）"""
    novel = db.query(Novel).filter(Novel.id == novel_id).first()
    chapter = db.query(Chapter).filter(Chapter.id == chapter_id).first()
    synopsis = db.query(Synopsis).filter(Synopsis.chapter_id == chapter_id).first()
    worldbuilding = db.query(Worldbuilding).filter(Worldbuilding.novel_id == novel_id).first()

    all_char_names = synopsis.all_characters if synopsis else []
    characters = []
    if all_char_names:
        characters = db.query(Character).filter(
            Character.novel_id == novel_id,
            Character.name.in_(all_char_names),
        ).all()

    prev_chapter = None
    if chapter and chapter.chapter_number > 1:
        prev_chapter = db.query(Chapter).filter(
            Chapter.novel_id == novel_id,
            Chapter.chapter_number == chapter.chapter_number - 1,
        ).first()

    segment_map = {
        "opening": ("开头段", "开场场景、基调和钩子，约1000字"),
        "middle": ("中间段", "主要事件和冲突展开，约1500字"),
        "ending": ("结尾段", "本章结局、悬念和下章钩子，约500字"),
    }
    seg_name, seg_desc = segment_map.get(segment, ("正文", "完整正文"))

    parts = [f"# 小说：{novel.title} — 第{chapter.chapter_number if chapter else '?'}章{seg_name}\n"]

    if worldbuilding:
        parts.append(f"## 世界观\n{_summarize_worldbuilding(worldbuilding)}\n")

    if characters:
        for c in characters:
            parts.append(_character_card(c))

    if segment == "opening" and prev_chapter and prev_chapter.content:
        tail = prev_chapter.content[-500:]
        parts.append(f"## 上一章结尾（保持文风衔接）\n...{tail}\n")

    if segment in ("middle", "ending") and prev_segment_text:
        tail = prev_segment_text[-300:]
        parts.append(f"## 上一段结尾（直接续写）\n...{tail}\n")

    if synopsis:
        seg_detail = ""
        if segment == "opening":
            seg_detail = f"场景：{synopsis.opening_scene}\n基调：{synopsis.opening_mood}\n钩子：{synopsis.opening_hook}"
        elif segment == "middle":
            seg_detail = f"事件：{', '.join(synopsis.development_events or [])}\n冲突：{', '.join(synopsis.development_conflicts or [])}"
        elif segment == "ending":
            seg_detail = f"结局：{synopsis.ending_resolution}\n悬念：{synopsis.ending_cliffhanger}\n下章钩子：{synopsis.ending_next_hook}"

        parts.append(f"## 本段细纲\n{seg_detail}\n")

    target = {"opening": 1000, "middle": 1500, "ending": 500}.get(segment, 1000)
    parts.append(f"""## 写作要求
1. 本段任务：{seg_desc}
2. 目标字数：约{target}字
3. 人物性格、境界、道具必须与角色卡一致
4. 世界观规则必须与设定一致
5. 文风：东方玄幻，文笔流畅，有代入感
6. 直接输出正文，不要输出任何说明或标注""")

    return "\n".join(parts)


def build_chat_context(db: Session, novel_id: str, context_type: str, context_id: str | None) -> str:
    """构建AI对话的系统上下文（上下文感知）"""
    novel = db.query(Novel).filter(Novel.id == novel_id).first()
    parts = [f"你是小说《{novel.title}》的AI创作助手。"]

    if context_type == "outline":
        outline = db.query(Outline).filter(
            Outline.novel_id == novel_id, Outline.confirmed == True
        ).order_by(Outline.version.desc()).first()
        if outline:
            parts.append(f"\n当前用户正在编辑【大纲】，内容如下：\n{outline.content[:1500]}")

    elif context_type == "characters":
        characters = db.query(Character).filter(Character.novel_id == novel_id).all()
        if characters:
            parts.append(f"\n当前用户正在编辑【角色库】，现有角色：\n{_summarize_characters(characters)}")

    elif context_type == "worldbuilding":
        wb = db.query(Worldbuilding).filter(Worldbuilding.novel_id == novel_id).first()
        if wb:
            parts.append(f"\n当前用户正在编辑【世界观设定】：\n{_summarize_worldbuilding(wb)}")

    elif context_type == "chapter" and context_id:
        chapter = db.query(Chapter).filter(Chapter.id == context_id).first()
        synopsis = db.query(Synopsis).filter(Synopsis.chapter_id == context_id).first() if chapter else None
        if chapter:
            parts.append(f"\n当前用户正在编辑【第{chapter.chapter_number}章《{chapter.title or ''}》】")
        if synopsis:
            parts.append(f"本章细纲：开场={synopsis.opening_scene}，冲突={', '.join(synopsis.development_conflicts or [])}")
        if chapter and chapter.content:
            parts.append(f"已写正文（最后300字）：...{chapter.content[-300:]}")

    parts.append("\n\n请根据用户的问题或建议，给出专业的创作意见。如果用户要求修改某段内容，请直接输出修改后的版本，用<PATCH>修改后的内容</PATCH>包裹。")
    return "".join(parts)
