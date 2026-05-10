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
async def test_cancel_task_preserves_refund_side_effect_boundary() -> None:
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
        approved=False,
    )

    assert result["tool_call"] is None
    assert result["task"]["status"] == "cancelled"
    assert repo.orders["ORD-2026-1001"].refund_id is None
    assert not any(audit["tool_name"] == "create_refund" for audit in repo.list_tool_audits())


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


@pytest.mark.asyncio
async def test_tool_runtime_blocks_unconfirmed_side_effect_with_audit() -> None:
    repo = DemoRepository()
    registry = BusinessToolRegistry(repo)
    runtime = ToolRuntime(repo, registry)
    repo.get_or_create_conversation("cv-confirmation-test", "u_1001")

    call = await runtime.execute(
        "create_refund",
        {"order_id": "ORD-2026-1001", "reason": "customer asked"},
        AuthContext(user_id="u_1001"),
        conversation_id="cv-confirmation-test",
        idempotency_key="refund-create:u_1001:ORD-2026-1001",
    )

    assert call.success is False
    assert call.requires_confirmation is True
    assert call.policy_status == "needs_confirmation"
    assert repo.orders["ORD-2026-1001"].refund_id is None
    audit = repo.list_tool_audits(conversation_id="cv-confirmation-test")[0]
    assert audit["requires_confirmation"] is True
    assert audit["policy_status"] == "needs_confirmation"


@pytest.mark.asyncio
async def test_confirm_task_appends_conversation_message() -> None:
    repo = DemoRepository()
    orchestrator = AgentOrchestrator(
        repository=repo,
        knowledge_store=create_seeded_knowledge_store(),
        tools=BusinessToolRegistry(repo),
        llm=MockLLMProvider(),
    )
    state = await orchestrator.run_once("我要申请 ORD-2026-1001 退款", "u_1001")
    before = repo.conversation_snapshot(state.conversation_id or "")

    await orchestrator.confirm_task(
        state.task_id or "",
        AuthContext(user_id="u_1001"),
        approved=True,
    )
    after = repo.conversation_snapshot(state.conversation_id or "")

    assert before is not None
    assert after is not None
    assert len(after["messages"]) == len(before["messages"]) + 1
    assert after["messages"][-1]["role"] == "assistant"


def test_ticket_human_reply_writes_back_to_conversation_and_closes_case() -> None:
    repo = DemoRepository()
    conversation = repo.get_or_create_conversation("cv-ticket-test", "u_1002")
    case = repo.create_or_get_case(
        user_id="u_1002",
        tenant_id="demo-tenant",
        conversation_id=conversation.id,
        category="handoff",
        priority="high",
    )
    ticket = repo.create_ticket(
        user_id="u_1002",
        title="人工处理",
        description="需要人工回复",
        priority="high",
        category="handoff",
    )
    repo.update_case(case["id"], {"related_ticket_id": ticket["id"]})

    updated = repo.update_ticket(
        ticket["id"],
        {
            "human_reply": "已为你提交二线复核，预计今天内回复。",
            "status": "resolved",
            "closed_reason": "人工已回复客户",
        },
    )
    snapshot = repo.conversation_snapshot(conversation.id)
    closed_case = repo.get_case(case["id"])

    assert updated is not None
    assert snapshot is not None
    assert snapshot["messages"][-1]["content"] == "已为你提交二线复核，预计今天内回复。"
    assert closed_case and closed_case["status"] == "resolved"
    assert closed_case["resolution"] == "人工已回复客户"
