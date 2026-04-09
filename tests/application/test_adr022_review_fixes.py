"""Tests for ADR-022 P1 review findings fixes.

Finding 1: Honor sources payload when creating document bundles
Finding 2: Index doc-type queries against stored source classifications
Finding 3: Update the selected source status instead of always touching index 0
Finding 4: Do not archive entire bundle because one source is unresolvable
"""

from __future__ import annotations

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock

from zenos.domain.models import Entity, EntityType, Tags, SourceType
from zenos.domain.search import search_ontology
from zenos.application.source_service import SourceService


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

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
    from zenos.application.ontology_service import OntologyService

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


def _make_index_entity(
    *,
    entity_id: str = "doc-idx-1",
    name: str = "Subscription Docs",
    sources: list[dict] | None = None,
) -> Entity:
    if sources is None:
        sources = [
            {
                "source_id": "src-a",
                "uri": "https://github.com/owner/repo/blob/main/docs/sub.md",
                "type": "github",
                "label": "sub.md",
                "doc_type": "SPEC",
                "status": "valid",
            },
            {
                "source_id": "src-b",
                "uri": "https://drive.google.com/file/d/abc/view",
                "type": "gdrive",
                "label": "decisions.pdf",
                "doc_type": "DECISION",
                "status": "valid",
            },
        ]
    return Entity(
        id=entity_id,
        name=name,
        type=EntityType.DOCUMENT,
        summary="Subscription management docs",
        tags=Tags(what=["subscription"], why="tracking", how="bundle", who=["dev"]),
        level=3,
        status="current",
        parent_id="parent-1",
        sources=sources,
        doc_role="index",
    )


class _StubEntityRepo:
    """Minimal in-memory stub for EntityRepository with source_id support."""

    def __init__(self, entities: list[Entity]) -> None:
        self._by_id = {e.id: e for e in entities if e.id}
        self._all = list(entities)
        self.source_status_updates: list[tuple[str, str, str | None]] = []
        self.archived_ids: list[str] = []

    async def get_by_id(self, entity_id: str) -> Entity | None:
        return self._by_id.get(entity_id)

    async def list_all(self, type_filter: str | None = None) -> list[Entity]:
        if type_filter is None:
            return list(self._all)
        return [e for e in self._all if e.type == type_filter]

    async def get_by_name(self, name: str) -> Entity | None:
        return None

    async def upsert(self, entity: Entity) -> Entity:
        return entity

    async def list_unconfirmed(self) -> list[Entity]:
        return []

    async def list_by_parent(self, parent_id: str) -> list[Entity]:
        return []

    async def update_source_status(self, entity_id: str, new_status: str, source_id: str | None = None) -> None:
        self.source_status_updates.append((entity_id, new_status, source_id))
        entity = self._by_id.get(entity_id)
        if entity and entity.sources:
            if source_id:
                for src in entity.sources:
                    if src.get("source_id") == source_id:
                        src["status"] = new_status
                        break
            else:
                entity.sources[0]["status"] = new_status

    async def archive_entity(self, entity_id: str) -> None:
        self.archived_ids.append(entity_id)
        entity = self._by_id.get(entity_id)
        if entity:
            entity.status = "archived"


class _StubSourceAdapter:
    def __init__(self, content: str | None = None, raises: Exception | None = None):
        self._content = content
        self._raises = raises

    async def read_content(self, uri: str) -> str:
        if self._raises is not None:
            raise self._raises
        return self._content or "file content"

    async def search_alternatives_for_uri(self, uri: str) -> list[str]:
        return []


# ===========================================================================
# Finding 1: Honor sources payload when creating document bundles
# ===========================================================================


