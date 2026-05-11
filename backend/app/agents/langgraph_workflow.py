from __future__ import annotations

from typing import Any, TypedDict

from app.agents.graph_runtime import langgraph_status
from app.core.config import settings


class SmartCSGraphState(TypedDict, total=False):
    conversation_id: str
    case_id: str
    task_id: str
    intent: str
    action_required: str


def build_langgraph_metadata() -> dict[str, Any]:
    """Expose the SmartCS live graph contract and runtime metadata."""

    nodes = [
        "router",
        "input_policy",
        "action_planner",
        "case_binding",
        "retrieve_policy",
        "tool_policy",
        "human_confirm",
        "human_handoff",
        "skip_optional",
        "guardrail",
        "compose_answer",
        "memory_writer",
    ]
    edges = [
        {"source": "router", "target": "input_policy", "condition": "always"},
        {"source": "input_policy", "target": "action_planner", "condition": "always"},
        {"source": "action_planner", "target": "case_binding", "condition": "always"},
        {"source": "case_binding", "target": "human_handoff", "condition": "input_blocked"},
        {"source": "case_binding", "target": "retrieve_policy", "condition": "input_allowed"},
        {"source": "retrieve_policy", "target": "tool_policy", "condition": "always"},
        {"source": "tool_policy", "target": "human_confirm", "condition": "pending_confirmation"},
        {"source": "tool_policy", "target": "human_handoff", "condition": "needs_handoff"},
        {"source": "tool_policy", "target": "skip_optional", "condition": "auto_resolved"},
        {"source": "human_confirm", "target": "guardrail", "condition": "interrupt_waiting"},
        {"source": "human_handoff", "target": "compose_answer", "condition": "input_blocked"},
        {"source": "human_handoff", "target": "guardrail", "condition": "ticket_created"},
        {"source": "skip_optional", "target": "guardrail", "condition": "no_interrupt"},
        {"source": "guardrail", "target": "compose_answer", "condition": "always"},
        {"source": "compose_answer", "target": "END", "condition": "input_blocked"},
        {"source": "compose_answer", "target": "memory_writer", "condition": "input_allowed"},
        {"source": "memory_writer", "target": "END", "condition": "always"},
    ]
    metadata: dict[str, Any] = {
        "nodes": nodes,
        "edges": edges,
        "interrupt_nodes": ["human_confirm"],
        "checkpoint_fields": ["conversation_id", "case_id", "task_id", "resume_token"],
        "execution_mode": "langgraph_state_graph"
        if settings.agent_runtime.strip().lower() == "langgraph"
        else "orchestrator_sequence",
        "default_runtime": settings.agent_runtime,
        "langgraph_available": False,
        "langgraph_runtime": "metadata_only",
        "langgraph_nodes_bound": False,
    }
    status = langgraph_status()
    metadata.update({key: value for key, value in status.items() if key != "graph"})
    metadata["graph"] = None
    return metadata
