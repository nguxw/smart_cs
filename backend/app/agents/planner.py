from __future__ import annotations

from app.models.schemas import ActionPlan, Intent

LATEST_ORDER_PHRASES = (
    "最近订单",
    "最近一笔",
    "上一单",
    "上一个订单",
    "刚买",
    "刚下单",
    "最新订单",
    "latest order",
    "last order",
)

ACTIONABLE_PHRASES = (
    "帮我",
    "我要",
    "我想",
    "申请",
    "办理",
    "处理",
    "查一下",
    "看一下",
    "确认",
    "下载",
)

POLICY_PHRASES = (
    "规则",
    "政策",
    "条件",
    "流程",
    "说明",
    "怎么办",
    "多久",
    "几天",
    "可以吗",
    "能不能",
)


def references_latest_order(message: str) -> bool:
    text = message.lower()
    return any(phrase in message or phrase in text for phrase in LATEST_ORDER_PHRASES)


def build_action_plan(
    message: str,
    intent: Intent,
    order_id: str | None,
) -> ActionPlan:
    slots: dict[str, str] = {}
    if order_id:
        slots["order_id"] = order_id
    elif references_latest_order(message):
        slots["order_reference"] = "latest"

    if intent in {"faq", "unknown"}:
        return ActionPlan(
            intent=intent,
            confidence=0.58,
            slots=slots,
            reason="知识问答类请求，优先使用知识库回复。",
        )

    if intent == "closing":
        return ActionPlan(
            intent=intent,
            confidence=0.92,
            slots=slots,
            risk_level="low",
            reason="用户主动结束本次会话，不需要进入人工队列。",
        )

    if intent == "handoff":
        return ActionPlan(
            intent=intent,
            confidence=0.86,
            slots=slots,
            required_tools=["create_ticket"],
            risk_level="medium",
            requires_handoff=True,
            reason="用户明确要求人工接管或投诉处理。",
        )

    if intent == "privacy":
        return ActionPlan(
            intent=intent,
            confidence=0.9,
            slots=slots,
            required_tools=["query_order"] if slots else ["create_ticket"],
            risk_level="high",
            requires_handoff=True,
            reason="请求涉及他人订单或隐私信息，需要权限校验并转人工留痕。",
        )

    if intent == "ticket":
        return ActionPlan(
            intent=intent,
            confidence=0.78,
            slots=slots,
            required_tools=["create_ticket"],
            risk_level="medium",
            requires_handoff=True,
            reason="商品质量或售后异常需要人工工单跟进。",
        )

    if intent == "refund":
        wants_action = _is_actionable(message)
        if not slots and wants_action:
            return ActionPlan(
                intent=intent,
                confidence=0.7,
                missing_slots=["order_id"],
                risk_level="medium",
                reason="退款会影响具体订单，缺少订单号时不能默认选择最近订单。",
            )
        if not slots:
            return ActionPlan(
                intent=intent,
                confidence=0.62,
                reason="退款规则咨询，先用知识库解释政策，不调用订单工具。",
            )
        return ActionPlan(
            intent=intent,
            confidence=0.9,
            slots=slots,
            required_tools=["check_refund_eligibility"],
            risk_level="medium",
            requires_confirmation=_is_refund_create_request(message),
            reason="先校验退款资格；创建退款申请必须等待客户确认。",
        )

    if intent == "invoice":
        if not slots and _is_actionable(message):
            return ActionPlan(
                intent=intent,
                confidence=0.68,
                missing_slots=["order_id"],
                reason="查询或下载发票需要明确订单号。",
            )
        if not slots:
            return ActionPlan(
                intent=intent,
                confidence=0.6,
                reason="发票规则咨询，先用知识库回复。",
            )
        return ActionPlan(
            intent=intent,
            confidence=0.88,
            slots=slots,
            required_tools=["query_invoice"],
            reason="订单号已明确，可以查询发票状态。",
        )

    if intent == "order":
        if not slots and _is_actionable(message):
            return ActionPlan(
                intent=intent,
                confidence=0.68,
                missing_slots=["order_id"],
                reason="订单或物流查询需要明确订单号。",
            )
        if not slots:
            return ActionPlan(
                intent=intent,
                confidence=0.6,
                reason="物流规则咨询，先用知识库回复。",
            )
        return ActionPlan(
            intent=intent,
            confidence=0.88,
            slots=slots,
            required_tools=["query_order"],
            reason="订单号已明确，可以查询订单和物流状态。",
        )

    return ActionPlan(intent=intent, confidence=0.5, slots=slots, reason="保守兜底计划。")


def _is_actionable(message: str) -> bool:
    return any(phrase in message for phrase in ACTIONABLE_PHRASES)


def _is_refund_create_request(message: str) -> bool:
    explicit_phrase = any(
        phrase in message
        for phrase in (
            "申请退款",
            "申请退货",
            "我要退款",
            "我要退货",
            "我想退款",
            "想退款",
            "帮我退款",
            "帮我退货",
            "想退货",
            "帮我申请",
            "办理退款",
            "退货退款",
            "退掉",
        )
    )
    intent_pair = any(verb in message for verb in ("申请", "我要", "帮我", "办理")) and any(
        noun in message for noun in ("退款", "退货")
    )
    return explicit_phrase or intent_pair
