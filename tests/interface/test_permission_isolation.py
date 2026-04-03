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

from zenos.application.ontology_service import UpsertEntityResult
from zenos.domain.models import Blindspot, Entity, Tags, Task
from zenos.infrastructure.context import current_partner_department, current_partner_roles


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
    "isAdmin": False,
    "sharedPartnerId": None,
    "defaultProject": None,
    "roles": [],
    "department": "all",
    "authorizedEntityIds": ["product-acme"],
}

# Scoped partner with null/empty authorized_entity_ids (behaves like internal member)
INTERNAL_EMPTY_SCOPE_PARTNER = {
    "id": "p-internal",
    "email": "internal@test.com",
    "displayName": "Internal User",
    "apiKey": "key-internal",  # pragma: allowlist secret
    "status": "active",
    "isAdmin": False,
    "sharedPartnerId": None,
    "defaultProject": None,
    "roles": [],
    "department": "all",
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

    async def test_marketing_only_sees_public_tasks(self):
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
        assert "task-restricted" not in task_ids, "Restricted task should be hidden from marketing"
        assert "task-confidential" not in task_ids, "Confidential task should be hidden from marketing"
        assert "task-mixed" not in task_ids, "Mixed task (has confidential entity) should be hidden"

    async def test_finance_cannot_see_restricted_or_confidential(self):
        """Per new permission model: restricted is admin-only, non-admin cannot see it."""
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
        assert "task-restricted" not in task_ids, "Restricted is now admin-only, finance cannot see it"
        assert "task-confidential" not in task_ids, "Confidential is admin-only"
        assert "task-mixed" not in task_ids, "Mixed task hidden (has restricted/confidential entity)"

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

    async def test_marketing_sees_public_and_mixed_blindspots(self):
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
        assert "bs-restricted" not in bs_ids, "Restricted blindspot hidden from marketing"
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
        from zenos.interface.tools import _current_partner
        self._tokens.append(("partner", _current_partner.set(self.partner)))
        self._tokens.append(("roles", current_partner_roles.set(self.partner.get("roles", []))))
        self._tokens.append(("dept", current_partner_department.set(self.partner.get("department", "all"))))
        return self

    def __exit__(self, *args):
        from zenos.interface.tools import _current_partner
        for name, token in reversed(self._tokens):
            if name == "partner":
                _current_partner.reset(token)
            elif name == "roles":
                current_partner_roles.reset(token)
            elif name == "dept":
                current_partner_department.reset(token)


@pytest.fixture(autouse=True)
def _mock_mcp_bootstrap():
    with patch("zenos.interface.tools._ensure_services", new=AsyncMock(return_value=None)), \
         patch("zenos.interface.tools.ontology_service", new=AsyncMock()), \
         patch("zenos.interface.tools.task_service", new=AsyncMock()), \
         patch("zenos.interface.tools.entity_repo", new=AsyncMock()), \
         patch("zenos.interface.tools.entry_repo", new=AsyncMock()):
        yield


@pytest.mark.asyncio
class TestMcpTaskIsolation:
    """MCP search/get tools should filter tasks by linked entity visibility."""

    async def test_marketing_cannot_search_restricted_tasks(self):
        from zenos.interface.tools import search

        with _McpPartnerContext(MARKETING_PARTNER):
            with patch("zenos.interface.tools.task_service") as mock_ts, \
                 patch("zenos.interface.tools.entity_repo") as mock_repo:
                mock_ts.list_tasks = AsyncMock(return_value=ALL_TASKS)
                mock_repo.get_by_id = AsyncMock(side_effect=_mock_entity_get_by_id)
                result = await search(collection="tasks")

        task_ids = [t["id"] for t in result["tasks"]]
        assert "task-pub" in task_ids
        assert "task-restricted" not in task_ids
        assert "task-confidential" not in task_ids

    async def test_admin_sees_all_via_mcp(self):
        from zenos.interface.tools import search

        with _McpPartnerContext(ADMIN_PARTNER):
            with patch("zenos.interface.tools.task_service") as mock_ts, \
                 patch("zenos.interface.tools.entity_repo") as mock_repo:
                mock_ts.list_tasks = AsyncMock(return_value=ALL_TASKS)
                mock_repo.get_by_id = AsyncMock(side_effect=_mock_entity_get_by_id)
                result = await search(collection="tasks")

        task_ids = [t["id"] for t in result["tasks"]]
        assert len(task_ids) == 4

    async def test_mcp_write_blocked_for_invisible_entity(self):
        from zenos.interface.tools import write

        with _McpPartnerContext(MARKETING_PARTNER):
            with patch("zenos.interface.tools.entity_repo") as mock_repo:
                mock_repo.get_by_id = AsyncMock(return_value=CONFIDENTIAL_ENTITY)
                mock_repo.get_by_name = AsyncMock(return_value=CONFIDENTIAL_ENTITY)
                result = await write(
                    collection="entities",
                    data={"id": "ent-confidential", "summary": "hacked"},
                )

        assert result["error"] == "FORBIDDEN"


# ===========================================================================
# Part 4: Cross-layer consistency
# ===========================================================================

@pytest.mark.asyncio
class TestCrossLayerConsistency:
    """Both API layers should produce the same visibility results."""

    async def test_same_tasks_visible_in_both_layers(self):
        """Marketing user should see the same tasks via Dashboard API and MCP tools."""
        from zenos.interface.tools import search as mcp_search
        from zenos.interface.dashboard_api import list_tasks as api_list_tasks

        # MCP layer
        with _McpPartnerContext(MARKETING_PARTNER):
            with patch("zenos.interface.tools.task_service") as mock_ts, \
                 patch("zenos.interface.tools.entity_repo") as mock_repo:
                mock_ts.list_tasks = AsyncMock(return_value=ALL_TASKS)
                mock_repo.get_by_id = AsyncMock(side_effect=_mock_entity_get_by_id)
                mcp_result = await mcp_search(collection="tasks")

        mcp_task_ids = set(t["id"] for t in mcp_result["tasks"])

        # Dashboard API layer
        request = _make_request(headers={"authorization": "Bearer fake"})
        with patch("zenos.interface.dashboard_api._verify_firebase_token", return_value={"email": "marketing@test.com"}), \
             patch("zenos.interface.dashboard_api._get_partner_by_email_sql", return_value=MARKETING_PARTNER), \
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

    async def test_empty_authorized_entity_ids_behaves_like_internal(self):
        """DC-10: null/empty authorized_entity_ids partner behaves like internal member."""
        from zenos.interface.dashboard_api import list_entities

        request = _make_request(headers={"authorization": "Bearer fake"})

        with patch("zenos.interface.dashboard_api._verify_firebase_token", return_value={"email": "internal@test.com"}), \
             patch("zenos.interface.dashboard_api._get_partner_by_email_sql", return_value=INTERNAL_EMPTY_SCOPE_PARTNER), \
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
        # Still cannot see restricted/confidential
        assert "ent-restricted" not in entity_ids
        assert "ent-confidential" not in entity_ids


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

    async def test_mcp_scoped_partner_sees_no_blindspots(self):
        """DC-7: MCP search(collection='blindspots') returns empty for scoped partner."""
        from zenos.interface.tools import search

        with _McpPartnerContext(SCOPED_PARTNER):
            with patch("zenos.interface.tools.ontology_service") as mock_os, \
                 patch("zenos.interface.tools.entity_repo") as mock_repo:
                mock_os.list_blindspots = AsyncMock(return_value=ALL_BLINDSPOTS)
                mock_repo.get_by_id = AsyncMock(side_effect=_mock_scoped_entity_get_by_id)
                result = await search(collection="blindspots")

        assert result["blindspots"] == [], "Scoped partner should see no blindspots via MCP"


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
        from zenos.interface.tools import search

        with _McpPartnerContext(SCOPED_PARTNER):
            with patch("zenos.interface.tools.task_service") as mock_ts, \
                 patch("zenos.interface.tools.entity_repo") as mock_repo:
                mock_ts.list_tasks = AsyncMock(return_value=ALL_SCOPED_TASKS)
                mock_repo.get_by_id = AsyncMock(side_effect=_mock_scoped_entity_get_by_id)
                mock_repo.list_all = AsyncMock(return_value=list(SCOPED_ALL_ENTITIES))
                result = await search(collection="tasks")

        task_ids = [t["id"] for t in result["tasks"]]
        assert "task-in-l1" in task_ids, "Task in authorized L1 should be visible via MCP"
        assert "task-out-l1" not in task_ids, "Task outside authorized L1 should be hidden via MCP"
        assert "task-no-link" not in task_ids, "Unlinked task should not be visible to scoped partner via MCP"


@pytest.mark.asyncio
class TestRestrictedAdminOnly:
    """DC-1, DC-2: restricted and confidential entities are admin-only for internal members."""

    async def test_internal_non_admin_cannot_see_restricted_entity(self):
        """DC-1: restricted entity is not visible to internal non-admin members."""
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
        assert "ent-restricted" not in entity_ids, "Restricted entity is admin-only"
        assert "ent-confidential" not in entity_ids, "Confidential entity is admin-only"

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
class TestRoleRestrictedVisibility:
    """DC-3: role-restricted entities are only visible to matching roles."""

    async def test_role_restricted_visible_to_matching_role(self):
        """DC-3: partner with matching role sees role-restricted entity."""
        from zenos.application.ontology_service import OntologyService

        role_restricted = _make_entity(
            id="ent-role",
            name="Finance Dashboard",
            visibility="role-restricted",
            visible_to_roles=["finance"],
        )
        finance_partner = {
            "id": "p-finance",
            "isAdmin": False,
            "roles": ["finance"],
            "authorizedEntityIds": None,
        }
        assert OntologyService.is_entity_visible_for_partner(role_restricted, finance_partner) is True

    async def test_role_restricted_hidden_from_non_matching_role(self):
        """DC-3: partner without matching role cannot see role-restricted entity."""
        from zenos.application.ontology_service import OntologyService

        role_restricted = _make_entity(
            id="ent-role",
            name="Finance Dashboard",
            visibility="role-restricted",
            visible_to_roles=["finance"],
        )
        marketing_partner = {
            "id": "p-marketing",
            "isAdmin": False,
            "roles": ["marketing"],
            "authorizedEntityIds": None,
        }
        assert OntologyService.is_entity_visible_for_partner(role_restricted, marketing_partner) is False

    async def test_role_restricted_hidden_from_scoped_partner(self):
        """DC-3: scoped partners cannot see role-restricted entities regardless of roles."""
        from zenos.application.ontology_service import OntologyService

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
# Part 6: DC-1 fix — MCP _is_task_visible scoped partner ignores entity visibility
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
class TestScopedPartnerTaskVisibilityIgnoresEntityVisibility:
    """DC-1: MCP _is_task_visible scoped partner path must not filter by entity visibility.

    A task linked to a restricted entity that is inside the scoped partner's L1 subtree
    MUST be visible to the scoped partner.
    """

    async def test_mcp_scoped_partner_sees_task_linked_to_restricted_entity_in_l1(self):
        """DC-1: task linked to restricted entity in L1 scope is visible to scoped partner."""
        from zenos.interface.tools import search

        tasks = [SCOPED_TASK_RESTRICTED_IN_L1, SCOPED_TASK_OUT_L1, SCOPED_TASK_NO_LINK]

        with _McpPartnerContext(SCOPED_PARTNER):
            with patch("zenos.interface.tools.task_service") as mock_ts, \
                 patch("zenos.interface.tools.entity_repo") as mock_repo:
                mock_ts.list_tasks = AsyncMock(return_value=tasks)
                mock_repo.list_all = AsyncMock(return_value=SCOPED_ALL_ENTITIES_WITH_RESTRICTED)
                result = await search(collection="tasks")

        task_ids = [t["id"] for t in result["tasks"]]
        assert "task-restricted-in-l1" in task_ids, (
            "Scoped partner must see tasks linked to restricted entities within their L1 scope"
        )
        assert "task-out-l1" not in task_ids, "Task outside L1 scope remains hidden"
        assert "task-no-link" not in task_ids, "Unlinked task remains hidden"

    async def test_mcp_scoped_partner_and_dashboard_api_task_visibility_consistent_for_restricted_entity(self):
        """DC-2: MCP and Dashboard API agree on task visibility for restricted entity in L1 scope."""
        from zenos.interface.tools import search as mcp_search
        from zenos.interface.dashboard_api import list_tasks as api_list_tasks

        tasks = [SCOPED_TASK_RESTRICTED_IN_L1, SCOPED_TASK_OUT_L1, SCOPED_TASK_NO_LINK]

        # MCP layer
        with _McpPartnerContext(SCOPED_PARTNER):
            with patch("zenos.interface.tools.task_service") as mock_ts, \
                 patch("zenos.interface.tools.entity_repo") as mock_repo:
                mock_ts.list_tasks = AsyncMock(return_value=tasks)
                mock_repo.list_all = AsyncMock(return_value=SCOPED_ALL_ENTITIES_WITH_RESTRICTED)
                mcp_result = await mcp_search(collection="tasks")

        mcp_task_ids = set(t["id"] for t in mcp_result["tasks"])

        # Dashboard API layer
        request = _make_request(headers={"authorization": "Bearer fake"})
        with patch("zenos.interface.dashboard_api._verify_firebase_token", return_value={"email": "client@external.com"}), \
             patch("zenos.interface.dashboard_api._get_partner_by_email_sql", return_value=SCOPED_PARTNER), \
             patch("zenos.interface.dashboard_api._ensure_repos", new=AsyncMock()), \
             patch("zenos.interface.dashboard_api._task_repo") as mock_task_repo, \
             patch("zenos.interface.dashboard_api._entity_repo") as mock_entity_repo:
            mock_task_repo.list_all = AsyncMock(return_value=tasks)
            mock_entity_repo.list_all = AsyncMock(return_value=SCOPED_ALL_ENTITIES_WITH_RESTRICTED)
            api_resp = await api_list_tasks(request)

        api_body = json.loads(api_resp.body)
        api_task_ids = set(t["id"] for t in api_body["tasks"])

        assert mcp_task_ids == api_task_ids, (
            f"MCP and Dashboard API must agree on task visibility for scoped partner. "
            f"MCP: {mcp_task_ids}, API: {api_task_ids}"
        )
        assert "task-restricted-in-l1" in mcp_task_ids, "Both layers should expose task"


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
