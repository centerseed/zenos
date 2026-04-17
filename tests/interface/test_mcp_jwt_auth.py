"""Integration tests for delegated JWT auth boundary in MCP middleware (ADR-030)."""

from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import AsyncMock, patch

import pytest
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

import zenos.interface.mcp as mcp
from zenos.infrastructure.identity.jwt_service import JwtService
from zenos.interface.mcp import ApiKeyMiddleware


TEST_SECRET = "jwt-test-secret"  # pragma: allowlist secret

ACTIVE_PARTNER = {
    "id": "principal-1",
    "email": "jwt@test.com",
    "displayName": "JWT Partner",
    "status": "active",
    "isAdmin": False,
    "sharedPartnerId": "shared-99",
    "defaultProject": None,
    "roles": [],
    "department": "all",
    "authorizedEntityIds": ["l1-a"],
    "workspaceRole": "guest",
    "accessMode": "scoped",
}


def _build_token(
    *,
    principal_id: str = "principal-1",
    workspace_ids: list[str] | None = None,
    scopes: list[str] | None = None,
    ttl: int = 3600,
) -> str:
    service = JwtService(secret=TEST_SECRET)
    return service.sign_delegated_credential(
        principal_id=principal_id,
        app_id="trusted-app-1",
        workspace_ids=workspace_ids or ["principal-1", "shared-99"],
        scopes=scopes or ["read", "write", "task"],
        ttl=ttl,
    )


def _make_app() -> ApiKeyMiddleware:
    async def ping(_request):
        partner = mcp._auth._current_partner.get() or {}
        return JSONResponse({"ok": True, "defaultProject": partner.get("defaultProject")})

    async def call_write(_request):
        result = await mcp.write(
            collection="entities",
            data={
                "name": "JWT Entity",
                "type": "product",
                "summary": "demo",
                "tags": {"what": "x", "why": "y", "how": "z", "who": "w"},
            },
        )
        return JSONResponse(result)

    async def call_confirm(_request):
        result = await mcp.confirm(collection="entities", id="ent-1")
        return JSONResponse(result)

    async def call_journal_write(_request):
        result = await mcp.journal_write(summary="hello")
        return JSONResponse(result)

    async def call_upload_attachment(_request):
        result = await mcp.upload_attachment(
            task_id="task-1",
            filename="demo.txt",
            content_type="text/plain",
        )
        return JSONResponse(result)

    async def call_task(_request):
        result = await mcp.task(action="create", title="Create by JWT")
        return JSONResponse(result)

    async def call_plan(_request):
        result = await mcp.plan(action="list")
        return JSONResponse(result)

    async def call_search_with_workspace(request):
        result = await mcp.search(
            collection="entities",
            workspace_id=request.query_params.get("workspace_id"),
        )
        return JSONResponse(result)

    inner = Starlette(
        routes=[
            Route("/ping", ping),
            Route("/tool/write", call_write),
            Route("/tool/confirm", call_confirm),
            Route("/tool/journal_write", call_journal_write),
            Route("/tool/upload_attachment", call_upload_attachment),
            Route("/tool/task", call_task),
            Route("/tool/plan", call_plan),
            Route("/tool/search", call_search_with_workspace),
        ]
    )
    return ApiKeyMiddleware(inner)


@contextmanager
def _jwt_client(*, partner: dict | None, jwt_service: JwtService | object):
    class _Repo:
        def __init__(self, _pool):
            pass

        async def get_by_id(self, partner_id: str):
            if not partner:
                return None
            if str(partner["id"]) != str(partner_id):
                return None
            return dict(partner)

    app = _make_app()
    with (
        patch("zenos.interface.mcp._auth._get_jwt_service", return_value=jwt_service),
        patch("zenos.infrastructure.sql_common.get_pool", new=AsyncMock(return_value=object())),
        patch("zenos.infrastructure.identity.SqlPartnerRepository", _Repo),
    ):
        with TestClient(app, raise_server_exceptions=True) as client:
            yield client


