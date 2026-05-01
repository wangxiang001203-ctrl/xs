# AI 写书平台编辑器模块优化分析文档

> 本文档从**专业作家 + 编辑 + AI 系统架构师**三重视角，对你现有编辑器部分进行全面分析，聚焦：大纲-设定联动机制、长期记忆体系、AI 对话系统串联、以及流程瘦身。

---

## 一、现状问题全面诊断

### 1.1 当前流程为什么跑不通

你的系统目前存在 **"多层状态机互相锁死"** 的问题。让我还原一下现有流程链条：

```
大纲确认
  ↓
生成全书分卷 (生成卷级规划markdown)
  ↓
审批全书分卷 (每卷的 plan_data.book_plan_status = approved)
  ↓
进入单卷 → 生成全卷章节细纲 (一次性生成 N 章)
  ↓
审批单卷 (volume.review_status = approved)
  ↓
进入正文 (章节必须满足: 细纲approved + 前章final_approved)
  ↓
正文定稿检查 → 生成设定提案 → 逐条审批提案 → 章节final_approved
```

**问题链条分析：**

1. **双重审批负担**：每卷需要审批两次——先审"全书分卷"里的卷计划，再审"单卷细纲"节奏。用户的操作路径太深，两次审批之间没有清晰的下一步指引。

2. **章节解锁机制过严**：当前逻辑是"前章未定稿则后章不能进入"。这个机制在 40 章/卷的体量下会产生连锁阻塞——只要有一章卡住，后面的章节全部冻结，用户无法并行规划和创作。

3. **细纲和正文耦合**：ChapterPage 里同时展示细纲和正文，两者共用同一个章节上下文。正文 AI 对话（ContentAI.tsx）和设定 AI 对话（SettingsAI.tsx）功能高度重复但实现路径完全不同，没有统一调度。

4. **大纲修改没有任何联动**：当你修改大纲后，大纲里的"简介/卖点/主线"变了，但分卷规划不会自动同步、分卷里的章节规划不会同步、已生成的细纲更不会同步。这是**最大的架构缺陷**。

5. **关系网没有作为独立系统**：实体（EntityRelation, EntityEvent, StoryEntity）虽然设计了，但它们和编辑器之间是"松耦合"——正文写作时不会实时查询关系网来校验冲突，AI 也不会把关系网作为上下文来生成内容。

6. **AI 对话没有串联全系统**：当前有两个 AI 对话入口（ContentAI 和 SettingsAI），但它们都是"本地处理器"——没有全局上下文注入、没有跨模块推理能力、没有把设定变更回写到关系网。

### 1.2 当前代码结构的根本问题

**问题 A：数据模型层级混乱**

```
Outline（大纲）
  ├── OutlineChatMessage（大纲对话历史）
  ├── Volume（分卷）
  │     ├── plan_data.book_plan_status (卷级审批状态)
  │     ├── review_status (卷细纲审批状态)
  │     └── Chapter（章节）
  │           ├── Synopsis（章节细纲）
  │           ├── ChapterMemory（章节记忆）
  │           └── EntityProposal（设定提案）
  ├── Character（角色）
  ├── Worldbuilding（世界观）
  └── StoryEntity / EntityEvent / EntityRelation（关系网）
```

当前 Volume 同时承担了两个职责：卷级规划和细纲存储。plan_markdown 和 plan_data 混在一起，导致"全书分卷审批"和"单卷细纲审批"共享同一个对象但操作的是不同字段。

**问题 B：多层缓存导致状态不一致**

前端有 `documentDrafts` 本地草稿，后端有 `file_service` 的 JSON 文件存储，数据库还有 `Chapter.content`、`Synopsis`、`Volume.plan_markdown` 等多个副本。三套数据没有明确的同步优先级，用户很容易在不同状态之间迷失。

**问题 C：AI 生成是"一次性批处理"而非"持续创作流"**

- `generateBookVolumes` → 生成整书卷规划
- `generateVolumeSynopsis` → 生成整卷章节细纲
- `generateChapterDraft` → 生成单章正文

