from __future__ import annotations

import time
from dataclasses import dataclass
from enum import Enum
from typing import Any

from app.auth.context import AuthContext
from app.models.schemas import ToolCallRecord
from app.tools.business_tools import BusinessToolRegistry


class ToolRiskLevel(str, Enum):
    READ_ONLY = "read_only"
    SIDE_EFFECT = "side_effect"
    HIGH_RISK = "high_risk"


TOOL_RISK_LEVELS = {
    "query_order": ToolRiskLevel.READ_ONLY,
    "query_invoice": ToolRiskLevel.READ_ONLY,
    "check_refund_eligibility": ToolRiskLevel.READ_ONLY,
    "create_refund": ToolRiskLevel.SIDE_EFFECT,
    "create_ticket": ToolRiskLevel.SIDE_EFFECT,
    "handoff_to_human": ToolRiskLevel.SIDE_EFFECT,
}
SIDE_EFFECT_TOOLS = {
    name for name, risk_level in TOOL_RISK_LEVELS.items() if risk_level != ToolRiskLevel.READ_ONLY
}
TOOL_PERMISSIONS = {
    "query_order": "order:read:self",
    "check_refund_eligibility": "refund:create:self",
    "create_refund": "refund:create:self",
    "query_invoice": "invoice:read:self",
    "create_ticket": "ticket:create:self",
    "handoff_to_human": "ticket:create:self",
}


@dataclass(frozen=True)
class ToolPolicyDecision:
    allowed: bool
    status: str
    reason: str = ""
    requires_confirmation: bool = False
    risk_level: ToolRiskLevel = ToolRiskLevel.READ_ONLY


class ToolPolicy:
    def __init__(self, registry: BusinessToolRegistry) -> None:
        self.registry = registry

    def evaluate(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        auth_context: AuthContext,
        confirmed: bool = False,
    ) -> ToolPolicyDecision:
        available_tools = {tool["name"]: tool for tool in self.registry.list_tools()}
        tool = available_tools.get(tool_name)
        if tool is None:
            return ToolPolicyDecision(False, "tool_not_found", f"Tool not found: {tool_name}")

        missing = [
            field
            for field in (tool.get("inputSchema", {}).get("required") or [])
            if field not in arguments or arguments[field] in {None, ""}
        ]
        if missing:
            return ToolPolicyDecision(
                False,
                "schema_invalid",
                f"Missing required fields: {missing}",
            )

        permission = TOOL_PERMISSIONS.get(tool_name)
        if permission and not auth_context.has_permission(permission):
            return ToolPolicyDecision(
                False,
                "permission_denied",
                f"Missing permission: {permission}",
                risk_level=TOOL_RISK_LEVELS.get(tool_name, ToolRiskLevel.READ_ONLY),
            )

        risk_level = TOOL_RISK_LEVELS.get(tool_name, ToolRiskLevel.READ_ONLY)
        if risk_level != ToolRiskLevel.READ_ONLY and not confirmed:
            return ToolPolicyDecision(
                True,
                "needs_confirmation",
                "Side-effect tool requires explicit confirmation before execution.",
                requires_confirmation=True,
                risk_level=risk_level,
            )

        status = "side_effect_approved" if risk_level != ToolRiskLevel.READ_ONLY else "approved"
        return ToolPolicyDecision(True, status, risk_level=risk_level)


class ToolRuntime:
    """Policy, identity, idempotency, and audit wrapper around business tools."""

    def __init__(self, repository: Any, registry: BusinessToolRegistry) -> None:
        self.repository = repository
        self.registry = registry
        self.policy = ToolPolicy(registry)

    async def execute(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        auth_context: AuthContext,
        conversation_id: str,
        case_id: str | None = None,
        task_id: str | None = None,
        idempotency_key: str | None = None,
        confirmed: bool = False,
    ) -> ToolCallRecord:
        start = time.perf_counter()
        safe_arguments = self._bind_identity(tool_name, arguments, auth_context)
        if idempotency_key:
            existing = self.repository.find_tool_audit_by_idempotency_key(
                idempotency_key,
                tool_name=tool_name,
            )
            if existing and existing.get("success"):
                return ToolCallRecord(
                    name=tool_name,
                    arguments=dict(existing.get("arguments") or safe_arguments),
                    success=True,
                    result=existing.get("result"),
                    duration_ms=(time.perf_counter() - start) * 1000,
                    audit_id=existing.get("id"),
                    policy_status="idempotent_replay",
                    idempotency_key=idempotency_key,
                )
        decision = self.policy.evaluate(
            tool_name,
            safe_arguments,
            auth_context,
            confirmed=confirmed,
        )
        if not decision.allowed or decision.requires_confirmation:
            result = {
                "allowed": decision.allowed,
                "reason": decision.reason,
                "requires_confirmation": decision.requires_confirmation,
                "risk_level": decision.risk_level.value,
            }
            audit = self.repository.append_tool_audit(
                conversation_id=conversation_id,
                case_id=case_id,
                task_id=task_id,
                tool_name=tool_name,
                arguments=safe_arguments,
                auth_context=auth_context.to_dict(),
                policy_status=decision.status,
                success=False,
                result=result,
                error=decision.reason if not decision.allowed else None,
                idempotency_key=idempotency_key,
                requires_confirmation=decision.requires_confirmation,
            )
            return ToolCallRecord(
                name=tool_name,
                arguments=safe_arguments,
                success=False,
                result=result,
                error=decision.reason if not decision.allowed else None,
                duration_ms=(time.perf_counter() - start) * 1000,
                audit_id=audit["id"],
                policy_status=decision.status,
                idempotency_key=idempotency_key,
                requires_confirmation=decision.requires_confirmation,
            )

        call = await self.registry.call_tool(tool_name, safe_arguments)
        audit = self.repository.append_tool_audit(
            conversation_id=conversation_id,
            case_id=case_id,
            task_id=task_id,
            tool_name=tool_name,
            arguments=safe_arguments,
            auth_context=auth_context.to_dict(),
            policy_status=decision.status,
            success=call.success,
            result=call.result,
            error=call.error,
            idempotency_key=idempotency_key,
            requires_confirmation=False,
        )
        call.audit_id = audit["id"]
        call.policy_status = decision.status
        call.idempotency_key = idempotency_key
        return call

    @staticmethod
    def _bind_identity(
        tool_name: str,
        arguments: dict[str, Any],
        auth_context: AuthContext,
    ) -> dict[str, Any]:
        safe_arguments = dict(arguments)
        if tool_name in {
            "query_order",
            "check_refund_eligibility",
            "create_refund",
            "query_invoice",
            "create_ticket",
            "handoff_to_human",
        }:
            safe_arguments["user_id"] = auth_context.user_id
        return safe_arguments
