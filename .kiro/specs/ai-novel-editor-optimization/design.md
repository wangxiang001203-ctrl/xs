# AI 玄幻小说编辑器优化 - 设计文档

## Overview

本设计文档定义 AI 玄幻小说编辑器系统优化项目的技术架构和实现方案。该项目旨在通过系统性重构解决当前系统存在的核心问题：

1. **流程阻塞**：多层状态机互相锁死，大纲未确认时后续功能无法使用
2. **AI 能力分散**：ContentAI 和 SettingsAI 各自独立，无法访问全局上下文
3. **缺少长期记忆**：百万字级别创作时 AI 无法记住前面章节的关键信息
4. **联动机制缺失**：修改大纲或设定时无法自动检测影响范围和矛盾
5. **审批流程混乱**：不同类型的 AI 生成内容使用不同的审批方式

本设计基于现有代码库（FastAPI + SQLAlchemy + MySQL + React + Ant Design），采用渐进式重构策略，确保向后兼容性和平滑迁移。

### 核心设计目标

- **统一 AI 助手**：合并 ContentAI 和 SettingsAI，实现全局上下文访问和智能影响分析
- **三层记忆架构**：章节记忆（L0）→ 聚合记忆（L1）→ 全局状态（L2），支持百万字创作
- **变更影响分析**：自动检测大纲/设定修改的影响范围，生成联动修改方案
- **统一审批流**：所有 AI 生成内容进入统一的提案审批机制
- **大纲确认门禁**：前后端权限控制，确保创作流程清晰
- **统一文本编辑审批**：左右对比视图，一致的交互体验

## Architecture

### 系统架构图

```mermaid
graph TB
    subgraph "前端层 Frontend"
        UI[统一 AI 助手 UI]
        OutlineUI[大纲编辑器]
        CharacterUI[角色管理]
        WorldUI[世界观管理]
        ChapterUI[章节编辑器]
        ReviewUI[审批中心]
        CompareUI[对比审批视图]
    end

    subgraph "API 层 API Gateway"
        AssistantAPI[/api/assistant/chat]
        ImpactAPI[/api/impact/analyze]
        ReviewAPI[/api/review/*]
        MemoryAPI[/api/memory/*]
        GateAPI[/api/gate/check]
    end

    subgraph "核心服务层 Core Services"
        UnifiedAssistant[统一 AI 助手服务<br/>assistant_service.py]
        ImpactAnalyzer[变更影响分析器<br/>impact_analyzer.py]
        MemoryAggregator[记忆聚合器<br/>memory_aggregator.py]
        GlobalStateManager[全局状态管理器<br/>global_state_service.py]
        UnifiedReview[统一审批服务<br/>review_service.py]
        GateKeeper[门禁控制器<br/>gate_keeper.py]
    end

    subgraph "基础服务层 Foundation Services"
        ContextBuilder[上下文构建器<br/>context_builder.py]
        EntityService[实体关系服务<br/>entity_service.py]
        AIService[AI 调用服务<br/>ai_service.py]
        FileService[文件服务<br/>file_service.py]
    end

    subgraph "数据层 Data Layer"
        DB[(MySQL Database)]
        FileStorage[文件存储<br/>storage/projects/]
    end

    UI --> AssistantAPI
    OutlineUI --> ImpactAPI
    ReviewUI --> ReviewAPI
    ChapterUI --> MemoryAPI
    UI --> GateAPI

    AssistantAPI --> UnifiedAssistant
    ImpactAPI --> ImpactAnalyzer
    ReviewAPI --> UnifiedReview
    MemoryAPI --> MemoryAggregator
    GateAPI --> GateKeeper

    UnifiedAssistant --> ContextBuilder
    UnifiedAssistant --> EntityService
    ImpactAnalyzer --> EntityService
    MemoryAggregator --> GlobalStateManager
    UnifiedReview --> EntityService

    ContextBuilder --> DB
    EntityService --> DB
    GlobalStateManager --> DB
    UnifiedReview --> DB
    GateKeeper --> DB

    ContextBuilder --> FileStorage
    UnifiedReview --> FileStorage


## Components and Interfaces

### 1. 统一 AI 助手服务 (UnifiedAssistant)

**职责**：提供全局智能对话能力，访问所有文件，执行影响分析

**核心接口**：

```python
class UnifiedAssistantService:
    def chat(
        self,
        db: Session,
        novel_id: str,
        context_type: str,  # outline/characters/worldbuilding/chapter
        context_id: str | None,
        user_message: str,
        selected_file_ids: list[str] | None,
        conversation_history: list[dict],
    ) -> dict:
        """
        统一 AI 对话接口
        
        Returns:
            {
                "response": str,  # AI 回复
                "context_files": list[dict],  # 自动检索到的参考文件
                "suggestions": list[dict] | None,  # 联动修改建议
                "impact_report": dict | None,  # 影响分析报告
            }
        """
        pass
    
    def analyze_impact(
        self,
        db: Session,
        novel_id: str,
        change_type: str,  # outline/character/worldbuilding
        change_id: str,
        old_content: str,
        new_content: str,
    ) -> dict:
        """
        变更影响分析
        
        Returns:
            {
                "affected_volumes": list[dict],
                "affected_chapters": list[dict],
                "affected_characters": list[dict],
                "conflicts": list[dict],
                "suggestions": list[dict],
            }
        """
        pass


**实现要点**：

- 合并现有的 `assistant_service.py` 和 `context_builder.py`
- 使用 `build_file_catalog()` 构建全局文件索引
- 使用 `select_context_files()` 智能选择相关文件
- 使用 `build_relation_context()` 注入关系网数据
- 调用 `ImpactAnalyzer` 执行影响分析

**依赖服务**：
- `ContextBuilder`: 上下文构建
- `EntityService`: 实体关系查询
- `ImpactAnalyzer`: 影响分析
- `AIService`: 模型调用

### 2. 变更影响分析器 (ImpactAnalyzer)

**职责**：分析大纲/设定修改的影响范围，生成联动修改方案

**核心接口**：

```python
class ImpactAnalyzer:
    def analyze_outline_change(
        self,
        db: Session,
        novel_id: str,
        old_outline: Outline,
        new_outline: Outline,
    ) -> ImpactReport:
        """
        分析大纲修改的影响
        
        检测逻辑：
        1. 对比 old_outline 和 new_outline 的字段差异
        2. 扫描所有 Volume，检测引用了变更内容的部分
        3. 扫描所有 Synopsis，检测与新大纲的矛盾
        4. 扫描所有 Character，检测与新大纲的矛盾
        5. 生成影响评估报告
        """
        pass
    
    def analyze_character_change(
        self,
        db: Session,
        novel_id: str,
        character: Character,
        old_state: dict,
        new_state: dict,
    ) -> ImpactReport:
        """
        分析角色设定修改的影响
        
        检测逻辑：
        1. 对比角色状态变化（境界、势力、状态等）
        2. 扫描所有未定稿章节，检测矛盾
        3. 查询关系网，检测关联实体
        4. 生成矛盾警告清单
        """
        pass
    
    def generate_linkage_proposals(
        self,
        db: Session,
        impact_report: ImpactReport,
    ) -> list[LinkageProposal]:
        """
        生成联动修改方案
        
        Returns:
            [
                {
                    "target_type": "volume/synopsis/character",
                    "target_id": str,
                    "action": "update/regenerate",
                    "reason": str,
                    "preview": str,
                }
            ]
        """
        pass


**实现要点**：

- 使用文本相似度算法检测内容变化
- 使用 `EntityService` 查询关系网
- 使用 AI 生成矛盾检测和修改建议
- 结果存储到 `ImpactReport` 表

**依赖服务**：
- `EntityService`: 关系网查询
- `AIService`: AI 推理
- `ContextBuilder`: 上下文构建

### 3. 记忆聚合器 (MemoryAggregator)

**职责**：实现10章聚合和卷级聚合，生成聚合记忆摘要

**核心接口**：

```python
class MemoryAggregator:
    def aggregate_10_chapters(
        self,
        db: Session,
        novel_id: str,
        start_chapter: int,
        end_chapter: int,
    ) -> AggregatedMemory:
        """
        生成10章聚合记忆
        
        聚合逻辑：
        1. 读取 start_chapter 到 end_chapter 的所有 ChapterMemory
        2. 合并 key_events，去重并按时间排序
        3. 合并 state_changes，保留最新状态
        4. 合并 inventory_changes，追踪道具流转
        5. 合并 open_threads，标记已回收和未回收
        6. 调用 AI 生成摘要
        """
        pass
    
    def aggregate_volume(
        self,
        db: Session,
        volume: Volume,
    ) -> AggregatedMemory:
        """
        生成卷级聚合记忆
        
        聚合逻辑：
        1. 读取本卷所有章节的 ChapterMemory
        2. 读取本卷范围内的10章聚合记忆
        3. 合并关键事件和状态变化
        4. 调用 AI 生成卷级摘要
        """
        pass
    
    def get_memory_context_for_chapter(
        self,
        db: Session,
        novel_id: str,
        chapter_number: int,
    ) -> str:
        """
        为指定章节构建记忆上下文
        
        注入优先级：
        1. 本章细纲（必读）
        2. 前1-3章记忆
        3. 角色当前状态
        4. 最近的10章聚合快照
        5. 本卷聚合记忆
        6. 全局事件时间线
        
        Token 预算：8000 tokens
        """
        pass


**实现要点**：

- 聚合触发时机：每10章定稿后自动触发，每卷完成后自动触发
- 使用 AI 生成摘要，保持简洁（每10章约500字，每卷约1000字）
- 存储到 `AggregatedMemory` 表
- 动态注入时按优先级裁剪，确保不超过 token 预算

**依赖服务**：
- `AIService`: AI 摘要生成
- `GlobalStateManager`: 全局状态查询

### 4. 全局状态管理器 (GlobalStateManager)

**职责**：维护全局角色状态表、道具流转表、事件时间线、伏笔追踪表

**核心接口**：

```python
class GlobalStateManager:
    def update_character_state(
        self,
        db: Session,
        character: Character,
        chapter_number: int,
        state_changes: dict,
    ):
        """
        更新角色全局状态
        
        更新逻辑：
        1. 创建 EntityEvent 记录状态变化
        2. 更新 StoryEntity.current_state
        3. 更新 Character 表的对应字段
        4. 创建 GlobalState 快照
        """
        pass
    
    def track_item_transfer(
        self,
        db: Session,
        novel_id: str,
        item_name: str,
        from_owner: str | None,
        to_owner: str,
        chapter_number: int,
    ):
        """
        追踪道具流转
        
        记录逻辑：
        1. 创建 EntityEvent 记录流转事件
        2. 更新道具实体的 current_state.owner
        3. 更新 GlobalState 快照
        """
        pass
    
    def add_event_to_timeline(
        self,
        db: Session,
        novel_id: str,
        chapter_number: int,
        event_text: str,
        event_type: str,
    ):
        """
        添加事件到全局时间线
        
        记录逻辑：
        1. 创建 EntityEvent 记录
        2. 更新 GlobalState 快照
        """
        pass
    
    def track_foreshadowing(
        self,
        db: Session,
        novel_id: str,
        foreshadowing_text: str,
        planted_chapter: int,
        resolved_chapter: int | None,
    ):
        """
        追踪伏笔
        
        记录逻辑：
        1. 创建 EntityEvent 记录伏笔
        2. 如果 resolved_chapter 不为空，标记为已回收
        3. 更新 GlobalState 快照
        """
        pass
    
    def get_global_snapshot(
        self,
        db: Session,
        novel_id: str,
        chapter_number: int | None = None,
    ) -> GlobalState:
        """
        获取全局状态快照
        
        如果 chapter_number 为空，返回最新状态
        否则返回指定章节时的状态
        """
        pass


**实现要点**：

- 使用 `EntityEvent` 表记录所有状态变化
- 使用 `GlobalState` 表存储快照
- 快照生成时机：每章定稿后、每10章聚合后、每卷完成后
- 支持时间旅行查询（查询指定章节时的状态）

**依赖服务**：
- `EntityService`: 实体管理

### 5. 统一审批服务 (UnifiedReviewService)

**职责**：管理所有类型的审批提案，提供统一的审批流程

**核心接口**：

```python
class UnifiedReviewService:
    def create_proposal(
        self,
        db: Session,
        novel_id: str,
        proposal_type: str,  # outline/character/worldbuilding/chapter/entity_event/entity_relation
        action: str,  # create/update/delete
        target_id: str | None,
        payload: dict,
        reason: str,
    ) -> EntityProposal:
        """
        创建审批提案
        """
        pass
    
    def list_pending_proposals(
        self,
        db: Session,
        novel_id: str,
        filters: dict | None = None,
    ) -> list[EntityProposal]:
        """
        列出待审批提案
        
        支持筛选：
        - proposal_type: 提案类型
        - chapter_id: 章节ID
        - volume_id: 分卷ID
        - created_after: 创建时间
        """
        pass
    
    def approve_proposal(
        self,
        db: Session,
        proposal: EntityProposal,
    ):
        """
        批准提案
        
        执行逻辑：
        1. 根据 proposal_type 调用对应的 apply 函数
        2. 更新 proposal.status = "approved"
        3. 记录 resolved_at
        4. 触发后续联动（如扫描章节提及、更新关系网等）
        """
        pass
    
    def reject_proposal(
        self,
        db: Session,
        proposal: EntityProposal,
        reason: str,
    ):
        """
        拒绝提案
        
        执行逻辑：
        1. 更新 proposal.status = "rejected"
        2. 记录 reason 和 resolved_at
        """
        pass
    
    def batch_approve(
        self,
        db: Session,
        proposal_ids: list[str],
    ) -> dict:
        """
        批量批准提案
        
        Returns:
            {
                "success": int,
                "failed": int,
                "errors": list[dict],
            }
        """
        pass


