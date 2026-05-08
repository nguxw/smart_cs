from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from psycopg.types.json import Jsonb

ROOT_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT_DIR / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from app.data.postgres_repository import PostgresRepository, normalize_database_url  # noqa: E402
from app.rag.qdrant_store import QdrantKnowledgeStore  # noqa: E402


DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql+psycopg://smartcs:smartcs@localhost:5432/smartcs"
)
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "smartcs_kb")
QDRANT_VECTOR_SIZE = int(os.getenv("QDRANT_VECTOR_SIZE", "384"))


def day(days_ago: int) -> str:
    return (date.today() - timedelta(days=days_ago)).isoformat()


def stamp(hours_ago: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(hours=hours_ago)).isoformat()


DEMO_USERS = [
    ("u_1001", "林知夏", "gold", "偏好简洁答复，常买智能穿戴设备"),
    ("u_1002", "周明远", "silver", "需要发票提醒，关注大件物流"),
    ("u_1003", "陈星澜", "platinum", "高价值用户，售后希望优先处理"),
    ("u_1004", "王一诺", "bronze", "新用户，常询问退换货规则"),
    ("u_1005", "赵青禾", "silver", "关注母婴和家电订单"),
    ("u_1006", "刘景行", "gold", "经常申请电子发票"),
    ("u_1007", "许安然", "bronze", "偏好短信通知物流进度"),
    ("u_1008", "顾南舟", "platinum", "企业采购用户，关注批量售后"),
    ("anonymous", "访客用户", "guest", "无长期画像"),
]


