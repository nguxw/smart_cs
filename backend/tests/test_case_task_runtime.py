import pytest

from app.agents.orchestrator import AgentOrchestrator
from app.auth.context import AuthContext
from app.data.repository import DemoRepository
from app.llm.provider import MockLLMProvider
from app.rag.knowledge_store import create_seeded_knowledge_store
from app.state_machines import TicketWorkflow
from app.state_machines.errors import StateTransitionError
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
async def test_refund_without_order_asks_for_slot_without_latest_order_default() -> None:
    repo = DemoRepository()
    orchestrator = AgentOrchestrator(
        repository=repo,
        knowledge_store=create_seeded_knowledge_store(),
        tools=BusinessToolRegistry(repo),
        llm=MockLLMProvider(),
    )

    state = await orchestrator.run_once("我要退款", "u_1001")

    assert state.action_plan is not None
    assert state.action_plan.missing_slots == ["order_id"]
    assert state.metadata.get("order_id") is None
    assert state.tool_calls == []
    assert state.pending_confirmation is None
    assert "提供需要处理的订单号" in state.metadata["tool_summary"]


@pytest.mark.asyncio
async def test_latest_order_reference_must_be_explicit() -> None:
    repo = DemoRepository()
    orchestrator = AgentOrchestrator(
        repository=repo,
        knowledge_store=create_seeded_knowledge_store(),
        tools=BusinessToolRegistry(repo),
        llm=MockLLMProvider(),
    )

    state = await orchestrator.run_once("我想了解最近一笔订单能不能退款", "u_1001")

    assert state.action_plan is not None
    assert state.action_plan.slots["order_reference"] == "latest"
    assert state.metadata["order_id"] == "ORD-2026-1002"
    assert [call.name for call in state.tool_calls] == ["check_refund_eligibility"]


@pytest.mark.asyncio
async def test_ticket_without_order_does_not_call_query_order() -> None:
    repo = DemoRepository()
    orchestrator = AgentOrchestrator(
        repository=repo,
        knowledge_store=create_seeded_knowledge_store(),
        tools=BusinessToolRegistry(repo),
        llm=MockLLMProvider(),
    )

    state = await orchestrator.run_once("耳机坏了，需要售后工单", "u_1001")

    assert state.action_plan is not None
    assert state.action_plan.requires_handoff is True
    assert [call.name for call in state.tool_calls] == ["create_ticket"]
    assert state.tool_calls[0].policy_status == "side_effect_approved"


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
    assert call.success is False
    assert call.policy_status == "permission_denied"
    assert call.result["allowed"] is False
    assert repo.list_tool_audits(conversation_id="cv-auth-test")[0]["policy_status"] == (
        "permission_denied"
    )


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

    updated = TicketWorkflow(repo).update(
        ticket_id=ticket["id"],
        payload={
            "human_reply": "已为你提交二线复核，预计今天内回复。",
            "status": "resolved",
            "closed_reason": "人工已回复客户",
        },
        actor=AuthContext(user_id="agent-demo", roles=("agent",)),
    )
    snapshot = repo.conversation_snapshot(conversation.id)
    closed_case = repo.get_case(case["id"])

    assert updated is not None
    assert snapshot is not None
    assert snapshot["messages"][-1]["content"] == "已为你提交二线复核，预计今天内回复。"
    assert closed_case and closed_case["status"] == "resolved"
    assert closed_case["resolution"] == "人工已回复客户"


