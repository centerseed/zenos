"""Guest mutation contract tests at MCP surface (ADR-030)."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

import zenos.interface.mcp as mcp
from zenos.application.action.task_service import TaskResult
from zenos.application.knowledge.ontology_service import UpsertEntityResult
from zenos.domain.action import Task
from zenos.domain.knowledge import Entity, Tags
from zenos.domain.shared import TagConfidence
from zenos.infrastructure.context import (
    current_partner_authorized_entity_ids,
    current_partner_department,
    current_partner_id,
    current_partner_is_admin,
    current_partner_roles,
)


def _guest_partner() -> dict:
    return {
        "id": "guest-home-1",
        "email": "guest@test.com",
        "displayName": "Guest",
        "status": "active",
        "isAdmin": False,
        "sharedPartnerId": "shared-99",
        "defaultProject": None,
        "roles": [],
        "department": "all",
        "workspaceRole": "guest",
        "accessMode": "scoped",
        "authorizedEntityIds": ["l1-a"],
    }


def _make_task(tid: str) -> Task:
    return Task(
        id=tid,
        title="Guest task",
        description="guest-created",
        status="todo",
        priority="medium",
        created_by="guest-home-1",
        updated_by="guest-home-1",
        product_id="l1-a",
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        updated_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
    )


def _make_entity(*, eid: str, entity_type: str, parent_id: str, visibility: str) -> Entity:
    return Entity(
        id=eid,
        name="Guest L3",
        type=entity_type,
        level=3,
        parent_id=parent_id,
        status="active",
        summary="guest-created",
        tags=Tags(what=["x"], why="y", how="z", who=["w"]),
        visibility=visibility,
        confirmed_by_user=False,
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        updated_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
    )


class _GuestSharedContext:
    def __init__(self):
        self.partner = _guest_partner()
        self._tokens = []

    def __enter__(self):
        from zenos.interface.mcp._auth import (
            _current_partner,
            _original_shared_partner_id,
            _raw_authenticated_partner,
        )

        self._tokens.append((_current_partner, _current_partner.set(dict(self.partner))))
        self._tokens.append((_raw_authenticated_partner, _raw_authenticated_partner.set(dict(self.partner))))
        self._tokens.append((_original_shared_partner_id, _original_shared_partner_id.set("shared-99")))
        self._tokens.append((current_partner_id, current_partner_id.set("shared-99")))
        self._tokens.append((current_partner_roles, current_partner_roles.set([])))
        self._tokens.append((current_partner_department, current_partner_department.set("all")))
        self._tokens.append((current_partner_is_admin, current_partner_is_admin.set(False)))
        self._tokens.append((current_partner_authorized_entity_ids, current_partner_authorized_entity_ids.set(["l1-a"])))
        return self

    def __exit__(self, exc_type, exc, tb):
        for var, token in reversed(self._tokens):
            var.reset(token)


@pytest.fixture(autouse=True)
def _mock_bootstrap():
    with (
        patch("zenos.interface.mcp._ensure_services", new=AsyncMock(return_value=None)),
        patch("zenos.interface.mcp.ontology_service", new=AsyncMock()),
        patch("zenos.interface.mcp.task_service", new=AsyncMock()),
        patch("zenos.interface.mcp.entity_repo", new=AsyncMock()),
    ):
        yield


@pytest.mark.asyncio
async def test_guest_can_create_task_in_shared_workspace():
    with _GuestSharedContext():
        mcp.task_service.create_task = AsyncMock(return_value=TaskResult(task=_make_task("task-guest"), cascade_updates=[]))
        mcp.task_service.enrich_task = AsyncMock(return_value={"expanded_entities": []})

        result = await mcp.task(action="create", title="Create guest task", product_id="l1-a")

    assert result["status"] == "ok"
    assert result["data"]["id"] == "task-guest"
    assert result["workspace_context"]["workspace_id"] == "shared-99"


@pytest.mark.asyncio
async def test_guest_can_create_l3_and_write_back_to_active_workspace_with_public_visibility():
    observed_workspace: dict[str, str | None] = {"id": None}

    async def _upsert_entity(data: dict, partner: dict | None = None):
        observed_workspace["id"] = current_partner_id.get()
        assert partner is not None
        assert partner.get("workspaceRole") == "guest"
        assert data["parent_id"] == "l2-auth"
        return UpsertEntityResult(
            entity=_make_entity(
                eid="l3-guest-1",
                entity_type="goal",
                parent_id="l2-auth",
                visibility="public",
            ),
            tag_confidence=TagConfidence(confirmed_fields=[], draft_fields=[]),
            split_recommendation=None,
            warnings=[],
        )

    with _GuestSharedContext():
        mcp.entity_repo.get_by_name = AsyncMock(return_value=None)
        mcp.entity_repo.get_by_id = AsyncMock(return_value=None)
        mcp.ontology_service.upsert_entity = AsyncMock(side_effect=_upsert_entity)

        result = await mcp.write(
            collection="entities",
            data={
                "name": "Guest L3",
                "type": "goal",
                "parent_id": "l2-auth",
                "summary": "Guest creates L3",
                "visibility": "restricted",
                "tags": {"what": "x", "why": "y", "how": "z", "who": "w"},
            },
        )

    assert result["status"] == "ok"
    assert result["data"]["entity"]["visibility"] == "public"
    assert result["workspace_context"]["workspace_id"] == "shared-99"
    assert observed_workspace["id"] == "shared-99"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("entity_type", "error_message"),
    [
        ("product", "Guest partners cannot create L1 entities"),
        ("module", "Guest partners cannot create L2 entities"),
    ],
)
async def test_guest_cannot_create_l1_or_l2(entity_type: str, error_message: str):
    with _GuestSharedContext():
        mcp.entity_repo.get_by_name = AsyncMock(return_value=None)
        mcp.entity_repo.get_by_id = AsyncMock(return_value=None)
        mcp.ontology_service.upsert_entity = AsyncMock(
            side_effect=PermissionError(error_message)
        )

        result = await mcp.write(
            collection="entities",
            data={
                "name": f"Guest {entity_type}",
                "type": entity_type,
                "summary": "not allowed",
                "tags": {"what": "x", "why": "y", "how": "z", "who": "w"},
            },
        )

    assert result["status"] == "rejected"
    assert error_message in result["rejection_reason"]


@pytest.mark.asyncio
async def test_guest_cannot_write_after_switching_to_unauthorized_workspace():
    with _GuestSharedContext():
        mcp.entity_repo.get_by_name = AsyncMock(return_value=None)
        mcp.entity_repo.get_by_id = AsyncMock(return_value=None)
        mcp.ontology_service.upsert_entity = AsyncMock()

        result = await mcp.write(
            collection="entities",
            data={
                "name": "Guest unauthorized write",
                "type": "goal",
                "parent_id": "l2-auth",
                "summary": "should fail",
                "tags": {"what": "x", "why": "y", "how": "z", "who": "w"},
            },
            workspace_id="evil-workspace",
        )

    assert result["status"] == "error"
    assert result["data"]["error"] == "FORBIDDEN_WORKSPACE"
    mcp.ontology_service.upsert_entity.assert_not_called()
