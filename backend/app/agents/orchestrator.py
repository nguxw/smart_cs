from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import asdict
from typing import Any

from app.agents.guardrails import check_input_safety, check_output_safety
from app.agents.llm_planner import build_llm_action_plan
from app.agents.llm_router import classify_intent_hybrid
from app.agents.plan_validator import merge_and_validate_action_plan
from app.agents.planner import build_action_plan
from app.agents.query_rewriter import rewrite_kb_query
from app.agents.router import classify_intent, extract_order_id
from app.auth.context import AuthContext, build_dev_auth_context
from app.core.config import Settings, settings
from app.data.repository import DemoRepository
from app.llm.provider import LLMProvider
from app.models.schemas import (
    AgentState,
    AgentStep,
    ChatMessage,
    GuardrailResult,
    StreamEvent,
    ToolCallRecord,
)
from app.state_machines import CaseStatus, CaseWorkflow, TaskStatus, TaskWorkflow, TicketWorkflow
from app.tools.business_tools import BusinessToolRegistry
from app.tools.runtime import ToolRuntime

NodeHandler = Callable[[AgentState], Awaitable[None]]


def _event(event: str, **data: Any) -> StreamEvent:
    return StreamEvent(event=event, data=data)  # type: ignore[arg-type]


class AgentOrchestrator:
    """Resolution-oriented SmartCS runtime with case tasks and human confirmation."""

    def __init__(
        self,
        repository: DemoRepository,
        knowledge_store: Any,
        tools: BusinessToolRegistry,
        llm: LLMProvider,
        tool_runtime: ToolRuntime | None = None,
        config: Settings | None = None,
    ) -> None:
        self.repository = repository
        self.knowledge_store = knowledge_store
        self.tools = tools
        self.tool_runtime = tool_runtime or ToolRuntime(repository, tools)
        self.llm = llm
        self.settings = config or settings
        self.case_workflow = CaseWorkflow(repository)
        self.task_workflow = TaskWorkflow(repository)
        self.ticket_workflow = TicketWorkflow(repository)

    async def run_stream(
        self,
        message: str,
        user_id: str = "anonymous",
        conversation_id: str | None = None,
        auth_context: AuthContext | None = None,
    ) -> AsyncIterator[StreamEvent]:
        auth = auth_context or build_dev_auth_context(None, user_id)
        conversation = self._get_or_create_conversation(conversation_id, auth)
        prior_messages = list(conversation.messages)
        user_message = ChatMessage(role="user", content=message)
        self.repository.append_message(conversation.id, user_message)
        state = AgentState(
            messages=[*prior_messages, user_message],
            user_profile=self.repository.get_user_profile(auth.user_id),
            auth_context=auth.to_dict(),
            conversation_id=conversation.id,
        )
        steps: list[AgentStep] = []

        async for event in self._run_node("router", state, steps, self._router):
            yield event
        async for event in self._run_node("input_policy", state, steps, self._input_policy):
            yield event
        async for event in self._run_node("action_planner", state, steps, self._action_planner):
            yield event
        async for event in self._run_node("case_binding", state, steps, self._case_binding):
            yield event

        if state.guardrail_result and state.guardrail_result.blocked:
            async for event in self._run_node("human_handoff", state, steps, self._human_handoff):
                yield event
            async for event in self._run_node(
                "compose_answer",
                state,
                steps,
                self._answer_composer,
            ):
                yield event
            async for event in self._finalize(state, steps):
                yield event
            return

        async for event in self._run_node("retrieve_policy", state, steps, self._retrieve_policy):
            yield event
        async for event in self._run_node("tool_policy", state, steps, self._business_action):
            yield event

        if state.pending_confirmation:
            async for event in self._run_node(
                "human_confirm", state, steps, self._human_confirmation
            ):
                yield event
        elif state.intent in {"ticket", "handoff"} or state.metadata.get("needs_ticket"):
            async for event in self._run_node("human_handoff", state, steps, self._human_handoff):
                yield event
        else:
            async for event in self._skip_node("human_confirm", state, steps, "no confirmation"):
                yield event
            async for event in self._skip_node("human_handoff", state, steps, "no handoff"):
                yield event

        async for event in self._run_node("guardrail", state, steps, self._guardrail):
            yield event
        async for event in self._run_node("compose_answer", state, steps, self._answer_composer):
            yield event
        async for event in self._run_node("memory_writer", state, steps, self._memory_writer):
            yield event
        async for event in self._finalize(state, steps):
            yield event

    async def run_once(
        self,
        message: str,
        user_id: str = "anonymous",
        conversation_id: str | None = None,
        auth_context: AuthContext | None = None,
    ) -> AgentState:
        final: AgentState | None = None
        async for event in self.run_stream(message, user_id, conversation_id, auth_context):
            if event.event == "final":
                final = event.data["state"]
        if final is None:  # pragma: no cover - defensive
            raise RuntimeError("Agent run did not finalize")
        return final

    def _get_or_create_conversation(
        self,
        conversation_id: str | None,
        auth: AuthContext,
    ) -> Any:
        try:
            return self.repository.get_or_create_conversation(
                conversation_id,
                auth.user_id,
                tenant_id=auth.tenant_id,
            )
        except TypeError:
            return self.repository.get_or_create_conversation(conversation_id, auth.user_id)

    async def confirm_task(
        self,
        task_id: str,
        auth_context: AuthContext,
        approved: bool = True,
    ) -> dict[str, Any]:
        task = self.repository.get_task(task_id)
        if task is None:
            raise KeyError(f"Task not found: {task_id}")
        case = self.repository.get_case(task["case_id"])
        if case is None:
            raise KeyError(f"Case not found: {task['case_id']}")
        if task["status"] != "pending":
            return {"case": case, "task": task, "tool_call": None, "message": "任务已处理"}
        if not approved:
            updated_task = self.task_workflow.transition(
                task_id=task_id,
                target=TaskStatus.CANCELLED,
                reason="customer_cancelled",
                actor=auth_context,
                result={"approved": False},
            )
            updated_case = self.repository.get_case(case["id"])
            return {
                "case": updated_case,
                "task": updated_task,
                "tool_call": None,
                "message": "已取消待确认动作，未执行副作用工具。",
            }

        pending = task.get("pending_confirmation") or {}
        tool_name = str(pending.get("tool"))
        arguments = dict(pending.get("arguments") or {})
        idempotency_key = str(pending.get("idempotency_key") or task["resume_token"])
        call = await self.tool_runtime.execute(
            tool_name,
            arguments,
            auth_context,
            conversation_id=case["conversation_id"],
            case_id=case["id"],
            task_id=task_id,
            idempotency_key=idempotency_key,
            confirmed=True,
        )
        updated_task = self.task_workflow.transition(
            task_id=task_id,
            target=TaskStatus.COMPLETED if call.success else TaskStatus.FAILED,
            reason="customer_confirmed",
            actor=auth_context,
            result={
                "approved": True,
                "tool_call": asdict(call),
            },
        )
        resolution = "退款申请已提交" if call.name == "create_refund" and call.success else ""
        updated_case = self.case_workflow.transition(
            case_id=case["id"],
            target=CaseStatus.PROCESSING if call.success else CaseStatus.OPEN,
            reason=_summarize_tool(call),
            actor=auth_context,
            updates={
                "summary": _summarize_tool(call),
                "resolution": resolution,
            },
        )
        if call.success:
            self.repository.append_message(
                case["conversation_id"],
                ChatMessage(role="assistant", content=_summarize_tool(call)),
            )
        return {
            "case": updated_case,
            "task": updated_task,
            "tool_call": asdict(call),
            "message": _summarize_tool(call),
        }

    async def handoff_case(
        self,
        case_id: str,
        auth_context: AuthContext,
        reason: str = "人工坐席接管",
    ) -> dict[str, Any]:
        case = self.repository.get_case(case_id)
        if case is None:
            raise KeyError(f"Case not found: {case_id}")
        call = await self.tool_runtime.execute(
            "handoff_to_human",
            {
                "reason": reason,
                "conversation_id": case["conversation_id"],
                "case_id": case_id,
            },
            auth_context,
            conversation_id=case["conversation_id"],
            case_id=case_id,
            idempotency_key=f"handoff:{case_id}",
            confirmed=True,
        )
        ticket = call.result if call.success else None
        updated_case = self.case_workflow.transition(
            case_id=case_id,
            target=CaseStatus.HANDOFF,
            reason=reason,
            actor=auth_context,
            updates={
                "related_ticket_id": ticket.get("id") if isinstance(ticket, dict) else None,
                "summary": reason,
                "risk_level": "high",
            },
        )
        return {"case": updated_case, "tool_call": asdict(call)}

    async def _run_node(
        self,
        name: str,
        state: AgentState,
        steps: list[AgentStep],
        handler: NodeHandler,
    ) -> AsyncIterator[StreamEvent]:
        yield _event("agent_step", agent=name, status="started", message=f"{name} started")
        start = time.perf_counter()
        tool_call_count = len(state.tool_calls)
        previous_task_id = state.task_id
        try:
            await handler(state)
            elapsed = (time.perf_counter() - start) * 1000
            state.graph_path.append(name)
            step = AgentStep(
                agent=name,
                status="completed",
                message=self._node_summary(name, state),
                elapsed_ms=round(elapsed, 2),
            )
            steps.append(step)
            yield _event("agent_step", **asdict(step))
            yield _event(
                "checkpoint",
                checkpoint_id=state.checkpoint_id,
                conversation_id=state.conversation_id,
                case_id=state.case_id,
                task_id=state.task_id,
                graph_path=state.graph_path,
            )
            if name == "case_binding" and state.metadata.get("latest_case"):
                yield _event("case_update", **state.metadata["latest_case"])
            if name == "action_planner" and state.action_plan:
                yield _event("action_plan", **asdict(state.action_plan))
            if (
                state.task_id
                and state.task_id != previous_task_id
                and state.metadata.get("latest_task")
            ):
                yield _event("task_update", **state.metadata["latest_task"])
            if name == "retrieve_policy":
                for doc in state.retrieved_docs[:3]:
                    yield _event("citation", **asdict(doc))
            if name in {"tool_policy", "human_handoff"}:
                for call in state.tool_calls[tool_call_count:]:
                    yield _event("tool_call", **asdict(call))
                    if call.audit_id:
                        yield _event("audit", audit_id=call.audit_id, tool_name=call.name)
            if name == "human_confirm" and state.pending_confirmation:
                yield _event(
                    "action_required",
                    action_required=state.action_required,
                    pending_confirmation=state.pending_confirmation,
                    case_id=state.case_id,
                    task_id=state.task_id,
                    resume_token=state.resume_token,
                )
        except Exception as exc:  # pragma: no cover - defensive boundary
            elapsed = (time.perf_counter() - start) * 1000
            step = AgentStep(
                agent=name,
                status="failed",
                message=str(exc),
                elapsed_ms=round(elapsed, 2),
            )
            steps.append(step)
            yield _event("error", agent=name, message=str(exc))

    async def _skip_node(
        self,
        name: str,
        state: AgentState,
        steps: list[AgentStep],
        reason: str,
    ) -> AsyncIterator[StreamEvent]:
        step = AgentStep(agent=name, status="skipped", message=reason, elapsed_ms=0.0)
        state.graph_path.append(name)
        steps.append(step)
        yield _event("agent_step", **asdict(step))

    async def _router(self, state: AgentState) -> None:
        latest = state.messages[-1].content
        if self.settings.llm_router_enabled:
            decision = await classify_intent_hybrid(
                latest,
                self.llm,
                timeout_s=self.settings.llm_decision_timeout_s,
            )
            state.intent = decision.intent
            state.metadata["order_id"] = decision.order_id
            state.metadata["router_source"] = decision.source
            state.metadata["router_confidence"] = decision.confidence
            state.metadata["router_reason"] = decision.reason
            state.metadata["router_llm_attempted"] = decision.llm_attempted
            state.metadata["router_llm_json_parse_success"] = decision.llm_json_parse_success
            state.metadata["router_fallback_reason"] = decision.fallback_reason
            return

        state.intent = classify_intent(latest)
        state.metadata["order_id"] = extract_order_id(latest)
        state.metadata["router_source"] = "rule"
        state.metadata["router_confidence"] = 1.0
        state.metadata["router_reason"] = "llm_router_disabled"
        state.metadata["router_llm_attempted"] = False
        state.metadata["router_llm_json_parse_success"] = False

    async def _input_policy(self, state: AgentState) -> None:
        result = check_input_safety(state.messages[-1].content)
        state.guardrail_result = result
        if result.blocked:
            state.metadata["needs_ticket"] = True
            state.metadata["risk_level"] = "high"

    async def _action_planner(self, state: AgentState) -> None:
        latest = state.messages[-1].content
        plan = build_action_plan(latest, state.intent, state.metadata.get("order_id"))
        state.metadata["planner_source"] = "rule"
        state.metadata["llm_plan_available"] = False
        state.metadata["planner_validation_rejected"] = False
        state.metadata["planner_validation_rejected_tools"] = []
        state.metadata["planner_validation_adjustments"] = []
        state.metadata["unsafe_plan_blocked"] = False
        if plan.slots.get("order_reference") == "latest" and not plan.slots.get("order_id"):
            auth = _auth_from_state(state)
            latest_order = self.repository.latest_order_for_user(auth.user_id)
            if latest_order:
                plan.slots["order_id"] = latest_order.id
                state.metadata["order_id"] = latest_order.id
                state.metadata["order_id_source"] = "latest_reference"
        if self.settings.llm_planner_enabled:
            llm_plan = await build_llm_action_plan(
                latest,
                state.intent,
                state.metadata.get("order_id"),
                self.llm,
                timeout_s=self.settings.llm_decision_timeout_s,
            )
            validation = merge_and_validate_action_plan(plan, llm_plan)
            plan = validation.plan
            state.metadata["planner_source"] = validation.source
            state.metadata["llm_plan_available"] = validation.llm_plan_available
            state.metadata["planner_validation_rejected"] = validation.rejected
            state.metadata["planner_validation_rejected_tools"] = validation.rejected_tools
            state.metadata["planner_validation_adjustments"] = validation.adjustments
            state.metadata["unsafe_plan_blocked"] = validation.unsafe_plan_blocked
            if plan.slots.get("order_id"):
                state.metadata["order_id"] = plan.slots["order_id"]
            if plan.slots.get("order_reference") == "latest" and not plan.slots.get("order_id"):
                auth = _auth_from_state(state)
                latest_order = self.repository.latest_order_for_user(auth.user_id)
                if latest_order:
                    plan.slots["order_id"] = latest_order.id
                    state.metadata["order_id"] = latest_order.id
                    state.metadata["order_id_source"] = "latest_reference"
        state.action_plan = plan
        state.metadata["risk_level"] = _max_risk_level(
            str(state.metadata.get("risk_level", "low")),
            plan.risk_level,
        )
        if plan.missing_slots:
            state.metadata["missing_slots"] = plan.missing_slots

    async def _case_binding(self, state: AgentState) -> None:
        auth = _auth_from_state(state)
        latest = state.messages[-1].content
        if state.intent == "closing":
            case = _active_case_for_conversation(
                self.repository,
                state.conversation_id,
                auth.user_id,
            )
            if case:
                state.case_id = case["id"]
                state.task_id = case.get("current_task_id")
                state.metadata["latest_case"] = case
            return
        case = self.repository.create_or_get_case(
            user_id=auth.user_id,
            tenant_id=auth.tenant_id,
            conversation_id=state.conversation_id,
            category=state.intent,
            priority="high" if state.metadata.get("risk_level") == "high" else "medium",
            source_channel="web-console",
            related_order_id=state.metadata.get("order_id"),
            summary=latest[:180],
            risk_level=state.metadata.get("risk_level", "low"),
        )
        state.case_id = case["id"]
        state.task_id = case.get("current_task_id")
        state.metadata["latest_case"] = case

    async def _retrieve_policy(self, state: AgentState) -> None:
        if state.intent == "closing":
            state.retrieved_docs = []
            state.draft_answer = "用户希望结束本次会话。"
            return
        category = {
            "refund": "refund",
            "invoice": "invoice",
            "order": "order",
            "ticket": "support",
        }.get(state.intent)
        original_query = state.messages[-1].content
        query = original_query
        state.metadata["kb_query_source"] = "original"
        if self.settings.llm_query_rewrite_enabled:
            query = await rewrite_kb_query(
                original_query,
                state.intent,
                self.llm,
                timeout_s=self.settings.llm_decision_timeout_s,
            )
            state.metadata["kb_query_source"] = "llm" if query != original_query else "original"
        state.metadata["kb_query"] = query
        docs = self.knowledge_store.search(query, top_k=5, category=category)
        fallback_docs = self.knowledge_store.search(query, top_k=5)
        seen = {doc.id for doc in docs}
        docs = [*docs, *[doc for doc in fallback_docs if doc.id not in seen]][:5]
        state.retrieved_docs = docs
        if docs:
            state.draft_answer = f"知识库命中：{docs[0].title}。{docs[0].content[:160]}"
        else:
            state.draft_answer = "知识库暂无直接命中，需要结合业务工具或人工客服处理。"

    async def _business_action(self, state: AgentState) -> None:
        auth = _auth_from_state(state)
        plan = state.action_plan
        order_id = state.metadata.get("order_id")
        if order_id and state.case_id:
            self.repository.update_case(state.case_id, {"related_order_id": order_id})
        if state.intent == "closing":
            await self._close_conversation_work(state)
            return
        if plan and plan.missing_slots:
            state.metadata["tool_summary"] = "为了避免误操作，请提供需要处理的订单号。"
            return
        if plan and not plan.required_tools and state.intent in {"order", "refund", "invoice"}:
            state.metadata["tool_summary"] = "本轮是政策咨询，无需读取具体订单。"
            return
        if state.intent in {"faq", "unknown"}:
            state.metadata["tool_summary"] = "本轮无需业务工具，基于知识库回复。"
            return
        if state.intent == "handoff" and not order_id:
            state.metadata["needs_ticket"] = True
            state.metadata["tool_summary"] = "用户主动要求人工接管。"
            return
        if state.intent == "privacy" and not order_id:
            state.metadata["needs_ticket"] = True
            state.metadata["risk_level"] = "high"
            state.metadata["tool_summary"] = "请求涉及隐私信息，缺少可校验订单号，转人工留痕。"
            return
        if state.intent == "ticket" and not order_id:
            state.metadata["needs_ticket"] = True
            state.metadata["tool_summary"] = "售后异常需要人工工单跟进，本轮不读取具体订单。"
            return
        if not order_id and state.intent in {"order", "refund", "invoice"}:
            state.metadata["tool_summary"] = "为了避免误操作，请提供需要处理的订单号。"
            return

        if state.intent == "invoice":
            call = await self._execute_tool(
                state,
                "query_invoice",
                {"order_id": order_id},
                auth,
                idempotency_key=f"invoice:{auth.user_id}:{order_id}",
            )
            state.metadata["tool_summary"] = _summarize_tool(call)
            return

        if state.intent == "refund":
            check = await self._execute_tool(
                state,
                "check_refund_eligibility",
                {"order_id": order_id},
                auth,
                idempotency_key=f"refund-check:{auth.user_id}:{order_id}",
            )
            eligible = bool((check.result or {}).get("eligible")) if check.success else False
            wants_create = bool(plan and plan.requires_confirmation)
            if eligible and wants_create:
                pending = {
                    "tool": "create_refund",
                    "arguments": {
                        "order_id": order_id,
                        "reason": "用户在线申请售后退款",
                    },
                    "idempotency_key": f"refund-create:{auth.user_id}:{order_id}",
                    "summary": _summarize_tool(check),
                    "risk_level": "medium",
                    "mode": "dry_run",
                    "estimated_effect": "将创建退款申请，不会立即退回资金。",
                    "requires_confirmation": True,
                }
                task = self.task_workflow.create_confirmation(
                    case_id=state.case_id or "",
                    required_action="confirm_refund",
                    pending_confirmation=pending,
                    actor=auth,
                )
                state.task_id = task["id"]
                state.resume_token = task["resume_token"]
                state.pending_confirmation = {**pending, "task_id": state.task_id}
                state.action_required = "customer_confirmation"
                state.metadata["latest_task"] = task
                state.metadata["tool_summary"] = "退款资格已通过，等待用户确认后再创建退款申请。"
            elif not eligible:
                state.metadata["needs_ticket"] = True
                state.metadata["tool_summary"] = _summarize_tool(check)
            else:
                state.metadata["tool_summary"] = _summarize_tool(check)
            return

        if state.intent in {"order", "ticket", "handoff", "privacy"}:
            call = await self._execute_tool(
                state,
                "query_order",
                {"order_id": order_id},
                auth,
                idempotency_key=f"order:{auth.user_id}:{order_id}",
            )
            if not (call.result or {}).get("authorized"):
                state.metadata["needs_ticket"] = True
                state.metadata["risk_level"] = "high"
                if state.case_id:
                    self.repository.update_case(state.case_id, {"risk_level": "high"})
            state.metadata["tool_summary"] = _summarize_tool(call)

    async def _human_confirmation(self, state: AgentState) -> None:
        if not state.pending_confirmation:
            return
        state.metadata["tool_summary"] = (
            f"{state.metadata.get('tool_summary', '')} 请等待用户确认任务 {state.task_id}。"
        ).strip()

    async def _close_conversation_work(self, state: AgentState) -> None:
        resolution = "用户主动结束本次会话"
        state.metadata["tool_summary"] = resolution
        if not state.case_id:
            return
        for task in self.repository.list_tasks(case_id=state.case_id, status="pending"):
            self.task_workflow.transition(
                task_id=task["id"],
                target=TaskStatus.CANCELLED,
                reason="customer_closed_conversation",
                actor=_auth_from_state(state),
                result={"reason": "customer_closed_conversation"},
            )
        existing_case = self.repository.get_case(state.case_id)
        ticket_id = (existing_case or {}).get("related_ticket_id")
        if ticket_id:
            self.ticket_workflow.update(
                ticket_id=ticket_id,
                payload={
                    "status": "resolved",
                    "resolution_type": "customer_closed_conversation",
                    "closed_reason": resolution,
                },
                actor=_auth_from_state(state),
            )
        case = self.case_workflow.transition(
            case_id=state.case_id,
            target=CaseStatus.RESOLVED,
            reason=resolution,
            actor=_auth_from_state(state),
            updates={"resolution": resolution},
            allow_pending_tasks=True,
        )
        state.metadata["latest_case"] = self.repository.get_case(state.case_id) or case

    async def _human_handoff(self, state: AgentState) -> None:
        auth = _auth_from_state(state)
        latest = state.messages[-1].content
        reason = state.guardrail_result.reason if state.guardrail_result else latest[:120]
        description = (
            f"用户问题：{latest}\n"
            f"系统摘要：{state.metadata.get('tool_summary', '')}\n"
            f"服务案件：{state.case_id or '-'}"
        )
        tool_name = (
            "handoff_to_human"
            if state.guardrail_result and state.guardrail_result.blocked
            else "create_ticket"
        )
        arguments = (
            {"reason": reason, "conversation_id": state.conversation_id, "case_id": state.case_id}
            if tool_name == "handoff_to_human"
            else {
                "title": "售后问题人工跟进",
                "description": description,
                "conversation_id": state.conversation_id,
                "case_id": state.case_id,
                "priority": "high" if state.metadata.get("risk_level") == "high" else "medium",
                "category": state.intent,
                "handoff_reason": reason,
                "agent_summary": state.metadata.get("tool_summary", ""),
                "latest_customer_message": latest,
                "suggested_reply": state.draft_answer,
            }
        )
        call = await self._execute_tool(
            state,
            tool_name,
            arguments,
            auth,
            idempotency_key=f"{tool_name}:{state.case_id}:{state.trace_id}",
            confirmed=True,
        )
        state.metadata["ticket"] = call.result
        if state.case_id and isinstance(call.result, dict):
            case = self.case_workflow.transition(
                case_id=state.case_id,
                target=CaseStatus.HANDOFF,
                reason=_summarize_tool(call),
                actor=auth,
                updates={
                    "related_ticket_id": call.result.get("id"),
                    "summary": _summarize_tool(call),
                },
            )
            state.metadata["latest_case"] = case

    async def _guardrail(self, state: AgentState) -> None:
        candidate = "\n".join(
            part
            for part in [
                state.draft_answer,
                state.metadata.get("tool_summary", ""),
            ]
            if part
        )
        state.guardrail_result = check_output_safety(candidate)

    async def _answer_composer(self, state: AgentState) -> None:
        if state.intent == "closing":
            state.final_answer = "好的，本次会话已结束。如后续还需要帮助，随时再联系我。"
            return
        if state.pending_confirmation:
            state.final_answer = (
                "退款资格已校验通过，但创建退款属于有副作用操作。"
                f"请确认是否继续创建退款申请。任务号：{state.task_id}。"
            )
            return
        if state.guardrail_result and state.guardrail_result.blocked:
            ticket = state.metadata.get("ticket") or {}
            state.final_answer = (
                "这类请求涉及安全或越权风险，我不能按原要求处理。"
                f"已为你转人工客服，工单号：{ticket.get('id', '处理中')}。"
            )
            return

        tool_summary = state.metadata.get("tool_summary", "")
        citations = ", ".join(doc.source for doc in state.retrieved_docs[:2]) or "知识库"
        system_prompt = (
            "你是电商售后智能客服。回答必须简洁、可靠，基于知识库、服务案件状态和工具结果，"
            "不要编造。如果需要确认或人工处理，要明确下一步动作。"
        )
        user_prompt = (
            f"用户画像：{state.user_profile}\n"
            f"用户问题：{state.messages[-1].content}\n"
            f"意图：{state.intent}\n"
            f"服务案件：{state.case_id}\n"
            f"知识库草稿：{state.draft_answer}\n"
            f"工具结果：{tool_summary}\n"
            f"引用来源：{citations}\n"
            "请生成最终客服回复。"
        )
        try:
            answer = await self.llm.complete(system_prompt, user_prompt)
        except Exception as exc:
            answer = _fallback_answer(state, str(exc))
        safety = check_output_safety(answer)
        state.final_answer = safety.redacted_text
        if safety.pii_detected:
            state.guardrail_result = safety

    async def _memory_writer(self, state: AgentState) -> None:
        state.metadata["memory_summary"] = (
            f"最近意图={state.intent}; 服务案件={state.case_id or '无'}; "
            f"Task={state.task_id or '无'}; 订单={state.metadata.get('order_id', '无')}; "
            f"工具={','.join(call.name for call in state.tool_calls[-3:]) or '无'}"
        )

    async def _execute_tool(
        self,
        state: AgentState,
        tool_name: str,
        arguments: dict[str, Any],
        auth_context: AuthContext,
        idempotency_key: str | None = None,
        confirmed: bool = False,
    ) -> ToolCallRecord:
        call = await self.tool_runtime.execute(
            tool_name,
            arguments,
            auth_context,
            conversation_id=state.conversation_id,
            case_id=state.case_id,
            task_id=state.task_id,
            idempotency_key=idempotency_key,
            confirmed=confirmed,
        )
        state.tool_calls.append(call)
        return call

    async def _finalize(
        self,
        state: AgentState,
        steps: list[AgentStep],
    ) -> AsyncIterator[StreamEvent]:
        for chunk in _chunk_answer(state.final_answer):
            yield _event("token", content=chunk)
            await asyncio.sleep(0)
        self.repository.append_message(
            state.conversation_id, ChatMessage(role="assistant", content=state.final_answer)
        )
        self.repository.append_trace(
            conversation_id=state.conversation_id,
            trace_id=state.trace_id,
            steps=steps,
            tool_calls=state.tool_calls,
            summary=state.metadata.get("memory_summary", ""),
        )
        yield _event(
            "final",
            conversation_id=state.conversation_id,
            trace_id=state.trace_id,
            case_id=state.case_id,
            task_id=state.task_id,
            action_required=state.action_required,
            pending_confirmation=state.pending_confirmation,
            resume_token=state.resume_token,
            answer=state.final_answer,
            intent=state.intent,
            action_plan=asdict(state.action_plan) if state.action_plan else None,
            citations=[asdict(doc) for doc in state.retrieved_docs[:3]],
            tool_calls=[asdict(call) for call in state.tool_calls],
            guardrail=asdict(state.guardrail_result)
            if isinstance(state.guardrail_result, GuardrailResult)
            else None,
            graph_path=state.graph_path,
            auth_context=state.auth_context,
            state=state,
        )

    @staticmethod
    def _node_summary(name: str, state: AgentState) -> str:
        if name == "router":
            return f"intent={state.intent}; source={state.metadata.get('router_source', 'rule')}"
        if name == "input_policy":
            return state.guardrail_result.reason if state.guardrail_result else "not_checked"
        if name == "action_planner" and state.action_plan:
            plan = state.action_plan
            tools = ",".join(plan.required_tools) or "none"
            missing = ",".join(plan.missing_slots) or "none"
            return f"tools={tools}; missing={missing}; risk={plan.risk_level}"
        if name == "case_binding":
            return f"服务案件={state.case_id}"
        if name == "retrieve_policy":
            return f"retrieved={len(state.retrieved_docs)}"
        if name == "tool_policy":
            return state.metadata.get("tool_summary", "no tool call")
        if name == "human_confirm":
            return f"pending={state.task_id}" if state.task_id else "no pending task"
        if name == "human_handoff":
            ticket = state.metadata.get("ticket") or {}
            return f"ticket={ticket.get('id', 'none')}"
        if name == "guardrail":
            return state.guardrail_result.reason if state.guardrail_result else "not_checked"
        if name == "memory_writer":
            return state.metadata.get("memory_summary", "")
        return "completed"


