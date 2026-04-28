from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from pydantic import BaseModel, Field


class AssistantGraphState(BaseModel):
    payload: dict[str, Any]
    plan: dict[str, Any] | None = None
    gate: dict[str, Any] | None = None
    result: dict[str, Any] | None = None
    memory: dict[str, Any] | None = None
    next_node: str | None = None


NodeFunc = Callable[[AssistantGraphState], Awaitable[AssistantGraphState]]


@dataclass
class AssistantGraphRuntime:
    """Small graph runner with a LangGraph-shaped boundary.

    LangGraph can replace this runner later without changing service nodes.
    The important product contract is already graph-based: named nodes, state,
    conditional jumps and resumable DB step logs.
    """

    nodes: dict[str, NodeFunc] = field(default_factory=dict)
    edges: dict[str, str] = field(default_factory=dict)
    start_node: str = "classify"
    max_steps: int = 20
    prefer_langgraph: bool = True

    def add_node(self, name: str, func: NodeFunc) -> None:
        self.nodes[name] = func

    def add_edge(self, source: str, target: str) -> None:
        self.edges[source] = target

    async def run(self, state: AssistantGraphState) -> AssistantGraphState:
        if self.prefer_langgraph:
            try:
                langgraph_runtime = self._compile_langgraph()
            except ModuleNotFoundError:
                langgraph_runtime = None
            except ImportError:
                langgraph_runtime = None
            except Exception:
                langgraph_runtime = None
            if langgraph_runtime is not None:
                result = await langgraph_runtime.ainvoke(state)
                if isinstance(result, AssistantGraphState):
                    return result
                return AssistantGraphState.model_validate(result)
        node_name = self.start_node
        visited = 0
        while node_name != "end":
            visited += 1
            if visited > self.max_steps:
                raise RuntimeError("AI 工作流步骤过多，已中止以避免循环。")
            node = self.nodes.get(node_name)
            if not node:
                raise RuntimeError(f"AI 工作流节点不存在：{node_name}")
            state = await node(state)
            node_name = state.next_node or self.edges.get(node_name) or "end"
            state.next_node = None
        return state

    def _compile_langgraph(self):
        from langgraph.graph import END, StateGraph

        graph = StateGraph(AssistantGraphState)
        node_names = set(self.nodes.keys())

        for name, node in self.nodes.items():
            graph.add_node(name, node)

        graph.set_entry_point(self.start_node)

        def make_router(source: str):
            def route(next_state: AssistantGraphState) -> str:
                target = next_state.next_node or self.edges.get(source) or "end"
                return "end" if target == "end" else target

            return route

        path_map = {name: name for name in node_names}
        path_map["end"] = END
        for name in node_names:
            graph.add_conditional_edges(name, make_router(name), path_map)

        return graph.compile()


def create_runtime() -> AssistantGraphRuntime:
    return AssistantGraphRuntime()
