"""Authorization matrix tests for one principal across home/shared workspaces (ADR-030)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

import zenos.interface.mcp as mcp
from zenos.domain.action import Task
from zenos.domain.knowledge import Entity, Tags
from zenos.interface.mcp import ApiKeyMiddleware


VALID_KEY = "valid-key-matrix"


def _make_entity(
    *,
    eid: str,
    name: str,
    visibility: str = "public",
    parent_id: str | None = None,
    level: int = 2,
    type: str = "module",
) -> Entity:
    return Entity(
        id=eid,
        name=name,
        type=type,
        level=level,
        parent_id=parent_id,
        status="active",
        summary=f"{name} summary",
        tags=Tags(what=["x"], why="y", how="z", who=["w"]),
        visibility=visibility,
        confirmed_by_user=True,
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        updated_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
    )


def _make_task(*, tid: str, linked_entities: list[str]) -> Task:
    return Task(
        id=tid,
        title=tid,
        description=f"{tid} desc",
        status="todo",
        priority="medium",
        created_by="principal-1",
        updated_by="principal-1",
        linked_entities=linked_entities,
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        updated_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
    )


ALL_ENTITIES = [
    _make_entity(eid="l1-a", name="L1 A", type="product", level=1, visibility="public"),
    _make_entity(eid="l2-a-public", name="L2 A Public", parent_id="l1-a", visibility="public"),
    _make_entity(eid="l2-a-restricted", name="L2 A Restricted", parent_id="l1-a", visibility="restricted"),
    _make_entity(eid="l2-a-confidential", name="L2 A Confidential", parent_id="l1-a", visibility="confidential"),
    _make_entity(eid="l1-b", name="L1 B", type="product", level=1, visibility="public"),
    _make_entity(eid="l2-b-public", name="L2 B Public", parent_id="l1-b", visibility="public"),
]
ENTITY_MAP = {e.id: e for e in ALL_ENTITIES if e.id}

ALL_TASKS = [
    _make_task(tid="t-a-public", linked_entities=["l2-a-public"]),
    _make_task(tid="t-a-restricted", linked_entities=["l2-a-restricted"]),
    _make_task(tid="t-a-confidential", linked_entities=["l2-a-confidential"]),
    _make_task(tid="t-b-public", linked_entities=["l2-b-public"]),
    _make_task(tid="t-unlinked", linked_entities=[]),
]


def _make_partner(role: str) -> dict:
    base = {
        "id": "principal-1",
        "email": "principal@test.com",
        "displayName": "Principal",
        "apiKey": VALID_KEY,  # pragma: allowlist secret
        "status": "active",
        "isAdmin": False,
        "sharedPartnerId": "shared-99",
        "defaultProject": None,
        "roles": [],
        "department": "all",
    }
    if role == "guest":
        return {
            **base,
            "workspaceRole": "guest",
            "accessMode": "scoped",
            "authorizedEntityIds": ["l1-a"],
        }
    if role == "member":
        return {
            **base,
            "workspaceRole": "member",
            "accessMode": "internal",
            "authorizedEntityIds": [],
        }
    raise ValueError(f"unsupported role: {role}")


def _make_mcp_app() -> ApiKeyMiddleware:
    async def entities(_request):
        from zenos.interface.mcp._auth import _current_partner
        from zenos.infrastructure.context import current_partner_id

        result = await mcp.search(collection="entities")
        partner = _current_partner.get() or {}
        result["debug"] = {
            "workspace_role": partner.get("workspaceRole"),
            "effective_partner_id": current_partner_id.get(),
        }
        return JSONResponse(result)

    async def tasks(_request):
        from zenos.interface.mcp._auth import _current_partner
        from zenos.infrastructure.context import current_partner_id

        result = await mcp.search(collection="tasks")
        partner = _current_partner.get() or {}
        result["debug"] = {
            "workspace_role": partner.get("workspaceRole"),
            "effective_partner_id": current_partner_id.get(),
        }
        return JSONResponse(result)

    inner = Starlette(routes=[Route("/entities", entities), Route("/tasks", tasks)])
    return ApiKeyMiddleware(inner)


def _make_dashboard_request(headers: dict | None = None) -> MagicMock:
    req = MagicMock()
    req.method = "GET"
    req.headers = headers or {}
    req.query_params = {}
    req.path_params = {}
    return req


class _McpClientForRole:
    def __init__(self, role: str):
        self.role = role

    def __enter__(self):
        self.partner = _make_partner(self.role)
        self.app = _make_mcp_app()

        async def _validate(key: str):
            if key == VALID_KEY:
                return dict(self.partner)
            return None

        self._patches = [
            patch("zenos.interface.mcp._ensure_services", new=AsyncMock(return_value=None)),
            patch("zenos.interface.mcp.ontology_service", new=MagicMock()),
            patch("zenos.interface.mcp.task_service", new=MagicMock()),
            patch("zenos.interface.mcp.entity_repo", new=MagicMock()),
            patch("zenos.interface.mcp._auth._partner_validator", new=MagicMock()),
        ]
        for p in self._patches:
            p.start()

        mcp.ontology_service.list_entities = AsyncMock(return_value=ALL_ENTITIES)
        mcp.ontology_service._entities = MagicMock()
        mcp.ontology_service._entities.list_all = AsyncMock(return_value=ALL_ENTITIES)

        mcp.task_service.list_tasks = AsyncMock(return_value=ALL_TASKS)
        mcp.task_service.enrich_task = AsyncMock(
            side_effect=lambda task: {
                "expanded_entities": [{"id": eid} for eid in (task.linked_entities or [])],
            }
        )

        mcp.entity_repo.list_all = AsyncMock(return_value=ALL_ENTITIES)
        mcp.entity_repo.get_by_id = AsyncMock(side_effect=lambda eid: ENTITY_MAP.get(eid))

        from zenos.interface.mcp._auth import _partner_validator
        _partner_validator.validate = AsyncMock(side_effect=_validate)

        self.client = TestClient(self.app, raise_server_exceptions=True)
        self.client.__enter__()
        return self.client

    def __exit__(self, exc_type, exc, tb):
        self.client.__exit__(exc_type, exc, tb)
        for p in reversed(self._patches):
            p.stop()


class TestMcpWorkspaceAuthorizationMatrix:
    def test_guest_projection_home_vs_shared_entity_matrix(self):
        with _McpClientForRole("guest") as client:
            home = client.get("/entities", headers={"Authorization": f"Bearer {VALID_KEY}"}).json()
            shared = client.get(
                "/entities",
                headers={
                    "Authorization": f"Bearer {VALID_KEY}",
                    "X-Active-Workspace-Id": "shared-99",
                },
            ).json()

        home_ids = {e["id"] for e in home["entities"]}
        shared_ids = {e["id"] for e in shared["entities"]}

        assert home["workspace_context"]["is_home_workspace"] is True
        assert home["debug"]["workspace_role"] == "owner"
        assert home["debug"]["effective_partner_id"] == "principal-1"
        assert home_ids == set(ENTITY_MAP.keys())

        assert shared["workspace_context"]["is_home_workspace"] is False
        assert shared["debug"]["workspace_role"] == "guest"
        assert shared["debug"]["effective_partner_id"] == "shared-99"
        assert shared_ids == {"l1-a", "l2-a-public"}

    def test_member_projection_home_vs_shared_entity_matrix(self):
        with _McpClientForRole("member") as client:
            home = client.get("/entities", headers={"Authorization": f"Bearer {VALID_KEY}"}).json()
            shared = client.get(
                "/entities",
                headers={
                    "Authorization": f"Bearer {VALID_KEY}",
                    "X-Active-Workspace-Id": "shared-99",
                },
            ).json()

        home_ids = {e["id"] for e in home["entities"]}
        shared_ids = {e["id"] for e in shared["entities"]}

        assert home["workspace_context"]["is_home_workspace"] is True
        assert home["debug"]["workspace_role"] == "owner"
        assert home_ids == set(ENTITY_MAP.keys())

        assert shared["workspace_context"]["is_home_workspace"] is False
        assert shared["debug"]["workspace_role"] == "member"
        assert shared_ids == {
            "l1-a", "l2-a-public", "l2-a-restricted", "l1-b", "l2-b-public",
        }
        assert "l2-a-confidential" not in shared_ids

    @pytest.mark.parametrize(
        ("role", "expected_task_ids"),
        [
            ("guest", {"t-a-public", "t-a-restricted", "t-a-confidential"}),
            ("member", {"t-a-public", "t-a-restricted", "t-b-public", "t-unlinked"}),
        ],
    )
    def test_shared_workspace_task_matrix_for_guest_and_member(
        self,
        role: str,
        expected_task_ids: set[str],
    ):
        with _McpClientForRole(role) as client:
            shared = client.get(
                "/tasks",
                headers={
                    "Authorization": f"Bearer {VALID_KEY}",
                    "X-Active-Workspace-Id": "shared-99",
                },
            ).json()

        task_ids = {t["id"] for t in shared["tasks"]}
        assert shared["workspace_context"]["is_home_workspace"] is False
        assert shared["debug"]["workspace_role"] == role
        assert task_ids == expected_task_ids


@pytest.mark.asyncio
@pytest.mark.parametrize("role", ["guest", "member"])
async def test_dashboard_and_mcp_consistency_in_shared_workspace(role: str):
    """Cross-surface consistency: dashboard API and MCP agree for the same principal+workspace."""
    from zenos.interface.dashboard_api import list_entities as dashboard_list_entities
    from zenos.interface.dashboard_api import list_tasks as dashboard_list_tasks

    partner = _make_partner(role)

    with _McpClientForRole(role) as client:
        mcp_entities = client.get(
            "/entities",
            headers={
                "Authorization": f"Bearer {VALID_KEY}",
                "X-Active-Workspace-Id": "shared-99",
            },
        ).json()
        mcp_tasks = client.get(
            "/tasks",
            headers={
                "Authorization": f"Bearer {VALID_KEY}",
                "X-Active-Workspace-Id": "shared-99",
            },
        ).json()

    mcp_entity_ids = {e["id"] for e in mcp_entities["entities"]}
    mcp_task_ids = {t["id"] for t in mcp_tasks["tasks"]}

    request = _make_dashboard_request(
        headers={
            "authorization": "Bearer fake-token",
            "x-active-workspace-id": "shared-99",
        }
    )
    with (
        patch("zenos.interface.dashboard_api._verify_firebase_token", return_value={"email": partner["email"]}),
        patch("zenos.interface.dashboard_api._get_partner_by_email_sql", return_value=partner),
        patch("zenos.interface.dashboard_api._ensure_repos", new=AsyncMock(return_value=None)),
        patch("zenos.interface.dashboard_api._entity_repo") as mock_entity_repo,
        patch("zenos.interface.dashboard_api._task_repo") as mock_task_repo,
    ):
        mock_entity_repo.list_all = AsyncMock(return_value=ALL_ENTITIES)
        mock_entity_repo.get_by_id = AsyncMock(side_effect=lambda eid: ENTITY_MAP.get(eid))
        mock_task_repo.list_all = AsyncMock(return_value=ALL_TASKS)

        entities_resp = await dashboard_list_entities(request)
        tasks_resp = await dashboard_list_tasks(request)

    dashboard_entity_ids = {e["id"] for e in json.loads(entities_resp.body)["entities"]}
    dashboard_task_ids = {t["id"] for t in json.loads(tasks_resp.body)["tasks"]}

    assert mcp_entity_ids == dashboard_entity_ids
    assert mcp_task_ids == dashboard_task_ids
