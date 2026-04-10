"""Tests for MCP tool handlers (interface layer).

Strategy: mock the service layer (ontology_service, task_service, source_service)
and test that each tool function correctly:
  - Routes to the right service method
  - Serializes results properly
  - Handles errors with correct error codes
  - Validates input parameters
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from zenos.application.knowledge.ontology_service import (
    DocumentSyncResult,
    EntityWithRelationships,
    UpsertEntityResult,
)
from zenos.domain.governance import TagConfidence
from zenos.domain.action import Task
from zenos.domain.knowledge import Blindspot, Document, DocumentTags, Entity, EntityEntry, Gap, Protocol, Relationship, Source, Tags
from zenos.domain.shared import QualityCheckItem, QualityReport, StalenessWarning
from zenos.infrastructure.context import current_partner_department, current_partner_roles


# ---------------------------------------------------------------------------
# Fixtures: reusable domain objects
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _mock_tool_bootstrap():
    """Avoid bootstrapping real SQL repos in interface unit tests."""
    with patch("zenos.interface.mcp._ensure_services", new=AsyncMock(return_value=None)), \
         patch("zenos.interface.mcp.ontology_service", new=AsyncMock()), \
         patch("zenos.interface.mcp.task_service", new=AsyncMock()), \
         patch("zenos.interface.mcp.entity_repo", new=AsyncMock()), \
         patch("zenos.interface.mcp.entry_repo", new=AsyncMock()):
        yield

def _make_entity(**overrides) -> Entity:
    defaults = dict(
        id="ent-1",
        name="Paceriz",
        type="product",
        summary="A running coach",
        tags=Tags(what="app", why="coaching", how="AI", who="runners"),
        status="active",
        parent_id=None,
        confirmed_by_user=True,
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        updated_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
    )
    defaults.update(overrides)
    return Entity(**defaults)


def _make_task(**overrides) -> Task:
    defaults = dict(
        id="task-1",
        title="Fix login",
        status="todo",
        priority="high",
        created_by="architect",
        description="Login broken on iOS",
        assignee="developer",
        created_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
        updated_at=datetime(2026, 3, 20, tzinfo=timezone.utc),
    )
    defaults.update(overrides)
    return Task(**defaults)


def _make_document(**overrides) -> Document:
    defaults = dict(
        id="doc-1",
        title="API Spec",
        source=Source(type="github", uri="https://github.com/...", adapter="github"),
        tags=DocumentTags(what=["api"], why="reference", how="REST", who=["developer"]),
        summary="API specification document",
        linked_entity_ids=["ent-1"],
        status="current",
        confirmed_by_user=True,
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        updated_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
    )
    defaults.update(overrides)
    return Document(**defaults)


def _make_blindspot(**overrides) -> Blindspot:
    defaults = dict(
        id="bs-1",
        description="No monitoring",
        severity="red",
        related_entity_ids=["ent-1"],
        suggested_action="Add monitoring",
        status="open",
        confirmed_by_user=False,
        created_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
    )
    defaults.update(overrides)
    return Blindspot(**defaults)


def _make_protocol(**overrides) -> Protocol:
    defaults = dict(
        id="proto-1",
        entity_id="ent-1",
        entity_name="Paceriz",
        content={"what": {}, "why": {}, "how": {}, "who": {}},
        gaps=[],
        confirmed_by_user=False,
        generated_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
        updated_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
    )
    defaults.update(overrides)
    return Protocol(**defaults)


# ---------------------------------------------------------------------------
# Tool 1: search
# ---------------------------------------------------------------------------

class TestSearchTool:
    """Tests for the search MCP tool."""

    async def test_keyword_search_cross_collection(self):
        from zenos.interface.mcp import search

        entity = _make_entity()
        with patch("zenos.interface.mcp.ontology_service") as mock_os, \
             patch("zenos.interface.mcp.task_service") as mock_ts:
            mock_os.search = AsyncMock(return_value=[entity])
            mock_ts.list_tasks = AsyncMock(return_value=[])

            result = await search(query="Paceriz", collection="all")

            assert "results" in result
            assert result["count"] == 1
            mock_os.search.assert_called_once_with(
                "Paceriz", max_level=2, product_id=None,
            )

    async def test_list_entities_collection(self):
        from zenos.interface.mcp import search

        entities = [_make_entity(), _make_entity(id="ent-2", name="ZenOS")]
        with patch("zenos.interface.mcp.ontology_service") as mock_os:
            mock_os.list_entities = AsyncMock(return_value=entities)

            result = await search(collection="entities")

            assert "entities" in result
            assert len(result["entities"]) == 2

    async def test_list_entities_with_confirmed_filter(self):
        from zenos.interface.mcp import search

        entities = [
            _make_entity(confirmed_by_user=True),
            _make_entity(id="ent-2", confirmed_by_user=False),
        ]
        with patch("zenos.interface.mcp.ontology_service") as mock_os:
            mock_os.list_entities = AsyncMock(return_value=entities)

            result = await search(collection="entities", confirmed_only=True)

            assert len(result["entities"]) == 1

    async def test_list_tasks_with_assignee(self):
        from zenos.interface.mcp import search

        tasks = [_make_task()]
        with patch("zenos.interface.mcp.task_service") as mock_ts:
            mock_ts.list_tasks = AsyncMock(return_value=tasks)

            result = await search(collection="tasks", assignee="developer")

            mock_ts.list_tasks.assert_called_once_with(
                assignee="developer",
                created_by=None,
                status=None,
                limit=200,
                offset=0,
                project=None,
                plan_id=None,
            )
            assert "tasks" in result

    async def test_list_tasks_with_status_filter(self):
        from zenos.interface.mcp import search

        with patch("zenos.interface.mcp.task_service") as mock_ts:
            mock_ts.list_tasks = AsyncMock(return_value=[])

            await search(collection="tasks", status="todo,in_progress")

            mock_ts.list_tasks.assert_called_once_with(
                assignee=None,
                created_by=None,
                status=["todo", "in_progress"],
                limit=200,
                offset=0,
                project=None,
                plan_id=None,
            )

    async def test_empty_keyword_search(self):
        """Empty query with collection=all should list all collections."""
        from zenos.interface.mcp import search

        with patch("zenos.interface.mcp.ontology_service") as mock_os, \
             patch("zenos.interface.mcp.task_service") as mock_ts:
            mock_os.list_entities = AsyncMock(return_value=[])
            mock_os._entities = AsyncMock()
            mock_os._entities.list_all = AsyncMock(return_value=[])
            mock_os._protocols = AsyncMock()
            mock_os._protocols.list_unconfirmed = AsyncMock(return_value=[])
            mock_os.list_blindspots = AsyncMock(return_value=[])
            mock_ts.list_tasks = AsyncMock(return_value=[])

            result = await search(query="", collection="all")

            assert "entities" in result
            assert "tasks" in result

    async def test_limit_respected(self):
        from zenos.interface.mcp import search

        entities = [_make_entity(id=f"ent-{i}") for i in range(10)]
        with patch("zenos.interface.mcp.ontology_service") as mock_os:
            mock_os.list_entities = AsyncMock(return_value=entities)

            result = await search(collection="entities", limit=3)

            assert len(result["entities"]) == 3

    async def test_entities_confidential_hidden_for_member(self):
        from zenos.interface.mcp import search, _current_partner

        restricted = _make_entity(
            id="ent-r",
            visibility="confidential",
        )
        token_partner = _current_partner.set({"id": "p-marketing", "isAdmin": False})
        token_roles = current_partner_roles.set(["marketing"])
        token_dept = current_partner_department.set("marketing")
        try:
            with patch("zenos.interface.mcp.ontology_service") as mock_os:
                mock_os.list_entities = AsyncMock(return_value=[restricted])
                result = await search(collection="entities")
            assert result["entities"] == []
        finally:
            current_partner_department.reset(token_dept)
            current_partner_roles.reset(token_roles)
            _current_partner.reset(token_partner)

    async def test_entities_department_filter_blocks_other_department(self):
        from zenos.interface.mcp import search, _current_partner

        restricted = _make_entity(
            id="ent-d",
            visibility="public",
            visible_to_departments=["finance"],
        )
        token_partner = _current_partner.set({"id": "p-eng", "isAdmin": False})
        token_roles = current_partner_roles.set(["engineering"])
        token_dept = current_partner_department.set("engineering")
        try:
            with patch("zenos.interface.mcp.ontology_service") as mock_os:
                mock_os.list_entities = AsyncMock(return_value=[restricted])
                result = await search(collection="entities")
            assert result["entities"] == []
        finally:
            current_partner_department.reset(token_dept)
            current_partner_roles.reset(token_roles)
            _current_partner.reset(token_partner)

    async def test_entities_admin_can_see_confidential(self):
        from zenos.interface.mcp import search, _current_partner

        confidential = _make_entity(
            id="ent-c",
            visibility="confidential",
            visible_to_members=["p-admin"],
        )
        token_partner = _current_partner.set({"id": "p-admin", "isAdmin": True})
        token_roles = current_partner_roles.set([])
        token_dept = current_partner_department.set("all")
        try:
            with patch("zenos.interface.mcp.ontology_service") as mock_os:
                mock_os.list_entities = AsyncMock(return_value=[confidential])
                result = await search(collection="entities")
            assert len(result["entities"]) == 1
            assert result["entities"][0]["id"] == "ent-c"
        finally:
            current_partner_department.reset(token_dept)
            current_partner_roles.reset(token_roles)
            _current_partner.reset(token_partner)

    async def test_documents_collection_query_filters_by_source_uri(self):
        from zenos.interface.mcp import search

        doc_hit = _make_entity(
            id="doc-1",
            name="Spec A",
            type="document",
            summary="spec",
            sources=[{"uri": "https://github.com/acme/repo/blob/main/docs/spec-a.md", "label": "spec-a.md", "type": "github"}],
        )
        doc_miss = _make_entity(
            id="doc-2",
            name="Spec B",
            type="document",
            summary="spec",
            sources=[{"uri": "https://github.com/acme/repo/blob/main/docs/spec-b.md", "label": "spec-b.md", "type": "github"}],
        )
        with patch("zenos.interface.mcp.ontology_service") as mock_os:
            mock_os._entities = AsyncMock()
            mock_os._entities.list_all = AsyncMock(return_value=[doc_hit, doc_miss])
            mock_os._entities.get_by_name = AsyncMock(return_value=None)

            result = await search(
                collection="documents",
                query="spec-a.md",
            )

            assert "documents" in result
            assert [d["id"] for d in result["documents"]] == ["doc-1"]


class TestSearchNewParams:
    """Tests for new search params: product_id, offset, entity_level."""

    async def test_offset_pagination_entities(self):
        """offset skips the first N results for collection listing."""
        from zenos.interface.mcp import search

        entities = [_make_entity(id=f"ent-{i}", name=f"E{i}") for i in range(5)]
        with patch("zenos.interface.mcp.ontology_service") as mock_os:
            mock_os.list_entities = AsyncMock(return_value=entities)
            result = await search(collection="entities", limit=2, offset=2)
            assert len(result["entities"]) == 2
            assert result["entities"][0]["id"] == "ent-2"

    async def test_offset_pagination_tasks(self):
        """offset is passed to task_service.list_tasks."""
        from zenos.interface.mcp import search

        with patch("zenos.interface.mcp.task_service") as mock_ts:
            mock_ts.list_tasks = AsyncMock(return_value=[])
            await search(collection="tasks", offset=10, limit=5)
            mock_ts.list_tasks.assert_called_once_with(
                assignee=None,
                created_by=None,
                status=None,
                limit=5,
                offset=10,
                project=None,
                plan_id=None,
            )

    async def test_entity_level_default_filters_l3(self):
        """Default entity_level=None filters out L3 entities."""
        from zenos.interface.mcp import search

        l1 = _make_entity(id="ent-l1", name="Product", level=1)
        l2 = _make_entity(id="ent-l2", name="Module", level=2)
        l3 = _make_entity(id="ent-l3", name="Detail", level=3)
        with patch("zenos.interface.mcp.ontology_service") as mock_os:
            mock_os.list_entities = AsyncMock(return_value=[l1, l2, l3])
            result = await search(collection="entities")
            ids = [e["id"] for e in result["entities"]]
            assert "ent-l1" in ids
            assert "ent-l2" in ids
            assert "ent-l3" not in ids

    async def test_entity_level_all_includes_l3(self):
        """entity_level='all' includes L3 entities."""
        from zenos.interface.mcp import search

        l3 = _make_entity(id="ent-l3", name="Detail", level=3)
        with patch("zenos.interface.mcp.ontology_service") as mock_os:
            mock_os.list_entities = AsyncMock(return_value=[l3])
            result = await search(collection="entities", entity_level="all")
            assert len(result["entities"]) == 1

    async def test_entity_level_l1_only(self):
        """entity_level='L1' filters out L2 and L3."""
        from zenos.interface.mcp import search

        l1 = _make_entity(id="ent-l1", name="Product", level=1)
        l2 = _make_entity(id="ent-l2", name="Module", level=2)
        with patch("zenos.interface.mcp.ontology_service") as mock_os:
            mock_os.list_entities = AsyncMock(return_value=[l1, l2])
            result = await search(collection="entities", entity_level="L1")
            ids = [e["id"] for e in result["entities"]]
            assert "ent-l1" in ids
            assert "ent-l2" not in ids

    async def test_entity_level_none_level_treated_as_l1(self):
        """Entities with level=None are treated as L1 (included in default)."""
        from zenos.interface.mcp import search

        no_level = _make_entity(id="ent-nolevel", name="Legacy")
        # level defaults to None in Entity
        assert no_level.level is None
        with patch("zenos.interface.mcp.ontology_service") as mock_os:
            mock_os.list_entities = AsyncMock(return_value=[no_level])
            result = await search(collection="entities")
            assert len(result["entities"]) == 1

    async def test_product_id_filters_entities_to_subtree(self):
        """product_id filters entities to the product's subtree."""
        from zenos.interface.mcp import search

        product = _make_entity(id="prod-1", name="MyApp", type="product", level=1)
        child = _make_entity(id="mod-1", name="Auth", type="module", level=2, parent_id="prod-1")
        unrelated = _make_entity(id="mod-2", name="Billing", type="module", level=2, parent_id="prod-other")
        with patch("zenos.interface.mcp.ontology_service") as mock_os:
            mock_os.list_entities = AsyncMock(return_value=[product, child, unrelated])
            result = await search(collection="entities", product_id="prod-1")
            ids = [e["id"] for e in result["entities"]]
            assert "prod-1" in ids
            assert "mod-1" in ids
            assert "mod-2" not in ids

    async def test_keyword_search_passes_max_level_and_product_id(self):
        """Keyword search passes max_level and product_id to ontology_service.search."""
        from zenos.interface.mcp import search

        with patch("zenos.interface.mcp.ontology_service") as mock_os, \
             patch("zenos.interface.mcp.task_service") as mock_ts:
            mock_os.search = AsyncMock(return_value=[])
            mock_ts.list_tasks = AsyncMock(return_value=[])
            await search(query="test", collection="all", entity_level="L1", product_id="prod-1")
            mock_os.search.assert_called_once_with(
                "test", max_level=1, product_id="prod-1",
            )

    async def test_keyword_search_offset_pagination(self):
        """Keyword search with offset paginates the results."""
        from zenos.interface.mcp import search
        from zenos.domain.search import SearchResult

        results = [
            SearchResult(type="entity", id=f"ent-{i}", name=f"E{i}", summary="s", score=1.0)
            for i in range(5)
        ]
        with patch("zenos.interface.mcp.ontology_service") as mock_os, \
             patch("zenos.interface.mcp.task_service") as mock_ts:
            mock_os.search = AsyncMock(return_value=results)
            mock_ts.list_tasks = AsyncMock(return_value=[])
            result = await search(query="test", collection="all", offset=2, limit=2)
            assert result["count"] == 2
            assert result["total"] == 5
            assert result["results"][0]["id"] == "ent-2"

    async def test_search_with_product_name(self):
        """product name resolves to product_id via get_by_name."""
        from zenos.interface.mcp import search
        from zenos.domain.search import SearchResult

        product_entity = _make_entity(id="prod-abc", name="Paceriz", type="product")
        with patch("zenos.interface.mcp.entity_repo") as mock_repo, \
             patch("zenos.interface.mcp.ontology_service") as mock_os, \
             patch("zenos.interface.mcp.task_service") as mock_ts:
            mock_repo.get_by_name = AsyncMock(return_value=product_entity)
            mock_os.search = AsyncMock(return_value=[])
            mock_ts.list_tasks = AsyncMock(return_value=[])

            await search(query="test", collection="all", product="Paceriz")

            mock_repo.get_by_name.assert_called_once_with("Paceriz")
            mock_os.search.assert_called_once_with(
                "test", max_level=2, product_id="prod-abc",
            )

    async def test_search_with_invalid_product_name(self):
        """product name not found returns error dict."""
        from zenos.interface.mcp import search

        with patch("zenos.interface.mcp.entity_repo") as mock_repo:
            mock_repo.get_by_name = AsyncMock(return_value=None)

            result = await search(query="test", collection="all", product="NonExistent")

            assert "error" in result
            assert "NonExistent" in result["error"]
            assert "hint" in result

    async def test_search_product_name_takes_priority(self):
        """When both product and product_id are passed, product takes priority."""
        from zenos.interface.mcp import search

        product_entity = _make_entity(id="prod-from-name", name="Paceriz", type="product")
        with patch("zenos.interface.mcp.entity_repo") as mock_repo, \
             patch("zenos.interface.mcp.ontology_service") as mock_os, \
             patch("zenos.interface.mcp.task_service") as mock_ts:
            mock_repo.get_by_name = AsyncMock(return_value=product_entity)
            mock_os.search = AsyncMock(return_value=[])
            mock_ts.list_tasks = AsyncMock(return_value=[])

            # Pass both; product should win
            await search(query="test", collection="all", product="Paceriz", product_id="prod-ignored")

            mock_os.search.assert_called_once_with(
                "test", max_level=2, product_id="prod-from-name",
            )


