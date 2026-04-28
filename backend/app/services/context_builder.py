"""
AI上下文构建器 — 核心模块
负责为每次AI调用组装最优上下文，平衡信息完整性与token消耗
"""
from sqlalchemy.orm import Session
from app.models import Novel, Character, Chapter, Synopsis, ChapterMemory
from app.models.worldbuilding import Worldbuilding
from app.models.project import Outline
from app.models.volume import Volume
from app.services.worldbuilding_service import load_worldbuilding_document, summarize_worldbuilding_document


# 每次AI调用注入的最大token预算（为输出留空间）
CONTEXT_TOKEN_BUDGET = 6000


def build_outline_context(novel: Novel, idea: str) -> str:
    """生成大纲时的prompt上下文（不参考书名，因为可能是临时占位）"""
    return f"""你是一位资深的玄幻/修仙小说策划编辑，擅长构建完整的故事框架和节奏控制。请根据以下创意，生成一份详细、可执行的小说大纲。

【创意】
{idea}

【大纲生成规则】

## 一、故事背景与世界观
1. 世界设定：修炼体系、境界划分、力量来源
2. 时代背景：当前时代特征、主要势力分布
3. 核心设定：独特的世界观元素（如特殊灵根、功法体系等）

## 二、主角设定
1. 基础信息：姓名、年龄、出身背景
2. 初始状态：起点实力、特殊能力/机遇
3. 性格特点：3-5个核心性格标签
4. 成长目标：短期目标和终极目标

## 三、核心矛盾与主线
1. 外部矛盾：主角面临的主要敌对势力/人物
2. 内部矛盾：主角的心理成长线
3. 主线剧情：用一句话概括整个故事的核心冲突

## 四、分卷规划（至少3卷，建议5-8卷）
每卷必须包含：
- 卷名：简洁有力，体现本卷主题
- 阶段目标：主角在本卷要达成什么
- 境界跨度：从XX境到XX境
- 核心事件：3-5个关键剧情节点
- 主要角色：本卷新增的重要角色
- 卷末钩子：为下一卷埋下的悬念
- 预计章节数：建议每卷10-15章
- 预计字数：建议每卷3-5万字

## 五、节奏控制要求
1. 前期节奏要快，避免冗长铺垫
2. 每卷必须有明确的高潮和收束
3. 每3-5章要有一个小高潮
4. 避免重复套路，每卷要有新意

## 六、角色规划
1. 主角团队：2-3个核心伙伴
2. 主要反派：每卷至少1个有深度的反派
3. 关键配角：推动剧情的重要NPC

## 七、输出格式
请严格按照以下Markdown格式输出：

```markdown
# 小说大纲

## 一、世界观设定
[详细描述]

## 二、主角设定
**姓名**：
**年龄**：
**出身**：
**特殊能力**：
**性格**：
**成长目标**：

## 三、核心矛盾
[描述主要矛盾]

## 四、分卷规划

### 第一卷：[卷名]
- **阶段目标**：
- **境界跨度**：
- **核心事件**：
  1.
  2.
  3.
- **主要角色**：
- **卷末钩子**：
- **预计章节数**：12章
- **预计字数**：3.6万字

[后续各卷同样格式]

## 五、总体规划
- **预计总卷数**：X卷
- **预计总章节数**：XX章
- **预计总字数**：XX万字
```

【重要提醒】
1. 大纲要具体可执行，避免空泛描述
2. 每卷的核心事件要有因果关系，形成完整链条
3. 主角成长要有阶梯感，不能一步登天
4. 反派要有合理动机，不能脸谱化
5. 世界观设定要自洽，避免前后矛盾

请开始生成大纲。"""


