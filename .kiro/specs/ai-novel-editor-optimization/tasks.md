# Implementation Plan: AI 玄幻小说编辑器优化

## Overview

本实现计划将 AI 玄幻小说编辑器系统优化项目分解为可执行的编码任务。项目采用渐进式重构策略，分为4个阶段：基础架构重构、长期记忆系统、联动机制和影响分析、UI/UX 优化。

实现语言：**Python (Backend)** + **TypeScript/React (Frontend)**

## Tasks

### Phase 1: 基础架构重构（4-6周）

- [ ] 1. 数据库迁移和新表创建
  - [ ] 1.1 创建 Alembic 迁移脚本
    - 创建 `alembic/versions/001_add_new_tables.py`
    - 定义 `AggregatedMemory` 表结构
    - 定义 `GlobalState` 表结构
    - 定义 `ImpactReport` 表结构
    - 扩展 `Outline` 表（添加 `confirmed_at`, `confirmed_by` 字段）
    - 扩展 `EntityProposal` 表（添加 `proposal_category`, `priority` 字段）
    - 创建必要的索引
    - _Requirements: Technical Constraints - 数据库兼容性_
  
  - [ ] 1.2 创建数据模型类
    - 在 `backend/app/models/` 中创建 `aggregated_memory.py`
    - 在 `backend/app/models/` 中创建 `global_state.py`
    - 在 `backend/app/models/` 中创建 `impact_report.py`
    - 更新 `backend/app/models/__init__.py` 导入新模型
    - _Requirements: Technical Constraints - 数据库兼容性_
  
  - [ ] 1.3 执行数据库迁移
    - 运行 `alembic upgrade head` 应用迁移
    - 验证所有表和字段创建成功
    - 创建数据迁移脚本 `scripts/migrate_existing_data.py`
    - _Requirements: Technical Constraints - 兼容性约束_

- [ ] 2. 统一 AI 助手服务实现
  - [ ] 2.1 重构 `assistant_service.py` 为统一 AI 助手
    - 合并 ContentAI 和 SettingsAI 的功能
    - 实现 `chat()` 方法，支持全局上下文访问
    - 实现 `analyze_impact()` 方法，调用影响分析器
    - 添加智能文件选择逻辑
    - _Requirements: Requirement 3 - 全局 AI 智能体_
  
  - [ ] 2.2 增强 `context_builder.py` 上下文构建能力
    - 实现 `build_unified_context()` 方法
    - 实现 `build_file_catalog()` 方法，构建全局文件索引
    - 实现 `select_context_files()` 方法，智能选择相关文件
    - 实现 `build_relation_context()` 方法，注入关系网数据
    - _Requirements: Requirement 3 - 全局 AI 智能体_
  
  - [ ] 2.3 创建统一 AI 助手 API 端点
    - 在 `backend/app/routers/` 中创建或更新 `assistant.py`
    - 实现 `POST /api/assistant/chat` 端点
    - 实现请求验证和错误处理
    - 集成 `UnifiedAssistantService`
    - _Requirements: Requirement 3 - 全局 AI 智能体_

- [ ] 3. 统一审批流机制实现
  - [ ] 3.1 扩展 `review_service.py` 为统一审批服务
    - 实现 `create_proposal()` 方法，支持所有提案类型
    - 实现 `list_pending_proposals()` 方法，支持筛选
    - 实现 `approve_proposal()` 方法，根据类型调用对应的 apply 函数
    - 实现 `reject_proposal()` 方法
    - 实现 `batch_approve()` 方法，支持批量审批
    - _Requirements: Requirement 4 - 统一审批流机制_
  
  - [ ] 3.2 创建审批流 API 端点
    - 实现 `GET /api/review/proposals` 端点（列出提案）
    - 实现 `POST /api/review/proposals/{id}/approve` 端点
    - 实现 `POST /api/review/proposals/{id}/reject` 端点
    - 实现 `POST /api/review/proposals/batch-approve` 端点
    - 添加请求验证和权限检查
    - _Requirements: Requirement 4 - 统一审批流机制_

