from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from typing import Any

from app.auth.context import AuthContext
from app.auth.rbac import permissions_for_roles


class TokenError(ValueError):
    pass


def _b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def create_access_token(
    *,
    user_id: str,
    roles: tuple[str, ...] = ("customer",),
    tenant_id: str = "demo-tenant",
    secret: str,
    expires_in_seconds: int = 3600,
) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "sub": user_id,
        "tenant_id": tenant_id,
        "roles": list(roles),
        "exp": int(time.time()) + expires_in_seconds,
    }
    signing_input = ".".join(
        [
            _b64encode(json.dumps(header, separators=(",", ":")).encode()),
            _b64encode(json.dumps(payload, separators=(",", ":")).encode()),
        ]
    )
    signature = hmac.new(secret.encode(), signing_input.encode(), hashlib.sha256).digest()
    return f"{signing_input}.{_b64encode(signature)}"


def verify_access_token(token: str, *, secret: str) -> AuthContext:
    try:
        header_b64, payload_b64, signature_b64 = token.split(".", 2)
    except ValueError as exc:
        raise TokenError("Malformed bearer token") from exc
    signing_input = f"{header_b64}.{payload_b64}"
    expected = hmac.new(secret.encode(), signing_input.encode(), hashlib.sha256).digest()
    actual = _b64decode(signature_b64)
    if not hmac.compare_digest(expected, actual):
        raise TokenError("Invalid bearer token signature")
    payload: dict[str, Any] = json.loads(_b64decode(payload_b64))
    if int(payload.get("exp", 0)) < int(time.time()):
        raise TokenError("Bearer token expired")
    user_id = str(payload.get("sub") or "").strip()
    if not user_id:
        raise TokenError("Bearer token missing subject")
    roles = tuple(
        str(role).strip()
        for role in payload.get("roles", ["customer"])
        if str(role).strip()
    )
    if not roles:
        roles = ("customer",)
    return AuthContext(
        user_id=user_id,
        tenant_id=str(payload.get("tenant_id") or "demo-tenant"),
        roles=roles,
        permissions=permissions_for_roles(roles),
        source="bearer-token",
    )