class TestFinding1_SourcesPayload:
    @pytest.mark.asyncio
    async def test_plural_sources_payload_persisted(self):
        """When caller provides sources (plural), they are persisted as-is."""
        svc = _make_service()
        parent = Entity(
            id="parent-1", name="Parent", type="module",
            summary="Parent", tags=Tags(what=["x"], why="", how="", who=[""]),
            level=2,
        )
        svc._entities.get_by_id = AsyncMock(return_value=parent)

        result = await svc.upsert_document({
            "title": "Bundle Doc",
            "summary": "A document bundle",
            "tags": {"what": ["test"], "why": "testing", "how": "auto", "who": ["dev"]},
            "doc_role": "index",
            "linked_entity_ids": ["parent-1"],
            "sources": [
                {"uri": "https://github.com/o/r/blob/main/a.md", "type": "github", "label": "a.md", "doc_type": "SPEC"},
                {"uri": "https://github.com/o/r/blob/main/b.md", "type": "github", "label": "b.md", "doc_type": "DECISION"},
            ],
        })
        assert len(result.sources) == 2
        assert result.sources[0]["uri"] == "https://github.com/o/r/blob/main/a.md"
        assert result.sources[0]["doc_type"] == "SPEC"
        assert result.sources[1]["uri"] == "https://github.com/o/r/blob/main/b.md"
        assert result.sources[1]["doc_type"] == "DECISION"
        # Each source should have a generated source_id
        assert result.sources[0].get("source_id")
        assert result.sources[1].get("source_id")

    @pytest.mark.asyncio
    async def test_singular_source_still_works(self):
        """Legacy singular source field still works when sources is absent."""
        svc = _make_service()
        parent = Entity(
            id="parent-1", name="Parent", type="module",
            summary="Parent", tags=Tags(what=["x"], why="", how="", who=[""]),
            level=2,
        )
        svc._entities.get_by_id = AsyncMock(return_value=parent)

        result = await svc.upsert_document({
            "title": "Single Doc",
            "summary": "A single document",
            "tags": {"what": ["test"], "why": "testing", "how": "auto", "who": ["dev"]},
            "source": {"type": "github", "uri": "https://github.com/o/r/blob/main/single.md"},
            "linked_entity_ids": ["parent-1"],
        })
        assert len(result.sources) == 1
        assert result.sources[0]["uri"] == "https://github.com/o/r/blob/main/single.md"

    @pytest.mark.asyncio
    async def test_plural_sources_takes_priority_over_singular(self):
        """When both sources and source are present, sources (plural) wins."""
        svc = _make_service()
        parent = Entity(
            id="parent-1", name="Parent", type="module",
            summary="Parent", tags=Tags(what=["x"], why="", how="", who=[""]),
            level=2,
        )
        svc._entities.get_by_id = AsyncMock(return_value=parent)

        result = await svc.upsert_document({
            "title": "Both Fields",
            "summary": "Has both source and sources",
            "tags": {"what": ["test"], "why": "testing", "how": "auto", "who": ["dev"]},
            "source": {"type": "github", "uri": "https://github.com/o/r/blob/main/old.md"},
            "sources": [
                {"uri": "https://github.com/o/r/blob/main/new1.md", "type": "github"},
                {"uri": "https://github.com/o/r/blob/main/new2.md", "type": "github"},
            ],
            "doc_role": "index",
            "linked_entity_ids": ["parent-1"],
        })
        assert len(result.sources) == 2
        assert result.sources[0]["uri"] == "https://github.com/o/r/blob/main/new1.md"


# ===========================================================================
# Finding 2: Index doc-type queries against stored source classifications
# ===========================================================================


