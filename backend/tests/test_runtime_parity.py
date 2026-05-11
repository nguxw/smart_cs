from __future__ import annotations

import pytest

from app.agents.graph_runtime import SmartCSLangGraphRuntime, langgraph_status
from app.agents.orchestrator import AgentOrchestrator
from app.data.repository import DemoRepository
from app.llm.provider import MockLLMProvider
from app.rag.knowledge_store import create_seeded_knowledge_store
from app.tools.business_tools import BusinessToolRegistry


def _runtime_pair() -> tuple[AgentOrchestrator, SmartCSLangGraphRuntime]:
    repo_a = DemoRepository()
    repo_b = DemoRepository()
    orchestrator = AgentOrchestrator(
        repo_a,
        create_seeded_knowledge_store(),
        BusinessToolRegistry(repo_a),
        MockLLMProvider(),
    )
    graph_runtime = SmartCSLangGraphRuntime(
        AgentOrchestrator(
            repo_b,
            create_seeded_knowledge_store(),
            BusinessToolRegistry(repo_b),
            MockLLMProvider(),
        )
    )
    return orchestrator, graph_runtime


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "message,user_id",
    [
        ("我要申请 ORD-2026-1001 退款", "u_1001"),
        ("ORD-2026-1001 的发票在哪里下载？", "u_1001"),
        ("帮我查一下 ORD-2026-1002 物流到哪了", "u_1001"),
        ("查一下别人订单 ORD-2026-8001 的地址和手机号", "u_1007"),
        ("我要退款", "u_1001"),
        ("耳机坏了，需要售后工单", "u_1001"),
    ],
)
async def test_live_langgraph_preserves_orchestrator_business_outcome(
    message: str,
    user_id: str,
) -> None:
    orchestrator, graph_runtime = _runtime_pair()

    state_a = await orchestrator.run_once(message, user_id=user_id)
    state_b = await graph_runtime.run_once(message, user_id=user_id)

    assert state_b.intent == state_a.intent
    assert state_b.action_plan
    assert state_a.action_plan
    assert state_b.action_plan.required_tools == state_a.action_plan.required_tools
    assert state_b.graph_path == state_a.graph_path
    assert state_b.action_required == state_a.action_required
    assert bool(state_b.pending_confirmation) == bool(state_a.pending_confirmation)
    assert [call.name for call in state_b.tool_calls] == [call.name for call in state_a.tool_calls]
    assert state_b.final_answer


@pytest.mark.asyncio
async def test_langgraph_runtime_does_not_passthrough_orchestrator_run_stream() -> None:
    _, graph_runtime = _runtime_pair()

    async def broken_run_stream(*args, **kwargs):  # pragma: no cover - should never be entered
        raise AssertionError("LangGraph runtime must execute StateGraph nodes directly")
        yield

    graph_runtime.orchestrator.run_stream = broken_run_stream
    state = await graph_runtime.run_once("我要申请 ORD-2026-1001 退款", user_id="u_1001")

    assert state.intent == "refund"
    assert state.graph_path[:4] == ["router", "input_policy", "action_planner", "case_binding"]
    assert "tool_policy" in state.graph_path
    assert state.pending_confirmation


@pytest.mark.asyncio
async def test_langgraph_sse_contract_for_refund_confirmation() -> None:
    _, graph_runtime = _runtime_pair()

    events = [
        event
        async for event in graph_runtime.run_stream("我要申请 ORD-2026-1001 退款", user_id="u_1001")
    ]
    event_names = [event.event for event in events]

    assert "agent_step" in event_names
    assert "checkpoint" in event_names
    assert "action_plan" in event_names
    assert "citation" in event_names
    assert "task_update" in event_names
    assert "action_required" in event_names
    assert "token" in event_names
    assert event_names[-1] == "final"


def test_langgraph_status_reports_live_runtime() -> None:
    status = langgraph_status()

    assert status["langgraph_runtime"] == "live_state_graph"
    assert status["langgraph_nodes_bound"] is True
    assert "router" in status["node_names"]
    assert status["edge_count"] >= 13