每次生成都是一个独立任务，没有"增量生成 + 渐进审批"的机制。40 章细纲一次性全部生成，用户要么全接受要么全放弃，粒度太粗。

---

## 二、核心问题 1：大纲 ↔ 设定联动机制

### 2.1 需求定义

修改大纲时，系统必须能够：
- 识别大纲中哪些字段发生了变化（简介变化、主线变化、核心冲突变化）
- 自动检测哪些分卷/章节细纲引用了这些内容
- 给出变更影响评估：哪些卷规划需要调整、哪些章节细纲需要刷新
- 用户确认变更范围后，自动执行联动修改

反过来，修改设定时：
- 识别这个设定被哪些章节引用
- 检测是否与大纲矛盾（如大纲说主角在 A 城，但设定里主角已迁移到 B 城）
- 生成矛盾报告和修正建议

### 2.2 现有代码的缺陷

**`ai_workflow_service.py` 的 `classify_intent` 函数**：意图识别做得很好，但没有实现"联动影响分析"。当用户说"把主角从废柴改成天才"，AI 能识别这是 `revise_outline`，但它不知道这会影响多少章节细纲和已写正文。

**`assistant_service.py` 的 `build_file_catalog` 函数**：虽然构建了文件目录，但没有对"变更影响范围"做语义分析。它只是把所有文件都读出来，没有判断"这个文件里的哪个部分会被这次修改影响"。

**`review_service.py` 的 `create_memory_review_proposals`**：章节定稿后抽取记忆的逻辑很好，但它只处理单个章节，没有"跨章节的状态回溯"。

### 2.3 推荐方案

#### 2.3.1 新增「变更影响分析器」模块

在 `assistant_service.py` 或独立模块中实现：

```python
class OutlineChangeImpactAnalyzer:
    """
    分析大纲修改对全书的影响范围。
    输出：
      - affected_volumes: 哪些卷的分卷规划引用了大纲变化内容
      - affected_chapters: 哪些章节细纲需要刷新
      - setting_conflicts: 哪些设定与新大纲存在矛盾
      - generation_required: 哪些内容需要重新生成
    """

    def analyze(self, old_outline: Outline, new_outline: Outline) -> ImpactReport:
        ...
```

#### 2.3.2 变更联动写入协议

当大纲变更被用户确认后，系统应该：
1. 记录变更 diff（使用结构化 diff 而非纯文本）
2. 扫描所有 Volume.plan_markdown，标记引用了变更内容的章节
3. 扫描所有 Synopsis，检测矛盾（用 `validator.py` 的现有校验能力）
4. 生成"需要刷新"清单，用户可批量或逐个确认刷新
5. 用新大纲内容作为上下文重新生成受影响部分

#### 2.3.3 设定变更的联动机制

反过来，当角色设定变更时（境界升级、地点迁移、关系变化）：
1. 扫描所有未定稿章节的正文中是否已出现新状态
2. 生成矛盾警告（如"第5章已写主角在A城，但设定已变更到B城"）
3. 矛盾清单提交给用户，决定是回退设定还是覆盖正文

**这正是你需要图数据库（Neo4j）的原因**：关系网越复杂，跨实体的影响分析越需要图遍历能力。PostgreSQL + JSONB 在 100+ 角色、1000+ 关系的规模下仍然可行，但到了 1000+ 角色、10,000+ 关系时，图数据库的查询性能优势会非常明显。建议：

- **初期（1000 会员，假设每本 100 章）**：继续用 PostgreSQL + JSONB，用 `EntityRelation` 表的多跳查询可以支撑。
- **中后期**：如果你的用户增长到 10,000+，考虑引入 Neo4j 或者用 PostgreSQL 的 `pgRouting` 扩展做图查询。

---

## 三、核心问题 2：长期记忆体系（支持百万字小说）

### 3.1 需求定义

百万字小说 = ~1000 章。当前系统只有**章节级记忆**（ChapterMemory），缺少**跨章节聚合记忆**和**全局知识索引**。