def build_volume_synopsis_context(db: Session, novel_id: str, volume_id: str) -> str:
    """生成整卷细纲时的prompt上下文（一次性生成所有章节细纲）"""
    novel = db.query(Novel).filter(Novel.id == novel_id).first()
    volume = db.query(Volume).filter(Volume.id == volume_id).first()
    outline = db.query(Outline).filter(
        Outline.novel_id == novel_id, Outline.confirmed == True
    ).order_by(Outline.version.desc()).first()
    worldbuilding = db.query(Worldbuilding).filter(Worldbuilding.novel_id == novel_id).first()
    characters = db.query(Character).filter(Character.novel_id == novel_id).all()

    # 获取本卷所有章节
    chapters = db.query(Chapter).filter(
        Chapter.volume_id == volume_id
    ).order_by(Chapter.chapter_number).all()

    # 获取前一卷的最后一章记忆（用于衔接）
    prev_volume_last_memory = None
    if volume.volume_number > 1:
        prev_volume = db.query(Volume).filter(
            Volume.novel_id == novel_id,
            Volume.volume_number == volume.volume_number - 1
        ).first()
        if prev_volume:
            prev_volume_last_chapter = db.query(Chapter).filter(
                Chapter.volume_id == prev_volume.id
            ).order_by(Chapter.chapter_number.desc()).first()
            if prev_volume_last_chapter:
                prev_volume_last_memory = db.query(ChapterMemory).filter(
                    ChapterMemory.chapter_id == prev_volume_last_chapter.id
                ).first()

    parts = [f"# 小说：{novel.title}\n"]

    if outline:
        outline_excerpt = outline.content[:2000] if outline.content else ""
        parts.append(f"## 大纲摘要\n{outline_excerpt}\n")

    if worldbuilding:
        wb_summary = _summarize_worldbuilding(worldbuilding)
        parts.append(f"## 世界观设定\n{wb_summary}\n")

    if characters:
        char_summary = _summarize_characters(characters)
        parts.append(f"## 角色列表（必须从此列表选取出场人物）\n{char_summary}\n")

    if prev_volume_last_memory:
        parts.append(f"""## 前一卷结尾状态
**第{prev_volume_last_memory.chapter_number}章摘要**：{prev_volume_last_memory.summary or '无'}
**关键事件**：{', '.join(prev_volume_last_memory.key_events or [])}
**状态变化**：{', '.join(prev_volume_last_memory.state_changes or [])}
**未完事项**：{', '.join(prev_volume_last_memory.open_threads or [])}
""")

    parts.append(f"""## 本卷信息
**卷名**：第{volume.volume_number}卷 {volume.title}
**卷简介**：{volume.description or '无'}
**主线**：{volume.main_line or '无'}
**人物成长弧线**：{volume.character_arc or '无'}
**卷末钩子**：{volume.ending_hook or '无'}
**计划章节数**：{len(chapters)}章（第{chapters[0].chapter_number}章 - 第{chapters[-1].chapter_number}章）
""")

    parts.append(f"""## 任务
请为本卷的所有章节（共{len(chapters)}章）生成完整细纲。你需要一次性规划好整卷的节奏，确保：
1. 每章之间有明确的因果关系和递进
2. 整卷有起承转合的完整结构
3. 每3-5章有一个小高潮
4. 卷末有明确的高潮和收束

必须输出以下JSON结构：

```json
{{
  "chapters": [
    {{
      "chapter_number": {chapters[0].chapter_number},
      "title": "章节标题",
      "summary_line": "本章一句话概括",
      "word_count_target": 3000,
      "content_md": "## 本章目标\\n...\\n\\n## 情节推进\\n1. ...\\n\\n## 角色与状态\\n- ...\\n\\n## 本章约束\\n- ...\\n\\n## 章末钩子\\n...",
      "hard_constraints": ["硬约束1", "硬约束2"],
      "referenced_entities": {{
        "characters": ["角色名"],
        "items": ["道具名"],
        "factions": ["势力名"],
        "locations": ["地点名"],
        "rules": ["规则名"],
        "realms": ["境界名"]
      }},
      "proposal_candidates": [
        {{
          "entity_type": "item",
          "name": "新道具名",
          "reason": "为什么首次出现它是合理的",
          "target_section": "items",
          "entry": {{
            "name": "新道具名",
            "summary": "一句话定义",
            "details": "详细说明"
          }}
        }}
      ],
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
      "plot_summary_update": "一句话概括本章主要事件"
    }}
    // ... 后续章节同样格式
  ]
}}
```

注意：
1. 必须为本卷所有{len(chapters)}章都生成细纲
2. 章节编号从{chapters[0].chapter_number}到{chapters[-1].chapter_number}
3. 优先使用已有角色列表、世界观设定中的实体
4. 如果确实首次出现新人物/新道具/新规则，必须放入 proposal_candidates 等待作者审批
5. referenced_entities 必须只填写本章真正用到的实体
6. 整卷节奏要合理，避免重复套路""")

    return "\n".join(parts)