class TestParseEntityLevel:
    """Tests for _parse_entity_level helper."""

    def test_none_defaults_to_2(self):
        from zenos.interface.mcp import _parse_entity_level
        assert _parse_entity_level(None) == 2

    def test_all_returns_none(self):
        from zenos.interface.mcp import _parse_entity_level
        assert _parse_entity_level("all") is None

    def test_l1_returns_1(self):
        from zenos.interface.mcp import _parse_entity_level
        assert _parse_entity_level("L1") == 1

    def test_l2_returns_2(self):
        from zenos.interface.mcp import _parse_entity_level
        assert _parse_entity_level("L2") == 2

    def test_l1_l2_returns_2(self):
        from zenos.interface.mcp import _parse_entity_level
        assert _parse_entity_level("L1,L2") == 2

    def test_l1_l2_l3_returns_none(self):
        from zenos.interface.mcp import _parse_entity_level
        assert _parse_entity_level("L1,L2,L3") is None

    def test_case_insensitive(self):
        from zenos.interface.mcp import _parse_entity_level
        assert _parse_entity_level("l1") == 1
        assert _parse_entity_level("ALL") is None


# ---------------------------------------------------------------------------
# Tool 2: get
# ---------------------------------------------------------------------------

class TestGetTool:
    """Tests for the get MCP tool."""

    async def test_get_entity_by_name(self):
        from zenos.interface.mcp import get

        entity = _make_entity()
        rels = [Relationship(source_entity_id="ent-1", target_id="ent-2",
                             type="depends_on", description="test")]
        ewr = EntityWithRelationships(entity=entity, relationships=rels)

        with patch("zenos.interface.mcp.ontology_service") as mock_os:
            mock_os.get_entity = AsyncMock(return_value=ewr)

            result = await get(collection="entities", name="Paceriz")

            assert result["entity"]["name"] == "Paceriz"
            assert len(result["outgoing_relationships"]) == 1
            assert len(result["incoming_relationships"]) == 0

    async def test_get_entity_by_id(self):
        from zenos.interface.mcp import get

        entity = _make_entity()
        with patch("zenos.interface.mcp.entity_repo") as mock_er, \
             patch("zenos.interface.mcp.relationship_repo") as mock_rr:
            mock_er.get_by_id = AsyncMock(return_value=entity)
            mock_rr.list_by_entity = AsyncMock(return_value=[])

            result = await get(collection="entities", id="ent-1")

            assert result["entity"]["id"] == "ent-1"

    async def test_guest_get_entity_enforces_shared_l1_scope(self):
        from zenos.interface.mcp import get, _current_partner

        shared_root = _make_entity(id="product-acme", type="product", level=1, name="Acme", parent_id=None)
        shared_child = _make_entity(
            id="ent-shared",
            name="Shared Module",
            type="module",
            level=2,
            parent_id="product-acme",
            visibility="public",
        )
        other_root = _make_entity(id="product-other", type="product", level=1, name="Other", parent_id=None)
        other_child = _make_entity(
            id="ent-other",
            name="Other Module",
            type="module",
            level=2,
            parent_id="product-other",
            visibility="public",
        )

        token = _current_partner.set(
            {
                "id": "p-guest",
                "isAdmin": False,
                "workspaceRole": "guest",
                "authorizedEntityIds": ["product-acme"],
            }
        )
        try:
            with patch("zenos.interface.mcp.entity_repo") as mock_er, \
                 patch("zenos.interface.mcp.relationship_repo") as mock_rr, \
                 patch("zenos.interface.mcp.ontology_service") as mock_os:
                mock_er.list_all = AsyncMock(return_value=[shared_root, shared_child, other_root, other_child])
                mock_er.get_by_id = AsyncMock(side_effect=lambda eid: {
                    "ent-shared": shared_child,
                    "ent-other": other_child,
                }.get(eid))
                mock_rr.list_by_entity = AsyncMock(return_value=[])
                mock_os.get_entity = AsyncMock(side_effect=lambda name: None)

                allowed = await get(collection="entities", id="ent-shared")
                denied = await get(collection="entities", id="ent-other")

                assert allowed["entity"]["id"] == "ent-shared"
                assert denied["error"] == "NOT_FOUND"
        finally:
            _current_partner.reset(token)

    async def test_guest_get_document_enforces_shared_l1_scope(self):
        from zenos.interface.mcp import get, _current_partner

        shared_root = _make_entity(id="product-acme", type="product", level=1, name="Acme", parent_id=None)
        shared_doc = _make_entity(
            id="doc-shared",
            name="Shared Doc",
            type="document",
            level=3,
            parent_id="product-acme",
            visibility="public",
        )
        other_root = _make_entity(id="product-other", type="product", level=1, name="Other", parent_id=None)
        other_doc = _make_entity(
            id="doc-other",
            name="Other Doc",
            type="document",
            level=3,
            parent_id="product-other",
            visibility="public",
        )

        token = _current_partner.set(
            {
                "id": "p-guest",
                "isAdmin": False,
                "workspaceRole": "guest",
                "authorizedEntityIds": ["product-acme"],
            }
        )
        try:
            with patch("zenos.interface.mcp.entity_repo") as mock_er, \
                 patch("zenos.interface.mcp.ontology_service") as mock_os:
                mock_er.list_all = AsyncMock(return_value=[shared_root, shared_doc, other_root, other_doc])
                mock_os.get_document = AsyncMock(side_effect=lambda doc_id: {
                    "doc-shared": shared_doc,
                    "doc-other": other_doc,
                }.get(doc_id))

                allowed = await get(collection="documents", id="doc-shared")
                denied = await get(collection="documents", id="doc-other")

                assert allowed["id"] == "doc-shared"
                assert denied["error"] == "NOT_FOUND"
        finally:
            _current_partner.reset(token)

    async def test_get_entity_not_found(self):
        from zenos.interface.mcp import get

        with patch("zenos.interface.mcp.ontology_service") as mock_os:
            mock_os.get_entity = AsyncMock(return_value=None)

            result = await get(collection="entities", name="NonExistent")

            assert result["error"] == "NOT_FOUND"

    async def test_get_no_name_no_id(self):
        from zenos.interface.mcp import get

        result = await get(collection="entities")

        assert result["error"] == "INVALID_INPUT"
        assert "Must provide" in result["message"]

    async def test_get_unknown_collection(self):
        from zenos.interface.mcp import get

        result = await get(collection="foobar", name="test")

        assert result["error"] == "INVALID_INPUT"
        assert "Unknown collection" in result["message"]

    async def test_get_task_by_id(self):
        from zenos.interface.mcp import get

        task = _make_task()
        enrichments = {"expanded_entities": []}
        with patch("zenos.interface.mcp.task_service") as mock_ts:
            mock_ts.get_task_enriched = AsyncMock(return_value=(task, enrichments))

            result = await get(collection="tasks", id="task-1")

            assert result["title"] == "Fix login"

    async def test_get_task_not_found(self):
        from zenos.interface.mcp import get

        with patch("zenos.interface.mcp.task_service") as mock_ts:
            mock_ts.get_task_enriched = AsyncMock(return_value=None)

            result = await get(collection="tasks", id="nonexistent")

            assert result["error"] == "NOT_FOUND"

    async def test_get_task_requires_id(self):
        from zenos.interface.mcp import get

        result = await get(collection="tasks", name="some-name")

        assert result["error"] == "INVALID_INPUT"
        assert "id" in result["message"].lower()

    async def test_get_blindspot_by_id(self):
        from zenos.interface.mcp import get

        bs = _make_blindspot()
        with patch("zenos.interface.mcp.blindspot_repo") as mock_br:
            mock_br.get_by_id = AsyncMock(return_value=bs)

            result = await get(collection="blindspots", id="bs-1")

            assert result["description"] == "No monitoring"

    async def test_get_document_by_id(self):
        from zenos.interface.mcp import get

        doc = _make_document()
        with patch("zenos.interface.mcp.ontology_service") as mock_os:
            mock_os.get_document = AsyncMock(return_value=doc)

            result = await get(collection="documents", id="doc-1")

            assert result["title"] == "API Spec"

    async def test_get_protocol_by_id_prefers_protocol_doc_id(self):
        from zenos.interface.mcp import get

        proto = _make_protocol(id="proto-1", entity_id="ent-1")
        with patch("zenos.interface.mcp.protocol_repo") as mock_pr:
            mock_pr.get_by_id = AsyncMock(return_value=proto)
            mock_pr.get_by_entity = AsyncMock(return_value=None)

            result = await get(collection="protocols", id="proto-1")

            assert result["id"] == "proto-1"
            mock_pr.get_by_id.assert_called_once_with("proto-1")
            mock_pr.get_by_entity.assert_not_called()


