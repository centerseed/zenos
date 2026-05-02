"""
AC tests for SPEC-mcp-schema-compatibility-resilience.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from zenos.application.action.task_service import TaskResult
from zenos.application.knowledge.ontology_service import UpsertEntityResult
from zenos.domain.action import Task
from zenos.domain.knowledge import Entity, Tags

pytestmark = pytest.mark.asyncio


def _make_entity(**overrides) -> Entity:
    defaults = dict(
        id="doc-1",
        name="Test Entity",
        type="product",
        summary="A test entity",
        tags=Tags(what=["test"], why="testing", how="pytest", who=["dev"]),
        status="active",
        created_at=datetime(2026, 5, 1, tzinfo=timezone.utc),
        updated_at=datetime(2026, 5, 1, tzinfo=timezone.utc),
    )
    defaults.update(overrides)
    return Entity(**defaults)


def _make_task(**overrides) -> Task:
    defaults = dict(
        id="task-1",
        title="Fix schema",
        status="in_progress",
        priority="high",
        created_by="creator-1",
        updated_by="actor-1",
        created_at=datetime(2026, 5, 1, tzinfo=timezone.utc),
        updated_at=datetime(2026, 5, 1, tzinfo=timezone.utc),
    )
    defaults.update(overrides)
    return Task(**defaults)


@pytest.mark.spec("AC-MSCR-01")
async def test_ac_mscr_01_write_accepts_json_string_data_with_warning():
    """write(data='<valid JSON object>') coerces to dict, proceeds, and warns."""
    from zenos.interface.mcp.write import write

    saved = _make_entity(id="ent-1", name="Schema Compat")
    upsert_result = UpsertEntityResult(
        entity=saved,
        tag_confidence=None,
        split_recommendation=None,
        warnings=[],
        similar_items=[],
    )

    with (
        patch("zenos.interface.mcp._ensure_services", AsyncMock()),
        patch("zenos.interface.mcp.entity_repo") as entity_repo,
        patch("zenos.interface.mcp.ontology_service") as ontology_service,
        patch("zenos.interface.mcp._schedule_embed", MagicMock()),
        patch("zenos.interface.mcp.write._current_partner") as partner_ctx,
    ):
        partner_ctx.get.return_value = None
        entity_repo.get_by_id = AsyncMock(return_value=None)
        entity_repo.get_by_name = AsyncMock(return_value=None)
        ontology_service.upsert_entity = AsyncMock(return_value=upsert_result)

        result = await write(
            collection="entities",
            data='{"name":"Schema Compat","type":"product","summary":"ok","tags":{"what":["x"],"why":"y","how":"z","who":["dev"]}}',
        )

    assert result["status"] == "ok"
    ontology_service.upsert_entity.assert_awaited_once()
    assert isinstance(ontology_service.upsert_entity.call_args.args[0], dict)
    assert any("DEPRECATED_WRITE_DATA_JSON_STRING" in warning for warning in result["warnings"])

    invalid = await write(collection="entities", data='["not", "object"]')
    assert invalid["status"] == "rejected"
    assert invalid["data"]["error"] == "INVALID_DATA_JSON_OBJECT"


@pytest.mark.spec("AC-MSCR-02")
async def test_ac_mscr_02_journal_write_normalizes_string_tags():
    """journal_write string tags normalize to list tags."""
    from zenos.interface.mcp.journal import journal_write

    repo = AsyncMock()
    repo.create = AsyncMock(return_value="journal-1")
    repo.count = AsyncMock(return_value=1)
    repo.list_recent = AsyncMock(return_value=([], 0))

    mock_pid = MagicMock()
    mock_pid.get.return_value = "partner-1"
    mock_partner = MagicMock()
    mock_partner.get.return_value = {"id": "partner-1", "defaultProject": ""}

    with (
        patch("zenos.interface.mcp._journal_repo", repo),
        patch("zenos.interface.mcp._ensure_journal_repo", AsyncMock()),
        patch("zenos.infrastructure.context.current_partner_id", mock_pid),
        patch("zenos.interface.mcp.journal._current_partner", mock_partner),
    ):
        csv_result = await journal_write(summary="csv tags", tags="a,b")
        csv_tags = repo.create.call_args.kwargs["tags"]
        json_result = await journal_write(summary="json tags", tags='["a","b"]')
        json_tags = repo.create.call_args.kwargs["tags"]

    assert csv_result["status"] == "ok"
    assert csv_tags == ["a", "b"]
    assert json_result["status"] == "ok"
    assert json_tags == ["a", "b"]


@pytest.mark.spec("AC-MSCR-03")
async def test_ac_mscr_03_read_source_uri_alias_warns_and_reads_doc():
    """read_source(uri=...) maps to doc_id, reads content, and warns."""
    from zenos.interface.mcp.source import read_source

    doc = _make_entity(id="doc-1", name="Test Doc", type="document", sources=[])

    with (
        patch("zenos.interface.mcp._ensure_services", AsyncMock()),
        patch("zenos.interface.mcp.ontology_service") as ontology_service,
        patch("zenos.interface.mcp.source_service") as source_service,
        patch("zenos.interface.mcp.source._current_partner") as partner_ctx,
    ):
        partner_ctx.get.return_value = None
        ontology_service.get_document = AsyncMock(return_value=doc)
        source_service.read_source = AsyncMock(return_value="full content")

        docs_result = await read_source(uri="/docs/doc-1")
        plain_result = await read_source(uri="doc-1")
        invalid_results = [
            await read_source(uri="https://example.com/doc.md"),
            await read_source(uri="/bad/doc-1"),
            await read_source(uri="/docs/"),
        ]

    assert docs_result["status"] == "ok"
    assert docs_result["data"]["doc_id"] == "doc-1"
    assert docs_result["data"]["content"] == "full content"
    assert any("DEPRECATED_READ_SOURCE_URI_ALIAS" in warning for warning in docs_result["warnings"])
    assert plain_result["status"] == "ok"
    assert plain_result["data"]["doc_id"] == "doc-1"
    assert any("DEPRECATED_READ_SOURCE_URI_ALIAS" in warning for warning in plain_result["warnings"])
    assert source_service.read_source.await_count == 2
    for invalid in invalid_results:
        assert invalid["status"] == "rejected"
        assert invalid["data"]["error"] == "INVALID_READ_SOURCE_URI_ALIAS"


@pytest.mark.spec("AC-MSCR-04")
async def test_ac_mscr_04_task_updated_by_audit_echo_is_ignored_with_warning():
    """task(updated_by=...) is ignored with warning rather than schema failure."""
    from zenos.interface.mcp.task import task

    service_result = TaskResult(task=_make_task(updated_by="actor-1"), cascade_updates=[])

    with (
        patch("zenos.interface.mcp.task_service") as task_service,
        patch("zenos.interface.mcp.task._current_partner") as partner_ctx,
        patch("zenos.interface.mcp.task._enrich_task_result", AsyncMock(return_value={"id": "task-1", "updated_by": "actor-1"})),
    ):
        partner_ctx.get.return_value = {"id": "actor-1", "defaultProject": ""}
        task_service.update_task = AsyncMock(return_value=service_result)

        result = await task(
            action="update",
            id="task-1",
            status="in_progress",
            updated_by="legacy-client",
        )

    assert result["status"] == "ok"
    updates = task_service.update_task.call_args.args[1]
    assert updates["updated_by"] == "actor-1"
    assert updates["updated_by"] != "legacy-client"
    assert any("UPDATED_BY_IGNORED" in warning for warning in result["warnings"])


@pytest.mark.spec("AC-MSCR-05")
async def test_ac_mscr_05_get_missing_collection_returns_structured_rejection():
    """get(collection=None) returns structured MISSING_COLLECTION rejection."""
    from zenos.interface.mcp.get import get

    result = await get(collection=None, id="x")

    assert result["status"] == "rejected"
    assert result["data"]["error"] == "MISSING_COLLECTION"
    assert "entities" in result["data"]["allowed"]
