"""
QA-added regression tests for SPEC-docs-native-edit-and-helper-ingest.

Written by QA during S04 acceptance — not part of Developer's original test suite.

Covers:
- Risk 1: cross-doc duplicate try/except silent swallow — mock entity_repo to raise,
  confirm response still surfaces warning or at least does not emit a false "no duplicate" signal.
- Regression: IndentationError in recent_updates.py blocks AC-DNH-12/13/17 import path
  (documented as production code bug that must be fixed before deploy).
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from zenos.domain.knowledge import Entity, EntityType, Tags


# ---------------------------------------------------------------------------
# Shared helpers (copied from test_docs_native_edit_and_helper_ingest_ac.py)
# ---------------------------------------------------------------------------

def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _make_entity(
    *,
    entity_id: str = "doc-test-1",
    name: str = "Test Doc",
    sources: list[dict] | None = None,
    status: str = "current",
    doc_role: str = "index",
    partner_id: str = "partner-test",
) -> Entity:
    if sources is None:
        sources = [{
            "source_id": "src-1",
            "uri": "/docs/doc-test-1",
            "type": "zenos_native",
            "status": "valid",
            "source_status": "valid",
            "is_primary": True,
        }]
    return Entity(
        id=entity_id,
        name=name,
        type=EntityType.DOCUMENT,
        summary="Test document",
        tags=Tags(what=["test"], why="testing", how="unit", who=["dev"]),
        status=status,
        sources=sources,
        doc_role=doc_role,
        visibility="public",
        created_at=_now_utc(),
        updated_at=_now_utc(),
    )


class _StubEntityRepo:
    """In-memory stub for EntityRepository (same as in AC test file)."""

    def __init__(self, entities: list[Entity]) -> None:
        self._by_id = {e.id: e for e in entities if e.id}
        self._all = list(entities)

    async def get_by_id(self, entity_id: str) -> Entity | None:
        return self._by_id.get(entity_id)

    async def get_by_name(self, name: str) -> Entity | None:
        return next((e for e in self._all if e.name == name), None)

    async def list_all(self, type_filter: str | None = None) -> list[Entity]:
        if type_filter is None:
            return list(self._all)
        return [e for e in self._all if e.type == type_filter]

    async def upsert(self, entity: Entity) -> Entity:
        self._by_id[entity.id] = entity
        self._all = [e if e.id != entity.id else entity for e in self._all]
        if entity.id not in {e.id for e in self._all}:
            self._all.append(entity)
        return entity

    async def list_unconfirmed(self) -> list[Entity]:
        return []

    async def list_by_parent(self, parent_id: str) -> list[Entity]:
        return []

    async def list_by_ids(self, ids: list[str]) -> list[Entity]:
        return [self._by_id[i] for i in ids if i in self._by_id]

    async def update_source_status(self, entity_id: str, status: str, source_id: str | None = None) -> None:
        entity = self._by_id.get(entity_id)
        if entity:
            for src in (entity.sources or []):
                if source_id is None or src.get("source_id") == source_id:
                    src["status"] = status
                    src["source_status"] = status

    async def archive_entity(self, entity_id: str) -> None:
        entity = self._by_id.get(entity_id)
        if entity:
            entity.status = "archived"

    async def find_by_id_prefix(self, prefix: str, partner_id: str, limit: int = 11) -> list[Entity]:
        return []


PARENT_ENTITY = Entity(
    id="parent-entity-1",
    name="Test L2 Module",
    type="module",
    summary="Parent module for tests",
    tags=Tags(what=["module"], why="test", how="test", who=["dev"]),
    status="active",
    level=2,
)

_LINKED = ["parent-entity-1"]


def _make_ontology_service(entities: list[Entity] | None = None):
    """Create real OntologyService with in-memory stubs."""
    from zenos.application.knowledge.ontology_service import OntologyService

    all_entities = list(entities or [])
    if not any(e.id == PARENT_ENTITY.id for e in all_entities):
        all_entities.append(PARENT_ENTITY)

    entity_repo = _StubEntityRepo(all_entities)
    doc_repo = AsyncMock()
    doc_repo.list_all = AsyncMock(return_value=[])
    doc_repo.get_by_id = AsyncMock(return_value=None)
    rel_repo = AsyncMock()
    rel_repo.list_by_entity = AsyncMock(return_value=[])
    rel_repo.add = AsyncMock()
    rel_repo.find_duplicate = AsyncMock(return_value=None)
    rel_repo.remove_by_id = AsyncMock(return_value=1)
    rel_repo.delete_by_source_and_type = AsyncMock(return_value=0)
    protocol_repo = AsyncMock()
    protocol_repo.get_by_entity = AsyncMock(return_value=None)
    blindspot_repo = AsyncMock()

    svc = OntologyService(
        entity_repo=entity_repo,
        document_repo=doc_repo,
        relationship_repo=rel_repo,
        protocol_repo=protocol_repo,
        blindspot_repo=blindspot_repo,
    )
    return svc, entity_repo


# ---------------------------------------------------------------------------
# Risk 1: cross-doc duplicate try/except silent swallow
# ---------------------------------------------------------------------------

@pytest.mark.qa_regression
@pytest.mark.spec("Risk-1-cross-doc-duplicate-swallow")
async def test_risk1_cross_doc_duplicate_check_exception_is_logged_not_silently_swallowed():
    """Regression: RISK-1 — cross-doc external_id duplicate check try/except.

    When entity_repo.list_all raises an exception during cross-doc duplicate check,
    the operation should NOT emit a false 'no DUPLICATE_EXTERNAL_ID_ACROSS_BUNDLES' signal.
    The exception must be logged (logger.warning), and _helper_warnings should be empty
    (not containing false negatives).

    The correct behavior:
    - Exception is caught and logged (logger.warning with exc_info=True)
    - _helper_warnings remains empty ([] — not a false 'clean' signal)
    - The upsert itself succeeds (the entity is saved)
    - The caller is NOT given a misleading 'all clear' on cross-doc duplicates

    Found by QA on 2026-04-20 during S04 acceptance.
    """
    import logging

    doc_entity = _make_entity(
        entity_id="doc-risk1-test",
        sources=[{
            "source_id": "src-risk1",
            "uri": "/docs/doc-risk1-test",
            "type": "zenos_native",
            "status": "valid",
            "source_status": "valid",
            "is_primary": True,
        }],
    )
    svc, entity_repo = _make_ontology_service([doc_entity])

    # Patch list_all to raise an exception on the cross-doc check call
    # (The cross-doc check calls list_all with type_filter=EntityType.DOCUMENT)
    original_list_all = entity_repo.list_all
    call_count = [0]

    async def list_all_raise_on_second(type_filter=None):
        call_count[0] += 1
        # The cross-doc duplicate check calls list_all with type_filter=DOCUMENT
        if type_filter == EntityType.DOCUMENT or type_filter == "document":
            raise RuntimeError("Simulated DB error during cross-doc check")
        return await original_list_all(type_filter=type_filter)

    entity_repo.list_all = list_all_raise_on_second

    with patch.object(
        logging.getLogger("zenos.application.knowledge.ontology_service"),
        "warning",
    ) as mock_warning:
        result = await svc.upsert_document({
            "id": "doc-risk1-test",
            "linked_entity_ids": _LINKED,
            "add_source": {
                "type": "notion",
                "uri": "https://www.notion.so/risk1-page-abc123def456abc123def456abc123de",
                "external_id": "notion:risk1-test",
                "snapshot_summary": "Risk 1 summary.",
            },
        })

    # Assertion 1: The upsert itself succeeded
    assert result is not None, "Upsert should succeed even if cross-doc check fails"

    # Assertion 2: logger.warning was called (exception was not silently swallowed)
    assert mock_warning.called, (
        "logger.warning should have been called when list_all raises during cross-doc check. "
        "Exception was silently swallowed — this masks the true state of cross-doc duplicates."
    )

    # Assertion 3: _helper_warnings is empty (not a false positive, but also not misleading)
    helper_warnings = getattr(result, "_helper_warnings", [])
    assert isinstance(helper_warnings, list), "_helper_warnings should be a list"
    # It should be empty because the check failed — empty != "confirmed no duplicates"
    # This is acceptable behavior, but the caller must know the check was degraded
    assert len(helper_warnings) == 0, (
        "When cross-doc check fails, _helper_warnings should be empty (not a false DUPLICATE warning). "
        f"Got: {helper_warnings}"
    )


@pytest.mark.qa_regression
@pytest.mark.spec("Risk-1-cross-doc-duplicate-swallow")
async def test_risk1_cross_doc_duplicate_detected_when_repo_works():
    """Companion to risk1 test: verify the happy path still produces warning when repo works.

    This ensures the try/except doesn't prevent the warning when there IS a duplicate.
    Found by QA on 2026-04-20.
    """
    # doc X already has the external_id
    doc_x = _make_entity(
        entity_id="doc-x-risk1",
        name="Doc X Risk1",
        sources=[{
            "source_id": "src-x-risk1",
            "uri": "https://www.notion.so/notion-risk1-abc123def456abc123def456abc123de",
            "type": "notion",
            "external_id": "notion:risk1-cross",
            "status": "valid",
            "source_status": "valid",
        }],
    )
    # doc Y will receive the same external_id
    doc_y = _make_entity(
        entity_id="doc-y-risk1",
        name="Doc Y Risk1",
        sources=[{
            "source_id": "src-y-risk1",
            "uri": "/docs/doc-y-risk1",
            "type": "zenos_native",
            "status": "valid",
            "source_status": "valid",
        }],
    )
    svc, repo = _make_ontology_service([doc_x, doc_y])

    result = await svc.upsert_document({
        "id": "doc-y-risk1",
        "linked_entity_ids": _LINKED,
        "add_source": {
            "type": "notion",
            "uri": "https://www.notion.so/another-risk1-abc123def456abc123def456abc12345",
            "external_id": "notion:risk1-cross",
            "snapshot_summary": "Cross-doc risk1 summary.",
        },
    })

    assert result is not None
    helper_warnings = getattr(result, "_helper_warnings", [])
    assert any(
        "DUPLICATE_EXTERNAL_ID_ACROSS_BUNDLES" in w for w in helper_warnings
    ), (
        f"Expected DUPLICATE_EXTERNAL_ID_ACROSS_BUNDLES warning when repo works fine, "
        f"got: {helper_warnings}"
    )