# ---------------------------------------------------------------------------
# Tool 3: read_source
# ---------------------------------------------------------------------------

class TestReadSourceTool:
    """Tests for the read_source MCP tool."""

    async def test_read_source_success(self):
        from zenos.interface.mcp import read_source

        with patch("zenos.interface.mcp.source_service") as mock_ss:
            mock_ss.read_source = AsyncMock(return_value="# Hello World")

            result = await read_source(doc_id="doc-1")

            assert result["doc_id"] == "doc-1"
            assert result["content"] == "# Hello World"

    async def test_read_source_not_found(self):
        from zenos.interface.mcp import read_source

        with patch("zenos.interface.mcp.source_service") as mock_ss:
            mock_ss.read_source = AsyncMock(side_effect=ValueError("Doc not found"))

            result = await read_source(doc_id="nonexistent")

            assert result["error"] == "NOT_FOUND"

    async def test_read_source_file_not_found(self):
        from zenos.interface.mcp import read_source

        with patch("zenos.interface.mcp.source_service") as mock_ss:
            mock_ss.read_source = AsyncMock(
                side_effect=FileNotFoundError("File missing"))

            result = await read_source(doc_id="doc-1")

            assert result["error"] == "NOT_FOUND"

    async def test_read_source_permission_error(self):
        from zenos.interface.mcp import read_source

        with patch("zenos.interface.mcp.source_service") as mock_ss:
            mock_ss.read_source = AsyncMock(
                side_effect=PermissionError("No access"))

            result = await read_source(doc_id="doc-1")

            assert result["error"] == "ADAPTER_ERROR"
            assert "Permission denied" in result["message"]

    async def test_read_source_runtime_error(self):
        from zenos.interface.mcp import read_source

        with patch("zenos.interface.mcp.source_service") as mock_ss:
            mock_ss.read_source = AsyncMock(
                side_effect=RuntimeError("Adapter broken"))

            result = await read_source(doc_id="doc-1")

            assert result["error"] == "ADAPTER_ERROR"


# ---------------------------------------------------------------------------
# Tool 4: write
# ---------------------------------------------------------------------------