def build_synopsis_context(db: Session, novel_id: str, chapter_number: int) -> str:
    """生成细纲时的prompt上下文"""
    novel = db.query(Novel).filter(Novel.id == novel_id).first()
    outline = db.query(Outline).filter(
        Outline.novel_id == novel_id, Outline.confirmed == True
    ).order_by(Outline.version.desc()).first()
    worldbuilding = db.query(Worldbuilding).filter(Worldbuilding.novel_id == novel_id).first()
    characters = db.query(Character).filter(Character.novel_id == novel_id).all()

    # 获取前5章的动态记忆（连贯性保障）
    prev_memories = db.query(ChapterMemory).filter(
        ChapterMemory.novel_id == novel_id,
        ChapterMemory.chapter_number < chapter_number,
    ).order_by(ChapterMemory.chapter_number.desc()).limit(5).all()

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

    # 优先使用动态记忆
    if prev_memories:
        prev_memories.reverse()
        memory_lines = []
        for mem in prev_memories:
            memory_lines.append(f"### 第{mem.chapter_number}章")
            if mem.summary:
                memory_lines.append(f"**摘要**：{mem.summary}")
            if mem.key_events:
                memory_lines.append(f"**关键事件**：{', '.join(mem.key_events)}")
            if mem.state_changes:
                memory_lines.append(f"**状态变化**：{', '.join(mem.state_changes)}")
            if mem.inventory_changes:
                memory_lines.append(f"**物品变化**：{', '.join(mem.inventory_changes)}")
            if mem.open_threads:
                memory_lines.append(f"**未完事项**：{', '.join(mem.open_threads)}")
            memory_lines.append("")
        parts.append(f"## 前情动态记忆（真实发生的事实）\n" + "\n".join(memory_lines))
    elif prev_chapters:
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
请为第{chapter_number}章生成完整细纲，必须包含以下JSON结构：

