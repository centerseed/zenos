"""Backend tests for task comment endpoints (Dashboard API).

Tests:
  - test_list_comments_requires_task_access
  - test_create_comment_success
  - test_delete_comment_own
  - test_delete_comment_by_admin
  - test_delete_comment_by_other_user
  - test_delete_comment_wrong_task

All tests use mock patches to avoid real DB/Firebase calls.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from zenos.domain.models import Entity, Tags, Task


# ---------------------------------------------------------------------------
# Shared test data helpers
# ---------------------------------------------------------------------------

def _make_entity(**overrides) -> Entity:
    defaults = dict(
        id="ent-pub",
        name="PublicEntity",
        type="product",
        level=1,
        parent_id=None,
        status="active",
        summary="A public entity",
        tags=Tags(what=["x"], why="y", how="z", who=["dev"]),
        details=None,
        confirmed_by_user=True,
        owner="Alice",
        sources=[],
        visibility="public",
        last_reviewed_at=None,
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        updated_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
    )
    defaults.update(overrides)
    return Entity(**defaults)


def _make_task(**overrides) -> Task:
    defaults = dict(
        id="task-abc",
        title="Sample Task",
        description="A task for testing",
        status="todo",
        priority="medium",
        created_by="p-author",
        assignee=None,
        linked_entities=["ent-pub"],
        created_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
        updated_at=datetime(2026, 3, 20, tzinfo=timezone.utc),
    )
    defaults.update(overrides)
    return Task(**defaults)


def _make_comment(**overrides) -> dict:
    defaults = dict(
        id="comment-1",
        task_id="task-abc",
        partner_id="p-author",
        content="Hello world",
        author_name="Author Name",
        created_at="2026-04-01T10:00:00+00:00",
    )
    defaults.update(overrides)
    return defaults


def _make_request(method="GET", headers=None, query_params=None, path_params=None, body=None):
    req = MagicMock()
    req.method = method
    req.headers = headers or {"authorization": "Bearer fake-token"}
    req.query_params = query_params or {}
    req.path_params = path_params or {}
    if body is not None:
        req.json = AsyncMock(return_value=body)
    return req


# Shared partner fixtures
ADMIN_PARTNER = {
    "id": "p-admin",
    "email": "admin@test.com",
    "displayName": "Admin",
    "isAdmin": True,
    "sharedPartnerId": None,
    "status": "active",
    "roles": [],
    "department": "all",
    "authorizedEntityIds": [],
}

REGULAR_PARTNER = {
    "id": "p-author",
    "email": "author@test.com",
    "displayName": "Author",
    "isAdmin": False,
    "sharedPartnerId": None,
    "status": "active",
    "roles": [],
    "department": "all",
    "authorizedEntityIds": [],
}

OTHER_PARTNER = {
    "id": "p-other",
    "email": "other@test.com",
    "displayName": "Other User",
    "isAdmin": False,
    "sharedPartnerId": None,
    "status": "active",
    "roles": [],
    "department": "all",
    "authorizedEntityIds": [],
}

# Scoped partner that is NOT authorized for "ent-pub"
SCOPED_UNAUTHORIZED = {
    "id": "p-client-outside",
    "email": "outsider@external.com",
    "displayName": "Outside Client",
    "isAdmin": False,
    "sharedPartnerId": None,
    "status": "active",
    "roles": [],
    "department": "all",
    "authorizedEntityIds": ["product-other"],
}

# L1 product entity for scoped partner tests
L1_OTHER = _make_entity(id="product-other", name="Other Product", type="product", level=1, visibility="public")
SCOPED_ALL_ENTITIES = [L1_OTHER]
SCOPED_ENTITY_MAP = {e.id: e for e in SCOPED_ALL_ENTITIES}

# Task linked to "ent-pub", which is NOT in "product-other" subtree
TASK_IN_PUB = _make_task(id="task-abc", linked_entities=["ent-pub"])


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestListComments:

    async def test_list_comments_requires_task_access(self):
        """Scoped partner cannot list comments on a task outside their authorized L1."""
        from zenos.interface.dashboard_api import list_comments

        request = _make_request(path_params={"taskId": "task-abc"})

        with patch("zenos.interface.dashboard_api._verify_firebase_token", return_value={"email": "outsider@external.com"}), \
             patch("zenos.interface.dashboard_api._get_partner_by_email_sql", return_value=SCOPED_UNAUTHORIZED), \
             patch("zenos.interface.dashboard_api._ensure_repos", new=AsyncMock()), \
             patch("zenos.interface.dashboard_api._task_repo") as mock_task_repo, \
             patch("zenos.interface.dashboard_api._entity_repo") as mock_entity_repo, \
             patch("zenos.interface.dashboard_api._comment_repo") as mock_comment_repo:
            mock_task_repo.get_by_id = AsyncMock(return_value=TASK_IN_PUB)
            mock_entity_repo.list_all = AsyncMock(return_value=SCOPED_ALL_ENTITIES)
            mock_comment_repo.list_by_task = AsyncMock(return_value=[])

            resp = await list_comments(request)

        assert resp.status_code == 404, "Scoped partner with no access to task should get 404"
        # Comments should NOT have been fetched
        mock_comment_repo.list_by_task.assert_not_called()

    async def test_list_comments_success_for_authorized_partner(self):
        """Internal (non-scoped) partner can list comments on a visible task."""
        from zenos.interface.dashboard_api import list_comments

        request = _make_request(path_params={"taskId": "task-abc"})
        comment = _make_comment()

        with patch("zenos.interface.dashboard_api._verify_firebase_token", return_value={"email": "author@test.com"}), \
             patch("zenos.interface.dashboard_api._get_partner_by_email_sql", return_value=REGULAR_PARTNER), \
             patch("zenos.interface.dashboard_api._ensure_repos", new=AsyncMock()), \
             patch("zenos.interface.dashboard_api._task_repo") as mock_task_repo, \
             patch("zenos.interface.dashboard_api._entity_repo") as mock_entity_repo, \
             patch("zenos.interface.dashboard_api._comment_repo") as mock_comment_repo:
            mock_task_repo.get_by_id = AsyncMock(return_value=TASK_IN_PUB)
            mock_entity_repo.get_by_id = AsyncMock(return_value=_make_entity())
            mock_comment_repo.list_by_task = AsyncMock(return_value=[comment])

            resp = await list_comments(request)

        assert resp.status_code == 200
        body = json.loads(resp.body)
        assert len(body["comments"]) == 1
        assert body["comments"][0]["id"] == "comment-1"


@pytest.mark.asyncio
class TestCreateComment:

    async def test_create_comment_success(self):
        """Authorized partner can create a comment; returns 201 with comment dict."""
        from zenos.interface.dashboard_api import create_comment

        request = _make_request(
            method="POST",
            path_params={"taskId": "task-abc"},
            body={"content": "New comment text"},
        )
        comment = _make_comment(content="New comment text")

        with patch("zenos.interface.dashboard_api._verify_firebase_token", return_value={"email": "author@test.com"}), \
             patch("zenos.interface.dashboard_api._get_partner_by_email_sql", return_value=REGULAR_PARTNER), \
             patch("zenos.interface.dashboard_api._ensure_repos", new=AsyncMock()), \
             patch("zenos.interface.dashboard_api._task_repo") as mock_task_repo, \
             patch("zenos.interface.dashboard_api._entity_repo") as mock_entity_repo, \
             patch("zenos.interface.dashboard_api._comment_repo") as mock_comment_repo:
            mock_task_repo.get_by_id = AsyncMock(return_value=TASK_IN_PUB)
            mock_entity_repo.get_by_id = AsyncMock(return_value=_make_entity())
            mock_comment_repo.create = AsyncMock(return_value=comment)

            resp = await create_comment(request)

        assert resp.status_code == 201
        body = json.loads(resp.body)
        assert body["comment"]["content"] == "New comment text"
        mock_comment_repo.create.assert_called_once_with(
            task_id="task-abc",
            partner_id="p-author",
            content="New comment text",
        )

    async def test_create_comment_empty_content_rejected(self):
        """Empty content should return 400."""
        from zenos.interface.dashboard_api import create_comment

        request = _make_request(
            method="POST",
            path_params={"taskId": "task-abc"},
            body={"content": "   "},
        )

        with patch("zenos.interface.dashboard_api._verify_firebase_token", return_value={"email": "author@test.com"}), \
             patch("zenos.interface.dashboard_api._get_partner_by_email_sql", return_value=REGULAR_PARTNER), \
             patch("zenos.interface.dashboard_api._ensure_repos", new=AsyncMock()), \
             patch("zenos.interface.dashboard_api._task_repo") as mock_task_repo, \
             patch("zenos.interface.dashboard_api._entity_repo") as mock_entity_repo, \
             patch("zenos.interface.dashboard_api._comment_repo"):
            mock_task_repo.get_by_id = AsyncMock(return_value=TASK_IN_PUB)
            mock_entity_repo.get_by_id = AsyncMock(return_value=_make_entity())

            resp = await create_comment(request)

        assert resp.status_code == 400


@pytest.mark.asyncio
class TestDeleteComment:

    async def test_delete_comment_own(self):
        """Comment author can delete their own comment; returns 204."""
        from zenos.interface.dashboard_api import delete_comment

        request = _make_request(
            method="DELETE",
            path_params={"taskId": "task-abc", "commentId": "comment-1"},
        )
        comment = _make_comment(partner_id="p-author")

        with patch("zenos.interface.dashboard_api._verify_firebase_token", return_value={"email": "author@test.com"}), \
             patch("zenos.interface.dashboard_api._get_partner_by_email_sql", return_value=REGULAR_PARTNER), \
             patch("zenos.interface.dashboard_api._ensure_repos", new=AsyncMock()), \
             patch("zenos.interface.dashboard_api._task_repo") as mock_task_repo, \
             patch("zenos.interface.dashboard_api._entity_repo") as mock_entity_repo, \
             patch("zenos.interface.dashboard_api._comment_repo") as mock_comment_repo:
            mock_task_repo.get_by_id = AsyncMock(return_value=TASK_IN_PUB)
            mock_entity_repo.get_by_id = AsyncMock(return_value=_make_entity())
            mock_comment_repo.get_by_id = AsyncMock(return_value=comment)
            mock_comment_repo.delete = AsyncMock(return_value=True)

            resp = await delete_comment(request)

        assert resp.status_code == 204
        mock_comment_repo.delete.assert_called_once_with("comment-1")

    async def test_delete_comment_by_admin(self):
        """Admin can delete any comment, regardless of authorship."""
        from zenos.interface.dashboard_api import delete_comment

        request = _make_request(
            method="DELETE",
            path_params={"taskId": "task-abc", "commentId": "comment-1"},
        )
        # Comment belongs to "p-author", but admin ("p-admin") is deleting it
        comment = _make_comment(partner_id="p-author")

        with patch("zenos.interface.dashboard_api._verify_firebase_token", return_value={"email": "admin@test.com"}), \
             patch("zenos.interface.dashboard_api._get_partner_by_email_sql", return_value=ADMIN_PARTNER), \
             patch("zenos.interface.dashboard_api._ensure_repos", new=AsyncMock()), \
             patch("zenos.interface.dashboard_api._task_repo") as mock_task_repo, \
             patch("zenos.interface.dashboard_api._entity_repo") as mock_entity_repo, \
             patch("zenos.interface.dashboard_api._comment_repo") as mock_comment_repo:
            mock_task_repo.get_by_id = AsyncMock(return_value=TASK_IN_PUB)
            mock_entity_repo.get_by_id = AsyncMock(return_value=_make_entity())
            mock_comment_repo.get_by_id = AsyncMock(return_value=comment)
            mock_comment_repo.delete = AsyncMock(return_value=True)

            resp = await delete_comment(request)

        assert resp.status_code == 204
        mock_comment_repo.delete.assert_called_once_with("comment-1")

    async def test_delete_comment_by_other_user(self):
        """Non-author non-admin gets 403 when trying to delete another user's comment."""
        from zenos.interface.dashboard_api import delete_comment

        request = _make_request(
            method="DELETE",
            path_params={"taskId": "task-abc", "commentId": "comment-1"},
        )
        # Comment belongs to "p-author", but "p-other" is trying to delete it
        comment = _make_comment(partner_id="p-author")

        with patch("zenos.interface.dashboard_api._verify_firebase_token", return_value={"email": "other@test.com"}), \
             patch("zenos.interface.dashboard_api._get_partner_by_email_sql", return_value=OTHER_PARTNER), \
             patch("zenos.interface.dashboard_api._ensure_repos", new=AsyncMock()), \
             patch("zenos.interface.dashboard_api._task_repo") as mock_task_repo, \
             patch("zenos.interface.dashboard_api._entity_repo") as mock_entity_repo, \
             patch("zenos.interface.dashboard_api._comment_repo") as mock_comment_repo:
            mock_task_repo.get_by_id = AsyncMock(return_value=TASK_IN_PUB)
            mock_entity_repo.get_by_id = AsyncMock(return_value=_make_entity())
            mock_comment_repo.get_by_id = AsyncMock(return_value=comment)
            mock_comment_repo.delete = AsyncMock()

            resp = await delete_comment(request)

        assert resp.status_code == 403
        mock_comment_repo.delete.assert_not_called()

    async def test_delete_comment_wrong_task(self):
        """Comment exists but belongs to a different task → 404 (prevents lateral access)."""
        from zenos.interface.dashboard_api import delete_comment

        request = _make_request(
            method="DELETE",
            # URL says task-abc, but the comment's task_id is task-xyz
            path_params={"taskId": "task-abc", "commentId": "comment-1"},
        )
        comment = _make_comment(partner_id="p-admin", task_id="task-xyz")

        with patch("zenos.interface.dashboard_api._verify_firebase_token", return_value={"email": "admin@test.com"}), \
             patch("zenos.interface.dashboard_api._get_partner_by_email_sql", return_value=ADMIN_PARTNER), \
             patch("zenos.interface.dashboard_api._ensure_repos", new=AsyncMock()), \
             patch("zenos.interface.dashboard_api._task_repo") as mock_task_repo, \
             patch("zenos.interface.dashboard_api._entity_repo") as mock_entity_repo, \
             patch("zenos.interface.dashboard_api._comment_repo") as mock_comment_repo:
            mock_task_repo.get_by_id = AsyncMock(return_value=TASK_IN_PUB)
            mock_entity_repo.get_by_id = AsyncMock(return_value=_make_entity())
            mock_comment_repo.get_by_id = AsyncMock(return_value=comment)
            mock_comment_repo.delete = AsyncMock()

            resp = await delete_comment(request)

        assert resp.status_code == 404
        mock_comment_repo.delete.assert_not_called()