class TestWriteTool:
    """Tests for the write MCP tool."""

    async def test_write_entity_success(self):
        from zenos.interface.mcp import write

        entity = _make_entity()
        upsert_result = UpsertEntityResult(
            entity=entity,
            tag_confidence=TagConfidence(
                confirmed_fields=["what", "who"],
                draft_fields=["why", "how"],
            ),
            split_recommendation=None,
            warnings=None,
        )

        with patch("zenos.interface.mcp.ontology_service") as mock_os:
            mock_os.upsert_entity = AsyncMock(return_value=upsert_result)

            result = await write(
                collection="entities",
                data={
                    "name": "Paceriz",
                    "type": "product",
                    "summary": "A running coach",
                    "tags": {"what": "app", "why": "coaching", "how": "AI", "who": "runners"},
                },
            )

            assert result["status"] == "ok"
            assert result["data"]["entity"]["name"] == "Paceriz"
            assert result["warnings"] == []
            assert "context_bundle" in result
            assert "governance_hints" in result

    async def test_guest_write_entity_is_rejected(self):
        """Guest attempting L1 entity write → application-layer guard raises PermissionError,
        interface layer converts it to status=rejected response."""
        from zenos.interface.mcp import write, _current_partner

        token = _current_partner.set(
            {
                "id": "p-guest",
                "isAdmin": False,
                "workspaceRole": "guest",
                "authorizedEntityIds": ["product-acme"],
            }
        )
        try:
            with patch("zenos.interface.mcp.entity_repo") as mock_er, \
                 patch("zenos.interface.mcp.ontology_service") as mock_os:
                # No pre-existing entity (new entity creation path)
                mock_er.get_by_id = AsyncMock(return_value=None)
                mock_er.get_by_name = AsyncMock(return_value=None)
                # Application-layer guard raises PermissionError for L1 entity creation
                mock_os.upsert_entity = AsyncMock(
                    side_effect=PermissionError(
                        "Guest partners cannot create L1 entities (type='product')."
                    )
                )
                result = await write(
                    collection="entities",
                    data={
                        "name": "Guest Entity",
                        "type": "product",
                        "summary": "not allowed",
                        "tags": {"what": "x", "why": "y", "how": "z", "who": "w"},
                    },
                )

            assert result["status"] == "rejected"
            assert "FORBIDDEN" in result["rejection_reason"]
            assert "Guest" in result["rejection_reason"]
        finally:
            _current_partner.reset(token)

    async def test_write_module_without_parent_id_returns_warning(self):
        from zenos.interface.mcp import write

        entity = _make_entity(type="module", parent_id=None)
        upsert_result = UpsertEntityResult(
            entity=entity,
            tag_confidence=TagConfidence(
                confirmed_fields=["what", "who"],
                draft_fields=["why", "how"],
            ),
            split_recommendation=None,
            warnings=["Module entity has no parent_id. "
                       "It will not appear under any product in the Dashboard. "
                       "Set parent_id to the owning product's entity ID."],
        )

        with patch("zenos.interface.mcp.ontology_service") as mock_os:
            mock_os.upsert_entity = AsyncMock(return_value=upsert_result)

            result = await write(
                collection="entities",
                data={
                    "name": "Training Plan",
                    "type": "module",
                    "summary": "Weekly plan generation",
                    "tags": {"what": "plan", "why": "training", "how": "AI", "who": "coach"},
                },
            )

            assert result["status"] == "ok"
            assert "warnings" in result
            assert "parent_id" in result["warnings"][0]

    async def test_write_entity_with_id_updates(self):
        from zenos.interface.mcp import write

        entity = _make_entity()
        upsert_result = UpsertEntityResult(
            entity=entity,
            tag_confidence=TagConfidence(confirmed_fields=[], draft_fields=[]),
            split_recommendation=None,
        )

        with patch("zenos.interface.mcp.ontology_service") as mock_os:
            mock_os.upsert_entity = AsyncMock(return_value=upsert_result)

            await write(
                collection="entities",
                data={"name": "X", "type": "product", "summary": "Y",
                      "tags": {"what": "", "why": "", "how": "", "who": ""}},
                id="ent-1",
            )

            call_data = mock_os.upsert_entity.call_args[0][0]
            assert call_data["id"] == "ent-1"

    async def test_write_unknown_collection(self):
        from zenos.interface.mcp import write

        result = await write(collection="foobar", data={})

        assert result["status"] == "rejected"
        assert "Unknown collection" in result["rejection_reason"]

    async def test_write_entity_missing_required_field(self):
        from zenos.interface.mcp import write

        with patch("zenos.interface.mcp.ontology_service") as mock_os:
            mock_os.upsert_entity = AsyncMock(side_effect=KeyError("name"))

            result = await write(collection="entities", data={})

            assert result["status"] == "rejected"

    async def test_write_documents_sync_mode_routes_to_sync_api(self):
        from zenos.interface.mcp import write

        doc_entity = _make_entity(id="doc-1", type="document", name="Spec", status="current")
        sync_result = DocumentSyncResult(
            operation="rename",
            dry_run=True,
            document_id="doc-1",
            before={"name": "Spec v1"},
            after={"name": "Spec v2"},
            relationship_changes={"add": [], "remove": []},
            document=doc_entity,
        )
        with patch("zenos.interface.mcp.ontology_service") as mock_os:
            mock_os.sync_document_governance = AsyncMock(return_value=sync_result)

            result = await write(
                collection="documents",
                data={
                    "sync_mode": "rename",
                    "id": "doc-1",
                    "title": "Spec v2",
                    "dry_run": True,
                },
            )

            assert result["status"] == "ok"
            assert result["data"]["operation"] == "rename"
            assert result["data"]["dry_run"] is True
            assert result["data"]["document_id"] == "doc-1"

    async def test_write_relationship_success(self):
        from zenos.interface.mcp import write

        rel = Relationship(
            id="rel-1",
            source_entity_id="ent-1",
            target_id="ent-2",
            type="depends_on",
            description="Training depends on data",
        )

        with patch("zenos.interface.mcp.ontology_service") as mock_os:
            mock_os.add_relationship = AsyncMock(return_value=rel)

            result = await write(
                collection="relationships",
                data={
                    "source_entity_id": "ent-1",
                    "target_entity_id": "ent-2",
                    "type": "depends_on",
                    "description": "Training depends on data",
                },
            )

            assert result["status"] == "ok"
            assert result["data"]["type"] == "depends_on"

    async def test_write_relationship_missing_field(self):
        from zenos.interface.mcp import write

        result = await write(
            collection="relationships",
            data={"source_entity_id": "ent-1"},  # missing target, type, description
        )

        assert result["status"] == "rejected"

    async def test_write_red_blindspot_skips_duplicate_open_task(self):
        from zenos.interface.mcp import write

        blindspot = _make_blindspot(id="bs-1", severity="red")
        existing_task = _make_task(
            id="task-dup",
            status="backlog",
            linked_blindspot="bs-1",
            source_type="blindspot",
        )
        with patch("zenos.interface.mcp.ontology_service") as mock_os, \
             patch("zenos.interface.mcp.task_service") as mock_ts:
            mock_os.add_blindspot = AsyncMock(return_value=blindspot)
            mock_ts.list_tasks = AsyncMock(return_value=[existing_task])
            mock_ts.create_task = AsyncMock()

            result = await write(
                collection="blindspots",
                data={
                    "description": "No monitoring",
                    "severity": "red",
                    "suggested_action": "Add monitoring",
                    "related_entity_ids": [],
                },
            )

            assert result["status"] == "ok"
            assert result["data"]["auto_task_skipped"] == "EXISTING_OPEN_TASK"
            assert result["data"]["auto_created_task"]["id"] == "task-dup"
            mock_ts.create_task.assert_not_called()


# ---------------------------------------------------------------------------
# Tool 5: confirm
# ---------------------------------------------------------------------------

class TestConfirmTool:
    """Tests for the confirm MCP tool."""

    async def test_confirm_entity(self):
        from zenos.interface.mcp import confirm

        with patch("zenos.interface.mcp.ontology_service") as mock_os:
            mock_os.confirm = AsyncMock(return_value={"status": "confirmed"})

            result = await confirm(collection="entities", id="ent-1")

            mock_os.confirm.assert_called_once_with("entities", "ent-1")
            assert result["status"] == "ok"
            assert result["data"]["status"] == "confirmed"
            assert "context_bundle" in result
            assert "governance_hints" in result

    async def test_confirm_not_found(self):
        from zenos.interface.mcp import confirm

        with patch("zenos.interface.mcp.ontology_service") as mock_os:
            mock_os.confirm = AsyncMock(
                side_effect=ValueError("Entity 'x' not found"))

            result = await confirm(collection="entities", id="x")

            assert result["status"] == "rejected"
            assert "not found" in result["rejection_reason"].lower()

    async def test_confirm_invalid_input(self):
        from zenos.interface.mcp import confirm

        with patch("zenos.interface.mcp.ontology_service") as mock_os:
            mock_os.confirm = AsyncMock(
                side_effect=ValueError("Invalid status"))

            result = await confirm(collection="entities", id="x")

            assert result["status"] == "rejected"

    async def test_confirm_task_with_entity_entries_writes_entries_when_accepted(self):
        from zenos.interface.mcp import confirm
        from zenos.application.action.task_service import TaskResult

        t = _make_task(id="task-review", status="done")
        confirm_result = TaskResult(task=t, cascade_updates=[])

        with patch("zenos.interface.mcp.task_service") as mock_ts, \
             patch("zenos.interface.mcp.entry_repo") as mock_entry_repo:
            mock_ts.confirm_task = AsyncMock(return_value=confirm_result)
            mock_entry_repo.create = AsyncMock(side_effect=lambda e: e)

            entries = [
                {"entity_id": "ent-1", "type": "insight", "content": "Some valuable insight"},
                {"entity_id": "ent-2", "type": "decision", "content": "Key architectural decision"},
            ]
            result = await confirm(
                collection="tasks",
                id="task-review",
                accepted=True,
                entity_entries=entries,
            )

            # task_service.confirm_task should receive entity_entries
            mock_ts.confirm_task.assert_called_once()
            call_kwargs = mock_ts.confirm_task.call_args.kwargs
            assert call_kwargs["entity_entries"] == entries

            # entry_repo.create should be called for each entry
            assert mock_entry_repo.create.call_count == 2

    async def test_confirm_task_entity_entries_not_written_when_rejected(self):
        from zenos.interface.mcp import confirm
        from zenos.application.action.task_service import TaskResult

        t = _make_task(id="task-review", status="in_progress")
        confirm_result = TaskResult(task=t, cascade_updates=[])

        with patch("zenos.interface.mcp.task_service") as mock_ts, \
             patch("zenos.interface.mcp.entry_repo") as mock_entry_repo:
            mock_ts.confirm_task = AsyncMock(return_value=confirm_result)
            mock_entry_repo.create = AsyncMock(side_effect=lambda e: e)

            entries = [{"entity_id": "ent-1", "type": "insight", "content": "ignored entry"}]
            result = await confirm(
                collection="tasks",
                id="task-review",
                accepted=False,
                rejection_reason="Does not meet criteria",
                entity_entries=entries,
            )

            # entry_repo.create should NOT be called for rejected tasks
            mock_entry_repo.create.assert_not_called()

    async def test_confirm_task_entity_entries_skips_invalid_content(self):
        """Entries with missing entity_id or content > 200 chars are skipped."""
        from zenos.interface.mcp import confirm
        from zenos.application.action.task_service import TaskResult

        t = _make_task(id="task-review", status="done")
        confirm_result = TaskResult(task=t, cascade_updates=[])

        with patch("zenos.interface.mcp.task_service") as mock_ts, \
             patch("zenos.interface.mcp.entry_repo") as mock_entry_repo:
            mock_ts.confirm_task = AsyncMock(return_value=confirm_result)
            mock_entry_repo.create = AsyncMock(side_effect=lambda e: e)

            entries = [
                {"type": "insight", "content": "missing entity_id — should be skipped"},
                {"entity_id": "ent-1", "type": "insight", "content": "x" * 201},  # too long
                {"entity_id": "ent-2", "type": "insight", "content": "valid entry"},
            ]
            await confirm(
                collection="tasks",
                id="task-review",
                accepted=True,
                entity_entries=entries,
            )

            # Only the valid entry should be written
            assert mock_entry_repo.create.call_count == 1

    async def test_confirm_task_without_entity_entries_is_backward_compatible(self):
        """confirm without entity_entries works the same as before."""
        from zenos.interface.mcp import confirm
        from zenos.application.action.task_service import TaskResult

        t = _make_task(id="task-review", status="done")
        confirm_result = TaskResult(task=t, cascade_updates=[])

        with patch("zenos.interface.mcp.task_service") as mock_ts, \
             patch("zenos.interface.mcp.entry_repo") as mock_entry_repo:
            mock_ts.confirm_task = AsyncMock(return_value=confirm_result)
            mock_entry_repo.create = AsyncMock(side_effect=lambda e: e)

            result = await confirm(collection="tasks", id="task-review", accepted=True)

            mock_ts.confirm_task.assert_called_once()
            mock_entry_repo.create.assert_not_called()

    async def test_confirm_task_audit_log_includes_entity_entries(self):
        """Audit log records entity_entries in changes."""
        from zenos.interface.mcp import confirm
        from zenos.application.action.task_service import TaskResult

        t = _make_task(id="task-review", status="done")
        confirm_result = TaskResult(task=t, cascade_updates=[])

        audit_calls = []
        with patch("zenos.interface.mcp.task_service") as mock_ts, \
             patch("zenos.interface.mcp.entry_repo") as mock_entry_repo, \
             patch("zenos.interface.mcp.confirm._audit_log", side_effect=lambda **kw: audit_calls.append(kw)):
            mock_ts.confirm_task = AsyncMock(return_value=confirm_result)
            mock_entry_repo.create = AsyncMock(side_effect=lambda e: e)

            entries = [{"entity_id": "ent-1", "type": "insight", "content": "test insight"}]
            await confirm(
                collection="tasks",
                id="task-review",
                accepted=True,
                entity_entries=entries,
            )

            assert len(audit_calls) == 1
            changes = audit_calls[0]["changes"]
            assert "entity_entries" in changes
            assert changes["entity_entries"] == entries


