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

from zenos.application.ontology_service import (
    DocumentSyncResult,
    EntityWithRelationships,
    UpsertEntityResult,
)
from zenos.domain.governance import TagConfidence
from zenos.domain.models import (
    Blindspot,
    Document,
    DocumentTags,
    Entity,
    EntityEntry,
    Gap,
    Protocol,
    QualityCheckItem,
    QualityReport,
    Relationship,
    Source,
    StalenessWarning,
    Tags,
    Task,
)
from zenos.infrastructure.context import current_partner_department, current_partner_roles


# ---------------------------------------------------------------------------
# Fixtures: reusable domain objects
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _mock_tool_bootstrap():
    """Avoid bootstrapping real SQL repos in interface unit tests."""
    with patch("zenos.interface.tools._ensure_services", new=AsyncMock(return_value=None)), \
         patch("zenos.interface.tools.ontology_service", new=AsyncMock()), \
         patch("zenos.interface.tools.task_service", new=AsyncMock()), \
         patch("zenos.interface.tools.entity_repo", new=AsyncMock()), \
         patch("zenos.interface.tools.entry_repo", new=AsyncMock()):
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
        from zenos.interface.tools import search

        entity = _make_entity()
        with patch("zenos.interface.tools.ontology_service") as mock_os, \
             patch("zenos.interface.tools.task_service") as mock_ts:
            mock_os.search = AsyncMock(return_value=[entity])
            mock_ts.list_tasks = AsyncMock(return_value=[])

            result = await search(query="Paceriz", collection="all")

            assert "results" in result
            assert result["count"] == 1
            mock_os.search.assert_called_once_with("Paceriz")

    async def test_list_entities_collection(self):
        from zenos.interface.tools import search

        entities = [_make_entity(), _make_entity(id="ent-2", name="ZenOS")]
        with patch("zenos.interface.tools.ontology_service") as mock_os:
            mock_os.list_entities = AsyncMock(return_value=entities)

            result = await search(collection="entities")

            assert "entities" in result
            assert len(result["entities"]) == 2

    async def test_list_entities_with_confirmed_filter(self):
        from zenos.interface.tools import search

        entities = [
            _make_entity(confirmed_by_user=True),
            _make_entity(id="ent-2", confirmed_by_user=False),
        ]
        with patch("zenos.interface.tools.ontology_service") as mock_os:
            mock_os.list_entities = AsyncMock(return_value=entities)

            result = await search(collection="entities", confirmed_only=True)

            assert len(result["entities"]) == 1

    async def test_list_tasks_with_assignee(self):
        from zenos.interface.tools import search

        tasks = [_make_task()]
        with patch("zenos.interface.tools.task_service") as mock_ts:
            mock_ts.list_tasks = AsyncMock(return_value=tasks)

            result = await search(collection="tasks", assignee="developer")

            mock_ts.list_tasks.assert_called_once_with(
                assignee="developer",
                created_by=None,
                status=None,
                limit=50,
                project=None,
            )
            assert "tasks" in result

    async def test_list_tasks_with_status_filter(self):
        from zenos.interface.tools import search

        with patch("zenos.interface.tools.task_service") as mock_ts:
            mock_ts.list_tasks = AsyncMock(return_value=[])

            await search(collection="tasks", status="todo,in_progress")

            mock_ts.list_tasks.assert_called_once_with(
                assignee=None,
                created_by=None,
                status=["todo", "in_progress"],
                limit=50,
                project=None,
            )

    async def test_empty_keyword_search(self):
        """Empty query with collection=all should list all collections."""
        from zenos.interface.tools import search

        with patch("zenos.interface.tools.ontology_service") as mock_os, \
             patch("zenos.interface.tools.task_service") as mock_ts:
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
        from zenos.interface.tools import search

        entities = [_make_entity(id=f"ent-{i}") for i in range(10)]
        with patch("zenos.interface.tools.ontology_service") as mock_os:
            mock_os.list_entities = AsyncMock(return_value=entities)

            result = await search(collection="entities", limit=3)

            assert len(result["entities"]) == 3

    async def test_entities_role_restricted_hidden_without_role_match(self):
        from zenos.interface.tools import search, _current_partner

        restricted = _make_entity(
            id="ent-r",
            visibility="role-restricted",
            visible_to_roles=["engineering"],
        )
        token_partner = _current_partner.set({"id": "p-marketing", "isAdmin": False})
        token_roles = current_partner_roles.set(["marketing"])
        token_dept = current_partner_department.set("marketing")
        try:
            with patch("zenos.interface.tools.ontology_service") as mock_os:
                mock_os.list_entities = AsyncMock(return_value=[restricted])
                result = await search(collection="entities")
            assert result["entities"] == []
        finally:
            current_partner_department.reset(token_dept)
            current_partner_roles.reset(token_roles)
            _current_partner.reset(token_partner)

    async def test_entities_department_filter_blocks_other_department(self):
        from zenos.interface.tools import search, _current_partner

        restricted = _make_entity(
            id="ent-d",
            visibility="public",
            visible_to_departments=["finance"],
        )
        token_partner = _current_partner.set({"id": "p-eng", "isAdmin": False})
        token_roles = current_partner_roles.set(["engineering"])
        token_dept = current_partner_department.set("engineering")
        try:
            with patch("zenos.interface.tools.ontology_service") as mock_os:
                mock_os.list_entities = AsyncMock(return_value=[restricted])
                result = await search(collection="entities")
            assert result["entities"] == []
        finally:
            current_partner_department.reset(token_dept)
            current_partner_roles.reset(token_roles)
            _current_partner.reset(token_partner)

    async def test_entities_admin_can_see_confidential(self):
        from zenos.interface.tools import search, _current_partner

        confidential = _make_entity(
            id="ent-c",
            visibility="confidential",
            visible_to_members=["p-admin"],
        )
        token_partner = _current_partner.set({"id": "p-admin", "isAdmin": True})
        token_roles = current_partner_roles.set([])
        token_dept = current_partner_department.set("all")
        try:
            with patch("zenos.interface.tools.ontology_service") as mock_os:
                mock_os.list_entities = AsyncMock(return_value=[confidential])
                result = await search(collection="entities")
            assert len(result["entities"]) == 1
            assert result["entities"][0]["id"] == "ent-c"
        finally:
            current_partner_department.reset(token_dept)
            current_partner_roles.reset(token_roles)
            _current_partner.reset(token_partner)

    async def test_documents_collection_query_filters_by_source_uri(self):
        from zenos.interface.tools import search

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
        with patch("zenos.interface.tools.ontology_service") as mock_os:
            mock_os._entities = AsyncMock()
            mock_os._entities.list_all = AsyncMock(return_value=[doc_hit, doc_miss])
            mock_os._entities.get_by_name = AsyncMock(return_value=None)

            result = await search(
                collection="documents",
                query="spec-a.md",
            )

            assert "documents" in result
            assert [d["id"] for d in result["documents"]] == ["doc-1"]


