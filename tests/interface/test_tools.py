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
from zenos.domain.knowledge import Blindspot, Document, Entity, EntityEntry, Gap, Protocol, Relationship, Source, Tags
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


def _ok_data(result: dict) -> dict:
    assert result["status"] == "ok"
    return result["data"]


def _non_ok_data(result: dict, status: str) -> dict:
    assert result["status"] == status
    return result["data"]


class _Acquire:
    def __init__(self, conn):
        self._conn = conn

    async def __aenter__(self):
        return self._conn

    async def __aexit__(self, exc_type, exc, tb):
        return False

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
        tags=Tags(what=["api"], why="reference", how="REST", who=["developer"]),
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
            data = _ok_data(result)

            assert "results" in data
            assert data["count"] == 1
            mock_os.search.assert_called_once_with(
                "Paceriz", max_level=2, product_id=None,
            )

    async def test_list_entities_collection(self):
        from zenos.interface.mcp import search

        entities = [_make_entity(), _make_entity(id="ent-2", name="ZenOS")]
        with patch("zenos.interface.mcp.ontology_service") as mock_os:
            mock_os.list_entities = AsyncMock(return_value=entities)

            result = await search(collection="entities")
            data = _ok_data(result)

            assert "entities" in data
            assert len(data["entities"]) == 2

    async def test_list_entities_with_confirmed_filter(self):
        from zenos.interface.mcp import search

        entities = [
            _make_entity(confirmed_by_user=True),
            _make_entity(id="ent-2", confirmed_by_user=False),
        ]
        with patch("zenos.interface.mcp.ontology_service") as mock_os:
            mock_os.list_entities = AsyncMock(return_value=entities)

            result = await search(collection="entities", confirmed_only=True)
            assert len(_ok_data(result)["entities"]) == 1

    async def test_list_tasks_with_assignee(self):
        from zenos.interface.mcp import search

        tasks = [_make_task()]
        with patch("zenos.interface.mcp.task_service") as mock_ts:
            mock_ts.list_tasks = AsyncMock(return_value=tasks)

            result = await search(collection="tasks", assignee="developer")
            data = _ok_data(result)

            mock_ts.list_tasks.assert_called_once_with(
                assignee="developer",
                created_by=None,
                dispatcher=None,
                parent_task_id=None,
                linked_entity=None,
                status=None,
                limit=200,
                offset=0,
                project=None,
                product_id=None,
                plan_id=None,
            )
            assert "tasks" in data

    async def test_list_tasks_with_status_filter(self):
        from zenos.interface.mcp import search

        with patch("zenos.interface.mcp.task_service") as mock_ts:
            mock_ts.list_tasks = AsyncMock(return_value=[])

            await search(collection="tasks", status="todo,in_progress")

            mock_ts.list_tasks.assert_called_once_with(
                assignee=None,
                created_by=None,
                dispatcher=None,
                parent_task_id=None,
                linked_entity=None,
                status=["todo", "in_progress"],
                limit=200,
                offset=0,
                project=None,
                product_id=None,
                plan_id=None,
            )

    async def test_list_tasks_normalizes_project_filter(self):
        from zenos.interface.mcp import search

        with patch("zenos.interface.mcp.task_service") as mock_ts:
            mock_ts.list_tasks = AsyncMock(return_value=[])

            await search(collection="tasks", project="  Paceriz  ")

            mock_ts.list_tasks.assert_called_once_with(
                assignee=None,
                created_by=None,
                dispatcher=None,
                parent_task_id=None,
                linked_entity=None,
                status=None,
                limit=200,
                offset=0,
                project="paceriz",
                product_id=None,
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
            data = _ok_data(result)

            assert "entities" in data
            assert "tasks" in data

    async def test_limit_respected(self):
        from zenos.interface.mcp import search

        entities = [_make_entity(id=f"ent-{i}") for i in range(10)]
        with patch("zenos.interface.mcp.ontology_service") as mock_os:
            mock_os.list_entities = AsyncMock(return_value=entities)

            result = await search(collection="entities", limit=3)
            assert len(_ok_data(result)["entities"]) == 3

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
            assert _ok_data(result)["entities"] == []
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
            assert _ok_data(result)["entities"] == []
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
            data = _ok_data(result)
            assert len(data["entities"]) == 1
            assert data["entities"][0]["id"] == "ent-c"
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
            data = _ok_data(result)

            assert "documents" in data
            assert [d["id"] for d in data["documents"]] == ["doc-1"]

    async def test_documents_collection_query_matches_all_tokens_not_just_substring(self):
        from zenos.interface.mcp import search

        doc_hit = _make_entity(
            id="doc-1",
            name="ADR-013: 分散治理模型——Agent 端語意判斷 vs Server 端結構執法",
            type="document",
            summary="分散治理 decision",
            sources=[{"uri": "adr.md", "label": "ADR-013-distributed-governance.md", "type": "github"}],
        )
        doc_miss = _make_entity(
            id="doc-2",
            name="Other ADR",
            type="document",
            summary="unrelated",
            sources=[{"uri": "other.md", "label": "other.md", "type": "github"}],
        )
        with patch("zenos.interface.mcp.ontology_service") as mock_os:
            mock_os._entities = AsyncMock()
            mock_os._entities.list_all = AsyncMock(return_value=[doc_hit, doc_miss])
            mock_os._entities.get_by_name = AsyncMock(return_value=None)

            result = await search(
                collection="documents",
                query="Agent 端語意判斷 Server 端結構執法",
            )
            data = _ok_data(result)

            assert [d["id"] for d in data["documents"]] == ["doc-1"]

    async def test_documents_entity_name_filter_uses_related_to_links(self):
        from zenos.interface.mcp import search

        primary = _make_entity(id="module-primary", name="Primary Module", type="module")
        secondary = _make_entity(id="module-secondary", name="Secondary Module", type="module")
        doc = _make_entity(
            id="doc-1",
            name="Shared Spec",
            type="document",
            parent_id="module-primary",
            summary="spec",
        )
        rel = Relationship(
            id="rel-1",
            source_entity_id="doc-1",
            target_id="module-secondary",
            type="related_to",
            description="document linked to entity",
        )

        async def list_all(type_filter=None):
            if type_filter == "document":
                return [doc]
            return [primary, secondary, doc]

        with patch("zenos.interface.mcp.ontology_service") as mock_os:
            mock_os._entities = AsyncMock()
            mock_os._entities.list_all = AsyncMock(side_effect=list_all)
            mock_os._entities.get_by_name = AsyncMock(return_value=secondary)
            mock_os._relationships = AsyncMock()
            mock_os._relationships.list_by_entity = AsyncMock(return_value=[rel])

            result = await search(collection="documents", entity_name="Secondary Module")
            data = _ok_data(result)

            assert [d["id"] for d in data["documents"]] == ["doc-1"]
            assert data["documents"][0]["linked_entity_ids"] == ["module-primary", "module-secondary"]
            assert data["documents"][0]["related_entity_ids"] == ["module-secondary"]

    async def test_documents_entity_name_prioritizes_primary_link_over_related_link(self):
        from zenos.interface.mcp import search

        target = _make_entity(id="module-mcp", name="MCP 介面設計", type="module")
        l3_governance = _make_entity(id="module-l3", name="L3 文件治理", type="module")
        primary_doc = _make_entity(
            id="doc-primary",
            name="MCP Primary Index",
            type="document",
            parent_id="module-mcp",
            status="current",
            summary="answers MCP tool design questions",
            doc_role="single",
            sources=[{"source_id": "src-primary", "uri": "mcp.md"}],
        )
        related_index = _make_entity(
            id="doc-related-index",
            name="L3 Governance Retrieval Map",
            type="document",
            parent_id="module-l3",
            status="current",
            summary="answers L3 document governance questions",
            details={"formal_entry": True},
            doc_role="index",
            bundle_highlights=[{"source_id": "src-related", "priority": "primary"}],
            sources=[
                {"source_id": "src-related", "uri": "l3.md"},
                {"source_id": "src-extra", "uri": "l3-extra.md"},
            ],
        )
        rel = Relationship(
            id="rel-1",
            source_entity_id="doc-related-index",
            target_id="module-mcp",
            type="related_to",
            description="document linked to entity",
        )

        async def list_all(type_filter=None):
            if type_filter == "document":
                return [related_index, primary_doc]
            return [target, l3_governance, related_index, primary_doc]

        async def list_by_entity(entity_id):
            if entity_id == "doc-related-index":
                return [rel]
            return []

        with patch("zenos.interface.mcp.ontology_service") as mock_os:
            mock_os._entities = AsyncMock()
            mock_os._entities.list_all = AsyncMock(side_effect=list_all)
            mock_os._entities.get_by_name = AsyncMock(return_value=target)
            mock_os._relationships = AsyncMock()
            mock_os._relationships.list_by_entity = AsyncMock(side_effect=list_by_entity)

            result = await search(collection="documents", entity_name="MCP 介面設計")
            data = _ok_data(result)

            assert [d["id"] for d in data["documents"]] == ["doc-primary", "doc-related-index"]

    async def test_documents_product_filter_uses_any_linked_entity(self):
        from zenos.interface.mcp import search

        product = _make_entity(id="product-1", name="Product", type="product", parent_id=None)
        primary = _make_entity(id="module-primary", name="Primary Module", type="module", parent_id=None)
        secondary = _make_entity(id="module-secondary", name="Secondary Module", type="module", parent_id="product-1")
        doc = _make_entity(
            id="doc-1",
            name="Shared Spec",
            type="document",
            parent_id="module-primary",
            summary="spec",
        )
        rel = Relationship(
            id="rel-1",
            source_entity_id="doc-1",
            target_id="module-secondary",
            type="related_to",
            description="document linked to entity",
        )

        async def list_all(type_filter=None):
            if type_filter == "document":
                return [doc]
            return [product, primary, secondary, doc]

        with patch("zenos.interface.mcp.ontology_service") as mock_os:
            mock_os._entities = AsyncMock()
            mock_os._entities.list_all = AsyncMock(side_effect=list_all)
            mock_os._entities.get_by_name = AsyncMock(return_value=None)
            mock_os._relationships = AsyncMock()
            mock_os._relationships.list_by_entity = AsyncMock(return_value=[rel])

            result = await search(collection="documents", product_id="product-1")
            data = _ok_data(result)

            assert [d["id"] for d in data["documents"]] == ["doc-1"]

    async def test_documents_search_prioritizes_current_index_retrieval_maps(self):
        from zenos.interface.mcp import search

        module = _make_entity(id="module-1", name="L3 文件治理", type="module")
        single_doc = _make_entity(
            id="doc-single",
            name="Single Spec",
            type="document",
            parent_id="module-1",
            status="current",
            summary="single source doc",
            doc_role="single",
            sources=[{"source_id": "src-single", "uri": "single.md"}],
            updated_at=datetime(2026, 4, 24, tzinfo=timezone.utc),
        )
        draft_index = _make_entity(
            id="doc-draft-index",
            name="Draft Index",
            type="document",
            parent_id="module-1",
            status="draft",
            summary="draft index",
            doc_role="index",
            bundle_highlights=[{"source_id": "src-draft", "priority": "primary"}],
            sources=[{"source_id": "src-draft", "uri": "draft.md"}],
            updated_at=datetime(2026, 4, 25, tzinfo=timezone.utc),
        )
        current_index = _make_entity(
            id="doc-current-index",
            name="Current Index",
            type="document",
            parent_id="module-1",
            status="current",
            summary="retrieval map for the bundle",
            details={"formal_entry": True},
            doc_role="index",
            bundle_highlights=[{"source_id": "src-primary", "priority": "primary"}],
            sources=[
                {"source_id": "src-primary", "uri": "primary.md"},
                {"source_id": "src-ref", "uri": "reference.md"},
            ],
            updated_at=datetime(2026, 4, 23, tzinfo=timezone.utc),
        )

        async def list_all(type_filter=None):
            if type_filter == "document":
                return [single_doc, draft_index, current_index]
            return [module, single_doc, draft_index, current_index]

        with patch("zenos.interface.mcp.ontology_service") as mock_os:
            mock_os._entities = AsyncMock()
            mock_os._entities.list_all = AsyncMock(side_effect=list_all)
            mock_os._entities.get_by_name = AsyncMock(return_value=module)
            mock_os._relationships = AsyncMock()
            mock_os._relationships.list_by_entity = AsyncMock(return_value=[])

            result = await search(collection="documents", entity_name="L3 文件治理")
            data = _ok_data(result)

            assert [d["id"] for d in data["documents"]] == [
                "doc-current-index",
                "doc-single",
                "doc-draft-index",
            ]

    async def test_documents_entity_name_many_results_auto_degrades_to_summary_payload(self):
        from zenos.interface.mcp import search

        module = _make_entity(id="module-1", name="語意治理 Pipeline", type="module")
        docs = [
            _make_entity(
                id=f"doc-{i}",
                name=f"Doc {i}",
                type="document",
                parent_id="module-1",
                status="current",
                summary=f"retrieval map {i}",
                sources=[{"source_id": f"src-{i}", "uri": f"doc-{i}.md", "type": "github"}],
                doc_role="index",
            )
            for i in range(11)
        ]

        async def list_all(type_filter=None):
            if type_filter == "document":
                return docs
            return [module, *docs]

        with patch("zenos.interface.mcp.ontology_service") as mock_os:
            mock_os._entities = AsyncMock()
            mock_os._entities.list_all = AsyncMock(side_effect=list_all)
            mock_os._entities.get_by_name = AsyncMock(return_value=module)
            mock_os._relationships = AsyncMock()
            mock_os._relationships.list_by_entity = AsyncMock(return_value=[])

            result = await search(collection="documents", entity_name="語意治理 Pipeline", limit=20)
            data = _ok_data(result)

            assert len(data["documents"]) == 11
            assert "sources" not in data["documents"][0]
            assert "summary" not in data["documents"][0]
            assert "summary_short" in data["documents"][0]
            assert data["documents"][0]["source_count"] == 1
            assert data["documents"][0]["primary_source"]["uri"].endswith(".md")
            assert any("compact summary" in warning for warning in result["warnings"])


class TestSearchNewParams:
    """Tests for new search params: product_id, offset, entity_level."""

    async def test_offset_pagination_entities(self):
        """offset skips the first N results for collection listing."""
        from zenos.interface.mcp import search

        entities = [_make_entity(id=f"ent-{i}", name=f"E{i}") for i in range(5)]
        with patch("zenos.interface.mcp.ontology_service") as mock_os:
            mock_os.list_entities = AsyncMock(return_value=entities)
            result = await search(collection="entities", limit=2, offset=2)
            data = _ok_data(result)
            assert len(data["entities"]) == 2
            assert data["entities"][0]["id"] == "ent-2"

    async def test_offset_pagination_tasks(self):
        """offset is passed to task_service.list_tasks."""
        from zenos.interface.mcp import search

        with patch("zenos.interface.mcp.task_service") as mock_ts:
            mock_ts.list_tasks = AsyncMock(return_value=[])
            await search(collection="tasks", offset=10, limit=5)
            mock_ts.list_tasks.assert_called_once_with(
                assignee=None,
                created_by=None,
                dispatcher=None,
                parent_task_id=None,
                linked_entity=None,
                status=None,
                limit=5,
                offset=10,
                project=None,
                product_id=None,
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
            ids = [e["id"] for e in _ok_data(result)["entities"]]
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
            assert len(_ok_data(result)["entities"]) == 1

    async def test_entity_level_l1_only(self):
        """entity_level='L1' filters out L2 and L3."""
        from zenos.interface.mcp import search

        l1 = _make_entity(id="ent-l1", name="Product", level=1)
        l2 = _make_entity(id="ent-l2", name="Module", level=2)
        with patch("zenos.interface.mcp.ontology_service") as mock_os:
            mock_os.list_entities = AsyncMock(return_value=[l1, l2])
            result = await search(collection="entities", entity_level="L1")
            ids = [e["id"] for e in _ok_data(result)["entities"]]
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
            assert len(_ok_data(result)["entities"]) == 1

    async def test_applied_filters_echoes_entity_level(self):
        """INV3: search response echoes applied_filters so agent can see what was excluded."""
        from zenos.interface.mcp import search

        l1 = _make_entity(id="ent-l1", name="Product", level=1)
        with patch("zenos.interface.mcp.ontology_service") as mock_os:
            mock_os.list_entities = AsyncMock(return_value=[l1])
            result = await search(collection="entities", entity_level="L1")

        af = result["applied_filters"]
        assert af["entity_level"]["input"] == "L1"
        assert af["entity_level"]["effective_max_level"] == 1
        assert af["entity_level"]["included_types"] == ["product"]
        # project/goal/role/module must appear in excluded_types so agent
        # understands why their L1=project entity didn't show up.
        assert "project" in af["entity_level"]["excluded_types"]
        assert "module" in af["entity_level"]["excluded_types"]
        assert af["visibility_applied"] is True

    async def test_completeness_declared_per_mode(self):
        """INV4: collection listing is exhaustive; keyword search is partial."""
        from zenos.interface.mcp import search

        with patch("zenos.interface.mcp.ontology_service") as mock_os:
            mock_os.list_entities = AsyncMock(return_value=[])
            listing = await search(collection="entities")
        assert listing["completeness"] == "exhaustive"

        with patch("zenos.interface.mcp.ontology_service") as mock_os, \
             patch("zenos.interface.mcp.task_service") as mock_ts, \
             patch("zenos.interface.mcp.entry_repo") as mock_er:
            mock_os.search = AsyncMock(return_value=[])
            mock_ts.list_tasks = AsyncMock(return_value=[])
            mock_er.search_content = AsyncMock(return_value=[])
            keyword = await search(query="foo", collection="all")
        assert keyword["completeness"] == "partial"

    async def test_product_id_filters_entities_to_subtree(self):
        """product_id filters entities to the product's subtree."""
        from zenos.interface.mcp import search

        product = _make_entity(id="prod-1", name="MyApp", type="product", level=1)
        child = _make_entity(id="mod-1", name="Auth", type="module", level=2, parent_id="prod-1")
        unrelated = _make_entity(id="mod-2", name="Billing", type="module", level=2, parent_id="prod-other")
        with patch("zenos.interface.mcp.ontology_service") as mock_os:
            mock_os.list_entities = AsyncMock(return_value=[product, child, unrelated])
            result = await search(collection="entities", product_id="prod-1")
            ids = [e["id"] for e in _ok_data(result)["entities"]]
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
            data = _ok_data(result)
            assert data["count"] == 2
            assert data["total"] == 5
            assert data["results"][0]["id"] == "ent-2"

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
            data = _non_ok_data(result, "rejected")

            assert data["error"] == "NOT_FOUND"
            assert "NonExistent" in data["message"]
            assert "hint" in data

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
            data = _ok_data(result)

            assert data["entity"]["name"] == "Paceriz"
            assert len(data["outgoing_relationships"]) == 1
            assert len(data["incoming_relationships"]) == 0

    async def test_get_entity_by_id(self):
        from zenos.interface.mcp import get

        entity = _make_entity()
        with patch("zenos.interface.mcp.entity_repo") as mock_er, \
             patch("zenos.interface.mcp.relationship_repo") as mock_rr:
            mock_er.get_by_id = AsyncMock(return_value=entity)
            mock_rr.list_by_entity = AsyncMock(return_value=[])

            result = await get(collection="entities", id="ent-1")

            assert _ok_data(result)["entity"]["id"] == "ent-1"

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

                assert _ok_data(allowed)["entity"]["id"] == "ent-shared"
                assert _non_ok_data(denied, "rejected")["error"] == "NOT_FOUND"
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

                assert _ok_data(allowed)["id"] == "doc-shared"
                assert _non_ok_data(denied, "rejected")["error"] == "NOT_FOUND"
        finally:
            _current_partner.reset(token)

    async def test_guest_get_document_allows_secondary_related_to_scope(self):
        from zenos.interface.mcp import get, _current_partner

        shared_root = _make_entity(id="product-acme", type="product", level=1, name="Acme", parent_id=None)
        shared_module = _make_entity(
            id="module-shared",
            name="Shared Module",
            type="module",
            level=2,
            parent_id="product-acme",
            visibility="public",
        )
        other_root = _make_entity(id="product-other", type="product", level=1, name="Other", parent_id=None)
        primary_module = _make_entity(
            id="module-other",
            name="Other Module",
            type="module",
            level=2,
            parent_id="product-other",
            visibility="public",
        )
        doc = _make_entity(
            id="doc-secondary-shared",
            name="Secondary Shared Doc",
            type="document",
            level=3,
            parent_id="module-other",
            visibility="public",
        )
        rel = Relationship(
            id="rel-doc-secondary",
            source_entity_id="doc-secondary-shared",
            target_id="module-shared",
            type="related_to",
            description="document linked to entity",
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
                mock_er.list_all = AsyncMock(return_value=[shared_root, shared_module, other_root, primary_module, doc])
                mock_os.get_document = AsyncMock(return_value=doc)
                mock_os._relationships = AsyncMock()
                mock_os._relationships.list_by_entity = AsyncMock(return_value=[rel])
                mock_os._entities = AsyncMock()
                mock_os._entities.list_all = AsyncMock(return_value=[shared_root, shared_module, other_root, primary_module, doc])

                result = await get(collection="documents", id="doc-secondary-shared")

                assert _ok_data(result)["id"] == "doc-secondary-shared"
        finally:
            _current_partner.reset(token)

    async def test_get_entity_not_found(self):
        from zenos.interface.mcp import get

        with patch("zenos.interface.mcp.ontology_service") as mock_os:
            mock_os.get_entity = AsyncMock(return_value=None)

            result = await get(collection="entities", name="NonExistent")

            assert _non_ok_data(result, "rejected")["error"] == "NOT_FOUND"

    async def test_get_no_name_no_id(self):
        from zenos.interface.mcp import get

        result = await get(collection="entities")
        data = _non_ok_data(result, "rejected")

        assert data["error"] == "INVALID_INPUT"
        assert "Must provide" in data["message"]

    async def test_get_unknown_collection(self):
        from zenos.interface.mcp import get

        result = await get(collection="foobar", name="test")
        data = _non_ok_data(result, "rejected")

        assert data["error"] == "INVALID_INPUT"
        assert "Unknown collection" in data["message"]

    async def test_get_task_by_id(self):
        from zenos.interface.mcp import get

        task = _make_task()
        enrichments = {"expanded_entities": []}
        with patch("zenos.interface.mcp.task_service") as mock_ts:
            mock_ts.get_task_enriched = AsyncMock(return_value=(task, enrichments))

            result = await get(collection="tasks", id="task-1")

            assert _ok_data(result)["title"] == "Fix login"

    async def test_get_task_not_found(self):
        from zenos.interface.mcp import get

        with patch("zenos.interface.mcp.task_service") as mock_ts:
            mock_ts.get_task_enriched = AsyncMock(return_value=None)

            result = await get(collection="tasks", id="nonexistent")

            assert _non_ok_data(result, "rejected")["error"] == "NOT_FOUND"

    async def test_get_task_requires_id(self):
        from zenos.interface.mcp import get

        result = await get(collection="tasks", name="some-name")
        data = _non_ok_data(result, "rejected")

        assert data["error"] == "INVALID_INPUT"
        assert "id" in data["message"].lower()

    async def test_get_blindspot_by_id(self):
        from zenos.interface.mcp import get

        bs = _make_blindspot()
        with patch("zenos.interface.mcp.blindspot_repo") as mock_br:
            mock_br.get_by_id = AsyncMock(return_value=bs)

            result = await get(collection="blindspots", id="bs-1")

            assert _ok_data(result)["description"] == "No monitoring"

    async def test_get_document_by_id(self):
        from zenos.interface.mcp import get

        doc = _make_document()
        with patch("zenos.interface.mcp.ontology_service") as mock_os:
            mock_os.get_document = AsyncMock(return_value=doc)

            result = await get(collection="documents", id="doc-1")

            assert _ok_data(result)["title"] == "API Spec"

    async def test_get_document_exposes_canonical_linked_entity_ids(self):
        from zenos.interface.mcp import get

        doc = _make_entity(
            id="doc-1",
            name="Shared Spec",
            type="document",
            parent_id="module-primary",
            summary="spec",
        )
        primary = _make_entity(id="module-primary", name="Primary Module", type="module")
        secondary = _make_entity(id="module-secondary", name="Secondary Module", type="module")
        rel = Relationship(
            id="rel-1",
            source_entity_id="doc-1",
            target_id="module-secondary",
            type="related_to",
            description="document linked to entity",
        )

        with patch("zenos.interface.mcp.ontology_service") as mock_os:
            mock_os.get_document = AsyncMock(return_value=doc)
            mock_os._relationships = AsyncMock()
            mock_os._relationships.list_by_entity = AsyncMock(return_value=[rel])
            mock_os._entities = AsyncMock()
            mock_os._entities.list_all = AsyncMock(return_value=[primary, secondary, doc])

            result = await get(collection="documents", id="doc-1")
            data = _ok_data(result)

            assert data["linked_entity_ids"] == ["module-primary", "module-secondary"]
            assert data["primary_linked_entity_id"] == "module-primary"
            assert data["related_entity_ids"] == ["module-secondary"]
            assert [e["name"] for e in data["linked_entities"]] == ["Primary Module", "Secondary Module"]

    async def test_get_protocol_by_id_prefers_protocol_doc_id(self):
        from zenos.interface.mcp import get

        proto = _make_protocol(id="proto-1", entity_id="ent-1")
        with patch("zenos.interface.mcp.protocol_repo") as mock_pr:
            mock_pr.get_by_id = AsyncMock(return_value=proto)
            mock_pr.get_by_entity = AsyncMock(return_value=None)

            result = await get(collection="protocols", id="proto-1")

            assert _ok_data(result)["id"] == "proto-1"
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
            data = _ok_data(result)

            assert data["doc_id"] == "doc-1"
            assert data["content"] == "# Hello World"

    async def test_read_source_not_found(self):
        from zenos.interface.mcp import read_source

        with patch("zenos.interface.mcp.source_service") as mock_ss:
            mock_ss.read_source = AsyncMock(side_effect=ValueError("Doc not found"))

            result = await read_source(doc_id="nonexistent")

            assert _non_ok_data(result, "rejected")["error"] == "NOT_FOUND"

    async def test_read_source_file_not_found(self):
        from zenos.interface.mcp import read_source

        with patch("zenos.interface.mcp.source_service") as mock_ss:
            mock_ss.read_source = AsyncMock(
                side_effect=FileNotFoundError("File missing"))

            result = await read_source(doc_id="doc-1")

            assert _non_ok_data(result, "rejected")["error"] == "NOT_FOUND"

    async def test_read_source_permission_error(self):
        from zenos.interface.mcp import read_source

        with patch("zenos.interface.mcp.source_service") as mock_ss:
            mock_ss.read_source = AsyncMock(
                side_effect=PermissionError("No access"))

            result = await read_source(doc_id="doc-1")
            data = _non_ok_data(result, "error")

            assert data["error"] == "ADAPTER_ERROR"
            assert "Permission denied" in data["message"]

    async def test_read_source_runtime_error(self):
        from zenos.interface.mcp import read_source

        with patch("zenos.interface.mcp.source_service") as mock_ss:
            mock_ss.read_source = AsyncMock(
                side_effect=RuntimeError("Adapter broken"))

            result = await read_source(doc_id="doc-1")

            assert _non_ok_data(result, "error")["error"] == "ADAPTER_ERROR"

    async def test_read_source_zenos_native_without_revision_returns_snapshot_unavailable(self):
        from zenos.interface.mcp import read_source

        doc = _make_entity(
            id="doc-native",
            name="Native Doc",
            type="document",
            sources=[{
                "source_id": "src-native",
                "uri": "/docs/doc-native",
                "type": "zenos_native",
                "status": "valid",
                "source_status": "valid",
            }],
        )

        with patch("zenos.interface.mcp.ontology_service") as mock_os, \
             patch("zenos.interface.mcp.source_service") as mock_ss:
            mock_os.get_document = AsyncMock(return_value=doc)
            mock_os._relationships = AsyncMock()
            mock_os._relationships.list_by_entity = AsyncMock(return_value=[])
            mock_ss.read_source_with_snapshot = AsyncMock(return_value={"error": "NOT_FOUND"})

            result = await read_source(doc_id="doc-native")
            data = _non_ok_data(result, "error")

            assert data["error"] == "SNAPSHOT_UNAVAILABLE"
            assert data["source_type"] == "zenos_native"
            assert "Dashboard 儲存文件" in data["setup_hint"]

    async def test_read_source_zenos_native_returns_snapshot_content(self):
        from zenos.interface.mcp import read_source

        doc = _make_entity(
            id="doc-native",
            name="Native Doc",
            type="document",
            sources=[{
                "source_id": "src-native",
                "uri": "/docs/doc-native",
                "type": "zenos_native",
                "status": "valid",
                "source_status": "valid",
            }],
        )

        with patch("zenos.interface.mcp.ontology_service") as mock_os, \
             patch("zenos.interface.mcp.source_service") as mock_ss:
            mock_os.get_document = AsyncMock(return_value=doc)
            mock_os._relationships = AsyncMock()
            mock_os._relationships.list_by_entity = AsyncMock(return_value=[])
            mock_ss.read_source_with_snapshot = AsyncMock(return_value={
                "content": "# Native",
                "content_type": "full",
                "source_id": "src-native",
            })

            result = await read_source(doc_id="doc-native")
            data = _ok_data(result)

            assert data["content"] == "# Native"
            assert data["content_type"] == "full"


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
            assert result["data"]["id"] == entity.id
            assert result["data"]["name"] == entity.name
            assert result["data"]["type"] == entity.type
            assert result["data"]["level"] == entity.level
            assert result["data"]["status"] == entity.status
            assert result["data"]["parent_id"] == entity.parent_id
            assert result["data"]["entity_id"] == entity.id
            assert result["data"]["entity_name"] == entity.name
            assert result["data"]["entity"]["id"] == entity.id
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

    async def test_write_relationship_delete_by_id_success(self):
        from zenos.interface.mcp import write

        with patch("zenos.interface.mcp.relationship_repo") as mock_rr:
            mock_rr.remove_by_id = AsyncMock(return_value=1)

            result = await write(
                collection="relationships",
                id="rel-1",
                data={"action": "delete", "reason": "remove invalid impacts target"},
            )

            assert result["status"] == "ok"
            assert result["data"]["id"] == "rel-1"
            assert result["data"]["deleted"] is True
            assert result["data"]["reason"] == "remove invalid impacts target"

    async def test_write_relationship_delete_by_id_missing_returns_rejected(self):
        from zenos.interface.mcp import write

        with patch("zenos.interface.mcp.relationship_repo") as mock_rr:
            mock_rr.remove_by_id = AsyncMock(return_value=0)

            result = await write(
                collection="relationships",
                id="rel-missing",
                data={"action": "delete", "reason": "cleanup"},
            )

            assert result["status"] == "rejected"
            assert "Relationship" in result["rejection_reason"]

    async def test_write_relationship_impacts_non_concrete_returns_rejected(self):
        from zenos.interface.mcp import write

        with patch("zenos.interface.mcp.ontology_service") as mock_os:
            mock_os.add_relationship = AsyncMock(
                side_effect=ValueError(
                    "impacts relationship description must be concrete. "
                    "Use format: A 改了什麼 → B 的什麼要跟著看"
                )
            )

            result = await write(
                collection="relationships",
                data={
                    "source_entity_id": "ent-1",
                    "target_entity_id": "ent-2",
                    "type": "impacts",
                    "description": "A affects B",
                },
            )

            assert result["status"] == "rejected"
            assert "impacts relationship description must be concrete" in result["rejection_reason"]

    async def test_write_patches_dry_run_validates_document_repair_patches(self):
        from zenos.interface.mcp import write

        patch_payload = {
            "tool": "write",
            "collection": "documents",
            "needs_agent_review": True,
            "data": {
                "id": "doc-1",
                "title": "Spec Index",
                "doc_role": "index",
                "summary": "Agent 找到對應 L2 後，先讀這份 summary 再選 source。",
                "linked_entity_ids": ["module-1"],
            },
        }

        with patch("zenos.interface.mcp.ontology_service") as mock_os:
            result = await write(
                collection="patches",
                data={"dry_run": True, "patches": [patch_payload]},
            )

        data = _ok_data(result)
        assert data["dry_run"] is True
        assert data["validated_count"] == 1
        assert data["patches"][0]["data"]["id"] == "doc-1"
        mock_os.upsert_document.assert_not_called()

    async def test_write_patches_dry_run_validates_index_create_patch(self):
        from zenos.interface.mcp import write

        patch_payload = {
            "tool": "write",
            "collection": "documents",
            "needs_agent_review": True,
            "data": {
                "id": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                "create_index_document": True,
                "title": "Action Layer：文件群索引",
                "status": "current",
                "doc_role": "index",
                "formal_entry": True,
                "linked_entity_ids": ["module-1"],
                "tags": {"what": ["Action Layer"], "why": "routing", "how": "index", "who": ["agent"]},
                "summary": "Agent 找到 L2 後，先讀這份 retrieval map 再選 source。",
                "change_summary": "Analyzer 建議建立 current index document。",
                "sources": [{
                    "source_id": "src-1",
                    "type": "zenos_native",
                    "uri": "/docs/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                    "label": "GUIDE: Action Layer index",
                    "doc_type": "GUIDE",
                    "doc_status": "current",
                    "is_primary": True,
                    "retrieval_mode": "snapshot",
                    "content_access": "full",
                }],
                "bundle_highlights": [{
                    "source_id": "src-1",
                    "headline": "Action Layer index",
                    "reason_to_read": "需要理解 Action Layer 的文件入口時先讀。",
                    "priority": "primary",
                }],
            },
        }

        with patch("zenos.interface.mcp.ontology_service") as mock_os:
            result = await write(
                collection="patches",
                data={"dry_run": True, "patches": [patch_payload]},
            )

        data = _ok_data(result)
        assert data["dry_run"] is True
        assert data["validated_count"] == 1
        assert data["patches"][0]["data"]["create_index_document"] is True
        mock_os.upsert_document.assert_not_called()

    async def test_write_patches_rejects_index_create_with_wrong_source_uri(self):
        from zenos.interface.mcp import write

        result = await write(
            collection="patches",
            data={
                "patches": [{
                    "tool": "write",
                    "collection": "documents",
                    "needs_agent_review": True,
                    "data": {
                        "id": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                        "create_index_document": True,
                        "title": "Action Layer：文件群索引",
                        "status": "current",
                        "doc_role": "index",
                        "linked_entity_ids": ["module-1"],
                        "tags": {"what": ["Action Layer"], "why": "routing", "how": "index", "who": ["agent"]},
                        "summary": "Agent 找到 L2 後，先讀這份 retrieval map 再選 source。",
                        "change_summary": "Analyzer 建議建立 current index document。",
                        "sources": [{
                            "source_id": "src-1",
                            "type": "zenos_native",
                            "uri": "/docs/other-doc",
                            "is_primary": True,
                        }],
                        "bundle_highlights": [{
                            "source_id": "src-1",
                            "headline": "Action Layer index",
                            "reason_to_read": "需要理解 Action Layer 的文件入口時先讀。",
                            "priority": "primary",
                        }],
                    },
                }],
            },
        )

        data = _non_ok_data(result, "rejected")
        assert data["errors"][0]["reason"] == "patch_create_index_source_uri_must_match_document"

    async def test_write_patches_rejects_non_document_patch_batch(self):
        from zenos.interface.mcp import write

        result = await write(
            collection="patches",
            data={
                "patches": [{
                    "tool": "write",
                    "collection": "relationships",
                    "needs_agent_review": True,
                    "data": {
                        "source_entity_id": "a",
                        "target_entity_id": "b",
                        "type": "related_to",
                        "description": "x",
                    },
                }],
            },
        )

        data = _non_ok_data(result, "rejected")
        assert result["rejection_reason"] == "invalid_patch_batch"
        assert data["errors"][0]["reason"] == "patch_collection_must_be_documents"
        assert any("tool=write" in s and "collection=documents" in s for s in result["suggestions"])

    async def test_write_patches_missing_review_flag_suggests_preserving_analyzer_patch(self):
        from zenos.interface.mcp import write

        result = await write(
            collection="patches",
            data={
                "dry_run": True,
                "patches": [{
                    "tool": "write",
                    "collection": "documents",
                    "data": {
                        "id": "doc-1",
                        "title": "Spec Index",
                        "summary": "Agent 找到對應 L2 後，先讀這份 summary 再選 source。",
                    },
                }],
            },
        )

        data = _non_ok_data(result, "rejected")
        assert data["errors"][0]["reason"] == "patch_must_be_analyzer_reviewable"
        assert any("needs_agent_review=true" in s for s in result["suggestions"])

    async def test_write_patches_rejects_disallowed_document_fields(self):
        from zenos.interface.mcp import write

        result = await write(
            collection="patches",
            data={
                "patches": [{
                    "tool": "write",
                    "collection": "documents",
                    "needs_agent_review": True,
                    "data": {
                        "id": "doc-1",
                        "title": "Spec Index",
                        "sync_mode": "archive",
                    },
                }],
            },
        )

        data = _non_ok_data(result, "rejected")
        assert data["errors"][0]["reason"] == "patch_data_has_disallowed_fields"
        assert data["errors"][0]["fields"] == ["sync_mode"]
        assert any("suggested_write_patch" in s for s in result["suggestions"])

    async def test_write_patches_rejects_unsafe_add_source_patch(self):
        from zenos.interface.mcp import write

        result = await write(
            collection="patches",
            data={
                "patches": [{
                    "tool": "write",
                    "collection": "documents",
                    "needs_agent_review": True,
                    "data": {
                        "id": "doc-1",
                        "title": "Spec Index",
                        "add_source": {
                            "type": "github",
                            "uri": "https://github.com/acme/repo/blob/main/spec.md",
                            "is_primary": True,
                        },
                    },
                }],
            },
        )

        data = _non_ok_data(result, "rejected")
        assert data["errors"][0]["reason"] == "patch_add_source_must_be_zenos_native"
        assert any("add_source repair patch" in s for s in result["suggestions"])

    async def test_write_patches_rejects_invalid_add_source_retrieval_mode(self):
        from zenos.interface.mcp import write

        result = await write(
            collection="patches",
            data={
                "patches": [{
                    "tool": "write",
                    "collection": "documents",
                    "needs_agent_review": True,
                    "data": {
                        "id": "doc-1",
                        "title": "Spec Index",
                        "add_source": {
                            "type": "zenos_native",
                            "uri": "/docs/doc-1",
                            "is_primary": True,
                            "retrieval_mode": "full",
                        },
                    },
                }],
            },
        )

        data = _non_ok_data(result, "rejected")
        assert data["errors"][0]["reason"] == "patch_add_source_invalid_retrieval_mode"

    async def test_write_patches_rejects_invalid_add_source_doc_type(self):
        from zenos.interface.mcp import write

        result = await write(
            collection="patches",
            data={
                "patches": [{
                    "tool": "write",
                    "collection": "documents",
                    "needs_agent_review": True,
                    "data": {
                        "id": "doc-1",
                        "title": "Spec Index",
                        "add_source": {
                            "type": "zenos_native",
                            "uri": "/docs/doc-1",
                            "is_primary": True,
                            "doc_type": "NOT_A_TYPE",
                        },
                    },
                }],
            },
        )

        data = _non_ok_data(result, "rejected")
        assert data["errors"][0]["reason"] == "patch_add_source_invalid_doc_type"

    async def test_write_patches_applies_documents_sequentially(self):
        from zenos.interface.mcp import write
        from zenos.domain.knowledge import Entity, Tags

        doc = Entity(
            id="doc-1",
            name="Spec Index",
            type="document",
            summary="retrieval map",
            tags=Tags(what=["spec"], why="governance", how="mcp", who=["agent"]),
            status="current",
            parent_id="module-1",
            sources=[],
            doc_role="index",
        )
        patch_payload = {
            "tool": "write",
            "collection": "documents",
            "needs_agent_review": True,
            "data": {
                "id": "doc-1",
                "title": "Spec Index",
                "status": "current",
                "doc_role": "index",
                "summary": "Agent 找到對應 L2 後，先讀這份 summary 再選 source。",
                "linked_entity_ids": ["module-1"],
            },
        }

        with (
            patch("zenos.interface.mcp.ontology_service") as mock_os,
            patch("zenos.interface.mcp.write._load_document_relationships", new=AsyncMock(return_value=[])),
            patch("zenos.interface.mcp.write._document_delivery_suggestions", new=AsyncMock(return_value=[])),
            patch("zenos.interface.mcp.write._maybe_auto_publish_document", new=AsyncMock(return_value=[])),
            patch("zenos.interface.mcp.write._build_context_bundle", new=AsyncMock(return_value={})),
            patch("zenos.interface.mcp.write._audit_log"),
        ):
            mock_os.upsert_document = AsyncMock(return_value=doc)

            result = await write(
                collection="patches",
                data={"patches": [patch_payload], "source": "analyze.invalid_documents"},
            )

        data = _ok_data(result)
        assert data["applied_count"] == 1
        assert data["rejected_count"] == 0
        assert data["applied"][0]["document_id"] == "doc-1"
        mock_os.upsert_document.assert_awaited_once()
        call_data = mock_os.upsert_document.await_args.args[0]
        assert call_data["id"] == "doc-1"
        assert call_data["summary"].startswith("Agent 找到對應 L2")

    async def test_write_patches_accepts_top_level_source_metadata(self):
        from zenos.interface.mcp import write
        from zenos.domain.knowledge import Entity, Tags

        doc = Entity(
            id="doc-1",
            name="Spec Index",
            type="document",
            summary="retrieval map",
            tags=Tags(what=["spec"], why="governance", how="mcp", who=["agent"]),
            status="current",
            parent_id="module-1",
            sources=[],
            doc_role="index",
        )
        patch_payload = {
            "tool": "write",
            "collection": "documents",
            "needs_agent_review": True,
            "data": {
                "id": "doc-1",
                "title": "Spec Index",
                "status": "current",
                "doc_role": "index",
                "summary": "Agent 找到對應 L2 後，先讀這份 summary 再選 source。",
                "linked_entity_ids": ["module-1"],
            },
        }

        with (
            patch("zenos.interface.mcp.ontology_service") as mock_os,
            patch("zenos.interface.mcp.write._load_document_relationships", new=AsyncMock(return_value=[])),
            patch("zenos.interface.mcp.write._document_delivery_suggestions", new=AsyncMock(return_value=[])),
            patch("zenos.interface.mcp.write._maybe_auto_publish_document", new=AsyncMock(return_value=[])),
            patch("zenos.interface.mcp.write._build_context_bundle", new=AsyncMock(return_value={})),
            patch("zenos.interface.mcp.write._audit_log") as audit_log,
        ):
            mock_os.upsert_document = AsyncMock(return_value=doc)

            result = await write(
                collection="patches",
                data={"patches": [patch_payload]},
                source="dogfood.patch_batch",
            )

        data = _ok_data(result)
        assert data["applied_count"] == 1
        audit_log.assert_called()
        assert audit_log.call_args.kwargs["changes"]["source"] == "dogfood.patch_batch"

    async def test_write_patches_applies_index_create_with_internal_allow_create(self):
        from zenos.interface.mcp import write
        from zenos.domain.knowledge import Entity, Tags

        doc = Entity(
            id="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            name="Action Layer：文件群索引",
            type="document",
            summary="retrieval map",
            tags=Tags(what=["Action Layer"], why="routing", how="index", who=["agent"]),
            status="current",
            parent_id="module-1",
            sources=[{
                "source_id": "src-1",
                "type": "zenos_native",
                "uri": "/docs/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                "is_primary": True,
            }],
            doc_role="index",
            bundle_highlights=[{
                "source_id": "src-1",
                "headline": "Action Layer index",
                "reason_to_read": "需要理解 Action Layer 的文件入口時先讀。",
                "priority": "primary",
            }],
        )
        patch_payload = {
            "tool": "write",
            "collection": "documents",
            "needs_agent_review": True,
            "data": {
                "id": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                "create_index_document": True,
                "title": "Action Layer：文件群索引",
                "status": "current",
                "doc_role": "index",
                "linked_entity_ids": ["module-1"],
                "tags": {"what": ["Action Layer"], "why": "routing", "how": "index", "who": ["agent"]},
                "summary": "Agent 找到 L2 後，先讀這份 retrieval map 再選 source。",
                "change_summary": "Analyzer 建議建立 current index document。",
                "sources": [{
                    "source_id": "src-1",
                    "type": "zenos_native",
                    "uri": "/docs/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                    "label": "GUIDE: Action Layer index",
                    "doc_type": "GUIDE",
                    "doc_status": "current",
                    "is_primary": True,
                    "retrieval_mode": "snapshot",
                    "content_access": "full",
                }],
                "bundle_highlights": [{
                    "source_id": "src-1",
                    "headline": "Action Layer index",
                    "reason_to_read": "需要理解 Action Layer 的文件入口時先讀。",
                    "priority": "primary",
                }],
            },
        }

        with (
            patch("zenos.interface.mcp.ontology_service") as mock_os,
            patch("zenos.interface.mcp.write._load_document_relationships", new=AsyncMock(return_value=[])),
            patch("zenos.interface.mcp.write._document_delivery_suggestions", new=AsyncMock(return_value=[])),
            patch("zenos.interface.mcp.write._maybe_auto_publish_document", new=AsyncMock(return_value=[])),
            patch("zenos.interface.mcp.write._build_context_bundle", new=AsyncMock(return_value={})),
            patch("zenos.interface.mcp.write._audit_log"),
        ):
            mock_os.upsert_document = AsyncMock(return_value=doc)

            result = await write(
                collection="patches",
                data={"patches": [patch_payload], "source": "analyze.invalid_documents"},
            )

        data = _ok_data(result)
        assert data["applied_count"] == 1
        call_data = mock_os.upsert_document.await_args.args[0]
        assert call_data["id"] == "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
        assert call_data["allow_create_with_id"] is True
        assert "create_index_document" not in call_data

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

    async def test_write_documents_adds_delivery_suggestions_for_current_formal_entry(self):
        from zenos.interface.mcp import write, _current_partner
        from zenos.domain.knowledge import Entity, Tags

        doc = Entity(
            id="doc-1",
            name="Spec",
            type="document",
            summary="summary",
            tags=Tags(what=["demo"], why="why", how="how", who=["pm"]),
            status="current",
            parent_id="module-1",
            sources=[{
                "source_id": "src-1",
                "uri": "https://github.com/acme/repo/blob/main/docs/spec.md",
                "type": "github",
                "status": "valid",
                "source_status": "valid",
                "is_primary": True,
            }],
            doc_role="index",
            bundle_highlights=[{
                "source_id": "src-1",
                "headline": "SSOT",
                "reason_to_read": "primary",
                "priority": "primary",
            }],
        )

        conn = MagicMock()
        conn.fetchrow = AsyncMock(return_value={
            "primary_snapshot_revision_id": None,
            "delivery_status": None,
        })
        pool = MagicMock()
        pool.acquire = MagicMock(return_value=_Acquire(conn))

        token = _current_partner.set({"id": "partner-1", "isAdmin": False})
        try:
            with (
                patch("zenos.interface.mcp.ontology_service") as mock_os,
                patch("zenos.interface.mcp.write.get_pool", new=AsyncMock(return_value=pool)),
                patch("zenos.interface.mcp.write._build_context_bundle", new=AsyncMock(return_value={})),
                patch("zenos.interface.mcp.write._audit_log"),
                patch("zenos.interface.dashboard_api._publish_document_snapshot_internal", new=AsyncMock(return_value={"revision_id": "rev-1"})),
            ):
                mock_os.upsert_document = AsyncMock(return_value=doc)

                result = await write(
                    collection="documents",
                    data={
                        "title": "Spec",
                        "summary": "summary",
                        "tags": {"what": ["demo"], "why": "why", "how": "how", "who": ["pm"]},
                        "linked_entity_ids": ["module-1"],
                    },
                )

            assert result["status"] == "ok"
            assert any("git + gcs" in s for s in result["suggestions"])
            assert any("delivery snapshot" in s for s in result["suggestions"])
            assert any("自動補上 delivery snapshot" in s for s in result["suggestions"])
        finally:
            _current_partner.reset(token)

    async def test_write_documents_uses_explicit_formal_entry_flag(self):
        from zenos.interface.mcp import write, _current_partner
        from zenos.domain.knowledge import Entity, Tags

        doc = Entity(
            id="doc-1",
            name="Spec",
            type="document",
            summary="summary",
            tags=Tags(what=["demo"], why="why", how="how", who=["pm"]),
            status="current",
            parent_id=None,
            details={"formal_entry": True},
            sources=[{
                "source_id": "src-1",
                "uri": "https://github.com/acme/repo/blob/main/docs/spec.md",
                "type": "github",
                "status": "valid",
                "source_status": "valid",
                "is_primary": True,
            }],
            doc_role="single",
        )

        conn = MagicMock()
        conn.fetchrow = AsyncMock(return_value={
            "primary_snapshot_revision_id": None,
            "delivery_status": None,
        })
        pool = MagicMock()
        pool.acquire = MagicMock(return_value=_Acquire(conn))

        token = _current_partner.set({"id": "partner-1", "isAdmin": False})
        try:
            with (
                patch("zenos.interface.mcp.ontology_service") as mock_os,
                patch("zenos.interface.mcp.write.get_pool", new=AsyncMock(return_value=pool)),
                patch("zenos.interface.mcp.write._build_context_bundle", new=AsyncMock(return_value={})),
                patch("zenos.interface.mcp.write._audit_log"),
                patch("zenos.interface.dashboard_api._publish_document_snapshot_internal", new=AsyncMock(return_value={"revision_id": "rev-1"})),
            ):
                mock_os.upsert_document = AsyncMock(return_value=doc)

                result = await write(
                    collection="documents",
                    data={
                        "title": "Spec",
                        "summary": "summary",
                        "tags": {"what": ["demo"], "why": "why", "how": "how", "who": ["pm"]},
                        "linked_entity_ids": ["module-1"],
                    },
                )

            assert result["status"] == "ok"
            assert any("git + gcs" in s for s in result["suggestions"])
        finally:
            _current_partner.reset(token)

    async def test_write_documents_response_echoes_normalized_multi_linkage(self):
        from zenos.interface.mcp import write, _current_partner
        from zenos.domain.knowledge import Entity, Tags

        doc = Entity(
            id="doc-1",
            name="Shared Spec",
            type="document",
            summary="summary",
            tags=Tags(what=["demo"], why="why", how="how", who=["pm"]),
            status="draft",
            parent_id="module-primary",
            sources=[],
            doc_role="index",
        )
        rel = Relationship(
            id="rel-1",
            source_entity_id="doc-1",
            target_id="module-secondary",
            type="related_to",
            description="document linked to entity",
        )

        token = _current_partner.set({"id": "partner-1", "isAdmin": False})
        try:
            with (
                patch("zenos.interface.mcp.ontology_service") as mock_os,
                patch("zenos.interface.mcp.write._build_context_bundle", new=AsyncMock(return_value={})),
                patch("zenos.interface.mcp.write._audit_log"),
            ):
                mock_os.upsert_document = AsyncMock(return_value=doc)
                mock_os._relationships = AsyncMock()
                mock_os._relationships.list_by_entity = AsyncMock(return_value=[rel])

                result = await write(
                    collection="documents",
                    data={
                        "title": "Shared Spec",
                        "summary": "summary",
                        "status": "draft",
                        "tags": {"what": ["demo"], "why": "why", "how": "how", "who": ["pm"]},
                        "linked_entity_ids": ["module-primary", "module-secondary"],
                    },
                )

            data = _ok_data(result)
            assert data["linked_entity_ids"] == ["module-primary", "module-secondary"]
            assert data["primary_linked_entity_id"] == "module-primary"
            assert data["related_entity_ids"] == ["module-secondary"]
        finally:
            _current_partner.reset(token)

    async def test_write_documents_rejects_missing_linked_entity_ids_with_error_code(self):
        from zenos.interface.mcp import write
        from zenos.application.knowledge.ontology_service import DocumentLinkageValidationError

        with (
            patch("zenos.interface.mcp.ontology_service") as mock_os,
            patch("zenos.interface.mcp.write._audit_log"),
        ):
            mock_os.upsert_document = AsyncMock(
                side_effect=DocumentLinkageValidationError(
                    "LINKED_ENTITY_IDS_REQUIRED",
                    "linked_entity_ids 為必填；請先 search(collection='entities') 找到合法 entity IDs 後再寫入 document。",
                )
            )

            result = await write(
                collection="documents",
                data={
                    "title": "Spec",
                    "summary": "summary",
                    "tags": {"what": ["demo"], "why": "why", "how": "how", "who": ["pm"]},
                },
            )

        assert result["status"] == "rejected"
        assert result["data"]["error"]["code"] == "LINKED_ENTITY_IDS_REQUIRED"
        assert "linked_entity_ids 為必填" in result["data"]["message"]
        assert any("search(collection='entities')" in s for s in result["suggestions"])

    async def test_write_documents_rejects_missing_entity_ids_with_details(self):
        from zenos.interface.mcp import write
        from zenos.application.knowledge.ontology_service import DocumentLinkageValidationError

        with (
            patch("zenos.interface.mcp.ontology_service") as mock_os,
            patch("zenos.interface.mcp.write._audit_log"),
        ):
            mock_os.upsert_document = AsyncMock(
                side_effect=DocumentLinkageValidationError(
                    "LINKED_ENTITY_NOT_FOUND",
                    "linked_entity_ids 包含不存在的 entity ID；請確認後重試。",
                    missing_entity_ids=["ghost-1"],
                )
            )

            result = await write(
                collection="documents",
                data={
                    "title": "Spec",
                    "summary": "summary",
                    "tags": {"what": ["demo"], "why": "why", "how": "how", "who": ["pm"]},
                    "linked_entity_ids": ["ghost-1"],
                },
            )

        assert result["status"] == "rejected"
        assert result["data"]["error"]["code"] == "LINKED_ENTITY_NOT_FOUND"
        assert result["data"]["error"]["missing_entity_ids"] == ["ghost-1"]

    async def test_write_documents_rejects_unpushed_github_for_explicit_formal_entry(self):
        from zenos.interface.mcp import write, _current_partner

        token = _current_partner.set({"id": "partner-1", "isAdmin": False})
        try:
            with (
                patch("zenos.interface.mcp.ontology_service") as mock_os,
                patch("zenos.interface.mcp.write._audit_log"),
                patch("zenos.interface.mcp.write.GitHubAdapter") as mock_adapter_cls,
            ):
                mock_adapter = MagicMock()
                mock_adapter.read_content = AsyncMock(side_effect=FileNotFoundError("not pushed"))
                mock_adapter_cls.return_value = mock_adapter

                result = await write(
                    collection="documents",
                    data={
                        "title": "Spec",
                        "summary": "summary",
                        "tags": {"what": ["demo"], "why": "why", "how": "how", "who": ["pm"]},
                        "formal_entry": True,
                        "status": "current",
                        "source": {
                            "type": "github",
                            "uri": "https://github.com/acme/repo/blob/main/docs/spec.md",
                        },
                    },
                )

            assert result["status"] == "rejected"
            assert "remote 可見" in result["rejection_reason"]
            assert any("push 到 remote" in s for s in result["suggestions"])
            mock_os.upsert_document.assert_not_called()
        finally:
            _current_partner.reset(token)

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
                {"entity_id": "ent-2", "type": "insight", "content": "決策：entry 只記 code/git log 讀不出的長期脈絡。"},
            ]
            await confirm(
                collection="tasks",
                id="task-review",
                accepted=True,
                entity_entries=entries,
            )

            # Only the valid entry should be written
            assert mock_entry_repo.create.call_count == 1

    async def test_confirm_task_entity_entries_skips_completion_reports(self):
        from zenos.interface.mcp import confirm
        from zenos.application.action.task_service import TaskResult

        t = _make_task(id="task-review", status="done")
        confirm_result = TaskResult(task=t, cascade_updates=[])

        with patch("zenos.interface.mcp.task_service") as mock_ts, \
             patch("zenos.interface.mcp.entry_repo") as mock_entry_repo:
            mock_ts.confirm_task = AsyncMock(return_value=confirm_result)
            mock_entry_repo.create = AsyncMock(side_effect=lambda e: e)

            entries = [
                {"entity_id": "ent-1", "type": "change", "content": "QA PASS；pytest 337 passed；AC-DF-01 通過"},
                {"entity_id": "ent-2", "type": "decision", "content": "決策：journal 僅保留重大 flow；task completion 留在 task.result，不寫 entry。"},
            ]
            result = await confirm(
                collection="tasks",
                id="task-review",
                accepted=True,
                entity_entries=entries,
            )

            assert mock_entry_repo.create.call_count == 1
            assert any("entry_is_acceptance_report" in warning for warning in result["warnings"])

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
                product_id="prod-1",
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
                product_id="prod-1",
            )
            payload = mock_ts.create_task.call_args.args[0]
            assert payload["linked_entities"] == ["ent-1", "ent-2"]
            assert payload["acceptance_criteria"] == ["a", "b"]

    async def test_create_task_normalizes_project_scope(self):
        from zenos.interface.mcp import task, _current_partner, entity_repo
        from zenos.application.action.task_service import TaskResult

        t = _make_task(project="Paceriz", product_id="prod-1")
        create_result = TaskResult(task=t, cascade_updates=[])
        token_partner = _current_partner.set({"id": "partner-1", "defaultProject": "  Paceriz  "})
        try:
            with patch("zenos.interface.mcp.task_service") as mock_ts:
                mock_ts.create_task = AsyncMock(return_value=create_result)
                entity_repo.get_by_name = AsyncMock(return_value=_make_entity(id="prod-1", name="Paceriz", level=1))

                await task(
                    action="create",
                    title="Fix login",
                    created_by="architect",
                )

                payload = mock_ts.create_task.call_args.args[0]
                assert payload["project"] == "paceriz"
        finally:
            _current_partner.reset(token_partner)

    async def test_create_task_forwards_product_id(self):
        from zenos.interface.mcp import task
        from zenos.application.action.task_service import TaskResult

        t = _make_task(project="paceriz", product_id="prod-1")
        create_result = TaskResult(task=t, cascade_updates=[])
        with patch("zenos.interface.mcp.task_service") as mock_ts:
            mock_ts.create_task = AsyncMock(return_value=create_result)

            await task(
                action="create",
                title="Fix login",
                created_by="architect",
                product_id="prod-1",
            )

            payload = mock_ts.create_task.call_args.args[0]
            assert payload["product_id"] == "prod-1"

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
            product_id="prod-1",
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
                product_id="prod-1",
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
                product_id="prod-1",
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
                product_id="prod-1",
            )

            payload = mock_ts.create_task.call_args.args[0]
            assert payload["source_metadata"]["sync_sources"] == metadata["sync_sources"]
            assert payload["source_metadata"]["provenance"] == metadata["provenance"]
            assert payload["source_metadata"]["created_via_agent"] is True

    async def test_create_task_returns_auto_inferred_missing_link_warning(self):
        from zenos.interface.mcp import task
        from zenos.application.action.task_service import TaskResult

        warning = (
            "auto-inferred linked entity IDs were ignored because they no longer exist: "
            "missing-auto-link"
        )
        create_result = TaskResult(
            task=_make_task(linked_entities=[]),
            cascade_updates=[],
            warnings=[warning],
        )

        with patch("zenos.interface.mcp.task_service") as mock_ts:
            mock_ts.create_task = AsyncMock(return_value=create_result)

            result = await task(
                action="create",
                title="整理來源追溯資料",
                created_by="amy",
                product_id="prod-1",
            )

            assert result["status"] == "ok"
            assert warning in result["warnings"]

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
                product_id="prod-1",
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
                product_id="prod-1",
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
                product_id="prod-1",
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
                product_id="prod-1",
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

    async def test_update_task_forwards_linked_entities_project_and_product_id(self):
        """task update must forward linked_entities/project/product_id into task_service updates."""
        from zenos.interface.mcp import _task_handler
        from zenos.application.action.task_service import TaskResult

        t = _make_task(id="task-1", linked_entities=["ent-old"])
        update_result = TaskResult(task=t, cascade_updates=[])

        with patch("zenos.interface.mcp.task_service") as mock_ts:
            mock_ts.update_task = AsyncMock(return_value=update_result)
            mock_ts.enrich_task = AsyncMock(return_value={"expanded_entities": []})

            result = await _task_handler(
                action="update",
                id="task-1",
                linked_entities=["ent-1", "ent-2"],
                project="ZenOS",
                product_id="prod-1",
            )

            assert result["status"] == "ok"
            _, updates = mock_ts.update_task.await_args.args
            assert updates["linked_entities"] == ["ent-1", "ent-2"]
            assert updates["project"] == "zenos"
            assert updates["product_id"] == "prod-1"


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
            data = _ok_data(result)

            assert "quality" in data
            assert data["quality"]["score"] == 85

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
            data = _ok_data(result)

            assert data["quality"]["active_l2_missing_impacts"] == 1
            assert len(data["quality"]["l2_impacts_repairs"]) == 1
            assert data["quality"]["l2_backfill_count"] == 1
            assert data["quality"]["l2_backfill_proposals"][0]["entity_id"] == "mod-1"

    async def test_analyze_impacts_includes_relationship_delete_repair_payload(self):
        from zenos.interface.mcp import analyze

        validity_report = [{
            "source_entity_id": "mod-1",
            "source_entity_name": "Governance",
            "broken_impacts": [{
                "relationship_id": "rel-123",
                "impacts_description": "治理規則改了→confirm gate 要跟著看",
                "target_entity_id": "ghost-id",
                "target_entity_name": None,
                "reason": "target_missing",
                "suggested_action": "目標 entity 已不存在，建議移除此 impacts 關聯",
            }],
            "suggested_actions": ["標記 stale", "更新 impacts", "移除無效關聯"],
        }]

        with patch("zenos.interface.mcp.governance_service") as mock_gs:
            mock_gs.check_impacts_target_validity = AsyncMock(return_value=validity_report)

            result = await analyze(check_type="impacts")
            data = _ok_data(result)

            repair_action = data["quality"]["l2_impacts_validity"][0]["broken_impacts"][0]["repair_action"]
            assert repair_action["tool"] == "write"
            assert repair_action["collection"] == "relationships"
            assert repair_action["id"] == "rel-123"
            assert repair_action["data"]["action"] == "delete"
            assert "target_missing" in repair_action["data"]["reason"]

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

            assert _ok_data(result)["staleness"]["count"] == 1

    async def test_analyze_blindspot(self):
        from zenos.interface.mcp import analyze

        blindspots = [_make_blindspot()]

        with patch("zenos.interface.mcp.governance_service") as mock_gs:
            mock_gs.run_blindspot_analysis = AsyncMock(return_value=blindspots)

            result = await analyze(check_type="blindspot")

            assert _ok_data(result)["blindspots"]["count"] == 1

    async def test_analyze_invalid_documents_caps_bundle_issues(self):
        from zenos.interface.mcp import analyze

        docs = [
            _make_entity(
                id=f"doc-{idx}",
                name=f"Doc {idx}",
                type="document",
                parent_id=f"module-{idx}",
                status="current",
                doc_role="index",
                summary="Thin.",
                bundle_highlights=[],
            )
            for idx in range(60)
        ]

        with patch("zenos.interface.mcp.ontology_service") as mock_os:
            mock_os._entities = AsyncMock()
            mock_os._entities.list_all = AsyncMock(return_value=docs)
            mock_os._relationships = AsyncMock()
            mock_os._relationships.list_by_entity = AsyncMock(return_value=[])

            result = await analyze(check_type="invalid_documents")
            data = _ok_data(result)["invalid_documents"]

            assert data["bundle_issue_count"] == 120
            assert data["bundle_issue_limit"] == 50
            assert data["bundle_issues_truncated"] is True
            assert len(data["bundle_issues"]) == 50
            assert data["bundle_issues"][0]["severity"] == "red"

    async def test_analyze_invalid_documents_filters_by_entity_scope(self):
        from zenos.interface.mcp import analyze

        product = _make_entity(id="prod-1", name="Product", type="product", parent_id=None)
        module = _make_entity(id="module-1", name="Scoped Module", type="module", parent_id="prod-1")
        outside_module = _make_entity(id="module-2", name="Outside Module", type="module", parent_id="other-prod")
        scoped_doc = _make_entity(
            id="doc-scoped",
            name="Scoped Index",
            type="document",
            parent_id="module-1",
            status="current",
            doc_role="index",
            summary=(
                "This document bundle answers scoped questions across sources, source routing, primary source, "
                "and the current reading boundary for this module."
            ),
            bundle_highlights=[],
        )
        outside_doc = _make_entity(
            id="doc-outside",
            name="Outside Index",
            type="document",
            parent_id="module-2",
            status="current",
            doc_role="index",
            summary=(
                "This document bundle answers outside questions across sources, source routing, primary source, "
                "and the current reading boundary for another module."
            ),
            bundle_highlights=[],
        )

        async def list_all(type_filter=None):
            if type_filter == "document":
                return [scoped_doc, outside_doc]
            return [product, module, outside_module, scoped_doc, outside_doc]

        with patch("zenos.interface.mcp.ontology_service") as mock_os:
            mock_os._entities = AsyncMock()
            mock_os._entities.list_all = AsyncMock(side_effect=list_all)
            mock_os._relationships = AsyncMock()
            mock_os._relationships.list_by_entity = AsyncMock(return_value=[])

            result = await analyze(check_type="invalid_documents", entity_id="prod-1")
            data = _ok_data(result)["invalid_documents"]

            assert data["scope"]["entity_id"] == "prod-1"
            assert data["scope"]["document_count"] == 1
            assert data["bundle_issue_count"] == 1
            assert data["bundle_issues"][0]["entity_id"] == "doc-scoped"

    async def test_analyze_invalid_documents_returns_suggested_write_patch(self):
        from zenos.interface.mcp import analyze

        doc = _make_entity(
            id="doc-1",
            name="Thin Index",
            type="document",
            parent_id="module-1",
            status="current",
            doc_role="index",
            summary="Thin.",
            sources=[{
                "source_id": "src-1",
                "label": "SPEC-thin.md",
                "uri": "https://github.com/acme/repo/blob/main/docs/SPEC-thin.md",
                "is_primary": True,
                "snapshot_summary": "Defines delayed binding behavior and onboarding acceptance boundaries.",
            }],
            bundle_highlights=[],
        )

        with patch("zenos.interface.mcp.ontology_service") as mock_os:
            mock_os._entities = AsyncMock()
            mock_os._entities.list_all = AsyncMock(return_value=[doc])
            mock_os._relationships = AsyncMock()
            mock_os._relationships.list_by_entity = AsyncMock(return_value=[])

            result = await analyze(check_type="invalid_documents")
            data = _ok_data(result)["invalid_documents"]

            highlight_issue = next(
                issue for issue in data["bundle_issues"]
                if issue["issue_type"] == "index_missing_bundle_highlights"
            )
            repair_patch = highlight_issue["suggested_write_patch"]
            assert repair_patch["tool"] == "write"
            assert repair_patch["collection"] == "documents"
            assert repair_patch["needs_agent_review"] is True
            assert repair_patch["data"]["id"] == "doc-1"
            assert repair_patch["data"]["bundle_highlights"][0]["source_id"] == "src-1"
            assert repair_patch["data"]["bundle_highlights"][0]["priority"] == "primary"
            assert "需求、驗收邊界或功能規格" in repair_patch["data"]["bundle_highlights"][0]["reason_to_read"]
            assert repair_patch["data"]["change_summary"]

            summary_issue = next(
                issue for issue in data["bundle_issues"]
                if issue["issue_type"] == "index_summary_not_retrieval_map"
            )
            summary_patch = summary_issue["suggested_write_patch"]["data"]["summary"]
            assert "retrieval map" in summary_patch
            assert "主要回答" in summary_patch
            assert "Primary source 類型判定為 SPEC" in summary_patch
            assert "delayed binding behavior" in summary_patch

    async def test_analyze_invalid_documents_omits_unactionable_highlight_patch(self):
        from zenos.interface.mcp import analyze

        doc = _make_entity(
            id="doc-1",
            name="Source Without ID Index",
            type="document",
            parent_id="module-1",
            status="current",
            doc_role="index",
            summary=(
                "This document bundle explains sources, source routing, primary source, "
                "and the current reading boundary for this module."
            ),
            sources=[{"uri": "https://github.com/acme/repo/blob/main/docs/spec.md"}],
            bundle_highlights=[],
            change_summary="Updated routing.",
        )

        with patch("zenos.interface.mcp.ontology_service") as mock_os:
            mock_os._entities = AsyncMock()
            mock_os._entities.list_all = AsyncMock(return_value=[doc])
            mock_os._relationships = AsyncMock()
            mock_os._relationships.list_by_entity = AsyncMock(return_value=[])

            result = await analyze(check_type="invalid_documents")
            data = _ok_data(result)["invalid_documents"]

            issue = data["bundle_issues"][0]
            assert issue["issue_type"] == "index_missing_bundle_highlights"
            assert "suggested_write_patch" not in issue

    async def test_analyze_invalid_documents_suggests_native_source_patch(self):
        from zenos.interface.mcp import analyze

        doc = _make_entity(
            id="doc-1",
            name="SPEC: Sourceless Index",
            type="document",
            parent_id="module-1",
            status="current",
            doc_role="index",
            summary=(
                "This document bundle explains sources, source routing, primary source, "
                "and the current reading boundary for this module."
            ),
            sources=[],
            bundle_highlights=[],
            change_summary="Updated routing.",
        )

        with patch("zenos.interface.mcp.ontology_service") as mock_os:
            mock_os._entities = AsyncMock()
            mock_os._entities.list_all = AsyncMock(return_value=[doc])
            mock_os._relationships = AsyncMock()
            mock_os._relationships.list_by_entity = AsyncMock(return_value=[])

            result = await analyze(check_type="invalid_documents")
            data = _ok_data(result)["invalid_documents"]

            issue = data["bundle_issues"][0]
            assert issue["issue_type"] == "index_missing_sources"
            repair_patch = issue["suggested_write_patch"]
            assert repair_patch["collection"] == "documents"
            assert repair_patch["data"]["add_source"]["type"] == "zenos_native"
            assert repair_patch["data"]["add_source"]["uri"] == "/docs/doc-1"
            assert repair_patch["data"]["add_source"]["doc_type"] == "SPEC"
            assert repair_patch["data"]["add_source"]["label"].startswith("SPEC:")
            assert repair_patch["data"]["add_source"]["is_primary"] is True
            assert repair_patch["data"]["add_source"]["retrieval_mode"] == "snapshot"
            assert repair_patch["data"]["add_source"]["content_access"] == "full"

    async def test_analyze_invalid_documents_suggests_l2_index_create_patch(self):
        from zenos.interface.mcp import analyze

        module = _make_entity(
            id="module-1",
            name="Action Layer",
            type="module",
            parent_id="prod-1",
        )
        single_doc = _make_entity(
            id="doc-single",
            name="Action Layer PRD",
            type="document",
            parent_id="module-1",
            status="current",
            doc_role="single",
            summary="Action Layer requirements.",
            sources=[{
                "source_id": "src-existing",
                "uri": "https://github.com/acme/repo/blob/main/docs/PRD.md",
                "label": "PRD.md",
                "doc_type": "SPEC",
                "snapshot_summary": "Defines action lifecycle, ownership, and acceptance criteria.",
            }],
        )

        async def list_all(type_filter=None):
            if type_filter == "document":
                return [single_doc]
            return [module, single_doc]

        with (
            patch("zenos.interface.mcp.ontology_service") as mock_os,
            patch("zenos.interface.mcp.analyze._new_id", return_value="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"),
            patch("zenos.interface.mcp.analyze.generate_source_id", return_value="src-new"),
        ):
            mock_os._entities = AsyncMock()
            mock_os._entities.list_all = AsyncMock(side_effect=list_all)
            mock_os._relationships = AsyncMock()
            mock_os._relationships.list_by_entity = AsyncMock(return_value=[])

            result = await analyze(check_type="invalid_documents")
            issues = _ok_data(result)["invalid_documents"]["bundle_issues"]

            issue = next(
                item for item in issues
                if item["issue_type"] == "l2_missing_current_index_document"
            )
            repair_patch = issue["suggested_write_patch"]
            patch_data = repair_patch["data"]
            assert repair_patch["collection"] == "documents"
            assert patch_data["id"] == "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
            assert patch_data["create_index_document"] is True
            assert patch_data["title"] == "Action Layer：文件群索引"
            assert patch_data["linked_entity_ids"] == ["module-1"]
            assert patch_data["sources"][0]["source_id"] == "src-new"
            assert patch_data["sources"][0]["uri"] == "/docs/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
            assert patch_data["bundle_highlights"][0]["source_id"] == "src-new"
            assert "Action Layer PRD" in patch_data["summary"]
            assert "action lifecycle" in patch_data["summary"]

    async def test_analyze_invalid_documents_maps_doc_type_prefixes(self):
        from zenos.interface.mcp import analyze

        docs = [
            _make_entity(
                id="doc-adr",
                name="ADR-005：Graph Library 選型",
                type="document",
                parent_id="module-1",
                status="current",
                doc_role="index",
                summary=(
                    "This document bundle explains sources, source routing, primary source, "
                    "and the current reading boundary for this module."
                ),
                sources=[],
                bundle_highlights=[],
                change_summary="Updated routing.",
            ),
            _make_entity(
                id="doc-td",
                name="TD-dashboard-v1-implementation",
                type="document",
                parent_id="module-1",
                status="current",
                doc_role="index",
                summary=(
                    "This document bundle explains sources, source routing, primary source, "
                    "and the current reading boundary for this module."
                ),
                sources=[],
                bundle_highlights=[],
                change_summary="Updated routing.",
            ),
            _make_entity(
                id="doc-prd",
                name="PRD: Action Layer",
                type="document",
                parent_id="module-1",
                status="current",
                doc_role="index",
                summary=(
                    "This document bundle explains sources, source routing, primary source, "
                    "and the current reading boundary for this module."
                ),
                sources=[],
                bundle_highlights=[],
                change_summary="Updated routing.",
            ),
            _make_entity(
                id="doc-guide",
                name="task-governance：Task 治理操作規範",
                type="document",
                parent_id="module-1",
                status="current",
                doc_role="index",
                summary=(
                    "This document bundle explains sources, source routing, primary source, "
                    "and the current reading boundary for this module."
                ),
                sources=[],
                bundle_highlights=[],
                change_summary="Updated routing.",
            ),
        ]

        with patch("zenos.interface.mcp.ontology_service") as mock_os:
            mock_os._entities = AsyncMock()
            mock_os._entities.list_all = AsyncMock(return_value=docs)
            mock_os._relationships = AsyncMock()
            mock_os._relationships.list_by_entity = AsyncMock(return_value=[])

            result = await analyze(check_type="invalid_documents")
            issues = _ok_data(result)["invalid_documents"]["bundle_issues"]

            types_by_id = {
                issue["entity_id"]: issue["suggested_write_patch"]["data"]["add_source"]["doc_type"]
                for issue in issues
                if issue["issue_type"] == "index_missing_sources"
            }
            assert types_by_id["doc-adr"] == "DECISION"
            assert types_by_id["doc-td"] == "DESIGN"
            assert types_by_id["doc-prd"] == "SPEC"
            assert types_by_id["doc-guide"] == "GUIDE"

    async def test_analyze_invalid_documents_missing_scope_returns_rejected(self):
        from zenos.interface.mcp import analyze

        with patch("zenos.interface.mcp.ontology_service") as mock_os:
            mock_os._entities = AsyncMock()
            mock_os._entities.list_all = AsyncMock(return_value=[])
            mock_os._relationships = AsyncMock()
            mock_os._relationships.list_by_entity = AsyncMock(return_value=[])

            result = await analyze(check_type="invalid_documents", entity_id="ghost")

            assert result["status"] == "rejected"
            assert result["data"]["error"] == "NOT_FOUND"

    async def test_analyze_all(self):
        from zenos.interface.mcp import analyze

        report = QualityReport(score=90, passed=[], failed=[], warnings=[])

        with patch("zenos.interface.mcp.governance_service") as mock_gs:
            mock_gs.analyze_llm_health = AsyncMock(return_value={
                "check_type": "llm_health",
                "provider_status": [],
                "dependency_points": [],
                "findings": [],
                "overall_level": "green",
            })
            mock_gs.run_quality_check = AsyncMock(return_value=report)
            mock_gs.run_staleness_check = AsyncMock(
                return_value={"warnings": [], "document_consistency_warnings": [], "document_consistency_count": 0}
            )
            mock_gs.run_blindspot_analysis = AsyncMock(return_value=[])
            mock_gs.infer_l2_backfill_proposals = AsyncMock(return_value=[])

            result = await analyze(check_type="all")
            data = _ok_data(result)

            assert "quality" in data
            assert "staleness" in data
            assert "blindspots" in data
            assert "llm_health" in data

    async def test_analyze_llm_health(self):
        from zenos.interface.mcp import analyze

        llm_health = {
            "check_type": "llm_health",
            "provider_status": [
                {
                    "name": "gemini",
                    "status": "degraded",
                    "last_success_at": None,
                    "error_rate_1h": 0.0,
                    "success_count_7d": 0,
                    "fallback_count_7d": 3,
                    "exception_count_7d": 1,
                    "fallback_rate_7d": 0.75,
                    "exception_rate_7d": 0.25,
                    "model": "gemini/gemini-2.5-flash-lite",
                    "notes": "API key missing",
                }
            ],
            "dependency_points": [
                {
                    "location": "src/zenos/application/action/task_service.py::infer_task_links",
                    "path_category": "critical",
                    "purpose": "task_auto_linking",
                    "compliant": False,
                    "notes": "task(action=create) 未帶 linked_entities 時會呼叫 infer_task_links。",
                }
            ],
            "findings": [
                {
                    "severity": "red",
                    "type": "critical_path_llm_dependency",
                    "location": "src/zenos/application/action/task_service.py::infer_task_links",
                    "description": "task(action=create) 未帶 linked_entities 時會呼叫 infer_task_links。",
                }
            ],
            "overall_level": "red",
        }

        with patch("zenos.interface.mcp.governance_service") as mock_gs:
            mock_gs.analyze_llm_health = AsyncMock(return_value=llm_health)

            result = await analyze(check_type="llm_health")
            data = _ok_data(result)

            assert data["llm_health"]["overall_level"] == "red"
            assert data["llm_health"]["provider_status"][0]["name"] == "gemini"

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
                "bundle_highlights_coverage": {"value": 0.5, "level": "yellow"},
                "llm_health": {"value": 2, "level": "red"},
            },
            "overall_level": "red",
            "recommended_action": "run_governance",
            "red_reasons": [],
            "llm_health": {
                "check_type": "llm_health",
                "provider_status": [],
                "dependency_points": [],
                "findings": [],
                "overall_level": "red",
            },
        }
        with patch("zenos.interface.mcp.governance_service") as mock_gs, \
             patch("zenos.interface.mcp.ontology_service") as mock_os, \
             patch("zenos.interface.mcp.blindspot_repo") as mock_br:
            mock_gs.analyze_llm_health = AsyncMock(return_value=health_signal["llm_health"])
            mock_gs.run_quality_check = AsyncMock(return_value=report)
            mock_gs.run_staleness_check = AsyncMock(
                return_value={"warnings": [], "document_consistency_warnings": [], "document_consistency_count": 0}
            )
            mock_gs.run_blindspot_analysis = AsyncMock(return_value=[])
            mock_gs.infer_l2_backfill_proposals = AsyncMock(return_value=[])
            mock_gs.compute_health_signal = AsyncMock(return_value=health_signal)
            mock_os._entities = AsyncMock()
            mock_os._entities.list_all = AsyncMock(return_value=entities)
            mock_os._protocols = AsyncMock()
            mock_os._protocols.get_by_entity = AsyncMock(return_value=None)
            mock_br.list_all = AsyncMock(return_value=[])

            result = await analyze(check_type="all")
            data = _ok_data(result)

            assert "kpis" in data
            assert "health_signal" in data
            assert data["health_signal"]["overall_level"] == "red"
            assert data["kpis"]["blindspot_total"] == 2
            assert data["kpis"]["duplicate_blindspot_rate"] == 0.5
            assert data["kpis"]["bundle_highlights_coverage"] == 0.5

    async def test_analyze_health_forwards_entity_scope(self):
        from zenos.interface.mcp import analyze

        health_signal = {
            "scope": {"entity_id": "prod-1", "mode": "subtree"},
            "kpis": {"quality_score": {"value": 80, "level": "green"}},
            "overall_level": "green",
            "recommended_action": "none",
            "red_reasons": [],
        }
        with patch("zenos.interface.mcp.governance_service") as mock_gs:
            mock_gs.compute_health_signal = AsyncMock(return_value=health_signal)

            result = await analyze(check_type="health", entity_id="prod-1")
            data = _ok_data(result)

            mock_gs.compute_health_signal.assert_awaited_once_with(entity_id="prod-1")
            assert data["scope"]["entity_id"] == "prod-1"

    async def test_analyze_health_missing_scope_returns_rejected(self):
        from zenos.interface.mcp import analyze

        with patch("zenos.interface.mcp.governance_service") as mock_gs:
            mock_gs.compute_health_signal = AsyncMock(side_effect=ValueError("Entity 'ghost' not found"))

            result = await analyze(check_type="health", entity_id="ghost")

            assert result["status"] == "rejected"
            assert result["data"]["error"] == "NOT_FOUND"
            assert "ghost" in result["rejection_reason"]

    async def test_analyze_governance_ssot_returns_invalid_input(self):
        from zenos.interface.mcp import analyze

        result = await analyze(check_type="governance_ssot")
        data = _non_ok_data(result, "rejected")
        assert data["error"] == "INVALID_INPUT"
        assert "Unknown check_type" in data["message"]

    async def test_analyze_invalid_type(self):
        from zenos.interface.mcp import analyze

        result = await analyze(check_type="foobar")
        data = _non_ok_data(result, "rejected")

        assert data["error"] == "INVALID_INPUT"
        assert "Unknown check_type" in data["message"]

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
            data = _ok_data(result)

            assert "quality" in data
            assert data["quality"]["entry_saturation"] == []
            assert data["quality"]["entry_saturation_count"] == 0

    async def test_analyze_quality_entry_saturation_has_proposal(self):
        """DF-20260419-L2c: analyze quality lists saturated entities (no LLM proposal);
        proposal is returned only by targeted consolidate check_type."""
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

            # quality → list-only, no LLM consolidation in the payload
            result = await analyze(check_type="quality")
            data = _ok_data(result)

            assert data["quality"]["entry_saturation_count"] == 1
            saturation_items = data["quality"]["entry_saturation"]
            assert len(saturation_items) == 1
            assert saturation_items[0]["entity_id"] == "ent-1"
            assert "consolidation_proposal" not in saturation_items[0]
            # consolidate_entries not called by quality branch anymore
            assert mock_ai.consolidate_entries.call_count == 0

            # consolidate with entity_id → targeted LLM proposal
            result2 = await analyze(check_type="consolidate", entity_id="ent-1")
            data2 = _ok_data(result2)
            assert data2["entity_id"] == "ent-1"
            assert data2["consolidation_proposal"] is not None
            assert mock_ai.consolidate_entries.call_count == 1

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

            # DF-20260419-L2c: quality lists saturated, targeted consolidate
            # handles the LLM path including failure.
            result = await analyze(check_type="quality")
            data = _ok_data(result)
            assert "quality" in data
            assert data["quality"]["entry_saturation_count"] == 1

            # When LLM fails for the targeted consolidate, proposal is None but
            # response is still ok (payload carries consolidation_proposal=None).
            result2 = await analyze(check_type="consolidate", entity_id="ent-1")
            data2 = _ok_data(result2)
            assert data2["consolidation_proposal"] is None


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

    async def test_write_entry_rejects_completion_report_content(self):
        from zenos.interface.mcp import write

        result = await write(
            collection="entries",
            data={
                "entity_id": "ent-1",
                "type": "change",
                "content": "Implementation complete；pytest 337 passed；QA PASS",
            },
        )

        assert result["status"] == "rejected"
        assert result["data"]["error"] == "LOW_VALUE_ENTRY"
        assert result["data"]["reason"] == "entry_is_completion_report"

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
        data = _ok_data(result)

        assert "active_entries" in data
        assert len(data["active_entries"]) == 1
        assert data["active_entries"][0]["type"] == "decision"
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
        data = _ok_data(result)

        assert "active_entries" in data
        assert data["active_entries"] == []


