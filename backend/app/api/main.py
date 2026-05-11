from __future__ import annotations

import json
import time
from dataclasses import asdict, is_dataclass
from typing import Any, cast

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse, StreamingResponse
from pydantic import BaseModel, Field

from app.agents.graph_runtime import create_agent_runtime
from app.agents.langgraph_workflow import build_langgraph_metadata
from app.agents.orchestrator import AgentOrchestrator
from app.auth.context import AuthContext
from app.auth.dependencies import (
    require_auth,
    require_case_access,
    require_permission,
    require_task_access,
    require_ticket_access,
)
from app.core.config import settings
from app.core.observability import configure_observability
from app.core.services import create_knowledge_store, create_repository, create_runtime_service
from app.evals.harness import EvalHarness, build_eval_cases, eval_run_to_dict
from app.llm.provider import create_llm_provider
from app.observability.metrics import metrics_registry
from app.observability.trace_service import TraceService
from app.state_machines import CaseStatus, CaseWorkflow, TaskWorkflow, TicketWorkflow
from app.state_machines.errors import StateTransitionError
from app.tools.business_tools import BusinessToolRegistry

load_dotenv()
configure_observability(settings)

repository = create_repository(settings)
runtime_service = create_runtime_service(settings)
knowledge_store = create_knowledge_store(settings)
tool_registry = BusinessToolRegistry(repository)
llm_provider = create_llm_provider(settings)
base_orchestrator = AgentOrchestrator(repository, knowledge_store, tool_registry, llm_provider)
orchestrator = create_agent_runtime(
    runtime_name=settings.agent_runtime,
    orchestrator=base_orchestrator,
)
case_workflow = CaseWorkflow(repository)
task_workflow = TaskWorkflow(repository)
ticket_workflow = TicketWorkflow(repository)
trace_service = TraceService(repository, runtime_service)
eval_runs: dict[str, dict[str, Any]] = {}
AUTH_CONTEXT = Depends(require_auth)

app = FastAPI(
    title="SmartCS ResolutionOps Console",
    description="电商售后智能客服运营项目",
    version="0.1.0",
)
app.state.settings = settings

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_credentials=settings.cors_allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = (time.perf_counter() - start) * 1000
    route = request.scope.get("route")
    path = getattr(route, "path", request.url.path)
    metrics_registry.inc(
        "smartcs_request_total",
        method=request.method,
        path=str(path),
        status=str(response.status_code),
    )
    metrics_registry.observe(
        "smartcs_request_latency_ms",
        elapsed_ms,
        method=request.method,
        path=str(path),
    )
    return response


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


def _case_visible(case: dict[str, Any], auth: AuthContext) -> bool:
    if auth.has_permission("*"):
        return True
    if case.get("user_id") == auth.user_id and auth.has_permission("case:read:self"):
        return True
    return case.get("tenant_id") == auth.tenant_id and auth.has_permission("case:read:tenant")


def _ticket_visible(ticket: dict[str, Any], auth: AuthContext) -> bool:
    if auth.has_permission("*"):
        return True
    if ticket.get("user_id") == auth.user_id and auth.has_permission("ticket:create:self"):
        return True
    return auth.has_permission("ticket:read:tenant")


def _case_for_task(task_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    task = repository.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    case = repository.get_case(task["case_id"])
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")
    return task, case


def _state_error(exc: StateTransitionError) -> HTTPException:
    return HTTPException(status_code=409, detail=str(exc))


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
            "action_plan",
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
                "action_plan",
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
                    "action_planner",
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
            "missing_slot_accuracy": 0.90,
            "forbidden_tool_violation_rate": 0.0,
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
    auth_context: AuthContext = AUTH_CONTEXT,
):
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
async def list_cases(
    user_id: str | None = None,
    status: str | None = None,
    auth_context: AuthContext = AUTH_CONTEXT,
):
    effective_user = user_id
    if not auth_context.has_permission("case:read:tenant") and not auth_context.has_permission("*"):
        effective_user = auth_context.user_id
    cases = [
        case
        for case in repository.list_cases(user_id=effective_user, status=status)
        if _case_visible(case, auth_context)
    ]
    return {"auth_source": auth_context.source, "cases": cases}


