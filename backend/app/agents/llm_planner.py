from __future__ import annotations

import asyncio
import json
import re
from typing import Any

from app.llm.provider import LLMProvider
from app.models.schemas import ActionPlan, Intent

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
VALID_RISK_LEVELS = {"low", "medium", "high"}


async def build_llm_action_plan(
    message: str,
    intent: Intent,
    order_id: str | None,
    llm: LLMProvider,
    timeout_s: float = 3.0,
) -> ActionPlan | None:
    """Ask the LLM for a candidate plan; callers must validate before use."""

    system_prompt = (
        "You propose candidate ActionPlan JSON for an ecommerce after-sales agent. "
        "Return JSON only. Do not execute tools. Valid tools are query_order, "
        "query_invoice, check_refund_eligibility, create_ticket, handoff_to_human. "
        "Never include create_refund; refunds are created only after confirmation."
    )
    user_prompt = (
        f"Current intent: {intent}\n"
        f"Known order_id: {order_id or 'null'}\n"
        f"User message: {message}\n\n"
        "Return this JSON shape:\n"
        "{\n"
        '  "intent": "order",\n'
        '  "confidence": 0.0,\n'
        '  "slots": {"order_id": null},\n'
        '  "required_tools": [],\n'
        '  "missing_slots": [],\n'
        '  "risk_level": "low",\n'
        '  "requires_confirmation": false,\n'
        '  "requires_handoff": false,\n'
        '  "reason": ""\n'
        "}"
    )

    try:
        raw = await asyncio.wait_for(llm.complete(system_prompt, user_prompt), timeout=timeout_s)
        data = _parse_json_object(raw)
    except Exception:
        return None

    llm_intent = str(data.get("intent") or intent).strip().lower()
    if llm_intent not in VALID_INTENTS:
        return None
    risk_level = str(data.get("risk_level") or "low").strip().lower()
    if risk_level not in VALID_RISK_LEVELS:
        risk_level = "low"

    return ActionPlan(
        intent=llm_intent,  # type: ignore[arg-type]
        confidence=_coerce_float(data.get("confidence"), default=0.0),
        slots=_coerce_dict(data.get("slots")),
        required_tools=_coerce_str_list(data.get("required_tools")),
        missing_slots=_coerce_str_list(data.get("missing_slots")),
        risk_level=risk_level,  # type: ignore[arg-type]
        requires_confirmation=bool(data.get("requires_confirmation", False)),
        requires_handoff=bool(data.get("requires_handoff", False)),
        reason=str(data.get("reason") or ""),
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
        raise ValueError("LLM planner response is not a JSON object")
    return payload


def _coerce_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _coerce_dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _coerce_str_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]
