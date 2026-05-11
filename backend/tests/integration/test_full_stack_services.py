from __future__ import annotations

import os
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.agents.orchestrator import AgentOrchestrator
from app.auth.context import AuthContext
from app.data.postgres_repository import PostgresRepository
from app.llm.provider import MockLLMProvider
from app.rag.qdrant_store import QdrantKnowledgeStore
from app.runtime.redis_runtime import RedisRuntimeService
from app.tools.business_tools import BusinessToolRegistry

pytestmark = pytest.mark.skipif(
    os.getenv("SMARTCS_RUN_INTEGRATION") != "1",
    reason="Set SMARTCS_RUN_INTEGRATION=1 when Postgres, Redis, and Qdrant are available.",
)


@pytest.mark.asyncio
async def test_postgres_redis_qdrant_refund_confirmation_flow() -> None:
    database_url = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg://smartcs:smartcs@localhost:5432/smartcs",
    )
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    qdrant_url = os.getenv("QDRANT_URL", "http://localhost:6333")
    collection = f"smartcs_it_{uuid4().hex[:8]}"

    repository = PostgresRepository(database_url)
    runtime = RedisRuntimeService(redis_url)
    knowledge_store = QdrantKnowledgeStore(qdrant_url, collection)
    order_suffix = int(uuid4().hex[:4], 16) % 9000 + 1000
    order_id = f"ORD-2026-{order_suffix:04d}"
    _seed_refundable_order(repository, order_id)
    knowledge_store.add_document(
        title="Refund policy",
        content="Refunds require eligibility check and customer confirmation.",
        source="integration.md",
        category="refund",
        tags=["integration"],
    )

    docs = knowledge_store.search("refund confirmation", top_k=3, category="refund")
    assert docs

    registry = BusinessToolRegistry(repository)
    orchestrator = AgentOrchestrator(repository, knowledge_store, registry, MockLLMProvider())
    auth = AuthContext(user_id="u_1001")

    state = await orchestrator.run_once(
        f"我要申请 {order_id} 退款",
        user_id="u_1001",
        conversation_id=f"it-{uuid4().hex}",
        auth_context=auth,
    )
    assert state.task_id
    assert state.pending_confirmation

    runtime.cache_message(state.conversation_id, "user", "integration")
    runtime.append_stream_event(state.conversation_id, "checkpoint", {"trace_id": state.trace_id})
    assert runtime.get_short_memory(state.conversation_id)
    assert runtime.latest_stream_events(state.conversation_id)

    result = await orchestrator.confirm_task(state.task_id or "", auth, approved=True)
    repeated = await orchestrator.confirm_task(state.task_id or "", auth, approved=True)

    assert result["tool_call"]["name"] == "create_refund"
    assert result["tool_call"]["success"] is True
    assert repeated["tool_call"] is None
    audits = repository.list_tool_audits(case_id=state.case_id)
    assert any(audit["tool_name"] == "create_refund" for audit in audits)


def _seed_refundable_order(repository: PostgresRepository, order_id: str) -> None:
    now = datetime.now(UTC).isoformat()
    with repository._connect() as conn:
        conn.execute("DELETE FROM refunds WHERE order_id = %s", (order_id,))
        conn.execute(
            """
            DELETE FROM tool_audits
            WHERE idempotency_key IN (%s, %s)
            """,
            (f"refund-check:u_1001:{order_id}", f"refund-create:u_1001:{order_id}"),
        )
        conn.execute(
            """
            INSERT INTO orders (
                id, user_id, item, amount, status, paid_at, delivered_at,
                carrier, tracking_no, invoice_status, refund_id, tenant_id
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NULL, %s)
            ON CONFLICT (id) DO UPDATE SET
                user_id = EXCLUDED.user_id,
                item = EXCLUDED.item,
                amount = EXCLUDED.amount,
                status = EXCLUDED.status,
                paid_at = EXCLUDED.paid_at,
                delivered_at = EXCLUDED.delivered_at,
                carrier = EXCLUDED.carrier,
                tracking_no = EXCLUDED.tracking_no,
                invoice_status = EXCLUDED.invoice_status,
                refund_id = NULL,
                tenant_id = EXCLUDED.tenant_id
            """,
            (
                order_id,
                "u_1001",
                "Integration test order",
                88.8,
                "delivered",
                now,
                now,
                "SF Express",
                f"SF{order_id[-4:]}",
                "not_requested",
                "demo-tenant",
            ),
        )
