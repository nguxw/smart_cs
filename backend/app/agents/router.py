from __future__ import annotations

import re

from app.models.schemas import Intent

ORDER_RE = re.compile(r"ORD-\d{4}-\d{4}", re.IGNORECASE)


def extract_order_id(message: str) -> str | None:
    match = ORDER_RE.search(message)
    return match.group(0).upper() if match else None


def classify_intent(message: str) -> Intent:
    text = message.lower()
    if _is_closing_request(message, text):
        return "closing"
    if any(word in message for word in ("朋友", "别人", "他人", "收货地址", "隐私")):
        return "privacy"
    if any(word in message for word in ("人工", "投诉", "客服介入", "转人工", "工单")):
        return "handoff"
    if any(word in message for word in ("发票", "开票", "票据", "invoice")):
        return "invoice"
    if any(word in message for word in ("退款", "退货", "退回", "售后", "refund", "return")):
        return "refund"
    if any(
        word in message
        for word in ("订单", "物流", "快递", "配送", "到哪", "order", "tracking")
    ):
        return "order"
    if any(word in message for word in ("坏了", "破损", "质量", "维修", "保修", "换货")):
        return "ticket"
    if "ord-" in text:
        return "order"
    return "faq"


def _is_closing_request(message: str, text: str) -> bool:
    normalized = re.sub(r"[\s。.!！?？~～,，、]+", "", text)
    closing_phrases = (
        "结束吧",
        "结束了",
        "结束对话",
        "结束会话",
        "关闭对话",
        "关闭会话",
        "不用了",
        "不需要了",
        "没事了",
        "没有问题了",
        "没问题了",
        "可以了",
        "就这样",
        "先这样",
        "再见",
        "拜拜",
        "bye",
        "goodbye",
        "thanksbye",
        "thankyoubye",
    )
    if normalized in closing_phrases:
        return True
    return any(phrase in message for phrase in ("结束本次", "到此为止", "无需继续"))
