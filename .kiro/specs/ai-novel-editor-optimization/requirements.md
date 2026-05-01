# Requirements Document

## Introduction

本文档定义 AI 玄幻小说编辑器系统优化项目的功能需求。该项目旨在解决当前系统存在的流程不通畅、AI 能力不足、缺少长期记忆等核心问题，通过系统性重构提升用户创作体验和 AI 辅助能力。

**项目背景**：当前系统已实现基础的大纲-分卷-章节创作流程，但存在多层状态机互相锁死、AI 对话能力分散、缺少跨章节记忆聚合等问题。本次优化将重构核心架构，建立统一的 AI 助手、三层记忆体系和大纲-设定联动机制。

**目标用户**：网文作者（玄幻/修仙类型），需要 AI 辅助完成百万字级别长篇小说创作。

## Glossary

- **System**: AI 玄幻小说编辑器系统
- **Outline_Module**: 大纲模块，负责管理小说总体框架
- **Synopsis_Module**: 细纲模块，负责管理章节级别的剧情规划
- **Chapter_Module**: 章节模块，负责管理正文内容
- **Character_Module**: 角色模块，负责管理角色设定
- **Worldbuilding_Module**: 世界观模块，负责管理世界观设定
- **AI_Assistant**: 统一 AI 助手，提供全局智能对话能力
- **Memory_System**: 长期记忆系统，支持百万字小说的上下文管理
- **Relation_Network**: 关系网系统，管理实体间的关系和状态
- **Review_System**: 审批系统，管理所有 AI 生成内容的审批流程
- **Impact_Analyzer**: 变更影响分析器，分析修改对全书的影响范围
- **Entity**: 实体，包括角色、道具、地点、势力、功法、境界等
- **Proposal**: 提案，AI 生成的待审批内容
- **Chapter_Memory**: 章节记忆，单章节的事实抽取结果
- **Aggregated_Memory**: 聚合记忆，多章节的汇总摘要
- **Global_State**: 全局状态，全书级别的实体状态快照

## Requirements

### Requirement 1: 强制大纲确认门禁

**User Story:** 作为作者，我希望在确认大纲之前无法进入后续创作流程，以确保创作方向明确后再开始详细规划。

#### Acceptance Criteria

1. WHEN THE Outline_Module 的大纲未确认，THE System SHALL 锁定所有后续功能入口
2. WHEN 用户尝试访问角色、世界观、分卷、章节等模块，THE System SHALL 显示提示信息并阻止访问
3. WHEN THE Outline_Module 的大纲被确认，THE System SHALL 解锁所有后续功能模块
4. THE System SHALL 在界面上清晰标识大纲确认状态
5. WHEN 大纲已确认后被修改，THE System SHALL 触发影响分析流程

### Requirement 2: 统一文本编辑审批体验

**User Story:** 作为作者，我希望所有文本编辑都使用一致的对比审批模式，以便高效地审阅和确认 AI 生成的内容。

#### Acceptance Criteria

1. WHEN AI 生成大纲、角色、世界观或章节内容，THE System SHALL 展示左右对比视图
2. THE System SHALL 在左侧显示原始内容，在右侧显示 AI 修改后的内容
3. THE System SHALL 提供接受、拒绝、继续修改三个操作选项
4. WHEN 用户选择接受，THE System SHALL 将修改后的内容保存为正式版本
5. WHEN 用户选择拒绝，THE System SHALL 保留原始内容并丢弃修改
6. WHEN 用户选择继续修改，THE System SHALL 保持审批界面并允许用户提出新的修改要求
7. THE System SHALL 记录每次审批的历史版本

### Requirement 3: 全局 AI 智能体

**User Story:** 作为作者，我希望 AI 能够访问所有文件并主动分析修改的影响范围，以便在修改大纲或设定时获得智能的联动建议。

#### Acceptance Criteria

1. THE AI_Assistant SHALL 能够访问大纲、角色、世界观、章节、记忆等所有文件
2. WHEN 用户修改大纲，THE AI_Assistant SHALL 自动分析哪些分卷、章节、角色会受影响
3. WHEN 用户修改角色设定，THE AI_Assistant SHALL 检测与大纲和已写章节的矛盾
4. THE AI_Assistant SHALL 生成变更影响报告，列出受影响的具体内容
5. THE AI_Assistant SHALL 提出联动修改方案供用户审批
6. WHEN 用户确认联动修改，THE System SHALL 批量执行修改并更新相关内容
7. THE AI_Assistant SHALL 在对话中展示全局视角，而非仅回答当前页面的问题
8. THE AI_Assistant SHALL 能够跨章节查询和推理，支持"检查第5章和第15章的角色状态是否矛盾"等请求

### Requirement 4: 统一审批流机制

**User Story:** 作为作者，我希望所有 AI 生成的内容都进入统一的审批流程，以便集中管理和批量处理待审批项。