# ---------------------------------------------------------------------------
# Tool 2: get
# ---------------------------------------------------------------------------

class TestGetTool:
    """Tests for the get MCP tool."""

    async def test_get_entity_by_name(self):
        from zenos.interface.tools import get

        entity = _make_entity()
        rels = [Relationship(source_entity_id="ent-1", target_id="ent-2",
                             type="depends_on", description="test")]
        ewr = EntityWithRelationships(entity=entity, relationships=rels)

        with patch("zenos.interface.tools.ontology_service") as mock_os:
            mock_os.get_entity = AsyncMock(return_value=ewr)

            result = await get(collection="entities", name="Paceriz")

            assert result["entity"]["name"] == "Paceriz"
            assert len(result["relationships"]) == 1

    async def test_get_entity_by_id(self):
        from zenos.interface.tools import get

        entity = _make_entity()
        with patch("zenos.interface.tools.entity_repo") as mock_er, \
             patch("zenos.interface.tools.relationship_repo") as mock_rr:
            mock_er.get_by_id = AsyncMock(return_value=entity)
            mock_rr.list_by_entity = AsyncMock(return_value=[])

            result = await get(collection="entities", id="ent-1")

            assert result["entity"]["id"] == "ent-1"

    async def test_get_entity_not_found(self):
        from zenos.interface.tools import get

        with patch("zenos.interface.tools.ontology_service") as mock_os:
            mock_os.get_entity = AsyncMock(return_value=None)

            result = await get(collection="entities", name="NonExistent")

            assert result["error"] == "NOT_FOUND"

    async def test_get_no_name_no_id(self):
        from zenos.interface.tools import get

        result = await get(collection="entities")

        assert result["error"] == "INVALID_INPUT"
        assert "Must provide" in result["message"]

    async def test_get_unknown_collection(self):
        from zenos.interface.tools import get

        result = await get(collection="foobar", name="test")

        assert result["error"] == "INVALID_INPUT"
        assert "Unknown collection" in result["message"]

    async def test_get_task_by_id(self):
        from zenos.interface.tools import get

        task = _make_task()
        enrichments = {"expanded_entities": []}
        with patch("zenos.interface.tools.task_service") as mock_ts:
            mock_ts.get_task_enriched = AsyncMock(return_value=(task, enrichments))

            result = await get(collection="tasks", id="task-1")

            assert result["title"] == "Fix login"

    async def test_get_task_not_found(self):
        from zenos.interface.tools import get

        with patch("zenos.interface.tools.task_service") as mock_ts:
            mock_ts.get_task_enriched = AsyncMock(return_value=None)

            result = await get(collection="tasks", id="nonexistent")

            assert result["error"] == "NOT_FOUND"

    async def test_get_task_requires_id(self):
        from zenos.interface.tools import get

        result = await get(collection="tasks", name="some-name")

        assert result["error"] == "INVALID_INPUT"
        assert "id" in result["message"].lower()

    async def test_get_blindspot_by_id(self):
        from zenos.interface.tools import get

        bs = _make_blindspot()
        with patch("zenos.interface.tools.blindspot_repo") as mock_br:
            mock_br.get_by_id = AsyncMock(return_value=bs)

            result = await get(collection="blindspots", id="bs-1")

            assert result["description"] == "No monitoring"

    async def test_get_document_by_id(self):
        from zenos.interface.tools import get

        doc = _make_document()
        with patch("zenos.interface.tools.ontology_service") as mock_os:
            mock_os.get_document = AsyncMock(return_value=doc)

            result = await get(collection="documents", id="doc-1")

            assert result["title"] == "API Spec"

    async def test_get_protocol_by_id_prefers_protocol_doc_id(self):
        from zenos.interface.tools import get

        proto = _make_protocol(id="proto-1", entity_id="ent-1")
        with patch("zenos.interface.tools.protocol_repo") as mock_pr:
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
        from zenos.interface.tools import read_source

        with patch("zenos.interface.tools.source_service") as mock_ss:
            mock_ss.read_source = AsyncMock(return_value="# Hello World")

            result = await read_source(doc_id="doc-1")

            assert result["doc_id"] == "doc-1"
            assert result["content"] == "# Hello World"

    async def test_read_source_not_found(self):
        from zenos.interface.tools import read_source

        with patch("zenos.interface.tools.source_service") as mock_ss:
            mock_ss.read_source = AsyncMock(side_effect=ValueError("Doc not found"))

            result = await read_source(doc_id="nonexistent")

            assert result["error"] == "NOT_FOUND"

    async def test_read_source_file_not_found(self):
        from zenos.interface.tools import read_source

        with patch("zenos.interface.tools.source_service") as mock_ss:
            mock_ss.read_source = AsyncMock(
                side_effect=FileNotFoundError("File missing"))

            result = await read_source(doc_id="doc-1")

            assert result["error"] == "NOT_FOUND"

    async def test_read_source_permission_error(self):
        from zenos.interface.tools import read_source

        with patch("zenos.interface.tools.source_service") as mock_ss:
            mock_ss.read_source = AsyncMock(
                side_effect=PermissionError("No access"))

            result = await read_source(doc_id="doc-1")

            assert result["error"] == "ADAPTER_ERROR"
            assert "Permission denied" in result["message"]

    async def test_read_source_runtime_error(self):
        from zenos.interface.tools import read_source

        with patch("zenos.interface.tools.source_service") as mock_ss:
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
        from zenos.interface.tools import write

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

        with patch("zenos.interface.tools.ontology_service") as mock_os:
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

            assert result["entity"]["name"] == "Paceriz"
            assert result.get("warnings") is None

    async def test_write_module_without_parent_id_returns_warning(self):
        from zenos.interface.tools import write

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

        with patch("zenos.interface.tools.ontology_service") as mock_os:
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

            assert "warnings" in result
            assert "parent_id" in result["warnings"][0]

    async def test_write_entity_with_id_updates(self):
        from zenos.interface.tools import write

        entity = _make_entity()
        upsert_result = UpsertEntityResult(
            entity=entity,
            tag_confidence=TagConfidence(confirmed_fields=[], draft_fields=[]),
            split_recommendation=None,
        )

        with patch("zenos.interface.tools.ontology_service") as mock_os:
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
        from zenos.interface.tools import write

        result = await write(collection="foobar", data={})

        assert result["error"] == "INVALID_INPUT"
        assert "Unknown collection" in result["message"]

    async def test_write_entity_missing_required_field(self):
        from zenos.interface.tools import write

        with patch("zenos.interface.tools.ontology_service") as mock_os:
            mock_os.upsert_entity = AsyncMock(side_effect=KeyError("name"))

            result = await write(collection="entities", data={})

            assert result["error"] == "INVALID_INPUT"

    async def test_write_documents_sync_mode_routes_to_sync_api(self):
        from zenos.interface.tools import write

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
        with patch("zenos.interface.tools.ontology_service") as mock_os:
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

            assert result["operation"] == "rename"
            assert result["dry_run"] is True
            assert result["document_id"] == "doc-1"

    async def test_write_relationship_success(self):
        from zenos.interface.tools import write

        rel = Relationship(
            id="rel-1",
            source_entity_id="ent-1",
            target_id="ent-2",
            type="depends_on",
            description="Training depends on data",
        )

        with patch("zenos.interface.tools.ontology_service") as mock_os:
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

            assert result["type"] == "depends_on"

    async def test_write_relationship_missing_field(self):
        from zenos.interface.tools import write

        result = await write(
            collection="relationships",
            data={"source_entity_id": "ent-1"},  # missing target, type, description
        )

        assert result["error"] == "INVALID_INPUT"

    async def test_write_red_blindspot_skips_duplicate_open_task(self):
        from zenos.interface.tools import write

        blindspot = _make_blindspot(id="bs-1", severity="red")
        existing_task = _make_task(
            id="task-dup",
            status="backlog",
            linked_blindspot="bs-1",
            source_type="blindspot",
        )
        with patch("zenos.interface.tools.ontology_service") as mock_os, \
             patch("zenos.interface.tools.task_service") as mock_ts:
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

            assert result["auto_task_skipped"] == "EXISTING_OPEN_TASK"
            assert result["auto_created_task"]["id"] == "task-dup"
            mock_ts.create_task.assert_not_called()


