"""Tests for SourceService.read_source — UUID lookup and URI-based fallback."""

from __future__ import annotations

import pytest
from unittest.mock import patch

from zenos.application.knowledge.source_service import SourceService
from zenos.domain.knowledge import Entity, EntityStatus, Tags
from zenos.infrastructure.context import current_partner_id


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

def _make_entity(entity_id: str, uri: str) -> Entity:
    return Entity(
        id=entity_id,
        name="Test Doc",
        type="document",
        summary="A test document",
        tags=Tags(what=["test"], why="testing", how="unit", who=["dev"]),
        status=EntityStatus.ACTIVE,
        sources=[{"uri": uri, "label": "source", "type": "github"}],
    )


class _StubEntityRepo:
    """Minimal in-memory stub for EntityRepository."""

    def __init__(self, entities: list[Entity]) -> None:
        self._by_id = {e.id: e for e in entities if e.id}
        self._all = entities

    async def get_by_id(self, entity_id: str) -> Entity | None:
        return self._by_id.get(entity_id)

    async def list_all(self, type_filter: str | None = None) -> list[Entity]:
        if type_filter is None:
            return list(self._all)
        return [e for e in self._all if e.type == type_filter]

    # Unused protocol methods — provided to satisfy duck typing in tests
    async def get_by_name(self, name: str) -> Entity | None:
        return None

    async def upsert(self, entity: Entity) -> Entity:
        return entity

    async def list_unconfirmed(self) -> list[Entity]:
        return []

    async def list_by_parent(self, parent_id: str) -> list[Entity]:
        return []


class _StubSourceAdapter:
    """Returns a fixed string for any URI."""

    def __init__(self, content: str = "file content") -> None:
        self._content = content

    async def read_content(self, uri: str) -> str:
        return self._content


class _RaisingSourceAdapter:
    """Raises a fixed exception for any URI."""

    def __init__(self, exc: Exception) -> None:
        self._exc = exc

    async def read_content(self, uri: str) -> str:
        raise self._exc

    async def search_alternatives_for_uri(self, uri: str) -> list[str]:
        return []


# ---------------------------------------------------------------------------
# Tests: UUID lookup (existing happy path)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_read_source_by_uuid_succeeds():
    """UUID lookup path: entity found by ID, content returned."""
    entity = _make_entity("uuid-001", "centerseed/havital/cloud/api_service/docs/spec.md")
    repo = _StubEntityRepo([entity])
    adapter = _StubSourceAdapter("spec content")
    svc = SourceService(entity_repo=repo, source_adapter=adapter)

    result = await svc.read_source("uuid-001")

    assert result == "spec content"


# ---------------------------------------------------------------------------
# Tests: URI-based fallback
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_read_source_by_uri_fallback_succeeds():
    """URI fallback: UUID lookup returns None, then URI scan finds the entity."""
    uri = "centerseed/havital/cloud/api_service/docs/spec.md"
    entity = _make_entity("uuid-002", uri)
    repo = _StubEntityRepo([entity])
    adapter = _StubSourceAdapter("fallback content")
    svc = SourceService(entity_repo=repo, source_adapter=adapter)

    # Pass the GitHub URI as doc_id (no matching UUID)
    result = await svc.read_source(uri)

    assert result == "fallback content"


@pytest.mark.asyncio
async def test_read_source_uri_match_is_exact():
    """URI match must be exact — a similar but different URI does not match."""
    stored_uri = "centerseed/havital/cloud/api_service/docs/spec.md"
    entity = _make_entity("uuid-003", stored_uri)
    repo = _StubEntityRepo([entity])
    adapter = _StubSourceAdapter("some content")
    svc = SourceService(entity_repo=repo, source_adapter=adapter)

    with pytest.raises(ValueError, match="not found"):
        await svc.read_source("centerseed/havital/cloud/api_service/docs/OTHER.md")


@pytest.mark.asyncio
async def test_read_source_uri_strips_whitespace():
    """URI stored with leading/trailing whitespace is normalised before matching."""
    uri = "centerseed/havital/cloud/api_service/docs/spec.md"
    entity = _make_entity("uuid-004", f"  {uri}  ")
    repo = _StubEntityRepo([entity])
    adapter = _StubSourceAdapter("trimmed content")
    svc = SourceService(entity_repo=repo, source_adapter=adapter)

    result = await svc.read_source(uri)

    assert result == "trimmed content"


# ---------------------------------------------------------------------------
# Tests: not-found raises ValueError (no silent failure)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_read_source_not_found_raises_value_error():
    """Nonexistent ID raises ValueError — no silent failure."""
    repo = _StubEntityRepo([])
    adapter = _StubSourceAdapter()
    svc = SourceService(entity_repo=repo, source_adapter=adapter)

    with pytest.raises(ValueError, match="not found"):
        await svc.read_source("nonexistent-id")


@pytest.mark.asyncio
async def test_read_source_uri_not_in_any_entity_raises_value_error():
    """URI that matches no entity also raises ValueError."""
    entity = _make_entity("uuid-005", "centerseed/havital/other/path.md")
    repo = _StubEntityRepo([entity])
    adapter = _StubSourceAdapter()
    svc = SourceService(entity_repo=repo, source_adapter=adapter)

    with pytest.raises(ValueError, match="not found"):
        await svc.read_source("centerseed/havital/no-match/path.md")


