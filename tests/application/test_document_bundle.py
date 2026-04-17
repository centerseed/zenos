"""Tests for ADR-022 Document Bundle — application layer operations.

Tests cover:
  - doc_role handling (single/index)
  - add_source / update_source / remove_source operations
  - doc_role guards (single cannot add 2nd source)
  - change_summary and summary_updated_at
  - source_id generation and preservation
  - doc_type warning for unknown types
"""

from __future__ import annotations

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from zenos.domain.knowledge import Entity, EntityType, Tags


def _make_entity_repo():
    """Create a mock entity repository."""
    repo = AsyncMock()
    repo.list_all = AsyncMock(return_value=[])
    repo.get_by_id = AsyncMock(return_value=None)
    repo.get_by_name = AsyncMock(return_value=None)
    repo.upsert = AsyncMock(side_effect=lambda e, **kw: e)
    return repo


def _make_service(entity_repo=None):
    """Create an OntologyService with mocked repos."""
    from zenos.application.knowledge.ontology_service import OntologyService

    entity_repo = entity_repo or _make_entity_repo()
    doc_repo = AsyncMock()
    doc_repo.list_all = AsyncMock(return_value=[])
    rel_repo = AsyncMock()
    rel_repo.list_by_entity = AsyncMock(return_value=[])
    rel_repo.upsert = AsyncMock()
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
    return svc


def _make_doc_entity(
    *,
    doc_id: str = "doc-test-1",
    name: str = "Test Document",
    doc_role: str = "single",
    sources: list[dict] | None = None,
    bundle_highlights: list[dict] | None = None,
    change_summary: str | None = None,
    highlights_updated_at: datetime | None = None,
    summary_updated_at: datetime | None = None,
) -> Entity:
    """Create a test document entity."""
    if sources is None:
        sources = [{
            "source_id": "src-1",
            "uri": "https://github.com/owner/repo/blob/main/docs/test.md",
            "type": "github",
            "label": "test.md",
            "status": "valid",
        }]
    return Entity(
        id=doc_id,
        name=name,
        type=EntityType.DOCUMENT,
        summary="Test document summary",
        tags=Tags(what=["test"], why="testing", how="auto", who=["dev"]),
        level=3,
        status="current",
        parent_id="parent-1",
        sources=sources,
        doc_role=doc_role,
        bundle_highlights=bundle_highlights or [],
        highlights_updated_at=highlights_updated_at,
        change_summary=change_summary,
        summary_updated_at=summary_updated_at,
    )


class TestDocRoleHandling:
    @pytest.mark.asyncio
    async def test_new_doc_defaults_to_index(self):
        """New document without doc_role defaults to index."""
        svc = _make_service()
        parent = Entity(
            id="parent-1", name="Parent Module", type="module",
            summary="Parent", tags=Tags(what=["x"], why="", how="", who=[""]),
            level=2,
        )
        svc._entities.get_by_id = AsyncMock(return_value=parent)

        result = await svc.upsert_document({
            "title": "New Doc",
            "summary": "A new document",
            "tags": {"what": ["test"], "why": "testing", "how": "auto", "who": ["dev"]},
            "source": {"type": "github", "uri": "https://github.com/owner/repo/blob/main/new.md"},
            "linked_entity_ids": ["parent-1"],
        })
        assert result.doc_role == "index"

    @pytest.mark.asyncio
    async def test_create_with_index_role(self):
        """Can create a document with doc_role=index."""
        svc = _make_service()
        parent = Entity(
            id="parent-1", name="Parent Module", type="module",
            summary="Parent", tags=Tags(what=["x"], why="", how="", who=[""]),
            level=2,
        )
        svc._entities.get_by_id = AsyncMock(return_value=parent)

        result = await svc.upsert_document({
            "title": "Doc Index",
            "summary": "A document index",
            "tags": {"what": ["test"], "why": "testing", "how": "auto", "who": ["dev"]},
            "source": {"type": "github", "uri": "https://github.com/owner/repo/blob/main/index.md"},
            "linked_entity_ids": ["parent-1"],
            "doc_role": "index",
        })
        assert result.doc_role == "index"

    @pytest.mark.asyncio
    async def test_formal_entry_persists_in_details(self):
        """formal_entry flag is persisted in document details."""
        svc = _make_service()
        parent = Entity(
            id="parent-1", name="Parent Module", type="module",
            summary="Parent", tags=Tags(what=["x"], why="", how="", who=[""]),
            level=2,
        )
        svc._entities.get_by_id = AsyncMock(return_value=parent)

        result = await svc.upsert_document({
            "title": "Doc Index",
            "summary": "A document index",
            "tags": {"what": ["test"], "why": "testing", "how": "auto", "who": ["dev"]},
            "source": {"type": "github", "uri": "https://github.com/owner/repo/blob/main/index.md"},
            "linked_entity_ids": ["parent-1"],
            "doc_role": "index",
            "formal_entry": True,
        })
        assert result.details is not None
        assert result.details["formal_entry"] is True