# ---------------------------------------------------------------------------
# Repository unit tests (mock asyncpg pool)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestPostgresTaskCommentRepositoryCreate:
    """Unit tests for PostgresTaskCommentRepository.create() using a mock pool.

    These tests verify that:
      1. create() returns author_name from the partners table (not just partner_id).
      2. create() falls back to partner_id when the partner row is not found.
    """

    def _make_pool(self, insert_row, author_row):
        """Build a mock asyncpg pool that simulates fetchrow calls in sequence."""
        conn = AsyncMock()
        conn.fetchrow = AsyncMock(side_effect=[insert_row, author_row])
        pool = MagicMock()
        pool.acquire = MagicMock()
        pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
        pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)
        return pool

    async def test_create_returns_author_name_from_partners(self):
        """create() fetches display_name from partners and includes it as author_name."""
        from datetime import datetime, timezone
        from zenos.infrastructure.sql_repo import PostgresTaskCommentRepository

        insert_row = {
            "id": "uuid-comment-1",
            "task_id": "uuid-task-1",
            "partner_id": "p-alice",
            "content": "Hello",
            "created_at": datetime(2026, 4, 1, tzinfo=timezone.utc),
        }
        author_row = {"display_name": "Alice"}

        pool = self._make_pool(insert_row, author_row)
        repo = PostgresTaskCommentRepository(pool)

        result = await repo.create(task_id="uuid-task-1", partner_id="p-alice", content="Hello")

        assert result["author_name"] == "Alice"
        assert result["partner_id"] == "p-alice"
        assert result["content"] == "Hello"

    async def test_create_falls_back_to_partner_id_when_partner_not_found(self):
        """create() uses partner_id as author_name when partner row is missing."""
        from datetime import datetime, timezone
        from zenos.infrastructure.sql_repo import PostgresTaskCommentRepository

        insert_row = {
            "id": "uuid-comment-2",
            "task_id": "uuid-task-1",
            "partner_id": "p-ghost",
            "content": "Boo",
            "created_at": datetime(2026, 4, 1, tzinfo=timezone.utc),
        }
        # Simulates partner not found (fetchrow returns None)
        author_row = None

        pool = self._make_pool(insert_row, author_row)
        repo = PostgresTaskCommentRepository(pool)

        result = await repo.create(task_id="uuid-task-1", partner_id="p-ghost", content="Boo")

        assert result["author_name"] == "p-ghost"


@pytest.mark.asyncio
class TestPostgresTaskCommentRepositoryListByTask:
    """Unit tests for PostgresTaskCommentRepository.list_by_task().

    These tests verify that the JOIN uses partners.id (not partners.uid) by
    checking that the SQL query string passed to conn.fetch contains 'p.id'.
    """

    async def test_list_by_task_join_uses_partners_id(self):
        """list_by_task() SQL must JOIN partners on p.id, not p.uid."""
        from zenos.infrastructure.sql_repo import PostgresTaskCommentRepository

        conn = AsyncMock()
        conn.fetch = AsyncMock(return_value=[])
        pool = MagicMock()
        pool.acquire = MagicMock()
        pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
        pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

        repo = PostgresTaskCommentRepository(pool)
        await repo.list_by_task("task-abc")

        # Verify the SQL used the correct join key
        call_args = conn.fetch.call_args
        sql: str = call_args[0][0]
        assert "p.id" in sql, f"Expected 'p.id' in SQL but got: {sql}"
        assert "p.uid" not in sql, f"Unexpected 'p.uid' found in SQL: {sql}"
