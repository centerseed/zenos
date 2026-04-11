"""Tests for IngestionService."""

from __future__ import annotations

import pytest

from zenos.application.ingestion import IngestionService, InMemoryIngestionRepository


@pytest.mark.asyncio
async def test_distill_produces_candidates_without_core_mutation():
    repo = InMemoryIngestionRepository()
    service = IngestionService(repo)

    await service.ingest(
        {
            "workspace_id": "ws-1",
            "product_id": "prod-1",
            "external_user_id": "u-1",
            "external_signal_id": "sig-1",
            "event_type": "task_input",
            "raw_ref": "app://zentropy/signals/sig-1",
            "summary": "Need to ship API",
            "intent": "todo",
            "confidence": 0.9,
            "occurred_at": service.parse_iso8601("2026-04-11T10:00:00Z"),
        }
    )

    out = await service.distill(
        workspace_id="ws-1",
        product_id="prod-1",
        window_from=service.parse_iso8601("2026-04-10T00:00:00Z"),
        window_to=service.parse_iso8601("2026-04-12T00:00:00Z"),
        max_items=20,
    )

    assert out["batch_id"]
    assert len(out["task_candidates"]) == 1
    assert out["entry_candidates"] == []
    assert out["l2_update_candidates"] == []


@pytest.mark.asyncio
async def test_commit_uses_canonical_adapters_for_task_and_entry():
    repo = InMemoryIngestionRepository()
    service = IngestionService(repo)

    task_calls: list[dict] = []
    entry_calls: list[dict] = []

    async def _task_adapter(_workspace_id: str, payload: dict) -> dict:
        task_calls.append(payload)
        return {"status": "ok", "data": {"id": "task-1"}}

    async def _entry_adapter(_workspace_id: str, payload: dict) -> dict:
        entry_calls.append(payload)
        return {"status": "ok", "data": {"id": "entry-1"}}

    out = await service.commit(
        workspace_id="ws-1",
        product_id="prod-1",
        batch_id="batch-1",
        task_candidates=[{"title": "t1", "description": "d1", "forbidden": "x"}],
        entry_candidates=[{"entity_id": "ent-1", "type": "insight", "content": "c1"}],
        l2_update_candidates=[],
        task_adapter=_task_adapter,
        entry_adapter=_entry_adapter,
        atomic=False,
    )

    assert len(out["committed"]) == 2
    assert out["rejected"] == []
    assert len(task_calls) == 1
    assert len(entry_calls) == 1
    assert "forbidden" not in task_calls[0]
    assert any("ignored unknown fields" in w for w in out["warnings"])


@pytest.mark.asyncio
async def test_commit_rejects_forbidden_entry_type_and_routes_l2_to_review_queue():
    repo = InMemoryIngestionRepository()
    service = IngestionService(repo)

    async def _ok_task(_workspace_id: str, payload: dict) -> dict:
        return {"status": "ok", "data": {"id": "task-1", "title": payload.get("title")}}

    async def _ok_entry(_workspace_id: str, payload: dict) -> dict:
        return {"status": "ok", "data": {"id": "entry-1", "entity_id": payload.get("entity_id")}}

    out = await service.commit(
        workspace_id="ws-1",
        product_id="prod-1",
        batch_id="batch-1",
        task_candidates=[{"title": "ok-task"}],
        entry_candidates=[{"entity_id": "ent-1", "type": "invalid", "content": "nope"}],
        l2_update_candidates=[{"entity_id": "l2-1"}],
        task_adapter=_ok_task,
        entry_adapter=_ok_entry,
        atomic=False,
    )

    assert len(out["committed"]) == 1
    assert len(out["rejected"]) == 1
    assert out["rejected"][0]["type"] == "entry"
    assert len(out["queued_for_review"]) == 1


@pytest.mark.asyncio
async def test_commit_rejects_forbidden_mutation_target():
    repo = InMemoryIngestionRepository()
    service = IngestionService(repo)

    async def _ok_task(_workspace_id: str, payload: dict) -> dict:
        return {"status": "ok", "data": {"id": "task-1", "title": payload.get("title")}}

    async def _ok_entry(_workspace_id: str, payload: dict) -> dict:
        return {"status": "ok", "data": {"id": "entry-1", "entity_id": payload.get("entity_id")}}

    out = await service.commit(
        workspace_id="ws-1",
        product_id="prod-1",
        batch_id="batch-1",
        task_candidates=[{"title": "bad", "collection": "entities"}],
        entry_candidates=[{"entity_id": "ent-1", "type": "insight", "content": "ok"}],
        l2_update_candidates=[],
        task_adapter=_ok_task,
        entry_adapter=_ok_entry,
        atomic=False,
    )

    assert len(out["committed"]) == 1
    assert len(out["rejected"]) == 1
    assert out["rejected"][0]["reason"] == "forbidden mutation target"


@pytest.mark.asyncio
async def test_validate_candidates_rejects_entry_content_longer_than_200():
    repo = InMemoryIngestionRepository()
    service = IngestionService(repo)

    (
        _validated_tasks,
        validated_entries,
        rejected,
        _warnings,
    ) = service.validate_candidates(
        task_candidates=[],
        entry_candidates=[
            {
                "entity_id": "ent-1",
                "type": "insight",
                "content": "x" * 201,
            }
        ],
    )

    assert validated_entries == []
    assert len(rejected) == 1
    assert rejected[0]["type"] == "entry"
    assert rejected[0]["reason"] == "content must be 1-200 chars"


@pytest.mark.asyncio
async def test_validate_candidates_rejects_entry_context_longer_than_200():
    repo = InMemoryIngestionRepository()
    service = IngestionService(repo)

    (
        _validated_tasks,
        validated_entries,
        rejected,
        _warnings,
    ) = service.validate_candidates(
        task_candidates=[],
        entry_candidates=[
            {
                "entity_id": "ent-1",
                "type": "insight",
                "content": "valid content",
                "context": "c" * 201,
            }
        ],
    )

    assert validated_entries == []
    assert len(rejected) == 1
    assert rejected[0]["type"] == "entry"
    assert rejected[0]["reason"] == "context must be <= 200 chars"