#### Acceptance Criteria

1. WHEN AI 生成任何内容（大纲、角色、世界观、章节、设定提案），THE System SHALL 创建审批提案
2. THE Review_System SHALL 将所有提案标记为"待审批"状态
3. THE System SHALL 提供统一的审批中心界面，展示所有待审批项
4. THE System SHALL 支持按类型、章节、时间筛选待审批项
5. THE System SHALL 支持批量审批操作
6. WHEN 用户审批提案，THE System SHALL 记录审批时间、操作和结果
7. THE System SHALL 保留审批历史记录，支持追溯
8. THE System SHALL 在相关模块中显示待审批数量提示

### Requirement 5: 百万字长期记忆系统

**User Story:** 作为作者，我希望系统能够支持百万字级别的长篇小说创作，AI 能够记住前面章节的关键信息并在生成新内容时参考。

#### Acceptance Criteria

1. THE Memory_System SHALL 实现三层记忆架构：章节记忆、聚合记忆、全局状态
2. WHEN 章节定稿，THE System SHALL 自动抽取章节记忆（关键事件、状态变化、道具变化、未完事项）
3. WHEN 完成10章创作，THE System SHALL 自动生成聚合记忆摘要
4. WHEN 完成一卷创作，THE System SHALL 生成卷级聚合记忆
5. THE Memory_System SHALL 维护全局角色状态表，记录每个角色的当前境界、位置、关系
6. THE Memory_System SHALL 维护全局道具流转表，记录每个道具的当前持有者和历史归属
7. THE Memory_System SHALL 维护全局事件时间线，按章节排序记录所有关键事件
8. THE Memory_System SHALL 维护伏笔追踪表，记录哪些伏笔在哪章埋下、是否已回收
9. WHEN AI 生成新内容，THE System SHALL 根据当前章节号动态注入相关记忆上下文
10. THE System SHALL 按优先级注入记忆：章节细纲（必读）> 前1-3章记忆 > 角色当前状态 > 10章聚合快照 > 卷级记忆 > 全局事件时间线

### Requirement 6: 大纲-设定-角色联动机制

**User Story:** 作为作者，我希望修改大纲时系统能够自动检测对设定和角色的影响，并提供联动修改建议，以保持全书的一致性。

#### Acceptance Criteria

1. WHEN 用户修改大纲，THE Impact_Analyzer SHALL 识别大纲中哪些字段发生了变化
2. THE Impact_Analyzer SHALL 扫描所有分卷规划，标记引用了变更内容的部分
3. THE Impact_Analyzer SHALL 扫描所有章节细纲，检测与新大纲的矛盾
4. THE Impact_Analyzer SHALL 扫描所有角色设定，检测与新大纲的矛盾
5. THE Impact_Analyzer SHALL 生成变更影响评估报告，列出需要调整的分卷、章节、角色
6. THE System SHALL 展示影响评估报告供用户确认
7. WHEN 用户确认变更范围，THE System SHALL 用新大纲内容作为上下文重新生成受影响部分
8. WHEN 用户修改角色设定，THE Impact_Analyzer SHALL 扫描所有未定稿章节检测矛盾
9. THE Impact_Analyzer SHALL 生成矛盾警告清单，提交给用户决定是回退设定还是覆盖正文
10. THE System SHALL 使用关系网（EntityRelation、EntityEvent、StoryEntity）进行跨实体影响分析

### Requirement 7: UI/UX 简化优化

**User Story:** 作为作者，我希望界面简洁易用，去除冗余功能，统一交互模式，以提升创作效率。

#### Acceptance Criteria

1. THE System SHALL 移除设定页面的无用工具栏
2. THE System SHALL 简化侧边栏结构，按"作品结构"、"通用设定"、"正文"三个区域组织
3. THE System SHALL 在正文列表中按卷折叠显示章节
4. THE System SHALL 统一所有模块的交互模式，使用一致的操作按钮和布局
5. THE System SHALL 合并重复的 AI 对话入口（ContentAI 和 SettingsAI）为统一 AI 助手
6. THE System SHALL 根据当前页面上下文动态调整 AI 助手的能力和提示
7. THE System SHALL 去除 documentDrafts 本地草稿，改用后端自动保存和版本历史

## Technical Constraints

### 技术栈约束

1. 后端必须使用 FastAPI + SQLAlchemy + MySQL
2. 前端必须使用 React + Ant Design
3. AI 服务必须通过火山方舟调用豆包/DeepSeek
4. 存储必须使用数据库 + 文件系统双存储模式

### 性能约束

1. 单次 AI 调用的上下文不得超过模型的 token 限制
2. 记忆注入的总 token 预算不得超过 8000 tokens
3. 影响分析的响应时间不得超过 5 秒
4. 审批列表的加载时间不得超过 2 秒

