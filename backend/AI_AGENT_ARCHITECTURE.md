# AI Agent Architecture

本项目的 AI 底层不依赖 Dify。核心目标是把小说创作做成可审计、可恢复、可审批的代码级 Agent 系统。

## Runtime

- `model_gateway.py`：统一模型网关。业务代码不直接调用豆包、OpenAI、Claude 等提供商。
- `structured_output_service.py`：Pydantic 结构化输出与 JSON 自动修复，最多重试 3 次。
- `assistant_graph_runtime.py`：LangGraph 形态的图执行器。安装 `langgraph` 后优先使用 LangGraph；未安装时使用内置轻量图执行器，保证本地开发可启动。
- `ai_workflow_service.py`：小说 Agent 主流程，负责意图识别、追问、记忆装载、门禁、执行和结果落审。

## Memory

项目不依赖模型自带长期记忆。长期记忆由产品自己保存和检索：

- 正式大纲、简介、角色、世界观、分卷、章节正文。
- 章节定稿后的 `ChapterMemory`。
- 最近 AI 工作流记录。
- 用户可配置的提示词与工作流策略。

`agent_memory_service.py` 会在每次 Agent 执行前组合这些资料，形成本次上下文。

## Write Safety

AI 不允许直接删除、覆盖或正式写入核心内容。

- 文本类内容先进入编辑器待确认草稿。
- 角色、道具、地点、势力等卡片类内容先生成提案。
- 大纲未确认前，简介、角色、世界观、正文等写入会被门禁拦截。
- 所有工作流步骤会记录到 `AIWorkflowRun` 和 `AIWorkflowStep`。

## Provider Expansion

后续接入新模型时，只需要扩展：

1. 后台模型配置中的 provider/model。
2. `model_gateway.py` 中非 OpenAI-compatible provider 的适配器。
3. 如需成本统计、缓存命中、fallback 策略，也统一放在模型网关层。