**实现要点**：

- 扩展现有的 `review_service.py`
- 使用 `EntityProposal` 表统一存储所有提案
- 提案类型通过 `entity_type` 和 `action` 字段区分
- 批准时调用对应的 `apply_proposal()` 函数
- 支持批量操作，事务保证原子性

**依赖服务**：
- `EntityService`: 实体管理
- `FileService`: 文件保存

### 6. 门禁控制器 (GateKeeper)

**职责**：实现大纲确认门禁，控制后续功能的访问权限

**核心接口**：

```python
class GateKeeper:
    def check_outline_confirmed(
        self,
        db: Session,
        novel_id: str,
    ) -> bool:
        """
        检查大纲是否已确认
        """
        pass
    
    def check_access(
        self,
        db: Session,
        novel_id: str,
        module: str,  # characters/worldbuilding/volumes/chapters
    ) -> dict:
        """
        检查模块访问权限
        
        Returns:
            {
                "allowed": bool,
                "reason": str | None,
                "required_steps": list[str] | None,
            }
        """
        pass
    
    def unlock_all_modules(
        self,
        db: Session,
        novel_id: str,
    ):
        """
        解锁所有模块（大纲确认后调用）
        """
        pass


**实现要点**：

- 前端调用 `/api/gate/check` 检查权限
- 后端中间件拦截未授权请求
- 大纲确认时自动解锁所有模块
- 界面上显示锁定状态和解锁提示

## Data Models

### 新增表

#### 1. AggregatedMemory（聚合记忆表）

```python
class AggregatedMemory(Base):
    __tablename__ = "aggregated_memories"
    __table_args__ = {"comment": "聚合记忆表"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    novel_id: Mapped[str] = mapped_column(String(36), ForeignKey("novels.id", ondelete="CASCADE"))
    aggregation_type: Mapped[str] = mapped_column(String(20), comment="聚合类型：10章/卷级")
    start_chapter: Mapped[int] = mapped_column(Integer, comment="起始章节号")
    end_chapter: Mapped[int] = mapped_column(Integer, comment="结束章节号")
    volume_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("volumes.id", ondelete="SET NULL"))
    
    summary: Mapped[str] = mapped_column(Text, comment="聚合摘要")
    key_events: Mapped[list] = mapped_column(JSON, default=list, comment="关键事件列表")
    state_snapshot: Mapped[dict] = mapped_column(JSON, default=dict, comment="状态快照")
    item_transfers: Mapped[list] = mapped_column(JSON, default=list, comment="道具流转记录")
    open_threads: Mapped[list] = mapped_column(JSON, default=list, comment="未回收伏笔")
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
```

**字段说明**：
- `aggregation_type`: "10_chapters" 或 "volume"
- `start_chapter` / `end_chapter`: 聚合范围
- `summary`: AI 生成的摘要（500-1000字）
- `key_events`: 合并后的关键事件列表
- `state_snapshot`: 角色、道具等的状态快照
- `item_transfers`: 道具流转记录
- `open_threads`: 未回收的伏笔和悬念

#### 2. GlobalState（全局状态快照表）

```python
class GlobalState(Base):
    __tablename__ = "global_states"
    __table_args__ = {"comment": "全局状态快照表"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    novel_id: Mapped[str] = mapped_column(String(36), ForeignKey("novels.id", ondelete="CASCADE"))
    snapshot_type: Mapped[str] = mapped_column(String(20), comment="快照类型：章节/10章/卷")
    chapter_number: Mapped[int | None] = mapped_column(Integer, comment="快照时的章节号")
    volume_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("volumes.id", ondelete="SET NULL"))
    
    character_states: Mapped[dict] = mapped_column(JSON, default=dict, comment="角色状态表")
    item_ownership: Mapped[dict] = mapped_column(JSON, default=dict, comment="道具归属表")
    event_timeline: Mapped[list] = mapped_column(JSON, default=list, comment="事件时间线")
    foreshadowing_tracker: Mapped[list] = mapped_column(JSON, default=list, comment="伏笔追踪表")
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
```

**字段说明**：
- `snapshot_type`: "chapter" / "10_chapters" / "volume"
- `character_states`: `{角色名: {境界, 位置, 状态, ...}}`
- `item_ownership`: `{道具名: {当前持有者, 历史归属}}`
- `event_timeline`: `[{章节号, 事件描述, 时间戳}]`
- `foreshadowing_tracker`: `[{伏笔内容, 埋下章节, 回收章节, 状态}]`

#### 3. ImpactReport（影响分析报告表）

```python
class ImpactReport(Base):
    __tablename__ = "impact_reports"
    __table_args__ = {"comment": "变更影响分析报告表"}

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=gen_uuid)
    novel_id: Mapped[str] = mapped_column(String(36), ForeignKey("novels.id", ondelete="CASCADE"))
    change_type: Mapped[str] = mapped_column(String(20), comment="变更类型：outline/character/worldbuilding")
    change_target_id: Mapped[str] = mapped_column(String(36), comment="变更目标ID")
    
    affected_volumes: Mapped[list] = mapped_column(JSON, default=list, comment="受影响的分卷")
    affected_chapters: Mapped[list] = mapped_column(JSON, default=list, comment="受影响的章节")
    affected_characters: Mapped[list] = mapped_column(JSON, default=list, comment="受影响的角色")
    conflicts: Mapped[list] = mapped_column(JSON, default=list, comment="检测到的矛盾")
    suggestions: Mapped[list] = mapped_column(JSON, default=list, comment="联动修改建议")
    
    status: Mapped[str] = mapped_column(String(20), default="pending", comment="处理状态")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, comment="处理完成时间")