def demo_orders() -> list[dict[str, Any]]:
    return [
        {
            "id": "ORD-2026-1001",
            "user_id": "u_1001",
            "item": "SmartBand Pro 智能手环",
            "amount": 399.0,
            "status": "delivered",
            "paid_at": day(5),
            "delivered_at": day(2),
            "carrier": "顺丰速运",
            "tracking_no": "SF10266001",
            "invoice_status": "issued",
        },
        {
            "id": "ORD-2026-1002",
            "user_id": "u_1001",
            "item": "Nebula Buds 降噪耳机",
            "amount": 699.0,
            "status": "shipped",
            "paid_at": day(3),
            "delivered_at": None,
            "carrier": "京东物流",
            "tracking_no": "JD88260102",
            "invoice_status": "not_requested",
        },
        {
            "id": "ORD-2026-1003",
            "user_id": "u_1001",
            "item": "HomeCam Mini 云台摄像头",
            "amount": 229.0,
            "status": "paid",
            "paid_at": day(1),
            "delivered_at": None,
            "carrier": "仓库待发货",
            "tracking_no": "PENDING1003",
            "invoice_status": "not_requested",
        },
        {
            "id": "ORD-2026-2001",
            "user_id": "u_1002",
            "item": "AeroDesk 升降桌",
            "amount": 1299.0,
            "status": "delivered",
            "paid_at": day(19),
            "delivered_at": day(12),
            "carrier": "德邦快递",
            "tracking_no": "DB77882601",
            "invoice_status": "not_requested",
        },
        {
            "id": "ORD-2026-2002",
            "user_id": "u_1002",
            "item": "AirPure X1 空气净化器",
            "amount": 1699.0,
            "status": "delivered",
            "paid_at": day(8),
            "delivered_at": day(6),
            "carrier": "顺丰速运",
            "tracking_no": "SF20262002",
            "invoice_status": "issued",
        },
        {
            "id": "ORD-2026-3001",
            "user_id": "u_1003",
            "item": "VisionPad 12 平板电脑",
            "amount": 3599.0,
            "status": "delivered",
            "paid_at": day(4),
            "delivered_at": day(1),
            "carrier": "京东物流",
            "tracking_no": "JD30013001",
            "invoice_status": "issued",
        },
        {
            "id": "ORD-2026-3002",
            "user_id": "u_1003",
            "item": "ProDock Type-C 扩展坞",
            "amount": 499.0,
            "status": "delivered",
            "paid_at": day(15),
            "delivered_at": day(10),
            "carrier": "中通快递",
            "tracking_no": "ZT30023002",
            "invoice_status": "not_requested",
        },
        {
            "id": "ORD-2026-3003",
            "user_id": "u_1003",
            "item": "NoiseFree Max 头戴耳机",
            "amount": 1299.0,
            "status": "returned",
            "paid_at": day(25),
            "delivered_at": day(22),
            "carrier": "顺丰速运",
            "tracking_no": "SF30033003",
            "invoice_status": "issued",
            "refund_id": "RF-DEMO-3003",
        },
        {
            "id": "ORD-2026-4001",
            "user_id": "u_1004",
            "item": "LiteKettle 恒温水壶",
            "amount": 189.0,
            "status": "delivered",
            "paid_at": day(2),
            "delivered_at": day(1),
            "carrier": "圆通速递",
            "tracking_no": "YT40014001",
            "invoice_status": "not_requested",
        },
        {
            "id": "ORD-2026-4002",
            "user_id": "u_1004",
            "item": "SleepLamp 智能床头灯",
            "amount": 259.0,
            "status": "cancelled",
            "paid_at": day(6),
            "delivered_at": None,
            "carrier": "未发货",
            "tracking_no": "CANCEL4002",
            "invoice_status": "not_requested",
        },
        {
            "id": "ORD-2026-5001",
            "user_id": "u_1005",
            "item": "BabyCare 恒温暖奶器",
            "amount": 329.0,
            "status": "shipped",
            "paid_at": day(1),
            "delivered_at": None,
            "carrier": "韵达快递",
            "tracking_no": "YD50015001",
            "invoice_status": "not_requested",
        },
        {
            "id": "ORD-2026-5002",
            "user_id": "u_1005",
            "item": "CleanBot S 扫地机器人",
            "amount": 2199.0,
            "status": "delivered",
            "paid_at": day(13),
            "delivered_at": day(9),
            "carrier": "顺丰速运",
            "tracking_no": "SF50025002",
            "invoice_status": "issued",
        },
        {
            "id": "ORD-2026-6001",
            "user_id": "u_1006",
            "item": "ErgoChair Plus 人体工学椅",
            "amount": 899.0,
            "status": "delivered",
            "paid_at": day(7),
            "delivered_at": day(3),
            "carrier": "德邦快递",
            "tracking_no": "DB60016001",
            "invoice_status": "issued",
        },
        {
            "id": "ORD-2026-6002",
            "user_id": "u_1006",
            "item": "DeskMat Pro 桌垫",
            "amount": 99.0,
            "status": "delivered",
            "paid_at": day(30),
            "delivered_at": day(28),
            "carrier": "中通快递",
            "tracking_no": "ZT60026002",
            "invoice_status": "not_requested",
        },
        {
            "id": "ORD-2026-7001",
            "user_id": "u_1007",
            "item": "TrailWatch 户外手表",
            "amount": 799.0,
            "status": "shipped",
            "paid_at": day(4),
            "delivered_at": None,
            "carrier": "顺丰速运",
            "tracking_no": "SF70017001",
            "invoice_status": "not_requested",
        },
        {
            "id": "ORD-2026-8001",
            "user_id": "u_1008",
            "item": "OfficeHub 企业套装 x10",
            "amount": 12990.0,
            "status": "delivered",
            "paid_at": day(20),
            "delivered_at": day(16),
            "carrier": "德邦快递",
            "tracking_no": "DB80018001",
            "invoice_status": "issued",
        },
        {
            "id": "ORD-2026-8002",
            "user_id": "u_1008",
            "item": "MeetingCam 4K 会议摄像头",
            "amount": 2499.0,
            "status": "delivered",
            "paid_at": day(3),
            "delivered_at": day(1),
            "carrier": "京东物流",
            "tracking_no": "JD80028002",
            "invoice_status": "not_requested",
        },
    ]


DEMO_REFUNDS = [
    {
        "id": "RF-DEMO-3003",
        "order_id": "ORD-2026-3003",
        "user_id": "u_1003",
        "status": "completed",
        "reason": "用户退回耳机，仓库质检通过",
        "amount": 1299.0,
        "created_at": stamp(96),
    },
    {
        "id": "RF-DEMO-4001",
        "order_id": "ORD-2026-4001",
        "user_id": "u_1004",
        "status": "reviewing",
        "reason": "用户反馈水壶外观划痕，等待照片审核",
        "amount": 189.0,
        "created_at": stamp(8),
    },
]