def _auth_from_state(state: AgentState) -> AuthContext:
    payload = state.auth_context or {}
    return AuthContext(
        user_id=str(payload.get("user_id") or "anonymous"),
        tenant_id=str(payload.get("tenant_id") or "demo-tenant"),
        roles=tuple(payload.get("roles") or ("customer",)),
        permissions=tuple(payload.get("permissions") or AuthContext("anonymous").permissions),
        source=str(payload.get("source") or "state"),
    )


def _active_case_for_conversation(
    repository: DemoRepository,
    conversation_id: str,
    user_id: str,
) -> dict[str, Any] | None:
    return next(
        (
            case
            for case in repository.list_cases(user_id=user_id)
            if case.get("conversation_id") == conversation_id
            and case.get("status") not in {"resolved", "closed"}
        ),
        None,
    )


def _max_risk_level(current: str, planned: str) -> str:
    order = {"low": 0, "medium": 1, "high": 2}
    return current if order.get(current, 0) >= order.get(planned, 0) else planned


def _summarize_tool(call: ToolCallRecord) -> str:
    if not call.success:
        return f"{call.name} failed: {call.error or (call.result or {}).get('reason', 'unknown')}"
    result = call.result or {}
    if call.name == "query_order":
        if not result.get("authorized"):
            return result.get("error", "订单查询失败")
        order = result["order"]
        return (
            f"订单{order['id']}状态{order['status']}，商品{order['item']}，"
            f"物流={order['carrier']} {order['tracking_no']}"
        )
    if call.name == "check_refund_eligibility":
        return f"退款资格={result.get('eligible')}，原因={result.get('reason')}"
    if call.name == "create_refund":
        if not result.get("created"):
            return f"退款未创建：{result.get('reason', result.get('error', '未知原因'))}"
        refund = result["refund"]
        return f"已创建退款{refund['id']}，金额{refund['amount']}，状态{refund['status']}"
    if call.name == "query_invoice":
        download_url = result.get("download_url") or "暂无"
        return f"发票状态{result.get('invoice_status')}，下载={download_url}"
    if call.name in {"create_ticket", "handoff_to_human"}:
        return f"已创建工单{result.get('id')}，状态{result.get('status')}"
    return str(result)


def _fallback_answer(state: AgentState, reason: str) -> str:
    parts = []
    if state.intent == "faq":
        parts.append(state.draft_answer)
    if state.metadata.get("tool_summary"):
        parts.append(state.metadata["tool_summary"])
    if state.metadata.get("ticket"):
        parts.append(f"已创建工单 {state.metadata['ticket'].get('id')}，人工客服会继续跟进。")
    if not parts:
        parts.append("我已记录你的问题，当前信息不足，建议补充订单号或问题截图。")
    citations = ", ".join(doc.source for doc in state.retrieved_docs[:2])
    suffix = f"（来源：{citations}）" if citations else ""
    fallback_note = (
        f"\n\n注：云模型暂不可用，已使用本地兜底回复。{reason[:80]}" if reason else ""
    )
    return "；".join(parts) + suffix + fallback_note


def _chunk_answer(answer: str, size: int = 18) -> list[str]:
    return [answer[index : index + size] for index in range(0, len(answer), size)] or [""]