```

**字段说明**：
- `change_type`: 变更类型
- `affected_*`: 受影响的实体列表，每项包含 `{id, name, reason, severity}`
- `conflicts`: 检测到的矛盾，每项包含 `{type, description, location}`
- `suggestions`: 联动修改建议，每项包含 `{target_type, target_id, action, preview}`
- `status`: "pending" / "approved" / "rejected"

### 扩展现有表

#### 1. Outline 表扩展

```python
# 新增字段
confirmed_at: Mapped[datetime | None] = mapped_column(DateTime, comment="确认时间")
confirmed_by: Mapped[str | None] = mapped_column(String(36), comment="确认人ID")
```

#### 2. EntityProposal 表扩展

```python
# 新增字段
proposal_category: Mapped[str | None] = mapped_column(String(20), comment="提案分类：setting/memory/linkage")
priority: Mapped[int] = mapped_column(Integer, default=3, comment="优先级 1-5")
```

**提案分类说明**：
- `setting`: 设定提案（角色、世界观等）
- `memory`: 记忆提案（事件、状态变化等）
- `linkage`: 联动提案（影响分析生成的修改建议）

## API Design

### 1. 统一 AI 助手 API

#### POST /api/assistant/chat

**请求**：
```json
{
  "novel_id": "uuid",
  "context_type": "outline|characters|worldbuilding|chapter",
  "context_id": "uuid|null",
  "user_message": "string",
  "selected_file_ids": ["file_id1", "file_id2"],
  "conversation_history": [
    {"role": "user", "content": "..."},
    {"role": "assistant", "content": "..."}
  ]
}
```

**响应**：
```json
{
  "response": "AI 回复内容",
  "context_files": [
    {
      "id": "file_id",
      "label": "文件标签",
      "path": "文件路径",
      "kind": "文件类型"
    }
  ],
  "suggestions": [
    {
      "type": "linkage",
      "target_type": "volume|synopsis|character",
      "target_id": "uuid",
      "action": "update|regenerate",
      "reason": "原因说明",
      "preview": "预览内容"
    }
  ],
  "impact_report": {
    "report_id": "uuid",
    "summary": "影响摘要"
  }
}
```

### 2. 影响分析 API

#### POST /api/impact/analyze

**请求**：
```json
{
  "novel_id": "uuid",
  "change_type": "outline|character|worldbuilding",
  "change_id": "uuid",
  "old_content": "旧内容",
  "new_content": "新内容"
}
```

**响应**：
```json
{
  "report_id": "uuid",
  "affected_volumes": [
    {
      "id": "uuid",
      "title": "卷标题",
      "reason": "影响原因",
      "severity": "high|medium|low"
    }
  ],
  "affected_chapters": [
    {
      "id": "uuid",
      "chapter_number": 1,
      "title": "章节标题",
      "reason": "影响原因",
      "severity": "high|medium|low"
    }
  ],
  "affected_characters": [
    {
      "id": "uuid",
      "name": "角色名",
      "reason": "影响原因",
      "severity": "high|medium|low"
    }
  ],
  "conflicts": [
    {
      "type": "contradiction|inconsistency",
      "description": "矛盾描述",
      "location": "位置信息"
    }
  ],
  "suggestions": [
    {
      "target_type": "volume|synopsis|character",
      "target_id": "uuid",
      "action": "update|regenerate",
      "reason": "建议原因",
      "preview": "预览内容"
    }
  ]
}
```

#### GET /api/impact/reports/{novel_id}

**响应**：
```json
{
  "reports": [
    {
      "id": "uuid",
      "change_type": "outline",
      "status": "pending|approved|rejected",
      "created_at": "2024-01-01T00:00:00Z",
      "summary": "影响摘要"
    }
  ]
}
```

### 3. 审批流 API

#### GET /api/review/proposals

**请求参数**：
- `novel_id`: 小说ID
- `status`: pending|approved|rejected
- `proposal_type`: outline|character|worldbuilding|chapter|entity_event|entity_relation
- `chapter_id`: 章节ID（可选）
- `volume_id`: 分卷ID（可选）
- `category`: setting|memory|linkage（可选）

**响应**：
```json
{
  "proposals": [
    {
      "id": "uuid",
      "novel_id": "uuid",
      "chapter_id": "uuid|null",
      "volume_id": "uuid|null",
      "entity_type": "character|item|...",
      "action": "create|update|delete|record_event|record_relation",
      "entity_name": "实体名称",
      "status": "pending",
      "reason": "提案理由",
      "payload": {},
      "proposal_category": "setting|memory|linkage",
      "priority": 3,
      "created_at": "2024-01-01T00:00:00Z"
    }
  ],
  "total": 10,
  "pending_count": 5
}
```

#### POST /api/review/proposals/{proposal_id}/approve

**响应**：
```json
{
  "success": true,
  "message": "提案已批准",
  "proposal": {...}
}
```

#### POST /api/review/proposals/{proposal_id}/reject

**请求**：
```json
{
  "reason": "拒绝原因"
}
```

**响应**：
```json
{
  "success": true,
  "message": "提案已拒绝"
}
```

#### POST /api/review/proposals/batch-approve

**请求**：
```json
{
  "proposal_ids": ["uuid1", "uuid2", "uuid3"]
}
```

**响应**：
```json
{
  "success": 2,
  "failed": 1,
  "errors": [
    {
      "proposal_id": "uuid3",
      "error": "错误信息"
    }
  ]
}
```

### 4. 记忆系统 API

#### GET /api/memory/aggregated

**请求参数**：
- `novel_id`: 小说ID
- `aggregation_type`: 10_chapters|volume
- `start_chapter`: 起始章节号（可选）
- `end_chapter`: 结束章节号（可选）
- `volume_id`: 分卷ID（可选）

**响应**：
```json
{
  "memories": [
    {
      "id": "uuid",
      "aggregation_type": "10_chapters",
      "start_chapter": 1,
      "end_chapter": 10,
      "summary": "聚合摘要",
      "key_events": ["事件1", "事件2"],
      "state_snapshot": {},
      "created_at": "2024-01-01T00:00:00Z"
    }
  ]
}
```

#### POST /api/memory/aggregate

**请求**：
```json
{
  "novel_id": "uuid",
  "aggregation_type": "10_chapters|volume",
  "start_chapter": 1,
  "end_chapter": 10,
  "volume_id": "uuid|null"
}
```

**响应**：
```json
{
  "success": true,
  "memory": {...}
}
```

#### GET /api/memory/global-state

**请求参数**：
- `novel_id`: 小说ID
- `chapter_number`: 章节号（可选，不传则返回最新状态）

**响应**：
```json
{
  "snapshot": {
    "id": "uuid",
    "snapshot_type": "chapter",
    "chapter_number": 10,
    "character_states": {
      "主角名": {
        "realm": "筑基期",
        "location": "天元城",
        "status": "alive"
      }
    },
    "item_ownership": {
      "玄铁剑": {
        "current_owner": "主角名",
        "history": [
          {"chapter": 1, "owner": "主角名"}
        ]
      }
    },
    "event_timeline": [
      {
        "chapter": 1,
        "event": "主角获得玄铁剑",
        "timestamp": "2024-01-01T00:00:00Z"
      }
    ],
    "foreshadowing_tracker": [
      {
        "content": "神秘老者的预言",
        "planted_chapter": 1,
        "resolved_chapter": null,
        "status": "open"
      }
    ]
  }
}
```

### 5. 门禁控制 API

#### GET /api/gate/check

**请求参数**：
- `novel_id`: 小说ID
- `module`: characters|worldbuilding|volumes|chapters

**响应**：
```json
{
  "allowed": false,
  "reason": "大纲未确认，请先完成大纲确认",
  "required_steps": [
    "确认大纲"
  ]
}
```

#### POST /api/gate/unlock

**请求**：
```json
{
  "novel_id": "uuid"
}
```

**响应**：
```json
{
  "success": true,
  "message": "所有模块已解锁"
}
```

### 6. 对比审批 API

#### GET /api/compare/{entity_type}/{entity_id}

**请求参数**：
- `entity_type`: outline|character|worldbuilding|chapter
- `entity_id`: 实体ID
- `version`: old|new（可选，默认对比最新两个版本）

**响应**：
```json
{
  "old_version": {
    "id": "uuid",
    "content": "旧内容",
    "version": 1,
    "created_at": "2024-01-01T00:00:00Z"
  },
  "new_version": {
    "id": "uuid",
    "content": "新内容",
    "version": 2,
    "created_at": "2024-01-02T00:00:00Z"
  },
  "diff": {
    "additions": ["新增内容1", "新增内容2"],
    "deletions": ["删除内容1"],
    "modifications": [
      {
        "old": "旧文本",
        "new": "新文本"
      }
    ]
  }
}
```

#### POST /api/compare/{entity_type}/{entity_id}/accept

**响应**：
```json
{
  "success": true,
  "message": "已接受修改"
}
```

#### POST /api/compare/{entity_type}/{entity_id}/reject

**响应**：
```json
{
  "success": true,
  "message": "已拒绝修改，保留原内容"
}
```

#### POST /api/compare/{entity_type}/{entity_id}/continue

**请求**：
```json
{
  "user_feedback": "继续修改的要求"
}
```

**响应**：
```json
{
  "success": true,
  "message": "已提交继续修改请求"
}
```

## Core Algorithms

### 1. 影响分析算法 (Impact Analysis Algorithm)

#### 1.1 大纲变更影响分析

**算法流程**：

```python
def analyze_outline_impact(old_outline: Outline, new_outline: Outline) -> ImpactReport:
    """
    分析大纲修改的影响范围
    """
    # Step 1: 计算字段级别的 diff
    field_diffs = compute_field_diff(old_outline, new_outline)
    # 关注字段: title, genre, theme, main_conflict, protagonist_goal, world_setting
    
    # Step 2: 文本相似度分析
    similarity_scores = {}
    for field in ["theme", "main_conflict", "protagonist_goal"]:
        old_text = getattr(old_outline, field, "")
        new_text = getattr(new_outline, field, "")
        similarity_scores[field] = compute_text_similarity(old_text, new_text)
    
    # Step 3: 扫描受影响的分卷
    affected_volumes = []
    for volume in get_all_volumes(novel_id):
        # 检查分卷规划中是否引用了变更内容
        references = find_text_references(volume.plan_markdown, field_diffs)
        if references:
            affected_volumes.append({
                "id": volume.id,
                "title": volume.title,
                "reason": f"引用了大纲中的 {', '.join(references)}",
                "severity": calculate_severity(references, similarity_scores)
            })
    
    # Step 4: 扫描受影响的章节细纲
    affected_chapters = []
    for synopsis in get_all_synopses(novel_id):
        conflicts = detect_conflicts(synopsis.content, new_outline)
        if conflicts:
            affected_chapters.append({
                "id": synopsis.chapter_id,
                "chapter_number": synopsis.chapter_number,
                "reason": conflicts,
                "severity": "high" if "矛盾" in conflicts else "medium"
            })
    
    # Step 5: 扫描受影响的角色
    affected_characters = []
    for character in get_all_characters(novel_id):
        # 检查角色设定是否与新大纲矛盾
        character_conflicts = check_character_outline_consistency(character, new_outline)
        if character_conflicts:
            affected_characters.append({
                "id": character.id,
                "name": character.name,
                "reason": character_conflicts,
                "severity": "medium"
            })
    
    # Step 6: 生成影响报告
    return ImpactReport(
        novel_id=novel_id,
        change_type="outline",
        affected_volumes=affected_volumes,
        affected_chapters=affected_chapters,
        affected_characters=affected_characters,
        conflicts=extract_conflicts(affected_chapters, affected_characters),
        suggestions=generate_linkage_suggestions(affected_volumes, affected_chapters)
    )
```

**关键函数说明**：

1. **compute_text_similarity**: 使用余弦相似度或编辑距离计算文本相似度
   - 相似度 > 0.9: 微小变化
   - 0.7 - 0.9: 中等变化
   - < 0.7: 重大变化

2. **find_text_references**: 使用关键词提取和语义匹配检测引用
   - 提取大纲变更字段的关键词
   - 在分卷规划中搜索这些关键词
   - 使用 TF-IDF 或 BERT 嵌入计算语义相似度

3. **detect_conflicts**: 使用 AI 检测矛盾
   - 构建 prompt: "对比以下细纲和新大纲，检测是否存在矛盾"
   - 调用 AI 模型生成矛盾报告
   - 解析 AI 输出，提取矛盾类型和位置

4. **calculate_severity**: 根据引用数量和相似度计算严重程度
   - high: 相似度 < 0.7 且引用 > 3 处
   - medium: 相似度 0.7-0.9 或引用 1-3 处
   - low: 相似度 > 0.9 且引用 1 处

#### 1.2 角色设定变更影响分析

**算法流程**：

```python
def analyze_character_impact(character: Character, old_state: dict, new_state: dict) -> ImpactReport:
    """
    分析角色设定修改的影响范围
    """
    # Step 1: 识别状态变化
    state_changes = {}
    for key in ["realm", "faction", "location", "status"]:
        if old_state.get(key) != new_state.get(key):
            state_changes[key] = {
                "old": old_state.get(key),
                "new": new_state.get(key)
            }
    
    # Step 2: 查询关系网
    related_entities = query_related_entities(character.id)
    # 返回: 与该角色有关系的所有实体（角色、道具、地点等）
    
    # Step 3: 扫描未定稿章节
    affected_chapters = []
    for chapter in get_undrafted_chapters(novel_id):
        # 检查章节中是否已出现新状态
        conflicts = check_chapter_character_consistency(chapter, character, new_state)
        if conflicts:
            affected_chapters.append({
                "id": chapter.id,
                "chapter_number": chapter.chapter_number,
                "reason": conflicts,
                "severity": "high"
            })
    
    # Step 4: 生成矛盾警告
    conflicts = []
    for chapter_info in affected_chapters:
        conflicts.append({
            "type": "inconsistency",
            "description": f"第{chapter_info['chapter_number']}章: {chapter_info['reason']}",
            "location": f"chapter_{chapter_info['chapter_number']}"
        })
    
    return ImpactReport(
        novel_id=novel_id,
        change_type="character",
        affected_chapters=affected_chapters,
        conflicts=conflicts,
        suggestions=generate_character_fix_suggestions(conflicts)
    )
```

### 2. 记忆聚合算法 (Memory Aggregation Algorithm)

#### 2.1 10章聚合算法

**算法流程**：

```python
def aggregate_10_chapters(novel_id: str, start_chapter: int, end_chapter: int) -> AggregatedMemory:
    """
    生成10章聚合记忆
    """
    # Step 1: 读取章节记忆
    chapter_memories = []
    for chapter_num in range(start_chapter, end_chapter + 1):
        memory = get_chapter_memory(novel_id, chapter_num)
        if memory:
            chapter_memories.append(memory)
    
    # Step 2: 合并关键事件
    all_events = []
    for memory in chapter_memories:
        for event in memory.key_events:
            all_events.append({
                "chapter": memory.chapter_number,
                "event": event,
                "timestamp": memory.created_at
            })
    # 去重：使用文本相似度检测重复事件
    unique_events = deduplicate_events(all_events, threshold=0.85)
    
    # Step 3: 合并状态变化
    state_snapshot = {}
    for memory in chapter_memories:
        for change in memory.state_changes:
            # 解析状态变化: "角色名: 境界 炼气期 -> 筑基期"
            entity, field, old_val, new_val = parse_state_change(change)
            if entity not in state_snapshot:
                state_snapshot[entity] = {}
            state_snapshot[entity][field] = new_val
    
    # Step 4: 合并道具流转
    item_transfers = []
    for memory in chapter_memories:
        for transfer in memory.inventory_changes:
            item_transfers.append({
                "chapter": memory.chapter_number,
                "item": transfer["item"],
                "from": transfer.get("from"),
                "to": transfer["to"]
            })
    
    # Step 5: 合并未完事项
    open_threads = []
    for memory in chapter_memories:
        for thread in memory.open_threads:
            # 检查是否在后续章节中已回收
            if not is_thread_resolved(thread, chapter_memories):
                open_threads.append({
                    "content": thread,
                    "planted_chapter": memory.chapter_number
                })
    
    # Step 6: 调用 AI 生成摘要
    summary_prompt = f"""
    请根据以下10章的关键事件，生成一个500字左右的聚合摘要：
    
    关键事件：
    {format_events(unique_events)}
    
    状态变化：
    {format_state_snapshot(state_snapshot)}
    
    未回收伏笔：
    {format_open_threads(open_threads)}
    
    要求：
    1. 突出主角成长弧线
    2. 总结核心冲突进展
    3. 标记重要的状态变化
    4. 列出未解决的悬念
    """
    summary = call_ai_model(summary_prompt)
    
    # Step 7: 存储聚合记忆
    return AggregatedMemory(
        novel_id=novel_id,
        aggregation_type="10_chapters",
        start_chapter=start_chapter,
        end_chapter=end_chapter,
        summary=summary,
        key_events=unique_events,
        state_snapshot=state_snapshot,
        item_transfers=item_transfers,
        open_threads=open_threads
    )
