from __future__ import annotations

import os
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
        "我要申请 ORD-2026-1001 退款",
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
