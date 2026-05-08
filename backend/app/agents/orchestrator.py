from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator
from dataclasses import asdict
from typing import Any

from app.agents.guardrails import check_input_safety, check_output_safety
from app.agents.router import classify_intent, extract_order_id
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
from app.tools.business_tools import BusinessToolRegistry


def _event(event: str, **data: Any) -> StreamEvent:
    return StreamEvent(event=event, data=data)  # type: ignore[arg-type]


class AgentOrchestrator:
    """Coordinates SmartCS agents and emits a frontend-friendly execution stream."""

    def __init__(
        self,
        repository: DemoRepository,
        knowledge_store: Any,
        tools: BusinessToolRegistry,
        llm: LLMProvider,
    ) -> None:
        self.repository = repository
        self.knowledge_store = knowledge_store
        self.tools = tools
        self.llm = llm

    async def run_stream(
        self,
        message: str,
        user_id: str = "anonymous",
        conversation_id: str | None = None,
    ) -> AsyncIterator[StreamEvent]:
        conversation = self.repository.get_or_create_conversation(conversation_id, user_id)
        user_message = ChatMessage(role="user", content=message)
        self.repository.append_message(conversation.id, user_message)
        state = AgentState(
            messages=[*conversation.messages, user_message],
            user_profile=self.repository.get_user_profile(user_id),
            conversation_id=conversation.id,
        )
        steps: list[AgentStep] = []

        async for event in self._run_node("router", state, steps, self._router):
            yield event

        input_guardrail = check_input_safety(message)
        if input_guardrail.blocked:
            state.guardrail_result = input_guardrail
            async for event in self._run_node(
                "ticket_escalation", state, steps, self._ticket_escalation
            ):
                yield event
            async for event in self._run_node(
                "answer_composer", state, steps, self._answer_composer
            ):
                yield event
            async for event in self._finalize(state, steps):
                yield event
            return

        async for event in self._run_node("rag_answer", state, steps, self._rag_answer):
            yield event

        if state.intent in {"order", "refund", "invoice", "ticket", "handoff"}:
            async for event in self._run_node("order_refund", state, steps, self._order_refund):
                yield event

        if state.intent in {"ticket", "handoff"} or state.metadata.get("needs_ticket"):
            async for event in self._run_node(
                "ticket_escalation", state, steps, self._ticket_escalation
            ):
                yield event

        async for event in self._run_node("guardrail", state, steps, self._guardrail):
            yield event

        async for event in self._run_node("answer_composer", state, steps, self._answer_composer):
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
    ) -> AgentState:
        final: AgentState | None = None
        async for event in self.run_stream(message, user_id, conversation_id):
            if event.event == "final":
                final = event.data["state"]
        if final is None:  # pragma: no cover - defensive
            raise RuntimeError("Agent run did not finalize")
        return final

    async def _run_node(
        self,
        name: str,
        state: AgentState,
        steps: list[AgentStep],
        handler,
    ) -> AsyncIterator[StreamEvent]:
        yield _event("agent_step", agent=name, status="started", message=f"{name} started")
        start = time.perf_counter()
        tool_call_count = len(state.tool_calls)
        try:
            await handler(state)
            elapsed = (time.perf_counter() - start) * 1000
            step = AgentStep(
                agent=name,
                status="completed",
                message=self._node_summary(name, state),
                elapsed_ms=round(elapsed, 2),
            )
            steps.append(step)
            yield _event("agent_step", **asdict(step))
            if name == "rag_answer":
                for doc in state.retrieved_docs[:3]:
                    yield _event("citation", **asdict(doc))
            if name in {"order_refund", "ticket_escalation"}:
                for call in state.tool_calls[tool_call_count:]:
                    yield _event("tool_call", **asdict(call))
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

    async def _router(self, state: AgentState) -> None:
        latest = state.messages[-1].content
        state.intent = classify_intent(latest)
        state.metadata["order_id"] = extract_order_id(latest)

    async def _rag_answer(self, state: AgentState) -> None:
        query = state.messages[-1].content
        category = {
            "refund": "refund",
            "invoice": "invoice",
            "order": "order",
            "ticket": "support",
        }.get(state.intent)
        docs = self.knowledge_store.search(query, top_k=5, category=category)
        if not docs:
            docs = self.knowledge_store.search(query, top_k=5)
        state.retrieved_docs = docs
        if docs:
            state.draft_answer = f"知识库命中：{docs[0].title}。{docs[0].content[:160]}"
        else:
            state.draft_answer = "知识库暂无直接命中，需要结合业务工具或人工客服处理。"

    async def _order_refund(self, state: AgentState) -> None:
        latest = state.messages[-1].content
        user_id = state.user_profile["user_id"]
        order_id = state.metadata.get("order_id")
        if not order_id:
            latest_order = self.repository.latest_order_for_user(user_id)
            order_id = latest_order.id if latest_order else ""
            state.metadata["order_id"] = order_id
        if not order_id:
            state.metadata["needs_ticket"] = True
            state.metadata["tool_summary"] = "未找到可处理的订单号"
            return

        if state.intent == "invoice":
            call = await self.tools.call_tool(
                "query_invoice",
                {"order_id": order_id, "user_id": user_id},
            )
            state.tool_calls.append(call)
            state.metadata["tool_summary"] = _summarize_tool(call)
            return

        if state.intent == "refund":
            check = await self.tools.call_tool(
                "check_refund_eligibility", {"order_id": order_id, "user_id": user_id}
            )
            state.tool_calls.append(check)
            eligible = bool((check.result or {}).get("eligible")) if check.success else False
            wants_create = any(word in latest for word in ("申请", "我要", "帮我", "退货", "退款"))
            if eligible and wants_create:
                refund = await self.tools.call_tool(
                    "create_refund",
                    {"order_id": order_id, "user_id": user_id, "reason": "用户在线申请售后退款"},
                )
                state.tool_calls.append(refund)
            elif not eligible:
                state.metadata["needs_ticket"] = True
            state.metadata["tool_summary"] = "; ".join(
                _summarize_tool(call) for call in state.tool_calls[-2:]
            )
            return

        call = await self.tools.call_tool("query_order", {"order_id": order_id, "user_id": user_id})
        state.tool_calls.append(call)
        if not (call.result or {}).get("authorized"):
            state.metadata["needs_ticket"] = True
        state.metadata["tool_summary"] = _summarize_tool(call)

    async def _ticket_escalation(self, state: AgentState) -> None:
        user_id = state.user_profile["user_id"]
        latest = state.messages[-1].content
        reason = state.guardrail_result.reason if state.guardrail_result else latest[:120]
        if state.guardrail_result and state.guardrail_result.blocked:
            call = await self.tools.call_tool(
                "handoff_to_human",
                {
                    "user_id": user_id,
                    "reason": reason,
                    "conversation_id": state.conversation_id,
                },
            )
        else:
            description = (
                f"用户问题：{latest}\n"
                f"系统摘要：{state.metadata.get('tool_summary', '')}"
            )
            call = await self.tools.call_tool(
                "create_ticket",
                {
                    "user_id": user_id,
                    "title": "售后问题人工跟进",
                    "description": description,
                    "priority": "medium",
                    "category": state.intent,
                },
            )
        state.tool_calls.append(call)
        state.metadata["ticket"] = call.result

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
            "你是电商售后智能客服。回答必须简洁、可靠，基于知识库和工具结果，不编造。"
            "如果工具返回无权限或信息不足，要说明下一步。"
        )
        user_prompt = (
            f"用户画像：{state.user_profile}\n"
            f"用户问题：{state.messages[-1].content}\n"
            f"意图：{state.intent}\n"
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
            f"最近意图={state.intent}; 订单={state.metadata.get('order_id', '无')}; "
            f"工具={','.join(call.name for call in state.tool_calls[-3:]) or '无'}"
        )

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
            answer=state.final_answer,
            intent=state.intent,
            citations=[asdict(doc) for doc in state.retrieved_docs[:3]],
            tool_calls=[asdict(call) for call in state.tool_calls],
            guardrail=asdict(state.guardrail_result)
            if isinstance(state.guardrail_result, GuardrailResult)
            else None,
            state=state,
        )

    @staticmethod
    def _node_summary(name: str, state: AgentState) -> str:
        if name == "router":
            return f"intent={state.intent}"
        if name == "rag_answer":
            return f"retrieved={len(state.retrieved_docs)}"
        if name == "order_refund":
            return state.metadata.get("tool_summary", "no tool call")
        if name == "ticket_escalation":
            ticket = state.metadata.get("ticket") or {}
            return f"ticket={ticket.get('id', 'none')}"
        if name == "guardrail":
            return state.guardrail_result.reason if state.guardrail_result else "not_checked"
        if name == "memory_writer":
            return state.metadata.get("memory_summary", "")
        return "completed"


def _summarize_tool(call: ToolCallRecord) -> str:
    if not call.success:
        return f"{call.name} failed: {call.error}"
    result = call.result or {}
    if call.name == "query_order":
        if not result.get("authorized"):
            return result.get("error", "订单查询失败")
        order = result["order"]
        return (
            f"订单{order['id']}状态={order['status']}，商品={order['item']}，"
            f"物流={order['carrier']} {order['tracking_no']}"
        )
    if call.name == "check_refund_eligibility":
        return f"退款资格={result.get('eligible')}，原因={result.get('reason')}"
    if call.name == "create_refund":
        if not result.get("created"):
            return f"退款未创建：{result.get('reason', result.get('error', '未知原因'))}"
        refund = result["refund"]
        return f"已创建退款{refund['id']}，金额={refund['amount']}，状态={refund['status']}"
    if call.name == "query_invoice":
        download_url = result.get("download_url") or "暂无"
        return f"发票状态={result.get('invoice_status')}，下载={download_url}"
    if call.name in {"create_ticket", "handoff_to_human"}:
        return f"已创建工单{result.get('id')}，状态={result.get('status')}"
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
