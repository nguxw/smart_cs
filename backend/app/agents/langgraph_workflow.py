from __future__ import annotations

from typing import Any, TypedDict


class SmartCSGraphState(TypedDict, total=False):
    conversation_id: str
    case_id: str
    task_id: str
    intent: str
    action_required: str


def build_langgraph_metadata() -> dict[str, Any]:
    """Expose the SmartCS workflow contract used by the current orchestrator.

    The production path is still driven by AgentOrchestrator. This metadata is
    intentionally explicit so the future LangGraph migration has a testable
    node, edge, interrupt, and checkpoint contract without claiming that the
    installed runtime is already executing real LangGraph nodes.
    """

    nodes = [
        "router",
        "input_policy",
        "case_binding",
        "retrieve_policy",
        "tool_policy",
        "human_confirm",
        "human_handoff",
        "guardrail",
        "compose_answer",
        "memory_writer",
    ]
    edges = [
        {"source": "router", "target": "input_policy", "condition": "always"},
        {"source": "input_policy", "target": "case_binding", "condition": "always"},
        {"source": "case_binding", "target": "human_handoff", "condition": "input_blocked"},
        {"source": "case_binding", "target": "retrieve_policy", "condition": "input_allowed"},
        {"source": "retrieve_policy", "target": "tool_policy", "condition": "always"},
        {"source": "tool_policy", "target": "human_confirm", "condition": "pending_confirmation"},
        {"source": "tool_policy", "target": "human_handoff", "condition": "needs_handoff"},
        {"source": "tool_policy", "target": "guardrail", "condition": "auto_resolved"},
        {"source": "human_confirm", "target": "guardrail", "condition": "interrupt_waiting"},
        {"source": "human_handoff", "target": "guardrail", "condition": "ticket_created"},
        {"source": "guardrail", "target": "compose_answer", "condition": "always"},
        {"source": "compose_answer", "target": "memory_writer", "condition": "input_allowed"},
        {"source": "memory_writer", "target": "END", "condition": "always"},
    ]
    metadata: dict[str, Any] = {
        "nodes": nodes,
        "edges": edges,
        "interrupt_nodes": ["human_confirm"],
        "checkpoint_fields": ["conversation_id", "case_id", "task_id", "resume_token"],
        "execution_mode": "orchestrator_sequence",
        "langgraph_available": False,
        "langgraph_runtime": "metadata_only",
        "langgraph_nodes_bound": False,
    }
    try:
        import langgraph  # noqa: F401

        metadata["langgraph_available"] = True
    except Exception:
        pass
    metadata["graph"] = None
    return metadata
