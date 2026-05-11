from __future__ import annotations

import time
from dataclasses import dataclass
from enum import Enum
from typing import Any

from app.auth.context import AuthContext
from app.models.schemas import ToolCallRecord
from app.observability.metrics import metrics_registry
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
    "query_order": ("order:read:self", "order:read:tenant"),
    "check_refund_eligibility": ("refund:create:self",),
    "create_refund": ("refund:create:self",),
    "query_invoice": ("invoice:read:self", "invoice:read:tenant"),
    "create_ticket": ("ticket:create:self", "ticket:create:tenant"),
    "handoff_to_human": ("ticket:create:self", "ticket:create:tenant"),
}


@dataclass(frozen=True)
class ToolPolicyDecision:
    allowed: bool
    status: str
    reason: str = ""
    requires_confirmation: bool = False
    risk_level: ToolRiskLevel = ToolRiskLevel.READ_ONLY
    subject_user_id: str | None = None
    resource_id: str | None = None
    policy_rules_hit: tuple[str, ...] = ()


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
                policy_rules_hit=("schema.required",),
            )

        permissions = TOOL_PERMISSIONS.get(tool_name, ())
        if permissions and not self._has_tool_permission(
            tool_name,
            arguments,
            auth_context,
            permissions,
        ):
            return ToolPolicyDecision(
                False,
                "permission_denied",
                f"Missing one of permissions: {', '.join(permissions)}",
                risk_level=TOOL_RISK_LEVELS.get(tool_name, ToolRiskLevel.READ_ONLY),
                subject_user_id=auth_context.user_id,
                resource_id=str(
                    arguments.get("order_id") or arguments.get("conversation_id") or ""
                ),
                policy_rules_hit=("rbac.permission",),
            )

        risk_level = TOOL_RISK_LEVELS.get(tool_name, ToolRiskLevel.READ_ONLY)
        if risk_level != ToolRiskLevel.READ_ONLY and not confirmed:
            return ToolPolicyDecision(
                True,
                "needs_confirmation",
                "Side-effect tool requires explicit confirmation before execution.",
                requires_confirmation=True,
                risk_level=risk_level,
                subject_user_id=auth_context.user_id,
                resource_id=str(
                    arguments.get("order_id") or arguments.get("conversation_id") or ""
                ),
                policy_rules_hit=("risk.confirmation_required",),
            )

        status = "side_effect_approved" if risk_level != ToolRiskLevel.READ_ONLY else "approved"
        return ToolPolicyDecision(
            True,
            status,
            risk_level=risk_level,
            subject_user_id=auth_context.user_id,
            resource_id=str(arguments.get("order_id") or arguments.get("conversation_id") or ""),
            policy_rules_hit=("risk.approved",),
        )

    def _has_tool_permission(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        auth_context: AuthContext,
        permissions: tuple[str, ...],
    ) -> bool:
        if auth_context.has_permission("*"):
            return True
        order = _order_for_arguments(arguments, self.registry.repository)
        resource_user_id = str(
            (order or {}).get("user_id") or arguments.get("user_id") or auth_context.user_id
        )
        resource_tenant_id = _resource_tenant_id(self.registry.repository, tool_name, arguments)
        for permission in permissions:
            if not auth_context.has_permission(permission):
                continue
            if permission.endswith(":self") and resource_user_id == auth_context.user_id:
                return True
            if permission.endswith(":tenant") and resource_tenant_id == auth_context.tenant_id:
                return True
        return False


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
                "subject_user_id": decision.subject_user_id,
                "resource_id": decision.resource_id,
                "policy_rules_hit": list(decision.policy_rules_hit),
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
            record = ToolCallRecord(
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
            metrics_registry.inc(
                "smartcs_tool_call_total",
                tool=tool_name,
                status=decision.status,
                success="false",
            )
            return record

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
        metrics_registry.inc(
            "smartcs_tool_call_total",
            tool=tool_name,
            status=decision.status,
            success=str(call.success).lower(),
        )
        return call

    def _bind_identity(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        auth_context: AuthContext,
    ) -> dict[str, Any]:
        safe_arguments = dict(arguments)
        if tool_name in {
            "query_order",
            "query_invoice",
        }:
            if auth_context.has_permission("order:read:tenant") or auth_context.has_permission(
                "invoice:read:tenant"
            ):
                order = _order_for_arguments(arguments, self.repository)
                if order and order.get("tenant_id") == auth_context.tenant_id:
                    safe_arguments["user_id"] = order["user_id"]
                    return safe_arguments
            safe_arguments["user_id"] = auth_context.user_id
        if tool_name in {
            "check_refund_eligibility",
            "create_refund",
        }:
            safe_arguments["user_id"] = auth_context.user_id
        if tool_name in {
            "create_ticket",
            "handoff_to_human",
        }:
            requested_user_id = str(safe_arguments.get("user_id") or auth_context.user_id)
            if (
                auth_context.has_permission("ticket:create:tenant")
                and _user_tenant_id(self.repository, requested_user_id) == auth_context.tenant_id
            ):
                safe_arguments["user_id"] = requested_user_id
            else:
                safe_arguments["user_id"] = auth_context.user_id
            safe_arguments["tenant_id"] = auth_context.tenant_id
        return safe_arguments


def _order_for_arguments(
    arguments: dict[str, Any],
    repository: Any | None,
) -> dict[str, Any] | None:
    order_id = arguments.get("order_id")
    if not order_id or repository is None:
        return None
    if hasattr(repository, "get_order_metadata"):
        order = repository.get_order_metadata(str(order_id))
        return dict(order) if order else None
    orders = getattr(repository, "orders", None)
    if isinstance(orders, dict) and order_id in orders:
        order = orders[order_id]
        return {
            "id": order.id,
            "user_id": order.user_id,
            "tenant_id": getattr(order, "tenant_id", "demo-tenant"),
        }
    return None


def _resource_tenant_id(repository: Any, tool_name: str, arguments: dict[str, Any]) -> str:
    if tool_name in {"query_order", "query_invoice", "check_refund_eligibility", "create_refund"}:
        order = _order_for_arguments(arguments, repository)
        if order:
            return str(order.get("tenant_id") or "demo-tenant")
    return str(arguments.get("tenant_id") or "demo-tenant")


def _user_tenant_id(repository: Any | None, user_id: str) -> str:
    if repository is not None and hasattr(repository, "get_user_tenant_id"):
        tenant_id = repository.get_user_tenant_id(user_id)
        if tenant_id:
            return tenant_id
    users = getattr(repository, "users", None) if repository is not None else None
    if isinstance(users, dict):
        user = users.get(user_id)
        if isinstance(user, dict):
            return str(user.get("tenant_id") or "demo-tenant")
    return "demo-tenant"
