from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta
from threading import RLock
from typing import Any
from uuid import uuid4

from app.data.seed import seed_orders, seed_users
from app.models.schemas import AgentStep, ChatMessage, ToolCallRecord, utc_now


@dataclass
class Order:
    id: str
    user_id: str
    item: str
    amount: float
    status: str
    paid_at: str
    delivered_at: str | None
    carrier: str
    tracking_no: str
    invoice_status: str = "not_requested"
    refund_id: str | None = None
    tenant_id: str = "demo-tenant"


@dataclass
class Refund:
    id: str
    order_id: str
    user_id: str
    status: str
    reason: str
    amount: float
    created_at: str = field(default_factory=utc_now)


@dataclass
class Ticket:
    id: str
    user_id: str
    title: str
    description: str
    priority: str
    category: str
    status: str = "open"
    assigned_to: str | None = None
    assignee_name: str | None = None
    sla_deadline: str | None = None
    handoff_reason: str = ""
    agent_summary: str = ""
    customer_emotion: str = "neutral"
    latest_customer_message: str = ""
    suggested_reply: str = ""
    human_reply: str = ""
    resolution_type: str = ""
    closed_reason: str = ""
    csat_score: int | None = None
    tenant_id: str = "demo-tenant"
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)


@dataclass
class SupportCase:
    id: str
    user_id: str
    tenant_id: str
    conversation_id: str
    category: str
    status: str
    priority: str
    source_channel: str
    related_order_id: str | None = None
    related_ticket_id: str | None = None
    current_task_id: str | None = None
    resolution: str = ""
    risk_level: str = "low"
    summary: str = ""
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)


@dataclass
class CaseTask:
    id: str
    case_id: str
    type: str
    status: str
    required_action: str
    pending_confirmation: dict[str, Any] | None = None
    assigned_to: str | None = None
    deadline: str | None = None
    result: dict[str, Any] | None = None
    resume_token: str = field(default_factory=lambda: uuid4().hex)
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)


@dataclass
class ToolAuditLog:
    id: str
    conversation_id: str
    case_id: str | None
    task_id: str | None
    tool_name: str
    arguments: dict[str, Any]
    auth_context: dict[str, Any]
    policy_status: str
    success: bool
    result: Any = None
    error: str | None = None
    idempotency_key: str | None = None
    requires_confirmation: bool = False
    created_at: str = field(default_factory=utc_now)


@dataclass
class ConversationRecord:
    id: str
    user_id: str
    tenant_id: str = "demo-tenant"
    messages: list[ChatMessage] = field(default_factory=list)
    agent_steps: list[AgentStep] = field(default_factory=list)
    tool_calls: list[ToolCallRecord] = field(default_factory=list)
    summary: str = ""
    trace_ids: list[str] = field(default_factory=list)
    updated_at: str = field(default_factory=utc_now)