class TestAddSource:
    @pytest.mark.asyncio
    async def test_add_source_to_index(self):
        """Can add a source to an index document."""
        existing = _make_doc_entity(doc_role="index")
        repo = _make_entity_repo()
        repo.get_by_id = AsyncMock(return_value=existing)
        svc = _make_service(entity_repo=repo)

        result = await svc.upsert_document({
            "id": "doc-test-1",
            "linked_entity_ids": ["parent-1"],
            "add_source": {
                "uri": "https://github.com/owner/repo/blob/main/docs/new.md",
                "type": "github",
                "label": "new.md",
                "doc_type": "SPEC",
            },
        })
        assert len(result.sources) == 2
        new_source = result.sources[1]
        assert new_source["uri"] == "https://github.com/owner/repo/blob/main/docs/new.md"
        assert new_source["source_id"]  # generated
        assert new_source["doc_type"] == "SPEC"

    @pytest.mark.asyncio
    async def test_add_source_to_single_rejected(self):
        """Cannot add a second source to a single doc entity."""
        existing = _make_doc_entity(doc_role="single")
        repo = _make_entity_repo()
        repo.get_by_id = AsyncMock(return_value=existing)
        svc = _make_service(entity_repo=repo)

        with pytest.raises(ValueError, match="single doc entity 只能有一個 source"):
            await svc.upsert_document({
                "id": "doc-test-1",
                "linked_entity_ids": ["parent-1"],
                "add_source": {
                    "uri": "https://github.com/owner/repo/blob/main/docs/extra.md",
                    "type": "github",
                    "label": "extra.md",
                },
            })

    @pytest.mark.asyncio
    async def test_add_source_generates_suggestion(self):
        """Bundle operations should produce deterministic highlight suggestion."""
        existing = _make_doc_entity(doc_role="index")
        repo = _make_entity_repo()
        repo.get_by_id = AsyncMock(return_value=existing)
        svc = _make_service(entity_repo=repo)

        result = await svc.upsert_document({
            "id": "doc-test-1",
            "linked_entity_ids": ["parent-1"],
            "add_source": {
                "uri": "https://github.com/owner/repo/blob/main/docs/new.md",
                "type": "github",
                "label": "new.md",
                "doc_type": "SPEC",
            },
        })
        suggestions = getattr(result, "_bundle_suggestions", [])
        assert any("change_summary" in s for s in suggestions)
        highlight_suggestion = next(
            suggestion for suggestion in suggestions
            if isinstance(suggestion, dict) and suggestion.get("type") == "bundle_highlights_suggestion"
        )
        assert highlight_suggestion["items"][0]["headline"] == "new.md"
        assert highlight_suggestion["items"][0]["priority"] == "primary"

    @pytest.mark.asyncio
    async def test_add_source_unknown_doc_type_warns(self):
        """Unknown doc_type should produce a warning but not reject."""
        existing = _make_doc_entity(doc_role="index")
        repo = _make_entity_repo()
        repo.get_by_id = AsyncMock(return_value=existing)
        svc = _make_service(entity_repo=repo)

        result = await svc.upsert_document({
            "id": "doc-test-1",
            "linked_entity_ids": ["parent-1"],
            "add_source": {
                "uri": "https://github.com/owner/repo/blob/main/docs/new.md",
                "type": "github",
                "label": "new.md",
                "doc_type": "UNKNOWN_TYPE",
            },
        })
        suggestions = getattr(result, "_bundle_suggestions", [])
        assert any("not a known type" in s for s in suggestions)

    @pytest.mark.asyncio
    async def test_add_source_only_suggests_diff_when_highlights_exist(self):
        existing = _make_doc_entity(
            doc_role="index",
            sources=[
                {"source_id": "src-1", "uri": "https://github.com/o/r/blob/main/a.md", "type": "github", "label": "a.md", "status": "valid"},
                {"source_id": "src-2", "uri": "https://github.com/o/r/blob/main/b.md", "type": "github", "label": "b.md", "status": "valid"},
                {"source_id": "src-3", "uri": "https://github.com/o/r/blob/main/c.md", "type": "github", "label": "c.md", "status": "valid"},
            ],
            bundle_highlights=[
                {"source_id": "src-1", "headline": "A", "reason_to_read": "r1", "priority": "primary"},
                {"source_id": "src-2", "headline": "B", "reason_to_read": "r2", "priority": "important"},
                {"source_id": "src-3", "headline": "C", "reason_to_read": "r3", "priority": "supporting"},
            ],
        )
        repo = _make_entity_repo()
        repo.get_by_id = AsyncMock(return_value=existing)
        svc = _make_service(entity_repo=repo)

        result = await svc.upsert_document({
            "id": "doc-test-1",
            "linked_entity_ids": ["parent-1"],
            "add_source": {
                "uri": "https://github.com/owner/repo/blob/main/docs/new.md",
                "type": "github",
                "label": "new.md",
                "doc_type": "PLAN",
            },
        })

        highlight_suggestion = next(
            suggestion for suggestion in getattr(result, "_bundle_suggestions", [])
            if isinstance(suggestion, dict) and suggestion.get("type") == "bundle_highlights_suggestion"
        )
        assert len(highlight_suggestion["items"]) == 1
        assert highlight_suggestion["items"][0]["headline"] == "new.md"
        assert highlight_suggestion["items"][0]["priority"] == "important"

    @pytest.mark.asyncio
    async def test_document_bundle_write_does_not_call_governance_ai(self):
        class ExplodingGovernanceAI:
            def infer_all(self, entity_data, existing_entities, unlinked_docs):
                raise AssertionError("bundle path should not call GovernanceAI")

        existing = _make_doc_entity(doc_role="index")
        repo = _make_entity_repo()
        repo.get_by_id = AsyncMock(return_value=existing)
        svc = _make_service(entity_repo=repo)
        svc._governance_ai = ExplodingGovernanceAI()

        result = await svc.upsert_document({
            "id": "doc-test-1",
            "linked_entity_ids": ["parent-1"],
            "add_source": {
                "uri": "https://github.com/owner/repo/blob/main/docs/new.md",
                "type": "github",
                "label": "new.md",
                "doc_type": "SPEC",
            },
        })

        assert len(result.sources) == 2


