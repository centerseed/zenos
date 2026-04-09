"""Tests for SourceService.read_source_with_recovery — dead link detection."""

from __future__ import annotations

import pytest

from zenos.application.source_service import SourceService
from zenos.domain.models import Entity, EntityStatus, SourceType, Tags
from zenos.infrastructure.github_adapter import GitHubAdapter


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


def _make_entity(
    entity_id: str,
    uri: str,
    source_type: str = "github",
    source_status: str = "valid",
    entity_status: str = "active",
) -> Entity:
    return Entity(
        id=entity_id,
        name="Test Doc",
        type="document",
        summary="A test document",
        tags=Tags(what=["test"], why="testing", how="unit", who=["dev"]),
        status=entity_status,
        sources=[{"uri": uri, "label": "source", "type": source_type, "status": source_status}],
    )


class _StubEntityRepo:
    """Minimal in-memory stub for EntityRepository."""

    def __init__(self, entities: list[Entity]) -> None:
        self._by_id = {e.id: e for e in entities if e.id}
        self._all = list(entities)
        # Track mutation calls for assertions
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
        # Also update in-memory so subsequent reads see the new status
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
    """Source adapter that returns content or raises configurable errors."""

    def __init__(self, content: str | None = None, raises: Exception | None = None) -> None:
        self._content = content
        self._raises = raises

    async def read_content(self, uri: str) -> str:
        if self._raises is not None:
            raise self._raises
        return self._content or "file content"


class _StubGitHubAdapter(GitHubAdapter):
    """GitHubAdapter stub that controls search_by_filename results without HTTP calls."""

    def __init__(self, candidates: list[str] | None = None) -> None:
        # Skip parent __init__ to avoid needing a real token
        self._token = ""
        self._headers = {}
        self._candidates = candidates or []
        self._raises = None

    async def read_content(self, uri: str) -> str:
        if self._raises is not None:
            raise self._raises
        raise FileNotFoundError(f"404: {uri}")

    async def search_by_filename(
        self, owner: str, repo: str, ref: str, filename: str
    ) -> list[str]:
        return list(self._candidates)


# ---------------------------------------------------------------------------
# Tests: happy path — content returned as-is
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_recovery_happy_path_returns_content():
    """Successful read returns {"content": ...}, no side effects."""
    entity = _make_entity("id-1", "https://github.com/owner/repo/blob/main/docs/spec.md")
    repo = _StubEntityRepo([entity])
    adapter = _StubSourceAdapter(content="spec content")
    svc = SourceService(entity_repo=repo, source_adapter=adapter)

    result = await svc.read_source_with_recovery("id-1")

    assert result == {"content": "spec content"}
    assert repo.source_status_updates == []
    assert repo.archived_ids == []


# ---------------------------------------------------------------------------
# Tests: entity not found
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_recovery_entity_not_found():
    """Returns NOT_FOUND error when entity doesn't exist."""
    repo = _StubEntityRepo([])
    adapter = _StubSourceAdapter()
    svc = SourceService(entity_repo=repo, source_adapter=adapter)

    result = await svc.read_source_with_recovery("nonexistent-id")

    assert result["error"] == "NOT_FOUND"


# ---------------------------------------------------------------------------
# Tests: ALREADY_UNRESOLVABLE short-circuit
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_recovery_already_unresolvable_returns_early():
    """If source_status is already 'unresolvable', returns ALREADY_UNRESOLVABLE without calling adapter."""
    entity = _make_entity(
        "id-2",
        "https://github.com/owner/repo/blob/main/docs/gone.md",
        source_status="unresolvable",
    )
    repo = _StubEntityRepo([entity])
    # Adapter would fail if called — ensures we short-circuit before it
    adapter = _StubSourceAdapter(raises=FileNotFoundError("should not be called"))
    svc = SourceService(entity_repo=repo, source_adapter=adapter)

    result = await svc.read_source_with_recovery("id-2")

    assert result == {"error": "ALREADY_UNRESOLVABLE"}
    assert repo.source_status_updates == []


