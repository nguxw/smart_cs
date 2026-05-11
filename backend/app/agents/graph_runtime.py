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
    route_after_compose_answer,
    route_after_handoff,
    route_after_tool_policy,
    router_node,
    skip_optional_nodes,
    tool_policy_node,
)
from app.agents.orchestrator import AgentOrchestrator
from app.auth.context import AuthContext, build_dev_auth_context
from app.models.schemas import AgentState, AgentStep, ChatMessage, StreamEvent


class SmartCSGraphRuntimeState(TypedDict, total=False):
    runtime: Any
    agent_state: AgentState
    steps: list[AgentStep]
    node_events: list[StreamEvent]


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
    graph.add_node("skip_optional", skip_optional_nodes)
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
        {"confirm": "human_confirm", "handoff": "human_handoff", "continue": "skip_optional"},
    )
    graph.add_edge("human_confirm", "guardrail")
    graph.add_conditional_edges(
        "human_handoff",
        route_after_handoff,
        {"blocked": "compose_answer", "continue": "guardrail"},
    )
    graph.add_edge("skip_optional", "guardrail")
    graph.add_edge("guardrail", "compose_answer")
    graph.add_conditional_edges(
        "compose_answer",
        route_after_compose_answer,
        {"blocked": END, "continue": "memory_writer"},
    )
    graph.add_edge("memory_writer", END)
    return graph.compile()


def langgraph_status() -> dict[str, Any]:
    node_names = [
        "router",
        "input_policy",
        "action_planner",
        "case_binding",
        "retrieve_policy",
        "tool_policy",
        "human_confirm",
        "human_handoff",
        "guardrail",
        "skip_optional",
        "compose_answer",
        "memory_writer",
    ]
    try:
        graph = build_smartcs_graph()
    except Exception as exc:
        return {
            "langgraph_available": False,
            "langgraph_runtime": "unavailable",
            "langgraph_nodes_bound": False,
            "node_names": node_names,
            "edge_count": 17,
            "langgraph_error": str(exc),
        }
    return {
        "langgraph_available": True,
        "langgraph_runtime": "live_state_graph",
        "langgraph_nodes_bound": True,
        "node_names": node_names,
        "edge_count": 17,
        "graph": graph,
    }


class SmartCSLangGraphRuntime:
    """Live LangGraph runtime that executes SmartCS node handlers through StateGraph."""

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
        auth = auth_context or build_dev_auth_context(None, user_id)
        conversation = self.orchestrator._get_or_create_conversation(conversation_id, auth)
        prior_messages = list(conversation.messages)
        user_message = ChatMessage(role="user", content=message)
        self.orchestrator.repository.append_message(conversation.id, user_message)
        agent_state = AgentState(
            messages=[*prior_messages, user_message],
            user_profile=self.orchestrator.repository.get_user_profile(auth.user_id),
            auth_context=auth.to_dict(),
            conversation_id=conversation.id,
        )
        steps: list[AgentStep] = []
        graph_state: SmartCSGraphRuntimeState = {
            "runtime": self.orchestrator,
            "agent_state": agent_state,
            "steps": steps,
            "node_events": [],
        }

        async for update in self.graph.astream(graph_state, stream_mode="updates"):
            for event in _extract_node_events(update):
                yield event

        async for event in self.orchestrator._finalize(agent_state, steps):
            yield event

    async def run_once(
        self,
        message: str,
        user_id: str = "anonymous",
        conversation_id: str | None = None,
        auth_context: AuthContext | None = None,
    ) -> AgentState:
        final: AgentState | None = None
        async for event in self.run_stream(message, user_id, conversation_id, auth_context):
            if event.event == "final":
                final = event.data["state"]
        if final is None:  # pragma: no cover - defensive
            raise RuntimeError("Agent run did not finalize")
        return final

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


def _extract_node_events(update: Any) -> list[StreamEvent]:
    if isinstance(update, dict):
        if "node_events" in update:
            return [event for event in update["node_events"] if isinstance(event, StreamEvent)]
        events: list[StreamEvent] = []
        for value in update.values():
            events.extend(_extract_node_events(value))
        return events
    return []
