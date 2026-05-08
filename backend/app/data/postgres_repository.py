from __future__ import annotations

from dataclasses import asdict
from typing import Any
from uuid import uuid4

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from app.data.repository import ConversationRecord, Order, Refund, Ticket
from app.data.seed import seed_orders, seed_users
from app.models.schemas import AgentStep, ChatMessage, ToolCallRecord, utc_now


def normalize_database_url(database_url: str) -> str:
    return database_url.replace("postgresql+psycopg://", "postgresql://", 1)


class PostgresRepository:
    """PostgreSQL-backed repository for durable SmartCS business and trace data."""

    backend_name = "postgresql"

    def __init__(self, database_url: str) -> None:
        self.database_url = normalize_database_url(database_url)
        self._init_schema()
        self._seed()

    def _connect(self):
        return psycopg.connect(self.database_url, row_factory=dict_row, connect_timeout=2)

    def ping(self) -> bool:
        with self._connect() as conn:
            row = conn.execute("SELECT 1 AS ok").fetchone()
        return bool(row and row["ok"] == 1)

    def _init_schema(self) -> None:
        ddl = """
        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            tier TEXT NOT NULL,
            preference TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS orders (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL REFERENCES users(user_id),
            item TEXT NOT NULL,
            amount DOUBLE PRECISION NOT NULL,
            status TEXT NOT NULL,
            paid_at TEXT NOT NULL,
            delivered_at TEXT,
            carrier TEXT NOT NULL,
            tracking_no TEXT NOT NULL,
            invoice_status TEXT NOT NULL DEFAULT 'not_requested',
            refund_id TEXT
        );
        CREATE TABLE IF NOT EXISTS refunds (
            id TEXT PRIMARY KEY,
            order_id TEXT NOT NULL REFERENCES orders(id),
            user_id TEXT NOT NULL REFERENCES users(user_id),
            status TEXT NOT NULL,
            reason TEXT NOT NULL,
            amount DOUBLE PRECISION NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS tickets (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL REFERENCES users(user_id),
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            priority TEXT NOT NULL,
            category TEXT NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS conversations (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL REFERENCES users(user_id),
            summary TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS messages (
            id BIGSERIAL PRIMARY KEY,
            conversation_id TEXT NOT NULL REFERENCES conversations(id),
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS conversation_traces (
            id BIGSERIAL PRIMARY KEY,
            conversation_id TEXT NOT NULL REFERENCES conversations(id),
            trace_id TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS agent_steps (
            id BIGSERIAL PRIMARY KEY,
            conversation_id TEXT NOT NULL REFERENCES conversations(id),
            trace_id TEXT NOT NULL,
            agent TEXT NOT NULL,
            status TEXT NOT NULL,
            message TEXT NOT NULL,
            elapsed_ms DOUBLE PRECISION NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS tool_calls (
            id BIGSERIAL PRIMARY KEY,
            conversation_id TEXT NOT NULL REFERENCES conversations(id),
            trace_id TEXT NOT NULL,
            name TEXT NOT NULL,
            arguments JSONB NOT NULL,
            success BOOLEAN NOT NULL,
            result JSONB,
            error TEXT,
            duration_ms DOUBLE PRECISION NOT NULL,
            created_at TEXT NOT NULL
        );
        """
        with self._connect() as conn:
            conn.execute(ddl)

    def _seed(self) -> None:
        with self._connect() as conn:
            for user_id, name, tier, preference in seed_users():
                conn.execute(
                    """
                    INSERT INTO users (user_id, name, tier, preference)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (user_id) DO NOTHING
                    """,
                    (user_id, name, tier, preference),
                )
            for row in seed_orders():
                conn.execute(
                    """
                    INSERT INTO orders (
                        id, user_id, item, amount, status, paid_at, delivered_at,
                        carrier, tracking_no, invoice_status, refund_id
                    )
                    VALUES (%(id)s, %(user_id)s, %(item)s, %(amount)s, %(status)s,
                            %(paid_at)s, %(delivered_at)s, %(carrier)s, %(tracking_no)s,
                            %(invoice_status)s, %(refund_id)s)
                    ON CONFLICT (id) DO NOTHING
                    """,
                    {
                        **row,
                        "invoice_status": row.get("invoice_status", "not_requested"),
                        "refund_id": row.get("refund_id"),
                    },
                )

    def get_user_profile(self, user_id: str) -> dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT user_id, name, tier, preference FROM users WHERE user_id = %s",
                (user_id,),
            ).fetchone()
            if row is None:
                row = conn.execute(
                    "SELECT user_id, name, tier, preference FROM users WHERE user_id = %s",
                    ("anonymous",),
                ).fetchone()
        return dict(row or {"user_id": "anonymous", "name": "访客用户", "tier": "guest"})

    def get_or_create_conversation(
        self,
        conversation_id: str | None,
        user_id: str,
    ) -> ConversationRecord:
        cid = conversation_id or uuid4().hex
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO conversations (id, user_id, summary, updated_at)
                VALUES (%s, %s, '', %s)
                ON CONFLICT (id) DO NOTHING
                """,
                (cid, user_id, utc_now()),
            )
            record = conn.execute(
                "SELECT id, user_id, summary, updated_at FROM conversations WHERE id = %s",
                (cid,),
            ).fetchone()
            messages = conn.execute(
                """
                SELECT role, content, created_at
                FROM messages
                WHERE conversation_id = %s
                ORDER BY id ASC
                """,
                (cid,),
            ).fetchall()
        return ConversationRecord(
            id=record["id"],
            user_id=record["user_id"],
            summary=record["summary"],
            updated_at=record["updated_at"],
            messages=[
                ChatMessage(role=row["role"], content=row["content"], created_at=row["created_at"])
                for row in messages
            ],
        )

    def append_message(self, conversation_id: str, message: ChatMessage) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO messages (conversation_id, role, content, created_at)
                VALUES (%s, %s, %s, %s)
                """,
                (conversation_id, message.role, message.content, message.created_at),
            )
            conn.execute(
                "UPDATE conversations SET updated_at = %s WHERE id = %s",
                (utc_now(), conversation_id),
            )

    def append_trace(
        self,
        conversation_id: str,
        trace_id: str,
        steps: list[AgentStep],
        tool_calls: list[ToolCallRecord],
        summary: str,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO conversation_traces (conversation_id, trace_id, created_at)
                VALUES (%s, %s, %s)
                """,
                (conversation_id, trace_id, utc_now()),
            )
            for step in steps:
                conn.execute(
                    """
                    INSERT INTO agent_steps (
                        conversation_id, trace_id, agent, status, message, elapsed_ms, created_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        conversation_id,
                        trace_id,
                        step.agent,
                        step.status,
                        step.message,
                        step.elapsed_ms,
                        utc_now(),
                    ),
                )
            for call in tool_calls:
                conn.execute(
                    """
                    INSERT INTO tool_calls (
                        conversation_id, trace_id, name, arguments, success,
                        result, error, duration_ms, created_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        conversation_id,
                        trace_id,
                        call.name,
                        Jsonb(call.arguments),
                        call.success,
                        Jsonb(call.result),
                        call.error,
                        call.duration_ms,
                        utc_now(),
                    ),
                )
            conn.execute(
                "UPDATE conversations SET summary = %s, updated_at = %s WHERE id = %s",
                (summary, utc_now(), conversation_id),
            )

    def conversation_snapshot(self, conversation_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            record = conn.execute(
                "SELECT id, user_id, summary, updated_at FROM conversations WHERE id = %s",
                (conversation_id,),
            ).fetchone()
            if record is None:
                return None
            messages = conn.execute(
                """
                SELECT role, content, created_at
                FROM messages
                WHERE conversation_id = %s
                ORDER BY id ASC
                """,
                (conversation_id,),
            ).fetchall()
            steps = conn.execute(
                """
                SELECT agent, status, message, elapsed_ms
                FROM agent_steps
                WHERE conversation_id = %s
                ORDER BY id DESC
                LIMIT 50
                """,
                (conversation_id,),
            ).fetchall()
            tool_calls = conn.execute(
                """
                SELECT name, arguments, success, result, error, duration_ms
                FROM tool_calls
                WHERE conversation_id = %s
                ORDER BY id DESC
                LIMIT 50
                """,
                (conversation_id,),
            ).fetchall()
            traces = conn.execute(
                """
                SELECT trace_id
                FROM conversation_traces
                WHERE conversation_id = %s
                ORDER BY id DESC
                LIMIT 10
                """,
                (conversation_id,),
            ).fetchall()
        return {
            "id": record["id"],
            "user_id": record["user_id"],
            "summary": record["summary"],
            "messages": [dict(row) for row in messages],
            "agent_steps": [dict(row) for row in reversed(steps)],
            "tool_calls": [dict(row) for row in reversed(tool_calls)],
            "trace_ids": [row["trace_id"] for row in traces],
            "updated_at": record["updated_at"],
        }

    def query_order(self, order_id: str, user_id: str) -> dict[str, Any]:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM orders WHERE id = %s", (order_id,)).fetchone()
        if row is None:
            return {"found": False, "authorized": False, "error": "订单不存在"}
        if row["user_id"] != user_id:
            return {"found": True, "authorized": False, "error": "无权查看该订单"}
        return {"found": True, "authorized": True, "order": _order_dict(row)}

    def latest_order_for_user(self, user_id: str) -> Order | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM orders
                WHERE user_id = %s
                ORDER BY paid_at DESC
                LIMIT 1
                """,
                (user_id,),
            ).fetchone()
        return _order_from_row(row) if row else None

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
            from datetime import date, datetime, timedelta

            delivered_date = datetime.fromisoformat(delivered_at).date()
            if date.today() - delivered_date > timedelta(days=7):
                return {
                    "eligible": False,
                    "reason": "订单已超过7天无理由退款窗口，建议创建工单人工审核",
                    "order": order,
                }
        return {"eligible": True, "reason": "符合自助退款规则", "order": order}

    def create_refund(self, order_id: str, user_id: str, reason: str) -> dict[str, Any]:
        eligibility = self.check_refund_eligibility(order_id, user_id)
        if not eligibility.get("eligible"):
            return {"created": False, **eligibility}
        order = eligibility["order"]
        refund = Refund(
            id=f"RF-{uuid4().hex[:8].upper()}",
            order_id=order_id,
            user_id=user_id,
            status="submitted",
            reason=reason,
            amount=float(order["amount"]),
        )
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO refunds (id, order_id, user_id, status, reason, amount, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    refund.id,
                    refund.order_id,
                    refund.user_id,
                    refund.status,
                    refund.reason,
                    refund.amount,
                    refund.created_at,
                ),
            )
            conn.execute(
                "UPDATE orders SET refund_id = %s WHERE id = %s",
                (refund.id, order_id),
            )
        updated_order = self.query_order(order_id, user_id)["order"]
        return {"created": True, "refund": asdict(refund), "order": updated_order}

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
        ticket = Ticket(
            id=f"TK-{uuid4().hex[:8].upper()}",
            user_id=user_id,
            title=title,
            description=description,
            priority=priority,
            category=category,
        )
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO tickets (
                    id, user_id, title, description, priority, category,
                    status, created_at, updated_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    ticket.id,
                    ticket.user_id,
                    ticket.title,
                    ticket.description,
                    ticket.priority,
                    ticket.category,
                    ticket.status,
                    ticket.created_at,
                    ticket.updated_at,
                ),
            )
        return asdict(ticket)

    def list_tickets(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM tickets ORDER BY created_at ASC",
            ).fetchall()
        return [dict(row) for row in rows]

    def update_ticket(self, ticket_id: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        fields = [
            field_name
            for field_name in ("status", "priority", "category", "title", "description")
            if payload.get(field_name) is not None
        ]
        if not fields:
            with self._connect() as conn:
                row = conn.execute("SELECT * FROM tickets WHERE id = %s", (ticket_id,)).fetchone()
            return dict(row) if row else None
        assignments = ", ".join(f"{field_name} = %s" for field_name in fields)
        values = [payload[field_name] for field_name in fields]
        values.extend([utc_now(), ticket_id])
        with self._connect() as conn:
            row = conn.execute(
                f"""
                UPDATE tickets
                SET {assignments}, updated_at = %s
                WHERE id = %s
                RETURNING *
                """,
                values,
            ).fetchone()
        return dict(row) if row else None


def _order_from_row(row: dict[str, Any]) -> Order:
    return Order(
        id=row["id"],
        user_id=row["user_id"],
        item=row["item"],
        amount=float(row["amount"]),
        status=row["status"],
        paid_at=row["paid_at"],
        delivered_at=row["delivered_at"],
        carrier=row["carrier"],
        tracking_no=row["tracking_no"],
        invoice_status=row["invoice_status"],
        refund_id=row["refund_id"],
    )


def _order_dict(row: dict[str, Any]) -> dict[str, Any]:
    return asdict(_order_from_row(row))