```

**关键函数说明**：

1. **deduplicate_events**: 事件去重
   - 计算事件文本的 TF-IDF 向量
   - 使用余弦相似度检测重复
   - 相似度 > 0.85 视为重复，保留最早的记录

2. **parse_state_change**: 解析状态变化字符串
   - 正则表达式提取: `(\w+): (\w+) (.+) -> (.+)`
   - 返回: (实体名, 字段名, 旧值, 新值)

3. **is_thread_resolved**: 检查伏笔是否已回收
   - 在后续章节记忆中搜索相关内容
   - 使用语义相似度判断是否为同一伏笔的回收

#### 2.2 卷级聚合算法

**算法流程**：

```python
def aggregate_volume(volume: Volume) -> AggregatedMemory:
    """
    生成卷级聚合记忆
    """
    # Step 1: 读取本卷所有章节记忆
    chapter_memories = get_chapter_memories_by_volume(volume.id)
    
    # Step 2: 读取本卷范围内的10章聚合记忆
    aggregated_memories = get_aggregated_memories_by_volume(volume.id)
    
    # Step 3: 合并关键事件（优先使用聚合记忆中的事件）
    all_events = []
    for agg_mem in aggregated_memories:
        all_events.extend(agg_mem.key_events)
    
    # Step 4: 合并状态变化（保留最终状态）
    final_state = {}
    for agg_mem in aggregated_memories:
        for entity, state in agg_mem.state_snapshot.items():
            if entity not in final_state:
                final_state[entity] = {}
            final_state[entity].update(state)
    
    # Step 5: 调用 AI 生成卷级摘要
    summary_prompt = f"""
    请根据以下卷的内容，生成一个1000字左右的卷级摘要：
    
    卷标题：{volume.title}
    卷规划：{volume.plan_markdown}
    
    关键事件：
    {format_events(all_events)}
    
    最终状态：
    {format_state_snapshot(final_state)}
    
    要求：
    1. 总结本卷主角成长弧线
    2. 总结本卷核心冲突解决情况
    3. 列出开启的下卷伏笔
    4. 标记重要的里程碑事件
    """
    summary = call_ai_model(summary_prompt)
    
    return AggregatedMemory(
        novel_id=volume.novel_id,
        aggregation_type="volume",
        start_chapter=volume.start_chapter,
        end_chapter=volume.end_chapter,
        volume_id=volume.id,
        summary=summary,
        key_events=all_events,
        state_snapshot=final_state
    )
```

### 3. 上下文注入策略 (Context Injection Strategy)

#### 3.1 动态上下文构建

**算法流程**：

```python
def build_context_for_chapter(novel_id: str, chapter_number: int, token_budget: int = 8000) -> str:
    """
    为指定章节构建上下文，按优先级注入记忆
    """
    context_parts = []
    remaining_tokens = token_budget
    
    # 优先级1: 章节细纲（必读）
    synopsis = get_synopsis(novel_id, chapter_number)
    if synopsis:
        synopsis_text = f"【本章细纲】\n{synopsis.content}"
        synopsis_tokens = estimate_tokens(synopsis_text)
        context_parts.append(synopsis_text)
        remaining_tokens -= synopsis_tokens
    
    # 优先级2: 前1-3章记忆
    recent_memories = get_recent_memories(novel_id, chapter_number, count=3)
    for memory in recent_memories:
        memory_text = format_chapter_memory(memory)
        memory_tokens = estimate_tokens(memory_text)
        if remaining_tokens >= memory_tokens:
            context_parts.append(memory_text)
            remaining_tokens -= memory_tokens
    
    # 优先级3: 角色当前状态
    characters = get_active_characters(novel_id, chapter_number)
    character_states = get_character_states(characters, chapter_number)
    character_text = format_character_states(character_states)
    character_tokens = estimate_tokens(character_text)
    if remaining_tokens >= character_tokens:
        context_parts.append(character_text)
        remaining_tokens -= character_tokens
    
    # 优先级4: 最近的10章聚合快照
    latest_aggregation = get_latest_aggregation(novel_id, chapter_number, type="10_chapters")
    if latest_aggregation and remaining_tokens >= 1000:
        agg_text = f"【前10章摘要】\n{latest_aggregation.summary}"
        agg_tokens = estimate_tokens(agg_text)
        if remaining_tokens >= agg_tokens:
            context_parts.append(agg_text)
            remaining_tokens -= agg_tokens
    
    # 优先级5: 本卷聚合记忆
    volume = get_volume_by_chapter(novel_id, chapter_number)
    if volume:
        volume_aggregation = get_volume_aggregation(volume.id)
        if volume_aggregation and remaining_tokens >= 1500:
            vol_text = f"【本卷摘要】\n{volume_aggregation.summary}"
            vol_tokens = estimate_tokens(vol_text)
            if remaining_tokens >= vol_tokens:
                context_parts.append(vol_text)
                remaining_tokens -= vol_tokens
    
    # 优先级6: 全局事件时间线（截取最近20个事件）
    if remaining_tokens >= 500:
        global_state = get_global_snapshot(novel_id, chapter_number)
        if global_state:
            recent_events = global_state.event_timeline[-20:]
            events_text = format_event_timeline(recent_events)
            events_tokens = estimate_tokens(events_text)
            if remaining_tokens >= events_tokens:
                context_parts.append(events_text)
                remaining_tokens -= events_tokens
    
    return "\n\n".join(context_parts)
```

**关键函数说明**：

1. **estimate_tokens**: Token 估算
   - 中文: 1 字符 ≈ 1.5 tokens
   - 英文: 1 单词 ≈ 1.3 tokens
   - 使用 tiktoken 库精确计算

2. **format_chapter_memory**: 格式化章节记忆
   ```
   【第X章】
   关键事件：
   - 事件1
   - 事件2
   状态变化：
   - 角色A: 境界 炼气期 -> 筑基期
   ```

3. **get_active_characters**: 获取活跃角色
   - 查询关系网，找出在当前章节前后出现的角色
   - 按出现频率排序，取前10个

#### 3.2 智能文件选择

**算法流程**：

```python
def select_context_files(novel_id: str, user_message: str, context_type: str) -> list[dict]:
    """
    根据用户消息智能选择相关文件
    """
    # Step 1: 构建文件目录
    file_catalog = build_file_catalog(novel_id)
    # 返回: [{"id": "outline", "label": "大纲", "content": "...", "kind": "outline"}, ...]
    
    # Step 2: 提取用户消息中的关键词
    keywords = extract_keywords(user_message)
    # 使用 jieba 分词 + TF-IDF 提取关键词
    
    # Step 3: 计算文件相关性
    file_scores = []
    for file in file_catalog:
        # 计算关键词匹配度
        keyword_score = calculate_keyword_match(keywords, file["content"])
        
        # 计算语义相似度（使用 BERT 嵌入）
        semantic_score = calculate_semantic_similarity(user_message, file["content"])
        
        # 综合得分
        total_score = 0.4 * keyword_score + 0.6 * semantic_score
        
        file_scores.append({
            "file": file,
            "score": total_score
        })
    
    # Step 4: 按得分排序，取前5个
    file_scores.sort(key=lambda x: x["score"], reverse=True)
    selected_files = [item["file"] for item in file_scores[:5]]
    
    # Step 5: 根据 context_type 强制包含某些文件
    if context_type == "outline":
        # 大纲页面必须包含大纲文件
        if not any(f["kind"] == "outline" for f in selected_files):
            outline_file = next(f for f in file_catalog if f["kind"] == "outline")
            selected_files.insert(0, outline_file)
    elif context_type == "chapter":
        # 章节页面必须包含细纲和前几章记忆
        # ...
    
    return selected_files
```


## Frontend Components

### 1. 统一 AI 助手 UI (UnifiedAssistantUI)

**组件职责**：提供全局可用的 AI 对话界面，根据当前页面上下文动态调整能力

**组件结构**：

```tsx
interface UnifiedAssistantUIProps {
  novelId: string;
  contextType: 'outline' | 'characters' | 'worldbuilding' | 'chapter';
  contextId?: string;
  onSuggestionApply?: (suggestion: Suggestion) => void;
}

const UnifiedAssistantUI: React.FC<UnifiedAssistantUIProps> = ({
  novelId,
  contextType,
  contextId,
  onSuggestionApply
}) => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputValue, setInputValue] = useState('');
  const [selectedFiles, setSelectedFiles] = useState<string[]>([]);
  const [contextFiles, setContextFiles] = useState<ContextFile[]>([]);
  const [impactReport, setImpactReport] = useState<ImpactReport | null>(null);
  
  // 发送消息
  const handleSendMessage = async () => {
    const response = await api.post('/api/assistant/chat', {
      novel_id: novelId,
      context_type: contextType,
      context_id: contextId,
      user_message: inputValue,
      selected_file_ids: selectedFiles,
      conversation_history: messages
    });
    
    setMessages([...messages, 
      { role: 'user', content: inputValue },
      { role: 'assistant', content: response.data.response }
    ]);
    
    // 更新上下文文件
    if (response.data.context_files) {
      setContextFiles(response.data.context_files);
    }
    
    // 显示影响报告
    if (response.data.impact_report) {
      setImpactReport(response.data.impact_report);
    }
  };
  
  return (
    <div className="unified-assistant">
      {/* 上下文文件选择器 */}
      <ContextFileSelector
        files={contextFiles}
        selectedFiles={selectedFiles}
        onSelectionChange={setSelectedFiles}
      />
      
      {/* 对话历史 */}
      <MessageList messages={messages} />
      
      {/* 影响报告展示 */}
      {impactReport && (
        <ImpactReportCard
          report={impactReport}
          onViewDetails={() => {/* 跳转到影响分析页面 */}}
        />
      )}
      
      {/* 输入框 */}
      <Input.TextArea
        value={inputValue}
        onChange={(e) => setInputValue(e.target.value)}
        placeholder={getPlaceholderByContext(contextType)}
        onPressEnter={handleSendMessage}
      />
      
      {/* 快捷操作按钮 */}
      <QuickActions contextType={contextType} />
    </div>
  );
};
```

**关键子组件**：

1. **ContextFileSelector**: 上下文文件选择器
   - 展示 AI 自动检索到的相关文件
   - 支持用户手动选择/取消选择文件
   - 显示文件类型图标和标签

2. **MessageList**: 对话历史列表
   - 支持 Markdown 渲染
   - 支持代码高亮
   - 支持联动建议卡片展示

3. **ImpactReportCard**: 影响报告卡片
   - 简要展示受影响的内容数量
   - 提供"查看详情"按钮
   - 支持快速批准/拒绝联动修改

4. **QuickActions**: 快捷操作按钮
   - 根据 contextType 显示不同的快捷操作
   - 大纲页面: "生成分卷"、"检测矛盾"
   - 章节页面: "生成正文"、"检查连续性"
   - 设定页面: "创建角色"、"创建道具"

**交互流程**：

```mermaid
sequenceDiagram
    participant User
    participant UI as UnifiedAssistantUI
    participant API as Backend API
    participant AI as AI Service
    
    User->>UI: 输入消息
    UI->>API: POST /api/assistant/chat
    API->>AI: 调用 AI 模型
    AI-->>API: 返回回复 + 上下文文件
    API-->>UI: 返回响应
    UI->>UI: 更新对话历史
    UI->>UI: 更新上下文文件列表
    
    alt 包含影响分析
        API-->>UI: 返回影响报告
        UI->>User: 展示影响报告卡片
        User->>UI: 点击"查看详情"
        UI->>User: 跳转到影响分析页面
    end
```

### 2. 对比审批视图 (ComparisonReviewView)

**组件职责**：展示左右对比的文本差异，提供接受/拒绝/继续修改操作

**组件结构**：

```tsx
interface ComparisonReviewViewProps {
  entityType: 'outline' | 'character' | 'worldbuilding' | 'chapter';
  entityId: string;
  oldVersion: Version;
  newVersion: Version;
  onAccept: () => void;
  onReject: () => void;
  onContinue: (feedback: string) => void;
}