# ---------------------------------------------------------------------------
# Tool 8: governance_guide
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestGovernanceGuideTool:
    """Tests for the governance_guide MCP tool (DC-1, DC-2, DC-3, DC-4, DC-5, DC-6)."""

    # ── DC-1: Returns correct structure ─────────────────────────────────────

    async def test_returns_correct_structure_for_valid_input(self):
        """governance_guide returns content metadata for valid input."""
        from zenos.interface.mcp import governance_guide

        result = await governance_guide(topic="entity", level=1)
        data = _ok_data(result)

        assert data["topic"] == "entity"
        assert data["level"] == 1
        assert data["version"] == "1.1"
        assert isinstance(data["content"], str)
        assert len(data["content"]) > 0
        assert data["content_hash"].startswith("sha256:")
        assert isinstance(data["content_version"], str)

    async def test_default_level_is_2(self):
        """governance_guide defaults to level=2 when level not provided."""
        from zenos.interface.mcp import governance_guide

        result = await governance_guide(topic="capture")
        data = _ok_data(result)

        assert data["level"] == 2
        assert data["topic"] == "capture"

    async def test_since_hash_returns_unchanged_payload(self):
        """Matching since_hash returns unchanged=true and omits content."""
        from zenos.interface.mcp import governance_guide

        first = _ok_data(await governance_guide(topic="entity", level=2))
        second = _ok_data(await governance_guide(
            topic="entity",
            level=2,
            since_hash=first["content_hash"],
        ))

        assert second["unchanged"] is True
        assert "content" not in second
        assert second["content_hash"] == first["content_hash"]

    # ── DC-2: All topics × three levels ─────────────────────────────────────

    @pytest.mark.parametrize(
        "topic",
        ["entity", "document", "bundle", "task", "capture", "sync", "remediation"],
    )
    @pytest.mark.parametrize("level", [1, 2, 3])
    async def test_all_topics_and_levels_return_content(self, topic, level):
        """Each topic/level combination returns non-empty content."""
        from zenos.interface.mcp import governance_guide

        result = await governance_guide(topic=topic, level=level)
        data = _ok_data(result)

        assert "error" not in data
        assert data["topic"] == topic
        assert data["level"] == level
        assert isinstance(data["version"], str)
        assert len(data["version"]) > 0
        assert isinstance(data["content"], str)
        assert len(data["content"]) >= 100, (
            f"Content for {topic} level={level} is too short: {len(data['content'])} chars"
        )

    async def test_level1_content_is_shorter_than_level3(self):
        """Level 1 content is shorter than Level 3 for the same topic."""
        from zenos.interface.mcp import governance_guide

        result_l1 = await governance_guide(topic="entity", level=1)
        result_l3 = await governance_guide(topic="entity", level=3)

        assert len(_ok_data(result_l1)["content"]) < len(_ok_data(result_l3)["content"])

    # ── DC-3: Invalid input returns INVALID_INPUT error ─────────────────────

    async def test_invalid_topic_returns_error(self):
        """Invalid topic returns INVALID_INPUT error with valid topics listed."""
        from zenos.interface.mcp import governance_guide

        result = await governance_guide(topic="unknown_topic", level=1)
        data = _non_ok_data(result, "rejected")

        assert data["error"] == "UNKNOWN_TOPIC"
        assert "unknown_topic" in data["message"]
        assert "available_topics" in data
        # Must list valid topics in the message
        for valid in ["entity", "document", "bundle", "task", "capture", "sync", "remediation"]:
            assert valid in data["message"]

    async def test_invalid_level_returns_error(self):
        """Invalid level returns INVALID_INPUT error with valid levels listed."""
        from zenos.interface.mcp import governance_guide

        result = await governance_guide(topic="entity", level=99)
        data = _non_ok_data(result, "rejected")

        assert data["error"] == "INVALID_LEVEL"
        assert "99" in data["message"]
        assert "1/2/3" in data["message"]

    async def test_level_zero_returns_error(self):
        """Level 0 (boundary) returns INVALID_INPUT error."""
        from zenos.interface.mcp import governance_guide

        result = await governance_guide(topic="task", level=0)

        assert _non_ok_data(result, "rejected")["error"] == "INVALID_LEVEL"

    async def test_empty_topic_returns_error(self):
        """Empty string topic returns INVALID_INPUT error."""
        from zenos.interface.mcp import governance_guide

        result = await governance_guide(topic="", level=1)

        assert _non_ok_data(result, "rejected")["error"] == "UNKNOWN_TOPIC"

    # ── DC-4: Content is server-side (smoke test via import) ────────────────

    async def test_rules_come_from_server_module_not_external_files(self):
        """Rules are served from GOVERNANCE_RULES dict, not read from filesystem."""
        from zenos.interface.governance_rules import GOVERNANCE_RULES

        # Verify the dict has all required keys
        assert set(GOVERNANCE_RULES.keys()) == {
            "entity",
            "document",
            "bundle",
            "task",
            "capture",
            "sync",
            "remediation",
        }
        for topic, levels in GOVERNANCE_RULES.items():
            assert set(levels.keys()) == {1, 2, 3}, (
                f"Topic '{topic}' missing levels: {set(levels.keys())}"
            )

    # ── DC-5: No internal algorithm details exposed ──────────────────────────

    async def test_entity_rules_do_not_expose_llm_prompts(self):
        """Entity rules mention three-question requirement but not LLM prompt internals."""
        from zenos.interface.mcp import governance_guide

        result = await governance_guide(topic="entity", level=3)
        content = _ok_data(result)["content"]

        # Must mention the three-question gate (external rule)
        assert "三問" in content
        # Must NOT expose internal LLM prompt details
        assert "system prompt" not in content.lower()
        assert "temperature" not in content.lower()

    async def test_capture_rules_describe_routing_not_llm_internals(self):
        """Capture rules describe routing logic but not LLM model selection internals."""
        from zenos.interface.mcp import governance_guide

        result = await governance_guide(topic="capture", level=2)
        content = _ok_data(result)["content"]

        # External rule: routing is mentioned
        assert "LAYER_DOWNGRADE_REQUIRED" in content
        assert "Work Journal gate" in content
        assert "純掃描無變更不要寫 journal" in content
        assert "task.result" in content
        # No internal model details
        assert "gemini" not in content.lower()
        assert "flash" not in content.lower()

    async def test_document_rules_synced_to_delivery_snapshot_v22(self):
        """Document guide reflects current delivery-snapshot and dispatch-gate rules."""
        from zenos.interface.mcp import governance_guide

        result = await governance_guide(topic="document", level=2)
        data = _ok_data(result)
        content = data["content"]

        assert data["version"] == "2.2"
        assert "ZenOS Delivery Snapshot" in content
        assert "git + gcs" in content
        assert "linked_entity_ids" in content
        assert "Spec Compliance Matrix" in content
        assert "L3 index summary" in content
        assert "文件群 retrieval map" in content
        assert 'search(collection="documents", entity_name="<L2 name>")' in content
        assert "bundle_highlights" in content

    async def test_bundle_rules_require_index_summary_retrieval_map(self):
        """Bundle guide makes index summaries an agent-readable routing map."""
        from zenos.interface.mcp import governance_guide

        result = await governance_guide(topic="bundle", level=2)
        content = _ok_data(result)["content"]

        assert "index summary" in content
        assert "文件群 retrieval map" in content
        assert 'search(collection="documents", entity_name="<L2 name>")' in content
        assert "change_summary" in content


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