class TestUpdateSource:
    @pytest.mark.asyncio
    async def test_update_source_by_source_id(self):
        """Can update a specific source by source_id."""
        existing = _make_doc_entity(doc_role="index")
        repo = _make_entity_repo()
        repo.get_by_id = AsyncMock(return_value=existing)
        svc = _make_service(entity_repo=repo)

        result = await svc.upsert_document({
            "id": "doc-test-1",
            "linked_entity_ids": ["parent-1"],
            "update_source": {
                "source_id": "src-1",
                "label": "updated-label.md",
                "note": "Updated note",
            },
        })
        assert result.sources[0]["label"] == "updated-label.md"
        assert result.sources[0]["note"] == "Updated note"

    @pytest.mark.asyncio
    async def test_update_source_not_found(self):
        """Updating a non-existent source_id raises error."""
        existing = _make_doc_entity()
        repo = _make_entity_repo()
        repo.get_by_id = AsyncMock(return_value=existing)
        svc = _make_service(entity_repo=repo)

        with pytest.raises(ValueError, match="not found"):
            await svc.upsert_document({
                "id": "doc-test-1",
                "linked_entity_ids": ["parent-1"],
                "update_source": {
                    "source_id": "nonexistent",
                    "label": "new-label",
                },
            })

    @pytest.mark.asyncio
    async def test_update_source_requires_source_id(self):
        """update_source without source_id raises error."""
        existing = _make_doc_entity()
        repo = _make_entity_repo()
        repo.get_by_id = AsyncMock(return_value=existing)
        svc = _make_service(entity_repo=repo)

        with pytest.raises(ValueError, match="requires source_id"):
            await svc.upsert_document({
                "id": "doc-test-1",
                "linked_entity_ids": ["parent-1"],
                "update_source": {"label": "new-label"},
            })