class TestMcpJwtMiddlewareIntegration:
    def test_invalid_jwt_returns_401(self):
        jwt_service = JwtService(secret=TEST_SECRET)
        with _jwt_client(partner=ACTIVE_PARTNER, jwt_service=jwt_service) as client:
            # Must start with "eyJ" to trigger JWT auth path in middleware.
            resp = client.get("/ping", headers={"Authorization": "Bearer eyJ.invalid.jwt"})
        assert resp.status_code == 401
        assert resp.json()["error"] == "UNAUTHORIZED"

    def test_expired_jwt_returns_401(self):
        jwt_service = JwtService(secret=TEST_SECRET)
        expired = _build_token(ttl=-60)
        with _jwt_client(partner=ACTIVE_PARTNER, jwt_service=jwt_service) as client:
            resp = client.get("/ping", headers={"Authorization": f"Bearer {expired}"})
        assert resp.status_code == 401
        assert resp.json()["error"] == "UNAUTHORIZED"

    def test_principal_not_found_returns_401(self):
        jwt_service = JwtService(secret=TEST_SECRET)
        token = _build_token(principal_id="missing-principal")
        with _jwt_client(partner=None, jwt_service=jwt_service) as client:
            resp = client.get("/ping", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 401
        assert resp.json()["error"] == "UNAUTHORIZED"

    def test_workspace_header_not_in_workspace_ids_claim_returns_403(self):
        jwt_service = JwtService(secret=TEST_SECRET)
        token = _build_token(workspace_ids=["principal-1"])
        with _jwt_client(partner=ACTIVE_PARTNER, jwt_service=jwt_service) as client:
            resp = client.get(
                "/ping",
                headers={
                    "Authorization": f"Bearer {token}",
                    "X-Active-Workspace-Id": "shared-99",
                },
            )
        assert resp.status_code == 403
        assert resp.json()["error"] == "FORBIDDEN"

    def test_default_home_workspace_outside_workspace_ids_claim_returns_403(self):
        jwt_service = JwtService(secret=TEST_SECRET)
        # Token only allows shared workspace. Missing header means default-home resolution.
        token = _build_token(workspace_ids=["shared-99"])
        with _jwt_client(partner=ACTIVE_PARTNER, jwt_service=jwt_service) as client:
            resp = client.get("/ping", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 403
        assert resp.json()["error"] == "FORBIDDEN"

    @pytest.mark.parametrize(
        ("path", "required_scope"),
        [
            ("/tool/write", "write"),
            ("/tool/confirm", "write"),
            ("/tool/journal_write", "write"),
            ("/tool/upload_attachment", "write"),
            ("/tool/task", "task"),
            ("/tool/plan", "task"),
        ],
    )
    def test_scope_enforcement_on_real_tool_handlers(self, path: str, required_scope: str):
        """Middleware + wrapped tool handler integration (not decorator unit tests)."""
        jwt_service = JwtService(secret=TEST_SECRET)
        token = _build_token(scopes=["read"])
        with _jwt_client(partner=ACTIVE_PARTNER, jwt_service=jwt_service) as client:
            resp = client.get(path, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "error"
        assert body["data"]["error"] == "FORBIDDEN"
        assert any(required_scope in warning for warning in body.get("warnings", []))

    def test_workspace_override_rejected_when_not_in_jwt_workspace_ids_claim(self):
        jwt_service = JwtService(secret=TEST_SECRET)
        token = _build_token(workspace_ids=["principal-1"], scopes=["read"])
        with _jwt_client(partner=ACTIVE_PARTNER, jwt_service=jwt_service) as client:
            resp = client.get(
                "/tool/search?workspace_id=shared-99",
                headers={"Authorization": f"Bearer {token}"},
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "error"
        assert body["data"]["error"] == "FORBIDDEN"

    def test_query_project_overrides_default_project_for_jwt_request(self):
        jwt_service = JwtService(secret=TEST_SECRET)
        token = _build_token()
        with _jwt_client(partner=ACTIVE_PARTNER, jwt_service=jwt_service) as client:
            resp = client.get(
                "/ping?project=  Paceriz  ",
                headers={"Authorization": f"Bearer {token}"},
            )
        assert resp.status_code == 200
        assert resp.json()["defaultProject"] == "paceriz"