# ---------------------------------------------------------------------------
# Tests: GitHub 404 — found alternative
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_recovery_github_404_found_alternative_sets_stale_and_proposed_uri():
    """GitHub 404 with same-filename match sets status=stale and returns proposed_uri."""
    uri = "https://github.com/owner/repo/blob/main/docs/spec.md"
    entity = _make_entity("id-3", uri, source_type="github")
    repo = _StubEntityRepo([entity])
    adapter = _StubGitHubAdapter(
        candidates=["https://github.com/owner/repo/blob/main/new-docs/spec.md"]
    )
    svc = SourceService(entity_repo=repo, source_adapter=adapter)

    result = await svc.read_source_with_recovery("id-3")

    assert result["error"] == "DEAD_LINK"
    assert result["source_type"] == SourceType.GITHUB
    assert result["source_status"] == "stale"
    assert result["suggested_action"] == "search_repo"
    assert result["proposed_uri"] == "https://github.com/owner/repo/blob/main/new-docs/spec.md"
    assert ("id-3", "stale", None) in repo.source_status_updates
    assert "id-3" not in repo.archived_ids


# ---------------------------------------------------------------------------
# Tests: GitHub 404 — no alternative found
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_recovery_github_404_no_alternative_sets_unresolvable_and_archives():
    """GitHub 404 with no same-filename match sets unresolvable and archives entity."""
    uri = "https://github.com/owner/repo/blob/main/docs/deleted.md"
    entity = _make_entity("id-4", uri, source_type="github")
    repo = _StubEntityRepo([entity])
    adapter = _StubGitHubAdapter(candidates=[])
    svc = SourceService(entity_repo=repo, source_adapter=adapter)

    result = await svc.read_source_with_recovery("id-4")

    assert result["error"] == "DEAD_LINK"
    assert result["source_type"] == SourceType.GITHUB
    assert result["source_status"] == "unresolvable"
    assert result["suggested_action"] == "mark_unresolvable"
    assert result["proposed_uri"] is None
    assert ("id-4", "unresolvable", None) in repo.source_status_updates
    assert "id-4" in repo.archived_ids


# ---------------------------------------------------------------------------
# Tests: GDrive 404 — always unresolvable
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_recovery_gdrive_404_sets_unresolvable_and_archives():
    """GDrive 404 always sets unresolvable and archives entity."""
    entity = _make_entity(
        "id-5",
        "https://drive.google.com/file/d/abc123/view",
        source_type="gdrive",
    )
    repo = _StubEntityRepo([entity])
    adapter = _StubSourceAdapter(raises=FileNotFoundError("gdrive 404"))
    svc = SourceService(entity_repo=repo, source_adapter=adapter)

    result = await svc.read_source_with_recovery("id-5")

    assert result["error"] == "DEAD_LINK"
    assert result["source_type"] == "gdrive"
    assert result["source_status"] == "unresolvable"
    assert result["suggested_action"] == "mark_unresolvable"
    assert ("id-5", "unresolvable", None) in repo.source_status_updates
    assert "id-5" in repo.archived_ids


# ---------------------------------------------------------------------------
# Tests: Notion 404 — stale, not archived
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_recovery_notion_404_sets_stale_not_archived():
    """Notion 404 sets stale and suggests check_permission; entity is NOT archived."""
    entity = _make_entity(
        "id-6",
        "https://www.notion.so/workspace/Page-abc123",
        source_type="notion",
    )
    repo = _StubEntityRepo([entity])
    adapter = _StubSourceAdapter(raises=FileNotFoundError("notion 404"))
    svc = SourceService(entity_repo=repo, source_adapter=adapter)

    result = await svc.read_source_with_recovery("id-6")

    assert result["error"] == "DEAD_LINK"
    assert result["source_type"] == "notion"
    assert result["source_status"] == "stale"
    assert result["suggested_action"] == "check_permission"
    assert ("id-6", "stale", None) in repo.source_status_updates
    assert "id-6" not in repo.archived_ids


