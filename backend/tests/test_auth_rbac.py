from __future__ import annotations

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.auth.context import AuthContext
from app.auth.dependencies import (
    require_auth,
    require_case_access,
    require_permission,
    require_ticket_access,
)
from app.auth.tokens import create_access_token
from app.core.config import Settings
from app.data.repository import DemoRepository

AUTH = Depends(require_auth)


class DummySettings:
    app_env = "production"
    demo_header_auth_enabled = False
    auth_token_secret = "test-secret"


def _app(settings: DummySettings | None = None) -> FastAPI:
    app = FastAPI()
    app.state.settings = settings or DummySettings()

    @app.get("/me")
    async def me(auth: AuthContext = AUTH):
        return auth.to_dict()

    @app.get("/admin")
    async def admin(auth: AuthContext = AUTH):
        require_permission(auth, "*")
        return {"ok": True}

    return app


def test_prod_missing_token_returns_401() -> None:
    client = TestClient(_app())
    response = client.get("/me")
    assert response.status_code == 401


def test_prod_rejects_dev_header_auth() -> None:
    client = TestClient(_app())
    response = client.get("/me", headers={"X-SmartCS-User": "u_1001"})
    assert response.status_code == 401


def test_bearer_token_auth_and_admin_gate() -> None:
    client = TestClient(_app())
    customer_token = create_access_token(user_id="u_1001", secret="test-secret")
    admin_token = create_access_token(
        user_id="admin-demo",
        roles=("admin",),
        secret="test-secret",
    )

    customer_headers = {"Authorization": f"Bearer {customer_token}"}
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    assert client.get("/me", headers=customer_headers).status_code == 200
    assert client.get("/admin", headers=customer_headers).status_code == 403
    assert client.get("/admin", headers=admin_headers).status_code == 200


def test_local_demo_header_marks_auth_source() -> None:
    class LocalSettings:
        app_env = "local"
        demo_header_auth_enabled = True
        auth_token_secret = "test-secret"

    client = TestClient(_app(LocalSettings()))
    response = client.get(
        "/me",
        headers={"X-SmartCS-User": "u_1001", "X-SmartCS-Roles": "customer"},
    )
    assert response.status_code == 200
    assert response.json()["source"] == "dev-header"


def test_customer_case_access_is_owner_scoped() -> None:
    repo = DemoRepository()
    owned = repo.create_or_get_case("u_1001", "demo-tenant", "cv-owned", "refund")
    other = repo.create_or_get_case("u_1002", "demo-tenant", "cv-other", "refund")
    customer = AuthContext(user_id="u_1001")
    agent = AuthContext(
        user_id="agent-demo",
        roles=("agent",),
        permissions=("case:read:tenant",),
    )

    require_case_access(owned, customer)
    try:
        require_case_access(other, customer)
    except Exception as exc:
        assert getattr(exc, "status_code", None) == 403
    else:  # pragma: no cover - defensive
        raise AssertionError("customer should not access another user's case")

    require_case_access(other, agent)


def test_ticket_access_is_tenant_scoped() -> None:
    repo = DemoRepository()
    ticket = repo.create_ticket(
        user_id="u_1001",
        title="tenant scoped",
        description="same tenant only",
        tenant_id="tenant-a",
    )
    same_tenant_agent = AuthContext(
        user_id="agent-a",
        tenant_id="tenant-a",
        roles=("agent",),
        permissions=("ticket:read:tenant", "ticket:write:tenant"),
    )
    other_tenant_agent = AuthContext(
        user_id="agent-b",
        tenant_id="tenant-b",
        roles=("agent",),
        permissions=("ticket:read:tenant", "ticket:write:tenant"),
    )

    require_ticket_access(ticket, same_tenant_agent)
    with pytest.raises(Exception) as exc_info:
        require_ticket_access(ticket, other_tenant_agent)
    assert getattr(exc_info.value, "status_code", None) == 403


def test_production_runtime_boundaries_reject_demo_auth_settings() -> None:
    with pytest.raises(RuntimeError):
        Settings(
            app_env="production",
            demo_header_auth_enabled=True,
            auth_token_secret="not-demo",
        ).validate_runtime_boundaries()
    with pytest.raises(RuntimeError):
        Settings(
            app_env="production",
            demo_header_auth_enabled=False,
            auth_token_secret="local-demo-secret-change-me",
        ).validate_runtime_boundaries()