### 兼容性约束

1. 必须兼容现有的数据库表结构（可新增表和字段，但不能破坏现有数据）
2. 必须保留现有的文件存储格式（可扩展，但不能导致现有文件无法读取）
3. 必须支持现有项目的平滑迁移，不能要求用户重新创建项目

### 安全性约束

1. 所有 AI 生成的内容必须经过用户审批才能正式生效
2. 批量修改操作必须提供预览和确认机制
3. 关键操作（如删除、批量审批）必须有二次确认
4. 审批历史必须完整记录，支持审计追溯

## Dependencies

### 现有模块依赖

1. **assistant_service.py** - 需要大幅增强，实现统一 AI 助手和全局上下文注入
2. **context_builder.py** - 需要增强，实现三层记忆上下文构建
3. **entity_service.py** - 需要利用，实现关系网查询和影响分析
4. **review_service.py** - 需要扩展，实现统一审批流机制
5. **ai_workflow_service.py** - 需要重构，实现变更影响分析

### 新增模块需求

1. **impact_analyzer.py** - 变更影响分析器，分析大纲和设定修改的影响范围
2. **memory_aggregator.py** - 记忆聚合器，实现10章聚合和卷级聚合
3. **global_state_manager.py** - 全局状态管理器，维护全局角色状态表、道具流转表等
4. **unified_review_service.py** - 统一审批服务，管理所有类型的审批提案

### 数据库表依赖

1. **已有表**：Outline, Volume, Chapter, Synopsis, Character, Worldbuilding, ChapterMemory, EntityProposal, EntityRelation, EntityEvent, StoryEntity
2. **需新增表**：AggregatedMemory（聚合记忆）, GlobalState（全局状态快照）, ImpactReport（影响分析报告）

## Priority Classification

### P0 - 必须实现（第一阶段）

1. Requirement 1: 强制大纲确认门禁
2. Requirement 2: 统一文本编辑审批体验
3. Requirement 3: 全局 AI 智能体
4. Requirement 4: 统一审批流机制

**理由**：这四项是解决当前系统核心问题的关键，直接影响用户体验和系统可用性。

### P1 - 重要功能（第二阶段）

5. Requirement 5: 百万字长期记忆系统
6. Requirement 6: 大纲-设定-角色联动机制

**理由**：这两项是支持长篇创作的核心能力，需要在基础架构稳定后实施。

### P2 - 优化项（第三阶段）

7. Requirement 7: UI/UX 简化优化

**理由**：界面优化可以提升体验，但不影响核心功能，可以在功能完善后逐步优化。

## Implementation Phases

### Phase 1: 基础架构重构（4-6周）

**目标**：建立统一 AI 助手和审批流机制

**任务**：
1. 合并 ContentAI 和 SettingsAI 为统一 AI 助手
2. 实现全局上下文注入（访问所有文件）
3. 实现统一审批流机制
4. 实现大纲确认门禁
5. 实现统一的对比审批界面

**验收标准**：
- 所有页面使用同一个 AI 对话入口
- AI 能够访问和查询所有文件
- 所有 AI 生成内容进入统一审批流程
- 大纲未确认时后续功能被锁定

### Phase 2: 长期记忆系统（4-6周）

**目标**：实现三层记忆架构，支持百万字创作

**任务**：
1. 实现章节记忆自动抽取（已有，需优化）
2. 实现10章聚合记忆生成
3. 实现卷级聚合记忆生成
4. 实现全局状态表（角色、道具、事件、伏笔）
5. 实现记忆动态注入机制
6. 优化 AI 生成时的上下文构建

**验收标准**：
- 每10章自动生成聚合摘要
- 每卷结束自动生成卷级记忆
- 全局状态表实时更新
- AI 生成时能够访问相关记忆

### Phase 3: 联动机制和影响分析（3-4周）

**目标**：实现大纲-设定-角色联动和变更影响分析

**任务**：
1. 实现变更影响分析器
2. 实现大纲修改的影响检测
3. 实现角色设定修改的矛盾检测
4. 实现联动修改方案生成
5. 实现批量更新机制
6. 利用关系网进行跨实体分析

**验收标准**：
- 修改大纲时自动生成影响报告
- 修改角色时自动检测矛盾
- 用户确认后能够批量更新受影响内容
- 关系网能够支持影响分析查询

### Phase 4: UI/UX 优化（2-3周）

**目标**：简化界面，统一交互模式

**任务**：
1. 重构侧边栏结构
2. 移除冗余工具栏和功能
3. 统一所有模块的交互模式
4. 优化审批中心界面
5. 实现后端自动保存替代本地草稿

**验收标准**：
- 侧边栏结构清晰，按三个区域组织
- 所有模块使用一致的交互模式
- 审批中心支持筛选和批量操作
- 用户反馈界面更简洁易用