const ComparisonReviewView: React.FC<ComparisonReviewViewProps> = ({
  entityType,
  entityId,
  oldVersion,
  newVersion,
  onAccept,
  onReject,
  onContinue
}) => {
  const [diff, setDiff] = useState<Diff | null>(null);
  const [continueDialogVisible, setContinueDialogVisible] = useState(false);
  const [feedback, setFeedback] = useState('');
  
  useEffect(() => {
    // 加载 diff 数据
    loadDiff();
  }, [entityId]);
  
  const loadDiff = async () => {
    const response = await api.get(`/api/compare/${entityType}/${entityId}`);
    setDiff(response.data.diff);
  };
  
  return (
    <div className="comparison-review-view">
      {/* 标题栏 */}
      <div className="header">
        <h2>审批修改</h2>
        <Space>
          <Button type="primary" onClick={onAccept}>接受</Button>
          <Button onClick={onReject}>拒绝</Button>
          <Button onClick={() => setContinueDialogVisible(true)}>继续修改</Button>
        </Space>
      </div>
      
      {/* 对比视图 */}
      <div className="comparison-container">
        <div className="left-panel">
          <div className="panel-header">原始内容</div>
          <div className="panel-content">
            <MarkdownRenderer content={oldVersion.content} />
          </div>
        </div>
        
        <div className="diff-panel">
          <DiffViewer diff={diff} />
        </div>
        
        <div className="right-panel">
          <div className="panel-header">修改后内容</div>
          <div className="panel-content">
            <MarkdownRenderer content={newVersion.content} />
          </div>
        </div>
      </div>
      
      {/* 继续修改对话框 */}
      <Modal
        title="继续修改"
        visible={continueDialogVisible}
        onOk={() => {
          onContinue(feedback);
          setContinueDialogVisible(false);
        }}
        onCancel={() => setContinueDialogVisible(false)}
      >
        <Input.TextArea
          value={feedback}
          onChange={(e) => setFeedback(e.target.value)}
          placeholder="请描述您希望如何修改..."
          rows={4}
        />
      </Modal>
    </div>
  );
};
```

**关键子组件**：

1. **DiffViewer**: 差异展示组件
   - 使用 `react-diff-viewer` 或自定义实现
   - 高亮显示新增、删除、修改的内容
   - 支持行级和字符级 diff

2. **MarkdownRenderer**: Markdown 渲染器
   - 使用 `react-markdown` 或 `marked`
   - 支持代码高亮
   - 支持自定义样式

**样式设计**：

```css
.comparison-container {
  display: grid;
  grid-template-columns: 1fr 100px 1fr;
  gap: 16px;
  height: calc(100vh - 200px);
}

.left-panel, .right-panel {
  border: 1px solid #d9d9d9;
  border-radius: 4px;
  overflow: hidden;
}

.panel-header {
  background: #fafafa;
  padding: 12px 16px;
  border-bottom: 1px solid #d9d9d9;
  font-weight: 500;
}

.panel-content {
  padding: 16px;
  height: calc(100% - 48px);
  overflow-y: auto;
}

.diff-panel {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: #8c8c8c;
}
```

### 3. 审批中心 (ReviewCenter)

**组件职责**：集中展示所有待审批提案，支持筛选和批量操作

**组件结构**：

```tsx
const ReviewCenter: React.FC = () => {
  const [proposals, setProposals] = useState<Proposal[]>([]);
  const [filters, setFilters] = useState<Filters>({
    status: 'pending',
    proposal_type: undefined,
    category: undefined
  });
  const [selectedProposals, setSelectedProposals] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  
  useEffect(() => {
    loadProposals();
  }, [filters]);
  
  const loadProposals = async () => {
    setLoading(true);
    const response = await api.get('/api/review/proposals', { params: filters });
    setProposals(response.data.proposals);
    setLoading(false);
  };
  
  const handleBatchApprove = async () => {
    const response = await api.post('/api/review/proposals/batch-approve', {
      proposal_ids: selectedProposals
    });
    
    message.success(`成功批准 ${response.data.success} 个提案`);
    if (response.data.failed > 0) {
      message.error(`失败 ${response.data.failed} 个提案`);
    }
    
    loadProposals();
    setSelectedProposals([]);
  };
  
  return (
    <div className="review-center">
      {/* 筛选栏 */}
      <div className="filter-bar">
        <Space>
          <Select
            value={filters.status}
            onChange={(value) => setFilters({ ...filters, status: value })}
            style={{ width: 120 }}
          >
            <Select.Option value="pending">待审批</Select.Option>
            <Select.Option value="approved">已批准</Select.Option>
            <Select.Option value="rejected">已拒绝</Select.Option>
          </Select>
          
          <Select
            value={filters.proposal_type}
            onChange={(value) => setFilters({ ...filters, proposal_type: value })}
            style={{ width: 150 }}
            placeholder="提案类型"
            allowClear
          >
            <Select.Option value="outline">大纲</Select.Option>
            <Select.Option value="character">角色</Select.Option>
            <Select.Option value="worldbuilding">世界观</Select.Option>
            <Select.Option value="chapter">章节</Select.Option>
          </Select>
          
          <Select
            value={filters.category}
            onChange={(value) => setFilters({ ...filters, category: value })}
            style={{ width: 120 }}
            placeholder="分类"
            allowClear
          >
            <Select.Option value="setting">设定</Select.Option>
            <Select.Option value="memory">记忆</Select.Option>
            <Select.Option value="linkage">联动</Select.Option>
          </Select>
        </Space>
        
        {selectedProposals.length > 0 && (
          <Space>
            <Button type="primary" onClick={handleBatchApprove}>
              批量批准 ({selectedProposals.length})
            </Button>
            <Button onClick={() => setSelectedProposals([])}>
              取消选择
            </Button>
          </Space>
        )}
      </div>
      
      {/* 提案列表 */}
      <Table
        dataSource={proposals}
        loading={loading}
        rowSelection={{
          selectedRowKeys: selectedProposals,
          onChange: setSelectedProposals
        }}
        columns={[
          {
            title: '类型',
            dataIndex: 'entity_type',
            width: 100,
            render: (type) => <Tag>{type}</Tag>
          },
          {
            title: '实体名称',
            dataIndex: 'entity_name',
            width: 150
          },
          {
            title: '操作',
            dataIndex: 'action',
            width: 100,
            render: (action) => <Tag color="blue">{action}</Tag>
          },
          {
            title: '理由',
            dataIndex: 'reason',
            ellipsis: true
          },
          {
            title: '优先级',
            dataIndex: 'priority',
            width: 80,
            render: (priority) => (
              <Tag color={priority >= 4 ? 'red' : priority >= 3 ? 'orange' : 'default'}>
                P{priority}
              </Tag>
            )
          },
          {
            title: '创建时间',
            dataIndex: 'created_at',
            width: 180,
            render: (time) => dayjs(time).format('YYYY-MM-DD HH:mm:ss')
          },
          {
            title: '操作',
            width: 150,
            render: (_, record) => (
              <Space>
                <Button size="small" onClick={() => handleApprove(record.id)}>
                  批准
                </Button>
                <Button size="small" onClick={() => handleReject(record.id)}>
                  拒绝
                </Button>
              </Space>
            )
          }
        ]}
      />
    </div>
  );
};
```

**关键功能**：

1. **筛选功能**：
   - 按状态筛选（待审批/已批准/已拒绝）
   - 按提案类型筛选（大纲/角色/世界观/章节）
   - 按分类筛选（设定/记忆/联动）

2. **批量操作**：
   - 支持多选提案
   - 批量批准
   - 批量拒绝（需要二次确认）

3. **优先级展示**：
   - P5/P4: 红色标签（高优先级）
   - P3: 橙色标签（中优先级）
   - P1/P2: 默认标签（低优先级）

### 4. 门禁提示组件 (GatePromptComponent)

**组件职责**：在大纲未确认时显示锁定提示，引导用户完成大纲确认

**组件结构**：

```tsx
interface GatePromptProps {
  novelId: string;
  module: 'characters' | 'worldbuilding' | 'volumes' | 'chapters';
}

const GatePrompt: React.FC<GatePromptProps> = ({ novelId, module }) => {
  const [gateStatus, setGateStatus] = useState<GateStatus | null>(null);
  const navigate = useNavigate();
  
  useEffect(() => {
    checkGateStatus();
  }, [novelId, module]);
  
  const checkGateStatus = async () => {
    const response = await api.get('/api/gate/check', {
      params: { novel_id: novelId, module }
    });
    setGateStatus(response.data);
  };
  
  if (!gateStatus || gateStatus.allowed) {
    return null;
  }
  
  return (
    <div className="gate-prompt-overlay">
      <div className="gate-prompt-card">
        <div className="icon">
          <LockOutlined style={{ fontSize: 48, color: '#faad14' }} />
        </div>
        <h2>功能已锁定</h2>
        <p>{gateStatus.reason}</p>
        
        {gateStatus.required_steps && (
          <div className="required-steps">
            <h3>需要完成以下步骤：</h3>
            <ul>
              {gateStatus.required_steps.map((step, index) => (
                <li key={index}>{step}</li>
              ))}
            </ul>
          </div>
        )}
        
        <Button
          type="primary"
          size="large"
          onClick={() => navigate(`/novels/${novelId}/outline`)}
        >
          前往大纲页面
        </Button>
      </div>
    </div>
  );
};
```

**样式设计**：

```css
.gate-prompt-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.gate-prompt-card {
  background: white;
  border-radius: 8px;
  padding: 48px;
  max-width: 500px;
  text-align: center;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}

.gate-prompt-card .icon {
  margin-bottom: 24px;
}

.gate-prompt-card h2 {
  font-size: 24px;
  margin-bottom: 16px;
}

.gate-prompt-card p {
  color: #595959;
  margin-bottom: 24px;
}

.required-steps {
  text-align: left;
  margin-bottom: 24px;
  padding: 16px;
  background: #fafafa;
  border-radius: 4px;
}

.required-steps h3 {
  font-size: 16px;
  margin-bottom: 12px;
}

.required-steps ul {
  margin: 0;
  padding-left: 20px;
}

.required-steps li {
  margin-bottom: 8px;
}
```

**使用方式**：

```tsx
// 在需要门禁控制的页面中使用
const CharactersPage: React.FC = () => {
  const { novelId } = useParams();
  
  return (
    <div>
      <GatePrompt novelId={novelId} module="characters" />
      {/* 页面内容 */}
    </div>
  );
};
```


## Data Flow

### 1. 大纲修改流程

```mermaid
sequenceDiagram
    participant User
    participant OutlineUI as 大纲编辑器
    participant API as Backend API
    participant ImpactAnalyzer as 影响分析器
    participant AI as AI Service
    participant DB as Database
    
    User->>OutlineUI: 修改大纲内容
    OutlineUI->>API: POST /api/impact/analyze
    API->>DB: 读取旧大纲
    API->>ImpactAnalyzer: analyze_outline_change()
    ImpactAnalyzer->>DB: 扫描所有 Volume
    ImpactAnalyzer->>DB: 扫描所有 Synopsis
    ImpactAnalyzer->>DB: 扫描所有 Character
    ImpactAnalyzer->>AI: 检测矛盾
    AI-->>ImpactAnalyzer: 返回矛盾报告
    ImpactAnalyzer->>DB: 保存 ImpactReport
    ImpactAnalyzer-->>API: 返回影响报告
    API-->>OutlineUI: 返回受影响内容列表
    
    OutlineUI->>User: 展示影响报告
    User->>OutlineUI: 确认修改
    OutlineUI->>API: POST /api/outline/update
    API->>DB: 更新 Outline
    API->>DB: 更新 Outline.confirmed_at
    
    alt 用户选择联动修改
        User->>OutlineUI: 批准联动修改
        OutlineUI->>API: POST /api/review/proposals/batch-approve
        API->>DB: 批量更新受影响内容
        API-->>OutlineUI: 返回成功
    end
