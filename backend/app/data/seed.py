from __future__ import annotations

from datetime import date, timedelta
from typing import Any


def seed_users() -> list[tuple[str, str, str, str]]:
    return [
        ("u_1001", "林知夏", "gold", "prefers concise answers"),
        ("u_1002", "周明远", "silver", "needs invoice reminders"),
        ("u_1005", "赵青禾", "silver", "logistics sensitive"),
        ("u_1006", "刘景行", "gold", "frequent invoice requests"),
        ("u_1007", "许安然", "bronze", "privacy and safety demo"),
        ("u_1008", "顾南舟", "enterprise", "bulk after-sales"),
        ("anonymous", "访客用户", "guest", "no persistent profile"),
    ]


def seed_orders() -> list[dict[str, Any]]:
    today = date.today()
    return [
        {
            "id": "ORD-2026-1001",
            "user_id": "u_1001",
            "item": "SmartBand Pro 智能手环",
            "amount": 399.0,
            "status": "delivered",
            "paid_at": str(today - timedelta(days=5)),
            "delivered_at": str(today - timedelta(days=2)),
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
            "paid_at": str(today - timedelta(days=2)),
            "delivered_at": None,
            "carrier": "京东物流",
            "tracking_no": "JD88260102",
        },
        {
            "id": "ORD-2026-2001",
            "user_id": "u_1002",
            "item": "AeroDesk 升降桌",
            "amount": 1299.0,
            "status": "delivered",
            "paid_at": str(today - timedelta(days=18)),
            "delivered_at": str(today - timedelta(days=11)),
            "carrier": "德邦快递",
            "tracking_no": "DB77882601",
        },
        {
            "id": "ORD-2026-2002",
            "user_id": "u_1002",
            "item": "AirPure X1 空气净化器",
            "amount": 1699.0,
            "status": "delivered",
            "paid_at": str(today - timedelta(days=8)),
            "delivered_at": str(today - timedelta(days=6)),
            "carrier": "顺丰速运",
            "tracking_no": "SF20262002",
            "invoice_status": "issued",
        },
        {
            "id": "ORD-2026-5001",
            "user_id": "u_1005",
            "item": "BabyCare 恒温暖奶器",
            "amount": 329.0,
            "status": "shipped",
            "paid_at": str(today - timedelta(days=1)),
            "delivered_at": None,
            "carrier": "韵达快递",
            "tracking_no": "YD50015001",
        },
        {
            "id": "ORD-2026-6001",
            "user_id": "u_1006",
            "item": "ErgoChair Plus 人体工学椅",
            "amount": 899.0,
            "status": "delivered",
            "paid_at": str(today - timedelta(days=7)),
            "delivered_at": str(today - timedelta(days=3)),
            "carrier": "德邦快递",
            "tracking_no": "DB60016001",
            "invoice_status": "issued",
        },
        {
            "id": "ORD-2026-8001",
            "user_id": "u_1008",
            "item": "OfficeHub 企业套装 x10",
            "amount": 12990.0,
            "status": "delivered",
            "paid_at": str(today - timedelta(days=20)),
            "delivered_at": str(today - timedelta(days=16)),
            "carrier": "德邦快递",
            "tracking_no": "DB80018001",
            "invoice_status": "issued",
        },
    ]