- [ ] 4. 大纲确认门禁实现
  - [ ] 4.1 创建门禁控制器服务
    - 创建 `backend/app/services/gate_keeper.py`
    - 实现 `check_outline_confirmed()` 方法
    - 实现 `check_access()` 方法，检查模块访问权限
    - 实现 `unlock_all_modules()` 方法
    - _Requirements: Requirement 1 - 强制大纲确认门禁_
  
  - [ ] 4.2 创建门禁 API 端点
    - 在 `backend/app/routers/` 中创建 `gate.py`
    - 实现 `GET /api/gate/check` 端点
    - 实现 `POST /api/gate/unlock` 端点
    - _Requirements: Requirement 1 - 强制大纲确认门禁_
  
  - [ ] 4.3 实现大纲确认逻辑
    - 在 `backend/app/routers/outline.py` 中添加确认端点
    - 实现 `POST /api/outline/{id}/confirm` 端点
    - 更新 `Outline` 表的 `confirmed_at` 和 `confirmed_by` 字段
    - 调用 `GateKeeper.unlock_all_modules()`
    - _Requirements: Requirement 1 - 强制大纲确认门禁_

- [ ] 5. 统一对比审批界面实现
  - [ ] 5.1 创建对比 API 端点
    - 在 `backend/app/routers/` 中创建 `compare.py`
    - 实现 `GET /api/compare/{entity_type}/{entity_id}` 端点
    - 实现 `POST /api/compare/{entity_type}/{entity_id}/accept` 端点
    - 实现 `POST /api/compare/{entity_type}/{entity_id}/reject` 端点
    - 实现 `POST /api/compare/{entity_type}/{entity_id}/continue` 端点
    - 实现文本 diff 算法
    - _Requirements: Requirement 2 - 统一文本编辑审批体验_
  
  - [ ] 5.2 创建前端对比审批组件
    - 创建 `frontend/src/components/ComparisonReviewView.tsx`
    - 实现左右对比视图布局
    - 集成 `react-diff-viewer` 或自定义 diff 展示
    - 实现接受/拒绝/继续修改按钮
    - 实现继续修改对话框
    - _Requirements: Requirement 2 - 统一文本编辑审批体验_

- [ ] 6. Checkpoint - 基础架构验证
  - 验证所有新表创建成功
  - 验证统一 AI 助手能够访问所有文件
  - 验证审批流能够处理不同类型的提案
  - 验证大纲确认门禁正常工作
  - 验证对比审批界面正常显示
  - 运行单元测试确保核心功能正常
  - Ensure all tests pass, ask the user if questions arise.

### Phase 2: 长期记忆系统（4-6周）

- [ ] 7. 记忆聚合器实现
  - [ ] 7.1 创建记忆聚合器服务
    - 创建 `backend/app/services/memory_aggregator.py`
    - 实现 `aggregate_10_chapters()` 方法
    - 实现 `aggregate_volume()` 方法
    - 实现 `get_memory_context_for_chapter()` 方法
    - 实现事件去重算法 `deduplicate_events()`
    - 实现状态合并逻辑
    - _Requirements: Requirement 5 - 百万字长期记忆系统_
  
  - [ ] 7.2 实现聚合触发机制
    - 在章节定稿流程中添加聚合触发逻辑
    - 每10章定稿后自动调用 `aggregate_10_chapters()`
    - 每卷完成后自动调用 `aggregate_volume()`
    - 添加异步任务队列（可选，使用 Celery 或 FastAPI BackgroundTasks）
    - _Requirements: Requirement 5 - 百万字长期记忆系统_
  
  - [ ] 7.3 创建记忆 API 端点
    - 在 `backend/app/routers/` 中创建 `memory.py`
    - 实现 `GET /api/memory/aggregated` 端点
    - 实现 `POST /api/memory/aggregate` 端点（手动触发）
    - 实现 `GET /api/memory/global-state` 端点
    - _Requirements: Requirement 5 - 百万字长期记忆系统_