# ---------------------------------------------------------------------------
# Tests: entity with no sources still raises ValueError
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_read_source_entity_with_no_sources_raises():
    """Entity found by UUID but with no sources raises ValueError."""
    entity = Entity(
        id="uuid-006",
        name="Empty Doc",
        type="document",
        summary="no source",
        tags=Tags(what=["t"], why="y", how="h", who=["w"]),
        sources=[],
    )
    repo = _StubEntityRepo([entity])
    adapter = _StubSourceAdapter()
    svc = SourceService(entity_repo=repo, source_adapter=adapter)

    with pytest.raises(ValueError):
        await svc.read_source("uuid-006")


# ---------------------------------------------------------------------------
# Tests: source_uri parameter overrides sources[0]
# ---------------------------------------------------------------------------


class _RecordingSourceAdapter:
    """Records which URI was read."""

    def __init__(self) -> None:
        self.read_uris: list[str] = []

    async def read_content(self, uri: str) -> str:
        self.read_uris.append(uri)
        return f"content of {uri}"


@pytest.mark.asyncio
async def test_read_source_with_source_uri_reads_specified_uri():
    """When source_uri is provided, read_source reads that URI instead of sources[0]."""
    entity = Entity(
        id="uuid-010",
        name="Multi Source Doc",
        type="document",
        summary="doc with multiple sources",
        tags=Tags(what=["test"], why="testing", how="unit", who=["dev"]),
        sources=[
            {"uri": "first-uri.md", "label": "primary", "type": "github"},
            {"uri": "second-uri.md", "label": "secondary", "type": "github"},
        ],
    )
    repo = _StubEntityRepo([entity])
    adapter = _RecordingSourceAdapter()
    svc = SourceService(entity_repo=repo, source_adapter=adapter)

    result = await svc.read_source("uuid-010", source_uri="second-uri.md")

    assert result == "content of second-uri.md"
    assert adapter.read_uris == ["second-uri.md"]


@pytest.mark.asyncio
async def test_read_source_without_source_uri_reads_first():
    """Without source_uri, read_source still reads sources[0] as before."""
    entity = Entity(
        id="uuid-011",
        name="Multi Source Doc",
        type="document",
        summary="doc with multiple sources",
        tags=Tags(what=["test"], why="testing", how="unit", who=["dev"]),
        sources=[
            {"uri": "first-uri.md", "label": "primary", "type": "github"},
            {"uri": "second-uri.md", "label": "secondary", "type": "github"},
        ],
    )
    repo = _StubEntityRepo([entity])
    adapter = _RecordingSourceAdapter()
    svc = SourceService(entity_repo=repo, source_adapter=adapter)

    result = await svc.read_source("uuid-011")

    assert result == "content of first-uri.md"
    assert adapter.read_uris == ["first-uri.md"]


@pytest.mark.asyncio
async def test_read_source_with_recovery_honors_source_status_alias():
    """Recovery path reads source_status when legacy status key is absent."""
    entity = Entity(
        id="uuid-012",
        name="Alias Status Doc",
        type="document",
        summary="doc with canonical source_status only",
        tags=Tags(what=["test"], why="testing", how="unit", who=["dev"]),
        sources=[
            {
                "source_id": "src-1",
                "uri": "missing.md",
                "label": "missing",
                "type": "github",
                "source_status": "unresolvable",
            }
        ],
    )
    repo = _StubEntityRepo([entity])
    adapter = _RaisingSourceAdapter(FileNotFoundError("gone"))
    svc = SourceService(entity_repo=repo, source_adapter=adapter)

    result = await svc.read_source_with_recovery("uuid-012")

    assert result == {"error": "ALREADY_UNRESOLVABLE"}


@pytest.mark.asyncio
async def test_read_source_with_snapshot_falls_back_to_uri_when_source_id_misses():
    """Snapshot reads should recover via source_uri when source_id cannot be matched."""
    entity = Entity(
        id="uuid-013",
        name="Snapshot Doc",
        type="document",
        summary="doc with snapshot",
        tags=Tags(what=["test"], why="testing", how="unit", who=["dev"]),
        sources=[
            {
                "uri": "docs/spec.md",
                "label": "primary",
                "type": "github",
                # Intentionally omit source_id to simulate legacy/current mismatch.
                "source_status": "valid",
            }
        ],
    )
    repo = _StubEntityRepo([entity])
    adapter = _StubSourceAdapter()
    svc = SourceService(entity_repo=repo, source_adapter=adapter)

    class _FakeConn:
        async def fetchrow(self, query, *args):
            if "SELECT primary_snapshot_revision_id" in query:
                return {"primary_snapshot_revision_id": "rev-1"}
            if "SELECT snapshot_bucket, snapshot_object_path" in query:
                return {
                    "snapshot_bucket": "bucket-1",
                    "snapshot_object_path": "snapshots/rev-1.md",
                }
            raise AssertionError(f"Unexpected query: {query}")

    class _Acquire:
        async def __aenter__(self):
            return _FakeConn()

        async def __aexit__(self, exc_type, exc, tb):
            return False

    class _FakePool:
        def acquire(self):
            return _Acquire()

    token = current_partner_id.set("partner-1")
    try:
        with (
            patch("zenos.infrastructure.sql_common.get_pool", return_value=_FakePool()),
            patch("zenos.infrastructure.gcs_client.download_blob", return_value=(b"# snapshot", "text/markdown")),
        ):
            result = await svc.read_source_with_snapshot(
                "uuid-013",
                source_id="src-missing",
                source_uri="docs/spec.md",
            )
    finally:
        current_partner_id.reset(token)

    assert result["content"] == "# snapshot"
    assert result["content_type"] == "full"