# ---------------------------------------------------------------------------
# Tool 5: confirm
# ---------------------------------------------------------------------------

class TestConfirmTool:
    """Tests for the confirm MCP tool."""

    async def test_confirm_entity(self):
        from zenos.interface.tools import confirm

        with patch("zenos.interface.tools.ontology_service") as mock_os:
            mock_os.confirm = AsyncMock(return_value={"status": "confirmed"})

            result = await confirm(collection="entities", id="ent-1")

            mock_os.confirm.assert_called_once_with("entities", "ent-1")
            assert result["status"] == "confirmed"

    async def test_confirm_not_found(self):
        from zenos.interface.tools import confirm

        with patch("zenos.interface.tools.ontology_service") as mock_os:
            mock_os.confirm = AsyncMock(
                side_effect=ValueError("Entity 'x' not found"))

            result = await confirm(collection="entities", id="x")

            assert result["error"] == "NOT_FOUND"

    async def test_confirm_invalid_input(self):
        from zenos.interface.tools import confirm

        with patch("zenos.interface.tools.ontology_service") as mock_os:
            mock_os.confirm = AsyncMock(
                side_effect=ValueError("Invalid status"))

            result = await confirm(collection="entities", id="x")

            assert result["error"] == "INVALID_INPUT"


# ---------------------------------------------------------------------------
# Tool 6: task
# ---------------------------------------------------------------------------

