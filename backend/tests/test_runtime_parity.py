from __future__ import annotations

import pytest

from app.agents.graph_runtime import SmartCSLangGraphRuntime
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
async def test_langgraph_adapter_preserves_orchestrator_business_outcome() -> None:
    orchestrator, graph_runtime = _runtime_pair()
    message = "我要申请 ORD-2026-1001 退款"

    state_a = await orchestrator.run_once(message, user_id="u_1001")
    state_b = await graph_runtime.run_once(message, user_id="u_1001")

    assert state_b.intent == state_a.intent
    assert state_b.action_plan
    assert state_a.action_plan
    assert state_b.action_plan.required_tools == state_a.action_plan.required_tools
    assert state_b.graph_path == state_a.graph_path
    assert state_b.action_required == state_a.action_required
    assert bool(state_b.pending_confirmation) == bool(state_a.pending_confirmation)
    assert [call.name for call in state_b.tool_calls] == [call.name for call in state_a.tool_calls]