```

### 2. AI 对话流程

```mermaid
sequenceDiagram
    participant User
    participant AssistantUI as 统一 AI 助手
    participant API as Backend API
    participant UnifiedAssistant as 统一 AI 助手服务
    participant ContextBuilder as 上下文构建器
    participant EntityService as 实体服务
    participant AI as AI Service
    participant DB as Database
    
    User->>AssistantUI: 输入消息
    AssistantUI->>API: POST /api/assistant/chat
    API->>UnifiedAssistant: chat()
    
    UnifiedAssistant->>ContextBuilder: build_unified_context()
    ContextBuilder->>DB: 读取大纲、角色、世界观
    ContextBuilder->>DB: 读取章节记忆
    ContextBuilder->>DB: 读取聚合记忆
    ContextBuilder-->>UnifiedAssistant: 返回上下文
    
    UnifiedAssistant->>ContextBuilder: select_context_files()
    ContextBuilder->>DB: 查询相关文件
    ContextBuilder-->>UnifiedAssistant: 返回文件列表
    
    UnifiedAssistant->>EntityService: build_relation_context()
    EntityService->>DB: 查询关系网
    EntityService-->>UnifiedAssistant: 返回关系上下文
    
    UnifiedAssistant->>AI: 调用 AI 模型
    AI-->>UnifiedAssistant: 返回 AI 回复
    
    alt AI 建议修改大纲/设定
        UnifiedAssistant->>ImpactAnalyzer: analyze_impact()
        ImpactAnalyzer-->>UnifiedAssistant: 返回影响报告
    end
    
    UnifiedAssistant-->>API: 返回响应
    API-->>AssistantUI: 返回 AI 回复 + 上下文文件 + 影响报告
    AssistantUI->>User: 展示回复
```

### 3. 审批流程

```mermaid
sequenceDiagram
    participant User
    participant ReviewUI as 审批中心
    participant API as Backend API
    participant UnifiedReview as 统一审批服务
    participant EntityService as 实体服务
    participant FileService as 文件服务
    participant DB as Database
    
    User->>ReviewUI: 打开审批中心
    ReviewUI->>API: GET /api/review/proposals
    API->>UnifiedReview: list_pending_proposals()
    UnifiedReview->>DB: 查询 EntityProposal
    UnifiedReview-->>API: 返回提案列表
    API-->>ReviewUI: 返回提案
    ReviewUI->>User: 展示提案列表
    
    User->>ReviewUI: 选择提案并批准
    ReviewUI->>API: POST /api/review/proposals/{id}/approve
    API->>UnifiedReview: approve_proposal()
    
    UnifiedReview->>DB: 开始事务
    
    alt 提案类型: character
        UnifiedReview->>EntityService: create_or_update_entity()
        EntityService->>DB: 更新 Character
        EntityService->>DB: 更新 StoryEntity
        EntityService->>DB: 创建 EntityEvent
    else 提案类型: entity_event
        UnifiedReview->>EntityService: record_event()
        EntityService->>DB: 创建 EntityEvent
        EntityService->>DB: 更新 GlobalState
    else 提案类型: entity_relation
        UnifiedReview->>EntityService: create_relation()
        EntityService->>DB: 创建 EntityRelation
    end
    
    UnifiedReview->>DB: 更新 EntityProposal.status = "approved"
    UnifiedReview->>DB: 提交事务
    
    UnifiedReview->>FileService: save_to_file()
    FileService->>FileStorage: 保存 JSON 文件
    
    UnifiedReview-->>API: 返回成功
    API-->>ReviewUI: 返回成功
    ReviewUI->>User: 显示成功提示
```

### 4. 记忆聚合流程

```mermaid
sequenceDiagram
    participant System
    participant MemoryAggregator as 记忆聚合器
    participant GlobalStateManager as 全局状态管理器
    participant AI as AI Service
    participant DB as Database
    
    Note over System: 触发条件：每10章定稿后
    
    System->>MemoryAggregator: aggregate_10_chapters()
    MemoryAggregator->>DB: 读取10章 ChapterMemory
    MemoryAggregator->>MemoryAggregator: 合并关键事件
    MemoryAggregator->>MemoryAggregator: 合并状态变化
    MemoryAggregator->>MemoryAggregator: 合并道具流转
    MemoryAggregator->>MemoryAggregator: 合并未完事项
    
    MemoryAggregator->>AI: 生成聚合摘要
    AI-->>MemoryAggregator: 返回摘要文本
    
    MemoryAggregator->>DB: 保存 AggregatedMemory
    
    MemoryAggregator->>GlobalStateManager: update_global_snapshot()
    GlobalStateManager->>DB: 读取最新 GlobalState
    GlobalStateManager->>GlobalStateManager: 更新角色状态表
    GlobalStateManager->>GlobalStateManager: 更新道具归属表
    GlobalStateManager->>GlobalStateManager: 更新事件时间线
    GlobalStateManager->>DB: 保存新 GlobalState
    
    MemoryAggregator-->>System: 返回聚合记忆
    
    Note over System: 触发条件：每卷完成后
    
    System->>MemoryAggregator: aggregate_volume()
    MemoryAggregator->>DB: 读取本卷所有 ChapterMemory
    MemoryAggregator->>DB: 读取本卷所有 AggregatedMemory
    MemoryAggregator->>MemoryAggregator: 合并卷级事件
    MemoryAggregator->>MemoryAggregator: 计算最终状态
    
    MemoryAggregator->>AI: 生成卷级摘要
    AI-->>MemoryAggregator: 返回摘要文本
    
    MemoryAggregator->>DB: 保存卷级 AggregatedMemory
    MemoryAggregator-->>System: 返回卷级记忆
```

## Deployment and Migration

### 1. 部署方案

#### 1.1 开发环境

**技术栈**：
- Backend: FastAPI + Uvicorn (开发模式)
- Frontend: Vite Dev Server
- Database: MySQL 8.0 (本地)
- Cache: Redis (可选)

**启动命令**：
```bash
# 后端
cd backend
python -m uvicorn app.main:app --reload --port 8000

# 前端
cd frontend
npm run dev
```

#### 1.2 生产环境

**技术栈**：
- Backend: FastAPI + Gunicorn + Uvicorn Workers
- Frontend: Nginx (静态文件服务)
- Database: MySQL 8.0 (RDS 或自建)
- Cache: Redis (ElastiCache 或自建)
- Load Balancer: Nginx 或 ALB

**架构图**：

```
┌─────────────────────────────────────────────────────────┐
│                     Load Balancer                        │
│                      (Nginx/ALB)                         │
└────────────────┬────────────────────────────────────────┘
                 │
        ┌────────┴────────┐
        │                 │
┌───────▼──────┐  ┌───────▼──────┐
│  Frontend    │  │  Frontend    │
│  (Nginx)     │  │  (Nginx)     │
└──────────────┘  └──────────────┘
        │                 │
        └────────┬────────┘
                 │
        ┌────────▼────────┐
        │   API Gateway   │
        │    (Nginx)      │
        └────────┬────────┘
                 │
        ┌────────┴────────┐
        │                 │
┌───────▼──────┐  ┌───────▼──────┐
│  Backend 1   │  │  Backend 2   │
│  (FastAPI)   │  │  (FastAPI)   │
└──────┬───────┘  └──────┬───────┘
       │                 │
       └────────┬────────┘
                │
        ┌───────▼────────┐
        │                │
    ┌───▼───┐      ┌─────▼─────┐
    │ MySQL │      │   Redis   │
    └───────┘      └───────────┘
```

**部署配置**：

```yaml
# docker-compose.yml
version: '3.8'

services:
  backend:
    build: ./backend
    command: gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8000
    environment:
      - DATABASE_URL=mysql+pymysql://user:pass@mysql:3306/novel_db
      - REDIS_URL=redis://redis:6379/0
      - ARK_API_KEY=${ARK_API_KEY}
    volumes:
      - ./backend/storage:/app/storage
    depends_on:
      - mysql
      - redis
    deploy:
      replicas: 2
      resources:
        limits:
          cpus: '1'
          memory: 2G
  
  frontend:
    build: ./frontend
    volumes:
      - ./frontend/dist:/usr/share/nginx/html
    ports:
      - "80:80"
  
  mysql:
    image: mysql:8.0
    environment:
      - MYSQL_ROOT_PASSWORD=${MYSQL_ROOT_PASSWORD}
      - MYSQL_DATABASE=novel_db
    volumes:
      - mysql_data:/var/lib/mysql
    command: --default-authentication-plugin=mysql_native_password
  
  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data

volumes:
  mysql_data:
  redis_data:
```

#### 1.3 性能优化配置

**Gunicorn 配置** (`gunicorn.conf.py`):

```python
import multiprocessing

# Worker 配置
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "uvicorn.workers.UvicornWorker"
worker_connections = 1000
max_requests = 1000
max_requests_jitter = 50

# 超时配置
timeout = 120
graceful_timeout = 30
keepalive = 5

# 日志配置
accesslog = "/var/log/gunicorn/access.log"
errorlog = "/var/log/gunicorn/error.log"
loglevel = "info"

# 进程命名
proc_name = "novel-editor-api"
```

**Nginx 配置** (`nginx.conf`):

```nginx
upstream backend {
    least_conn;
    server backend1:8000 max_fails=3 fail_timeout=30s;
    server backend2:8000 max_fails=3 fail_timeout=30s;
}

server {
    listen 80;
    server_name api.example.com;
    
    client_max_body_size 10M;
    
    # API 代理
    location /api/ {
        proxy_pass http://backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # 超时配置
        proxy_connect_timeout 60s;
        proxy_send_timeout 120s;
        proxy_read_timeout 120s;
        
        # 缓存配置（仅 GET 请求）
        proxy_cache api_cache;
        proxy_cache_valid 200 5m;
        proxy_cache_methods GET;
        proxy_cache_key "$scheme$request_method$host$request_uri";
    }
    
    # 静态文件
    location /storage/ {
        alias /app/storage/;
        expires 1h;
        add_header Cache-Control "public, immutable";
    }
}

server {
    listen 80;
    server_name www.example.com;
    
    root /usr/share/nginx/html;
    index index.html;
    
    # SPA 路由
    location / {
        try_files $uri $uri/ /index.html;
    }
    
    # 静态资源缓存
    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
}
```

### 2. 数据迁移脚本设计

#### 2.1 数据库迁移

**使用 Alembic 管理数据库版本**：

```bash
# 初始化 Alembic
alembic init alembic

# 创建迁移脚本
alembic revision --autogenerate -m "add_aggregated_memory_table"

# 执行迁移
alembic upgrade head

