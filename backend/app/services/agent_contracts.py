from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


AssistantIntent = Literal[
    "generate_outline",
    "revise_outline",
    "rewrite_outline",
    "generate_synopsis",
    "revise_synopsis",
    "create_character",
    "revise_character",
    "revise_worldbuilding",
    "write_chapter",
    "revise_chapter",
    "continuity_check",
    "ask_question",
    "clarify",
    "reject",
]


class AgentFileRef(BaseModel):
    id: str = ""
    label: str = ""
    path: str = ""
    kind: str = ""
    status: str | None = None


class ClarificationQuestion(BaseModel):
    question: str
    options: list[str] = Field(default_factory=list)

    @field_validator("options")
    @classmethod
    def trim_options(cls, value: list[str]) -> list[str]:
        return [str(item).strip() for item in value if str(item).strip()][:6]


class IntentPlan(BaseModel):
    intent: AssistantIntent = "ask_question"
    confidence: float = Field(default=0.65, ge=0, le=1)
    needs_clarification: bool = False
    reason: str = "AI 已完成意图识别。"
    response_message: str = ""
    questions: list[ClarificationQuestion] = Field(default_factory=list)
    read_files: list[AgentFileRef] = Field(default_factory=list)
    write_targets: list[AgentFileRef] = Field(default_factory=list)

    def to_legacy_dict(self) -> dict[str, Any]:
        data = self.model_dump()
        data["questions"] = [item.model_dump() for item in self.questions[:5]]
        data["read_files"] = [item.model_dump() for item in self.read_files[:8]]
        data["write_targets"] = [item.model_dump() for item in self.write_targets[:8]]
        return data


class MemoryPack(BaseModel):
    source_files: list[AgentFileRef] = Field(default_factory=list)
    facts: list[str] = Field(default_factory=list)
    chapter_memories: list[str] = Field(default_factory=list)
    recent_runs: list[str] = Field(default_factory=list)
    search_terms: list[str] = Field(default_factory=list)

    def as_prompt(self) -> str:
        chunks: list[str] = []
        if self.facts:
            chunks.append("【长期事实】\n" + "\n".join(f"- {item}" for item in self.facts[:20]))
        if self.chapter_memories:
            chunks.append("【章节记忆】\n" + "\n".join(f"- {item}" for item in self.chapter_memories[:20]))
        if self.recent_runs:
            chunks.append("【最近 AI 工作】\n" + "\n".join(f"- {item}" for item in self.recent_runs[:8]))
        if self.source_files:
            chunks.append("【可引用文件】\n" + "\n".join(f"- {item.label}｜{item.path}｜{item.kind}" for item in self.source_files[:20]))
        return "\n\n".join(chunks) if chunks else "暂无长期记忆。"
