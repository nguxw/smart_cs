from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from fastapi import Header, HTTPException, Request

from app.auth.context import AuthContext, build_dev_auth_context
from app.auth.rbac import with_role_permissions
from app.auth.tokens import TokenError, verify_access_token
from app.core.config import settings as global_settings


def _settings_from_request(request: Request) -> Any:
    return getattr(request.app.state, "settings", global_settings)


async def require_auth(
    request: Request,
    authorization: str | None = Header(default=None),
    x_smartcs_user: str | None = Header(default=None),
    x_smartcs_tenant: str | None = Header(default=None),
    x_smartcs_roles: str | None = Header(default=None),
) -> AuthContext:
    settings = _settings_from_request(request)
    app_env = settings.app_env.strip().lower()
    has_demo_headers = any([x_smartcs_user, x_smartcs_tenant, x_smartcs_roles])
    if app_env in {"local", "dev", "development", "test"} and settings.demo_header_auth_enabled:
        return with_role_permissions(
            build_dev_auth_context(
                header_user_id=x_smartcs_user,
                fallback_user_id="anonymous",
                tenant_id=x_smartcs_tenant,
                roles_header=x_smartcs_roles,
            )
        )
    if has_demo_headers:
        raise HTTPException(status_code=401, detail="Development header authentication is disabled")
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    token = authorization.removeprefix("Bearer ").strip()
    try:
        return verify_access_token(token, secret=settings.auth_token_secret)
    except TokenError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


def require_permission(auth: AuthContext, permission: str) -> None:
    if not auth.has_permission(permission):
        raise HTTPException(status_code=403, detail=f"Missing permission: {permission}")


def has_any_permission(auth: AuthContext, permissions: Iterable[str]) -> bool:
    return any(auth.has_permission(permission) for permission in permissions)


def require_case_access(
    case: dict[str, Any],
    auth: AuthContext,
    *,
    write: bool = False,
) -> None:
    if auth.has_permission("*"):
        return
    owner_ok = case.get("user_id") == auth.user_id
    tenant_ok = case.get("tenant_id") == auth.tenant_id
    owner_permissions = (
        ("case:write:self", "case:write")
        if write
        else ("case:read:self", "case:read")
    )
    if owner_ok and has_any_permission(auth, owner_permissions):
        return
    if tenant_ok and auth.has_permission("case:write:tenant" if write else "case:read:tenant"):
        return
    raise HTTPException(status_code=403, detail="Case access denied")


def require_task_access(
    task: dict[str, Any],
    case: dict[str, Any],
    auth: AuthContext,
    *,
    confirm: bool = False,
) -> None:
    if auth.has_permission("*"):
        return
    owner_ok = case.get("user_id") == auth.user_id
    tenant_ok = case.get("tenant_id") == auth.tenant_id
    owner_permissions = (
        ("task:confirm:self", "task:confirm")
        if confirm
        else ("task:read:self", "task:read")
    )
    if owner_ok and has_any_permission(auth, owner_permissions):
        return
    if tenant_ok and auth.has_permission("task:confirm:tenant" if confirm else "task:read:tenant"):
        return
    raise HTTPException(status_code=403, detail="Task access denied")


def require_ticket_access(
    ticket: dict[str, Any],
    auth: AuthContext,
    *,
    write: bool = False,
) -> None:
    if auth.has_permission("*"):
        return
    owner_ok = ticket.get("user_id") == auth.user_id
    if owner_ok and not write and auth.has_permission("ticket:create:self"):
        return
    if auth.has_permission("ticket:write:tenant" if write else "ticket:read:tenant"):
        return
    raise HTTPException(status_code=403, detail="Ticket access denied")


def require_admin(auth: AuthContext) -> None:
    require_permission(auth, "*")