### 3.2 现有代码的缺陷

**`review_service.py` 的 `build_chapter_memory` 函数**：

```python
# 当前：只抽取本章的事实
content = chapter.content or ""
source_excerpt = content[:4000]  # 只取前4000字
prompt = f"""你是长篇玄幻修仙小说的连续性编辑。请只依据给定章节正文与细纲，抽取本章已经真实发生且能影响后续写作的事实。"""
```

**问题**：
1. 只看前 4000 字，超长章节会丢失后续内容
2. 没有"前 N 章关键状态摘要"作为上下文输入，AI 无法判断"这次升级和上次升级是什么关系"
3. 章节记忆独立存储，没有建立跨章节索引
4. 百万字小说需要"全局状态快照"——每个 10 万字节点需要一个聚合摘要

### 3.3 推荐方案：三层记忆架构

```
┌─────────────────────────────────────────────────────────────┐
│ L0: 原始数据层                                               │
│   - 章节正文 (Chapter.content)                              │
│   - 章节细纲 (Synopsis)                                      │
│   - 章节记忆 (ChapterMemory)                                  │
└──────────────────────────────┬──────────────────────────────┘
                               │ 聚合
┌──────────────────────────────▼──────────────────────────────┐
│ L1: 聚合摘要层（每 10 章一个快照）                            │
│   - BookChapterSnapshot: 10 章一聚合，包含：                  │
│     - 这 10 章的核心剧情走向                                  │
│     - 角色状态变化里程碑                                      │
│     - 关键道具/地点变更                                       │
│     - 未解决的伏笔清单                                        │
│   - 卷级记忆: 每卷结束时聚合本卷所有章节                        │
│     - 本卷主角成长弧线                                        │
│     - 本卷核心冲突解决情况                                    │
│     - 开启的下卷伏笔                                          │
└──────────────────────────────┬──────────────────────────────┘
                               │ 再聚合
┌──────────────────────────────▼──────────────────────────────┐
│ L2: 全局知识索引（全书级）                                    │
│   - 全局角色状态表: 每个角色的当前境界、位置、关系              │
│   - 全局道具流转表: 每个道具的当前持有者、历史归属              │
│   - 全局地点状态表: 每个地点的当前状态（战前/战后/沦陷等）     │
│   - 全局事件时间线: 按章节排序的所有关键事件                    │
│   - 伏笔追踪表: 哪些伏笔在哪章埋下、是否已回收                │
└─────────────────────────────────────────────────────────────┘
```

**实现要点：**

1. **L0 → L1 自动触发**：每写完 10 章（或每卷结束时），自动触发聚合摘要生成。不需要用户手动操作。

2. **L1 → L2 增量更新**：每次章节定稿后，更新全局索引中的"增量变更"。不需要全量重建。

3. **AI 生成时的记忆注入**：在 `assistant_service.py` 的 `build_smart_chat_context` 中，根据当前章节号，动态注入：
   - 前 3 章的关键状态
   - 本卷已确认的聚合摘要
   - 全局角色当前状态（如果涉及角色）
   - 未回收伏笔清单

4. **百万字检索策略**：当上下文窗口不足时，按优先级注入：
   ```
   优先级1: 章节细纲（必读）
   优先级2: 前 1-3 章记忆（高权重）
   优先级3: 角色当前状态（涉及角色时）
   优先级4: 10 章聚合快照（涉及剧情走向时）
   优先级5: 卷级记忆（涉及卷级冲突时）
   优先级6: 全局事件时间线（涉及伏笔时）
   ```

### 3.4 具体代码改造

在 `assistant_service.py` 中新增：

