from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from typing import Any, cast

from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.agents.langgraph_workflow import build_langgraph_metadata
from app.agents.orchestrator import AgentOrchestrator
from app.auth.context import build_dev_auth_context
from app.core.config import settings
from app.core.observability import configure_observability
from app.core.services import create_knowledge_store, create_repository, create_runtime_service
from app.evals.harness import EvalHarness, build_eval_cases, eval_run_to_dict
from app.llm.provider import create_llm_provider
from app.tools.business_tools import BusinessToolRegistry

load_dotenv()
configure_observability(settings)

repository = create_repository(settings)
runtime_service = create_runtime_service(settings)
knowledge_store = create_knowledge_store(settings)
tool_registry = BusinessToolRegistry(repository)
llm_provider = create_llm_provider(settings)
orchestrator = AgentOrchestrator(repository, knowledge_store, tool_registry, llm_provider)
eval_runs: dict[str, dict[str, Any]] = {}

app = FastAPI(
    title="SmartCS ResolutionOps Console",
    description="电商售后智能客服运营项目",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    user_id: str = "u_1001"
    conversation_id: str | None = None


class TicketPatchRequest(BaseModel):
    status: str | None = None
    priority: str | None = None
    category: str | None = None
    title: str | None = None
    description: str | None = None
    assigned_to: str | None = None
    assignee_name: str | None = None
    sla_deadline: str | None = None
    handoff_reason: str | None = None
    agent_summary: str | None = None
    customer_emotion: str | None = None
    latest_customer_message: str | None = None
    suggested_reply: str | None = None
    human_reply: str | None = None
    resolution_type: str | None = None
    closed_reason: str | None = None
    csat_score: int | None = None


class CasePatchRequest(BaseModel):
    status: str | None = None
    priority: str | None = None
    category: str | None = None
    related_order_id: str | None = None
    related_ticket_id: str | None = None
    current_task_id: str | None = None
    resolution: str | None = None
    risk_level: str | None = None
    summary: str | None = None


class TaskDecisionRequest(BaseModel):
    approved: bool = True


class HandoffRequest(BaseModel):
    reason: str = "人工坐席接管"


class KBIngestRequest(BaseModel):
    title: str
    content: str
    source: str = "manual.md"
    category: str = "faq"
    tags: list[str] = Field(default_factory=list)


class EvalRunRequest(BaseModel):
    size: int = Field(default=120, ge=1, le=240)


def to_jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return to_jsonable(asdict(cast(Any, value)))
    if isinstance(value, dict):
        return {key: to_jsonable(item) for key, item in value.items() if key != "state"}
    if isinstance(value, list):
        return [to_jsonable(item) for item in value]
    return value


def sse(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(to_jsonable(data), ensure_ascii=False)}\n\n"


def build_harness_manifest() -> dict[str, Any]:
    """Describe the engineering harness wrapped around the agent runtime.

    In this project, "harness" is the control layer that makes agent behavior
    reproducible, observable, testable, and safe to change. The eval runner is
    one adapter inside that layer, not the whole harness.
    """

    graph_metadata = build_langgraph_metadata()
    graph_metadata.pop("graph", None)
    tools = tool_registry.list_tools()
    return {
        "name": "SmartCS Agent Harness",
        "version": app.version,
        "definition": (
            "A control plane around the LLM workflow that standardizes state, "
            "tool contracts, fixtures, traces, replay evidence, guardrails, "
            "quality gates, and release decisions."
        ),
        "agent_state_contract": [
            "messages",
            "user_profile",
            "intent",
            "retrieved_docs",
            "tool_calls",
            "draft_answer",
            "guardrail_result",
            "final_answer",
            "trace_id",
            "conversation_id",
            "case_id",
            "task_id",
            "action_required",
            "pending_confirmation",
            "resume_token",
        ],
        "event_contract": {
            "stream": [
                "agent_step",
                "case_update",
                "task_update",
                "tool_call",
                "audit",
                "action_required",
                "citation",
                "checkpoint",
                "token",
                "final",
                "error",
            ],
            "trace_required_fields": [
                "trace_id",
                "agent_path",
                "case_id",
                "task_id",
                "tool_calls",
                "retrieved_docs",
                "latency_ms",
            ],
        },
        "planes": [
            {
                "id": "contracts",
                "title": "Contracts",
                "purpose": "Keep AgentState, SSE events, tool schemas, and KB metadata explicit.",
                "evidence": ["app.models.schemas.AgentState", "/api/tools", "/api/graph"],
            },
            {
                "id": "fixtures",
                "title": "Scenario Fixtures",
                "purpose": (
                    "Represent after-sales workflows as repeatable customer cases with expected "
                    "intent, tools, citations, and safety behavior."
                ),
                "evidence": ["app.evals.harness.BASE_CASES", "frontend scenario catalog"],
            },
            {
                "id": "execution",
                "title": "Controlled Execution",
                "purpose": (
                    "Run the agent through a bounded orchestrator sequence with typed business "
                    "tools instead of free-form side effects. The LangGraph shape is currently "
                    "a migration contract, not the live executor."
                ),
                "evidence": [
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
                ],
            },
            {
                "id": "observability",
                "title": "Observability",
                "purpose": (
                    "Persist the path, tool calls, retrieved docs, token stream, memory, and "
                    "latency for debugging and replay."
                ),
                "evidence": ["/api/conversations/{id}", "/api/conversations/{id}/stream-state"],
            },
            {
                "id": "gates",
                "title": "Quality Gates",
                "purpose": (
                    "Block risky prompt, tool, model, or KB changes when regression metrics fail "
                    "thresholds."
                ),
                "evidence": ["/api/evals/run", "CI smoke", "manual live eval"],
            },
        ],
        "release_gates": {
            "intent_accuracy": 0.90,
            "tool_accuracy": 0.90,
            "tool_argument_accuracy": 0.90,
            "citation_hit_rate": 0.85,
            "groundedness": 0.80,
            "pii_leakage_rate": 0.0,
            "unsafe_block_rate": 1.0,
            "handoff_precision": 0.85,
            "task_success_rate": 0.85,
            "first_token_p95_ms": 1500,
            "end_to_end_p95_ms": 6000,
        },
        "change_policy": [
            "Prompt changes must pass scenario fixtures and safety gates.",
            "Tool changes must preserve input schemas and authorization checks.",
            "Knowledge changes must be searchable by category and citation evidence.",
            "Model changes must be compared with the same fixtures before release.",
        ],
        "graph": graph_metadata,
        "tools": tools,
    }


@app.post("/api/chat/stream")
async def chat_stream(
    request: ChatRequest,
    x_smartcs_user: str | None = Header(default=None),
    x_smartcs_tenant: str | None = Header(default=None),
    x_smartcs_roles: str | None = Header(default=None),
):
    auth_context = build_dev_auth_context(
        header_user_id=x_smartcs_user,
        fallback_user_id=request.user_id,
        tenant_id=x_smartcs_tenant,
        roles_header=x_smartcs_roles,
    )
    rate_limit = runtime_service.check_rate_limit(auth_context.user_id)
    if not rate_limit.allowed:
        raise HTTPException(
            status_code=429,
            detail={
                "message": "Rate limit exceeded",
                "reset_seconds": rate_limit.reset_seconds,
            },
        )

    async def generator():
        assistant_answer = ""
        stream_key = request.conversation_id or f"pending:{auth_context.user_id}"
        async for event in orchestrator.run_stream(
            message=request.message,
            user_id=auth_context.user_id,
            conversation_id=request.conversation_id,
            auth_context=auth_context,
        ):
            payload = to_jsonable(event.data)
            conversation_key = payload.get("conversation_id") or stream_key
            if event.event == "token":
                assistant_answer += str(payload.get("content", ""))
            runtime_service.append_stream_event(conversation_key, event.event, payload)
            if event.event == "final":
                final_conversation_id = str(payload["conversation_id"])
                runtime_service.cache_message(final_conversation_id, "user", request.message)
                runtime_service.cache_message(final_conversation_id, "assistant", assistant_answer)
            yield sse(event.event, event.data)

    return StreamingResponse(generator(), media_type="text/event-stream")


@app.get("/api/cases")
async def list_cases(user_id: str | None = None, status: str | None = None):
    return {"cases": repository.list_cases(user_id=user_id, status=status)}


@app.get("/api/cases/{case_id}")
async def get_case(case_id: str):
    case = repository.get_case(case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")
    return {
        "case": case,
        "tasks": repository.list_tasks(case_id=case_id),
        "audits": repository.list_tool_audits(case_id=case_id),
    }


@app.patch("/api/cases/{case_id}")
async def update_case(case_id: str, request: CasePatchRequest):
    case = repository.update_case(case_id, request.model_dump(exclude_unset=True))
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")
    return case


@app.post("/api/cases/{case_id}/handoff")
async def handoff_case(
    case_id: str,
    request: HandoffRequest,
    x_smartcs_user: str | None = Header(default=None),
    x_smartcs_tenant: str | None = Header(default=None),
    x_smartcs_roles: str | None = Header(default="agent"),
):
    case = repository.get_case(case_id)
    fallback_user = case["user_id"] if case else "anonymous"
    auth_context = build_dev_auth_context(
        x_smartcs_user,
        fallback_user_id=fallback_user,
        tenant_id=x_smartcs_tenant,
        roles_header=x_smartcs_roles,
    )
    try:
        return await orchestrator.handoff_case(case_id, auth_context, reason=request.reason)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/tasks")
async def list_tasks(case_id: str | None = None, status: str | None = None):
    return {"tasks": repository.list_tasks(case_id=case_id, status=status)}


@app.post("/api/tasks/{task_id}/confirm")
async def confirm_task(
    task_id: str,
    request: TaskDecisionRequest,
    x_smartcs_user: str | None = Header(default=None),
    x_smartcs_tenant: str | None = Header(default=None),
    x_smartcs_roles: str | None = Header(default=None),
):
    task = repository.get_task(task_id)
    case = repository.get_case(task["case_id"]) if task else None
    fallback_user = case["user_id"] if case else "anonymous"
    auth_context = build_dev_auth_context(
        x_smartcs_user,
        fallback_user_id=fallback_user,
        tenant_id=x_smartcs_tenant,
        roles_header=x_smartcs_roles,
    )
    try:
        return await orchestrator.confirm_task(task_id, auth_context, approved=request.approved)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/tasks/{task_id}/cancel")
async def cancel_task(
    task_id: str,
    x_smartcs_user: str | None = Header(default=None),
    x_smartcs_tenant: str | None = Header(default=None),
    x_smartcs_roles: str | None = Header(default=None),
):
    task = repository.get_task(task_id)
    case = repository.get_case(task["case_id"]) if task else None
    fallback_user = case["user_id"] if case else "anonymous"
    auth_context = build_dev_auth_context(
        x_smartcs_user,
        fallback_user_id=fallback_user,
        tenant_id=x_smartcs_tenant,
        roles_header=x_smartcs_roles,
    )
    try:
        return await orchestrator.confirm_task(task_id, auth_context, approved=False)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/tool-audits")
async def list_tool_audits(
    conversation_id: str | None = None,
    case_id: str | None = None,
    tool_name: str | None = None,
):
    return {
        "audits": repository.list_tool_audits(
            conversation_id=conversation_id,
            case_id=case_id,
            tool_name=tool_name,
        )
    }


@app.get("/api/conversations/{conversation_id}")
async def get_conversation(conversation_id: str):
    snapshot = repository.conversation_snapshot(conversation_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return snapshot


@app.get("/api/conversations/{conversation_id}/stream-state")
async def get_stream_state(conversation_id: str):
    return {
        "conversation_id": conversation_id,
        "short_memory": runtime_service.get_short_memory(conversation_id),
        "stream_events": runtime_service.latest_stream_events(conversation_id),
    }


@app.get("/api/tickets")
async def list_tickets():
    return {"tickets": repository.list_tickets()}


@app.patch("/api/tickets/{ticket_id}")
async def update_ticket(ticket_id: str, request: TicketPatchRequest):
    ticket = repository.update_ticket(ticket_id, request.model_dump(exclude_unset=True))
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return ticket


@app.post("/api/kb/ingest")
async def ingest_kb(request: KBIngestRequest):
    docs = knowledge_store.add_document(
        title=request.title,
        content=request.content,
        source=request.source,
        category=request.category,
        tags=request.tags,
    )
    return {"ingested_chunks": len(docs), "documents": [asdict(doc) for doc in docs]}


@app.get("/api/kb/search")
async def search_kb(query: str, top_k: int = 5, category: str | None = None):
    docs = knowledge_store.search(query=query, top_k=top_k, category=category)
    return {"documents": [asdict(doc) for doc in docs]}


@app.post("/api/evals/run")
async def run_evals(request: EvalRunRequest):
    run = await EvalHarness(build_eval_cases(request.size)).run()
    payload = eval_run_to_dict(run)
    eval_runs[run.id] = payload
    return payload


@app.get("/api/evals/{run_id}")
async def get_eval(run_id: str):
    run = eval_runs.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Eval run not found")
    return run


@app.get("/api/tools")
async def list_tools():
    return {"tools": tool_registry.list_tools()}


@app.get("/api/graph")
async def graph_metadata():
    metadata = build_langgraph_metadata()
    metadata.pop("graph", None)
    return metadata


@app.get("/api/harness/manifest")
async def harness_manifest():
    return build_harness_manifest()


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "llm_provider": settings.llm_provider,
        "llm_model": settings.llm_model,
        "qdrant_collection": settings.qdrant_collection,
        "repository_backend": getattr(repository, "backend_name", "memory"),
        "runtime_backend": getattr(runtime_service, "backend_name", "memory"),
        "knowledge_backend": getattr(knowledge_store, "backend_name", "memory"),
    }