def test_ticket_queue_metadata_and_reopen_state_sync_to_case() -> None:
    repo = DemoRepository()
    conversation = repo.get_or_create_conversation("cv-ticket-sync-test", "u_1005")
    case = repo.create_or_get_case(
        user_id="u_1005",
        tenant_id="demo-tenant",
        conversation_id=conversation.id,
        category="ticket",
        priority="medium",
    )
    ticket = repo.create_ticket(
        user_id="u_1005",
        title="物流异常",
        description="需要人工处理物流异常",
        priority="medium",
        category="ticket",
    )
    repo.update_case(case["id"], {"related_ticket_id": ticket["id"]})

    workflow = TicketWorkflow(repo)
    workflow.update(
        ticket_id=ticket["id"],
        payload={
            "status": "pending",
            "priority": "high",
            "category": "handoff",
            "agent_summary": "物流停滞，已升级二线跟进。",
        },
        actor=AuthContext(user_id="agent-demo", roles=("agent",)),
    )
    escalated_case = repo.get_case(case["id"])

    assert escalated_case is not None
    assert escalated_case["status"] == "waiting_customer"
    assert escalated_case["priority"] == "high"
    assert escalated_case["category"] == "handoff"
    assert escalated_case["summary"] == "物流停滞，已升级二线跟进。"

    workflow.update(
        ticket_id=ticket["id"],
        payload={"status": "resolved", "closed_reason": "已补发"},
        actor=AuthContext(user_id="agent-demo", roles=("agent",)),
    )
    closed_case = repo.get_case(case["id"])

    assert closed_case is not None
    assert closed_case["status"] == "resolved"
    assert closed_case["resolution"] == "已补发"

    with pytest.raises(StateTransitionError):
        workflow.update(
            ticket_id=ticket["id"],
            payload={"status": "open"},
            actor=AuthContext(user_id="agent-demo", roles=("agent",)),
        )


@pytest.mark.asyncio
async def test_customer_closing_conversation_resolves_case_without_handoff() -> None:
    repo = DemoRepository()
    orchestrator = AgentOrchestrator(
        repository=repo,
        knowledge_store=create_seeded_knowledge_store(),
        tools=BusinessToolRegistry(repo),
        llm=MockLLMProvider(),
    )
    conversation = repo.get_or_create_conversation("cv-close-test", "u_1005")
    case = repo.create_or_get_case(
        user_id="u_1005",
        tenant_id="demo-tenant",
        conversation_id=conversation.id,
        category="faq",
        priority="medium",
    )
    task = repo.create_task(
        case_id=case["id"],
        task_type="customer_confirmation",
        required_action="confirm_refund",
        pending_confirmation={"tool": "create_refund"},
    )
    ticket = repo.create_ticket(
        user_id="u_1005",
        title="人工跟进",
        description="已有人工队列记录",
        priority="medium",
        category="handoff",
    )
    repo.update_case(case["id"], {"related_ticket_id": ticket["id"]})

    state = await orchestrator.run_once("结束吧", "u_1005", conversation.id)
    closed_case = repo.get_case(case["id"])
    closed_task = repo.get_task(task["id"])
    closed_ticket = repo.tickets[ticket["id"]]

    assert state.intent == "closing"
    assert state.tool_calls == []
    assert closed_case is not None
    assert closed_case["status"] == "resolved"
    assert closed_case["resolution"] == "用户主动结束本次会话"
    assert closed_task is not None
    assert closed_task["status"] == "cancelled"
    assert closed_ticket.status == "resolved"
    assert len(repo.tickets) == 1


@pytest.mark.asyncio
async def test_repeated_handoff_in_same_conversation_reuses_open_ticket() -> None:
    repo = DemoRepository()
    orchestrator = AgentOrchestrator(
        repository=repo,
        knowledge_store=create_seeded_knowledge_store(),
        tools=BusinessToolRegistry(repo),
        llm=MockLLMProvider(),
    )
    conversation_id = "cv-repeat-handoff"

    first = await orchestrator.run_once("请转人工处理这个售后问题", "u_1001", conversation_id)
    second = await orchestrator.run_once("还是需要人工客服继续处理", "u_1001", conversation_id)

    tickets = repo.list_tickets()
    assert len(tickets) == 1
    assert first.metadata["ticket"]["id"] == second.metadata["ticket"]["id"]
    assert first.metadata["ticket"]["reused"] is False
    assert second.metadata["ticket"]["reused"] is True
    assert repo.get_case(second.case_id or "")["related_ticket_id"] == tickets[0]["id"]
