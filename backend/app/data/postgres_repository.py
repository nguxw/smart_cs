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


POSTGRES_SCHEMA_DDL = [
    """
    CREATE TABLE IF NOT EXISTS users (
        user_id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        tier TEXT NOT NULL,
        preference TEXT NOT NULL
    )
    """,
    """
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
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS refunds (
        id TEXT PRIMARY KEY,
        order_id TEXT NOT NULL REFERENCES orders(id),
        user_id TEXT NOT NULL REFERENCES users(user_id),
        status TEXT NOT NULL,
        reason TEXT NOT NULL,
        amount DOUBLE PRECISION NOT NULL,
        created_at TEXT NOT NULL
    )
    """,
    """
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
    )
    """,
    "ALTER TABLE tickets ADD COLUMN IF NOT EXISTS assigned_to TEXT",
    "ALTER TABLE tickets ADD COLUMN IF NOT EXISTS assignee_name TEXT",
    "ALTER TABLE tickets ADD COLUMN IF NOT EXISTS sla_deadline TEXT",
    "ALTER TABLE tickets ADD COLUMN IF NOT EXISTS handoff_reason TEXT NOT NULL DEFAULT ''",
    "ALTER TABLE tickets ADD COLUMN IF NOT EXISTS agent_summary TEXT NOT NULL DEFAULT ''",
    """
    ALTER TABLE tickets ADD COLUMN IF NOT EXISTS customer_emotion
        TEXT NOT NULL DEFAULT 'neutral'
    """,
    """
    ALTER TABLE tickets ADD COLUMN IF NOT EXISTS latest_customer_message
        TEXT NOT NULL DEFAULT ''
    """,
    "ALTER TABLE tickets ADD COLUMN IF NOT EXISTS suggested_reply TEXT NOT NULL DEFAULT ''",
    "ALTER TABLE tickets ADD COLUMN IF NOT EXISTS human_reply TEXT NOT NULL DEFAULT ''",
    "ALTER TABLE tickets ADD COLUMN IF NOT EXISTS resolution_type TEXT NOT NULL DEFAULT ''",
    "ALTER TABLE tickets ADD COLUMN IF NOT EXISTS closed_reason TEXT NOT NULL DEFAULT ''",
    "ALTER TABLE tickets ADD COLUMN IF NOT EXISTS csat_score INTEGER",
    """
    CREATE TABLE IF NOT EXISTS conversations (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL REFERENCES users(user_id),
        summary TEXT NOT NULL DEFAULT '',
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS messages (
        id BIGSERIAL PRIMARY KEY,
        conversation_id TEXT NOT NULL REFERENCES conversations(id),
        role TEXT NOT NULL,
        content TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS conversation_traces (
        id BIGSERIAL PRIMARY KEY,
        conversation_id TEXT NOT NULL REFERENCES conversations(id),
        trace_id TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS agent_steps (
        id BIGSERIAL PRIMARY KEY,
        conversation_id TEXT NOT NULL REFERENCES conversations(id),
        trace_id TEXT NOT NULL,
        agent TEXT NOT NULL,
        status TEXT NOT NULL,
        message TEXT NOT NULL,
        elapsed_ms DOUBLE PRECISION NOT NULL,
        created_at TEXT NOT NULL
    )
    """,
    """
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
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS cases (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL REFERENCES users(user_id),
        tenant_id TEXT NOT NULL,
        conversation_id TEXT NOT NULL REFERENCES conversations(id),
        category TEXT NOT NULL,
        status TEXT NOT NULL,
        priority TEXT NOT NULL,
        source_channel TEXT NOT NULL,
        related_order_id TEXT,
        related_ticket_id TEXT,
        current_task_id TEXT,
        resolution TEXT NOT NULL DEFAULT '',
        risk_level TEXT NOT NULL DEFAULT 'low',
        summary TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS case_tasks (
        id TEXT PRIMARY KEY,
        case_id TEXT NOT NULL REFERENCES cases(id),
        type TEXT NOT NULL,
        status TEXT NOT NULL,
        required_action TEXT NOT NULL,
        pending_confirmation JSONB,
        assigned_to TEXT,
        deadline TEXT,
        result JSONB,
        resume_token TEXT NOT NULL UNIQUE,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS tool_audits (
        id TEXT PRIMARY KEY,
        conversation_id TEXT NOT NULL REFERENCES conversations(id),
        case_id TEXT,
        task_id TEXT,
        tool_name TEXT NOT NULL,
        arguments JSONB NOT NULL,
        auth_context JSONB NOT NULL,
        policy_status TEXT NOT NULL,
        success BOOLEAN NOT NULL,
        result JSONB,
        error TEXT,
        idempotency_key TEXT,
        requires_confirmation BOOLEAN NOT NULL DEFAULT FALSE,
        created_at TEXT NOT NULL
    )
    """,
]


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
        with self._connect() as conn:
            for statement in POSTGRES_SCHEMA_DDL:
                conn.execute(statement)

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
            cases = conn.execute(
                """
                SELECT *
                FROM cases
                WHERE conversation_id = %s
                ORDER BY updated_at DESC
                """,
                (conversation_id,),
            ).fetchall()
            case_ids = [row["id"] for row in cases]
            tasks = []
            if case_ids:
                tasks = conn.execute(
                    """
                    SELECT *
                    FROM case_tasks
                    WHERE case_id = ANY(%s)
                    ORDER BY updated_at DESC
                    """,
                    (case_ids,),
                ).fetchall()
        return {
            "id": record["id"],
            "user_id": record["user_id"],
            "summary": record["summary"],
            "messages": [dict(row) for row in messages],
            "agent_steps": [dict(row) for row in reversed(steps)],
            "tool_calls": [dict(row) for row in reversed(tool_calls)],
            "trace_ids": [row["trace_id"] for row in traces],
            "cases": [dict(row) for row in cases],
            "tasks": [dict(row) for row in tasks],
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
        ticket = Ticket(
            id=f"TK-{uuid4().hex[:8].upper()}",
            user_id=user_id,
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
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO tickets (
                    id, user_id, title, description, priority, category,
                    status, assigned_to, assignee_name, sla_deadline, handoff_reason,
                    agent_summary, customer_emotion, latest_customer_message,
                    suggested_reply, human_reply, resolution_type, closed_reason,
                    csat_score, created_at, updated_at
                )
                VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s
                )
                """,
                (
                    ticket.id,
                    ticket.user_id,
                    ticket.title,
                    ticket.description,
                    ticket.priority,
                    ticket.category,
                    ticket.status,
                    ticket.assigned_to,
                    ticket.assignee_name,
                    ticket.sla_deadline,
                    ticket.handoff_reason,
                    ticket.agent_summary,
                    ticket.customer_emotion,
                    ticket.latest_customer_message,
                    ticket.suggested_reply,
                    ticket.human_reply,
                    ticket.resolution_type,
                    ticket.closed_reason,
                    ticket.csat_score,
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
        sync_human_reply = "human_reply" in payload and bool(payload.get("human_reply"))
        close_case = payload.get("status") == "resolved"
        fields = [
            field_name
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
            )
            if payload.get(field_name) is not None
        ]
        with self._connect() as conn:
            previous = conn.execute("SELECT * FROM tickets WHERE id = %s", (ticket_id,)).fetchone()
            if previous is None:
                return None
            if not fields:
                return dict(previous)
            assignments = ", ".join(f"{field_name} = %s" for field_name in fields)
            values = [payload[field_name] for field_name in fields]
            values.extend([utc_now(), ticket_id])
            row = conn.execute(
                f"""
                UPDATE tickets
                SET {assignments}, updated_at = %s
                WHERE id = %s
                RETURNING *
                """,
                values,
            ).fetchone()
            if row is None:
                return None
            if sync_human_reply and payload.get("human_reply") != previous.get("human_reply"):
                linked_cases = conn.execute(
                    "SELECT id, conversation_id FROM cases WHERE related_ticket_id = %s",
                    (ticket_id,),
                ).fetchall()
                for case in linked_cases:
                    now = utc_now()
                    conn.execute(
                        """
                        INSERT INTO messages (conversation_id, role, content, created_at)
                        VALUES (%s, 'assistant', %s, %s)
                        """,
                        (case["conversation_id"], payload["human_reply"], now),
                    )
                    conn.execute(
                        """
                        UPDATE conversations SET updated_at = %s WHERE id = %s
                        """,
                        (now, case["conversation_id"]),
                    )
                    conn.execute(
                        """
                        UPDATE cases
                        SET summary = %s, updated_at = %s
                        WHERE id = %s
                        """,
                        (str(payload["human_reply"])[:180], now, case["id"]),
                    )
            if close_case:
                resolution = (
                    payload.get("closed_reason")
                    or payload.get("resolution_type")
                    or payload.get("human_reply")
                    or "工单已关闭"
                )
                conn.execute(
                    """
                    UPDATE cases
                    SET status = 'resolved', resolution = %s, updated_at = %s
                    WHERE related_ticket_id = %s
                    """,
                    (resolution, utc_now(), ticket_id),
                )
        return dict(row) if row else None

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
        with self._connect() as conn:
            existing = conn.execute(
                """
                SELECT *
                FROM cases
                WHERE conversation_id = %s AND status NOT IN ('resolved', 'closed')
                ORDER BY updated_at DESC
                LIMIT 1
                """,
                (conversation_id,),
            ).fetchone()
            if existing:
                row = conn.execute(
                    """
                    UPDATE cases
                    SET category = %s,
                        related_order_id = COALESCE(%s, related_order_id),
                        summary = CASE WHEN %s = '' THEN summary ELSE %s END,
                        risk_level = %s,
                        updated_at = %s
                    WHERE id = %s
                    RETURNING *
                    """,
                    (
                        category,
                        related_order_id,
                        summary,
                        summary,
                        risk_level,
                        utc_now(),
                        existing["id"],
                    ),
                ).fetchone()
                return dict(row)
            now = utc_now()
            case_id = f"CASE-{uuid4().hex[:8].upper()}"
            row = conn.execute(
                """
                INSERT INTO cases (
                    id, user_id, tenant_id, conversation_id, category, status, priority,
                    source_channel, related_order_id, risk_level, summary, created_at, updated_at
                )
                VALUES (%s, %s, %s, %s, %s, 'open', %s, %s, %s, %s, %s, %s, %s)
                RETURNING *
                """,
                (
                    case_id,
                    user_id,
                    tenant_id,
                    conversation_id,
                    category,
                    priority,
                    source_channel,
                    related_order_id,
                    risk_level,
                    summary,
                    now,
                    now,
                ),
            ).fetchone()
        return dict(row)

    def list_cases(
        self,
        user_id: str | None = None,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        clauses: list[str] = []
        values: list[Any] = []
        if user_id:
            clauses.append("user_id = %s")
            values.append(user_id)
        if status:
            clauses.append("status = %s")
            values.append(status)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT * FROM cases {where} ORDER BY updated_at DESC",
                values,
            ).fetchall()
        return [dict(row) for row in rows]

    def get_case(self, case_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM cases WHERE id = %s", (case_id,)).fetchone()
        return dict(row) if row else None

    def update_case(self, case_id: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        fields = [
            field_name
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
            )
            if payload.get(field_name) is not None
        ]
        if not fields:
            return self.get_case(case_id)
        assignments = ", ".join(f"{field_name} = %s" for field_name in fields)
        values = [payload[field_name] for field_name in fields]
        values.extend([utc_now(), case_id])
        with self._connect() as conn:
            row = conn.execute(
                f"""
                UPDATE cases
                SET {assignments}, updated_at = %s
                WHERE id = %s
                RETURNING *
                """,
                values,
            ).fetchone()
        return dict(row) if row else None

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
        now = utc_now()
        task_id = f"TASK-{uuid4().hex[:8].upper()}"
        resume_token = uuid4().hex
        with self._connect() as conn:
            row = conn.execute(
                """
                INSERT INTO case_tasks (
                    id, case_id, type, status, required_action, pending_confirmation,
                    assigned_to, deadline, result, resume_token, created_at, updated_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING *
                """,
                (
                    task_id,
                    case_id,
                    task_type,
                    status,
                    required_action,
                    Jsonb(pending_confirmation) if pending_confirmation is not None else None,
                    assigned_to,
                    deadline,
                    Jsonb(result) if result is not None else None,
                    resume_token,
                    now,
                    now,
                ),
            ).fetchone()
            conn.execute(
                """
                UPDATE cases
                SET current_task_id = %s,
                    status = CASE WHEN %s THEN 'waiting_customer' ELSE status END,
                    updated_at = %s
                WHERE id = %s
                """,
                (
                    task_id,
                    pending_confirmation is not None,
                    now,
                    case_id,
                ),
            )
        return dict(row)

    def get_task(self, task_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM case_tasks WHERE id = %s", (task_id,)).fetchone()
        return dict(row) if row else None

    def list_tasks(
        self,
        case_id: str | None = None,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        clauses: list[str] = []
        values: list[Any] = []
        if case_id:
            clauses.append("case_id = %s")
            values.append(case_id)
        if status:
            clauses.append("status = %s")
            values.append(status)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT * FROM case_tasks {where} ORDER BY updated_at DESC",
                values,
            ).fetchall()
        return [dict(row) for row in rows]

    def update_task(self, task_id: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        fields = [
            field_name
            for field_name in (
                "status",
                "required_action",
                "pending_confirmation",
                "assigned_to",
                "deadline",
                "result",
            )
            if payload.get(field_name) is not None
        ]
        if not fields:
            return self.get_task(task_id)
        assignments = ", ".join(f"{field_name} = %s" for field_name in fields)
        values = [
            Jsonb(payload[field_name])
            if field_name in {"pending_confirmation", "result"}
            else payload[field_name]
            for field_name in fields
        ]
        values.extend([utc_now(), task_id])
        with self._connect() as conn:
            row = conn.execute(
                f"""
                UPDATE case_tasks
                SET {assignments}, updated_at = %s
                WHERE id = %s
                RETURNING *
                """,
                values,
            ).fetchone()
            if row and payload.get("status") in {"completed", "cancelled"}:
                conn.execute(
                    """
                    UPDATE cases
                    SET status = 'open', current_task_id = NULL, updated_at = %s
                    WHERE id = %s
                    """,
                    (utc_now(), row["case_id"]),
                )
        return dict(row) if row else None

    def get_task_by_resume_token(self, resume_token: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM case_tasks WHERE resume_token = %s",
                (resume_token,),
            ).fetchone()
        return dict(row) if row else None

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
        with self._connect() as conn:
            if idempotency_key:
                existing = conn.execute(
                    """
                    SELECT * FROM tool_audits
                    WHERE idempotency_key = %s AND tool_name = %s
                    ORDER BY created_at DESC
                    LIMIT 1
                    """,
                    (idempotency_key, tool_name),
                ).fetchone()
                if existing:
                    return dict(existing)
            audit_id = f"AUD-{uuid4().hex[:10].upper()}"
            row = conn.execute(
                """
                INSERT INTO tool_audits (
                    id, conversation_id, case_id, task_id, tool_name, arguments,
                    auth_context, policy_status, success, result, error,
                    idempotency_key, requires_confirmation, created_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING *
                """,
                (
                    audit_id,
                    conversation_id,
                    case_id,
                    task_id,
                    tool_name,
                    Jsonb(arguments),
                    Jsonb(auth_context),
                    policy_status,
                    success,
                    Jsonb(result),
                    error,
                    idempotency_key,
                    requires_confirmation,
                    utc_now(),
                ),
            ).fetchone()
        return dict(row)

    def list_tool_audits(
        self,
        conversation_id: str | None = None,
        case_id: str | None = None,
        tool_name: str | None = None,
    ) -> list[dict[str, Any]]:
        clauses: list[str] = []
        values: list[Any] = []
        if conversation_id:
            clauses.append("conversation_id = %s")
            values.append(conversation_id)
        if case_id:
            clauses.append("case_id = %s")
            values.append(case_id)
        if tool_name:
            clauses.append("tool_name = %s")
            values.append(tool_name)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT * FROM tool_audits {where} ORDER BY created_at DESC",
                values,
            ).fetchall()
        return [dict(row) for row in rows]

    def find_tool_audit_by_idempotency_key(
        self,
        idempotency_key: str,
        tool_name: str | None = None,
    ) -> dict[str, Any] | None:
        clauses = ["idempotency_key = %s"]
        values: list[Any] = [idempotency_key]
        if tool_name:
            clauses.append("tool_name = %s")
            values.append(tool_name)
        with self._connect() as conn:
            row = conn.execute(
                f"""
                SELECT *
                FROM tool_audits
                WHERE {' AND '.join(clauses)}
                ORDER BY created_at DESC
                LIMIT 1
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