# 回滚迁移
alembic downgrade -1
```

**迁移脚本示例** (`alembic/versions/001_add_new_tables.py`):

```python
"""add aggregated memory and global state tables

Revision ID: 001
Revises: 
Create Date: 2024-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # 创建 aggregated_memories 表
    op.create_table(
        'aggregated_memories',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('novel_id', sa.String(36), sa.ForeignKey('novels.id', ondelete='CASCADE'), nullable=False),
        sa.Column('aggregation_type', sa.String(20), nullable=False, comment='聚合类型：10章/卷级'),
        sa.Column('start_chapter', sa.Integer, nullable=False, comment='起始章节号'),
        sa.Column('end_chapter', sa.Integer, nullable=False, comment='结束章节号'),
        sa.Column('volume_id', sa.String(36), sa.ForeignKey('volumes.id', ondelete='SET NULL'), nullable=True),
        sa.Column('summary', sa.Text, nullable=False, comment='聚合摘要'),
        sa.Column('key_events', mysql.JSON, nullable=False, comment='关键事件列表'),
        sa.Column('state_snapshot', mysql.JSON, nullable=False, comment='状态快照'),
        sa.Column('item_transfers', mysql.JSON, nullable=False, comment='道具流转记录'),
        sa.Column('open_threads', mysql.JSON, nullable=False, comment='未回收伏笔'),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
        comment='聚合记忆表'
    )
    
    # 创建 global_states 表
    op.create_table(
        'global_states',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('novel_id', sa.String(36), sa.ForeignKey('novels.id', ondelete='CASCADE'), nullable=False),
        sa.Column('snapshot_type', sa.String(20), nullable=False, comment='快照类型：章节/10章/卷'),
        sa.Column('chapter_number', sa.Integer, nullable=True, comment='快照时的章节号'),
        sa.Column('volume_id', sa.String(36), sa.ForeignKey('volumes.id', ondelete='SET NULL'), nullable=True),
        sa.Column('character_states', mysql.JSON, nullable=False, comment='角色状态表'),
        sa.Column('item_ownership', mysql.JSON, nullable=False, comment='道具归属表'),
        sa.Column('event_timeline', mysql.JSON, nullable=False, comment='事件时间线'),
        sa.Column('foreshadowing_tracker', mysql.JSON, nullable=False, comment='伏笔追踪表'),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
        comment='全局状态快照表'
    )
    
    # 创建 impact_reports 表
    op.create_table(
        'impact_reports',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('novel_id', sa.String(36), sa.ForeignKey('novels.id', ondelete='CASCADE'), nullable=False),
        sa.Column('change_type', sa.String(20), nullable=False, comment='变更类型：outline/character/worldbuilding'),
        sa.Column('change_target_id', sa.String(36), nullable=False, comment='变更目标ID'),
        sa.Column('affected_volumes', mysql.JSON, nullable=False, comment='受影响的分卷'),
        sa.Column('affected_chapters', mysql.JSON, nullable=False, comment='受影响的章节'),
        sa.Column('affected_characters', mysql.JSON, nullable=False, comment='受影响的角色'),
        sa.Column('conflicts', mysql.JSON, nullable=False, comment='检测到的矛盾'),
        sa.Column('suggestions', mysql.JSON, nullable=False, comment='联动修改建议'),
        sa.Column('status', sa.String(20), nullable=False, server_default='pending', comment='处理状态'),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column('resolved_at', sa.DateTime, nullable=True, comment='处理完成时间'),
        comment='变更影响分析报告表'
    )
    
    # 扩展 outlines 表
    op.add_column('outlines', sa.Column('confirmed_at', sa.DateTime, nullable=True, comment='确认时间'))
    op.add_column('outlines', sa.Column('confirmed_by', sa.String(36), nullable=True, comment='确认人ID'))
    
    # 扩展 entity_proposals 表
    op.add_column('entity_proposals', sa.Column('proposal_category', sa.String(20), nullable=True, comment='提案分类：setting/memory/linkage'))
    op.add_column('entity_proposals', sa.Column('priority', sa.Integer, nullable=False, server_default='3', comment='优先级 1-5'))
    
    # 创建索引
    op.create_index('idx_aggregated_memories_novel_type', 'aggregated_memories', ['novel_id', 'aggregation_type'])
    op.create_index('idx_global_states_novel_chapter', 'global_states', ['novel_id', 'chapter_number'])
    op.create_index('idx_impact_reports_novel_status', 'impact_reports', ['novel_id', 'status'])


def downgrade():
    # 删除索引
    op.drop_index('idx_impact_reports_novel_status', 'impact_reports')
    op.drop_index('idx_global_states_novel_chapter', 'global_states')
    op.drop_index('idx_aggregated_memories_novel_type', 'aggregated_memories')
    
    # 删除扩展字段
    op.drop_column('entity_proposals', 'priority')
    op.drop_column('entity_proposals', 'proposal_category')
    op.drop_column('outlines', 'confirmed_by')
    op.drop_column('outlines', 'confirmed_at')
    
    # 删除表
    op.drop_table('impact_reports')
    op.drop_table('global_states')
    op.drop_table('aggregated_memories')
```

#### 2.2 数据迁移脚本

**现有项目数据迁移** (`scripts/migrate_existing_data.py`):

```python
"""
迁移现有项目数据到新表结构
"""
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models import Novel, Chapter, ChapterMemory, AggregatedMemory, GlobalState
from app.services.memory_aggregator import MemoryAggregator
from app.services.global_state_service import GlobalStateManager

def migrate_chapter_memories(db: Session):
    """
    为所有已定稿章节生成聚合记忆
    """
    novels = db.query(Novel).all()
    aggregator = MemoryAggregator()
    
    for novel in novels:
        print(f"Processing novel: {novel.title}")
        
        # 获取所有已定稿章节
        chapters = db.query(Chapter).filter(
            Chapter.novel_id == novel.id,
            Chapter.final_approved == True
        ).order_by(Chapter.chapter_number).all()
        
        if not chapters:
            continue
        
        # 每10章生成一个聚合记忆
        for i in range(0, len(chapters), 10):
            batch = chapters[i:i+10]
            start_chapter = batch[0].chapter_number
            end_chapter = batch[-1].chapter_number
            
            print(f"  Aggregating chapters {start_chapter}-{end_chapter}")
            
            try:
                aggregator.aggregate_10_chapters(
                    db=db,
                    novel_id=novel.id,
                    start_chapter=start_chapter,
                    end_chapter=end_chapter
                )
                db.commit()
            except Exception as e:
                print(f"  Error: {e}")
                db.rollback()

def migrate_global_states(db: Session):
    """
    为所有小说生成全局状态快照
    """
    novels = db.query(Novel).all()
    state_manager = GlobalStateManager()
    
    for novel in novels:
        print(f"Processing novel: {novel.title}")
        
        try:
            # 生成最新的全局状态快照
            state_manager.create_snapshot(
                db=db,
                novel_id=novel.id,
                snapshot_type="current"
            )
            db.commit()
        except Exception as e:
            print(f"  Error: {e}")
            db.rollback()

def main():
    db = SessionLocal()
    try:
        print("Starting data migration...")
        
        print("\n1. Migrating chapter memories...")
        migrate_chapter_memories(db)
        
        print("\n2. Migrating global states...")
        migrate_global_states(db)
        
        print("\nMigration completed successfully!")
    except Exception as e:
        print(f"\nMigration failed: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    main()
```

### 3. 向后兼容性保证

#### 3.1 API 兼容性

**版本控制策略**：
- 使用 URL 路径版本控制: `/api/v1/`, `/api/v2/`
- 保留旧版本 API 至少 6 个月
- 在响应头中标注 API 版本和弃用信息

**示例**：

```python
# 旧版本 API（保留）
@router.post("/api/v1/assistant/chat")
async def chat_v1(request: ChatRequestV1):
    # 兼容旧版本请求格式
    return legacy_chat_handler(request)

# 新版本 API
@router.post("/api/v2/assistant/chat")
async def chat_v2(request: ChatRequestV2):
    # 新版本实现
    return unified_assistant.chat(request)
```

#### 3.2 数据库兼容性

**原则**：
- 只新增表和字段，不删除现有表和字段
- 新增字段必须有默认值或允许 NULL
- 使用数据迁移脚本填充新字段的默认数据

**示例**：

```python
# 新增字段时提供默认值
op.add_column('outlines', 
    sa.Column('confirmed_at', sa.DateTime, nullable=True, comment='确认时间')
)

# 为现有数据填充默认值
op.execute("""
    UPDATE outlines 
    SET confirmed_at = created_at 
    WHERE confirmed_at IS NULL