## Success Metrics

### 功能完整性指标

1. 所有 P0 需求 100% 实现
2. 所有 P1 需求 100% 实现
3. P2 需求至少 80% 实现

### 性能指标

1. AI 响应时间 < 10秒（95分位）
2. 影响分析响应时间 < 5秒
3. 审批列表加载时间 < 2秒
4. 支持至少 1000 章（约 300 万字）的小说创作

### 用户体验指标

1. 大纲到章节的创作流程清晰，无阻塞点
2. AI 对话能够理解全局上下文，回答准确率 > 85%
3. 审批流程高效，批量审批支持一次处理 > 10 项
4. 界面简洁，核心操作不超过 3 次点击

### 数据一致性指标

1. 大纲修改后，受影响内容的检测准确率 > 90%
2. 角色状态在全局状态表中的一致性 > 95%
3. 记忆抽取的准确率 > 85%（人工抽查）
4. 审批历史记录完整性 100%

## Risks and Mitigations

### 风险 1: AI 上下文 Token 超限

**描述**：百万字小说的全局上下文可能超过 AI 模型的 token 限制

**影响**：AI 无法访问完整上下文，生成质量下降

**缓解措施**：
1. 实现智能上下文裁剪，按优先级注入记忆
2. 使用聚合记忆替代原始章节内容
3. 实现分段查询机制，多次调用 AI 获取信息

### 风险 2: 影响分析性能问题

**描述**：大纲修改后扫描所有章节和设定可能耗时过长

**影响**：用户等待时间过长，体验下降

**缓解措施**：
1. 实现异步影响分析，后台执行
2. 使用索引和缓存优化查询性能
3. 实现增量分析，只检查变更相关的部分

### 风险 3: 数据迁移兼容性

**描述**：新增表和字段可能导致现有项目数据不兼容

**影响**：用户需要重新创建项目，数据丢失

**缓解措施**：
1. 实现数据迁移脚本，自动升级现有项目
2. 保留向后兼容性，新功能对旧数据降级处理
3. 提供数据备份和恢复机制

### 风险 4: AI 生成质量不稳定

**描述**：AI 生成的影响分析和联动建议可能不准确

**影响**：用户需要大量人工修正，降低效率

**缓解措施**：
1. 所有 AI 生成内容必须经过用户审批
2. 提供详细的生成依据和证据链
3. 实现用户反馈机制，持续优化 prompt
4. 提供手动修正和覆盖选项

## Appendix

### 参考文档

1. **AI写书平台编辑器优化分析文档.md** - 详细的系统问题分析和解决方案设计
2. **backend/app/services/assistant_service.py** - 现有 AI 助手服务实现
3. **backend/app/services/context_builder.py** - 现有上下文构建实现
4. **backend/app/services/entity_service.py** - 现有实体关系服务实现
5. **backend/app/services/review_service.py** - 现有审批服务实现

### 术语对照表

| 中文术语 | 英文术语 | 说明 |
|---------|---------|------|
| 大纲 | Outline | 小说总体框架 |
| 细纲 | Synopsis | 章节级别的剧情规划 |
| 章节 | Chapter | 正文内容 |
| 角色 | Character | 角色设定 |
| 世界观 | Worldbuilding | 世界观设定 |
| 审批 | Review | 用户确认 AI 生成内容的流程 |
| 提案 | Proposal | AI 生成的待审批内容 |
| 记忆 | Memory | 章节事实抽取结果 |
| 聚合 | Aggregation | 多章节记忆的汇总 |
| 实体 | Entity | 角色、道具、地点等可追踪对象 |
| 关系网 | Relation Network | 实体间的关系图谱 |
| 影响分析 | Impact Analysis | 分析修改对全书的影响范围 |
| 联动 | Linkage | 修改一处时自动更新相关内容 |

### 现有数据模型

#### 核心表

- **Outline**: 大纲表，存储小说总体框架
- **Volume**: 分卷表，存储卷级规划
- **Chapter**: 章节表，存储正文内容
- **Synopsis**: 细纲表，存储章节剧情规划
- **Character**: 角色表，存储角色设定
- **Worldbuilding**: 世界观表，存储世界观设定

#### 记忆和关系表

- **ChapterMemory**: 章节记忆表，存储章节事实抽取结果
- **StoryEntity**: 实体表，存储所有可追踪实体
- **EntityRelation**: 实体关系表，存储实体间的关系
- **EntityEvent**: 实体事件表，存储实体状态变化事件
- **EntityProposal**: 实体提案表，存储待审批的设定提案

#### 需新增表

- **AggregatedMemory**: 聚合记忆表，存储10章聚合和卷级聚合
- **GlobalState**: 全局状态表，存储全书级别的实体状态快照
- **ImpactReport**: 影响报告表，存储变更影响分析结果
