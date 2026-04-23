# 数据库表结构备注（业务字典）

> 说明：字段以后端 ORM 模型为准，已在模型中补充 `comment`。本文件用于快速查阅业务含义。

## novels（小说基础信息表）

- `id`：小说ID
- `title`：小说标题
- `genre`：小说题材
- `idea`：创作灵感或初始想法
- `synopsis`：小说简介
- `status`：创作状态（`draft`/`writing`/`completed`）
- `created_at`：创建时间
- `updated_at`：更新时间

## outlines（小说大纲表）

- `id`：大纲ID
- `novel_id`：所属小说ID
- `title`：大纲标题
- `synopsis`：故事简介（大纲层）
- `selling_points`：卖点设定
- `main_plot`：主线剧情规划
- `content`：兼容旧版的大纲正文
- `ai_generated`：是否由AI生成
- `confirmed`：是否已确认采用
- `version`：大纲版本号
- `created_at`：创建时间

## volumes（分卷信息表）

- `id`：分卷ID
- `novel_id`：所属小说ID
- `volume_number`：分卷序号
- `title`：分卷标题
- `description`：分卷简介
- `synopsis_generated`：是否已生成分卷细纲
- `created_at`：创建时间

## chapters（章节正文表）

- `id`：章节ID
- `novel_id`：所属小说ID
- `volume_id`：所属卷ID
- `chapter_number`：章节序号
- `title`：章节标题
- `content`：章节正文
- `word_count`：章节字数
- `plot_summary`：章节剧情摘要
- `status`：章节状态（`draft`/`writing`/`completed`）
- `created_at`：创建时间
- `updated_at`：更新时间

## characters（人物设定表）

- `id`：人物ID
- `novel_id`：所属小说ID
- `name`：人物名称
- `role`：人物定位（如主角/反派）
- `gender`：性别
- `age`：年龄
- `race`：种族
- `realm`：当前境界名称
- `realm_level`：境界层级数值
- `faction`：所属势力
- `techniques`：功法/技能列表（JSON）
- `artifacts`：法宝/装备列表（JSON）
- `appearance`：外貌特征
- `personality`：性格描述
- `background`：人物背景
- `golden_finger`：金手指或特殊能力
- `motivation`：核心动机或执念
- `relationships`：人物关系网（JSON）
- `status`：生存状态（`alive`/`dead`/`unknown`）
- `first_appearance_chapter`：首次出场章节号
- `last_updated_chapter`：最近一次更新涉及章节号
- `created_at`：创建时间
- `updated_at`：更新时间

## worldbuilding（世界观设定表）

- `id`：世界观ID
- `novel_id`：所属小说ID（唯一）
- `power_system`：力量或境界体系（JSON）
- `factions`：势力组织设定（JSON）
- `geography`：地理与关键地点（JSON）
- `core_rules`：世界核心规则（JSON）
- `items`：关键物品与资源（JSON）
- `updated_at`：更新时间

## synopses（章节细纲表）

- `id`：细纲ID
- `chapter_id`：所属章节ID（唯一）
- `novel_id`：所属小说ID
- `opening_scene`：开场场景
- `opening_mood`：开场氛围
- `opening_hook`：开场钩子
- `opening_characters`：开场出场人物（JSON）
- `development_events`：发展阶段关键事件（JSON）
- `development_conflicts`：发展阶段冲突（JSON）
- `development_characters`：发展阶段涉及人物（JSON）
- `ending_resolution`：结尾收束
- `ending_cliffhanger`：章末悬念
- `ending_next_hook`：下一章钩子
- `all_characters`：本章涉及人物全集（JSON）
- `word_count_target`：目标字数
- `plot_summary_update`：写作后剧情回填摘要
- `updated_at`：更新时间

## ai_context_snapshots（AI上下文快照表）

- `id`：快照ID
- `novel_id`：所属小说ID
- `chapter_id`：关联章节ID
- `snapshot_type`：快照类型（`outline`/`chapter`/`synopsis`/`worldbuilding`）
- `compressed_summary`：压缩后的上下文摘要
- `token_count`：摘要token数
- `created_at`：创建时间