# ---------------------------------------------------------------------------
# Tool 6: task
# ---------------------------------------------------------------------------

class TestTaskTool:
    """Tests for the task MCP tool."""

    async def test_create_task_success(self):
        from zenos.interface.mcp import task
        from zenos.application.action.task_service import TaskResult

        t = _make_task()
        create_result = TaskResult(task=t, cascade_updates=[])

        with patch("zenos.interface.mcp.task_service") as mock_ts:
            mock_ts.create_task = AsyncMock(return_value=create_result)

            result = await task(
                action="create",
                title="Fix login",
                created_by="architect",
                assignee="developer",
                priority="high",
            )

            assert result["status"] == "ok"
            assert result["data"]["title"] == "Fix login"

    async def test_create_task_accepts_json_array_string_for_list_fields(self):
        from zenos.interface.mcp import task
        from zenos.application.action.task_service import TaskResult

        t = _make_task()
        create_result = TaskResult(task=t, cascade_updates=[])
        with patch("zenos.interface.mcp.task_service") as mock_ts:
            mock_ts.create_task = AsyncMock(return_value=create_result)
            await task(
                action="create",
                title="Fix login",
                created_by="architect",
                linked_entities='["ent-1","ent-2"]',
                acceptance_criteria='["a","b"]',
            )
            payload = mock_ts.create_task.call_args.args[0]
            assert payload["linked_entities"] == ["ent-1", "ent-2"]
            assert payload["acceptance_criteria"] == ["a", "b"]

    async def test_create_task_missing_title(self):
        from zenos.interface.mcp import task

        result = await task(action="create", created_by="architect")

        assert result["status"] == "rejected"
        assert "title" in result["rejection_reason"]

    async def test_create_task_missing_created_by(self):
        from zenos.interface.mcp import task

        result = await task(action="create", title="Fix login")

        assert result["status"] == "rejected"
        assert "created_by" in result["rejection_reason"]

    async def test_create_task_invalid_due_date(self):
        from zenos.interface.mcp import task

        result = await task(
            action="create",
            title="Fix login",
            created_by="architect",
            due_date="not-a-date",
        )

        assert result["status"] == "rejected"
        assert "due_date" in result["rejection_reason"]

    async def test_create_task_plain_description_auto_formats_to_markdown(self):
        from zenos.interface.mcp import task
        from zenos.application.action.task_service import TaskResult

        t = _make_task()
        create_result = TaskResult(task=t, cascade_updates=[])
        raw = "業務要做母親節檔期素材，需符合品牌語氣\n主視覺要有 CTA\n本週五前交付"

        with patch("zenos.interface.mcp.task_service") as mock_ts:
            mock_ts.create_task = AsyncMock(return_value=create_result)

            await task(
                action="create",
                title="整理母親節素材需求",
                created_by="amy",
                description=raw,
            )

            payload = mock_ts.create_task.call_args.args[0]
            assert payload["description"].startswith("**需求摘要**：")
            assert "**補充資訊**" in payload["description"]
            assert "- 主視覺要有 CTA" in payload["description"]

    async def test_create_task_markdown_description_keeps_original(self):
        from zenos.interface.mcp import task
        from zenos.application.action.task_service import TaskResult

        t = _make_task()
        create_result = TaskResult(task=t, cascade_updates=[])
        markdown = "**需求摘要**：整理母親節素材\n\n- 完成主視覺\n- 完成投放尺寸"

        with patch("zenos.interface.mcp.task_service") as mock_ts:
            mock_ts.create_task = AsyncMock(return_value=create_result)

            await task(
                action="create",
                title="整理母親節素材需求",
                created_by="amy",
                description=markdown,
            )

            payload = mock_ts.create_task.call_args.args[0]
            assert payload["description"] == markdown

    async def test_create_task_passes_source_metadata(self):
        from zenos.interface.mcp import task
        from zenos.application.action.task_service import TaskResult

        t = _make_task()
        create_result = TaskResult(task=t, cascade_updates=[])
        metadata = {
            "sync_sources": ["Google Sheets - Banila Co #L15"],
            "provenance": [{"type": "sheet", "sheet_ref": "BanilaCo!L15"}],
        }

        with patch("zenos.interface.mcp.task_service") as mock_ts:
            mock_ts.create_task = AsyncMock(return_value=create_result)

            await task(
                action="create",
                title="整理來源追溯資料",
                created_by="amy",
                source_metadata=metadata,
            )

            payload = mock_ts.create_task.call_args.args[0]
            assert payload["source_metadata"]["sync_sources"] == metadata["sync_sources"]
            assert payload["source_metadata"]["provenance"] == metadata["provenance"]
            assert payload["source_metadata"]["created_via_agent"] is True

    async def test_create_task_accepts_explicit_agent_metadata(self):
        from zenos.interface.mcp import task
        from zenos.application.action.task_service import TaskResult

        t = _make_task()
        create_result = TaskResult(task=t, cascade_updates=[])

        with patch("zenos.interface.mcp.task_service") as mock_ts:
            mock_ts.create_task = AsyncMock(return_value=create_result)

            await task(
                action="create",
                title="建立 actor trace",
                created_by="amy",
                created_via_agent=True,
                agent_name="architect-agent",
            )

            payload = mock_ts.create_task.call_args.args[0]
            assert payload["source_metadata"]["created_via_agent"] is True
            assert payload["source_metadata"]["agent_name"] == "architect-agent"

    async def test_update_task_success(self):
        from zenos.interface.mcp import task
        from zenos.application.action.task_service import TaskResult

        t = _make_task(status="in_progress")
        update_result = TaskResult(task=t, cascade_updates=[])

        with patch("zenos.interface.mcp.task_service") as mock_ts:
            mock_ts.update_task = AsyncMock(return_value=update_result)

            result = await task(
                action="update",
                id="task-1",
                status="in_progress",
            )

            assert result["status"] == "ok"
            assert result["data"]["status"] == "in_progress"

    async def test_update_task_missing_id(self):
        from zenos.interface.mcp import task

        result = await task(action="update", status="in_progress")

        assert result["status"] == "rejected"
        assert "id" in result["rejection_reason"]

    async def test_unknown_action(self):
        from zenos.interface.mcp import task

        result = await task(action="delete", title="X", created_by="Y")

        assert result["status"] == "rejected"
        assert "Unknown action" in result["rejection_reason"]

    async def test_update_task_invalid_status(self):
        from zenos.interface.mcp import task

        with patch("zenos.interface.mcp.task_service") as mock_ts:
            mock_ts.update_task = AsyncMock(
                side_effect=ValueError("Cannot transition to done"))

            result = await task(action="update", id="task-1", status="done")

            assert result["status"] == "rejected"

    # ── Task 2: linked_entities=[] warning ──

    async def test_create_task_empty_linked_entities_produces_warning(self):
        """task create with no linked_entities should warn about missing ontology context."""
        from zenos.interface.mcp import _task_handler
        from zenos.application.action.task_service import TaskResult

        t = _make_task(linked_entities=[])
        create_result = TaskResult(task=t, cascade_updates=[])

        with patch("zenos.interface.mcp.task_service") as mock_ts:
            mock_ts.create_task = AsyncMock(return_value=create_result)
            mock_ts.enrich_task = AsyncMock(return_value={"expanded_entities": []})

            result = await _task_handler(
                action="create",
                title="Fix login",
                created_by="architect",
            )

            assert result["status"] == "ok"
            warning_texts = " ".join(result.get("warnings", []))
            assert "linked_entities" in warning_texts
            assert "ontology context" in warning_texts

    async def test_create_task_with_linked_entities_no_empty_warning(self):
        """task create with linked_entities set should NOT produce the empty-entities warning."""
        from zenos.interface.mcp import _task_handler
        from zenos.application.action.task_service import TaskResult

        entity_id = "ent-1"
        t = _make_task(linked_entities=[entity_id])
        create_result = TaskResult(task=t, cascade_updates=[])

        with patch("zenos.interface.mcp.task_service") as mock_ts:
            mock_ts.create_task = AsyncMock(return_value=create_result)
            mock_ts.enrich_task = AsyncMock(return_value={
                "expanded_entities": [{"id": entity_id, "name": "Paceriz", "summary": "s", "tags": {}, "status": "active"}],
            })

            result = await _task_handler(
                action="create",
                title="Fix login",
                created_by="architect",
                linked_entities=[entity_id],
            )

            assert result["status"] == "ok"
            for w in result.get("warnings", []):
                assert "linked_entities 為空" not in w

    # ── Task 3: linked_entities return type consistency ──

    async def test_create_task_linked_entities_returns_objects(self):
        """task create should return linked_entities as list of objects, not IDs."""
        from zenos.interface.mcp import _task_handler
        from zenos.application.action.task_service import TaskResult

        entity_id = "ent-1"
        t = _make_task(linked_entities=[entity_id])
        create_result = TaskResult(task=t, cascade_updates=[])
        expanded = [{"id": entity_id, "name": "Paceriz", "summary": "running coach", "tags": {}, "status": "active"}]

        with patch("zenos.interface.mcp.task_service") as mock_ts:
            mock_ts.create_task = AsyncMock(return_value=create_result)
            mock_ts.enrich_task = AsyncMock(return_value={"expanded_entities": expanded})

            result = await _task_handler(
                action="create",
                title="Fix login",
                created_by="architect",
                linked_entities=[entity_id],
            )

            assert result["status"] == "ok"
            linked = result["data"]["linked_entities"]
            assert isinstance(linked, list)
            assert len(linked) == 1
            assert isinstance(linked[0], dict)
            assert linked[0]["id"] == entity_id
            assert "name" in linked[0]

    async def test_update_task_linked_entities_returns_objects(self):
        """task update should return linked_entities as list of objects, not IDs."""
        from zenos.interface.mcp import _task_handler
        from zenos.application.action.task_service import TaskResult

        entity_id = "ent-1"
        t = _make_task(id="task-1", linked_entities=[entity_id])
        update_result = TaskResult(task=t, cascade_updates=[])
        expanded = [{"id": entity_id, "name": "Paceriz", "summary": "running coach", "tags": {}, "status": "active"}]

        with patch("zenos.interface.mcp.task_service") as mock_ts:
            mock_ts.update_task = AsyncMock(return_value=update_result)
            mock_ts.enrich_task = AsyncMock(return_value={"expanded_entities": expanded})

            result = await _task_handler(
                action="update",
                id="task-1",
                status="in_progress",
            )

            assert result["status"] == "ok"
            linked = result["data"]["linked_entities"]
            assert isinstance(linked, list)
            assert len(linked) == 1
            assert isinstance(linked[0], dict)
            assert linked[0]["id"] == entity_id
            assert "name" in linked[0]