```python
def build_memory_context(db: Session, novel_id: str, chapter_number: int | None, limit: int = 8000) -> str:
    """
    根据当前章节号，动态构建长期记忆上下文。
    策略：前3章记忆 + 10章聚合快照 + 全局角色状态 + 未回收伏笔
    """
    parts = []

    # 1. 前3章记忆
    if chapter_number:
        recent_memories = db.query(ChapterMemory).filter(
            ChapterMemory.novel_id == novel_id,
            ChapterMemory.chapter_number < chapter_number,
            ChapterMemory.chapter_number >= max(1, chapter_number - 3),
        ).all()
        for mem in recent_memories:
            if mem.summary:
                parts.append(f"【第{mem.chapter_number}章】{mem.summary}")
            if mem.state_changes:
                parts.append("  状态变化：" + "；".join(mem.state_changes))

    # 2. 全局角色状态表（按重要性取前10个）
    # 从 EntityRelation + StoryEntity + Character 聚合

    # 3. 未回收伏笔
    # 从 open_threads 字段聚合

    return "\n\n".join(parts)
```

---

## 四、核心问题 3：AI 对话系统重构（串联全系统）

### 4.1 现状问题

当前有两个 AI 对话入口，逻辑高度重复但能力分散：

| 对比项 | ContentAI | SettingsAI |
|--------|-----------|------------|
| 上下文 | 章节+角色+世界观+卷细纲 | 根据当前视图上下文 |
| 功能 | 章节写作辅助+提案审批 | 全局设定修改+大纲对话 |
| 缺陷 | 只能在章节页用，无法操作设定 | 不知道当前章节的状态 |
| 共同问题 | 都不能看到"全局状态快照"，无法做跨章节推理 |

**最核心的问题**：`ContentAI` 和 `SettingsAI` 都没有访问"全局关系网"和"长期记忆上下文"，它们只知道当前打开的文件内容，不知道整个系统的状态。

### 4.2 推荐方案：统一 AI 助手 + 分层能力

将 AI 对话重构为**一个统一的助手**，在不同上下文下展现不同能力：

```
┌──────────────────────────────────────────┐
│         统一 AI 助手（单一入口）           │
├──────────────────────────────────────────┤
│  ┌─ 上下文感知层 ─┐                       │
│  │ - 我现在在哪里（大纲/分卷/章节/设定）    │
│  │ - 当前章节号是多少                     │
│  │ - 哪些是已定稿章节                     │
│  │ - 未审提案数量                         │
│  └────────────────┘                       │
│  ┌─ 能力分发层 ─┐                        │
│  │ - 大纲页：生成/打磨大纲               │
│  │ - 分卷页：生成/修改卷规划              │
│  │ - 章节页：写作辅助 + 连续性检查        │
│  │ - 设定页：创建/修改角色/道具/地点      │
│  │ - 全局：变更联动分析 + 冲突检测        │
│  └────────────────┘                       │
│  ┌─ 记忆注入层 ─┐                        │
│  │ - 全局状态快照                        │
│  │ - 前 N 章关键状态                     │
│  │ - 关系网实时查询结果                   │
│  └────────────────┘                       │
└──────────────────────────────────────────┘
```

**具体改造：**

1. **合并两个 AI 对话入口**：前端只保留一个 AI 对话面板（SettingsAI 的交互更完整，以此为基础），但根据 `currentView` 动态注入不同的 system prompt 和上下文。

2. **新增"全局上下文"注入**（在 `assistant_service.py` 中）：
   ```python
   def build_unified_context(db: Session, payload: dict) -> str:
       novel_id = payload["novel_id"]
       context_type = payload.get("context_type")
       chapter_number = _get_current_chapter_number(db, payload)  # 新增

       lines = [f"【当前作品】{novel.title}"]
       lines.append(f"【当前页面】{context_type}")

       # 全局状态摘要（新增）
       global_summary = build_global_novel_summary(db, novel_id)
       lines.append(f"【全局状态】{global_summary}")

       # 长期记忆上下文（新增）
       if chapter_number:
           memory_context = build_memory_context(db, novel_id, chapter_number)
           lines.append(f"【近期记忆】{memory_context}")

       # 关系网上下文（新增）
       if context_type == "chapter":
           relation_context = build_relation_context(db, novel_id, chapter_number)
           lines.append(f"【关系网状态】{relation_context}")

       return "\n\n".join(lines)
   ```

