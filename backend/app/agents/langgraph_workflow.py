from __future__ import annotations

from typing import Any, TypedDict


class DemoGraphState(TypedDict, total=False):
    messages: list[str]


def build_langgraph_metadata() -> dict[str, Any]:
    """Expose the intended LangGraph topology without forcing it during tests.

    The runtime orchestrator emits richer SSE events directly. When langgraph is installed,
    this function also builds a small StateGraph object that documents the same node order and
    can be expanded into a fully compiled graph deployment later.
    """

    nodes = [
        "router",
        "rag_answer",
        "order_refund",
        "ticket_escalation",
        "guardrail",
        "answer_composer",
        "memory_writer",
    ]
    edges = [
        ("router", "rag_answer"),
        ("rag_answer", "order_refund"),
        ("order_refund", "ticket_escalation"),
        ("ticket_escalation", "guardrail"),
        ("guardrail", "answer_composer"),
        ("answer_composer", "memory_writer"),
    ]
    metadata: dict[str, Any] = {"nodes": nodes, "edges": edges, "langgraph_available": False}
    try:
        from langgraph.graph import END, StateGraph

        graph = StateGraph(DemoGraphState)
        for node in nodes:
            graph.add_node(node, lambda state: state)
        graph.set_entry_point("router")
        for source, target in edges:
            graph.add_edge(source, target)
        graph.add_edge("memory_writer", END)
        metadata["langgraph_available"] = True
        metadata["graph"] = graph
    except Exception:
        metadata["graph"] = None
    return metadata