# ---------------------------------------------------------------------------
# Tool 7: analyze
# ---------------------------------------------------------------------------

class TestAnalyzeTool:
    """Tests for the analyze MCP tool."""

    async def test_analyze_quality(self):
        from zenos.interface.mcp import analyze

        report = QualityReport(
            score=85,
            passed=[QualityCheckItem(name="check1", passed=True, detail="ok")],
            failed=[],
            warnings=[],
        )

        with patch("zenos.interface.mcp.governance_service") as mock_gs:
            mock_gs.run_quality_check = AsyncMock(return_value=report)
            mock_gs.infer_l2_backfill_proposals = AsyncMock(return_value=[])

            result = await analyze(check_type="quality")

            assert "quality" in result
            assert result["quality"]["score"] == 85

    async def test_analyze_quality_includes_l2_repair_suggestions(self):
        from zenos.interface.mcp import analyze

        report = QualityReport(
            score=80,
            passed=[],
            failed=[QualityCheckItem(name="l2_impacts_coverage", passed=False, detail="missing impacts")],
            warnings=[],
        )
        module = _make_entity(id="mod-1", type="module", name="Governance", status="active")

        with patch("zenos.interface.mcp.governance_service") as mock_gs, \
             patch("zenos.interface.mcp.ontology_service") as mock_os:
            mock_gs.run_quality_check = AsyncMock(return_value=report)
            mock_gs.infer_l2_backfill_proposals = AsyncMock(return_value=[{
                "entity_id": "mod-1",
                "entity_name": "Governance",
                "issues": ["缺少具體 impacts"],
                "repair_actions": ["補 impacts"],
                "suggested_summary": "Governance 是公司共識概念",
                "candidate_impacts": [],
                "source_documents": [],
                "existing_impacts_count": 0,
            }])
            mock_os._entities = AsyncMock()
            mock_os._entities.list_all = AsyncMock(return_value=[module])
            mock_os._relationships = AsyncMock()
            mock_os._relationships.list_by_entity = AsyncMock(return_value=[])

            result = await analyze(check_type="quality")

            assert result["quality"]["active_l2_missing_impacts"] == 1
            assert len(result["quality"]["l2_impacts_repairs"]) == 1
            assert result["quality"]["l2_backfill_count"] == 1
            assert result["quality"]["l2_backfill_proposals"][0]["entity_id"] == "mod-1"

    async def test_analyze_staleness(self):
        from zenos.interface.mcp import analyze

        warnings = [
            StalenessWarning(
                pattern="feature_doc_lag",
                description="Docs are stale",
                affected_entity_ids=["ent-1"],
                affected_document_ids=["doc-1"],
                suggested_action="Review docs",
            )
        ]

        with patch("zenos.interface.mcp.governance_service") as mock_gs:
            mock_gs.run_staleness_check = AsyncMock(
                return_value={"warnings": warnings, "document_consistency_warnings": [], "document_consistency_count": 0}
            )

            result = await analyze(check_type="staleness")

            assert result["staleness"]["count"] == 1

    async def test_analyze_blindspot(self):
        from zenos.interface.mcp import analyze

        blindspots = [_make_blindspot()]

        with patch("zenos.interface.mcp.governance_service") as mock_gs:
            mock_gs.run_blindspot_analysis = AsyncMock(return_value=blindspots)

            result = await analyze(check_type="blindspot")

            assert result["blindspots"]["count"] == 1

    async def test_analyze_all(self):
        from zenos.interface.mcp import analyze

        report = QualityReport(score=90, passed=[], failed=[], warnings=[])

        with patch("zenos.interface.mcp.governance_service") as mock_gs:
            mock_gs.run_quality_check = AsyncMock(return_value=report)
            mock_gs.run_staleness_check = AsyncMock(
                return_value={"warnings": [], "document_consistency_warnings": [], "document_consistency_count": 0}
            )
            mock_gs.run_blindspot_analysis = AsyncMock(return_value=[])
            mock_gs.infer_l2_backfill_proposals = AsyncMock(return_value=[])

            result = await analyze(check_type="all")

            assert "quality" in result
            assert "staleness" in result
            assert "blindspots" in result

    async def test_analyze_all_includes_kpis_when_data_available(self):
        from zenos.interface.mcp import analyze

        report = QualityReport(score=90, passed=[], failed=[], warnings=[])
        entities = [
            _make_entity(id="ent-1", type="product", confirmed_by_user=False),
            _make_entity(id="doc-1", type="document", confirmed_by_user=True),
        ]
        health_signal = {
            "kpis": {
                "quality_score": {"value": 90, "level": "green"},
                "unconfirmed_ratio": {"value": 0.5, "level": "yellow"},
                "blindspot_total": {"value": 2, "level": "green"},
                "median_confirm_latency_days": {"value": 1.0, "level": "green"},
                "active_l2_missing_impacts": {"value": 0, "level": "green"},
                "duplicate_blindspot_rate": {"value": 0.5, "level": "red"},
            },
            "overall_level": "red",
            "recommended_action": "run_governance",
            "red_reasons": [],
        }
        with patch("zenos.interface.mcp.governance_service") as mock_gs, \
             patch("zenos.interface.mcp.ontology_service") as mock_os, \
             patch("zenos.interface.mcp.blindspot_repo") as mock_br:
            mock_gs.run_quality_check = AsyncMock(return_value=report)
            mock_gs.run_staleness_check = AsyncMock(
                return_value={"warnings": [], "document_consistency_warnings": [], "document_consistency_count": 0}
            )
            mock_gs.run_blindspot_analysis = AsyncMock(return_value=[])
            mock_gs.infer_l2_backfill_proposals = AsyncMock(return_value=[])
            mock_gs.compute_health_signal = AsyncMock(return_value=health_signal)
            mock_os._entities = AsyncMock()
            mock_os._entities.list_all = AsyncMock(return_value=entities)
            mock_os._documents = AsyncMock()
            mock_os._documents.list_all = AsyncMock(return_value=[])
            mock_os._protocols = AsyncMock()
            mock_os._protocols.get_by_entity = AsyncMock(return_value=None)
            mock_br.list_all = AsyncMock(return_value=[])

            result = await analyze(check_type="all")

            assert "kpis" in result
            assert "health_signal" in result
            assert result["health_signal"]["overall_level"] == "red"
            assert result["kpis"]["blindspot_total"] == 2
            assert result["kpis"]["duplicate_blindspot_rate"] == 0.5

    async def test_analyze_invalid_type(self):
        from zenos.interface.mcp import analyze

        result = await analyze(check_type="foobar")

        assert result["error"] == "INVALID_INPUT"
        assert "Unknown check_type" in result["message"]

    async def test_analyze_quality_entry_saturation_empty(self):
        """analyze quality: entry_saturation=[] and count=0 when no saturated entities."""
        from zenos.interface.mcp import analyze
        from zenos.application.knowledge.governance_ai import GovernanceAI
        import zenos.interface.mcp as tools_mod

        report = QualityReport(score=90, passed=[], failed=[], warnings=[])

        with patch("zenos.interface.mcp.governance_service") as mock_gs, \
             patch("zenos.interface.mcp.ontology_service") as mock_os, \
             patch("zenos.interface.mcp._governance_ai") as mock_ai:
            mock_gs.run_quality_check = AsyncMock(return_value=report)
            mock_gs.infer_l2_backfill_proposals = AsyncMock(return_value=[])
            mock_gs.check_governance_review_overdue = AsyncMock(return_value=[])
            mock_os._entities = AsyncMock()
            mock_os._entities.list_all = AsyncMock(return_value=[])
            tools_mod.entry_repo.list_saturated_entities = AsyncMock(return_value=[])

            result = await analyze(check_type="quality")

            assert "quality" in result
            assert result["quality"]["entry_saturation"] == []
            assert result["quality"]["entry_saturation_count"] == 0

    async def test_analyze_quality_entry_saturation_has_proposal(self):
        """analyze quality: saturated entity produces proposal in entry_saturation."""
        from zenos.interface.mcp import analyze
        from zenos.application.knowledge.governance_ai import ConsolidationProposal, ConsolidationMergeGroup
        import zenos.interface.mcp as tools_mod

        report = QualityReport(score=70, passed=[], failed=[], warnings=[])

        entries = [_make_entry(id=f"entry-{i}") for i in range(20)]
        proposal = ConsolidationProposal(
            entity_id="ent-1",
            entity_name="ZenOS",
            merge_groups=[
                ConsolidationMergeGroup(
                    source_entry_ids=["entry-0", "entry-1"],
                    merged_content="Combined insight about PostgreSQL",
                )
            ],
            keep_as_is=[f"entry-{i}" for i in range(2, 20)],
            estimated_after_count=19,
        )

        mock_ai = MagicMock()
        mock_ai.consolidate_entries = MagicMock(return_value=proposal)

        with patch("zenos.interface.mcp.governance_service") as mock_gs, \
             patch("zenos.interface.mcp.ontology_service") as mock_os, \
             patch("zenos.interface.mcp._governance_ai", mock_ai):
            mock_gs.run_quality_check = AsyncMock(return_value=report)
            mock_gs.infer_l2_backfill_proposals = AsyncMock(return_value=[])
            mock_gs.check_governance_review_overdue = AsyncMock(return_value=[])
            mock_os._entities = AsyncMock()
            mock_os._entities.list_all = AsyncMock(return_value=[])
            tools_mod.entry_repo.list_saturated_entities = AsyncMock(return_value=[
                {"entity_id": "ent-1", "entity_name": "ZenOS", "active_count": 20}
            ])
            tools_mod.entry_repo.list_by_entity = AsyncMock(return_value=entries)

            result = await analyze(check_type="quality")

            assert result["quality"]["entry_saturation_count"] == 1
            saturation_items = result["quality"]["entry_saturation"]
            assert len(saturation_items) == 1
            assert saturation_items[0]["entity_id"] == "ent-1"
            assert saturation_items[0]["consolidation_proposal"] is not None

    async def test_analyze_quality_entry_saturation_llm_failure(self):
        """analyze quality: LLM failure in consolidate_entries -> proposal is None, analyze doesn't crash."""
        from zenos.interface.mcp import analyze
        import zenos.interface.mcp as tools_mod

        report = QualityReport(score=70, passed=[], failed=[], warnings=[])

        entries = [_make_entry(id=f"entry-{i}") for i in range(20)]

        mock_ai = MagicMock()
        mock_ai.consolidate_entries = MagicMock(return_value=None)  # LLM failure

        with patch("zenos.interface.mcp.governance_service") as mock_gs, \
             patch("zenos.interface.mcp.ontology_service") as mock_os, \
             patch("zenos.interface.mcp._governance_ai", mock_ai):
            mock_gs.run_quality_check = AsyncMock(return_value=report)
            mock_gs.infer_l2_backfill_proposals = AsyncMock(return_value=[])
            mock_gs.check_governance_review_overdue = AsyncMock(return_value=[])
            mock_os._entities = AsyncMock()
            mock_os._entities.list_all = AsyncMock(return_value=[])
            tools_mod.entry_repo.list_saturated_entities = AsyncMock(return_value=[
                {"entity_id": "ent-1", "entity_name": "ZenOS", "active_count": 20}
            ])
            tools_mod.entry_repo.list_by_entity = AsyncMock(return_value=entries)

            result = await analyze(check_type="quality")

            assert "quality" in result
            assert result["quality"]["entry_saturation_count"] == 1
            assert result["quality"]["entry_saturation"][0]["consolidation_proposal"] is None