class TestTaskTool:
    """Tests for the task MCP tool."""

    async def test_create_task_success(self):
        from zenos.interface.tools import task
        from zenos.application.task_service import TaskResult

        t = _make_task()
        create_result = TaskResult(task=t, cascade_updates=[])

        with patch("zenos.interface.tools.task_service") as mock_ts:
            mock_ts.create_task = AsyncMock(return_value=create_result)

            result = await task(
                action="create",
                title="Fix login",
                created_by="architect",
                assignee="developer",
                priority="high",
            )

            assert result["title"] == "Fix login"

    async def test_create_task_missing_title(self):
        from zenos.interface.tools import task

        result = await task(action="create", created_by="architect")

        assert result["error"] == "INVALID_INPUT"
        assert "title" in result["message"]

    async def test_create_task_missing_created_by(self):
        from zenos.interface.tools import task

        result = await task(action="create", title="Fix login")

        assert result["error"] == "INVALID_INPUT"
        assert "created_by" in result["message"]

    async def test_create_task_invalid_due_date(self):
        from zenos.interface.tools import task

        result = await task(
            action="create",
            title="Fix login",
            created_by="architect",
            due_date="not-a-date",
        )

        assert result["error"] == "INVALID_INPUT"
        assert "due_date" in result["message"]

    async def test_create_task_plain_description_auto_formats_to_markdown(self):
        from zenos.interface.tools import task
        from zenos.application.task_service import TaskResult

        t = _make_task()
        create_result = TaskResult(task=t, cascade_updates=[])
        raw = "業務要做母親節檔期素材，需符合品牌語氣\n主視覺要有 CTA\n本週五前交付"

        with patch("zenos.interface.tools.task_service") as mock_ts:
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
        from zenos.interface.tools import task
        from zenos.application.task_service import TaskResult

        t = _make_task()
        create_result = TaskResult(task=t, cascade_updates=[])
        markdown = "**需求摘要**：整理母親節素材\n\n- 完成主視覺\n- 完成投放尺寸"

        with patch("zenos.interface.tools.task_service") as mock_ts:
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
        from zenos.interface.tools import task
        from zenos.application.task_service import TaskResult

        t = _make_task()
        create_result = TaskResult(task=t, cascade_updates=[])
        metadata = {
            "sync_sources": ["Google Sheets - Banila Co #L15"],
            "provenance": [{"type": "sheet", "sheet_ref": "BanilaCo!L15"}],
        }

        with patch("zenos.interface.tools.task_service") as mock_ts:
            mock_ts.create_task = AsyncMock(return_value=create_result)

            await task(
                action="create",
                title="整理來源追溯資料",
                created_by="amy",
                source_metadata=metadata,
            )

            payload = mock_ts.create_task.call_args.args[0]
            assert payload["source_metadata"] == metadata

    async def test_update_task_success(self):
        from zenos.interface.tools import task
        from zenos.application.task_service import TaskResult

        t = _make_task(status="in_progress")
        update_result = TaskResult(task=t, cascade_updates=[])

        with patch("zenos.interface.tools.task_service") as mock_ts:
            mock_ts.update_task = AsyncMock(return_value=update_result)

            result = await task(
                action="update",
                id="task-1",
                status="in_progress",
            )

            assert result["status"] == "in_progress"

    async def test_update_task_missing_id(self):
        from zenos.interface.tools import task

        result = await task(action="update", status="in_progress")

        assert result["error"] == "INVALID_INPUT"
        assert "id" in result["message"]

    async def test_unknown_action(self):
        from zenos.interface.tools import task

        result = await task(action="delete", title="X", created_by="Y")

        assert result["error"] == "INVALID_INPUT"
        assert "Unknown action" in result["message"]

    async def test_update_task_invalid_status(self):
        from zenos.interface.tools import task

        with patch("zenos.interface.tools.task_service") as mock_ts:
            mock_ts.update_task = AsyncMock(
                side_effect=ValueError("Cannot transition to done"))

            result = await task(action="update", id="task-1", status="done")

            assert result["error"] == "INVALID_INPUT"