class TestFinding2_DocTypeSearch:
    def test_entity_with_source_doc_type_found_by_search(self):
        """Searching 'DECISION' finds an entity whose source has doc_type=DECISION."""
        entity = _make_index_entity()
        results = search_ontology("DECISION", [entity], [], [])
        assert len(results) >= 1
        assert results[0].id == "doc-idx-1"

    def test_entity_with_source_doc_type_spec_found(self):
        """Searching 'SPEC' finds an entity whose source has doc_type=SPEC."""
        entity = _make_index_entity()
        results = search_ontology("SPEC", [entity], [], [])
        assert len(results) >= 1
        assert results[0].id == "doc-idx-1"

    def test_entity_without_source_doc_type_not_found(self):
        """Searching 'GUIDE' does not find an entity with SPEC and DECISION sources."""
        entity = _make_index_entity()
        results = search_ontology("GUIDE", [entity], [], [])
        # Should not match (unless it coincidentally matches name/summary/tags)
        matching_ids = [r.id for r in results]
        assert "doc-idx-1" not in matching_ids

    def test_entity_with_empty_sources_still_searchable_by_name(self):
        """Entity with no sources can still be found by name."""
        entity = Entity(
            id="doc-empty",
            name="DECISION Board Notes",
            type=EntityType.DOCUMENT,
            summary="Notes",
            tags=Tags(what=["notes"], why="", how="", who=[]),
            sources=[],
        )
        results = search_ontology("DECISION", [entity], [], [])
        assert len(results) >= 1


# ===========================================================================
# Finding 3: Update the selected source status instead of always touching index 0
# ===========================================================================


class TestFinding3_TargetedSourceUpdate:
    @pytest.mark.asyncio
    async def test_permission_error_updates_correct_source(self):
        """PermissionError on source[1] should update source[1], not source[0]."""
        entity = _make_index_entity()
        repo = _StubEntityRepo([entity])
        adapter = _StubSourceAdapter(raises=PermissionError("access denied"))
        svc = SourceService(entity_repo=repo, source_adapter=adapter)

        # Read source_uri that matches source[1] (src-b)
        result = await svc.read_source_with_recovery(
            "doc-idx-1",
            source_uri="https://drive.google.com/file/d/abc/view",
        )

        assert result["error"] == "DEAD_LINK"
        assert result["source_status"] == "stale"
        # The update should target source_id "src-b", not None (which would hit index 0)
        assert ("doc-idx-1", "stale", "src-b") in repo.source_status_updates
        # source[0] should remain valid
        assert entity.sources[0]["status"] == "valid"

    @pytest.mark.asyncio
    async def test_404_updates_correct_source_not_first(self):
        """FileNotFoundError on source[1] should mark that source, not source[0]."""
        entity = _make_index_entity()
        repo = _StubEntityRepo([entity])
        adapter = _StubSourceAdapter(raises=FileNotFoundError("not found"))
        svc = SourceService(entity_repo=repo, source_adapter=adapter)

        result = await svc.read_source_with_recovery(
            "doc-idx-1",
            source_uri="https://drive.google.com/file/d/abc/view",
        )

        assert result["error"] == "DEAD_LINK"
        # gdrive 404 → unresolvable
        assert result["source_status"] == "unresolvable"
        assert ("doc-idx-1", "unresolvable", "src-b") in repo.source_status_updates
        # source[0] should remain valid
        assert entity.sources[0]["status"] == "valid"


# ===========================================================================
# Finding 4: Do not archive entire bundle because one source is unresolvable
# ===========================================================================