- [ ] 8. 全局状态管理器实现
  - [ ] 8.1 创建全局状态管理器服务
    - 创建 `backend/app/services/global_state_service.py`
    - 实现 `update_character_state()` 方法
    - 实现 `track_item_transfer()` 方法
    - 实现 `add_event_to_timeline()` 方法
    - 实现 `track_foreshadowing()` 方法
    - 实现 `get_global_snapshot()` 方法
    - _Requirements: Requirement 5 - 百万字长期记忆系统_
  
  - [ ] 8.2 集成全局状态更新到章节定稿流程
    - 在章节定稿时自动更新全局状态
    - 从 `ChapterMemory` 中提取状态变化
    - 调用 `GlobalStateManager` 更新角色状态、道具流转、事件时间线
    - 创建全局状态快照
    - _Requirements: Requirement 5 - 百万字长期记忆系统_

- [ ] 9. 优化上下文构建和注入
  - [ ] 9.1 实现动态上下文注入策略
    - 在 `context_builder.py` 中实现 `build_context_for_chapter()` 方法
    - 实现优先级注入逻辑（细纲 > 前1-3章记忆 > 角色状态 > 10章聚合 > 卷级记忆 > 全局时间线）
    - 实现 token 预算管理（8000 tokens）
    - 实现 token 估算函数 `estimate_tokens()`
    - _Requirements: Requirement 5 - 百万字长期记忆系统_
  
  - [ ] 9.2 集成记忆上下文到 AI 生成流程
    - 更新 `assistant_service.py` 的 `chat()` 方法，注入记忆上下文
    - 更新章节生成流程，使用 `get_memory_context_for_chapter()`
    - 更新细纲生成流程，注入相关记忆
    - _Requirements: Requirement 5 - 百万字长期记忆系统_

- [ ] 10. Checkpoint - 记忆系统验证
  - 创建测试小说，生成至少30章内容
  - 验证每10章自动生成聚合记忆
  - 验证卷级聚合记忆生成
  - 验证全局状态表正确更新
  - 验证 AI 生成时能够访问记忆上下文
  - 验证 token 预算管理正常工作
  - Ensure all tests pass, ask the user if questions arise.

### Phase 3: 联动机制和影响分析（3-4周）

- [ ] 11. 变更影响分析器实现
  - [ ] 11.1 创建影响分析器服务
    - 创建 `backend/app/services/impact_analyzer.py`
    - 实现 `analyze_outline_change()` 方法
    - 实现 `analyze_character_change()` 方法
    - 实现 `generate_linkage_proposals()` 方法
    - 实现文本相似度计算函数 `compute_text_similarity()`
    - 实现字段差异检测函数 `compute_field_diff()`
    - _Requirements: Requirement 6 - 大纲-设定-角色联动机制_
  
  - [ ] 11.2 实现大纲修改影响检测
    - 实现扫描所有 Volume 的逻辑
    - 实现扫描所有 Synopsis 的逻辑
    - 实现扫描所有 Character 的逻辑
    - 使用 AI 检测矛盾
    - 生成影响评估报告
    - _Requirements: Requirement 6 - 大纲-设定-角色联动机制_
  
  - [ ] 11.3 实现角色设定修改影响检测
    - 实现状态变化识别逻辑
    - 查询关系网获取关联实体
    - 扫描未定稿章节检测矛盾
    - 生成矛盾警告清单
    - _Requirements: Requirement 6 - 大纲-设定-角色联动机制_

