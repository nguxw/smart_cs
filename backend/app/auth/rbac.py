from __future__ import annotations

from app.auth.context import AuthContext

ROLE_PERMISSIONS: dict[str, tuple[str, ...]] = {
    "customer": (
        "conversation:read:self",
        "case:read:self",
        "case:write:self",
        "task:read:self",
        "task:confirm:self",
        "order:read:self",
        "refund:create:self",
        "invoice:read:self",
        "ticket:create:self",
        "kb:read",
    ),
    "agent": (
        "conversation:read:tenant",
        "case:read:tenant",
        "case:write:tenant",
        "task:read:tenant",
        "task:confirm:tenant",
        "ticket:read:tenant",
        "ticket:write:tenant",
        "ticket:create:tenant",
        "handoff:manage:tenant",
        "kb:read",
    ),
    "supervisor": (
        "conversation:read:tenant",
        "case:read:tenant",
        "case:write:tenant",
        "task:read:tenant",
        "task:confirm:tenant",
        "ticket:read:tenant",
        "ticket:write:tenant",
        "ticket:create:tenant",
        "handoff:manage:tenant",
        "handoff:resolve:tenant",
        "kb:read",
        "kb:write",
        "traces:read:tenant",
    ),
    "admin": ("*",),
}


def permissions_for_roles(roles: tuple[str, ...]) -> tuple[str, ...]:
    permissions: set[str] = set()
    for role in roles:
        permissions.update(ROLE_PERMISSIONS.get(role, ()))
    if not permissions:
        permissions.update(ROLE_PERMISSIONS["customer"])
    if "*" in permissions:
        return ("*",)
    return tuple(sorted(permissions))


def with_role_permissions(auth: AuthContext) -> AuthContext:
    return AuthContext(
        user_id=auth.user_id,
        tenant_id=auth.tenant_id,
        roles=auth.roles,
        permissions=permissions_for_roles(auth.roles),
        source=auth.source,
    )


def can_access_user(auth: AuthContext, user_id: str) -> bool:
    return auth.user_id == user_id or auth.has_permission("case:read:tenant")


def can_access_tenant_resource(auth: AuthContext, tenant_id: str | None) -> bool:
    if auth.has_permission("*"):
        return True
    if tenant_id and tenant_id != auth.tenant_id:
        return False
    return auth.has_permission("case:read:tenant") or auth.has_permission("ticket:read:tenant")
