"""Tests for MCP tool handlers (interface layer).

Strategy: mock the service layer (ontology_service, task_service, source_service)
and test that each tool function correctly:
  - Routes to the right service method
  - Serializes results properly
  - Handles errors with correct error codes
  - Validates input parameters
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from zenos.application.ontology_service import (
    EntityWithRelationships,
    UpsertEntityResult,
)
from zenos.domain.governance import TagConfidence
from zenos.domain.models import (
    Blindspot,
    Document,
    DocumentTags,
    Entity,
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


# ---------------------------------------------------------------------------
# Fixtures: reusable domain objects
# ---------------------------------------------------------------------------

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
        with patch("zenos.interface.tools.task_repo") as mock_tr:
            mock_tr.get_by_id = AsyncMock(return_value=task)

            result = await get(collection="tasks", id="task-1")

            assert result["title"] == "Fix login"

    async def test_get_task_not_found(self):
        from zenos.interface.tools import get

        with patch("zenos.interface.tools.task_repo") as mock_tr:
            mock_tr.get_by_id = AsyncMock(return_value=None)

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

            result = await analyze(check_type="quality")

            assert "quality" in result
            assert result["quality"]["score"] == 85

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
            mock_gs.run_staleness_check = AsyncMock(return_value=warnings)

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
            mock_gs.run_staleness_check = AsyncMock(return_value=[])
            mock_gs.run_blindspot_analysis = AsyncMock(return_value=[])

            result = await analyze(check_type="all")

            assert "quality" in result
            assert "staleness" in result
            assert "blindspots" in result

    async def test_analyze_invalid_type(self):
        from zenos.interface.tools import analyze

        result = await analyze(check_type="foobar")

        assert result["error"] == "INVALID_INPUT"
        assert "Unknown check_type" in result["message"]