class TestRemoveSource:
    @pytest.mark.asyncio
    async def test_remove_source_from_index(self):
        """Can remove a source from index doc (when >1 sources exist)."""
        existing = _make_doc_entity(
            doc_role="index",
            sources=[
                {"source_id": "src-1", "uri": "https://github.com/o/r/blob/main/a.md", "type": "github", "label": "a.md", "status": "valid"},
                {"source_id": "src-2", "uri": "https://github.com/o/r/blob/main/b.md", "type": "github", "label": "b.md", "status": "valid"},
            ],
        )
        repo = _make_entity_repo()
        repo.get_by_id = AsyncMock(return_value=existing)
        svc = _make_service(entity_repo=repo)

        result = await svc.upsert_document({
            "id": "doc-test-1",
            "linked_entity_ids": ["parent-1"],
            "remove_source": {"source_id": "src-1"},
        })
        assert len(result.sources) == 1
        assert result.sources[0]["source_id"] == "src-2"

    @pytest.mark.asyncio
    async def test_remove_last_source_rejected(self):
        """Cannot remove the last source."""
        existing = _make_doc_entity(doc_role="index")
        repo = _make_entity_repo()
        repo.get_by_id = AsyncMock(return_value=existing)
        svc = _make_service(entity_repo=repo)

        with pytest.raises(ValueError, match="不可移除最後一個"):
            await svc.upsert_document({
                "id": "doc-test-1",
                "linked_entity_ids": ["parent-1"],
                "remove_source": {"source_id": "src-1"},
            })

    @pytest.mark.asyncio
    async def test_remove_from_single_rejected(self):
        """Cannot remove source from single doc entity."""
        existing = _make_doc_entity(doc_role="single",
            sources=[
                {"source_id": "src-1", "uri": "https://github.com/o/r/blob/main/a.md", "type": "github", "label": "a.md", "status": "valid"},
                {"source_id": "src-2", "uri": "https://github.com/o/r/blob/main/b.md", "type": "github", "label": "b.md", "status": "valid"},
            ])
        repo = _make_entity_repo()
        repo.get_by_id = AsyncMock(return_value=existing)
        svc = _make_service(entity_repo=repo)

        with pytest.raises(ValueError, match="single doc entity 不支援 remove_source"):
            await svc.upsert_document({
                "id": "doc-test-1",
                "linked_entity_ids": ["parent-1"],
                "remove_source": {"source_id": "src-1"},
            })


