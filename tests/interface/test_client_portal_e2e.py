"""End-to-end integration tests for the Client Portal — complete client onboarding flow.

Covers the full permission boundary from invite → activate → scoped data access.
Each test represents a P0 acceptance criterion from SPEC-client-portal and
SPEC-permission-model.

Test approach:
- Uses unittest.mock (no real DB or network calls).
- Fixtures and mock patterns are consistent with test_permission_isolation.py.
- API key strings are marked with # pragma: allowlist secret.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from zenos.domain.models import Blindspot, Entity, Tags, Task


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _make_entity(**overrides) -> Entity:
    defaults = dict(
        id="ent-pub",
        name="Public Module",
        type="module",
        level=2,
        parent_id="l1-entity-id",
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
        id="task-1",
        title="Fix login",
        description="Login is broken",
        status="todo",
        priority="high",
        created_by="architect",
        assignee="dev",
        created_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
        updated_at=datetime(2026, 3, 20, tzinfo=timezone.utc),
    )
    defaults.update(overrides)
    return Task(**defaults)


def _make_blindspot(**overrides) -> Blindspot:
    defaults = dict(
        id="bs-1",
        description="No monitoring",
        severity="red",
        related_entity_ids=["ent-pub"],
        suggested_action="Add monitoring",
        status="open",
        confirmed_by_user=False,
        created_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
    )
    defaults.update(overrides)
    return Blindspot(**defaults)


def _mock_request(
    method: str = "GET",
    headers: dict | None = None,
    body: dict | None = None,
    path_params: dict | None = None,
    query_params: dict | None = None,
) -> MagicMock:
    """Create a mock Starlette Request."""
    req = MagicMock()
    req.method = method
    req.headers = headers or {}
    req.path_params = path_params or {}
    req.query_params = query_params or {}

    async def json_coro():
        return body or {}

    req.json = json_coro
    return req


def _firebase_token(email: str = "admin@test.com", name: str = "Admin") -> dict:
    return {"email": email, "name": name, "uid": "uid-e2e"}


# ---------------------------------------------------------------------------
# Test data — L1 scoped partner scenario
# ---------------------------------------------------------------------------

# L1 entity that client is authorized for
L1_ALLOWED = _make_entity(
    id="l1-entity-id",
    name="Acme Project",
    type="product",
    level=1,
    parent_id=None,
    visibility="public",
)

# Child entity inside allowed L1
CHILD_IN_L1 = _make_entity(
    id="ent-child-allowed",
    name="Module Alpha",
    type="module",
    level=2,
    parent_id="l1-entity-id",
    visibility="public",
)

# Child entity inside allowed L1 with visibility=restricted
RESTRICTED_IN_L1 = _make_entity(
    id="ent-restricted-in-l1",
    name="Internal Finance",
    type="module",
    level=2,
    parent_id="l1-entity-id",
    visibility="restricted",
)

# Another L1 the client is NOT authorized for
L1_OTHER = _make_entity(
    id="other-l1-id",
    name="Other Project",
    type="product",
    level=1,
    parent_id=None,
    visibility="public",
)

# Entity inside the unauthorized L1
OTHER_ENTITY = _make_entity(
    id="ent-other",
    name="Other Module",
    type="module",
    level=2,
    parent_id="other-l1-id",
    visibility="public",
)

ALL_ENTITIES = [L1_ALLOWED, CHILD_IN_L1, RESTRICTED_IN_L1, L1_OTHER, OTHER_ENTITY]
ENTITY_MAP = {e.id: e for e in ALL_ENTITIES}

# Task linked to entity in authorized L1
TASK_IN_L1 = _make_task(
    id="task-in-l1",
    title="Build login page",
    linked_entities=["ent-child-allowed"],
)

# Task linked to restricted entity (still inside allowed L1)
TASK_LINKED_RESTRICTED = _make_task(
    id="task-linked-restricted",
    title="Finance report",
    linked_entities=["ent-restricted-in-l1"],
)

# Task linked to entity outside allowed L1
TASK_OUT_L1 = _make_task(
    id="task-out-l1",
    title="Other project task",
    linked_entities=["ent-other"],
)

ALL_TASKS = [TASK_IN_L1, TASK_LINKED_RESTRICTED, TASK_OUT_L1]

# Blindspot data
BS_IN_L1 = _make_blindspot(id="bs-in-l1", related_entity_ids=["ent-child-allowed"])
BS_OTHER = _make_blindspot(id="bs-other", related_entity_ids=["ent-other"])

ALL_BLINDSPOTS = [BS_IN_L1, BS_OTHER]

# Scoped partner (external client)
SCOPED_CLIENT = {
    "id": "p-client-e2e",
    "email": "client@acme.com",
    "displayName": "Acme Client",
    "apiKey": "key-client-portal-test",  # pragma: allowlist secret
    "status": "active",
    "isAdmin": False,
    "sharedPartnerId": "p-admin-e2e",
    "defaultProject": None,
    "roles": [],
    "department": "all",
    "authorizedEntityIds": ["l1-entity-id"],
}

ADMIN_PARTNER = {
    "id": "p-admin-e2e",
    "email": "admin@zenos.com",
    "displayName": "Admin",
    "apiKey": "key-admin-e2e",  # pragma: allowlist secret
    "status": "active",
    "isAdmin": True,
    "sharedPartnerId": None,
    "defaultProject": None,
    "roles": [],
    "department": "all",
    "authorizedEntityIds": None,
}


async def _entity_get_by_id(eid: str):
    return ENTITY_MAP.get(eid)


# ===========================================================================
# E2E Scenario 1: 邀請流程（Invite Flow）
# ===========================================================================

@pytest.mark.asyncio
class TestInviteFlowE2E:
    """E2E: Admin invites external email with authorized_entity_ids."""

    async def test_admin_invite_creates_partner_with_l1_scope(self):
        """Admin invites external email → partner record has correct L1 scope and status.

        Verifies:
        - Response contains inviteExpiresAt (not None).
        - Partner record authorizedEntityIds == ["l1-entity-id"].
        - Partner status == "invited".
        """
        from zenos.interface.admin_api import invite_partner

        request = _mock_request(
            method="POST",
            headers={"authorization": "Bearer fake-token"},
            body={
                "email": "new-client@acme.com",
                "authorized_entity_ids": ["l1-entity-id"],
            },
        )

        mock_repo = AsyncMock()
        mock_repo.create = AsyncMock(return_value=None)

        with patch("zenos.interface.admin_api._verify_firebase_token", return_value=_firebase_token()), \
             patch("zenos.interface.admin_api._get_caller_partner", return_value=("p-admin-e2e", ADMIN_PARTNER)), \
             patch("zenos.interface.admin_api._get_partner_by_email", return_value=(None, None)), \
             patch("zenos.interface.admin_api._ensure_partner_repo", new_callable=AsyncMock, return_value=mock_repo):

            resp = await invite_partner(request)

        assert resp.status_code == 201
        body = json.loads(resp.body)

        assert body["email"] == "new-client@acme.com"
        assert body["status"] == "invited", "Newly invited partner must have status=invited"
        assert body["authorizedEntityIds"] == ["l1-entity-id"], "Scope must match requested L1"
        assert body.get("inviteExpiresAt") is not None, "inviteExpiresAt must be set on invite"

    async def test_invite_expires_at_is_roughly_7_days(self):
        """Invite expiry is approximately 7 days from now."""
        from zenos.interface.admin_api import invite_partner

        request = _mock_request(
            method="POST",
            headers={"authorization": "Bearer fake-token"},
            body={"email": "another-client@acme.com", "authorized_entity_ids": ["l1-entity-id"]},
        )

        mock_repo = AsyncMock()
        mock_repo.create = AsyncMock(return_value=None)

        with patch("zenos.interface.admin_api._verify_firebase_token", return_value=_firebase_token()), \
             patch("zenos.interface.admin_api._get_caller_partner", return_value=("p-admin-e2e", ADMIN_PARTNER)), \
             patch("zenos.interface.admin_api._get_partner_by_email", return_value=(None, None)), \
             patch("zenos.interface.admin_api._ensure_partner_repo", new_callable=AsyncMock, return_value=mock_repo):

            before = datetime.now(timezone.utc)
            resp = await invite_partner(request)
            after = datetime.now(timezone.utc)

        body = json.loads(resp.body)
        expires_str = body["inviteExpiresAt"]
        expires_at = datetime.fromisoformat(expires_str.replace("Z", "+00:00"))

        assert before + timedelta(days=6, hours=23) <= expires_at <= after + timedelta(days=7, seconds=5), (
            f"inviteExpiresAt should be ~7 days from now, got {expires_str}"
        )


# ===========================================================================
# E2E Scenario 2: 過期邀請 activate
# ===========================================================================

@pytest.mark.asyncio
class TestExpiredInviteE2E:
    """E2E: Activating an expired invite returns 410 INVITATION_EXPIRED."""

    async def test_activate_expired_invite_returns_410(self):
        """When invite_expires_at is in the past, activate returns 410 + INVITATION_EXPIRED.

        Verifies the SPEC-client-portal acceptance criterion:
        "邀請連結已過期（超過 7 天），When 外部用戶點擊，Then 顯示過期提示"
        """
        from zenos.interface.admin_api import activate_partner

        request = _mock_request(
            method="POST",
            headers={"authorization": "Bearer fake-token"},
        )

        expired_partner = {
            "email": "expired@acme.com",
            "status": "invited",
            "displayName": "expired@acme.com",
            "inviteExpiresAt": datetime.now(timezone.utc) - timedelta(days=8),  # already expired
        }

        with patch("zenos.interface.admin_api._verify_firebase_token", return_value=_firebase_token(email="expired@acme.com")), \
             patch("zenos.interface.admin_api._get_partner_by_email", return_value=("p-expired", expired_partner)):

            resp = await activate_partner(request)

        assert resp.status_code == 410, "Expired invite must return HTTP 410 Gone"
        body = json.loads(resp.body)
        assert body["error"] == "INVITATION_EXPIRED", "Error code must be INVITATION_EXPIRED"


# ===========================================================================
# E2E Scenario 3: L1 scope 隔離 — list_entities
# ===========================================================================

@pytest.mark.asyncio
class TestL1ScopeEntityListE2E:
    """E2E: Scoped partner list_entities only sees entities in authorized L1 subtree."""

    async def test_list_entities_returns_only_allowed_l1_subtree(self):
        """GET /api/data/entities returns only the authorized L1 and its public children.

        Verifies:
        - L1_ALLOWED ("l1-entity-id") is in result.
        - CHILD_IN_L1 ("ent-child-allowed") is in result.
        - L1_OTHER ("other-l1-id") is NOT in result.
        - OTHER_ENTITY ("ent-other") is NOT in result.
        - RESTRICTED_IN_L1 ("ent-restricted-in-l1") is NOT in result (visibility restriction).
        """
        from zenos.interface.dashboard_api import list_entities

        request = _mock_request(headers={"authorization": "Bearer fake"})

        with patch("zenos.interface.dashboard_api._verify_firebase_token", return_value={"email": "client@acme.com"}), \
             patch("zenos.interface.dashboard_api._get_partner_by_email_sql", return_value=SCOPED_CLIENT), \
             patch("zenos.interface.dashboard_api._ensure_repos", new=AsyncMock()), \
             patch("zenos.interface.dashboard_api._entity_repo") as mock_entity_repo:
            mock_entity_repo.list_all = AsyncMock(return_value=ALL_ENTITIES)
            resp = await list_entities(request)

        body = json.loads(resp.body)
        entity_ids = [e["id"] for e in body["entities"]]

        assert "l1-entity-id" in entity_ids, "Authorized L1 root must be visible"
        assert "ent-child-allowed" in entity_ids, "Public child of authorized L1 must be visible"
        assert "other-l1-id" not in entity_ids, "Unauthorized L1 must not be visible"
        assert "ent-other" not in entity_ids, "Entity in unauthorized L1 must not be visible"
        assert "ent-restricted-in-l1" not in entity_ids, "Restricted entity must not be visible to scoped partner"


# ===========================================================================
# E2E Scenario 4: L1 scope 隔離 — get_entity 越界
# ===========================================================================

@pytest.mark.asyncio
class TestL1ScopeGetEntityOutOfBoundsE2E:
    """E2E: Scoped partner accessing out-of-scope entity via GET /api/data/entities/{id} returns 404."""

    async def test_get_entity_outside_scope_returns_404(self):
        """GET /api/data/entities/{other-l1-id} returns 404 for scoped partner.

        Per SPEC-permission-model: "存取其他 L1 資源時回傳空結果（非 403），
        以免暴露 L1 存在" — implemented as 404 NOT_FOUND.
        """
        from zenos.interface.dashboard_api import get_entity

        request = _mock_request(
            headers={"authorization": "Bearer fake"},
            path_params={"id": "other-l1-id"},
        )

        with patch("zenos.interface.dashboard_api._verify_firebase_token", return_value={"email": "client@acme.com"}), \
             patch("zenos.interface.dashboard_api._get_partner_by_email_sql", return_value=SCOPED_CLIENT), \
             patch("zenos.interface.dashboard_api._ensure_repos", new=AsyncMock()), \
             patch("zenos.interface.dashboard_api._entity_repo") as mock_entity_repo:
            mock_entity_repo.get_by_id = AsyncMock(return_value=L1_OTHER)
            mock_entity_repo.list_all = AsyncMock(return_value=ALL_ENTITIES)
            resp = await get_entity(request)

        assert resp.status_code == 404, "Out-of-scope entity must return 404 to avoid L1 leakage"
        body = json.loads(resp.body)
        assert body["error"] == "NOT_FOUND"

    async def test_get_entity_inside_scope_returns_200(self):
        """GET /api/data/entities/{ent-child-allowed} returns 200 for scoped partner.

        Sanity check: valid in-scope access must succeed.
        """
        from zenos.interface.dashboard_api import get_entity

        request = _mock_request(
            headers={"authorization": "Bearer fake"},
            path_params={"id": "ent-child-allowed"},
        )

        with patch("zenos.interface.dashboard_api._verify_firebase_token", return_value={"email": "client@acme.com"}), \
             patch("zenos.interface.dashboard_api._get_partner_by_email_sql", return_value=SCOPED_CLIENT), \
             patch("zenos.interface.dashboard_api._ensure_repos", new=AsyncMock()), \
             patch("zenos.interface.dashboard_api._entity_repo") as mock_entity_repo:
            mock_entity_repo.get_by_id = AsyncMock(return_value=CHILD_IN_L1)
            mock_entity_repo.list_all = AsyncMock(return_value=ALL_ENTITIES)
            resp = await get_entity(request)

        assert resp.status_code == 200
        body = json.loads(resp.body)
        assert body["entity"]["id"] == "ent-child-allowed"


# ===========================================================================
# E2E Scenario 5: Blindspot 隔離
# ===========================================================================

@pytest.mark.asyncio
class TestBlindspotIsolationE2E:
    """E2E: Scoped partner sees empty blindspot list regardless of DB data."""

    async def test_scoped_partner_gets_empty_blindspot_list(self):
        """GET /api/data/blindspots returns [] for scoped partner even when DB has blindspots.

        Per SPEC-permission-model requirement 5:
        "Blindspot 類型資料完全不出現在結果中" for scoped partners.
        """
        from zenos.interface.dashboard_api import list_blindspots

        request = _mock_request(headers={"authorization": "Bearer fake"})

        with patch("zenos.interface.dashboard_api._verify_firebase_token", return_value={"email": "client@acme.com"}), \
             patch("zenos.interface.dashboard_api._get_partner_by_email_sql", return_value=SCOPED_CLIENT), \
             patch("zenos.interface.dashboard_api._ensure_repos", new=AsyncMock()), \
             patch("zenos.interface.dashboard_api._blindspot_repo") as mock_bs_repo, \
             patch("zenos.interface.dashboard_api._entity_repo"):
            mock_bs_repo.list_all = AsyncMock(return_value=ALL_BLINDSPOTS)
            resp = await list_blindspots(request)

        body = json.loads(resp.body)
        assert body["blindspots"] == [], (
            "Scoped partner must receive empty blindspot list, "
            f"got: {body['blindspots']}"
        )


# ===========================================================================
# E2E Scenario 6: Task 可見性（不受 entity visibility 過濾）
# ===========================================================================

@pytest.mark.asyncio
class TestTaskVisibilityIgnoresEntityVisibilityE2E:
    """E2E: Tasks linked to restricted entity are still visible to scoped partner.

    Per SPEC-permission-model requirement 4:
    "Task 不使用 visibility 欄位控制客戶可見性。Scoped partner 在自己的 L1 內
    預設能看到所有 task。"
    """

    async def test_task_linked_to_restricted_entity_is_visible_to_scoped_partner(self):
        """Scoped partner can see tasks whose linked entity has visibility=restricted.

        The task is inside the authorized L1, so the partner can see it even though
        the linked entity itself (restricted) would be filtered from entity lists.
        """
        from zenos.interface.dashboard_api import list_tasks

        request = _mock_request(headers={"authorization": "Bearer fake"})

        with patch("zenos.interface.dashboard_api._verify_firebase_token", return_value={"email": "client@acme.com"}), \
             patch("zenos.interface.dashboard_api._get_partner_by_email_sql", return_value=SCOPED_CLIENT), \
             patch("zenos.interface.dashboard_api._ensure_repos", new=AsyncMock()), \
             patch("zenos.interface.dashboard_api._task_repo") as mock_task_repo, \
             patch("zenos.interface.dashboard_api._entity_repo") as mock_entity_repo:
            mock_task_repo.list_all = AsyncMock(return_value=ALL_TASKS)
            mock_entity_repo.list_all = AsyncMock(return_value=ALL_ENTITIES)
            mock_entity_repo.get_by_id = AsyncMock(side_effect=_entity_get_by_id)
            resp = await list_tasks(request)

        body = json.loads(resp.body)
        task_ids = [t["id"] for t in body["tasks"]]

        assert "task-in-l1" in task_ids, (
            "Task linked to public entity in authorized L1 must be visible"
        )
        assert "task-linked-restricted" in task_ids, (
            "Task linked to restricted entity (but inside authorized L1) must still be visible — "
            "task visibility does not inherit entity visibility"
        )
        assert "task-out-l1" not in task_ids, (
            "Task linked to entity in unauthorized L1 must not be visible"
        )
