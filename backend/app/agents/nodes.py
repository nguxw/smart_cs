from __future__ import annotations

from typing import Any

from app.models.schemas import StreamEvent


async def _run_graph_node(
    graph_state: dict[str, Any],
    node_name: str,
    handler_name: str,
) -> dict[str, Any]:
    runtime = graph_state["runtime"]
    agent_state = graph_state["agent_state"]
    steps = graph_state.setdefault("steps", [])
    node_events: list[StreamEvent] = []
    handler = getattr(runtime, handler_name)
    async for event in runtime._run_node(node_name, agent_state, steps, handler):
        node_events.append(event)
    return {
        "runtime": runtime,
        "agent_state": agent_state,
        "steps": steps,
        "node_events": node_events,
    }


async def router_node(state: Any) -> Any:
    return await _run_graph_node(state, "router", "_router")


async def input_policy_node(state: Any) -> Any:
    return await _run_graph_node(state, "input_policy", "_input_policy")


async def action_planner_node(state: Any) -> Any:
    return await _run_graph_node(state, "action_planner", "_action_planner")


async def case_binding_node(state: Any) -> Any:
    return await _run_graph_node(state, "case_binding", "_case_binding")


async def retrieve_policy_node(state: Any) -> Any:
    return await _run_graph_node(state, "retrieve_policy", "_retrieve_policy")


async def tool_policy_node(state: Any) -> Any:
    return await _run_graph_node(state, "tool_policy", "_business_action")


async def human_confirm_node(state: Any) -> Any:
    return await _run_graph_node(state, "human_confirm", "_human_confirmation")


async def human_handoff_node(state: Any) -> Any:
    return await _run_graph_node(state, "human_handoff", "_human_handoff")


async def skip_optional_nodes(state: Any) -> Any:
    runtime = state["runtime"]
    agent_state = state["agent_state"]
    steps = state.setdefault("steps", [])
    node_events: list[StreamEvent] = []
    async for event in runtime._skip_node("human_confirm", agent_state, steps, "no confirmation"):
        node_events.append(event)
    async for event in runtime._skip_node("human_handoff", agent_state, steps, "no handoff"):
        node_events.append(event)
    return {
        "runtime": runtime,
        "agent_state": agent_state,
        "steps": steps,
        "node_events": node_events,
    }


async def guardrail_node(state: Any) -> Any:
    return await _run_graph_node(state, "guardrail", "_guardrail")


async def compose_answer_node(state: Any) -> Any:
    return await _run_graph_node(state, "compose_answer", "_answer_composer")


async def memory_writer_node(state: Any) -> Any:
    return await _run_graph_node(state, "memory_writer", "_memory_writer")


def route_after_case_binding(state: Any) -> str:
    agent_state = state.get("agent_state") if isinstance(state, dict) else state
    guardrail = getattr(agent_state, "guardrail_result", None)
    if guardrail and getattr(guardrail, "blocked", False):
        return "blocked"
    return "allowed"


def route_after_tool_policy(state: Any) -> str:
    if isinstance(state, dict):
        agent_state = state.get("agent_state")
        if agent_state is not None:
            if agent_state.pending_confirmation:
                return "confirm"
            if agent_state.intent in {"ticket", "handoff"} or agent_state.metadata.get(
                "needs_ticket"
            ):
                return "handoff"
            return "continue"
        if state.get("pending_confirmation"):
            return "confirm"
        if state.get("intent") in {"ticket", "handoff"} or state.get("needs_ticket"):
            return "handoff"
        return "continue"
    if state.pending_confirmation:
        return "confirm"
    if state.intent in {"ticket", "handoff"} or state.metadata.get("needs_ticket"):
        return "handoff"
    return "continue"


def route_after_handoff(state: Any) -> str:
    agent_state = state.get("agent_state") if isinstance(state, dict) else state
    guardrail = getattr(agent_state, "guardrail_result", None)
    if guardrail and getattr(guardrail, "blocked", False):
        return "blocked"
    return "continue"


def route_after_compose_answer(state: Any) -> str:
    agent_state = state.get("agent_state") if isinstance(state, dict) else state
    guardrail = getattr(agent_state, "guardrail_result", None)
    if guardrail and getattr(guardrail, "blocked", False):
        return "blocked"
    return "continue"