# ---------------------------------------------------------------------------
# Tests: Wiki 404 — stale, not archived
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_recovery_wiki_404_sets_stale_not_archived():
    """Wiki 404 sets stale and suggests check_permission; entity is NOT archived."""
    entity = _make_entity(
        "id-7",
        "https://wiki.company.com/page/SomePage",
        source_type="wiki",
    )
    repo = _StubEntityRepo([entity])
    adapter = _StubSourceAdapter(raises=FileNotFoundError("wiki 404"))
    svc = SourceService(entity_repo=repo, source_adapter=adapter)

    result = await svc.read_source_with_recovery("id-7")

    assert result["error"] == "DEAD_LINK"
    assert result["source_type"] == "wiki"
    assert result["source_status"] == "stale"
    assert result["suggested_action"] == "check_permission"
    assert ("id-7", "stale", None) in repo.source_status_updates
    assert "id-7" not in repo.archived_ids


# ---------------------------------------------------------------------------
# Tests: PermissionError sets stale + check_permission for any source type
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_recovery_permission_error_sets_stale_check_permission():
    """PermissionError always sets stale + check_permission, regardless of source type."""
    entity = _make_entity(
        "id-8",
        "https://github.com/owner/repo/blob/main/private/doc.md",
        source_type="github",
    )
    repo = _StubEntityRepo([entity])
    adapter = _StubSourceAdapter(raises=PermissionError("access denied"))
    svc = SourceService(entity_repo=repo, source_adapter=adapter)

    result = await svc.read_source_with_recovery("id-8")

    assert result["error"] == "DEAD_LINK"
    assert result["source_status"] == "stale"
    assert result["suggested_action"] == "check_permission"
    assert ("id-8", "stale", None) in repo.source_status_updates
    assert "id-8" not in repo.archived_ids


# ---------------------------------------------------------------------------
# Tests: response structure contains required fields
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_recovery_dead_link_response_contains_required_fields():
    """DEAD_LINK response always contains source_type and suggested_action fields."""
    entity = _make_entity(
        "id-9",
        "https://drive.google.com/file/d/xyz/view",
        source_type="gdrive",
    )
    repo = _StubEntityRepo([entity])
    adapter = _StubSourceAdapter(raises=FileNotFoundError("404"))
    svc = SourceService(entity_repo=repo, source_adapter=adapter)

    result = await svc.read_source_with_recovery("id-9")

    assert "error" in result
    assert "source_type" in result
    assert "suggested_action" in result
    assert "source_status" in result


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

    async def search_alternatives_for_uri(self, uri: str) -> list[str]:
        return []


@pytest.mark.asyncio
async def test_recovery_with_source_uri_reads_specified_uri():
    """When source_uri is provided, read_source_with_recovery reads that URI."""
    entity = _make_entity("id-20", "https://github.com/owner/repo/blob/main/first.md")
    # Add a second source to the entity
    entity.sources.append({
        "uri": "https://github.com/owner/repo/blob/main/second.md",
        "label": "secondary",
        "type": "github",
        "status": "valid",
    })
    repo = _StubEntityRepo([entity])
    adapter = _RecordingSourceAdapter()
    svc = SourceService(entity_repo=repo, source_adapter=adapter)

    result = await svc.read_source_with_recovery(
        "id-20",
        source_uri="https://github.com/owner/repo/blob/main/second.md",
    )

    assert result == {"content": "content of https://github.com/owner/repo/blob/main/second.md"}
    assert adapter.read_uris == ["https://github.com/owner/repo/blob/main/second.md"]


@pytest.mark.asyncio
async def test_recovery_without_source_uri_reads_first():
    """Without source_uri, read_source_with_recovery still reads sources[0]."""
    entity = _make_entity("id-21", "https://github.com/owner/repo/blob/main/first.md")
    entity.sources.append({
        "uri": "https://github.com/owner/repo/blob/main/second.md",
        "label": "secondary",
        "type": "github",
        "status": "valid",
    })
    repo = _StubEntityRepo([entity])
    adapter = _RecordingSourceAdapter()
    svc = SourceService(entity_repo=repo, source_adapter=adapter)

    result = await svc.read_source_with_recovery("id-21")

    assert result == {"content": "content of https://github.com/owner/repo/blob/main/first.md"}
    assert adapter.read_uris == ["https://github.com/owner/repo/blob/main/first.md"]