- [ ] 12. 影响分析 API 和集成
  - [ ] 12.1 创建影响分析 API 端点
    - 在 `backend/app/routers/` 中创建 `impact.py`
    - 实现 `POST /api/impact/analyze` 端点
    - 实现 `GET /api/impact/reports/{novel_id}` 端点
    - 添加异步处理支持（影响分析可能耗时较长）
    - _Requirements: Requirement 6 - 大纲-设定-角色联动机制_
  
  - [ ] 12.2 集成影响分析到大纲修改流程
    - 在大纲保存时自动触发影响分析
    - 在 `UnifiedAssistantService.chat()` 中检测大纲修改意图
    - 自动调用 `ImpactAnalyzer.analyze_outline_change()`
    - 返回影响报告给前端
    - _Requirements: Requirement 6 - 大纲-设定-角色联动机制_
  
  - [ ] 12.3 集成影响分析到角色修改流程
    - 在角色设定保存时自动触发影响分析
    - 调用 `ImpactAnalyzer.analyze_character_change()`
    - 生成矛盾警告并提交审批
    - _Requirements: Requirement 6 - 大纲-设定-角色联动机制_

- [ ] 13. 联动修改方案生成和执行
  - [ ] 13.1 实现联动修改方案生成
    - 在 `ImpactAnalyzer` 中实现 `generate_linkage_proposals()` 方法
    - 为每个受影响的实体生成修改建议
    - 使用 AI 生成修改预览
    - 创建 `EntityProposal` 记录，标记为 `linkage` 类型
    - _Requirements: Requirement 6 - 大纲-设定-角色联动机制_
  
  - [ ] 13.2 实现批量联动修改执行
    - 在 `UnifiedReviewService` 中实现批量更新逻辑
    - 支持用户选择性批准联动修改
    - 使用事务保证原子性
    - 记录修改历史
    - _Requirements: Requirement 6 - 大纲-设定-角色联动机制_

- [ ] 14. 前端影响分析界面实现
  - [ ] 14.1 创建影响报告展示组件
    - 创建 `frontend/src/components/ImpactReportCard.tsx`
    - 创建 `frontend/src/components/ImpactReportDetail.tsx`
    - 展示受影响的分卷、章节、角色列表
    - 展示矛盾检测结果
    - 展示联动修改建议
    - _Requirements: Requirement 6 - 大纲-设定-角色联动机制_
  
  - [ ] 14.2 集成影响报告到统一 AI 助手
    - 在 `UnifiedAssistantUI` 中展示影响报告卡片
    - 实现"查看详情"跳转
    - 实现快速批准/拒绝联动修改
    - _Requirements: Requirement 6 - 大纲-设定-角色联动机制_

- [ ] 15. Checkpoint - 联动机制验证
  - 修改测试小说的大纲，验证影响分析报告生成
  - 验证受影响的分卷、章节、角色被正确识别
  - 验证联动修改建议生成
  - 验证批量联动修改执行成功
  - 修改角色设定，验证矛盾检测
  - Ensure all tests pass, ask the user if questions arise.

### Phase 4: UI/UX 优化（2-3周）

- [ ] 16. 前端统一 AI 助手 UI 实现
  - [ ] 16.1 创建统一 AI 助手组件
    - 创建 `frontend/src/components/UnifiedAssistantUI.tsx`
    - 实现对话历史展示
    - 实现上下文文件选择器
    - 实现消息输入和发送
    - 实现快捷操作按钮
    - _Requirements: Requirement 3 - 全局 AI 智能体_
  
  - [ ] 16.2 集成统一 AI 助手到各个页面
    - 在大纲页面集成 `UnifiedAssistantUI`
    - 在角色管理页面集成 `UnifiedAssistantUI`
    - 在世界观页面集成 `UnifiedAssistantUI`
    - 在章节编辑页面集成 `UnifiedAssistantUI`
    - 根据 `contextType` 动态调整 AI 助手能力
    - _Requirements: Requirement 3 - 全局 AI 智能体_
  
  - [ ] 16.3 移除旧的 ContentAI 和 SettingsAI 组件
    - 删除或重构旧的 AI 对话组件
    - 更新所有引用旧组件的页面
    - 清理冗余代码
    - _Requirements: Requirement 7 - UI/UX 简化优化_