# ---------------------------------------------------------------------------
# Tool 7: analyze
# ---------------------------------------------------------------------------

class TestAnalyzeTool:
    """Tests for the analyze MCP tool."""

    async def test_analyze_quality(self):
        from zenos.interface.tools import analyze

        report = QualityReport(
            score=85,
            passed=[QualityCheckItem(name="check1", passed=True, detail="ok")],
            failed=[],
            warnings=[],
        )

        with patch("zenos.interface.tools.governance_service") as mock_gs:
            mock_gs.run_quality_check = AsyncMock(return_value=report)
            mock_gs.infer_l2_backfill_proposals = AsyncMock(return_value=[])

            result = await analyze(check_type="quality")

            assert "quality" in result
            assert result["quality"]["score"] == 85

    async def test_analyze_quality_includes_l2_repair_suggestions(self):
        from zenos.interface.tools import analyze

        report = QualityReport(
            score=80,
            passed=[],
            failed=[QualityCheckItem(name="l2_impacts_coverage", passed=False, detail="missing impacts")],
            warnings=[],
        )
        module = _make_entity(id="mod-1", type="module", name="Governance", status="active")

        with patch("zenos.interface.tools.governance_service") as mock_gs, \
             patch("zenos.interface.tools.ontology_service") as mock_os:
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
        from zenos.interface.tools import analyze

        warnings = [
            StalenessWarning(
                pattern="feature_doc_lag",
                description="Docs are stale",
                affected_entity_ids=["ent-1"],
                affected_document_ids=["doc-1"],
                suggested_action="Review docs",
            )
        ]

        with patch("zenos.interface.tools.governance_service") as mock_gs:
            mock_gs.run_staleness_check = AsyncMock(
                return_value={"warnings": warnings, "document_consistency_warnings": [], "document_consistency_count": 0}
            )

            result = await analyze(check_type="staleness")

            assert result["staleness"]["count"] == 1

    async def test_analyze_blindspot(self):
        from zenos.interface.tools import analyze

        blindspots = [_make_blindspot()]

        with patch("zenos.interface.tools.governance_service") as mock_gs:
            mock_gs.run_blindspot_analysis = AsyncMock(return_value=blindspots)

            result = await analyze(check_type="blindspot")

            assert result["blindspots"]["count"] == 1

    async def test_analyze_all(self):
        from zenos.interface.tools import analyze

        report = QualityReport(score=90, passed=[], failed=[], warnings=[])

        with patch("zenos.interface.tools.governance_service") as mock_gs:
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
        from zenos.interface.tools import analyze

        report = QualityReport(score=90, passed=[], failed=[], warnings=[])
        entities = [
            _make_entity(id="ent-1", type="product", confirmed_by_user=False),
            _make_entity(id="doc-1", type="document", confirmed_by_user=True),
        ]
        blindspots = [
            _make_blindspot(id="bs-1", description="dup", suggested_action="fix"),
            _make_blindspot(id="bs-2", description="dup", suggested_action="fix"),
        ]
        with patch("zenos.interface.tools.governance_service") as mock_gs, \
             patch("zenos.interface.tools.ontology_service") as mock_os, \
             patch("zenos.interface.tools.blindspot_repo") as mock_br:
            mock_gs.run_quality_check = AsyncMock(return_value=report)
            mock_gs.run_staleness_check = AsyncMock(
                return_value={"warnings": [], "document_consistency_warnings": [], "document_consistency_count": 0}
            )
            mock_gs.run_blindspot_analysis = AsyncMock(return_value=[])
            mock_gs.infer_l2_backfill_proposals = AsyncMock(return_value=[])
            mock_os._entities = AsyncMock()
            mock_os._entities.list_all = AsyncMock(return_value=entities)
            mock_os._documents = AsyncMock()
            mock_os._documents.list_all = AsyncMock(return_value=[])
            mock_os._protocols = AsyncMock()
            mock_os._protocols.get_by_entity = AsyncMock(return_value=None)
            mock_br.list_all = AsyncMock(return_value=blindspots)

            result = await analyze(check_type="all")

            assert "kpis" in result
            assert result["kpis"]["total_items"] >= 2
            assert result["kpis"]["duplicate_blindspots"] == 1

    async def test_analyze_invalid_type(self):
        from zenos.interface.tools import analyze

        result = await analyze(check_type="foobar")

        assert result["error"] == "INVALID_INPUT"
        assert "Unknown check_type" in result["message"]

    async def test_analyze_quality_entry_saturation_empty(self):
        """analyze quality: entry_saturation=[] and count=0 when no saturated entities."""
        from zenos.interface.tools import analyze
        from zenos.application.governance_ai import GovernanceAI
        import zenos.interface.tools as tools_mod

        report = QualityReport(score=90, passed=[], failed=[], warnings=[])

        with patch("zenos.interface.tools.governance_service") as mock_gs, \
             patch("zenos.interface.tools.ontology_service") as mock_os, \
             patch("zenos.interface.tools._governance_ai") as mock_ai:
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
        from zenos.interface.tools import analyze
        from zenos.application.governance_ai import ConsolidationProposal, ConsolidationMergeGroup
        import zenos.interface.tools as tools_mod

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

        with patch("zenos.interface.tools.governance_service") as mock_gs, \
             patch("zenos.interface.tools.ontology_service") as mock_os, \
             patch("zenos.interface.tools._governance_ai", mock_ai):
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
        from zenos.interface.tools import analyze
        import zenos.interface.tools as tools_mod

        report = QualityReport(score=70, passed=[], failed=[], warnings=[])

        entries = [_make_entry(id=f"entry-{i}") for i in range(20)]

        mock_ai = MagicMock()
        mock_ai.consolidate_entries = MagicMock(return_value=None)  # LLM failure

        with patch("zenos.interface.tools.governance_service") as mock_gs, \
             patch("zenos.interface.tools.ontology_service") as mock_os, \
             patch("zenos.interface.tools._governance_ai", mock_ai):
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
        from zenos.interface.tools import write
        import zenos.interface.tools as tools_mod

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

        assert "error" not in result
        assert result["id"] == "entry-1"
        assert result["type"] == "decision"
        assert result["content"] == "We chose PostgreSQL for reliability"
        assert "warning" not in result
        tools_mod.entry_repo.create.assert_called_once()

    async def test_write_entry_missing_entity_id(self):
        """write entries returns INVALID_INPUT when entity_id is missing."""
        from zenos.interface.tools import write

        result = await write(
            collection="entries",
            data={"type": "decision", "content": "Some content"},
        )

        assert result["error"] == "INVALID_INPUT"
        assert "entity_id" in result["message"]

    async def test_write_entry_missing_content(self):
        """write entries returns INVALID_INPUT when content is missing."""
        from zenos.interface.tools import write

        result = await write(
            collection="entries",
            data={"entity_id": "ent-1", "type": "decision"},
        )

        assert result["error"] == "INVALID_INPUT"

    async def test_write_entry_content_too_long(self):
        """write entries rejects content exceeding 200 chars."""
        from zenos.interface.tools import write

        result = await write(
            collection="entries",
            data={
                "entity_id": "ent-1",
                "type": "decision",
                "content": "x" * 201,
            },
        )

        assert result["error"] == "INVALID_INPUT"
        assert "200" in result["message"]

    async def test_write_entry_empty_content(self):
        """write entries rejects empty content."""
        from zenos.interface.tools import write

        result = await write(
            collection="entries",
            data={"entity_id": "ent-1", "type": "decision", "content": ""},
        )

        assert result["error"] == "INVALID_INPUT"

    async def test_write_entry_invalid_type(self):
        """write entries rejects unknown type value."""
        from zenos.interface.tools import write

        result = await write(
            collection="entries",
            data={"entity_id": "ent-1", "type": "unknown_type", "content": "some content"},
        )

        assert result["error"] == "INVALID_INPUT"
        assert "type" in result["message"]

    async def test_write_entry_context_too_long(self):
        """write entries rejects context exceeding 200 chars."""
        from zenos.interface.tools import write

        result = await write(
            collection="entries",
            data={
                "entity_id": "ent-1",
                "type": "insight",
                "content": "Valid content",
                "context": "c" * 201,
            },
        )

        assert result["error"] == "INVALID_INPUT"
        assert "context" in result["message"]

    async def test_write_entry_update_status_supersede(self):
        """write entries with id updates status for supersede flow."""
        from zenos.interface.tools import write
        import zenos.interface.tools as tools_mod

        old_entry = _make_entry(status="superseded", superseded_by="entry-2")
        tools_mod.entry_repo.update_status = AsyncMock(return_value=old_entry)

        result = await write(
            collection="entries",
            id="entry-1",
            data={"status": "superseded", "superseded_by": "entry-2"},
        )

        assert "error" not in result
        assert result["status"] == "superseded"
        assert result["superseded_by"] == "entry-2"
        tools_mod.entry_repo.update_status.assert_called_once_with(
            "entry-1", "superseded", "entry-2", None
        )

    async def test_write_entry_update_status_not_found(self):
        """write entries update returns NOT_FOUND when entry doesn't exist."""
        from zenos.interface.tools import write
        import zenos.interface.tools as tools_mod

        tools_mod.entry_repo.update_status = AsyncMock(return_value=None)

        result = await write(
            collection="entries",
            id="nonexistent",
            data={"status": "archived", "archive_reason": "manual"},
        )

        assert result["error"] == "NOT_FOUND"

    async def test_write_entry_archive_with_reason_success(self):
        """write entries with status=archived and archive_reason=manual succeeds."""
        from zenos.interface.tools import write
        import zenos.interface.tools as tools_mod

        archived_entry = _make_entry(status="archived", archive_reason="manual")
        tools_mod.entry_repo.update_status = AsyncMock(return_value=archived_entry)

        result = await write(
            collection="entries",
            id="entry-1",
            data={"status": "archived", "archive_reason": "manual"},
        )

        assert "error" not in result
        assert result["status"] == "archived"
        assert result["archive_reason"] == "manual"
        tools_mod.entry_repo.update_status.assert_called_once_with(
            "entry-1", "archived", None, "manual"
        )

    async def test_write_entry_archive_missing_reason(self):
        """write entries with status=archived but no archive_reason returns INVALID_INPUT."""
        from zenos.interface.tools import write

        result = await write(
            collection="entries",
            id="entry-1",
            data={"status": "archived"},
        )

        assert result["error"] == "INVALID_INPUT"
        assert "archive_reason" in result["message"]

    async def test_write_entry_archive_invalid_reason(self):
        """write entries with invalid archive_reason returns INVALID_INPUT."""
        from zenos.interface.tools import write

        result = await write(
            collection="entries",
            id="entry-1",
            data={"status": "archived", "archive_reason": "invalid_value"},
        )

        assert result["error"] == "INVALID_INPUT"
        assert "archive_reason" in result["message"]

    async def test_write_entry_superseded_requires_superseded_by(self):
        """write entries with status=superseded requires superseded_by field."""
        from zenos.interface.tools import write

        result = await write(
            collection="entries",
            id="entry-1",
            data={"status": "superseded"},
        )

        assert result["error"] == "INVALID_INPUT"
        assert "superseded_by" in result["message"]