DEMO_TICKETS = [
    {
        "id": "TK-DEMO-LOGISTICS-01",
        "user_id": "u_1005",
        "title": "物流超过48小时未更新",
        "description": "订单ORD-2026-5001在揽收后48小时无更新，需要联系韵达核查。",
        "priority": "medium",
        "category": "order",
        "status": "open",
    },
    {
        "id": "TK-DEMO-REFUND-01",
        "user_id": "u_1002",
        "title": "超过7天退款人工审核",
        "description": "订单ORD-2026-2001已超过7天无理由退款窗口，用户仍希望售后处理。",
        "priority": "medium",
        "category": "refund",
        "status": "open",
    },
    {
        "id": "TK-DEMO-INVOICE-01",
        "user_id": "u_1006",
        "title": "企业抬头发票重开",
        "description": "用户要求将ORD-2026-6001发票抬头从个人改为企业。",
        "priority": "low",
        "category": "invoice",
        "status": "pending",
    },
    {
        "id": "TK-DEMO-PRIVACY-01",
        "user_id": "u_1007",
        "title": "越权订单查询拦截",
        "description": "用户尝试查询非本人订单，系统已拒绝并记录安全事件。",
        "priority": "high",
        "category": "handoff",
        "status": "resolved",
    },
    {
        "id": "TK-DEMO-EXCHANGE-01",
        "user_id": "u_1008",
        "title": "批量采购配件补发",
        "description": "OfficeHub企业套装缺少2个Type-C转接头，需要仓库补发。",
        "priority": "high",
        "category": "ticket",
        "status": "open",
    },
]


@dataclass(frozen=True)
class DemoConversation:
    id: str
    user_id: str
    summary: str
    messages: list[dict[str, str]]
    trace_id: str
    steps: list[dict[str, Any]]
    tool_calls: list[dict[str, Any]]


DEMO_CONVERSATIONS = [
    DemoConversation(
        id="cv-demo-refund-window",
        user_id="u_1002",
        summary="最近意图=refund; 订单=ORD-2026-2001; 工具=check_refund_eligibility,create_ticket",
        messages=[
            {"role": "user", "content": "我的订单ORD-2026-2001超过七天了还能退款吗"},
            {"role": "assistant", "content": "该订单已超过7天无理由退款窗口，我已为你创建人工售后工单。"},
        ],
        trace_id="tr-demo-refund-window",
        steps=[
            {"agent": "router", "status": "completed", "message": "intent=refund", "elapsed_ms": 0.6},
            {"agent": "rag_answer", "status": "completed", "message": "retrieved=1", "elapsed_ms": 18.4},
            {"agent": "order_refund", "status": "completed", "message": "退款资格=False", "elapsed_ms": 22.1},
            {"agent": "ticket_escalation", "status": "completed", "message": "ticket=TK-DEMO-REFUND-01", "elapsed_ms": 31.7},
            {"agent": "guardrail", "status": "completed", "message": "output_safe", "elapsed_ms": 0.1},
        ],
        tool_calls=[
            {
                "name": "check_refund_eligibility",
                "arguments": {"order_id": "ORD-2026-2001", "user_id": "u_1002"},
                "success": True,
                "result": {"eligible": False, "reason": "订单已超过7天无理由退款窗口"},
                "error": None,
                "duration_ms": 15.8,
            },
            {
                "name": "create_ticket",
                "arguments": {"user_id": "u_1002", "category": "refund"},
                "success": True,
                "result": {"id": "TK-DEMO-REFUND-01", "status": "open"},
                "error": None,
                "duration_ms": 24.2,
            },
        ],
    ),
    DemoConversation(
        id="cv-demo-invoice",
        user_id="u_1006",
        summary="最近意图=invoice; 订单=ORD-2026-6001; 工具=query_invoice",
        messages=[
            {"role": "user", "content": "帮我查一下ORD-2026-6001的发票能不能下载"},
            {"role": "assistant", "content": "该订单电子发票已开具，可以从订单详情页下载。"},
        ],
        trace_id="tr-demo-invoice",
        steps=[
            {"agent": "router", "status": "completed", "message": "intent=invoice", "elapsed_ms": 0.4},
            {"agent": "rag_answer", "status": "completed", "message": "retrieved=1", "elapsed_ms": 16.0},
            {"agent": "order_refund", "status": "completed", "message": "发票状态=issued", "elapsed_ms": 12.5},
        ],
        tool_calls=[
            {
                "name": "query_invoice",
                "arguments": {"order_id": "ORD-2026-6001", "user_id": "u_1006"},
                "success": True,
                "result": {
                    "found": True,
                    "authorized": True,
                    "invoice_status": "issued",
                    "download_url": "https://demo.smartcs.local/invoices/ORD-2026-6001.pdf",
                },
                "error": None,
                "duration_ms": 9.3,
            }
        ],
    ),
    DemoConversation(
        id="cv-demo-privacy-block",
        user_id="u_1007",
        summary="最近意图=order; 越权订单查询已拦截",
        messages=[
            {"role": "user", "content": "帮我查一下朋友的订单ORD-2026-8001收货地址"},
            {"role": "assistant", "content": "我不能查询或透露他人订单信息，需要订单所属账户本人登录后处理。"},
        ],
        trace_id="tr-demo-privacy-block",
        steps=[
            {"agent": "router", "status": "completed", "message": "intent=order", "elapsed_ms": 0.5},
            {"agent": "order_refund", "status": "completed", "message": "无权查看该订单", "elapsed_ms": 13.6},
            {"agent": "guardrail", "status": "completed", "message": "output_safe", "elapsed_ms": 0.1},
        ],
        tool_calls=[
            {
                "name": "query_order",
                "arguments": {"order_id": "ORD-2026-8001", "user_id": "u_1007"},
                "success": True,
                "result": {"found": True, "authorized": False, "error": "无权查看该订单"},
                "error": None,
                "duration_ms": 11.2,
            }
        ],
    ),
]