# ===================================================================
# write(collection="entries") tests
# ===================================================================

def _make_entry(**overrides) -> EntityEntry:
    defaults = dict(
        id="entry-1",
        partner_id="partner-abc",
        entity_id="ent-1",
        type="decision",
        content="We chose PostgreSQL for reliability",
        status="active",
        context=None,
        author="Alice",
        source_task_id=None,
        superseded_by=None,
        archive_reason=None,
        created_at=datetime(2026, 3, 28, tzinfo=timezone.utc),
    )
    defaults.update(overrides)
    return EntityEntry(**defaults)


@pytest.mark.asyncio
class TestWriteEntriesCollection:

    async def test_write_entry_success(self):
        """write(collection='entries') creates an entry and returns serialized result."""
        from zenos.interface.mcp import write
        import zenos.interface.mcp as tools_mod

        entry = _make_entry()
        tools_mod.entry_repo.create = AsyncMock(return_value=entry)
        tools_mod.entry_repo.count_active_by_entity = AsyncMock(return_value=5)

        result = await write(
            collection="entries",
            data={
                "entity_id": "ent-1",
                "type": "decision",
                "content": "We chose PostgreSQL for reliability",
                "author": "Alice",
            },
        )

        assert result["status"] == "ok"
        assert result["data"]["id"] == "entry-1"
        assert result["data"]["type"] == "decision"
        assert result["data"]["content"] == "We chose PostgreSQL for reliability"
        assert result["warnings"] == []
        tools_mod.entry_repo.create.assert_called_once()

    async def test_write_entry_missing_entity_id(self):
        """write entries returns INVALID_INPUT when entity_id is missing."""
        from zenos.interface.mcp import write

        result = await write(
            collection="entries",
            data={"type": "decision", "content": "Some content"},
        )

        assert result["status"] == "rejected"
        assert "entity_id" in result["rejection_reason"]

    async def test_write_entry_missing_content(self):
        """write entries returns rejected when content is missing."""
        from zenos.interface.mcp import write

        result = await write(
            collection="entries",
            data={"entity_id": "ent-1", "type": "decision"},
        )

        assert result["status"] == "rejected"

    async def test_write_entry_content_too_long(self):
        """write entries rejects content exceeding 200 chars."""
        from zenos.interface.mcp import write

        result = await write(
            collection="entries",
            data={
                "entity_id": "ent-1",
                "type": "decision",
                "content": "x" * 201,
            },
        )

        assert result["status"] == "rejected"
        assert "200" in result["rejection_reason"]

    async def test_write_entry_empty_content(self):
        """write entries rejects empty content."""
        from zenos.interface.mcp import write

        result = await write(
            collection="entries",
            data={"entity_id": "ent-1", "type": "decision", "content": ""},
        )

        assert result["status"] == "rejected"

    async def test_write_entry_invalid_type(self):
        """write entries rejects unknown type value."""
        from zenos.interface.mcp import write

        result = await write(
            collection="entries",
            data={"entity_id": "ent-1", "type": "unknown_type", "content": "some content"},
        )

        assert result["status"] == "rejected"
        assert "type" in result["rejection_reason"]

    async def test_write_entry_context_too_long(self):
        """write entries rejects context exceeding 200 chars."""
        from zenos.interface.mcp import write

        result = await write(
            collection="entries",
            data={
                "entity_id": "ent-1",
                "type": "insight",
                "content": "Valid content",
                "context": "c" * 201,
            },
        )

        assert result["status"] == "rejected"
        assert "context" in result["rejection_reason"]

    async def test_write_entry_update_status_supersede(self):
        """write entries with id updates status for supersede flow."""
        from zenos.interface.mcp import write
        import zenos.interface.mcp as tools_mod

        old_entry = _make_entry(status="superseded", superseded_by="entry-2")
        tools_mod.entry_repo.update_status = AsyncMock(return_value=old_entry)

        result = await write(
            collection="entries",
            id="entry-1",
            data={"status": "superseded", "superseded_by": "entry-2"},
        )

        assert result["status"] == "ok"
        assert result["data"]["status"] == "superseded"
        assert result["data"]["superseded_by"] == "entry-2"
        tools_mod.entry_repo.update_status.assert_called_once_with(
            "entry-1", "superseded", "entry-2", None
        )

    async def test_write_entry_update_status_not_found(self):
        """write entries update returns NOT_FOUND when entry doesn't exist."""
        from zenos.interface.mcp import write
        import zenos.interface.mcp as tools_mod

        tools_mod.entry_repo.update_status = AsyncMock(return_value=None)

        result = await write(
            collection="entries",
            id="nonexistent",
            data={"status": "archived", "archive_reason": "manual"},
        )

        assert result["status"] == "rejected"
        assert "not found" in result["rejection_reason"].lower()

    async def test_write_entry_archive_with_reason_success(self):
        """write entries with status=archived and archive_reason=manual succeeds."""
        from zenos.interface.mcp import write
        import zenos.interface.mcp as tools_mod

        archived_entry = _make_entry(status="archived", archive_reason="manual")
        tools_mod.entry_repo.update_status = AsyncMock(return_value=archived_entry)

        result = await write(
            collection="entries",
            id="entry-1",
            data={"status": "archived", "archive_reason": "manual"},
        )

        assert result["status"] == "ok"
        assert result["data"]["status"] == "archived"
        assert result["data"]["archive_reason"] == "manual"
        tools_mod.entry_repo.update_status.assert_called_once_with(
            "entry-1", "archived", None, "manual"
        )

    async def test_write_entry_archive_missing_reason(self):
        """write entries with status=archived but no archive_reason returns rejected."""
        from zenos.interface.mcp import write

        result = await write(
            collection="entries",
            id="entry-1",
            data={"status": "archived"},
        )

        assert result["status"] == "rejected"
        assert "archive_reason" in result["rejection_reason"]

    async def test_write_entry_archive_invalid_reason(self):
        """write entries with invalid archive_reason returns rejected."""
        from zenos.interface.mcp import write

        result = await write(
            collection="entries",
            id="entry-1",
            data={"status": "archived", "archive_reason": "invalid_value"},
        )

        assert result["status"] == "rejected"
        assert "archive_reason" in result["rejection_reason"]

    async def test_write_entry_superseded_requires_superseded_by(self):
        """write entries with status=superseded requires superseded_by field."""
        from zenos.interface.mcp import write

        result = await write(
            collection="entries",
            id="entry-1",
            data={"status": "superseded"},
        )

        assert result["status"] == "rejected"
        assert "superseded_by" in result["rejection_reason"]


# ===================================================================
# write(collection="entries") — saturation warning tests (T2)
# ===================================================================

@pytest.mark.asyncio
class TestWriteEntriesSaturationWarning:

    async def test_write_entry_no_warning_when_below_limit(self):
        """write entries: no warning when active count < 20."""
        from zenos.interface.mcp import write
        import zenos.interface.mcp as tools_mod

        entry = _make_entry()
        tools_mod.entry_repo.create = AsyncMock(return_value=entry)
        tools_mod.entry_repo.count_active_by_entity = AsyncMock(return_value=19)

        result = await write(
            collection="entries",
            data={"entity_id": "ent-1", "type": "decision", "content": "PostgreSQL chosen"},
        )

        assert result["status"] == "ok"
        assert result["warnings"] == []

    async def test_write_entry_warning_when_at_limit(self):
        """write entries: warning returned when active count >= 20."""
        from zenos.interface.mcp import write
        import zenos.interface.mcp as tools_mod

        entry = _make_entry()
        tools_mod.entry_repo.create = AsyncMock(return_value=entry)
        tools_mod.entry_repo.count_active_by_entity = AsyncMock(return_value=20)

        result = await write(
            collection="entries",
            data={"entity_id": "ent-1", "type": "decision", "content": "PostgreSQL chosen"},
        )

        assert result["status"] == "ok"
        assert len(result["warnings"]) == 1
        assert "analyze" in result["warnings"][0]


