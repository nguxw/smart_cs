from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass(frozen=True)
class AuthContext:
    """Identity trusted by the backend and tool runtime.

    The demo console can still switch customers, but all business tools receive this
    server-built identity rather than trusting arbitrary tool arguments.
    """

    user_id: str
    tenant_id: str = "demo-tenant"
    roles: tuple[str, ...] = ("customer",)
    permissions: tuple[str, ...] = field(
        default_factory=lambda: (
            "conversation:read",
            "case:read",
            "case:write",
            "task:confirm",
            "order:read:self",
            "refund:create:self",
            "invoice:read:self",
            "ticket:create:self",
        )
    )
    source: str = "dev-header"

    def has_permission(self, permission: str) -> bool:
        return permission in self.permissions or "*" in self.permissions

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["roles"] = list(self.roles)
        payload["permissions"] = list(self.permissions)
        return payload


def build_dev_auth_context(
    header_user_id: str | None,
    fallback_user_id: str = "anonymous",
    tenant_id: str | None = None,
    roles_header: str | None = None,
) -> AuthContext:
    """Build a development AuthContext from request headers.

    `fallback_user_id` exists for backwards-compatible local demos only. The frontend
    sends the same value in `X-SmartCS-User`, and the tool runtime always uses the
    resulting AuthContext rather than trusting raw tool arguments.
    """

    user_id = (header_user_id or fallback_user_id or "anonymous").strip() or "anonymous"
    tenant = (tenant_id or "demo-tenant").strip() or "demo-tenant"
    roles = tuple(
        role.strip()
        for role in (roles_header or "customer").split(",")
        if role.strip()
    ) or ("customer",)
    permissions: tuple[str, ...]
    if "admin" in roles or "agent" in roles:
        permissions = ("*",)
    else:
        permissions = AuthContext(user_id=user_id).permissions
    return AuthContext(user_id=user_id, tenant_id=tenant, roles=roles, permissions=permissions)
