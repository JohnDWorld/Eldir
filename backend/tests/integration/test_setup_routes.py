"""Tests intégration des routes /setup et /auth."""

from __future__ import annotations

from app.services.setup_service import setup_service
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


async def _emit_token(session_factory: async_sessionmaker[AsyncSession]) -> str:
    async with session_factory() as db:
        token = await setup_service.ensure_bootstrap_token(db)
        await db.commit()
    assert token is not None
    return token


async def test_setup_status_needs_bootstrap_on_empty_db(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/setup/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["needs_bootstrap"] is True
    assert body["bootstrap_completed"] is False
    assert body["has_admin"] is False
    assert body["has_claude_credentials"] is False


async def test_bootstrap_complete_flow(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    token = await _emit_token(session_factory)

    resp = await client.post(
        "/api/v1/setup/bootstrap",
        json={
            "bootstrap_token": token,
            "admin_email": "admin@example.com",
            "admin_password": "averysecurepassword",
            "admin_display_name": "Admin",
            "claude_credentials": [
                {
                    "kind": "oauth_token",
                    "value": "sk-ant-oat01-test-token-value",
                    "label": "pro",
                }
            ],
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["access_token"]
    access_token = body["access_token"]

    # Status doit refléter le bootstrap effectué.
    status_resp = await client.get("/api/v1/setup/status")
    assert status_resp.json()["needs_bootstrap"] is False
    assert status_resp.json()["bootstrap_completed"] is True

    # /auth/me doit retourner l'admin avec le token reçu.
    me_resp = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert me_resp.status_code == 200
    assert me_resp.json()["email"] == "admin@example.com"

    # Re-bootstrap doit échouer (conflit).
    second = await client.post(
        "/api/v1/setup/bootstrap",
        json={
            "bootstrap_token": token,
            "admin_email": "another@example.com",
            "admin_password": "averysecurepassword",
        },
    )
    assert second.status_code == 409


async def test_login_after_bootstrap(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    token = await _emit_token(session_factory)
    await client.post(
        "/api/v1/setup/bootstrap",
        json={
            "bootstrap_token": token,
            "admin_email": "admin@example.com",
            "admin_password": "averysecurepassword",
        },
    )
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "averysecurepassword"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["access_token"]
    assert body["user"]["email"] == "admin@example.com"
