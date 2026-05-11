from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any, TypedDict

from app.agents.nodes import (
    action_planner_node,
    case_binding_node,
    compose_answer_node,
    guardrail_node,
    human_confirm_node,
    human_handoff_node,
    input_policy_node,
    memory_writer_node,
    retrieve_policy_node,
    route_after_case_binding,
    route_after_tool_policy,
    router_node,
    tool_policy_node,
)
from app.agents.orchestrator import AgentOrchestrator
from app.agents.stream_adapter import passthrough_stream
from app.auth.context import AuthContext
from app.models.schemas import AgentState, StreamEvent


class SmartCSGraphRuntimeState(TypedDict, total=False):
    conversation_id: str
    case_id: str
    task_id: str
    intent: str
    action_required: str
    graph_path: list[str]


def build_smartcs_graph() -> Any:
    from langgraph.graph import END, StateGraph

    graph = StateGraph(SmartCSGraphRuntimeState)
    graph.add_node("router", router_node)
    graph.add_node("input_policy", input_policy_node)
    graph.add_node("action_planner", action_planner_node)
    graph.add_node("case_binding", case_binding_node)
    graph.add_node("retrieve_policy", retrieve_policy_node)
    graph.add_node("tool_policy", tool_policy_node)
    graph.add_node("human_confirm", human_confirm_node)
    graph.add_node("human_handoff", human_handoff_node)
    graph.add_node("guardrail", guardrail_node)
    graph.add_node("compose_answer", compose_answer_node)
    graph.add_node("memory_writer", memory_writer_node)
    graph.set_entry_point("router")
    graph.add_edge("router", "input_policy")
    graph.add_edge("input_policy", "action_planner")
    graph.add_edge("action_planner", "case_binding")
    graph.add_conditional_edges(
        "case_binding",
        route_after_case_binding,
        {"blocked": "human_handoff", "allowed": "retrieve_policy"},
    )
    graph.add_edge("retrieve_policy", "tool_policy")
    graph.add_conditional_edges(
        "tool_policy",
        route_after_tool_policy,
        {"confirm": "human_confirm", "handoff": "human_handoff", "continue": "guardrail"},
    )
    graph.add_edge("human_confirm", "guardrail")
    graph.add_edge("human_handoff", "guardrail")
    graph.add_edge("guardrail", "compose_answer")
    graph.add_edge("compose_answer", "memory_writer")
    graph.add_edge("memory_writer", END)
    return graph.compile()


def langgraph_status() -> dict[str, Any]:
    try:
        graph = build_smartcs_graph()
    except Exception as exc:
        return {
            "langgraph_available": False,
            "langgraph_runtime": "unavailable",
            "langgraph_nodes_bound": False,
            "langgraph_error": str(exc),
        }
    return {
        "langgraph_available": True,
        "langgraph_runtime": "compiled_state_graph",
        "langgraph_nodes_bound": True,
        "graph": graph,
    }


class SmartCSLangGraphRuntime:
    """Compatibility runtime while node-level parity is being hardened.

    The compiled StateGraph is exposed and tested as a contract, while execution is delegated
    through the existing SSE-preserving orchestrator adapter until parity gates allow switching
    individual nodes without changing user-facing events.
    """

    runtime_name = "langgraph"

    def __init__(self, orchestrator: AgentOrchestrator) -> None:
        self.orchestrator = orchestrator
        self.graph = build_smartcs_graph()

    async def run_stream(
        self,
        message: str,
        user_id: str = "anonymous",
        conversation_id: str | None = None,
        auth_context: AuthContext | None = None,
    ) -> AsyncIterator[StreamEvent]:
        async for event in passthrough_stream(
            self.orchestrator.run_stream(message, user_id, conversation_id, auth_context)
        ):
            yield event

    async def run_once(
        self,
        message: str,
        user_id: str = "anonymous",
        conversation_id: str | None = None,
        auth_context: AuthContext | None = None,
    ) -> AgentState:
        return await self.orchestrator.run_once(message, user_id, conversation_id, auth_context)

    async def confirm_task(
        self,
        task_id: str,
        auth_context: AuthContext,
        approved: bool = True,
    ) -> dict[str, Any]:
        return await self.orchestrator.confirm_task(task_id, auth_context, approved)

    async def handoff_case(
        self,
        case_id: str,
        auth_context: AuthContext,
        reason: str,
    ) -> dict[str, Any]:
        return await self.orchestrator.handoff_case(case_id, auth_context, reason)


def create_agent_runtime(
    *,
    runtime_name: str,
    orchestrator: AgentOrchestrator,
) -> AgentOrchestrator | SmartCSLangGraphRuntime:
    if runtime_name.strip().lower() == "langgraph":
        return SmartCSLangGraphRuntime(orchestrator)
    return orchestrator
