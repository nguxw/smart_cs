import pytest

from app.agents.orchestrator import AgentOrchestrator
from app.auth.context import AuthContext
from app.data.repository import DemoRepository
from app.llm.provider import MockLLMProvider
from app.rag.knowledge_store import create_seeded_knowledge_store
from app.tools.business_tools import BusinessToolRegistry
from app.tools.runtime import ToolRuntime


@pytest.mark.asyncio
async def test_refund_creates_pending_confirmation_before_side_effect() -> None:
    repo = DemoRepository()
    orchestrator = AgentOrchestrator(
        repository=repo,
        knowledge_store=create_seeded_knowledge_store(),
        tools=BusinessToolRegistry(repo),
        llm=MockLLMProvider(),
    )

    state = await orchestrator.run_once("我要申请 ORD-2026-1001 退款", "u_1001")

    assert state.case_id
    assert state.task_id
    assert state.pending_confirmation
    assert state.action_required == "customer_confirmation"
    assert [call.name for call in state.tool_calls] == ["check_refund_eligibility"]
    assert repo.orders["ORD-2026-1001"].refund_id is None


@pytest.mark.asyncio
async def test_confirm_task_executes_refund_once_with_audit() -> None:
    repo = DemoRepository()
    orchestrator = AgentOrchestrator(
        repository=repo,
        knowledge_store=create_seeded_knowledge_store(),
        tools=BusinessToolRegistry(repo),
        llm=MockLLMProvider(),
    )
    state = await orchestrator.run_once("我要申请 ORD-2026-1001 退款", "u_1001")

    result = await orchestrator.confirm_task(
        state.task_id or "",
        AuthContext(user_id="u_1001"),
        approved=True,
    )
    repeated = await orchestrator.confirm_task(
        state.task_id or "",
        AuthContext(user_id="u_1001"),
        approved=True,
    )

    assert result["tool_call"]["name"] == "create_refund"
    assert result["tool_call"]["success"] is True
    assert repeated["tool_call"] is None
    assert len(repo.refunds) == 1
    audits = repo.list_tool_audits(case_id=state.case_id)
    assert any(audit["tool_name"] == "create_refund" for audit in audits)


@pytest.mark.asyncio
async def test_tool_runtime_rebinds_user_id_from_auth_context() -> None:
    repo = DemoRepository()
    registry = BusinessToolRegistry(repo)
    runtime = ToolRuntime(repo, registry)
    repo.get_or_create_conversation("cv-auth-test", "u_1001")

    call = await runtime.execute(
        "query_order",
        {"order_id": "ORD-2026-2001", "user_id": "u_1002"},
        AuthContext(user_id="u_1001"),
        conversation_id="cv-auth-test",
    )

    assert call.arguments["user_id"] == "u_1001"
    assert call.result["authorized"] is False
    assert repo.list_tool_audits(conversation_id="cv-auth-test")[0]["policy_status"] == "approved"
