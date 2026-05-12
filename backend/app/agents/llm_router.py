from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass
from typing import Any

from app.agents.router import classify_intent, extract_order_id
from app.llm.provider import LLMProvider
from app.models.schemas import Intent

VALID_INTENTS: set[str] = {
    "faq",
    "order",
    "refund",
    "invoice",
    "ticket",
    "handoff",
    "privacy",
    "closing",
    "unknown",
}


@dataclass(frozen=True)
class RouteDecision:
    intent: Intent
    confidence: float
    order_id: str | None = None
    reason: str = ""
    source: str = "rule"
    llm_attempted: bool = False
    llm_json_parse_success: bool = False
    fallback_reason: str = ""


async def classify_intent_hybrid(
    message: str,
    llm: LLMProvider,
    threshold: float = 0.75,
    timeout_s: float = 3.0,
) -> RouteDecision:
    """Classify intent with an LLM candidate and a deterministic rule fallback."""

    rule_intent = classify_intent(message)
    rule_order_id = extract_order_id(message)

    system_prompt = (
        "You are an intent classifier for an ecommerce after-sales support system. "
        "Return JSON only. Valid intent values are: "
        "faq, order, refund, invoice, ticket, handoff, privacy, closing, unknown. "
        "order_id must be null when absent."
    )
    user_prompt = (
        "User message:\n"
        f"{message}\n\n"
        "Return this JSON shape:\n"
        '{ "intent": "...", "confidence": 0.0, "order_id": null, "reason": "..." }'
    )

    try:
        raw = await asyncio.wait_for(llm.complete(system_prompt, user_prompt), timeout=timeout_s)
        data = _parse_json_object(raw)
        intent = str(data.get("intent", "")).strip().lower()
        confidence = float(data.get("confidence", 0.0))
        order_id = _normalize_order_id(data.get("order_id")) or rule_order_id
        reason = str(data.get("reason") or "")

        if intent in VALID_INTENTS and confidence >= threshold:
            return RouteDecision(
                intent=intent,  # type: ignore[arg-type]
                confidence=confidence,
                order_id=order_id,
                reason=reason,
                source="llm",
                llm_attempted=True,
                llm_json_parse_success=True,
            )
        fallback_reason = (
            "llm_low_confidence" if intent in VALID_INTENTS else "llm_invalid_intent"
        )
        return _rule_decision(
            rule_intent,
            rule_order_id,
            llm_attempted=True,
            llm_json_parse_success=True,
            fallback_reason=fallback_reason,
        )
    except Exception as exc:
        return _rule_decision(
            rule_intent,
            rule_order_id,
            llm_attempted=True,
            llm_json_parse_success=False,
            fallback_reason=f"llm_error:{exc.__class__.__name__}",
        )


def _rule_decision(
    intent: Intent,
    order_id: str | None,
    *,
    llm_attempted: bool,
    llm_json_parse_success: bool,
    fallback_reason: str,
) -> RouteDecision:
    return RouteDecision(
        intent=intent,
        confidence=1.0,
        order_id=order_id,
        reason="fallback_to_rule_router",
        source="rule",
        llm_attempted=llm_attempted,
        llm_json_parse_success=llm_json_parse_success,
        fallback_reason=fallback_reason,
    )


def _parse_json_object(raw: str) -> dict[str, Any]:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if not match:
            raise
        payload = json.loads(match.group(0))
    if not isinstance(payload, dict):
        raise ValueError("LLM router response is not a JSON object")
    return payload


def _normalize_order_id(value: Any) -> str | None:
    if value is None:
        return None
    return extract_order_id(str(value))