""")
```

#### 3.3 文件存储兼容性

**原则**：
- 保留现有文件存储格式
- 新增文件类型使用新的目录结构
- 提供文件格式转换工具

**目录结构**：

```
storage/projects/{novel_id}/
├── outline.md                    # 旧格式（保留）
├── characters.json               # 旧格式（保留）
├── worldbuilding.json            # 旧格式（保留）
├── chapters/                     # 旧格式（保留）
│   └── chapter_001/
│       ├── content.md
│       └── synopsis.md
└── memory/                       # 新增目录
    ├── aggregated/
    │   ├── chapters_001_010.json
    │   └── volume_001.json
    └── global_states/
        └── latest.json
```


## Testing Strategy

### 1. 单元测试 (Unit Tests)

#### 1.1 后端单元测试

**测试框架**: pytest + pytest-asyncio

**测试覆盖范围**：
- 所有服务层函数
- 所有工具函数
- 数据模型验证
- API 路由处理

**测试示例** (`tests/services/test_impact_analyzer.py`):

```python
import pytest
from app.services.impact_analyzer import ImpactAnalyzer
from app.models import Outline, Volume, Character
from tests.fixtures import create_test_novel, create_test_outline

class TestImpactAnalyzer:
    @pytest.fixture
    def analyzer(self):
        return ImpactAnalyzer()
    
    @pytest.fixture
    def test_data(self, db_session):
        novel = create_test_novel(db_session)
        old_outline = create_test_outline(db_session, novel.id, theme="修仙")
        new_outline = create_test_outline(db_session, novel.id, theme="玄幻")
        return novel, old_outline, new_outline
    
    def test_analyze_outline_change_detects_theme_change(self, analyzer, test_data, db_session):
        """测试大纲主题变更检测"""
        novel, old_outline, new_outline = test_data
        
        report = analyzer.analyze_outline_change(
            db=db_session,
            novel_id=novel.id,
            old_outline=old_outline,
            new_outline=new_outline
        )
        
        assert report is not None
        assert report.change_type == "outline"
        assert len(report.affected_volumes) >= 0
        assert "theme" in str(report.conflicts)
    
    def test_analyze_character_change_detects_realm_change(self, analyzer, db_session):
        """测试角色境界变更检测"""
        character = create_test_character(db_session, name="主角", realm="炼气期")
        old_state = {"realm": "炼气期"}
        new_state = {"realm": "筑基期"}
        
        report = analyzer.analyze_character_change(
            db=db_session,
            novel_id=character.novel_id,
            character=character,
            old_state=old_state,
            new_state=new_state
        )
        
        assert report is not None
        assert report.change_type == "character"
        assert "realm" in str(report.conflicts)
    
    def test_generate_linkage_proposals(self, analyzer, test_data, db_session):
        """测试联动修改方案生成"""
        novel, old_outline, new_outline = test_data
        
        report = analyzer.analyze_outline_change(
            db=db_session,
            novel_id=novel.id,
            old_outline=old_outline,
            new_outline=new_outline
        )
        
        proposals = analyzer.generate_linkage_proposals(db_session, report)
        
        assert isinstance(proposals, list)
        for proposal in proposals:
            assert "target_type" in proposal
            assert "target_id" in proposal
            assert "action" in proposal
            assert "reason" in proposal
```

**测试覆盖率目标**：
- 核心服务层: > 90%
- 工具函数: > 85%
- API 路由: > 80%
- 总体覆盖率: > 85%

**运行测试**：

```bash
# 运行所有测试
pytest

# 运行特定测试文件
pytest tests/services/test_impact_analyzer.py

# 运行并生成覆盖率报告
pytest --cov=app --cov-report=html

# 运行并显示详细输出
pytest -v -s
```

#### 1.2 前端单元测试

**测试框架**: Vitest + React Testing Library

**测试覆盖范围**：
- 所有组件渲染
- 用户交互逻辑
- 状态管理
- API 调用 mock

**测试示例** (`tests/components/UnifiedAssistantUI.test.tsx`):

```typescript
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { UnifiedAssistantUI } from '@/components/UnifiedAssistantUI';
import * as api from '@/services/api';

vi.mock('@/services/api');

describe('UnifiedAssistantUI', () => {
  it('renders chat interface', () => {
    render(
      <UnifiedAssistantUI
        novelId="test-novel-id"
        contextType="outline"
      />
    );
    
    expect(screen.getByPlaceholderText(/输入消息/i)).toBeInTheDocument();
  });
  
  it('sends message and displays response', async () => {
    const mockResponse = {
      response: 'AI 回复内容',
      context_files: [],
      suggestions: null,
      impact_report: null
    };
    
    vi.spyOn(api, 'post').mockResolvedValue({ data: mockResponse });
    
    render(
      <UnifiedAssistantUI
        novelId="test-novel-id"
        contextType="outline"
      />
    );
    
    const input = screen.getByPlaceholderText(/输入消息/i);
    fireEvent.change(input, { target: { value: '测试消息' } });
    fireEvent.keyPress(input, { key: 'Enter', code: 13, charCode: 13 });
    
    await waitFor(() => {
      expect(screen.getByText('AI 回复内容')).toBeInTheDocument();
    });
  });
  
  it('displays impact report when provided', async () => {
    const mockResponse = {
      response: 'AI 回复内容',
      context_files: [],
      suggestions: null,
      impact_report: {
        report_id: 'test-report-id',
        summary: '影响摘要'
      }
    };
    
    vi.spyOn(api, 'post').mockResolvedValue({ data: mockResponse });
    
    render(
      <UnifiedAssistantUI
        novelId="test-novel-id"
        contextType="outline"
      />
    );
    
    const input = screen.getByPlaceholderText(/输入消息/i);
    fireEvent.change(input, { target: { value: '修改大纲' } });
    fireEvent.keyPress(input, { key: 'Enter', code: 13, charCode: 13 });
    
    await waitFor(() => {
      expect(screen.getByText('影响摘要')).toBeInTheDocument();
    });
  });
});
```

### 2. 集成测试 (Integration Tests)

#### 2.1 API 集成测试

**测试框架**: pytest + httpx

**测试覆盖范围**：
- 完整的 API 请求-响应流程
- 数据库事务完整性
- 文件存储操作
- 错误处理和边界情况

**测试示例** (`tests/integration/test_assistant_api.py`):

```python
import pytest
from httpx import AsyncClient
from app.main import app
from tests.fixtures import create_test_novel, create_test_user

@pytest.mark.asyncio
class TestAssistantAPI:
    async def test_chat_with_outline_context(self, async_client: AsyncClient, test_user, test_novel):
        """测试大纲上下文的 AI 对话"""
        response = await async_client.post(
            "/api/assistant/chat",
            json={
                "novel_id": test_novel.id,
                "context_type": "outline",
                "context_id": None,
                "user_message": "帮我生成分卷规划",
                "selected_file_ids": [],
                "conversation_history": []
            },
            headers={"Authorization": f"Bearer {test_user.token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "response" in data
        assert "context_files" in data
        assert isinstance(data["context_files"], list)
    
    async def test_chat_triggers_impact_analysis(self, async_client: AsyncClient, test_user, test_novel):
        """测试 AI 对话触发影响分析"""
        response = await async_client.post(
            "/api/assistant/chat",
            json={
                "novel_id": test_novel.id,
                "context_type": "outline",
                "context_id": None,
                "user_message": "把主角从废柴改成天才",
                "selected_file_ids": [],
                "conversation_history": []
            },
            headers={"Authorization": f"Bearer {test_user.token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "impact_report" in data
        assert data["impact_report"] is not None
        assert "report_id" in data["impact_report"]
    
    async def test_chat_with_invalid_novel_id(self, async_client: AsyncClient, test_user):
        """测试无效小说 ID 的错误处理"""
        response = await async_client.post(
            "/api/assistant/chat",
            json={
                "novel_id": "invalid-id",
                "context_type": "outline",
                "context_id": None,
                "user_message": "测试消息",
                "selected_file_ids": [],
                "conversation_history": []
            },
            headers={"Authorization": f"Bearer {test_user.token}"}
        )
        
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()
```

#### 2.2 端到端测试 (E2E Tests)

**测试框架**: Playwright

**测试覆盖范围**：
- 完整的用户操作流程
- 跨页面交互
- 实时更新和通知
- 浏览器兼容性

**测试示例** (`tests/e2e/outline-workflow.spec.ts`):

```typescript
import { test, expect } from '@playwright/test';

test.describe('Outline Workflow', () => {
  test.beforeEach(async ({ page }) => {
    // 登录
    await page.goto('/login');
    await page.fill('input[name="username"]', 'testuser');
    await page.fill('input[name="password"]', 'testpass');
    await page.click('button[type="submit"]');
    await page.waitForURL('/novels');
    
    // 创建测试小说
    await page.click('text=创建小说');
    await page.fill('input[name="title"]', '测试小说');
    await page.click('button:has-text("确定")');
    await page.waitForURL(/\/novels\/[^/]+\/outline/);
  });
  
  test('complete outline confirmation flow', async ({ page }) => {
    // 1. 编辑大纲
    await page.fill('textarea[name="theme"]', '修仙世界');
    await page.fill('textarea[name="main_conflict"]', '主角逆天改命');
    await page.click('button:has-text("保存")');
    
    // 2. 确认大纲
    await page.click('button:has-text("确认大纲")');
    await page.click('button:has-text("确定")'); // 确认对话框
    
    // 3. 验证门禁解锁
    await page.click('text=角色管理');
    await expect(page.locator('.gate-prompt-overlay')).not.toBeVisible();
    
    // 4. 验证可以创建角色
    await page.click('button:has-text("创建角色")');
    await expect(page.locator('input[name="character_name"]')).toBeVisible();
  });
  
  test('outline change triggers impact analysis', async ({ page }) => {
    // 1. 确认初始大纲
    await page.fill('textarea[name="theme"]', '修仙世界');
    await page.click('button:has-text("确认大纲")');
    await page.click('button:has-text("确定")');
    
    // 2. 生成分卷
    await page.click('text=分卷规划');
    await page.click('button:has-text("生成分卷")');
    await page.waitForSelector('text=第一卷');
    
    // 3. 修改大纲
    await page.click('text=大纲');
    await page.fill('textarea[name="theme"]', '玄幻世界');
    await page.click('button:has-text("保存")');
    
    // 4. 验证影响分析报告
    await expect(page.locator('.impact-report-card')).toBeVisible();
    await expect(page.locator('text=受影响的分卷')).toBeVisible();
    
    // 5. 查看详情
    await page.click('button:has-text("查看详情")');
    await expect(page.locator('.impact-report-detail')).toBeVisible();
  });
});
```

### 3. Property-Based Testing (PBT) 策略

#### 3.1 PBT 适用场景

**核心算法测试**：
- 文本相似度计算
- 事件去重算法
- 状态合并逻辑
- 上下文注入策略

**数据一致性测试**：
- 聚合记忆的完整性
- 全局状态的一致性
- 关系网的传递性

#### 3.2 PBT 测试示例

**测试框架**: Hypothesis

**测试示例** (`tests/pbt/test_memory_aggregation.py`):

```python
import pytest
from hypothesis import given, strategies as st
from app.services.memory_aggregator import MemoryAggregator, deduplicate_events

# 定义事件策略
event_strategy = st.fixed_dictionaries({
    'chapter': st.integers(min_value=1, max_value=100),
    'event': st.text(min_size=10, max_size=100),
    'timestamp': st.datetimes()
})

@given(st.lists(event_strategy, min_size=1, max_size=50))
def test_deduplicate_events_preserves_unique_events(events):
    """
    属性：去重后的事件列表不应包含重复事件
    """
    deduplicated = deduplicate_events(events, threshold=0.85)
    
    # 检查去重后的事件列表中没有高度相似的事件对
    for i, event1 in enumerate(deduplicated):
        for event2 in deduplicated[i+1:]:
            similarity = compute_text_similarity(event1['event'], event2['event'])
            assert similarity < 0.85, f"Found duplicate events: {event1}, {event2}"

@given(st.lists(event_strategy, min_size=1, max_size=50))
def test_deduplicate_events_preserves_order(events):
    """
    属性：去重应保持事件的时间顺序
    """
    deduplicated = deduplicate_events(events, threshold=0.85)
    
    # 检查去重后的事件按时间排序
    for i in range(len(deduplicated) - 1):
        assert deduplicated[i]['timestamp'] <= deduplicated[i+1]['timestamp']

@given(
    st.integers(min_value=1, max_value=10),  # start_chapter
    st.integers(min_value=1, max_value=10)   # chapter_count
)
def test_aggregate_10_chapters_completeness(start_chapter, chapter_count):
    """
    属性：聚合记忆应包含所有章节的关键信息
    """
    end_chapter = start_chapter + chapter_count - 1
    
    # 创建测试数据
    chapter_memories = create_test_chapter_memories(start_chapter, end_chapter)
    
    # 执行聚合
    aggregator = MemoryAggregator()
    aggregated = aggregator.aggregate_chapters(chapter_memories)
    
    # 验证完整性
    assert aggregated.start_chapter == start_chapter
    assert aggregated.end_chapter == end_chapter
    assert len(aggregated.key_events) > 0
    assert len(aggregated.state_snapshot) >= 0
    
    # 验证所有章节的关键事件都被包含
    all_events = []
    for memory in chapter_memories:
        all_events.extend(memory.key_events)
    
    for event in all_events:
        # 检查事件是否在聚合结果中（允许去重）
        found = any(
            compute_text_similarity(event, agg_event['event']) > 0.85
            for agg_event in aggregated.key_events
        )
        assert found, f"Event not found in aggregated memory: {event}"
```

#### 3.3 正确性属性定义

**记忆聚合的正确性属性**：

1. **完整性 (Completeness)**：
   - 聚合记忆应包含所有输入章节的关键信息
   - 不应丢失重要事件

2. **一致性 (Consistency)**：
   - 状态变化应保持时间顺序
   - 最终状态应反映最新的变化

3. **去重性 (Deduplication)**：
   - 相似事件应被合并
   - 去重后不应有高度相似的事件对

4. **可逆性 (Reversibility)**：
   - 从聚合记忆应能还原出原始章节的关键信息
   - 信息损失应在可接受范围内

**影响分析的正确性属性**：

1. **覆盖性 (Coverage)**：
   - 所有受影响的内容都应被检测到
   - 不应遗漏任何受影响的实体

2. **准确性 (Accuracy)**：
   - 检测到的影响应是真实的
   - 不应产生过多的误报

3. **传递性 (Transitivity)**：
   - 如果 A 影响 B，B 影响 C，则 A 应影响 C
   - 关系网的传递性应被正确处理

### 4. 性能测试

#### 4.1 负载测试

**测试工具**: Locust

**测试场景**：

```python
from locust import HttpUser, task, between

class NovelEditorUser(HttpUser):
    wait_time = between(1, 3)
    
    def on_start(self):
        # 登录
        response = self.client.post("/api/auth/login", json={
            "username": "testuser",
            "password": "testpass"
        })
        self.token = response.json()["token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    @task(3)
    def chat_with_assistant(self):
        """AI 对话（高频操作）"""
        self.client.post("/api/assistant/chat", json={
            "novel_id": "test-novel-id",
            "context_type": "outline",
            "user_message": "测试消息",
            "selected_file_ids": [],
            "conversation_history": []
        }, headers=self.headers)
    
    @task(1)
    def analyze_impact(self):
        """影响分析（中频操作）"""
        self.client.post("/api/impact/analyze", json={
            "novel_id": "test-novel-id",
            "change_type": "outline",
            "change_id": "test-outline-id",
            "old_content": "旧内容",
            "new_content": "新内容"
        }, headers=self.headers)
    
    @task(2)
    def list_proposals(self):
        """列出提案（中频操作）"""
        self.client.get("/api/review/proposals", params={
            "novel_id": "test-novel-id",
            "status": "pending"
        }, headers=self.headers)
```

**性能目标**：
- 并发用户数: 100-500
- 响应时间 (P95): < 2s
- 响应时间 (P99): < 5s
- 错误率: < 1%

#### 4.2 压力测试

**测试场景**：
- 逐步增加并发用户数，直到系统崩溃
- 记录系统的最大承载能力
- 分析瓶颈和优化方向

**测试命令**：

```bash
# 启动负载测试
locust -f tests/performance/locustfile.py --host=http://localhost:8000

# 命令行模式（无 UI）
locust -f tests/performance/locustfile.py --host=http://localhost:8000 \
  --users 500 --spawn-rate 10 --run-time 10m --headless
```

### 5. 测试自动化

#### 5.1 CI/CD 集成

**GitHub Actions 配置** (`.github/workflows/test.yml`):

```yaml
name: Test

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main, develop ]

jobs:
  backend-test:
    runs-on: ubuntu-latest
    
    services:
      mysql:
        image: mysql:8.0
        env:
          MYSQL_ROOT_PASSWORD: testpass
          MYSQL_DATABASE: test_db
        ports:
          - 3306:3306
        options: --health-cmd="mysqladmin ping" --health-interval=10s --health-timeout=5s --health-retries=3
      
      redis:
        image: redis:7-alpine
        ports:
          - 6379:6379
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          cd backend
          pip install -r requirements.txt
          pip install pytest pytest-cov pytest-asyncio
      
      - name: Run tests
        env:
          DATABASE_URL: mysql+pymysql://root:testpass@localhost:3306/test_db
          REDIS_URL: redis://localhost:6379/0
        run: |
          cd backend
          pytest --cov=app --cov-report=xml --cov-report=html
      
      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          file: ./backend/coverage.xml
  
  frontend-test:
    runs-on: ubuntu-latest
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Node.js
        uses: actions/setup-node@v3
        with:
          node-version: '18'
      
      - name: Install dependencies
        run: |
          cd frontend
          npm ci
      
      - name: Run tests
        run: |
          cd frontend
          npm run test:unit
      
      - name: Run E2E tests
        run: |
          cd frontend
          npm run test:e2e
```

#### 5.2 测试报告

**覆盖率报告**：
- 使用 Codecov 或 Coveralls 展示覆盖率
- 在 PR 中自动评论覆盖率变化
- 设置覆盖率阈值，低于阈值则 CI 失败

**测试结果通知**：
- 测试失败时发送邮件或 Slack 通知
- 在 PR 中展示测试结果摘要
- 生成测试报告并上传到 S3 或 GitHub Pages