# ===================================================================
# write(collection="entries") — saturation warning tests (T2)
# ===================================================================

@pytest.mark.asyncio
class TestWriteEntriesSaturationWarning:

    async def test_write_entry_no_warning_when_below_limit(self):
        """write entries: no warning when active count < 20."""
        from zenos.interface.tools import write
        import zenos.interface.tools as tools_mod

        entry = _make_entry()
        tools_mod.entry_repo.create = AsyncMock(return_value=entry)
        tools_mod.entry_repo.count_active_by_entity = AsyncMock(return_value=19)

        result = await write(
            collection="entries",
            data={"entity_id": "ent-1", "type": "decision", "content": "PostgreSQL chosen"},
        )

        assert "error" not in result
        assert "warning" not in result

    async def test_write_entry_warning_when_at_limit(self):
        """write entries: warning returned when active count >= 20."""
        from zenos.interface.tools import write
        import zenos.interface.tools as tools_mod

        entry = _make_entry()
        tools_mod.entry_repo.create = AsyncMock(return_value=entry)
        tools_mod.entry_repo.count_active_by_entity = AsyncMock(return_value=20)

        result = await write(
            collection="entries",
            data={"entity_id": "ent-1", "type": "decision", "content": "PostgreSQL chosen"},
        )

        assert "error" not in result
        assert "warning" in result
        assert "analyze" in result["warning"]


