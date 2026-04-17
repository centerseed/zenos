"""Tests for the unified MCP response format (_unified_response helper)."""

from __future__ import annotations

from datetime import datetime, timezone
import pytest
from unittest.mock import AsyncMock, patch

from zenos.domain.action import Task
from zenos.domain.knowledge import Entity, Tags


# ---------------------------------------------------------------------------
# Bootstrap mocks — avoid wiring SQL repos in unit tests
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _mock_tool_bootstrap():
    """Prevent SQL repo bootstrapping in interface unit tests."""
    with patch("zenos.interface.mcp._ensure_services", new=AsyncMock(return_value=None)), \
         patch("zenos.interface.mcp.ontology_service", new=AsyncMock()), \
         patch("zenos.interface.mcp.task_service", new=AsyncMock()), \
         patch("zenos.interface.mcp.entity_repo", new=AsyncMock()), \
         patch("zenos.interface.mcp.entry_repo", new=AsyncMock()):
        yield


# ---------------------------------------------------------------------------
# Helper fixtures
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
        description="",
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        updated_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
    )
    defaults.update(overrides)
    return Task(**defaults)


# ---------------------------------------------------------------------------
# Unit tests for _unified_response helper
# ---------------------------------------------------------------------------


class TestUnifiedResponseHelper:
    """Unit tests for _unified_response()."""

    def test_unified_response_ok_with_data(self):
        """Normal ok response includes all required fields."""
        from zenos.interface.mcp import _unified_response

        result = _unified_response(data={"id": "abc", "name": "Test"})

        assert result["status"] == "ok"
        assert result["data"] == {"id": "abc", "name": "Test"}
        assert result["warnings"] == []
        assert result["suggestions"] == []
        assert result["similar_items"] == []
        assert result["context_bundle"] == {}
        assert result["governance_hints"] == {}
        assert "rejection_reason" not in result

    def test_unified_response_rejected_has_rejection_reason(self):
        """Rejected response includes rejection_reason field."""
        from zenos.interface.mcp import _unified_response

        result = _unified_response(
            status="rejected",
            data={},
            rejection_reason="Validation failed: missing name",
        )

        assert result["status"] == "rejected"
        assert result["data"] == {}
        assert result["rejection_reason"] == "Validation failed: missing name"

    def test_unified_response_defaults_are_empty(self):
        """All optional fields default to empty collections."""
        from zenos.interface.mcp import _unified_response

        result = _unified_response(data={"x": 1})

        assert result["warnings"] == []
        assert result["suggestions"] == []
        assert result["similar_items"] == []
        assert result["context_bundle"] == {}
        assert result["governance_hints"] == {}

    def test_unified_response_ok_no_rejection_reason(self):
        """rejection_reason key is absent for ok responses."""
        from zenos.interface.mcp import _unified_response

        result = _unified_response(data={})
        assert "rejection_reason" not in result

    def test_unified_response_carries_warnings(self):
        """Warnings list is preserved in the response."""
        from zenos.interface.mcp import _unified_response

        result = _unified_response(data={}, warnings=["w1", "w2"])
        assert result["warnings"] == ["w1", "w2"]

    def test_unified_response_carries_suggestions(self):
        """Suggestions list is preserved."""
        from zenos.interface.mcp import _unified_response

        sug = [{"id": "t1", "reason": "follow-up"}]
        result = _unified_response(data={}, suggestions=sug)
        assert result["suggestions"] == sug


# ---------------------------------------------------------------------------
# Integration tests: write() tool returns unified format
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestWriteEntitiesUnifiedFormat:

    async def test_write_entities_returns_unified_format(self):
        """write(collection='entities') returns unified response with data key."""
        from zenos.interface.mcp import write
        from zenos.application.knowledge.ontology_service import UpsertEntityResult
        from zenos.domain.shared import TagConfidence

        entity = _make_entity()
        upsert_result = UpsertEntityResult(
            entity=entity,
            tag_confidence=TagConfidence(confirmed_fields=[], draft_fields=[]),
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
                    "summary": "Test",
                    "tags": {"what": "app", "why": "x", "how": "y", "who": "z"},
                },
            )

        assert result["status"] == "ok"
        assert "data" in result
        assert result["data"]["entity"]["name"] == "Paceriz"
        assert "warnings" in result
        assert "suggestions" in result
        assert "similar_items" in result
        assert "context_bundle" in result
        assert "governance_hints" in result

    async def test_write_documents_returns_unified_format(self):
        """write(collection='documents') returns unified response."""
        from zenos.interface.mcp import write

        doc_entity = _make_entity(id="doc-1", name="Spec", type="document")

        with patch("zenos.interface.mcp.ontology_service") as mock_os:
            mock_os.upsert_document = AsyncMock(return_value=doc_entity)

            result = await write(
                collection="documents",
                data={
                    "title": "Spec",
                    "source": {"type": "github", "uri": "http://x.com", "adapter": "github"},
                    "tags": {"what": [], "why": "", "how": "", "who": []},
                    "summary": "A spec",
                    "linked_entity_ids": ["module-1"],
                },
            )

        assert result["status"] == "ok"
        assert "data" in result
        assert "context_bundle" in result
        assert "governance_hints" in result


