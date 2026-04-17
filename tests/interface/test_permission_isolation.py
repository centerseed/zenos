"""E2E permission isolation tests — both Dashboard API and MCP tools.

Verifies that restricted/confidential entities and their linked tasks/blindspots
are correctly hidden from unauthorized partners, across BOTH API layers:
  1. Dashboard REST API (dashboard_api.py)
  2. MCP tools (tools.py)
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from zenos.application.knowledge.ontology_service import UpsertEntityResult
from zenos.domain.action import Task
from zenos.domain.knowledge import Blindspot, Entity, Tags
from zenos.infrastructure.context import current_partner_department, current_partner_roles


def _ok_data(result: dict) -> dict:
    assert result["status"] == "ok"
    return result["data"]


def _non_ok_data(result: dict, status: str) -> dict:
    assert result["status"] == status
    return result["data"]


# ---------------------------------------------------------------------------
# Shared test data
# ---------------------------------------------------------------------------

def _make_entity(**overrides) -> Entity:
    defaults = dict(
        id="ent-pub",
        name="PublicEntity",
        type="module",
        level=2,
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


# Common entities for isolation tests
PUBLIC_ENTITY = _make_entity(id="ent-pub", name="Public Module", visibility="public")
RESTRICTED_ENTITY = _make_entity(
    id="ent-restricted",
    name="Finance Module",
    visibility="restricted",
    visible_to_roles=["finance"],
    visible_to_departments=["finance"],
)
CONFIDENTIAL_ENTITY = _make_entity(
    id="ent-confidential",
    name="Salary Data",
    visibility="confidential",
    visible_to_members=["p-finance-lead"],
)

# Tasks linked to different entities
PUBLIC_TASK = _make_task(id="task-pub", title="Public task", linked_entities=[])
RESTRICTED_TASK = _make_task(
    id="task-restricted",
    title="Fix salary calculation",
    linked_entities=["ent-restricted"],
)
CONFIDENTIAL_TASK = _make_task(
    id="task-confidential",
    title="Update bonus structure",
    linked_entities=["ent-confidential"],
)
MIXED_TASK = _make_task(
    id="task-mixed",
    title="Cross-team bug",
    linked_entities=["ent-pub", "ent-confidential"],
)

# Blindspots
PUBLIC_BLINDSPOT = _make_blindspot(id="bs-pub", related_entity_ids=["ent-pub"])
RESTRICTED_BLINDSPOT = _make_blindspot(
    id="bs-restricted",
    description="Finance gap",
    related_entity_ids=["ent-restricted"],
)
MIXED_BLINDSPOT = _make_blindspot(
    id="bs-mixed",
    description="Cross-team gap",
    related_entity_ids=["ent-pub", "ent-confidential"],
)

# L1 product entity (parent of PUBLIC_ENTITY for scoped partner tests)
L1_PRODUCT = _make_entity(
    id="product-acme",
    name="Acme Product",
    type="product",
    level=1,
    visibility="public",
)
# PUBLIC_ENTITY is a child of L1_PRODUCT
L1_PUBLIC_ENTITY = _make_entity(
    id="ent-pub",
    name="Public Module",
    type="module",
    level=2,
    parent_id="product-acme",
    visibility="public",
)
# Another L1 that the scoped partner is NOT authorized for
OTHER_L1 = _make_entity(
    id="product-other",
    name="Other Product",
    type="product",
    level=1,
    visibility="public",
)
OTHER_ENTITY = _make_entity(
    id="ent-other",
    name="Other Module",
    type="module",
    level=2,
    parent_id="product-other",
    visibility="public",
)

# Scoped entity map for tests: product-acme -> ent-pub, product-other -> ent-other
SCOPED_ALL_ENTITIES = [L1_PRODUCT, L1_PUBLIC_ENTITY, OTHER_L1, OTHER_ENTITY, RESTRICTED_ENTITY, CONFIDENTIAL_ENTITY]
SCOPED_ENTITY_MAP = {e.id: e for e in SCOPED_ALL_ENTITIES}


async def _mock_scoped_entity_get_by_id(eid: str):
    return SCOPED_ENTITY_MAP.get(eid)


# Task linked to L1_PUBLIC_ENTITY (in scoped partner's L1)
SCOPED_TASK_IN_L1 = _make_task(
    id="task-in-l1",
    title="Task in authorized L1",
    linked_entities=["ent-pub"],
)
# Task linked to OTHER_ENTITY (outside scoped partner's L1)
SCOPED_TASK_OUT_L1 = _make_task(
    id="task-out-l1",
    title="Task outside authorized L1",
    linked_entities=["ent-other"],
)
# Task with no linked entities
SCOPED_TASK_NO_LINK = _make_task(
    id="task-no-link",
    title="Unlinked task",
    linked_entities=[],
)

ALL_SCOPED_TASKS = [SCOPED_TASK_IN_L1, SCOPED_TASK_OUT_L1, SCOPED_TASK_NO_LINK]

ALL_ENTITIES = [PUBLIC_ENTITY, RESTRICTED_ENTITY, CONFIDENTIAL_ENTITY]
ALL_TASKS = [PUBLIC_TASK, RESTRICTED_TASK, CONFIDENTIAL_TASK, MIXED_TASK]
ALL_BLINDSPOTS = [PUBLIC_BLINDSPOT, RESTRICTED_BLINDSPOT, MIXED_BLINDSPOT]

# Partners
MARKETING_PARTNER = {
    "id": "p-marketing",
    "email": "marketing@test.com",
    "displayName": "Marketing User",
    "apiKey": "key-marketing",  # pragma: allowlist secret
    "status": "active",
    "accessMode": "internal",
    "isAdmin": False,
    "sharedPartnerId": None,
    "defaultProject": None,
    "roles": ["marketing"],
    "department": "marketing",
}

FINANCE_PARTNER = {
    "id": "p-finance",
    "email": "finance@test.com",
    "displayName": "Finance User",
    "apiKey": "key-finance",  # pragma: allowlist secret
    "status": "active",
    "accessMode": "internal",
    "isAdmin": False,
    "sharedPartnerId": None,
    "defaultProject": None,
    "roles": ["finance"],
    "department": "finance",
}

ADMIN_PARTNER = {
    "id": "p-admin",
    "email": "admin@test.com",
    "displayName": "Admin",
    "apiKey": "key-admin",  # pragma: allowlist secret
    "status": "active",
    "accessMode": "internal",
    "isAdmin": True,
    "sharedPartnerId": None,
    "defaultProject": None,
    "roles": [],
    "department": "all",
}

# Scoped partner authorized for L1 "product-acme" only
SCOPED_PARTNER = {
    "id": "p-client",
    "email": "client@external.com",
    "displayName": "External Client",
    "apiKey": "key-client",  # pragma: allowlist secret
    "status": "active",
    "accessMode": "scoped",
    "isAdmin": False,
    "sharedPartnerId": None,
    "defaultProject": None,
    "roles": [],
    "department": "all",
    "authorizedEntityIds": ["product-acme"],
}

INTERNAL_MEMBER_PARTNER = {
    "id": "p-internal",
    "email": "internal@test.com",
    "displayName": "Internal User",
    "apiKey": "key-internal",  # pragma: allowlist secret
    "status": "active",
    "accessMode": "internal",
    "isAdmin": False,
    "sharedPartnerId": None,
    "defaultProject": None,
    "roles": [],
    "department": "all",
    "authorizedEntityIds": [],
}

UNASSIGNED_PARTNER = {
    "id": "p-unassigned",
    "email": "unassigned@test.com",
    "displayName": "Unassigned User",
    "apiKey": "key-unassigned",  # pragma: allowlist secret
    "status": "active",
    "accessMode": "unassigned",
    "isAdmin": False,
    "sharedPartnerId": None,
    "defaultProject": None,
    "roles": [],
    "department": "all",
    "authorizedEntityIds": [],
}

SCOPED_EMPTY_SCOPE_PARTNER = {
    **SCOPED_PARTNER,
    "id": "p-client-empty",
    "email": "client-empty@external.com",
    "authorizedEntityIds": [],
}


async def _mock_entity_get_by_id(eid: str):
    entity_map = {e.id: e for e in ALL_ENTITIES}
    return entity_map.get(eid)


# ===========================================================================
# Part 1: Dashboard API — Task Isolation
# ===========================================================================

def _make_request(headers=None, query_params=None, path_params=None):
    req = MagicMock()
    req.method = "GET"
    req.headers = headers or {}
    req.query_params = query_params or {}
    req.path_params = path_params or {}
    return req


@pytest.mark.asyncio
class TestDashboardApiTaskIsolation:
    """Dashboard REST API should filter tasks by linked entity visibility."""

    async def test_marketing_sees_public_and_restricted_tasks(self):
        """Member (marketing) can see public + restricted tasks, not confidential (SPEC §4.1)."""
        from zenos.interface.dashboard_api import list_tasks

        request = _make_request(headers={"authorization": "Bearer fake"})

        with patch("zenos.interface.dashboard_api._verify_firebase_token", return_value={"email": "marketing@test.com"}), \
             patch("zenos.interface.dashboard_api._get_partner_by_email_sql", return_value=MARKETING_PARTNER), \
             patch("zenos.interface.dashboard_api._ensure_repos", new=AsyncMock()), \
             patch("zenos.interface.dashboard_api._task_repo") as mock_task_repo, \
             patch("zenos.interface.dashboard_api._entity_repo") as mock_entity_repo:
            mock_task_repo.list_all = AsyncMock(return_value=ALL_TASKS)
            mock_entity_repo.get_by_id = AsyncMock(side_effect=_mock_entity_get_by_id)
            resp = await list_tasks(request)

        body = json.loads(resp.body)
        task_ids = [t["id"] for t in body["tasks"]]
        assert "task-pub" in task_ids, "Public task should be visible"
        assert "task-restricted" in task_ids, "Member can see restricted task (SPEC §4.1)"
        assert "task-confidential" not in task_ids, "Confidential task should be hidden from marketing"
        assert "task-mixed" not in task_ids, "Mixed task (has confidential entity) should be hidden"

    async def test_finance_can_see_restricted_but_not_confidential(self):
        """Per SPEC §4.1: member can see public + restricted, but not confidential."""
        from zenos.interface.dashboard_api import list_tasks

        request = _make_request(headers={"authorization": "Bearer fake"})

        with patch("zenos.interface.dashboard_api._verify_firebase_token", return_value={"email": "finance@test.com"}), \
             patch("zenos.interface.dashboard_api._get_partner_by_email_sql", return_value=FINANCE_PARTNER), \
             patch("zenos.interface.dashboard_api._ensure_repos", new=AsyncMock()), \
             patch("zenos.interface.dashboard_api._task_repo") as mock_task_repo, \
             patch("zenos.interface.dashboard_api._entity_repo") as mock_entity_repo:
            mock_task_repo.list_all = AsyncMock(return_value=ALL_TASKS)
            mock_entity_repo.get_by_id = AsyncMock(side_effect=_mock_entity_get_by_id)
            resp = await list_tasks(request)

        body = json.loads(resp.body)
        task_ids = [t["id"] for t in body["tasks"]]
        assert "task-pub" in task_ids
        assert "task-restricted" in task_ids, "Member can see restricted task (SPEC §4.1)"
        assert "task-confidential" not in task_ids, "Confidential is owner/admin-only"
        assert "task-mixed" not in task_ids, "Mixed task hidden (has confidential entity)"

    async def test_admin_sees_all_tasks(self):
        from zenos.interface.dashboard_api import list_tasks

        request = _make_request(headers={"authorization": "Bearer fake"})

        with patch("zenos.interface.dashboard_api._verify_firebase_token", return_value={"email": "admin@test.com"}), \
             patch("zenos.interface.dashboard_api._get_partner_by_email_sql", return_value=ADMIN_PARTNER), \
             patch("zenos.interface.dashboard_api._ensure_repos", new=AsyncMock()), \
             patch("zenos.interface.dashboard_api._task_repo") as mock_task_repo, \
             patch("zenos.interface.dashboard_api._entity_repo") as mock_entity_repo:
            mock_task_repo.list_all = AsyncMock(return_value=ALL_TASKS)
            mock_entity_repo.get_by_id = AsyncMock(side_effect=_mock_entity_get_by_id)
            resp = await list_tasks(request)

        body = json.loads(resp.body)
        task_ids = [t["id"] for t in body["tasks"]]
        assert len(task_ids) == 4, "Admin should see all 4 tasks"


# ===========================================================================
# Part 2: Dashboard API — Blindspot Isolation
# ===========================================================================

@pytest.mark.asyncio
class TestDashboardApiBlindspotIsolation:

    async def test_marketing_sees_public_restricted_and_mixed_blindspots(self):
        """Member (marketing) sees blindspots linked to public or restricted entities (SPEC §4.1)."""
        from zenos.interface.dashboard_api import list_blindspots

        request = _make_request(headers={"authorization": "Bearer fake"})

        with patch("zenos.interface.dashboard_api._verify_firebase_token", return_value={"email": "marketing@test.com"}), \
             patch("zenos.interface.dashboard_api._get_partner_by_email_sql", return_value=MARKETING_PARTNER), \
             patch("zenos.interface.dashboard_api._ensure_repos", new=AsyncMock()), \
             patch("zenos.interface.dashboard_api._blindspot_repo") as mock_bs_repo, \
             patch("zenos.interface.dashboard_api._entity_repo") as mock_entity_repo:
            mock_bs_repo.list_all = AsyncMock(return_value=ALL_BLINDSPOTS)
            mock_entity_repo.get_by_id = AsyncMock(side_effect=_mock_entity_get_by_id)
            resp = await list_blindspots(request)

        body = json.loads(resp.body)
        bs_ids = [b["id"] for b in body["blindspots"]]
        assert "bs-pub" in bs_ids, "Public blindspot visible"
        assert "bs-restricted" in bs_ids, "Member can see restricted blindspot (SPEC §4.1)"
        assert "bs-mixed" in bs_ids, "Mixed blindspot visible (has at least one public entity)"


# ===========================================================================
# Part 3: MCP Tools — Task Isolation
# ===========================================================================

class _McpPartnerContext:
    """Set ContextVars for MCP tool tests."""

    def __init__(self, partner: dict):
        self.partner = partner
        self._tokens = []

    def __enter__(self):
        from zenos.interface.mcp import _current_partner
        self._tokens.append(("partner", _current_partner.set(self.partner)))
        self._tokens.append(("roles", current_partner_roles.set(self.partner.get("roles", []))))
        self._tokens.append(("dept", current_partner_department.set(self.partner.get("department", "all"))))
        return self

    def __exit__(self, *args):
        from zenos.interface.mcp import _current_partner
        for name, token in reversed(self._tokens):
            if name == "partner":
                _current_partner.reset(token)
            elif name == "roles":
                current_partner_roles.reset(token)
            elif name == "dept":
                current_partner_department.reset(token)


@pytest.fixture(autouse=True)
def _mock_mcp_bootstrap():
    with patch("zenos.interface.mcp._ensure_services", new=AsyncMock(return_value=None)), \
         patch("zenos.interface.mcp.ontology_service", new=AsyncMock()), \
         patch("zenos.interface.mcp.task_service", new=AsyncMock()), \
         patch("zenos.interface.mcp.entity_repo", new=AsyncMock()), \
         patch("zenos.interface.mcp.entry_repo", new=AsyncMock()):
        yield


@pytest.mark.asyncio
class TestMcpTaskIsolation:
    """MCP search/get tools should filter tasks by linked entity visibility."""

    async def test_finance_member_can_search_restricted_tasks(self):
        """Finance member can see restricted tasks in their department (SPEC §4.1 + department filter)."""
        from zenos.interface.mcp import search

        with _McpPartnerContext(FINANCE_PARTNER):
            with patch("zenos.interface.mcp.task_service") as mock_ts, \
                 patch("zenos.interface.mcp.entity_repo") as mock_repo:
                mock_ts.list_tasks = AsyncMock(return_value=ALL_TASKS)
                mock_repo.get_by_id = AsyncMock(side_effect=_mock_entity_get_by_id)
                result = await search(collection="tasks")

        task_ids = [t["id"] for t in _ok_data(result)["tasks"]]
        assert "task-pub" in task_ids
        assert "task-restricted" in task_ids, "Finance member can see restricted task in their dept (SPEC §4.1)"
        assert "task-confidential" not in task_ids

    async def test_admin_sees_all_via_mcp(self):
        from zenos.interface.mcp import search

        with _McpPartnerContext(ADMIN_PARTNER):
            with patch("zenos.interface.mcp.task_service") as mock_ts, \
                 patch("zenos.interface.mcp.entity_repo") as mock_repo:
                mock_ts.list_tasks = AsyncMock(return_value=ALL_TASKS)
                mock_repo.get_by_id = AsyncMock(side_effect=_mock_entity_get_by_id)
                result = await search(collection="tasks")

        task_ids = [t["id"] for t in _ok_data(result)["tasks"]]
        assert len(task_ids) == 4

    async def test_mcp_write_blocked_for_invisible_entity(self):
        from zenos.interface.mcp import write

        with _McpPartnerContext(MARKETING_PARTNER):
            with patch("zenos.interface.mcp.entity_repo") as mock_repo:
                mock_repo.get_by_id = AsyncMock(return_value=CONFIDENTIAL_ENTITY)
                mock_repo.get_by_name = AsyncMock(return_value=CONFIDENTIAL_ENTITY)
                result = await write(
                    collection="entities",
                    data={"id": "ent-confidential", "summary": "hacked"},
                )

        assert _non_ok_data(result, "error")["error"] == "FORBIDDEN"


# ===========================================================================
# Part 4: Cross-layer consistency
# ===========================================================================

@pytest.mark.asyncio
class TestCrossLayerConsistency:
    """Both API layers should produce the same visibility results."""

    async def test_same_tasks_visible_in_both_layers(self):
        """Finance member should see the same tasks via Dashboard API and MCP tools (SPEC §4.1).
        Uses FINANCE_PARTNER to test restricted visibility: finance dept passes the department
        filter on ent-restricted (visible_to_departments=['finance']).
        """
        from zenos.interface.mcp import search as mcp_search
        from zenos.interface.dashboard_api import list_tasks as api_list_tasks

        # MCP layer
        with _McpPartnerContext(FINANCE_PARTNER):
            with patch("zenos.interface.mcp.task_service") as mock_ts, \
                 patch("zenos.interface.mcp.entity_repo") as mock_repo:
                mock_ts.list_tasks = AsyncMock(return_value=ALL_TASKS)
                mock_repo.get_by_id = AsyncMock(side_effect=_mock_entity_get_by_id)
                mcp_result = await mcp_search(collection="tasks")

        mcp_task_ids = set(t["id"] for t in _ok_data(mcp_result)["tasks"])

        # Dashboard API layer
        request = _make_request(headers={"authorization": "Bearer fake"})
        with patch("zenos.interface.dashboard_api._verify_firebase_token", return_value={"email": "finance@test.com"}), \
             patch("zenos.interface.dashboard_api._get_partner_by_email_sql", return_value=FINANCE_PARTNER), \
             patch("zenos.interface.dashboard_api._ensure_repos", new=AsyncMock()), \
             patch("zenos.interface.dashboard_api._task_repo") as mock_task_repo, \
             patch("zenos.interface.dashboard_api._entity_repo") as mock_entity_repo:
            mock_task_repo.list_all = AsyncMock(return_value=ALL_TASKS)
            mock_entity_repo.get_by_id = AsyncMock(side_effect=_mock_entity_get_by_id)
            api_resp = await api_list_tasks(request)

        api_body = json.loads(api_resp.body)
        api_task_ids = set(t["id"] for t in api_body["tasks"])

        assert mcp_task_ids == api_task_ids, (
            f"MCP and Dashboard API should show same tasks. "
            f"MCP: {mcp_task_ids}, API: {api_task_ids}"
        )


# ===========================================================================
# Part 5: Scoped Partner — L1 Scope Isolation (DC-4, DC-6, DC-8)
# ===========================================================================

@pytest.mark.asyncio
class TestScopedPartnerEntityIsolation:
    """Scoped partner (authorized_entity_ids set) sees only public entities in their L1 subtree."""

    async def test_scoped_partner_only_sees_l1_public_entities(self):
        """DC-4: dashboard GET /api/data/entities only returns L1 scope public entities."""
        from zenos.interface.dashboard_api import list_entities

        request = _make_request(headers={"authorization": "Bearer fake"})

        with patch("zenos.interface.dashboard_api._verify_firebase_token", return_value={"email": "client@external.com"}), \
             patch("zenos.interface.dashboard_api._get_partner_by_email_sql", return_value=SCOPED_PARTNER), \
             patch("zenos.interface.dashboard_api._ensure_repos", new=AsyncMock()), \
             patch("zenos.interface.dashboard_api._entity_repo") as mock_entity_repo:
            mock_entity_repo.list_all = AsyncMock(return_value=SCOPED_ALL_ENTITIES)
            resp = await list_entities(request)

        body = json.loads(resp.body)
        entity_ids = [e["id"] for e in body["entities"]]
        assert "ent-pub" in entity_ids, "Entity in authorized L1 should be visible"
        assert "product-acme" in entity_ids, "L1 root itself should be visible"
        assert "ent-other" not in entity_ids, "Entity in unauthorized L1 should be hidden"
        assert "product-other" not in entity_ids, "Unauthorized L1 root should be hidden"
        assert "ent-restricted" not in entity_ids, "Restricted entity should not be visible to scoped partner"
        assert "ent-confidential" not in entity_ids, "Confidential entity should not be visible to scoped partner"

    async def test_scoped_partner_get_entity_outside_scope_returns_404(self):
        """DC-9: GET /api/data/entities/{id} for out-of-scope entity returns 404."""
        from zenos.interface.dashboard_api import get_entity

        request = _make_request(
            headers={"authorization": "Bearer fake"},
            path_params={"id": "ent-other"},
        )

        with patch("zenos.interface.dashboard_api._verify_firebase_token", return_value={"email": "client@external.com"}), \
             patch("zenos.interface.dashboard_api._get_partner_by_email_sql", return_value=SCOPED_PARTNER), \
             patch("zenos.interface.dashboard_api._ensure_repos", new=AsyncMock()), \
             patch("zenos.interface.dashboard_api._entity_repo") as mock_entity_repo:
            mock_entity_repo.get_by_id = AsyncMock(return_value=OTHER_ENTITY)
            mock_entity_repo.list_all = AsyncMock(return_value=SCOPED_ALL_ENTITIES)
            resp = await get_entity(request)

        body = json.loads(resp.body)
        assert resp.status_code == 404
        assert body["error"] == "NOT_FOUND"

    async def test_scoped_partner_get_entity_in_scope_returns_entity(self):
        """Scoped partner can fetch a public entity in their L1 scope."""
        from zenos.interface.dashboard_api import get_entity

        request = _make_request(
            headers={"authorization": "Bearer fake"},
            path_params={"id": "ent-pub"},
        )

        with patch("zenos.interface.dashboard_api._verify_firebase_token", return_value={"email": "client@external.com"}), \
             patch("zenos.interface.dashboard_api._get_partner_by_email_sql", return_value=SCOPED_PARTNER), \
             patch("zenos.interface.dashboard_api._ensure_repos", new=AsyncMock()), \
             patch("zenos.interface.dashboard_api._entity_repo") as mock_entity_repo:
            mock_entity_repo.get_by_id = AsyncMock(return_value=L1_PUBLIC_ENTITY)
            mock_entity_repo.list_all = AsyncMock(return_value=SCOPED_ALL_ENTITIES)
            resp = await get_entity(request)

        body = json.loads(resp.body)
        assert resp.status_code == 200
        assert body["entity"]["id"] == "ent-pub"

    async def test_internal_member_explicit_mode_can_see_cross_l1_public_data(self):
        """Explicit internal member remains cross-L1 even with empty authorized_entity_ids."""
        from zenos.interface.dashboard_api import list_entities

        request = _make_request(headers={"authorization": "Bearer fake"})

        with patch("zenos.interface.dashboard_api._verify_firebase_token", return_value={"email": "internal@test.com"}), \
             patch("zenos.interface.dashboard_api._get_partner_by_email_sql", return_value=INTERNAL_MEMBER_PARTNER), \
             patch("zenos.interface.dashboard_api._ensure_repos", new=AsyncMock()), \
             patch("zenos.interface.dashboard_api._entity_repo") as mock_entity_repo:
            mock_entity_repo.list_all = AsyncMock(return_value=SCOPED_ALL_ENTITIES)
            resp = await list_entities(request)

        body = json.loads(resp.body)
        entity_ids = [e["id"] for e in body["entities"]]
        # Internal non-admin: can see all public entities across all L1s
        assert "ent-pub" in entity_ids
        assert "ent-other" in entity_ids
        assert "product-acme" in entity_ids
        assert "product-other" in entity_ids
        # Member can see restricted, but not confidential (SPEC §4.1)
        assert "ent-restricted" in entity_ids, "Member can see restricted entity (SPEC §4.1)"
        assert "ent-confidential" not in entity_ids, "Member cannot see confidential entity"

    async def test_unassigned_partner_sees_no_entities(self):
        from zenos.interface.dashboard_api import list_entities

        request = _make_request(headers={"authorization": "Bearer fake"})

        with patch("zenos.interface.dashboard_api._verify_firebase_token", return_value={"email": "unassigned@test.com"}), \
             patch("zenos.interface.dashboard_api._get_partner_by_email_sql", return_value=UNASSIGNED_PARTNER), \
             patch("zenos.interface.dashboard_api._ensure_repos", new=AsyncMock()), \
             patch("zenos.interface.dashboard_api._entity_repo") as mock_entity_repo:
            mock_entity_repo.list_all = AsyncMock(return_value=SCOPED_ALL_ENTITIES)
            resp = await list_entities(request)

        body = json.loads(resp.body)
        assert body["entities"] == []

    async def test_scoped_partner_with_empty_scope_sees_no_entities(self):
        from zenos.interface.dashboard_api import list_entities

        request = _make_request(headers={"authorization": "Bearer fake"})

        with patch("zenos.interface.dashboard_api._verify_firebase_token", return_value={"email": "client-empty@external.com"}), \
             patch("zenos.interface.dashboard_api._get_partner_by_email_sql", return_value=SCOPED_EMPTY_SCOPE_PARTNER), \
             patch("zenos.interface.dashboard_api._ensure_repos", new=AsyncMock()), \
             patch("zenos.interface.dashboard_api._entity_repo") as mock_entity_repo:
            mock_entity_repo.list_all = AsyncMock(return_value=SCOPED_ALL_ENTITIES)
            resp = await list_entities(request)

        body = json.loads(resp.body)
        assert body["entities"] == []


@pytest.mark.asyncio
class TestScopedPartnerBlindspotIsolation:
    """DC-6: Scoped partner gets empty blindspot list."""

    async def test_scoped_partner_sees_no_blindspots(self):
        """DC-6: dashboard GET /api/data/blindspots returns empty for scoped partner."""
        from zenos.interface.dashboard_api import list_blindspots

        request = _make_request(headers={"authorization": "Bearer fake"})

        with patch("zenos.interface.dashboard_api._verify_firebase_token", return_value={"email": "client@external.com"}), \
             patch("zenos.interface.dashboard_api._get_partner_by_email_sql", return_value=SCOPED_PARTNER), \
             patch("zenos.interface.dashboard_api._ensure_repos", new=AsyncMock()), \
             patch("zenos.interface.dashboard_api._blindspot_repo") as mock_bs_repo, \
             patch("zenos.interface.dashboard_api._entity_repo"):
            mock_bs_repo.list_all = AsyncMock(return_value=ALL_BLINDSPOTS)
            resp = await list_blindspots(request)

        body = json.loads(resp.body)
        assert body["blindspots"] == [], "Scoped partner should see no blindspots"

    async def test_unassigned_partner_sees_no_blindspots(self):
        from zenos.interface.dashboard_api import list_blindspots

        request = _make_request(headers={"authorization": "Bearer fake"})

        with patch("zenos.interface.dashboard_api._verify_firebase_token", return_value={"email": "unassigned@test.com"}), \
             patch("zenos.interface.dashboard_api._get_partner_by_email_sql", return_value=UNASSIGNED_PARTNER), \
             patch("zenos.interface.dashboard_api._ensure_repos", new=AsyncMock()), \
             patch("zenos.interface.dashboard_api._blindspot_repo") as mock_bs_repo:
            mock_bs_repo.list_all = AsyncMock(return_value=ALL_BLINDSPOTS)
            resp = await list_blindspots(request)

        body = json.loads(resp.body)
        assert body["blindspots"] == []

    async def test_mcp_scoped_partner_sees_no_blindspots(self):
        """DC-7: MCP search(collection='blindspots') returns empty for scoped partner."""
        from zenos.interface.mcp import search

        with _McpPartnerContext(SCOPED_PARTNER):
            with patch("zenos.interface.mcp.ontology_service") as mock_os, \
                 patch("zenos.interface.mcp.entity_repo") as mock_repo:
                mock_os.list_blindspots = AsyncMock(return_value=ALL_BLINDSPOTS)
                mock_repo.get_by_id = AsyncMock(side_effect=_mock_scoped_entity_get_by_id)
                result = await search(collection="blindspots")

        assert _ok_data(result)["blindspots"] == [], "Scoped partner should see no blindspots via MCP"

    async def test_mcp_unassigned_partner_sees_no_blindspots(self):
        from zenos.interface.mcp import search

        with _McpPartnerContext(UNASSIGNED_PARTNER):
            with patch("zenos.interface.mcp.ontology_service") as mock_os:
                mock_os.list_blindspots = AsyncMock(return_value=ALL_BLINDSPOTS)
                result = await search(collection="blindspots")

        assert _ok_data(result)["blindspots"] == []


@pytest.mark.asyncio
class TestScopedPartnerTaskIsolation:
    """DC-8: Scoped partner sees only tasks with linked entities in their L1 scope."""

    async def test_scoped_partner_sees_only_tasks_in_l1_scope(self):
        """DC-8: dashboard GET /api/data/tasks only returns tasks with linked entity in L1 scope."""
        from zenos.interface.dashboard_api import list_tasks

        request = _make_request(headers={"authorization": "Bearer fake"})

        with patch("zenos.interface.dashboard_api._verify_firebase_token", return_value={"email": "client@external.com"}), \
             patch("zenos.interface.dashboard_api._get_partner_by_email_sql", return_value=SCOPED_PARTNER), \
             patch("zenos.interface.dashboard_api._ensure_repos", new=AsyncMock()), \
             patch("zenos.interface.dashboard_api._task_repo") as mock_task_repo, \
             patch("zenos.interface.dashboard_api._entity_repo") as mock_entity_repo:
            mock_task_repo.list_all = AsyncMock(return_value=ALL_SCOPED_TASKS)
            mock_entity_repo.list_all = AsyncMock(return_value=SCOPED_ALL_ENTITIES)
            mock_entity_repo.get_by_id = AsyncMock(side_effect=_mock_scoped_entity_get_by_id)
            resp = await list_tasks(request)

        body = json.loads(resp.body)
        task_ids = [t["id"] for t in body["tasks"]]
        assert "task-in-l1" in task_ids, "Task linked to authorized L1 entity should be visible"
        assert "task-out-l1" not in task_ids, "Task linked to unauthorized L1 entity should be hidden"
        assert "task-no-link" not in task_ids, "Unlinked task should not be visible to scoped partner"

    async def test_mcp_scoped_partner_task_isolation(self):
        """DC-5/DC-8 partial: MCP search(collection='tasks') filters for scoped partner."""
        from zenos.interface.mcp import search

        with _McpPartnerContext(SCOPED_PARTNER):
            with patch("zenos.interface.mcp.task_service") as mock_ts, \
                 patch("zenos.interface.mcp.entity_repo") as mock_repo:
                mock_ts.list_tasks = AsyncMock(return_value=ALL_SCOPED_TASKS)
                mock_repo.get_by_id = AsyncMock(side_effect=_mock_scoped_entity_get_by_id)
                mock_repo.list_all = AsyncMock(return_value=list(SCOPED_ALL_ENTITIES))
                result = await search(collection="tasks")

        task_ids = [t["id"] for t in _ok_data(result)["tasks"]]
        assert "task-in-l1" in task_ids, "Task in authorized L1 should be visible via MCP"
        assert "task-out-l1" not in task_ids, "Task outside authorized L1 should be hidden via MCP"
        assert "task-no-link" not in task_ids, "Unlinked task should not be visible to scoped partner via MCP"

    async def test_unassigned_partner_sees_no_tasks(self):
        from zenos.interface.dashboard_api import list_tasks

        request = _make_request(headers={"authorization": "Bearer fake"})

        with patch("zenos.interface.dashboard_api._verify_firebase_token", return_value={"email": "unassigned@test.com"}), \
             patch("zenos.interface.dashboard_api._get_partner_by_email_sql", return_value=UNASSIGNED_PARTNER), \
             patch("zenos.interface.dashboard_api._ensure_repos", new=AsyncMock()), \
             patch("zenos.interface.dashboard_api._task_repo") as mock_task_repo:
            mock_task_repo.list_all = AsyncMock(return_value=ALL_SCOPED_TASKS)
            resp = await list_tasks(request)

        body = json.loads(resp.body)
        assert body["tasks"] == []

    async def test_mcp_unassigned_partner_sees_no_tasks(self):
        from zenos.interface.mcp import search

        with _McpPartnerContext(UNASSIGNED_PARTNER):
            with patch("zenos.interface.mcp.task_service") as mock_ts:
                mock_ts.list_tasks = AsyncMock(return_value=ALL_SCOPED_TASKS)
                result = await search(collection="tasks")

        assert _ok_data(result)["tasks"] == []


@pytest.mark.asyncio
class TestRestrictedAdminOnly:
    """Confidential is owner/admin-only; members can see public + restricted (SPEC §4.1)."""

    async def test_internal_non_admin_can_see_restricted_but_not_confidential(self):
        """Member can see public + restricted, but not confidential (SPEC §4.1)."""
        from zenos.interface.dashboard_api import list_entities

        request = _make_request(headers={"authorization": "Bearer fake"})

        with patch("zenos.interface.dashboard_api._verify_firebase_token", return_value={"email": "marketing@test.com"}), \
             patch("zenos.interface.dashboard_api._get_partner_by_email_sql", return_value=MARKETING_PARTNER), \
             patch("zenos.interface.dashboard_api._ensure_repos", new=AsyncMock()), \
             patch("zenos.interface.dashboard_api._entity_repo") as mock_entity_repo:
            mock_entity_repo.list_all = AsyncMock(return_value=ALL_ENTITIES)
            resp = await list_entities(request)

        body = json.loads(resp.body)
        entity_ids = [e["id"] for e in body["entities"]]
        assert "ent-pub" in entity_ids, "Public entity should be visible"
        assert "ent-restricted" in entity_ids, "Member can see restricted entity (SPEC §4.1)"
        assert "ent-confidential" not in entity_ids, "Confidential entity is owner/admin-only"

    async def test_admin_sees_restricted_and_confidential_entities(self):
        """DC-1, DC-2: admin can see restricted and confidential entities."""
        from zenos.interface.dashboard_api import list_entities

        request = _make_request(headers={"authorization": "Bearer fake"})

        with patch("zenos.interface.dashboard_api._verify_firebase_token", return_value={"email": "admin@test.com"}), \
             patch("zenos.interface.dashboard_api._get_partner_by_email_sql", return_value=ADMIN_PARTNER), \
             patch("zenos.interface.dashboard_api._ensure_repos", new=AsyncMock()), \
             patch("zenos.interface.dashboard_api._entity_repo") as mock_entity_repo:
            mock_entity_repo.list_all = AsyncMock(return_value=ALL_ENTITIES)
            resp = await list_entities(request)

        body = json.loads(resp.body)
        entity_ids = [e["id"] for e in body["entities"]]
        assert "ent-pub" in entity_ids
        assert "ent-restricted" in entity_ids, "Admin should see restricted entity"
        assert "ent-confidential" in entity_ids, "Admin should see confidential entity"


@pytest.mark.asyncio
class TestLegacyRoleRestrictedCompatibility:
    """Legacy role-restricted is normalized to restricted at runtime.
    Per SPEC §4.1: members can see restricted (normalized from role-restricted);
    confidential remains owner/admin-only.
    """

    async def test_legacy_role_restricted_visible_to_member(self):
        """Legacy role-restricted normalizes to restricted, which members can see (SPEC §4.1)."""
        from zenos.application.knowledge.ontology_service import OntologyService

        role_restricted = _make_entity(
            id="ent-role",
            name="Finance Dashboard",
            visibility="role-restricted",
            visible_to_roles=["finance"],
        )
        finance_partner = {
            "id": "p-finance",
            "isAdmin": False,
            "accessMode": "internal",
            "status": "active",
            "roles": ["finance"],
            "authorizedEntityIds": None,
        }
        assert OntologyService.is_entity_visible_for_partner(role_restricted, finance_partner) is True

    async def test_legacy_role_restricted_visible_to_non_matching_member(self):
        """Legacy role-restricted normalizes to restricted — all members can see it, regardless of role."""
        from zenos.application.knowledge.ontology_service import OntologyService

        role_restricted = _make_entity(
            id="ent-role",
            name="Finance Dashboard",
            visibility="role-restricted",
            visible_to_roles=["finance"],
        )
        marketing_partner = {
            "id": "p-marketing",
            "isAdmin": False,
            "accessMode": "internal",
            "status": "active",
            "roles": ["marketing"],
            "authorizedEntityIds": None,
        }
        assert OntologyService.is_entity_visible_for_partner(role_restricted, marketing_partner) is True

    async def test_legacy_role_restricted_hidden_from_guest(self):
        """Guest still cannot see legacy role-restricted entities."""
        from zenos.application.knowledge.ontology_service import OntologyService

        role_restricted = _make_entity(
            id="ent-role",
            name="Finance Dashboard",
            visibility="role-restricted",
            visible_to_roles=["finance"],
        )
        scoped_with_role = {
            "id": "p-client",
            "isAdmin": False,
            "roles": ["finance"],
            "authorizedEntityIds": ["product-acme"],
        }
        assert OntologyService.is_entity_visible_for_partner(role_restricted, scoped_with_role) is False


# ===========================================================================
# Part 6: Guest task visibility follows entity visibility inside authorized subtree
# ===========================================================================

# A restricted entity that lives inside the scoped partner's L1 subtree
L1_RESTRICTED_ENTITY = _make_entity(
    id="ent-restricted-in-l1",
    name="Restricted Module In L1",
    type="module",
    level=2,
    parent_id="product-acme",
    visibility="restricted",
)

# Task linked to the restricted-but-in-scope entity
SCOPED_TASK_RESTRICTED_IN_L1 = _make_task(
    id="task-restricted-in-l1",
    title="Task linked to restricted entity in L1",
    linked_entities=["ent-restricted-in-l1"],
)

# Full entity map including the restricted-in-l1 entity
SCOPED_ALL_ENTITIES_WITH_RESTRICTED = [
    L1_PRODUCT, L1_PUBLIC_ENTITY, L1_RESTRICTED_ENTITY,
    OTHER_L1, OTHER_ENTITY, RESTRICTED_ENTITY, CONFIDENTIAL_ENTITY,
]


@pytest.mark.asyncio
class TestScopedPartnerTaskVisibilityRespectsEntityVisibility:
    """Guest should only see public tasks inside the authorized subtree."""

    async def test_mcp_scoped_partner_hides_task_linked_to_restricted_entity_in_l1(self):
        """Task linked to restricted entity in L1 scope stays hidden from scoped partner."""
        from zenos.interface.mcp import search

        tasks = [SCOPED_TASK_RESTRICTED_IN_L1, SCOPED_TASK_OUT_L1, SCOPED_TASK_NO_LINK]

        with _McpPartnerContext(SCOPED_PARTNER):
            with patch("zenos.interface.mcp.task_service") as mock_ts, \
                 patch("zenos.interface.mcp.entity_repo") as mock_repo:
                mock_ts.list_tasks = AsyncMock(return_value=tasks)
                mock_repo.list_all = AsyncMock(return_value=SCOPED_ALL_ENTITIES_WITH_RESTRICTED)
                mock_repo.get_by_id = AsyncMock(side_effect=lambda eid: next((e for e in SCOPED_ALL_ENTITIES_WITH_RESTRICTED if e.id == eid), None))
                result = await search(collection="tasks")

        task_ids = [t["id"] for t in _ok_data(result)["tasks"]]
        assert "task-restricted-in-l1" not in task_ids, (
            "Scoped partner must not see tasks linked to restricted entities within their L1 scope"
        )
        assert "task-out-l1" not in task_ids, "Task outside L1 scope remains hidden"
        assert "task-no-link" not in task_ids, "Unlinked task remains hidden"

    async def test_mcp_scoped_partner_and_dashboard_api_task_visibility_consistent_for_restricted_entity(self):
        """MCP and Dashboard API agree that restricted in-scope tasks stay hidden."""
        from zenos.interface.mcp import search as mcp_search
        from zenos.interface.dashboard_api import list_tasks as api_list_tasks

        tasks = [SCOPED_TASK_RESTRICTED_IN_L1, SCOPED_TASK_OUT_L1, SCOPED_TASK_NO_LINK]

        # MCP layer
        with _McpPartnerContext(SCOPED_PARTNER):
            with patch("zenos.interface.mcp.task_service") as mock_ts, \
                 patch("zenos.interface.mcp.entity_repo") as mock_repo:
                mock_ts.list_tasks = AsyncMock(return_value=tasks)
                mock_repo.list_all = AsyncMock(return_value=SCOPED_ALL_ENTITIES_WITH_RESTRICTED)
                mock_repo.get_by_id = AsyncMock(side_effect=lambda eid: next((e for e in SCOPED_ALL_ENTITIES_WITH_RESTRICTED if e.id == eid), None))
                mcp_result = await mcp_search(collection="tasks")

        mcp_task_ids = set(t["id"] for t in _ok_data(mcp_result)["tasks"])

        # Dashboard API layer
        request = _make_request(headers={"authorization": "Bearer fake"})
        with patch("zenos.interface.dashboard_api._verify_firebase_token", return_value={"email": "client@external.com"}), \
             patch("zenos.interface.dashboard_api._get_partner_by_email_sql", return_value=SCOPED_PARTNER), \
             patch("zenos.interface.dashboard_api._ensure_repos", new=AsyncMock()), \
             patch("zenos.interface.dashboard_api._task_repo") as mock_task_repo, \
             patch("zenos.interface.dashboard_api._entity_repo") as mock_entity_repo:
            mock_task_repo.list_all = AsyncMock(return_value=tasks)
            mock_entity_repo.list_all = AsyncMock(return_value=SCOPED_ALL_ENTITIES_WITH_RESTRICTED)
            mock_entity_repo.get_by_id = AsyncMock(
                side_effect=lambda eid: next(
                    (e for e in SCOPED_ALL_ENTITIES_WITH_RESTRICTED if e.id == eid),
                    None,
                )
            )
            api_resp = await api_list_tasks(request)

        api_body = json.loads(api_resp.body)
        api_task_ids = set(t["id"] for t in api_body["tasks"])

        assert mcp_task_ids == api_task_ids, (
            f"MCP and Dashboard API must agree on task visibility for scoped partner. "
            f"MCP: {mcp_task_ids}, API: {api_task_ids}"
        )
        assert "task-restricted-in-l1" not in mcp_task_ids, "Both layers should hide restricted in-scope task from guest"


# ===========================================================================
# Part 7: DC-3 fix — get_entity_children scoped partner L1 scope filtering
# ===========================================================================

@pytest.mark.asyncio
class TestScopedPartnerGetEntityChildren:
    """DC-3: get_entity_children applies L1 scope filtering for scoped partners."""

    async def test_scoped_partner_children_of_out_of_scope_parent_returns_empty(self):
        """DC-3a: requesting children of a parent not in allowed_ids returns empty list."""
        from zenos.interface.dashboard_api import get_entity_children

        # OTHER_L1 is not in SCOPED_PARTNER's allowed scope
        request = _make_request(
            headers={"authorization": "Bearer fake"},
            path_params={"id": "product-other"},
        )

        with patch("zenos.interface.dashboard_api._verify_firebase_token", return_value={"email": "client@external.com"}), \
             patch("zenos.interface.dashboard_api._get_partner_by_email_sql", return_value=SCOPED_PARTNER), \
             patch("zenos.interface.dashboard_api._ensure_repos", new=AsyncMock()), \
             patch("zenos.interface.dashboard_api._entity_repo") as mock_entity_repo:
            # children of product-other
            mock_entity_repo.list_by_parent = AsyncMock(return_value=[OTHER_ENTITY])
            mock_entity_repo.list_all = AsyncMock(return_value=SCOPED_ALL_ENTITIES)
            resp = await get_entity_children(request)

        body = json.loads(resp.body)
        assert body["entities"] == [], "Out-of-scope parent must return empty children"
        assert body["count"] == 0

    async def test_scoped_partner_children_of_in_scope_parent_filters_correctly(self):
        """DC-3b: children of in-scope parent are filtered to L1 scope + public only."""
        from zenos.interface.dashboard_api import get_entity_children

        # product-acme is in SCOPED_PARTNER's scope
        request = _make_request(
            headers={"authorization": "Bearer fake"},
            path_params={"id": "product-acme"},
        )

        with patch("zenos.interface.dashboard_api._verify_firebase_token", return_value={"email": "client@external.com"}), \
             patch("zenos.interface.dashboard_api._get_partner_by_email_sql", return_value=SCOPED_PARTNER), \
             patch("zenos.interface.dashboard_api._ensure_repos", new=AsyncMock()), \
             patch("zenos.interface.dashboard_api._entity_repo") as mock_entity_repo:
            # Two children: one public (in scope), one restricted (in scope but not public)
            mock_entity_repo.list_by_parent = AsyncMock(
                return_value=[L1_PUBLIC_ENTITY, L1_RESTRICTED_ENTITY]
            )
            mock_entity_repo.list_all = AsyncMock(return_value=SCOPED_ALL_ENTITIES_WITH_RESTRICTED)
            resp = await get_entity_children(request)

        body = json.loads(resp.body)
        entity_ids = [e["id"] for e in body["entities"]]
        assert "ent-pub" in entity_ids, "Public entity in L1 scope must be visible"
        assert "ent-restricted-in-l1" not in entity_ids, "Restricted entity must not be in children result"


# ===========================================================================
# Part 8: S04 query slicing — guest/member/owner entity query integration tests
# ===========================================================================

# Test data for S04 query slicing tests
S04_L1_A = _make_entity(id="s04-l1-a", name="Product A", type="product", level=1, visibility="public")
S04_L1_B = _make_entity(id="s04-l1-b", name="Product B", type="product", level=1, visibility="public")
S04_L2_A = _make_entity(
    id="s04-l2-a", name="Module A", type="module", level=2,
    parent_id="s04-l1-a", visibility="public",
)
S04_L2_B = _make_entity(
    id="s04-l2-b", name="Module B", type="module", level=2,
    parent_id="s04-l1-b", visibility="public",
)
S04_L3_A = _make_entity(
    id="s04-l3-a", name="Feature A", type="project", level=3,
    parent_id="s04-l2-a", visibility="public",
)
S04_RESTRICTED_IN_A = _make_entity(
    id="s04-restricted-a", name="Restricted In A", type="module", level=2,
    parent_id="s04-l1-a", visibility="restricted",
)
S04_CONFIDENTIAL = _make_entity(
    id="s04-confidential", name="Confidential", type="module", level=2,
    parent_id="s04-l1-a", visibility="confidential",
)

S04_ALL_ENTITIES = [
    S04_L1_A, S04_L1_B, S04_L2_A, S04_L2_B, S04_L3_A,
    S04_RESTRICTED_IN_A, S04_CONFIDENTIAL,
]

# Owner partner (isAdmin=True)
S04_OWNER_PARTNER = {
    "id": "s04-owner",
    "email": "owner@test.com",
    "displayName": "Owner",
    "isAdmin": True,
    "status": "active",
    "accessMode": "internal",
    "sharedPartnerId": None,
    "defaultProject": None,
    "roles": [],
    "department": "all",
    "authorizedEntityIds": [],
}

# Member partner (not admin, no scope restriction)
S04_MEMBER_PARTNER = {
    "id": "s04-member",
    "email": "member@test.com",
    "displayName": "Member",
    "isAdmin": False,
    "status": "active",
    "accessMode": "internal",
    "workspaceRole": "member",
    "sharedPartnerId": None,
    "defaultProject": None,
    "roles": [],
    "department": "all",
    "authorizedEntityIds": [],
}

# Guest partner authorized only for L1-A
S04_GUEST_PARTNER = {
    "id": "s04-guest",
    "email": "guest@test.com",
    "displayName": "Guest",
    "isAdmin": False,
    "status": "active",
    "accessMode": "scoped",
    "workspaceRole": "guest",
    "sharedPartnerId": None,
    "defaultProject": None,
    "roles": [],
    "department": "all",
    "authorizedEntityIds": ["s04-l1-a"],
}


@pytest.mark.asyncio
class TestS04QuerySlicingGuestMemberOwner:
    """S04 Done Criteria: guest/member/owner entity query slicing integration tests."""

    async def test_owner_sees_all_entities_including_restricted_and_confidential(self):
        """Owner: active workspace full scope — no additional filtering."""
        from zenos.interface.dashboard_api import list_entities

        request = _make_request(headers={"authorization": "Bearer fake"})

        with patch("zenos.interface.dashboard_api._verify_firebase_token", return_value={"email": "owner@test.com"}), \
             patch("zenos.interface.dashboard_api._get_partner_by_email_sql", return_value=S04_OWNER_PARTNER), \
             patch("zenos.interface.dashboard_api._ensure_repos", new=AsyncMock()), \
             patch("zenos.interface.dashboard_api._entity_repo") as mock_entity_repo:
            mock_entity_repo.list_all = AsyncMock(return_value=S04_ALL_ENTITIES)
            resp = await list_entities(request)

        body = json.loads(resp.body)
        entity_ids = [e["id"] for e in body["entities"]]
        assert "s04-l1-a" in entity_ids, "Owner sees L1-A"
        assert "s04-l1-b" in entity_ids, "Owner sees L1-B"
        assert "s04-l2-a" in entity_ids, "Owner sees L2-A"
        assert "s04-l2-b" in entity_ids, "Owner sees L2-B"
        assert "s04-l3-a" in entity_ids, "Owner sees L3-A"
        assert "s04-restricted-a" in entity_ids, "Owner sees restricted entity"
        assert "s04-confidential" in entity_ids, "Owner sees confidential entity"
        assert len(entity_ids) == 7, "Owner sees all 7 entities"

    async def test_member_sees_public_and_restricted_entities_across_l1s(self):
        """Member: active workspace full scope — sees public + restricted, not confidential (SPEC §4.1)."""
        from zenos.interface.dashboard_api import list_entities

        request = _make_request(headers={"authorization": "Bearer fake"})

        with patch("zenos.interface.dashboard_api._verify_firebase_token", return_value={"email": "member@test.com"}), \
             patch("zenos.interface.dashboard_api._get_partner_by_email_sql", return_value=S04_MEMBER_PARTNER), \
             patch("zenos.interface.dashboard_api._ensure_repos", new=AsyncMock()), \
             patch("zenos.interface.dashboard_api._entity_repo") as mock_entity_repo:
            mock_entity_repo.list_all = AsyncMock(return_value=S04_ALL_ENTITIES)
            resp = await list_entities(request)

        body = json.loads(resp.body)
        entity_ids = [e["id"] for e in body["entities"]]
        # Member sees all public across all L1s
        assert "s04-l1-a" in entity_ids, "Member sees L1-A (public)"
        assert "s04-l1-b" in entity_ids, "Member sees L1-B (public)"
        assert "s04-l2-a" in entity_ids, "Member sees L2-A (public)"
        assert "s04-l2-b" in entity_ids, "Member sees L2-B (public)"
        assert "s04-l3-a" in entity_ids, "Member sees L3-A (public)"
        # Member can see restricted but not confidential (SPEC §4.1)
        assert "s04-restricted-a" in entity_ids, "Member sees restricted entity (SPEC §4.1)"
        assert "s04-confidential" not in entity_ids, "Member cannot see confidential entity"

    async def test_guest_sees_only_authorized_l1_subtree_public_entities(self):
        """Guest: only authorized L1 subtree + public visibility."""
        from zenos.interface.dashboard_api import list_entities

        request = _make_request(headers={"authorization": "Bearer fake"})

        with patch("zenos.interface.dashboard_api._verify_firebase_token", return_value={"email": "guest@test.com"}), \
             patch("zenos.interface.dashboard_api._get_partner_by_email_sql", return_value=S04_GUEST_PARTNER), \
             patch("zenos.interface.dashboard_api._ensure_repos", new=AsyncMock()), \
             patch("zenos.interface.dashboard_api._entity_repo") as mock_entity_repo:
            mock_entity_repo.list_all = AsyncMock(return_value=S04_ALL_ENTITIES)
            resp = await list_entities(request)

        body = json.loads(resp.body)
        entity_ids = [e["id"] for e in body["entities"]]
        # Guest sees only L1-A subtree public entities
        assert "s04-l1-a" in entity_ids, "Guest sees authorized L1-A (public)"
        assert "s04-l2-a" in entity_ids, "Guest sees L2-A (public, under L1-A)"
        assert "s04-l3-a" in entity_ids, "Guest sees L3-A (public, under L2-A → L1-A)"
        # Guest cannot see L1-B subtree (not authorized)
        assert "s04-l1-b" not in entity_ids, "Guest cannot see unauthorized L1-B"
        assert "s04-l2-b" not in entity_ids, "Guest cannot see L2-B (under unauthorized L1-B)"
        # Guest cannot see restricted or confidential even within authorized L1
        assert "s04-restricted-a" not in entity_ids, "Guest cannot see restricted entity"
        assert "s04-confidential" not in entity_ids, "Guest cannot see confidential entity"

    async def test_mcp_owner_sees_all_entities(self):
        """MCP layer: owner sees all entities (L1+L2) via search including restricted and confidential."""
        from zenos.interface.mcp import search

        with _McpPartnerContext(S04_OWNER_PARTNER):
            with patch("zenos.interface.mcp.ontology_service") as mock_os:
                mock_os.list_entities = AsyncMock(return_value=S04_ALL_ENTITIES)
                # Default entity_level is L1+L2, so L3 is excluded from this assertion
                result = await search(collection="entities")

        entity_ids = [e["id"] for e in _ok_data(result)["entities"]]
        # Owner sees all L1+L2 entities (default max_level=2 excludes L3)
        assert "s04-l1-a" in entity_ids, "Owner sees L1-A"
        assert "s04-l1-b" in entity_ids, "Owner sees L1-B"
        assert "s04-l2-a" in entity_ids, "Owner sees L2-A"
        assert "s04-l2-b" in entity_ids, "Owner sees L2-B"
        assert "s04-restricted-a" in entity_ids, "Owner sees restricted via MCP"
        assert "s04-confidential" in entity_ids, "Owner sees confidential via MCP"

    async def test_mcp_member_sees_public_and_restricted_entities(self):
        """MCP layer: member sees public + restricted, not confidential (SPEC §4.1)."""
        from zenos.interface.mcp import search

        with _McpPartnerContext(S04_MEMBER_PARTNER):
            with patch("zenos.interface.mcp.ontology_service") as mock_os:
                mock_os.list_entities = AsyncMock(return_value=S04_ALL_ENTITIES)
                result = await search(collection="entities")

        entity_ids = [e["id"] for e in _ok_data(result)["entities"]]
        assert "s04-l1-a" in entity_ids
        assert "s04-l1-b" in entity_ids
        assert "s04-restricted-a" in entity_ids, "Member can see restricted via MCP (SPEC §4.1)"
        assert "s04-confidential" not in entity_ids, "Member cannot see confidential via MCP"

    async def test_mcp_guest_sees_only_authorized_subtree_public_via_search(self):
        """MCP layer: guest sees only authorized L1 subtree + public via search."""
        from zenos.interface.mcp import search

        with _McpPartnerContext(S04_GUEST_PARTNER):
            with patch("zenos.interface.mcp.ontology_service") as mock_os:
                mock_os.list_entities = AsyncMock(return_value=S04_ALL_ENTITIES)
                # The guest subtree calculation uses ontology_service._entities.list_all
                mock_os._entities = AsyncMock()
                mock_os._entities.list_all = AsyncMock(return_value=S04_ALL_ENTITIES)
                result = await search(collection="entities")

        entity_ids = [e["id"] for e in _ok_data(result)["entities"]]
        assert "s04-l1-a" in entity_ids, "Guest sees authorized L1-A via MCP"
        assert "s04-l2-a" in entity_ids, "Guest sees L2-A under authorized L1-A via MCP"
        assert "s04-l1-b" not in entity_ids, "Guest cannot see unauthorized L1-B via MCP"
        assert "s04-l2-b" not in entity_ids, "Guest cannot see L2-B under unauthorized L1-B via MCP"
        assert "s04-restricted-a" not in entity_ids, "Guest cannot see restricted via MCP"

    async def test_graph_unauthorized_relationships_excluded_for_guest(self):
        """S04 DC-4: unauthorized impact/relation excluded from graph for guest."""
        from zenos.interface.dashboard_api import get_entity_relationships

        # Guest authorized for L1-A only; relationship between L2-A and L2-B should be excluded
        request = _make_request(
            headers={"authorization": "Bearer fake"},
            path_params={"id": "s04-l2-a"},
        )

        from zenos.domain.knowledge import Relationship

        def _make_rel(src, tgt):
            return Relationship(
                id=f"rel-{src}-{tgt}",
                source_entity_id=src,
                target_id=tgt,
                type="depends_on",
                description="depends",
                confirmed_by_user=True,
            )

        rels = [
            _make_rel("s04-l2-a", "s04-l2-b"),   # cross-L1: should be excluded for guest
            _make_rel("s04-l2-a", "s04-l3-a"),   # within L1-A subtree: should be visible
        ]

        with patch("zenos.interface.dashboard_api._verify_firebase_token", return_value={"email": "guest@test.com"}), \
             patch("zenos.interface.dashboard_api._get_partner_by_email_sql", return_value=S04_GUEST_PARTNER), \
             patch("zenos.interface.dashboard_api._ensure_repos", new=AsyncMock()), \
             patch("zenos.interface.dashboard_api._entity_repo") as mock_entity_repo, \
             patch("zenos.interface.dashboard_api._relationship_repo") as mock_rel_repo:
            mock_entity_repo.get_by_id = AsyncMock(side_effect=lambda eid: {
                e.id: e for e in S04_ALL_ENTITIES
            }.get(eid))
            mock_entity_repo.list_all = AsyncMock(return_value=S04_ALL_ENTITIES)
            mock_rel_repo.list_by_entity = AsyncMock(return_value=rels)
            resp = await get_entity_relationships(request)

        body = json.loads(resp.body)
        rel_target_ids = [r["targetId"] for r in body["relationships"]]
        assert "s04-l3-a" in rel_target_ids, "Intra-L1 relationship must be visible to guest"
        assert "s04-l2-b" not in rel_target_ids, "Cross-L1 relationship must be excluded for guest"


# ===========================================================================
# Part 9: Guest tasks-by-entity must reject out-of-scope entity IDs
# ===========================================================================

S04_TASK_IN_A = _make_task(
    id="task-in-a", title="Task in A", linked_entities=["s04-l2-a"],
)
S04_TASK_IN_B = _make_task(
    id="task-in-b", title="Task in B", linked_entities=["s04-l2-b"],
)
S04_TASK_CROSS = _make_task(
    id="task-cross", title="Task cross", linked_entities=["s04-l2-a", "s04-l2-b"],
)


@pytest.mark.asyncio
class TestGuestTasksByEntityRejectsOutOfScope:
    """Guest calling tasks/by-entity/{entityId} with a public but out-of-scope
    entity must get an empty result — even if tasks exist that are also linked
    to an in-scope entity."""

    async def test_guest_cannot_list_tasks_for_out_of_scope_public_entity(self):
        """Out-of-scope entity ID is rejected before any task query runs."""
        from zenos.interface.dashboard_api import list_tasks_by_entity

        request = _make_request(
            headers={"authorization": "Bearer fake"},
            path_params={"entityId": "s04-l2-b"},  # under L1-B, guest only has L1-A
        )

        with patch("zenos.interface.dashboard_api._verify_firebase_token", return_value={"email": "guest@test.com"}), \
             patch("zenos.interface.dashboard_api._get_partner_by_email_sql", return_value=S04_GUEST_PARTNER), \
             patch("zenos.interface.dashboard_api._ensure_repos", new=AsyncMock()), \
             patch("zenos.interface.dashboard_api._entity_repo") as mock_entity_repo, \
             patch("zenos.interface.dashboard_api._task_repo") as mock_task_repo:
            mock_entity_repo.list_all = AsyncMock(return_value=S04_ALL_ENTITIES)
            # task_repo should never be called — scope rejection happens first
            mock_task_repo.list_all = AsyncMock(return_value=[S04_TASK_CROSS])
            resp = await list_tasks_by_entity(request)

        body = json.loads(resp.body)
        assert body["tasks"] == [], "Guest must not see tasks for out-of-scope entity"
        # Verify that task_repo was not queried (early rejection)
        mock_task_repo.list_all.assert_not_called()

    async def test_guest_can_list_tasks_for_in_scope_entity(self):
        """In-scope entity ID passes the guard and returns matching tasks."""
        from zenos.interface.dashboard_api import list_tasks_by_entity

        request = _make_request(
            headers={"authorization": "Bearer fake"},
            path_params={"entityId": "s04-l2-a"},  # under L1-A, guest has L1-A
        )

        with patch("zenos.interface.dashboard_api._verify_firebase_token", return_value={"email": "guest@test.com"}), \
             patch("zenos.interface.dashboard_api._get_partner_by_email_sql", return_value=S04_GUEST_PARTNER), \
             patch("zenos.interface.dashboard_api._ensure_repos", new=AsyncMock()), \
             patch("zenos.interface.dashboard_api._entity_repo") as mock_entity_repo, \
             patch("zenos.interface.dashboard_api._task_repo") as mock_task_repo:
            mock_entity_repo.list_all = AsyncMock(return_value=S04_ALL_ENTITIES)
            mock_entity_repo.get_by_id = AsyncMock(return_value=S04_L2_A)
            mock_task_repo.list_all = AsyncMock(return_value=[S04_TASK_IN_A])
            resp = await list_tasks_by_entity(request)

        body = json.loads(resp.body)
        task_ids = [t["id"] for t in body["tasks"]]
        assert "task-in-a" in task_ids, "Guest should see task linked to in-scope entity"