@app.get("/api/cases/{case_id}")
async def get_case(case_id: str, auth_context: AuthContext = AUTH_CONTEXT):
    case = repository.get_case(case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")
    require_case_access(case, auth_context)
    return {
        "case": case,
        "tasks": repository.list_tasks(case_id=case_id),
        "audits": repository.list_tool_audits(case_id=case_id),
    }


@app.patch("/api/cases/{case_id}")
async def update_case(
    case_id: str,
    request: CasePatchRequest,
    auth_context: AuthContext = AUTH_CONTEXT,
):
    existing = repository.get_case(case_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Case not found")
    require_case_access(existing, auth_context, write=True)
    payload = request.model_dump(exclude_unset=True)
    try:
        if payload.get("status"):
            status = payload.pop("status")
            case = case_workflow.transition(
                case_id=case_id,
                target=CaseStatus(status),
                reason=payload.get("resolution") or payload.get("summary") or "api_update",
                actor=auth_context,
                updates=payload,
            )
        else:
            case = repository.update_case(case_id, payload)
    except StateTransitionError as exc:
        raise _state_error(exc) from exc
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")
    return case


@app.post("/api/cases/{case_id}/handoff")
async def handoff_case(
    case_id: str,
    request: HandoffRequest,
    auth_context: AuthContext = AUTH_CONTEXT,
):
    case = repository.get_case(case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")
    require_case_access(case, auth_context, write=True)
    require_permission(auth_context, "handoff:manage:tenant")
    try:
        return await orchestrator.handoff_case(case_id, auth_context, reason=request.reason)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/tasks")
async def list_tasks(
    case_id: str | None = None,
    status: str | None = None,
    auth_context: AuthContext = AUTH_CONTEXT,
):
    tasks = repository.list_tasks(case_id=case_id, status=status)
    visible = []
    for task in tasks:
        case = repository.get_case(task["case_id"])
        if case and _case_visible(case, auth_context):
            visible.append(task)
    return {"tasks": visible}


@app.post("/api/tasks/{task_id}/confirm")
async def confirm_task(
    task_id: str,
    request: TaskDecisionRequest,
    auth_context: AuthContext = AUTH_CONTEXT,
):
    task, case = _case_for_task(task_id)
    require_task_access(task, case, auth_context, confirm=True)
    try:
        return await orchestrator.confirm_task(task_id, auth_context, approved=request.approved)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/tasks/{task_id}/cancel")
async def cancel_task(
    task_id: str,
    auth_context: AuthContext = AUTH_CONTEXT,
):
    task, case = _case_for_task(task_id)
    require_task_access(task, case, auth_context, confirm=True)
    try:
        return await orchestrator.confirm_task(task_id, auth_context, approved=False)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/tool-audits")
async def list_tool_audits(
    conversation_id: str | None = None,
    case_id: str | None = None,
    tool_name: str | None = None,
    auth_context: AuthContext = AUTH_CONTEXT,
):
    audits = repository.list_tool_audits(
        conversation_id=conversation_id,
        case_id=case_id,
        tool_name=tool_name,
    )
    visible: list[dict[str, Any]] = []
    for audit in audits:
        if audit.get("case_id"):
            case = repository.get_case(audit["case_id"])
            if case and _case_visible(case, auth_context):
                visible.append(audit)
        elif auth_context.has_permission("*") or auth_context.has_permission("case:read:tenant"):
            visible.append(audit)
    return {"audits": visible}


@app.get("/api/conversations/{conversation_id}")
async def get_conversation(
    conversation_id: str,
    auth_context: AuthContext = AUTH_CONTEXT,
):
    snapshot = repository.conversation_snapshot(conversation_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    if snapshot.get("user_id") != auth_context.user_id and not auth_context.has_permission(
        "conversation:read:tenant"
    ):
        raise HTTPException(status_code=403, detail="Conversation access denied")
    return snapshot


@app.get("/api/conversations/{conversation_id}/stream-state")
async def get_stream_state(
    conversation_id: str,
    auth_context: AuthContext = AUTH_CONTEXT,
):
    snapshot = repository.conversation_snapshot(conversation_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    if snapshot.get("user_id") != auth_context.user_id and not auth_context.has_permission(
        "conversation:read:tenant"
    ):
        raise HTTPException(status_code=403, detail="Conversation access denied")
    return {
        "conversation_id": conversation_id,
        "short_memory": runtime_service.get_short_memory(conversation_id),
        "stream_events": runtime_service.latest_stream_events(conversation_id),
    }


@app.get("/api/tickets")
async def list_tickets(auth_context: AuthContext = AUTH_CONTEXT):
    tickets = [
        ticket for ticket in repository.list_tickets() if _ticket_visible(ticket, auth_context)
    ]
    return {"tickets": tickets}


@app.get("/api/tickets/{ticket_id}/thread")
async def get_ticket_thread(
    ticket_id: str,
    auth_context: AuthContext = AUTH_CONTEXT,
):
    ticket = next((row for row in repository.list_tickets() if row["id"] == ticket_id), None)
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found")
    require_ticket_access(ticket, auth_context)
    linked_case = next(
        (
            row
            for row in repository.list_cases()
            if row.get("related_ticket_id") == ticket_id
        ),
        None,
    )
    conversation = (
        repository.conversation_snapshot(linked_case["conversation_id"])
        if linked_case
        else None
    )
    return {"ticket": ticket, "case": linked_case, "conversation": conversation}


@app.patch("/api/tickets/{ticket_id}")
async def update_ticket(
    ticket_id: str,
    request: TicketPatchRequest,
    auth_context: AuthContext = AUTH_CONTEXT,
):
    existing = next((row for row in repository.list_tickets() if row["id"] == ticket_id), None)
    if existing is None:
        raise HTTPException(status_code=404, detail="Ticket not found")
    require_ticket_access(existing, auth_context, write=True)
    try:
        return ticket_workflow.update(
            ticket_id=ticket_id,
            payload=request.model_dump(exclude_unset=True),
            actor=auth_context,
        )
    except StateTransitionError as exc:
        raise _state_error(exc) from exc


@app.post("/api/kb/ingest")
async def ingest_kb(
    request: KBIngestRequest,
    auth_context: AuthContext = AUTH_CONTEXT,
):
    require_permission(auth_context, "kb:write")
    docs = knowledge_store.add_document(
        title=request.title,
        content=request.content,
        source=request.source,
        category=request.category,
        tags=request.tags,
    )
    return {"ingested_chunks": len(docs), "documents": [asdict(doc) for doc in docs]}


@app.get("/api/kb/search")
async def search_kb(
    query: str,
    top_k: int = 5,
    category: str | None = None,
    auth_context: AuthContext = AUTH_CONTEXT,
):
    require_permission(auth_context, "kb:read")
    docs = knowledge_store.search(query=query, top_k=top_k, category=category)
    return {"documents": [asdict(doc) for doc in docs]}


@app.post("/api/evals/run")
async def run_evals(
    request: EvalRunRequest,
    auth_context: AuthContext = AUTH_CONTEXT,
):
    require_permission(auth_context, "*")
    run = await EvalHarness(build_eval_cases(request.size)).run()
    payload = eval_run_to_dict(run)
    eval_runs[run.id] = payload
    metrics_registry.inc("smartcs_eval_run_total", source="api")
    return payload


@app.get("/api/evals/{run_id}")
async def get_eval(
    run_id: str,
    auth_context: AuthContext = AUTH_CONTEXT,
):
    require_permission(auth_context, "*")
    run = eval_runs.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Eval run not found")
    return run


@app.get("/api/tools")
async def list_tools(auth_context: AuthContext = AUTH_CONTEXT):
    require_permission(auth_context, "*")
    return {"tools": tool_registry.list_tools()}


@app.get("/api/graph")
async def graph_metadata(auth_context: AuthContext = AUTH_CONTEXT):
    require_permission(auth_context, "*")
    metadata = build_langgraph_metadata()
    metadata.pop("graph", None)
    return metadata


@app.get("/api/harness/manifest")
async def harness_manifest(auth_context: AuthContext = AUTH_CONTEXT):
    require_permission(auth_context, "*")
    return build_harness_manifest()


@app.get("/api/traces/{trace_id}")
async def get_trace(trace_id: str, auth_context: AuthContext = AUTH_CONTEXT):
    trace = trace_service.get_trace(trace_id, auth_context)
    if trace is None:
        raise HTTPException(status_code=404, detail="Trace not found")
    return trace


@app.get("/metrics")
async def metrics():
    return PlainTextResponse(metrics_registry.render_prometheus(), media_type="text/plain")


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