class DemoRepository:
    """Thread-safe in-memory repository used for local demos and tests.

    The public methods intentionally mirror the future SQL/Redis adapters, so switching to
    PostgreSQL and Redis does not change agent code.
    """

    def __init__(self) -> None:
        self._lock = RLock()
        self.users: dict[str, dict[str, Any]] = {}
        self.orders: dict[str, Order] = {}
        self.refunds: dict[str, Refund] = {}
        self.tickets: dict[str, Ticket] = {}
        self.cases: dict[str, SupportCase] = {}
        self.tasks: dict[str, CaseTask] = {}
        self.tool_audits: dict[str, ToolAuditLog] = {}
        self.conversations: dict[str, ConversationRecord] = {}
        self._seed()

    def _seed(self) -> None:
        for user_id, name, tier, preference in seed_users():
            self.users[user_id] = {
                "user_id": user_id,
                "tenant_id": "demo-tenant",
                "name": name,
                "tier": tier,
                "preference": preference,
            }

        self.orders = {row["id"]: Order(**row) for row in seed_orders()}

    def get_user_profile(self, user_id: str) -> dict[str, Any]:
        with self._lock:
            return self.users.get(user_id, self.users["anonymous"]).copy()

    def get_or_create_conversation(
        self,
        conversation_id: str | None,
        user_id: str,
        tenant_id: str = "demo-tenant",
    ) -> ConversationRecord:
        with self._lock:
            cid = conversation_id or uuid4().hex
            if cid not in self.conversations:
                self.conversations[cid] = ConversationRecord(
                    id=cid,
                    user_id=user_id,
                    tenant_id=tenant_id,
                )
            return self.conversations[cid]

    def append_message(self, conversation_id: str, message: ChatMessage) -> None:
        with self._lock:
            self.conversations[conversation_id].messages.append(message)
            self.conversations[conversation_id].updated_at = utc_now()

    def append_trace(
        self,
        conversation_id: str,
        trace_id: str,
        steps: list[AgentStep],
        tool_calls: list[ToolCallRecord],
        summary: str,
    ) -> None:
        with self._lock:
            record = self.conversations[conversation_id]
            record.trace_ids.append(trace_id)
            record.agent_steps.extend(steps)
            record.tool_calls.extend(tool_calls)
            record.summary = summary
            record.updated_at = utc_now()

    def conversation_snapshot(self, conversation_id: str) -> dict[str, Any] | None:
        with self._lock:
            record = self.conversations.get(conversation_id)
            if record is None:
                return None
            return {
                "id": record.id,
                "user_id": record.user_id,
                "tenant_id": record.tenant_id,
                "summary": record.summary,
                "messages": [asdict(msg) for msg in record.messages],
                "agent_steps": [asdict(step) for step in record.agent_steps[-50:]],
                "tool_calls": [asdict(call) for call in record.tool_calls[-50:]],
                "trace_ids": record.trace_ids[-10:],
                "cases": [
                    asdict(case)
                    for case in self.cases.values()
                    if case.conversation_id == conversation_id
                ],
                "tasks": [
                    asdict(task)
                    for task in self.tasks.values()
                    if self.cases.get(task.case_id)
                    and self.cases[task.case_id].conversation_id == conversation_id
                ],
                "updated_at": record.updated_at,
            }

    def query_order(self, order_id: str, user_id: str) -> dict[str, Any]:
        with self._lock:
            order = self.orders.get(order_id)
            if order is None:
                return {"found": False, "authorized": False, "error": "订单不存在"}
            if order.user_id != user_id:
                return {"found": True, "authorized": False, "error": "无权查看该订单"}
            return {"found": True, "authorized": True, "order": asdict(order)}

    def latest_order_for_user(self, user_id: str) -> Order | None:
        with self._lock:
            orders = [order for order in self.orders.values() if order.user_id == user_id]
            sorted_orders = sorted(orders, key=lambda order: order.paid_at, reverse=True)
            return sorted_orders[0] if sorted_orders else None

    def get_order_metadata(self, order_id: str) -> dict[str, Any] | None:
        with self._lock:
            order = self.orders.get(order_id)
            return asdict(order) if order else None

    def get_user_tenant_id(self, user_id: str) -> str | None:
        with self._lock:
            user = self.users.get(user_id)
            return str(user.get("tenant_id")) if user else None

    def check_refund_eligibility(self, order_id: str, user_id: str) -> dict[str, Any]:
        order_result = self.query_order(order_id, user_id)
        if not order_result.get("authorized"):
            return {**order_result, "eligible": False}
        order = order_result["order"]
        if order["refund_id"]:
            return {"eligible": False, "reason": "该订单已经创建过退款申请", "order": order}
        if order["status"] not in {"delivered", "shipped"}:
            return {"eligible": False, "reason": "订单当前状态暂不支持退款", "order": order}
        delivered_at = order["delivered_at"]
        if delivered_at:
            delivered_date = datetime.fromisoformat(delivered_at).date()
            if date.today() - delivered_date > timedelta(days=7):
                return {
                    "eligible": False,
                    "reason": "订单已超过7天无理由退款窗口，建议创建工单人工审核",
                    "order": order,
                }
        return {"eligible": True, "reason": "符合自助退款规则", "order": order}

    def create_refund(self, order_id: str, user_id: str, reason: str) -> dict[str, Any]:
        with self._lock:
            eligibility = self.check_refund_eligibility(order_id, user_id)
            if not eligibility.get("eligible"):
                return {"created": False, **eligibility}
            order = self.orders[order_id]
            refund = Refund(
                id=f"RF-{uuid4().hex[:8].upper()}",
                order_id=order_id,
                user_id=user_id,
                status="submitted",
                reason=reason,
                amount=order.amount,
            )
            order.refund_id = refund.id
            self.refunds[refund.id] = refund
            return {"created": True, "refund": asdict(refund), "order": asdict(order)}

    def query_invoice(self, order_id: str, user_id: str) -> dict[str, Any]:
        order_result = self.query_order(order_id, user_id)
        if not order_result.get("authorized"):
            return order_result
        order = order_result["order"]
        return {
            "found": True,
            "authorized": True,
            "order_id": order_id,
            "invoice_status": order["invoice_status"],
            "download_url": f"https://demo.smartcs.local/invoices/{order_id}.pdf"
            if order["invoice_status"] == "issued"
            else None,
        }

    def create_ticket(
        self,
        user_id: str,
        title: str,
        description: str,
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
        tenant_id: str = "demo-tenant",
    ) -> dict[str, Any]:
        with self._lock:
            ticket = Ticket(
                id=f"TK-{uuid4().hex[:8].upper()}",
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
            self.tickets[ticket.id] = ticket
            return asdict(ticket)

    def list_tickets(self) -> list[dict[str, Any]]:
        with self._lock:
            tickets = sorted(self.tickets.values(), key=lambda ticket: ticket.created_at)
            return [asdict(ticket) for ticket in tickets]

    def update_ticket(self, ticket_id: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        with self._lock:
            ticket = self.tickets.get(ticket_id)
            if ticket is None:
                return None
            previous_human_reply = ticket.human_reply
            for field_name in (
                "status",
                "priority",
                "category",
                "title",
                "description",
                "assigned_to",
                "assignee_name",
                "sla_deadline",
                "handoff_reason",
                "agent_summary",
                "customer_emotion",
                "latest_customer_message",
                "suggested_reply",
                "human_reply",
                "resolution_type",
                "closed_reason",
                "csat_score",
                "tenant_id",
            ):
                if field_name in payload and payload[field_name] is not None:
                    setattr(ticket, field_name, payload[field_name])
            ticket.updated_at = utc_now()
            if previous_human_reply != ticket.human_reply:
                ticket.updated_at = utc_now()
            return asdict(ticket)

    def create_or_get_case(
        self,
        user_id: str,
        tenant_id: str,
        conversation_id: str,
        category: str,
        priority: str = "medium",
        source_channel: str = "web",
        related_order_id: str | None = None,
        summary: str = "",
        risk_level: str = "low",
    ) -> dict[str, Any]:
        with self._lock:
            for case in self.cases.values():
                if (
                    case.conversation_id == conversation_id
                    and case.status not in {"resolved", "closed"}
                ):
                    case.category = category or case.category
                    case.related_order_id = related_order_id or case.related_order_id
                    case.summary = summary or case.summary
                    case.risk_level = risk_level or case.risk_level
                    case.updated_at = utc_now()
                    return asdict(case)
            case = SupportCase(
                id=f"CASE-{uuid4().hex[:8].upper()}",
                user_id=user_id,
                tenant_id=tenant_id,
                conversation_id=conversation_id,
                category=category,
                status="open",
                priority=priority,
                source_channel=source_channel,
                related_order_id=related_order_id,
                summary=summary,
                risk_level=risk_level,
            )
            self.cases[case.id] = case
            return asdict(case)

    def list_cases(
        self,
        user_id: str | None = None,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        with self._lock:
            cases = list(self.cases.values())
            if user_id:
                cases = [case for case in cases if case.user_id == user_id]
            if status:
                cases = [case for case in cases if case.status == status]
            sorted_cases = sorted(cases, key=lambda item: item.updated_at, reverse=True)
            return [asdict(case) for case in sorted_cases]

    def get_case(self, case_id: str) -> dict[str, Any] | None:
        with self._lock:
            case = self.cases.get(case_id)
            return asdict(case) if case else None

    def update_case(self, case_id: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        with self._lock:
            case = self.cases.get(case_id)
            if case is None:
                return None
            for field_name in (
                "status",
                "priority",
                "category",
                "related_order_id",
                "related_ticket_id",
                "current_task_id",
                "resolution",
                "risk_level",
                "summary",
            ):
                if field_name in payload and payload[field_name] is not None:
                    setattr(case, field_name, payload[field_name])
            case.updated_at = utc_now()
            return asdict(case)

    def close_case(self, case_id: str, resolution: str) -> dict[str, Any] | None:
        return self.update_case(case_id, {"status": "resolved", "resolution": resolution})

    def create_task(
        self,
        case_id: str,
        task_type: str,
        required_action: str,
        pending_confirmation: dict[str, Any] | None = None,
        status: str = "pending",
        assigned_to: str | None = None,
        deadline: str | None = None,
        result: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            task = CaseTask(
                id=f"TASK-{uuid4().hex[:8].upper()}",
                case_id=case_id,
                type=task_type,
                status=status,
                required_action=required_action,
                pending_confirmation=pending_confirmation,
                assigned_to=assigned_to,
                deadline=deadline,
                result=result,
            )
            self.tasks[task.id] = task
            return asdict(task)

    def get_task(self, task_id: str) -> dict[str, Any] | None:
        with self._lock:
            task = self.tasks.get(task_id)
            return asdict(task) if task else None

    def list_tasks(
        self,
        case_id: str | None = None,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        with self._lock:
            tasks = list(self.tasks.values())
            if case_id:
                tasks = [task for task in tasks if task.case_id == case_id]
            if status:
                tasks = [task for task in tasks if task.status == status]
            sorted_tasks = sorted(tasks, key=lambda item: item.updated_at, reverse=True)
            return [asdict(task) for task in sorted_tasks]

    def update_task(self, task_id: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        with self._lock:
            task = self.tasks.get(task_id)
            if task is None:
                return None
            for field_name in (
                "status",
                "required_action",
                "pending_confirmation",
                "assigned_to",
                "deadline",
                "result",
            ):
                if field_name in payload and payload[field_name] is not None:
                    setattr(task, field_name, payload[field_name])
            task.updated_at = utc_now()
            return asdict(task)

    def get_task_by_resume_token(self, resume_token: str) -> dict[str, Any] | None:
        with self._lock:
            for task in self.tasks.values():
                if task.resume_token == resume_token:
                    return asdict(task)
            return None

    def append_tool_audit(
        self,
        conversation_id: str,
        tool_name: str,
        arguments: dict[str, Any],
        auth_context: dict[str, Any],
        policy_status: str,
        success: bool,
        result: Any = None,
        error: str | None = None,
        case_id: str | None = None,
        task_id: str | None = None,
        idempotency_key: str | None = None,
        requires_confirmation: bool = False,
    ) -> dict[str, Any]:
        with self._lock:
            if idempotency_key:
                for audit in self.tool_audits.values():
                    if audit.idempotency_key == idempotency_key and audit.tool_name == tool_name:
                        return asdict(audit)
            audit = ToolAuditLog(
                id=f"AUD-{uuid4().hex[:10].upper()}",
                conversation_id=conversation_id,
                case_id=case_id,
                task_id=task_id,
                tool_name=tool_name,
                arguments=arguments,
                auth_context=auth_context,
                policy_status=policy_status,
                success=success,
                result=result,
                error=error,
                idempotency_key=idempotency_key,
                requires_confirmation=requires_confirmation,
            )
            self.tool_audits[audit.id] = audit
            return asdict(audit)

    def list_tool_audits(
        self,
        conversation_id: str | None = None,
        case_id: str | None = None,
        tool_name: str | None = None,
    ) -> list[dict[str, Any]]:
        with self._lock:
            audits = list(self.tool_audits.values())
            if conversation_id:
                audits = [audit for audit in audits if audit.conversation_id == conversation_id]
            if case_id:
                audits = [audit for audit in audits if audit.case_id == case_id]
            if tool_name:
                audits = [audit for audit in audits if audit.tool_name == tool_name]
            return [
                asdict(audit)
                for audit in sorted(audits, key=lambda item: item.created_at, reverse=True)
            ]

    def find_tool_audit_by_idempotency_key(
        self,
        idempotency_key: str,
        tool_name: str | None = None,
    ) -> dict[str, Any] | None:
        with self._lock:
            for audit in self.tool_audits.values():
                if audit.idempotency_key == idempotency_key and (
                    tool_name is None or audit.tool_name == tool_name
                ):
                    return asdict(audit)
            return None