3. **AI 对话应该能执行"联动操作"**：
   - 用户说"修改大纲里主角的开局设定" → AI 应该能直接修改大纲，检测影响范围，并给用户展示受影响的部分
   - 用户说"检查第5章和第15章的角色状态是否矛盾" → AI 应该能跨章节查询关系网，输出对比报告
   - 用户说"生成第3卷的第20章正文" → AI 应该知道第3卷的结构、第20章的细纲、前19章的关键状态

4. **AI 对话的结果应该自动写回关系网**：当用户在 AI 对话中确认了一个设定变更，这个变更应该自动进入 `EntityProposal` 审批流，或者直接写入关系网（取决于变更类型）。

---

## 五、流程瘦身方案

### 5.1 剔除冗余逻辑

| 当前 | 建议 | 原因 |
|------|------|------|
| `OutlineChatMessage` 表 | 合并到通用对话历史 | 大纲对话和设定对话不应该分开存储 |
| 双层提案系统（章节页+分卷页各一套） | 统一提案池，按 chapter_id/volume_id 筛选 | 两套提案审批逻辑重复，维护成本高 |
| `documentDrafts` 本地草稿 | 改用后端自动保存 + 版本历史 | 前端本地草稿在多设备场景下不可靠 |
| `plan_markdown` 和 `plan_data` 双存储 | 统一到结构化 JSON，只在展示层渲染 markdown | 避免 markdown 和结构化数据不同步 |
| 两个 AI 对话入口 | 合并为一个统一 AI 助手 | 减少用户困惑，降低维护成本 |

### 5.2 流程简化为 5 步

```
Step 1: 大纲 → 用户与 AI 对话生成大纲 → 确认大纲（锁定）
    ↓
Step 2: 生成全书分卷 → AI 根据大纲生成分卷规划 → 审批（一次性审批所有卷）
    ↓
Step 3: 进入某一卷 → AI 一次性生成本卷所有章节细纲（批量） → 审批（一次性审批所有细纲）
    ↓
Step 4: 按章节创作正文 → 每章定稿 → AI 自动抽取记忆 → 全局状态快照自动更新
    ↓
Step 5: 设定维护（随时可做） → AI 辅助 → 提案审批 → 写入关系网
```

**关键变化：**
- 去掉"卷细纲审批"单独页面（合并到分卷生成流程中）
- 去掉"正文侧边栏分卷/正文两个区域"（合并为单一章节列表）
- 去掉"细纲页"（细纲在章节页侧边栏展示，不单独占用页面）
- AI 对话在所有页面可用，不受页面类型限制

### 5.3 侧边栏重构

**新的左侧结构：**
```
作品结构
├── 大纲
├── 简介
├── 全书分卷（展示所有卷的概览列表）
│
通用设定
├── 角色库（全部角色卡片列表）
├── 关系网（可视化图谱）
├── 世界观（所有设定文件）
│
正文
└── 第1卷 第1章 / 第2章 / ... 第N章
    第2卷 第1章 / 第2章 / ... 第N章
```

正文列表按"卷"折叠，点击卷展开所有章节。**不能在正文列表里直接新建章节**——章节由 AI 在"全书分卷"流程中自动生成。

---

## 六、技术架构建议

### 6.1 Python 是否够用？

**够用，但需要升级架构。** 当前 FastAPI + 同步数据库操作的模式在 1000+ 并发用户下会有瓶颈。建议：

1. **异步数据库**：用 `SQLAlchemy 2.0` + `asyncpg`，所有数据库操作改为 `async`
2. **任务队列**：用 `Celery` + `Redis` 或 `FastAPI BackgroundTasks` 处理 AI 生成任务
3. **连接池**：配置合理的数据库连接池大小（建议 min=10, max=50）
4. **缓存**：用 Redis 缓存热门小说的"全局状态快照"和"关系网"，减少数据库查询

