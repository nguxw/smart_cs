import pytest

from app.agents.orchestrator import AgentOrchestrator
from app.data.repository import ConversationRecord, DemoRepository
from app.llm.provider import MockLLMProvider
from app.rag.knowledge_store import HybridKnowledgeStore, create_seeded_knowledge_store
from app.tools.business_tools import BusinessToolRegistry


class SnapshotRepository(DemoRepository):
    def get_or_create_conversation(
        self, conversation_id: str | None, user_id: str
    ) -> ConversationRecord:
        record = super().get_or_create_conversation(conversation_id, user_id)
        return ConversationRecord(
            id=record.id,
            user_id=record.user_id,
            messages=list(record.messages),
            agent_steps=list(record.agent_steps),
            tool_calls=list(record.tool_calls),
            summary=record.summary,
            trace_ids=list(record.trace_ids),
            updated_at=record.updated_at,
        )


@pytest.mark.asyncio
async def test_refund_tool_flow() -> None:
    repo = DemoRepository()
    tools = BusinessToolRegistry(repo)
    check = await tools.call_tool(
        "check_refund_eligibility", {"order_id": "ORD-2026-1001", "user_id": "u_1001"}
    )
    assert check.success is True
    assert check.result["eligible"] is True
    refund = await tools.call_tool(
        "create_refund",
        {"order_id": "ORD-2026-1001", "user_id": "u_1001", "reason": "测试退款"},
    )
    assert refund.success is True
    assert refund.result["created"] is True


def test_unauthorized_order_is_blocked() -> None:
    repo = DemoRepository()
    result = repo.query_order("ORD-2026-2001", "u_1001")
    assert result["found"] is True
    assert result["authorized"] is False


def test_knowledge_store_category_filter() -> None:
    store: HybridKnowledgeStore = create_seeded_knowledge_store()
    docs = store.search("发票 下载", category="invoice")
    assert docs
    assert docs[0].category == "invoice"


@pytest.mark.asyncio
async def test_agent_uses_new_message_with_persistent_repository_snapshot() -> None:
    repo = SnapshotRepository()
    orchestrator = AgentOrchestrator(
        repository=repo,
        knowledge_store=create_seeded_knowledge_store(),
        tools=BusinessToolRegistry(repo),
        llm=MockLLMProvider(),
    )

    state = await orchestrator.run_once("我的订单ORD-2026-2001超过七天了还能退款吗", "u_1002")

    assert state.messages[-1].content == "我的订单ORD-2026-2001超过七天了还能退款吗"
    assert state.intent == "refund"
    assert [call.name for call in state.tool_calls] == [
        "check_refund_eligibility",
        "create_ticket",
    ]