def seed_postgres() -> None:
    repository = PostgresRepository(DATABASE_URL)
    db_url = normalize_database_url(DATABASE_URL)
    with repository._connect() as conn:  # noqa: SLF001 - demo seeding uses the adapter connection.
        for user in DEMO_USERS:
            conn.execute(
                """
                INSERT INTO users (user_id, name, tier, preference)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (user_id) DO UPDATE
                SET name = EXCLUDED.name,
                    tier = EXCLUDED.tier,
                    preference = EXCLUDED.preference
                """,
                user,
            )
        for row in demo_orders():
            conn.execute(
                """
                INSERT INTO orders (
                    id, user_id, item, amount, status, paid_at, delivered_at,
                    carrier, tracking_no, invoice_status, refund_id
                )
                VALUES (
                    %(id)s, %(user_id)s, %(item)s, %(amount)s, %(status)s,
                    %(paid_at)s, %(delivered_at)s, %(carrier)s, %(tracking_no)s,
                    %(invoice_status)s, %(refund_id)s
                )
                ON CONFLICT (id) DO UPDATE
                SET user_id = EXCLUDED.user_id,
                    item = EXCLUDED.item,
                    amount = EXCLUDED.amount,
                    status = EXCLUDED.status,
                    paid_at = EXCLUDED.paid_at,
                    delivered_at = EXCLUDED.delivered_at,
                    carrier = EXCLUDED.carrier,
                    tracking_no = EXCLUDED.tracking_no,
                    invoice_status = EXCLUDED.invoice_status,
                    refund_id = COALESCE(orders.refund_id, EXCLUDED.refund_id)
                """,
                {**row, "invoice_status": row.get("invoice_status", "not_requested"), "refund_id": row.get("refund_id")},
            )
        for refund in DEMO_REFUNDS:
            conn.execute(
                """
                INSERT INTO refunds (id, order_id, user_id, status, reason, amount, created_at)
                VALUES (%(id)s, %(order_id)s, %(user_id)s, %(status)s, %(reason)s, %(amount)s, %(created_at)s)
                ON CONFLICT (id) DO UPDATE
                SET status = EXCLUDED.status,
                    reason = EXCLUDED.reason,
                    amount = EXCLUDED.amount
                """,
                refund,
            )
            conn.execute(
                "UPDATE orders SET refund_id = %s WHERE id = %s AND refund_id IS NULL",
                (refund["id"], refund["order_id"]),
            )
        now = stamp(0)
        for ticket in DEMO_TICKETS:
            conn.execute(
                """
                INSERT INTO tickets (
                    id, user_id, title, description, priority, category,
                    status, created_at, updated_at
                )
                VALUES (
                    %(id)s, %(user_id)s, %(title)s, %(description)s, %(priority)s,
                    %(category)s, %(status)s, %(created_at)s, %(updated_at)s
                )
                ON CONFLICT (id) DO UPDATE
                SET title = EXCLUDED.title,
                    description = EXCLUDED.description,
                    priority = EXCLUDED.priority,
                    category = EXCLUDED.category,
                    status = EXCLUDED.status,
                    updated_at = EXCLUDED.updated_at
                """,
                {**ticket, "created_at": stamp(24), "updated_at": now},
            )
        for conversation in DEMO_CONVERSATIONS:
            conn.execute(
                """
                INSERT INTO conversations (id, user_id, summary, updated_at)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE
                SET summary = EXCLUDED.summary,
                    updated_at = EXCLUDED.updated_at
                """,
                (conversation.id, conversation.user_id, conversation.summary, now),
            )
            existing_messages = conn.execute(
                "SELECT count(*) AS count FROM messages WHERE conversation_id = %s",
                (conversation.id,),
            ).fetchone()["count"]
            if existing_messages == 0:
                for index, message in enumerate(conversation.messages):
                    conn.execute(
                        """
                        INSERT INTO messages (conversation_id, role, content, created_at)
                        VALUES (%s, %s, %s, %s)
                        """,
                        (
                            conversation.id,
                            message["role"],
                            message["content"],
                            stamp(12 - index),
                        ),
                    )
            trace_exists = conn.execute(
                "SELECT 1 FROM conversation_traces WHERE trace_id = %s",
                (conversation.trace_id,),
            ).fetchone()
            if trace_exists:
                continue
            conn.execute(
                """
                INSERT INTO conversation_traces (conversation_id, trace_id, created_at)
                VALUES (%s, %s, %s)
                """,
                (conversation.id, conversation.trace_id, now),
            )
            for step in conversation.steps:
                conn.execute(
                    """
                    INSERT INTO agent_steps (
                        conversation_id, trace_id, agent, status, message, elapsed_ms, created_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        conversation.id,
                        conversation.trace_id,
                        step["agent"],
                        step["status"],
                        step["message"],
                        step["elapsed_ms"],
                        now,
                    ),
                )
            for call in conversation.tool_calls:
                conn.execute(
                    """
                    INSERT INTO tool_calls (
                        conversation_id, trace_id, name, arguments, success,
                        result, error, duration_ms, created_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        conversation.id,
                        conversation.trace_id,
                        call["name"],
                        Jsonb(call["arguments"]),
                        call["success"],
                        Jsonb(call["result"]),
                        call["error"],
                        call["duration_ms"],
                        now,
                    ),
                )
        counts = conn.execute(
            """
            SELECT
                (SELECT count(*) FROM users) AS users,
                (SELECT count(*) FROM orders) AS orders,
                (SELECT count(*) FROM refunds) AS refunds,
                (SELECT count(*) FROM tickets) AS tickets,
                (SELECT count(*) FROM conversations) AS conversations,
                (SELECT count(*) FROM messages) AS messages,
                (SELECT count(*) FROM conversation_traces) AS traces,
                (SELECT count(*) FROM tool_calls) AS tool_calls
            """
        ).fetchone()
    print(f"PostgreSQL seeded at {db_url}")
    print(
        "counts users/orders/refunds/tickets/conversations/messages/traces/tool_calls = "
        f"{counts}"
    )


def seed_qdrant() -> None:
    kb_dir = BACKEND_DIR / "data" / "kb"
    store = QdrantKnowledgeStore(
        url=QDRANT_URL,
        collection_name=QDRANT_COLLECTION,
        vector_size=QDRANT_VECTOR_SIZE,
    )
    ingested = store.ingest_markdown_dir(kb_dir)
    collection = store.client.get_collection(QDRANT_COLLECTION)
    print(
        f"Qdrant seeded collection={QDRANT_COLLECTION} docs_upserted={ingested} "
        f"points={collection.points_count}"
    )


if __name__ == "__main__":
    seed_postgres()
    seed_qdrant()
