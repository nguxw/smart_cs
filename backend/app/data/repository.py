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
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)


@dataclass
class ConversationRecord:
    id: str
    user_id: str
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
        self.conversations: dict[str, ConversationRecord] = {}
        self._seed()

    def _seed(self) -> None:
        for user_id, name, tier, preference in seed_users():
            self.users[user_id] = {
                "user_id": user_id,
                "name": name,
                "tier": tier,
                "preference": preference,
            }

        self.orders = {row["id"]: Order(**row) for row in seed_orders()}

    def get_user_profile(self, user_id: str) -> dict[str, Any]:
        with self._lock:
            return self.users.get(user_id, self.users["anonymous"]).copy()

    def get_or_create_conversation(
        self, conversation_id: str | None, user_id: str
    ) -> ConversationRecord:
        with self._lock:
            cid = conversation_id or uuid4().hex
            if cid not in self.conversations:
                self.conversations[cid] = ConversationRecord(id=cid, user_id=user_id)
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
                "summary": record.summary,
                "messages": [asdict(msg) for msg in record.messages],
                "agent_steps": [asdict(step) for step in record.agent_steps[-50:]],
                "tool_calls": [asdict(call) for call in record.tool_calls[-50:]],
                "trace_ids": record.trace_ids[-10:],
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
    ) -> dict[str, Any]:
        with self._lock:
            ticket = Ticket(
                id=f"TK-{uuid4().hex[:8].upper()}",
                user_id=user_id,
                title=title,
                description=description,
                priority=priority,
                category=category,
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
            for field_name in ("status", "priority", "category", "title", "description"):
                if field_name in payload and payload[field_name] is not None:
                    setattr(ticket, field_name, payload[field_name])
            ticket.updated_at = utc_now()
            return asdict(ticket)
