from __future__ import annotations

import inspect
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from app.models.schemas import ToolCallRecord

ToolHandler = Callable[..., Awaitable[Any]]


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    input_schema: dict[str, Any]
    category: str


class BusinessToolRegistry:
    """MCP-style tool registry used by agents and exposed by the API."""

    def __init__(self, repository: Any) -> None:
        self.repository = repository
        self._tools: dict[str, tuple[ToolDefinition, Callable[..., Any]]] = {}
        self._register_defaults()

    def register(
        self,
        definition: ToolDefinition,
        handler: Callable[..., Any],
    ) -> None:
        self._tools[definition.name] = (definition, handler)

    def list_tools(self) -> list[dict[str, Any]]:
        return [
            {
                "name": definition.name,
                "description": definition.description,
                "inputSchema": definition.input_schema,
                "category": definition.category,
            }
            for definition, _ in self._tools.values()
        ]

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> ToolCallRecord:
        start = time.perf_counter()
        definition_handler = self._tools.get(name)
        if definition_handler is None:
            return ToolCallRecord(
                name=name,
                arguments=arguments,
                success=False,
                error=f"Tool not found: {name}",
            )
        _, handler = definition_handler
        try:
            result = handler(**arguments)
            if inspect.isawaitable(result):
                result = await result
            return ToolCallRecord(
                name=name,
                arguments=arguments,
                success=True,
                result=result,
                duration_ms=(time.perf_counter() - start) * 1000,
            )
        except Exception as exc:  # pragma: no cover - defensive boundary
            return ToolCallRecord(
                name=name,
                arguments=arguments,
                success=False,
                error=str(exc),
                duration_ms=(time.perf_counter() - start) * 1000,
            )

    def _register_defaults(self) -> None:
        self.register(
            ToolDefinition(
                name="query_order",
                description="查询当前用户名下订单、物流、金额和发票状态",
                input_schema={
                    "type": "object",
                    "properties": {
                        "order_id": {"type": "string"},
                        "user_id": {"type": "string"},
                    },
                    "required": ["order_id", "user_id"],
                },
                category="order",
            ),
            self.repository.query_order,
        )
        self.register(
            ToolDefinition(
                name="check_refund_eligibility",
                description="检查订单是否符合自助退款规则",
                input_schema={
                    "type": "object",
                    "properties": {
                        "order_id": {"type": "string"},
                        "user_id": {"type": "string"},
                    },
                    "required": ["order_id", "user_id"],
                },
                category="refund",
            ),
            self.repository.check_refund_eligibility,
        )
        self.register(
            ToolDefinition(
                name="create_refund",
                description="创建退款申请",
                input_schema={
                    "type": "object",
                    "properties": {
                        "order_id": {"type": "string"},
                        "user_id": {"type": "string"},
                        "reason": {"type": "string"},
                    },
                    "required": ["order_id", "user_id", "reason"],
                },
                category="refund",
            ),
            self.repository.create_refund,
        )
        self.register(
            ToolDefinition(
                name="query_invoice",
                description="查询订单发票状态和下载地址",
                input_schema={
                    "type": "object",
                    "properties": {
                        "order_id": {"type": "string"},
                        "user_id": {"type": "string"},
                    },
                    "required": ["order_id", "user_id"],
                },
                category="invoice",
            ),
            self.repository.query_invoice,
        )
        self.register(
            ToolDefinition(
                name="create_ticket",
                description="创建人工客服工单",
                input_schema={
                    "type": "object",
                    "properties": {
                        "user_id": {"type": "string"},
                        "tenant_id": {"type": "string"},
                        "title": {"type": "string"},
                        "description": {"type": "string"},
                        "conversation_id": {"type": "string"},
                        "case_id": {"type": "string"},
                        "priority": {"type": "string"},
                        "category": {"type": "string"},
                        "assigned_to": {"type": "string"},
                        "assignee_name": {"type": "string"},
                        "sla_deadline": {"type": "string"},
                        "handoff_reason": {"type": "string"},
                        "agent_summary": {"type": "string"},
                        "customer_emotion": {"type": "string"},
                        "latest_customer_message": {"type": "string"},
                        "suggested_reply": {"type": "string"},
                        "human_reply": {"type": "string"},
                        "resolution_type": {"type": "string"},
                        "closed_reason": {"type": "string"},
                        "csat_score": {"type": "integer"},
                    },
                    "required": ["user_id", "title", "description"],
                },
                category="ticket",
            ),
            self._create_ticket,
        )
        self.register(
            ToolDefinition(
                name="handoff_to_human",
                description="将敏感或复杂问题移交人工客服",
                input_schema={
                    "type": "object",
                    "properties": {
                        "user_id": {"type": "string"},
                        "tenant_id": {"type": "string"},
                        "reason": {"type": "string"},
                        "conversation_id": {"type": "string"},
                        "case_id": {"type": "string"},
                    },
                    "required": ["user_id", "reason", "conversation_id"],
                },
                category="ticket",
            ),
            self._handoff_to_human,
        )

    def _handoff_to_human(
        self,
        user_id: str,
        reason: str,
        conversation_id: str,
        case_id: str | None = None,
        tenant_id: str = "demo-tenant",
    ) -> dict[str, Any]:
        return self._create_ticket(
            user_id=user_id,
            tenant_id=tenant_id,
            conversation_id=conversation_id,
            case_id=case_id,
            title="人工客服介入",
            description=f"会话 {conversation_id} 需要人工处理：{reason}",
            priority="high",
            category="handoff",
            handoff_reason=reason,
            latest_customer_message=reason,
        )

    def _create_ticket(
        self,
        user_id: str,
        title: str,
        description: str,
        tenant_id: str = "demo-tenant",
        conversation_id: str | None = None,
        case_id: str | None = None,
        priority: str = "medium",
        category: str = "general",
        assigned_to: str | None = None,
        assignee_name: str | None = None,
        sla_deadline: str | None = None,
        handoff_reason: str = "",
        agent_summary: str = "",
        customer_emotion: str = "neutral",
        latest_customer_message: str = "",
        suggested_reply: str = "",
        human_reply: str = "",
        resolution_type: str = "",
        closed_reason: str = "",
        csat_score: int | None = None,
    ) -> dict[str, Any]:
        existing = self._active_ticket_for_context(
            user_id=user_id,
            tenant_id=tenant_id,
            conversation_id=conversation_id,
            case_id=case_id,
        )
        if existing:
            updated = self.repository.update_ticket(
                existing["id"],
                {
                    "priority": _higher_priority(existing.get("priority", "medium"), priority),
                    "category": category or existing.get("category"),
                    "description": _merge_ticket_text(existing.get("description", ""), description),
                    "handoff_reason": handoff_reason or existing.get("handoff_reason", ""),
                    "agent_summary": agent_summary or existing.get("agent_summary", ""),
                    "customer_emotion": customer_emotion
                    or existing.get("customer_emotion", "neutral"),
                    "latest_customer_message": latest_customer_message
                    or existing.get("latest_customer_message", ""),
                    "suggested_reply": suggested_reply or existing.get("suggested_reply", ""),
                },
            )
            result = dict(updated or existing)
            result["reused"] = True
            return result

        ticket = self.repository.create_ticket(
            user_id=user_id,
            tenant_id=tenant_id,
            title=title,
            description=description,
            priority=priority,
            category=category,
            assigned_to=assigned_to,
            assignee_name=assignee_name,
            sla_deadline=sla_deadline,
            handoff_reason=handoff_reason,
            agent_summary=agent_summary,
            customer_emotion=customer_emotion,
            latest_customer_message=latest_customer_message,
            suggested_reply=suggested_reply,
            human_reply=human_reply,
            resolution_type=resolution_type,
            closed_reason=closed_reason,
            csat_score=csat_score,
        )
        ticket["reused"] = False
        return ticket

    def _active_ticket_for_context(
        self,
        *,
        user_id: str,
        tenant_id: str,
        conversation_id: str | None,
        case_id: str | None,
    ) -> dict[str, Any] | None:
        ticket_id = self._ticket_id_from_case(case_id)
        if ticket_id:
            ticket = self._ticket_by_id(ticket_id)
            if _is_reusable_ticket(ticket, user_id=user_id, tenant_id=tenant_id):
                return ticket

        if conversation_id:
            linked_cases = [
                case
                for case in self.repository.list_cases()
                if case.get("conversation_id") == conversation_id and case.get("related_ticket_id")
            ]
            linked_cases.sort(key=lambda case: str(case.get("updated_at") or ""), reverse=True)
            for case in linked_cases:
                ticket = self._ticket_by_id(str(case.get("related_ticket_id")))
                if _is_reusable_ticket(ticket, user_id=user_id, tenant_id=tenant_id):
                    return ticket
        return None

    def _ticket_id_from_case(self, case_id: str | None) -> str | None:
        if not case_id:
            return None
        case = self.repository.get_case(case_id)
        if not case:
            return None
        ticket_id = case.get("related_ticket_id")
        return str(ticket_id) if ticket_id else None

    def _ticket_by_id(self, ticket_id: str) -> dict[str, Any] | None:
        return next(
            (ticket for ticket in self.repository.list_tickets() if ticket.get("id") == ticket_id),
            None,
        )


def _is_reusable_ticket(
    ticket: dict[str, Any] | None,
    *,
    user_id: str,
    tenant_id: str,
) -> bool:
    if not ticket:
        return False
    return (
        ticket.get("status") in {"open", "pending"}
        and ticket.get("user_id") == user_id
        and ticket.get("tenant_id", "demo-tenant") == tenant_id
    )


def _higher_priority(current: str, incoming: str) -> str:
    rank = {"low": 0, "medium": 1, "high": 2}
    return incoming if rank.get(incoming, 1) > rank.get(current, 1) else current


def _merge_ticket_text(current: str, incoming: str) -> str:
    if not incoming or incoming in current:
        return current
    if not current:
        return incoming
    return f"{current}\n\n--- latest handoff ---\n{incoming}"
