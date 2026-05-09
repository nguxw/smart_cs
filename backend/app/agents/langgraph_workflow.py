from __future__ import annotations

from typing import Any, TypedDict


class SmartCSGraphState(TypedDict, total=False):
    conversation_id: str
    case_id: str
    task_id: str
    intent: str
    action_required: str


def build_langgraph_metadata() -> dict[str, Any]:
    """Expose the executable SmartCS state graph used by the orchestrator."""

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
        "langgraph_available": False,
    }
    try:
        from langgraph.graph import END, StateGraph

        graph = StateGraph(SmartCSGraphState)
        for node in nodes:
            graph.add_node(node, lambda state: state)
        graph.set_entry_point("router")
        graph.add_edge("router", "input_policy")
        graph.add_edge("input_policy", "case_binding")
        graph.add_conditional_edges(
            "case_binding",
            lambda state: "human_handoff" if state.get("input_blocked") else "retrieve_policy",
        )
        graph.add_edge("retrieve_policy", "tool_policy")
        graph.add_conditional_edges(
            "tool_policy",
            lambda state: "human_confirm"
            if state.get("action_required") == "customer_confirmation"
            else "human_handoff"
            if state.get("needs_handoff")
            else "guardrail",
        )
        graph.add_edge("human_confirm", "guardrail")
        graph.add_edge("human_handoff", "guardrail")
        graph.add_edge("guardrail", "compose_answer")
        graph.add_edge("compose_answer", "memory_writer")
        graph.add_edge("memory_writer", END)
        metadata["langgraph_available"] = True
        metadata["graph"] = graph
    except Exception:
        metadata["graph"] = None
    return metadata