# ===================================================================
# get(collection="entities") with active_entries tests
# ===================================================================

@pytest.mark.asyncio
class TestGetEntitiesActiveEntries:

    async def test_get_entity_by_name_includes_active_entries(self):
        """get(collection='entities', name=...) includes active_entries in response."""
        from zenos.interface.tools import get
        import zenos.interface.tools as tools_mod
        from zenos.application.ontology_service import EntityWithRelationships

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
        from zenos.interface.tools import get
        import zenos.interface.tools as tools_mod
        from zenos.application.ontology_service import EntityWithRelationships

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
        from zenos.interface.tools import governance_guide

        result = await governance_guide(topic="entity", level=1)

        assert result["topic"] == "entity"
        assert result["level"] == 1
        assert result["version"] == "1.0"
        assert isinstance(result["content"], str)
        assert len(result["content"]) > 0

    async def test_default_level_is_1(self):
        """governance_guide defaults to level=1 when level not provided."""
        from zenos.interface.tools import governance_guide

        result = await governance_guide(topic="capture")

        assert result["level"] == 1
        assert result["topic"] == "capture"

    # ── DC-2: All four topics × three levels ────────────────────────────────

    @pytest.mark.parametrize("topic", ["entity", "document", "task", "capture"])
    @pytest.mark.parametrize("level", [1, 2, 3])
    async def test_all_topics_and_levels_return_content(self, topic, level):
        """Each of the 12 topic/level combinations returns non-empty content."""
        from zenos.interface.tools import governance_guide

        result = await governance_guide(topic=topic, level=level)

        assert "error" not in result
        assert result["topic"] == topic
        assert result["level"] == level
        assert result["version"] == "1.0"
        assert isinstance(result["content"], str)
        assert len(result["content"]) >= 100, (
            f"Content for {topic} level={level} is too short: {len(result['content'])} chars"
        )

    async def test_level1_content_is_shorter_than_level3(self):
        """Level 1 content is shorter than Level 3 for the same topic."""
        from zenos.interface.tools import governance_guide

        result_l1 = await governance_guide(topic="entity", level=1)
        result_l3 = await governance_guide(topic="entity", level=3)

        assert len(result_l1["content"]) < len(result_l3["content"])

    # ── DC-3: Invalid input returns INVALID_INPUT error ─────────────────────

    async def test_invalid_topic_returns_error(self):
        """Invalid topic returns INVALID_INPUT error with valid topics listed."""
        from zenos.interface.tools import governance_guide

        result = await governance_guide(topic="unknown_topic", level=1)

        assert result["error"] == "INVALID_INPUT"
        assert "unknown_topic" in result["message"]
        # Must list valid topics in the message
        for valid in ["entity", "document", "task", "capture"]:
            assert valid in result["message"]

    async def test_invalid_level_returns_error(self):
        """Invalid level returns INVALID_INPUT error with valid levels listed."""
        from zenos.interface.tools import governance_guide

        result = await governance_guide(topic="entity", level=99)

        assert result["error"] == "INVALID_INPUT"
        assert "99" in result["message"]
        assert "1/2/3" in result["message"]

    async def test_level_zero_returns_error(self):
        """Level 0 (boundary) returns INVALID_INPUT error."""
        from zenos.interface.tools import governance_guide

        result = await governance_guide(topic="task", level=0)

        assert result["error"] == "INVALID_INPUT"

    async def test_empty_topic_returns_error(self):
        """Empty string topic returns INVALID_INPUT error."""
        from zenos.interface.tools import governance_guide

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
        from zenos.interface.tools import governance_guide

        result = await governance_guide(topic="entity", level=3)
        content = result["content"]

        # Must mention the three-question gate (external rule)
        assert "三問" in content
        # Must NOT expose internal LLM prompt details
        assert "system prompt" not in content.lower()
        assert "temperature" not in content.lower()

    async def test_capture_rules_describe_routing_not_llm_internals(self):
        """Capture rules describe routing logic but not LLM model selection internals."""
        from zenos.interface.tools import governance_guide

        result = await governance_guide(topic="capture", level=2)
        content = result["content"]

        # External rule: routing is mentioned
        assert "LAYER_DOWNGRADE_REQUIRED" in content
        # No internal model details
        assert "gemini" not in content.lower()
        assert "flash" not in content.lower()