```json
{{
  "title": "章节标题",
  "summary_line": "本章一句话概括",
  "word_count_target": 3000,
  "content_md": "# 第{chapter_number}章 章节标题\\n\\n## 本章目标\\n...\\n\\n## 情节推进\\n1. ...\\n\\n## 角色与状态\\n- ...\\n\\n## 本章约束\\n- ...\\n\\n## 章末钩子\\n...",
  "hard_constraints": ["硬约束1", "硬约束2"],
  "referenced_entities": {{
    "characters": ["角色名"],
    "items": ["道具名"],
    "factions": ["势力名"],
    "locations": ["地点名"],
    "rules": ["规则名"],
    "realms": ["境界名"]
  }},
  "proposal_candidates": [
    {{
      "entity_type": "item",
      "name": "新道具名",
      "reason": "为什么首次出现它是合理的",
      "target_section": "items",
      "entry": {{
        "name": "新道具名",
        "summary": "一句话定义",
        "details": "详细说明"
      }}
    }}
  ],
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
1. 细纲正文请写在 content_md 中，给作者直接阅读和修改
2. 优先使用已有角色列表、世界观设定中的实体
3. 如果确实首次出现新人物/新道具/新规则，不得当作已存在事实直接写死，必须放入 proposal_candidates 等待作者审批
4. referenced_entities 必须只填写本章真正用到的实体""")

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

    recent_memories = db.query(ChapterMemory).filter(
        ChapterMemory.novel_id == novel_id,
        ChapterMemory.chapter_number < (chapter.chapter_number if chapter else 1),
    ).order_by(ChapterMemory.chapter_number.desc()).limit(3).all()

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

    if recent_memories:
        recent_memories.reverse()
        memory_lines = []
        for item in recent_memories:
            summary = item.summary or "待补充"
            memory_lines.append(f"- 第{item.chapter_number}章：{summary}")
        parts.append(f"## 近期动态记忆\n" + "\n".join(memory_lines) + "\n")

    if synopsis:
        if synopsis.content_md:
            parts.append(f"## 本章细纲\n{synopsis.content_md}\n")
        else:
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

    # 上一卷最后5章的动态记忆（连贯性）
    first_ch_num = chapters[0].chapter_number if chapters else 1
    prev_memories = db.query(ChapterMemory).filter(
        ChapterMemory.novel_id == novel_id,
        ChapterMemory.chapter_number < first_ch_num,
    ).order_by(ChapterMemory.chapter_number.desc()).limit(5).all()

    # 上一卷最后3章的剧情缩略（连贯性）
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

    # 优先使用动态记忆
    if prev_memories:
        prev_memories.reverse()
        memory_lines = []
        for mem in prev_memories:
            memory_lines.append(f"### 第{mem.chapter_number}章")
            if mem.summary:
                memory_lines.append(f"**摘要**：{mem.summary}")
            if mem.key_events:
                memory_lines.append(f"**关键事件**：{', '.join(mem.key_events)}")
            if mem.state_changes:
                memory_lines.append(f"**状态变化**：{', '.join(mem.state_changes)}")
            if mem.inventory_changes:
                memory_lines.append(f"**物品变化**：{', '.join(mem.inventory_changes)}")
            if mem.open_threads:
                memory_lines.append(f"**未完事项**：{', '.join(mem.open_threads)}")
            memory_lines.append("")
        parts.append(f"## 前情动态记忆（真实发生的事实）\n" + "\n".join(memory_lines))
    elif prev_chapters:
        prev_chapters.reverse()
        summaries = "\n".join(
            f"- 第{c.chapter_number}章《{c.title or ''}》：{c.plot_summary}" for c in prev_chapters
        )
        parts.append(f"## 前情回顾\n{summaries}\n")

    chapter_list = "\n".join(
        f"- 第{c.chapter_number}章：{c.title or f'第{c.chapter_number}章'}" for c in chapters
    )
    parts.append(f"## 本次待生成章节列表\n{chapter_list}\n")

    parts.append(f"""## 任务说明
你需要为本卷的所有章节一次性生成完整细纲。这是整卷节奏规划的关键环节，作者会先评估整卷节奏是否合理，再决定是否开始写作。

## 细纲生成要求

### 1. 节奏控制
- 本卷共{len(chapters)}章，需要合理分配剧情密度
- 前3章：快速进入状态，建立本卷主线冲突
- 中间章节：稳步推进，每3-5章要有一个小高潮
- 最后2-3章：本卷高潮和收束，为下一卷埋钩子
- 避免连续多章都是打斗或都是对话，要有张弛节奏

### 2. 章节细纲结构
每章细纲必须包含：
- **本章目标**：这一章要完成什么剧情任务
- **开场**：场景、氛围、出场人物
- **剧情推进**：3-5个关键事件，要有因果关系
- **冲突与转折**：本章的矛盾点和意外转折
- **角色状态**：涉及角色的当前状态和变化
- **硬性约束**：必须遵守的设定（如境界、已有道具等）
- **章末钩子**：为下一章埋的悬念

### 3. 连贯性要求
- 每章的"章末钩子"要和下一章的"开场"衔接
- 角色状态要连续，不能突然出现未解释的变化
- 道具、功法等实体首次出现要合理，不能凭空冒出
- 境界突破要有铺垫，不能一章内连跳几级

### 4. 实体引用规则（重要）
- **优先使用已有角色**：从角色列表中选择，不要随意创造新角色
- **新角色必须有理由**：如果必须新增角色，在proposal_candidates中说明
- **道具/功法首次出现**：要评估合理性，提交提案
- **严禁幻觉**：不能引用不存在的角色、道具、地点

### 5. 输出格式
请输出一个JSON数组，每个元素对应一章：

```json
[
  {{
    "chapter_number": 1,
    "title": "章节标题（简洁有力，体现本章核心）",
    "summary_line": "一句话概括本章剧情",
    "word_count_target": 3000,
    "content_md": "# 本章目标\\n[本章要完成的剧情任务]\\n\\n## 开场\\n**场景**：[地点、时间]\\n**氛围**：[紧张/轻松/神秘等]\\n**出场人物**：[角色名列表]\\n**开场钩子**：[吸引读者的开场设计]\\n\\n## 剧情推进\\n1. [第一个关键事件]\\n2. [第二个关键事件]\\n3. [第三个关键事件]\\n...\\n\\n## 冲突与转折\\n[本章的主要矛盾和意外转折]\\n\\n## 角色状态\\n- [角色A]：当前境界XX，状态XX，本章变化XX\\n- [角色B]：...\\n\\n## 硬性约束\\n- [必须遵守的设定1]\\n- [必须遵守的设定2]\\n\\n## 章末钩子\\n[为下一章埋的悬念，要具体]",
    "hard_constraints": [
      "主角当前境界：炼气九层，不能突破到筑基",
      "已有道具：玄铁剑、储物袋",
      "已知敌人：血煞宗长老（筑基后期）"
    ],
    "referenced_entities": {{
      "characters": ["主角名", "配角A", "反派B"],
      "items": ["玄铁剑", "储物袋"],
      "factions": ["血煞宗"],
      "locations": ["青云山", "天元城"],
      "rules": ["炼气期不能御空飞行"],
      "realms": ["炼气九层", "筑基后期"]
    }},
    "proposal_candidates": [
      {{
        "entity_type": "item",
        "name": "新道具名",
        "reason": "首次出现合理性",
        "target_section": "items",
        "entry": {{
          "name": "新道具名",
          "summary": "一句话定义",
          "details": "详细说明"
        }}
      }}
    ],
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
4. 优先使用已有角色和世界观实体；如果确需首次出现新实体，必须放进 proposal_candidates，等待作者审批
5. content_md 是给作者读和改的整章细纲，必须是一整块 Markdown 文本；不要再写“第X章”标题，标题只放在 title 字段
6. 只输出JSON，不要输出任何说明文字""")

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

    if recent_memories:
        recent_memories.reverse()
        memory_lines = [f"- 第{item.chapter_number}章：{item.summary or '待补充'}" for item in recent_memories]
        parts.append("## 近期动态记忆\n" + "\n".join(memory_lines) + "\n")

    if synopsis:
        seg_detail = synopsis.content_md or ""
        if segment == "opening":
            seg_detail = seg_detail or f"场景：{synopsis.opening_scene}\n基调：{synopsis.opening_mood}\n钩子：{synopsis.opening_hook}"
        elif segment == "middle":
            seg_detail = seg_detail or f"事件：{', '.join(synopsis.development_events or [])}\n冲突：{', '.join(synopsis.development_conflicts or [])}"
        elif segment == "ending":
            seg_detail = seg_detail or f"结局：{synopsis.ending_resolution}\n悬念：{synopsis.ending_cliffhanger}\n下章钩子：{synopsis.ending_next_hook}"

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

    if context_type == "outline":
        outline = db.query(Outline).filter(
            Outline.novel_id == novel_id, Outline.confirmed == True
        ).order_by(Outline.version.desc()).first()
        if outline:
            parts = [f"你是小说《{novel.title}》的AI创作助手。"]
            parts.append(f"\n当前用户正在编辑【大纲】，内容如下：\n{outline.content[:1500]}")
        else:
            # 大纲未生成时，强制引导流程
            parts = [f"你是小说创作AI助手。当前用户正在【大纲页】，书名「{novel.title}」只是占位符。"]
            parts.append("\n【核心规则】用户如果说「生成大纲」「帮我生成大纲」等类似请求，你必须：")
            parts.append("1. 不要直接生成任何内容")
            parts.append("2. 不要使用书名作为创意")
            parts.append("3. 必须先通过友好对话询问用户：")
            parts.append("   - 想写什么类型的小说？（玄幻/修仙/都市/科幻等）")
            parts.append("   - 故事的核心创意是什么？（主角、能力、目标、冲突）")
            parts.append("   - 希望什么故事基调？（热血/黑暗/轻松等）")
            parts.append("\n【对话示例】")
            parts.append("用户：帮我生成大纲")
            parts.append("你：好的！在生成大纲之前，我需要了解一些信息：")
            parts.append("1. 你想写什么类型的小说？（玄幻、修仙、都市、科幻等）")
            parts.append("2. 能简单说说故事的核心创意吗？比如主角是谁、有什么特殊能力、要完成什么目标？")
            parts.append("3. 你希望故事是什么基调？（热血、黑暗、轻松等）")
            parts.append("\n【重要】只有当用户回答了这些问题后，你才能用<GENERATE_OUTLINE>用户提供的完整创意</GENERATE_OUTLINE>标记触发生成。")
            parts.append("\n【禁止】绝对不要用书名、不要用<PATCH>标记、不要直接输出大纲内容。")

    elif context_type == "characters":
        parts = [f"你是小说《{novel.title}》的AI创作助手。"]
        characters = db.query(Character).filter(Character.novel_id == novel_id).all()
        if characters:
            parts.append(f"\n当前用户正在编辑【角色库】，现有角色：\n{_summarize_characters(characters)}")

    elif context_type == "worldbuilding":
        parts = [f"你是小说《{novel.title}》的AI创作助手。"]
        wb = db.query(Worldbuilding).filter(Worldbuilding.novel_id == novel_id).first()
        if wb:
            parts.append(f"\n当前用户正在编辑【世界观设定】：\n{_summarize_worldbuilding(wb)}")

    elif context_type == "chapter" and context_id:
        parts = [f"你是小说《{novel.title}》的AI创作助手。"]
        chapter = db.query(Chapter).filter(Chapter.id == context_id).first()
        synopsis = db.query(Synopsis).filter(Synopsis.chapter_id == context_id).first() if chapter else None
        if chapter:
            parts.append(f"\n当前用户正在编辑【第{chapter.chapter_number}章《{chapter.title or ''}》】")
        if synopsis:
            parts.append(f"本章细纲：开场={synopsis.opening_scene}，冲突={', '.join(synopsis.development_conflicts or [])}")
        if chapter and chapter.content:
            parts.append(f"已写正文（最后300字）：...{chapter.content[-300:]}")
    else:
        parts = [f"你是小说《{novel.title}》的AI创作助手。"]

    if context_type != "outline" or (context_type == "outline" and db.query(Outline).filter(Outline.novel_id == novel_id, Outline.confirmed == True).first()):
        parts.append("\n\n请根据用户的问题或建议，给出专业的创作意见。如果用户要求修改某段内容，请直接输出修改后的版本，用<PATCH>修改后的内容</PATCH>包裹。")

    return "".join(parts)