# ===================================================================
# get(collection="entities") with active_entries tests
# ===================================================================

@pytest.mark.asyncio
class TestGetEntitiesActiveEntries:

    async def test_get_entity_by_name_includes_active_entries(self):
        """get(collection='entities', name=...) includes active_entries in response."""
        from zenos.interface.mcp import get
        import zenos.interface.mcp as tools_mod
        from zenos.application.knowledge.ontology_service import EntityWithRelationships

        entity = _make_entity()
        entry = _make_entry(entity_id=entity.id)
        result_obj = EntityWithRelationships(entity=entity, relationships=[])

        tools_mod.ontology_service.get_entity = AsyncMock(return_value=result_obj)
        tools_mod.entry_repo.list_by_entity = AsyncMock(return_value=[entry])

        result = await get(collection="entities", name="Paceriz")

        assert "active_entries" in result
        assert len(result["active_entries"]) == 1
        assert result["active_entries"][0]["type"] == "decision"
        tools_mod.entry_repo.list_by_entity.assert_called_once()

    async def test_get_entity_active_entries_empty_when_none(self):
        """get(collection='entities') returns empty active_entries list when no entries."""
        from zenos.interface.mcp import get
        import zenos.interface.mcp as tools_mod
        from zenos.application.knowledge.ontology_service import EntityWithRelationships

        entity = _make_entity()
        result_obj = EntityWithRelationships(entity=entity, relationships=[])

        tools_mod.ontology_service.get_entity = AsyncMock(return_value=result_obj)
        tools_mod.entry_repo.list_by_entity = AsyncMock(return_value=[])

        result = await get(collection="entities", name="Paceriz")

        assert "active_entries" in result
        assert result["active_entries"] == []


# ---------------------------------------------------------------------------
# Tool 8: governance_guide
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestGovernanceGuideTool:
    """Tests for the governance_guide MCP tool (DC-1, DC-2, DC-3, DC-4, DC-5, DC-6)."""

    # ── DC-1: Returns correct structure ─────────────────────────────────────

    async def test_returns_correct_structure_for_valid_input(self):
        """governance_guide returns {topic, level, version, content} for valid input."""
        from zenos.interface.mcp import governance_guide

        result = await governance_guide(topic="entity", level=1)

        assert result["topic"] == "entity"
        assert result["level"] == 1
        assert result["version"] == "1.1"
        assert isinstance(result["content"], str)
        assert len(result["content"]) > 0

    async def test_default_level_is_1(self):
        """governance_guide defaults to level=1 when level not provided."""
        from zenos.interface.mcp import governance_guide

        result = await governance_guide(topic="capture")

        assert result["level"] == 1
        assert result["topic"] == "capture"

    # ── DC-2: All four topics × three levels ────────────────────────────────

    @pytest.mark.parametrize("topic", ["entity", "document", "task", "capture"])
    @pytest.mark.parametrize("level", [1, 2, 3])
    async def test_all_topics_and_levels_return_content(self, topic, level):
        """Each of the 12 topic/level combinations returns non-empty content."""
        from zenos.interface.mcp import governance_guide

        result = await governance_guide(topic=topic, level=level)

        assert "error" not in result
        assert result["topic"] == topic
        assert result["level"] == level
        assert isinstance(result["version"], str)
        assert len(result["version"]) > 0
        assert isinstance(result["content"], str)
        assert len(result["content"]) >= 100, (
            f"Content for {topic} level={level} is too short: {len(result['content'])} chars"
        )

    async def test_level1_content_is_shorter_than_level3(self):
        """Level 1 content is shorter than Level 3 for the same topic."""
        from zenos.interface.mcp import governance_guide

        result_l1 = await governance_guide(topic="entity", level=1)
        result_l3 = await governance_guide(topic="entity", level=3)

        assert len(result_l1["content"]) < len(result_l3["content"])

    # ── DC-3: Invalid input returns INVALID_INPUT error ─────────────────────

    async def test_invalid_topic_returns_error(self):
        """Invalid topic returns INVALID_INPUT error with valid topics listed."""
        from zenos.interface.mcp import governance_guide

        result = await governance_guide(topic="unknown_topic", level=1)

        assert result["error"] == "INVALID_INPUT"
        assert "unknown_topic" in result["message"]
        # Must list valid topics in the message
        for valid in ["entity", "document", "task", "capture"]:
            assert valid in result["message"]

    async def test_invalid_level_returns_error(self):
        """Invalid level returns INVALID_INPUT error with valid levels listed."""
        from zenos.interface.mcp import governance_guide

        result = await governance_guide(topic="entity", level=99)

        assert result["error"] == "INVALID_INPUT"
        assert "99" in result["message"]
        assert "1/2/3" in result["message"]

    async def test_level_zero_returns_error(self):
        """Level 0 (boundary) returns INVALID_INPUT error."""
        from zenos.interface.mcp import governance_guide

        result = await governance_guide(topic="task", level=0)

        assert result["error"] == "INVALID_INPUT"

    async def test_empty_topic_returns_error(self):
        """Empty string topic returns INVALID_INPUT error."""
        from zenos.interface.mcp import governance_guide

        result = await governance_guide(topic="", level=1)

        assert result["error"] == "INVALID_INPUT"

    # ── DC-4: Content is server-side (smoke test via import) ────────────────

    async def test_rules_come_from_server_module_not_external_files(self):
        """Rules are served from GOVERNANCE_RULES dict, not read from filesystem."""
        from zenos.interface.governance_rules import GOVERNANCE_RULES

        # Verify the dict has all required keys
        assert set(GOVERNANCE_RULES.keys()) == {"entity", "document", "task", "capture"}
        for topic, levels in GOVERNANCE_RULES.items():
            assert set(levels.keys()) == {1, 2, 3}, (
                f"Topic '{topic}' missing levels: {set(levels.keys())}"
            )

    # ── DC-5: No internal algorithm details exposed ──────────────────────────

    async def test_entity_rules_do_not_expose_llm_prompts(self):
        """Entity rules mention three-question requirement but not LLM prompt internals."""
        from zenos.interface.mcp import governance_guide

        result = await governance_guide(topic="entity", level=3)
        content = result["content"]

        # Must mention the three-question gate (external rule)
        assert "三問" in content
        # Must NOT expose internal LLM prompt details
        assert "system prompt" not in content.lower()
        assert "temperature" not in content.lower()

    async def test_capture_rules_describe_routing_not_llm_internals(self):
        """Capture rules describe routing logic but not LLM model selection internals."""
        from zenos.interface.mcp import governance_guide

        result = await governance_guide(topic="capture", level=2)
        content = result["content"]

        # External rule: routing is mentioned
        assert "LAYER_DOWNGRADE_REQUIRED" in content
        # No internal model details
        assert "gemini" not in content.lower()
        assert "flash" not in content.lower()


class TestBatchUpdateSources:
    """Tests for the batch_update_sources MCP tool."""

    async def test_happy_path(self):
        from zenos.interface.mcp import batch_update_sources

        mock_result = {
            "updated": ["doc-1", "doc-2"],
            "not_found": [],
            "errors": [],
        }
        with patch("zenos.interface.mcp.ontology_service") as mock_os:
            mock_os.batch_update_document_sources = AsyncMock(return_value=mock_result)

            result = await batch_update_sources(
                updates=[
                    {"document_id": "doc-1", "new_uri": "https://github.com/org/repo/blob/main/new/path1.md"},
                    {"document_id": "doc-2", "new_uri": "https://github.com/org/repo/blob/main/new/path2.md"},
                ],
                atomic=False,
            )

            assert result["status"] == "ok"
            assert result["data"]["updated"] == ["doc-1", "doc-2"]
            assert result["data"]["not_found"] == []
            assert result["data"]["errors"] == []
            mock_os.batch_update_document_sources.assert_called_once()

    async def test_partial_failure_non_atomic(self):
        from zenos.interface.mcp import batch_update_sources

        mock_result = {
            "updated": ["doc-1"],
            "not_found": ["doc-missing"],
            "errors": [],
        }
        with patch("zenos.interface.mcp.ontology_service") as mock_os:
            mock_os.batch_update_document_sources = AsyncMock(return_value=mock_result)

            result = await batch_update_sources(
                updates=[
                    {"document_id": "doc-1", "new_uri": "https://github.com/org/repo/blob/main/new.md"},
                    {"document_id": "doc-missing", "new_uri": "https://github.com/org/repo/blob/main/gone.md"},
                ],
                atomic=False,
            )

            assert result["status"] == "ok"
            assert "doc-1" in result["data"]["updated"]
            assert "doc-missing" in result["data"]["not_found"]

    async def test_exceeds_batch_limit(self):
        from zenos.interface.mcp import batch_update_sources

        with patch("zenos.interface.mcp.ontology_service") as mock_os:
            mock_os.batch_update_document_sources = AsyncMock(
                side_effect=ValueError("Batch size 101 exceeds limit of 100")
            )

            result = await batch_update_sources(
                updates=[{"document_id": f"doc-{i}", "new_uri": f"uri-{i}"} for i in range(101)],
            )

            assert result["status"] == "rejected"
            assert "100" in result["rejection_reason"]

    async def test_atomic_mode_passed_to_service(self):
        from zenos.interface.mcp import batch_update_sources

        mock_result = {"updated": ["doc-1"], "not_found": [], "errors": []}
        with patch("zenos.interface.mcp.ontology_service") as mock_os:
            mock_os.batch_update_document_sources = AsyncMock(return_value=mock_result)

            await batch_update_sources(
                updates=[{"document_id": "doc-1", "new_uri": "new-uri"}],
                atomic=True,
            )

            mock_os.batch_update_document_sources.assert_called_once_with(
                [{"document_id": "doc-1", "new_uri": "new-uri"}],
                atomic=True,
            )

    async def test_empty_updates(self):
        from zenos.interface.mcp import batch_update_sources

        mock_result = {"updated": [], "not_found": [], "errors": []}
        with patch("zenos.interface.mcp.ontology_service") as mock_os:
            mock_os.batch_update_document_sources = AsyncMock(return_value=mock_result)

            result = await batch_update_sources(updates=[])

            assert result["status"] == "ok"
            assert result["data"]["updated"] == []