# ---------------------------------------------------------------------------
# Integration tests: task() tool returns unified format
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestTaskUnifiedFormat:

    async def test_task_create_returns_unified_format(self):
        """task(action='create') returns unified response with data key."""
        from zenos.interface.mcp import task
        from zenos.application.action.task_service import TaskResult

        t = _make_task()
        create_result = TaskResult(task=t, cascade_updates=[])

        with patch("zenos.interface.mcp.task_service") as mock_ts:
            mock_ts.create_task = AsyncMock(return_value=create_result)
            mock_ts.enrich_task = AsyncMock(return_value={"expanded_entities": []})

            result = await task(
                action="create",
                title="Fix login",
                created_by="architect",
            )

        assert result["status"] == "ok"
        assert "data" in result
        assert result["data"]["title"] == "Fix login"
        assert "warnings" in result
        assert "suggestions" in result

    async def test_task_update_returns_unified_format(self):
        """task(action='update') returns unified response with data key."""
        from zenos.interface.mcp import task
        from zenos.application.action.task_service import TaskResult

        t = _make_task(status="in_progress")
        update_result = TaskResult(task=t, cascade_updates=[])

        with patch("zenos.interface.mcp.task_service") as mock_ts:
            mock_ts.update_task = AsyncMock(return_value=update_result)
            mock_ts.enrich_task = AsyncMock(return_value={"expanded_entities": []})

            result = await task(action="update", id="task-1", status="in_progress")

        assert result["status"] == "ok"
        assert "data" in result
        assert result["data"]["status"] == "in_progress"


# ---------------------------------------------------------------------------
# Integration tests: confirm() tool returns unified format
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestConfirmUnifiedFormat:

    async def test_confirm_tasks_returns_unified_format(self):
        """confirm(collection='tasks') returns unified response."""
        from zenos.interface.mcp import confirm
        from zenos.application.action.task_service import TaskResult

        t = _make_task(status="done")
        confirm_result = TaskResult(task=t, cascade_updates=[])

        with patch("zenos.interface.mcp.task_service") as mock_ts, \
             patch("zenos.interface.mcp.entry_repo") as _mock_er:
            mock_ts.confirm_task = AsyncMock(return_value=confirm_result)

            result = await confirm(collection="tasks", id="task-1", accepted=True)

        assert result["status"] == "ok"
        assert "data" in result
        assert "suggestions" in result
        assert "context_bundle" in result
        assert "governance_hints" in result

    async def test_confirm_entities_returns_unified_format(self):
        """confirm(collection='entities') returns unified response."""
        from zenos.interface.mcp import confirm

        with patch("zenos.interface.mcp.ontology_service") as mock_os:
            mock_os.confirm = AsyncMock(return_value={"confirmed_by_user": True})

            result = await confirm(collection="entities", id="ent-1")

        assert result["status"] == "ok"
        assert "data" in result
        assert "context_bundle" in result
        assert "governance_hints" in result


# ---------------------------------------------------------------------------
# Validation error → rejected status
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestValidationErrorReturnsRejected:

    async def test_write_unknown_collection_returns_rejected(self):
        """Calling write() with unknown collection returns status=rejected."""
        from zenos.interface.mcp import write

        result = await write(collection="invalid_col", data={})

        assert result["status"] == "rejected"
        assert "rejection_reason" in result
        assert "invalid_col" in result["rejection_reason"]

    async def test_task_missing_title_returns_rejected(self):
        """task(action='create') without title returns status=rejected."""
        from zenos.interface.mcp import task

        result = await task(action="create", created_by="architect")

        assert result["status"] == "rejected"
        assert "title" in result["rejection_reason"]

    async def test_confirm_value_error_returns_rejected(self):
        """confirm() that raises ValueError returns status=rejected."""
        from zenos.interface.mcp import confirm

        with patch("zenos.interface.mcp.ontology_service") as mock_os:
            mock_os.confirm = AsyncMock(side_effect=ValueError("Entity not found"))

            result = await confirm(collection="entities", id="missing")

        assert result["status"] == "rejected"
        assert "rejection_reason" in result
