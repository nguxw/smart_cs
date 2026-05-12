from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from app.agents.router import extract_order_id
from app.models.schemas import ActionPlan

VALID_TOOLS = {
    "query_order",
    "query_invoice",
    "check_refund_eligibility",
    "create_refund",
    "create_ticket",
    "handoff_to_human",
}
LLM_ALLOWED_TOOLS = {
    "query_order",
    "query_invoice",
    "check_refund_eligibility",
}
SIDE_EFFECT_TOOLS = {
    "create_refund",
    "create_ticket",
    "handoff_to_human",
}
RISK_ORDER = {"low": 0, "medium": 1, "high": 2}


@dataclass(frozen=True)
class PlanValidationResult:
    plan: ActionPlan
    source: str
    llm_plan_available: bool
    rejected_tools: list[str]
    adjustments: list[str]
    rejected: bool = False
    unsafe_plan_blocked: bool = False


def merge_and_validate_action_plan(
    rule_plan: ActionPlan,
    llm_plan: ActionPlan | None,
) -> PlanValidationResult:
    """Merge an LLM candidate into the rule plan without relaxing policy boundaries."""

    if llm_plan is None:
        return PlanValidationResult(
            plan=rule_plan,
            source="rule",
            llm_plan_available=False,
            rejected_tools=[],
            adjustments=[],
        )

    rejected_tools: list[str] = []
    adjustments: list[str] = []
    unsafe_plan_blocked = False

    if llm_plan.intent != rule_plan.intent:
        return PlanValidationResult(
            plan=rule_plan,
            source="rule",
            llm_plan_available=True,
            rejected_tools=[],
            adjustments=["intent_mismatch"],
            rejected=True,
        )

    merged = replace(rule_plan)
    merged.slots = dict(rule_plan.slots)
    merged.required_tools = list(rule_plan.required_tools)
    merged.missing_slots = list(rule_plan.missing_slots)

    for key, value in llm_plan.slots.items():
        normalized = _normalize_slot(key, value)
        if normalized is not None and key not in merged.slots:
            merged.slots[key] = normalized
            adjustments.append(f"slot_added:{key}")

    candidate_tools = []
    for tool in llm_plan.required_tools:
        if tool not in VALID_TOOLS:
            rejected_tools.append(tool)
            adjustments.append(f"unknown_tool_blocked:{tool}")
            continue
        if tool in SIDE_EFFECT_TOOLS:
            rejected_tools.append(tool)
            adjustments.append(f"side_effect_tool_blocked:{tool}")
            unsafe_plan_blocked = True
            continue
        if tool not in LLM_ALLOWED_TOOLS:
            rejected_tools.append(tool)
            adjustments.append(f"tool_not_llm_allowed:{tool}")
            continue
        candidate_tools.append(tool)

    order_id = merged.slots.get("order_id")
    if not order_id:
        blocked = [tool for tool in candidate_tools if tool in LLM_ALLOWED_TOOLS]
        for tool in blocked:
            rejected_tools.append(tool)
            adjustments.append(f"missing_order_id_blocks:{tool}")
        candidate_tools = []

    if rule_plan.intent in {"order", "invoice"} and candidate_tools:
        merged.required_tools = _ordered_unique([*merged.required_tools, *candidate_tools])
        adjustments.append("low_risk_tools_merged")
    elif rule_plan.intent == "refund" and order_id:
        if "check_refund_eligibility" in candidate_tools or merged.required_tools:
            merged.required_tools = ["check_refund_eligibility"]
            adjustments.append("refund_tool_normalized")

    merged.confidence = max(rule_plan.confidence, llm_plan.confidence)
    merged.risk_level = _max_risk_level(rule_plan.risk_level, llm_plan.risk_level)
    if llm_plan.reason:
        merged.reason = f"{rule_plan.reason} LLM candidate: {llm_plan.reason}".strip()

    return PlanValidationResult(
        plan=merged,
        source="llm_validated",
        llm_plan_available=True,
        rejected_tools=_ordered_unique(rejected_tools),
        adjustments=_ordered_unique(adjustments),
        rejected=bool(rejected_tools),
        unsafe_plan_blocked=unsafe_plan_blocked,
    )


def _normalize_slot(key: str, value: Any) -> Any:
    if value in {None, ""}:
        return None
    if key == "order_id":
        return extract_order_id(str(value))
    if isinstance(value, str):
        return value.strip() or None
    return value


def _ordered_unique(items: list[str]) -> list[str]:
    return list(dict.fromkeys(items))


def _max_risk_level(left: str, right: str) -> str:
    return left if RISK_ORDER.get(left, 0) >= RISK_ORDER.get(right, 0) else right