class TestChangeSummary:
    @pytest.mark.asyncio
    async def test_change_summary_sets_timestamp(self):
        """Writing change_summary auto-sets summary_updated_at."""
        existing = _make_doc_entity()
        repo = _make_entity_repo()
        repo.get_by_id = AsyncMock(return_value=existing)
        svc = _make_service(entity_repo=repo)

        before = datetime.now(timezone.utc)
        result = await svc.upsert_document({
            "id": "doc-test-1",
            "linked_entity_ids": ["parent-1"],
            "change_summary": "Updated SPEC with new acceptance criteria",
        })
        assert result.change_summary == "Updated SPEC with new acceptance criteria"
        assert result.summary_updated_at is not None
        assert result.summary_updated_at >= before

    @pytest.mark.asyncio
    async def test_change_summary_preserved_on_other_updates(self):
        """Existing change_summary is preserved when updating other fields."""
        existing = _make_doc_entity(
            change_summary="Existing summary",
            summary_updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        repo = _make_entity_repo()
        repo.get_by_id = AsyncMock(return_value=existing)
        svc = _make_service(entity_repo=repo)

        result = await svc.upsert_document({
            "id": "doc-test-1",
            "linked_entity_ids": ["parent-1"],
            "summary": "Updated entity summary",
        })
        assert result.change_summary == "Existing summary"


class TestBundleHighlights:
    @pytest.mark.asyncio
    async def test_bundle_highlights_set_timestamp(self):
        existing = _make_doc_entity(doc_role="index")
        repo = _make_entity_repo()
        repo.get_by_id = AsyncMock(return_value=existing)
        svc = _make_service(entity_repo=repo)

        before = datetime.now(timezone.utc)
        result = await svc.upsert_document({
            "id": "doc-test-1",
            "linked_entity_ids": ["parent-1"],
            "bundle_highlights": [{
                "source_id": "src-1",
                "headline": "This is the SSOT",
                "reason_to_read": "Defines the main flow",
                "priority": "primary",
            }],
        })
        assert result.bundle_highlights[0]["headline"] == "This is the SSOT"
        assert result.highlights_updated_at is not None
        assert result.highlights_updated_at >= before

    @pytest.mark.asyncio
    async def test_bundle_highlights_preserved_on_other_updates(self):
        existing = _make_doc_entity(
            doc_role="index",
            bundle_highlights=[{
                "source_id": "src-1",
                "headline": "Existing",
                "reason_to_read": "Still important",
                "priority": "primary",
            }],
            highlights_updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        repo = _make_entity_repo()
        repo.get_by_id = AsyncMock(return_value=existing)
        svc = _make_service(entity_repo=repo)

        result = await svc.upsert_document({
            "id": "doc-test-1",
            "linked_entity_ids": ["parent-1"],
            "summary": "Updated summary only",
        })
        assert result.bundle_highlights[0]["headline"] == "Existing"

    @pytest.mark.asyncio
    async def test_index_without_bundle_highlights_generates_suggestion(self):
        existing = _make_doc_entity(doc_role="index")
        repo = _make_entity_repo()
        repo.get_by_id = AsyncMock(return_value=existing)
        svc = _make_service(entity_repo=repo)

        result = await svc.upsert_document({
            "id": "doc-test-1",
            "linked_entity_ids": ["parent-1"],
            "summary": "Updated summary only",
        })
        suggestions = getattr(result, "_bundle_suggestions", [])
        assert any("bundle_highlights" in s for s in suggestions)

    @pytest.mark.asyncio
    async def test_bundle_highlights_require_existing_source(self):
        existing = _make_doc_entity(doc_role="index")
        repo = _make_entity_repo()
        repo.get_by_id = AsyncMock(return_value=existing)
        svc = _make_service(entity_repo=repo)

        with pytest.raises(ValueError, match="bundle_highlights source_id"):
            await svc.upsert_document({
                "id": "doc-test-1",
                "linked_entity_ids": ["parent-1"],
                "bundle_highlights": [{
                    "source_id": "missing-src",
                    "headline": "Bad highlight",
                    "reason_to_read": "Points to nowhere",
                    "priority": "primary",
                }],
            })


class TestSourceIdGeneration:
    @pytest.mark.asyncio
    async def test_legacy_sources_get_backfilled_ids(self):
        """Legacy sources without source_id get one assigned."""
        existing = _make_doc_entity(
            sources=[{"uri": "https://github.com/o/r/blob/main/a.md", "type": "github", "label": "a.md", "status": "valid"}]
        )
        repo = _make_entity_repo()
        repo.get_by_id = AsyncMock(return_value=existing)
        svc = _make_service(entity_repo=repo)

        result = await svc.upsert_document({
            "id": "doc-test-1",
            "linked_entity_ids": ["parent-1"],
            "summary": "trigger update",
        })
        assert result.sources[0].get("source_id")
        assert len(result.sources[0]["source_id"]) == 36  # UUID format