- [ ] 17. 审批中心界面实现
  - [ ] 17.1 创建审批中心组件
    - 创建 `frontend/src/pages/ReviewCenter.tsx`
    - 实现提案列表展示
    - 实现筛选功能（状态、类型、分类）
    - 实现批量选择和批量审批
    - 实现单个提案审批操作
    - _Requirements: Requirement 4 - 统一审批流机制_
  
  - [ ] 17.2 添加审批中心路由和导航
    - 在路由配置中添加审批中心页面
    - 在侧边栏或顶部导航添加审批中心入口
    - 显示待审批数量徽章
    - _Requirements: Requirement 4 - 统一审批流机制_

- [ ] 18. 门禁提示组件实现
  - [ ] 18.1 创建门禁提示组件
    - 创建 `frontend/src/components/GatePrompt.tsx`
    - 实现锁定状态遮罩层
    - 实现提示信息展示
    - 实现"前往大纲页面"按钮
    - _Requirements: Requirement 1 - 强制大纲确认门禁_
  
  - [ ] 18.2 集成门禁提示到受保护页面
    - 在角色管理页面添加 `GatePrompt`
    - 在世界观页面添加 `GatePrompt`
    - 在分卷页面添加 `GatePrompt`
    - 在章节页面添加 `GatePrompt`
    - _Requirements: Requirement 1 - 强制大纲确认门禁_

- [ ] 19. 侧边栏和导航优化
  - [ ] 19.1 重构侧边栏结构
    - 按"作品结构"、"通用设定"、"正文"三个区域组织
    - 移除冗余的工具栏和功能
    - 在正文列表中按卷折叠显示章节
    - 统一所有模块的交互模式
    - _Requirements: Requirement 7 - UI/UX 简化优化_
  
  - [ ] 19.2 优化页面布局和样式
    - 统一所有页面的操作按钮位置和样式
    - 简化设定页面的工具栏
    - 优化对比审批视图的布局
    - 优化审批中心的筛选和列表展示
    - _Requirements: Requirement 7 - UI/UX 简化优化_

- [ ] 20. 后端自动保存和版本历史
  - [ ] 20.1 实现后端自动保存机制
    - 在各个编辑 API 中添加自动保存逻辑
    - 实现版本历史记录
    - 移除前端 `documentDrafts` 本地草稿逻辑
    - _Requirements: Requirement 7 - UI/UX 简化优化_
  
  - [ ] 20.2 创建版本历史 API 端点
    - 实现 `GET /api/{entity_type}/{entity_id}/versions` 端点
    - 实现 `POST /api/{entity_type}/{entity_id}/restore` 端点（恢复历史版本）
    - _Requirements: Requirement 7 - UI/UX 简化优化_

- [ ] 21. Final Checkpoint - 完整系统验证
  - 创建新小说项目，完整走通创作流程
  - 验证大纲确认门禁正常工作
  - 验证统一 AI 助手在各个页面正常工作
  - 验证审批中心能够管理所有类型的提案
  - 验证对比审批界面在各个模块正常工作
  - 验证记忆系统在长篇创作中正常工作
  - 验证影响分析和联动修改正常工作
  - 验证 UI/UX 优化后的界面简洁易用
  - 运行完整的集成测试套件
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- 所有任务都是必须实现的核心功能，没有标记为可选
- 每个任务都明确引用了对应的需求条款，确保需求覆盖
- Checkpoint 任务用于阶段性验证，确保增量开发的质量
- 实现过程中应保持向后兼容性，不破坏现有功能
- 所有数据库操作应使用事务保证原子性
- 所有 API 端点应包含适当的错误处理和验证
- 前端组件应遵循 React 和 Ant Design 的最佳实践
- 后端服务应遵循 FastAPI 和 SQLAlchemy 的最佳实践