class TestFinding4_IndexArchiveProtection:
    @pytest.mark.asyncio
    async def test_index_not_archived_when_one_source_unresolvable(self):
        """Index doc should NOT be archived when only one of two sources is unresolvable."""
        entity = _make_index_entity()
        repo = _StubEntityRepo([entity])
        adapter = _StubSourceAdapter(raises=FileNotFoundError("gdrive 404"))
        svc = SourceService(entity_repo=repo, source_adapter=adapter)

        result = await svc.read_source_with_recovery(
            "doc-idx-1",
            source_uri="https://drive.google.com/file/d/abc/view",
        )

        assert result["error"] == "DEAD_LINK"
        assert result["source_status"] == "unresolvable"
        # Entity should NOT be archived because source[0] is still valid
        assert "doc-idx-1" not in repo.archived_ids

    @pytest.mark.asyncio
    async def test_index_archived_when_all_sources_unresolvable(self):
        """Index doc SHOULD be archived when all sources become unresolvable."""
        entity = _make_index_entity(sources=[
            {
                "source_id": "src-a",
                "uri": "https://github.com/o/r/blob/main/gone.md",
                "type": "github",
                "label": "gone.md",
                "status": "unresolvable",  # already unresolvable
            },
            {
                "source_id": "src-b",
                "uri": "https://drive.google.com/file/d/abc/view",
                "type": "gdrive",
                "label": "decisions.pdf",
                "status": "valid",  # will become unresolvable
            },
        ])
        repo = _StubEntityRepo([entity])
        adapter = _StubSourceAdapter(raises=FileNotFoundError("gdrive 404"))
        svc = SourceService(entity_repo=repo, source_adapter=adapter)

        result = await svc.read_source_with_recovery(
            "doc-idx-1",
            source_uri="https://drive.google.com/file/d/abc/view",
        )

        assert result["error"] == "DEAD_LINK"
        # After this call, src-b becomes unresolvable too — now all are unresolvable
        assert "doc-idx-1" in repo.archived_ids

    @pytest.mark.asyncio
    async def test_single_doc_still_archived_on_unresolvable(self):
        """Single (non-index) doc should still be archived as before."""
        entity = Entity(
            id="doc-single-1",
            name="Single Doc",
            type=EntityType.DOCUMENT,
            summary="A single document",
            tags=Tags(what=["test"], why="", how="", who=[]),
            sources=[{
                "source_id": "src-1",
                "uri": "https://drive.google.com/file/d/xyz/view",
                "type": "gdrive",
                "label": "file.pdf",
                "status": "valid",
            }],
            doc_role="single",
        )
        repo = _StubEntityRepo([entity])
        adapter = _StubSourceAdapter(raises=FileNotFoundError("gdrive 404"))
        svc = SourceService(entity_repo=repo, source_adapter=adapter)

        result = await svc.read_source_with_recovery("doc-single-1")

        assert result["error"] == "DEAD_LINK"
        assert result["source_status"] == "unresolvable"
        # Single doc should be archived
        assert "doc-single-1" in repo.archived_ids

    @pytest.mark.asyncio
    async def test_github_index_not_archived_when_one_source_unresolvable(self):
        """GitHub 404 with no alternative: index doc not archived if other source still valid."""
        entity = _make_index_entity(sources=[
            {
                "source_id": "src-a",
                "uri": "https://github.com/o/r/blob/main/valid.md",
                "type": "github",
                "label": "valid.md",
                "status": "valid",
            },
            {
                "source_id": "src-b",
                "uri": "https://github.com/o/r/blob/main/gone.md",
                "type": "github",
                "label": "gone.md",
                "status": "valid",
            },
        ])
        repo = _StubEntityRepo([entity])

        # Adapter that raises FileNotFoundError and returns no alternatives
        from zenos.infrastructure.github_adapter import GitHubAdapter

        class _StubGitHub(GitHubAdapter):
            def __init__(self):
                self._token = ""
                self._headers = {}
                self._raises = None

            async def read_content(self, uri: str) -> str:
                raise FileNotFoundError(f"404: {uri}")

            async def search_by_filename(self, owner, repo, ref, filename):
                return []

        svc = SourceService(entity_repo=repo, source_adapter=_StubGitHub())

        result = await svc.read_source_with_recovery(
            "doc-idx-1",
            source_uri="https://github.com/o/r/blob/main/gone.md",
        )

        assert result["error"] == "DEAD_LINK"
        assert result["source_status"] == "unresolvable"
        # Entity should NOT be archived — source[0] is still valid
        assert "doc-idx-1" not in repo.archived_ids
        # Only src-b should be marked unresolvable
        assert ("doc-idx-1", "unresolvable", "src-b") in repo.source_status_updates
