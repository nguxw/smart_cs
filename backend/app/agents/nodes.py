from __future__ import annotations

from typing import Any


async def router_node(state: Any) -> Any:
    return state


async def input_policy_node(state: Any) -> Any:
    return state


async def action_planner_node(state: Any) -> Any:
    return state


async def case_binding_node(state: Any) -> Any:
    return state


async def retrieve_policy_node(state: Any) -> Any:
    return state


async def tool_policy_node(state: Any) -> Any:
    return state


async def human_confirm_node(state: Any) -> Any:
    return state


async def human_handoff_node(state: Any) -> Any:
    return state


async def guardrail_node(state: Any) -> Any:
    return state


async def compose_answer_node(state: Any) -> Any:
    return state


async def memory_writer_node(state: Any) -> Any:
    return state


def route_after_case_binding(state: Any) -> str:
    guardrail = state.get("guardrail_result") if isinstance(state, dict) else None
    if guardrail and getattr(guardrail, "blocked", False):
        return "blocked"
    return "allowed"


def route_after_tool_policy(state: Any) -> str:
    if isinstance(state, dict):
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
