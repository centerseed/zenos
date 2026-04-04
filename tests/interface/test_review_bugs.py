"""Tests confirming 3 bugs found in code review.

Bug 1: journal_write/journal_read accept empty partner_id without rejection
Bug 2: journal_read allows negative limit (produces invalid SQL)
Bug 3: list_tasks_by_entity doesn't pass allowed_ids for scoped partners
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from zenos.domain.models import Entity, Tags, Task

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_journal_repo(
    *,
    create_return: str = "uuid-1234",
    count_return: int = 1,
    list_recent_return: tuple | None = None,
) -> AsyncMock:
    repo = AsyncMock()
    repo.create = AsyncMock(return_value=create_return)
    repo.count = AsyncMock(return_value=count_return)
    repo.list_recent = AsyncMock(return_value=list_recent_return or ([], 0))
    return repo


def _make_entity(eid: str = "e1", level: int = 2, parent_id: str | None = None) -> Entity:
    return Entity(
        id=eid, name="Test", type="module", level=level,
        parent_id=parent_id, status="active", summary="s",
        tags=Tags(what=["x"], why="y", how="h", who=["w"]),
        details=None, confirmed_by_user=False, owner="Alice",
        sources=[], visibility="public", last_reviewed_at=None,
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )


def _make_task(tid: str = "t1", linked_entities: list | None = None) -> Task:
    return Task(
        id=tid, title="Fix it", description="desc",
        status="todo", priority="high",
        created_by="Alice", assignee="Bob",
        linked_entities=linked_entities or [],
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )


def _make_request(headers: dict | None = None, path_params: dict | None = None) -> MagicMock:
    req = MagicMock()
    req.method = "GET"
    req.headers = headers or {}
    req.path_params = path_params or {}
    req.query_params = {}
    return req


# ---------------------------------------------------------------------------
# Bug 1: journal_write/journal_read should reject empty partner_id
# ---------------------------------------------------------------------------


class TestJournalEmptyPartnerId:
    """journal tools should reject when partner_id is empty string."""

    async def test_journal_write_rejects_empty_partner_id(self):
        import zenos.interface.tools as tools

        repo = _make_journal_repo()
        with (
            patch.object(tools, "_journal_repo", repo),
            patch.object(tools, "_ensure_journal_repo", AsyncMock()),
            patch.object(tools, "_current_partner_id") as mock_pid,
            patch.object(tools, "datetime") as mock_dt,
        ):
            mock_pid.get.return_value = ""  # empty partner_id
            mock_dt.now.return_value = datetime(2026, 4, 4, tzinfo=timezone.utc)

            result = await tools.journal_write(summary="test")

        # Should be rejected, not ok
        assert result["status"] == "rejected", (
            "BUG: journal_write accepted empty partner_id — "
            "writes will go to partner_id='' mixing data across unauthenticated calls"
        )

    async def test_journal_read_rejects_empty_partner_id(self):
        import zenos.interface.tools as tools

        repo = _make_journal_repo()
        with (
            patch.object(tools, "_journal_repo", repo),
            patch.object(tools, "_ensure_journal_repo", AsyncMock()),
            patch.object(tools, "_current_partner_id") as mock_pid,
        ):
            mock_pid.get.return_value = ""  # empty partner_id

            result = await tools.journal_read()

        assert result["status"] == "rejected", (
            "BUG: journal_read accepted empty partner_id — "
            "could leak journal entries from other unauthenticated calls"
        )


# ---------------------------------------------------------------------------
# Bug 2: journal_read should clamp negative limit
# ---------------------------------------------------------------------------


class TestJournalNegativeLimit:
    """journal_read with negative limit should not produce invalid SQL."""

    async def test_journal_read_negative_limit_clamped_to_positive(self):
        import zenos.interface.tools as tools

        repo = _make_journal_repo()
        with (
            patch.object(tools, "_journal_repo", repo),
            patch.object(tools, "_ensure_journal_repo", AsyncMock()),
            patch.object(tools, "_current_partner_id") as mock_pid,
        ):
            mock_pid.get.return_value = "partner-1"

            await tools.journal_read(limit=-5)

        call_kwargs = repo.list_recent.call_args[1]
        assert call_kwargs["limit"] >= 1, (
            f"BUG: journal_read passed limit={call_kwargs['limit']} to repo — "
            "negative LIMIT produces invalid SQL in PostgreSQL"
        )


# ---------------------------------------------------------------------------
# Bug 3: list_tasks_by_entity doesn't pass allowed_ids for scoped partners
# ---------------------------------------------------------------------------


class TestListTasksByEntityScopedPartner:
    """Scoped partners should see tasks linked to entities in their scope."""

    async def test_scoped_partner_gets_empty_list_without_allowed_ids(self):
        """Demonstrates the bug: scoped partner always gets empty task list
        because _is_task_visible_for_partner is called without allowed_ids."""
        from zenos.interface.dashboard_api import list_tasks_by_entity

        # Scoped partner with authorizedEntityIds (not admin)
        scoped_partner = {
            "id": "p-scoped",
            "email": "client@test.com",
            "displayName": "Client",
            "authorizedEntityIds": ["e-root"],
            "isAdmin": False,
            "sharedPartnerId": "shared-1",
            "roles": [],
            "department": None,
            "status": "active",
        }

        # Entity e1 is a child of e-root (in scope)
        e_root = _make_entity("e-root", level=1)
        entity = _make_entity("e1", level=2, parent_id="e-root")
        # Task linked to e1 (should be visible to scoped partner)
        task = _make_task("t1", linked_entities=["e1"])

        request = _make_request(
            headers={"authorization": "Bearer fake-token"},
            path_params={"entityId": "e1"},
        )

        with (
            patch("zenos.interface.dashboard_api._verify_firebase_token",
                  return_value={"email": "client@test.com", "uid": "u1"}),
            patch("zenos.interface.dashboard_api._get_partner_by_email_sql",
                  return_value=scoped_partner),
            patch("zenos.interface.dashboard_api._ensure_repos"),
            patch("zenos.interface.dashboard_api._entity_repo") as mock_erepo,
            patch("zenos.interface.dashboard_api._task_repo") as mock_trepo,
            patch("zenos.interface.dashboard_api.current_partner_id") as mock_ctx,
            patch("zenos.interface.dashboard_api.OntologyService") as mock_osvc,
        ):
            mock_ctx.set = MagicMock(return_value="tok")
            mock_ctx.reset = MagicMock()
            mock_erepo.get_by_id = AsyncMock(return_value=entity)
            mock_erepo.list_all = AsyncMock(return_value=[e_root, entity])
            mock_trepo.list_all = AsyncMock(return_value=[task])
            mock_osvc.is_entity_visible_for_partner.return_value = True

            resp = await list_tasks_by_entity(request)

        body = json.loads(resp.body)
        # BUG: scoped partner should see t1 (linked to e1 which is in scope)
        # but gets empty list because allowed_ids is not passed
        assert len(body["tasks"]) > 0, (
            "BUG: scoped partner gets empty task list from list_tasks_by_entity — "
            "_is_task_visible_for_partner called without allowed_ids, "
            "so scoped partners always get False (line 174: if allowed_ids is None: return False)"
        )