**预估并发能力**（如果做了上述升级）：
- 单 FastAPI 实例：~200-500 并发用户
- 4 实例 + Nginx 负载均衡：~1000-2000 并发
- 初期 1000 会员完全够用

### 6.2 前端是否需要升级？

当前 React + Ant Design 的组合**够用**，但有几个建议：

1. **富文本编辑器**：当前用原生 TextArea，建议换用 `@tiptap/react` 或 `slate` 作为正文编辑器，支持格式化和 AI 辅助写作
2. **状态管理**：当前用 `useAppStore`（应该是 Zustand 或类似），可以考虑升级到更结构化的方案
3. **实时协作**：如果以后需要多人协作编辑，考虑引入 Yjs 或 Automerge

### 6.3 是否需要单独管理端项目？

**建议分开**，但分两步走：

**第一阶段（在当前项目中）：**
- 用不同的路由前缀区分：`/admin/*` 和 `/api/*`
- 管理端复用同一个数据库，只是 API 路径不同
- 用户端和管理端共享 `model_config` 等配置

**第二阶段（用户量超过 5000 后）：**
- 拆出独立 `admin-backend` 项目（FastAPI 或 Django）
- 独立 `admin-frontend` 项目（React Admin 或 Refine）
- 两个后端共享同一个 PostgreSQL，用不同的只读/读写权限分离
- 理由：管理端的查询模式（批量导出、报表、计费统计）和用户端完全不同，放一起会增加复杂度

### 6.4 多模型接入建议

当前 `ai_service.py` 的模型调用需要抽象成统一接口：

```python
class AIModelAdapter(Protocol):
    async def generate(self, system: str, messages: list[dict]) -> str: ...

class OpenAIAdapter(AIModelAdapter): ...
class AnthropicAdapter(AIModelAdapter): ...
class DoubaoAdapter(AIModelAdapter): ...

class ModelRouter:
    def __init__(self, config: WorkflowConfig):
        self.adapters: dict[str, AIModelAdapter] = {
            "openai": OpenAIAdapter(...),
            "anthropic": AnthropicAdapter(...),
            "doubao": DoubaoAdapter(...),
        }

    async def generate(self, model_id: str, system: str, messages: list[dict]) -> str:
        adapter = self.adapters.get(model_id)
        if not adapter:
            adapter = self.adapters["doubao"]  # 默认用豆包
        return await adapter.generate(system, messages)
```

计费模块：
- 每次 AI 调用记录 `token_used`、`model_id`、`cost`
- 按用户汇总月度用量
- 在管理端展示用量排行榜

---

## 七、实施优先级建议

| 优先级 | 改造项 | 工作量 | 价值 |
|--------|--------|--------|------|
| P0 | 统一 AI 助手（合并 ContentAI + SettingsAI） | 中 | 直接提升用户体验 |
| P0 | 全局状态快照 + 三层记忆架构 | 高 | 支持百万字的核心能力 |
| P0 | 大纲 ↔ 设定联动机制（变更影响分析） | 高 | 解决最核心的逻辑缺陷 |
| P1 | 流程瘦身（去掉冗余审批层） | 中 | 降低用户操作复杂度 |
| P1 | 关系网实时查询（AI 对话中注入关系上下文） | 中 | 让 AI 真正理解全系统状态 |
| P2 | PostgreSQL 异步化 + Redis 缓存 | 高 | 支撑 1000+ 并发 |
| P2 | 富文本编辑器升级 | 中 | 提升写作体验 |
| P3 | 管理端拆分 | 低 | 将来再考虑 |

---

## 八、总结

你的核心问题是**三个没有打通**：

1. **大纲没有和后续内容打通** → 修改大纲后其他设定不会联动变化
2. **AI 对话没有和关系网打通** → AI 不知道全系统的当前状态
3. **章节记忆没有和全局状态打通** → 百万字小说时 AI 无法做跨章节推理

只要解决这三个"打通"，整个系统的逻辑就会流畅起来。建议按优先级从 P0 开始逐个实现。
