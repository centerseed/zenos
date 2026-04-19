"""Tests for document title validation and auto-derivation in OntologyService.upsert_document().

Covers Task 10 (title validation / blacklist) and Task 30 (H1 extraction from GitHub .md).

DC-1: title="" → ValueError
DC-2: title="github" → ValueError with "source type" in message
DC-3: title="GitHub" (uppercase) → ValueError (case-insensitive)
DC-4: title="notion" → ValueError
DC-5: title=None + GitHub URL → auto-derived as filename
DC-6: title=None + non-GitHub source → ValueError
DC-7: title="正常標題" → accepted without error
DC-8: GitHub .md with H1 → title = H1 text
DC-9: GitHub .md without H1 → title = filename
DC-10: GitHub 404 → title = filename, sources[0]["status"] = "stale"
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from zenos.application.knowledge.ontology_service import OntologyService
from zenos.domain.knowledge import Entity, EntityType, Tags


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_parent_entity() -> Entity:
    return Entity(
        id="mod-1",
        name="Parent Module",
        type=EntityType.MODULE,
        summary="Parent document module",
        tags=Tags(what=["doc"], why="test", how="manual", who=["qa"]),
        parent_id="prod-1",
    )


def _mock_repos() -> dict:
    parent = _make_parent_entity()
    entity_repo = AsyncMock()
    entity_repo.get_by_id = AsyncMock(side_effect=lambda eid: {"mod-1": parent}.get(eid))
    entity_repo.get_by_name = AsyncMock(return_value=None)
    entity_repo.list_all = AsyncMock(return_value=[parent])
    entity_repo.upsert = AsyncMock(side_effect=lambda e: e)

    relationship_repo = AsyncMock()
    relationship_repo.add = AsyncMock(side_effect=lambda r: r)
    relationship_repo.list_by_entity = AsyncMock(return_value=[])
    relationship_repo.find_duplicate = AsyncMock(return_value=None)

    document_repo = AsyncMock()
    document_repo.list_by_entity = AsyncMock(return_value=[])
    document_repo.upsert = AsyncMock(side_effect=lambda d: d)

    protocol_repo = AsyncMock()
    protocol_repo.upsert = AsyncMock(side_effect=lambda p: p)

    blindspot_repo = AsyncMock()
    blindspot_repo.add = AsyncMock(side_effect=lambda b: b)

    return {
        "entity_repo": entity_repo,
        "relationship_repo": relationship_repo,
        "document_repo": document_repo,
        "protocol_repo": protocol_repo,
        "blindspot_repo": blindspot_repo,
    }


def _make_service(repos: dict | None = None, source_adapter=None) -> OntologyService:
    r = repos or _mock_repos()
    return OntologyService(**r, source_adapter=source_adapter)


def _base_doc_data(**overrides) -> dict:
    defaults = {
        "title": "Test Document",
        "summary": "A test summary",
        "tags": {"what": ["doc"], "why": "test", "how": "manual", "who": ["qa"]},
        "linked_entity_ids": ["mod-1"],
    }
    defaults.update(overrides)
    return defaults


_GITHUB_URL = "https://github.com/owner/repo/blob/main/docs/SPEC-xxx.md"


# ---------------------------------------------------------------------------
# Task 10: Title validation
# ---------------------------------------------------------------------------


class TestTitleValidation:

    async def test_empty_title_raises_value_error(self):
        """DC-1: title="" → ValueError (no auto-derive possible without GitHub source)."""
        svc = _make_service()
        with pytest.raises(ValueError, match="title"):
            await svc.upsert_document(_base_doc_data(title=""))

    async def test_bare_domain_github_raises(self):
        """DC-2: title='github' → ValueError with 'source type' message."""
        svc = _make_service()
        with pytest.raises(ValueError, match="source type"):
            await svc.upsert_document(_base_doc_data(title="github"))

    async def test_bare_domain_github_uppercase_raises(self):
        """DC-3: title='GitHub' (uppercase) → ValueError (case-insensitive)."""
        svc = _make_service()
        with pytest.raises(ValueError, match="source type"):
            await svc.upsert_document(_base_doc_data(title="GitHub"))

    async def test_bare_domain_notion_raises(self):
        """DC-4: title='notion' → ValueError."""
        svc = _make_service()
        with pytest.raises(ValueError, match="source type"):
            await svc.upsert_document(_base_doc_data(title="notion"))

    async def test_bare_domain_drive_raises(self):
        """title='drive' → ValueError."""
        svc = _make_service()
        with pytest.raises(ValueError, match="source type"):
            await svc.upsert_document(_base_doc_data(title="drive"))

    async def test_bare_domain_wiki_raises(self):
        """title='wiki' → ValueError."""
        svc = _make_service()
        with pytest.raises(ValueError, match="source type"):
            await svc.upsert_document(_base_doc_data(title="wiki"))

    async def test_normal_title_accepted(self):
        """DC-7: title='正常標題' → accepted without error."""
        svc = _make_service()
        result = await svc.upsert_document(_base_doc_data(title="正常標題"))
        assert result is not None

    async def test_empty_title_with_github_source_derives_filename(self):
        """DC-5: title=None + valid GitHub URL → title auto-set to filename."""
        # source_adapter returns no H1 content, falls back to filename
        mock_adapter = AsyncMock()
        mock_adapter.read_content = AsyncMock(return_value="No heading here.")
        svc = _make_service(source_adapter=mock_adapter)
        result = await svc.upsert_document(
            _base_doc_data(
                title="",
                summary="a summary",
                source={
                    "type": "github",
                    "uri": _GITHUB_URL,
                },
            )
        )
        entity = result if isinstance(result, Entity) else getattr(result, "entity", result)
        assert entity.name == "SPEC-xxx.md"

    async def test_empty_title_with_non_github_source_raises(self):
        """DC-6: title=None + non-GitHub source → ValueError."""
        svc = _make_service()
        with pytest.raises(ValueError, match="title"):
            await svc.upsert_document(
                _base_doc_data(
                    title="",
                    source={"type": "notion", "uri": "https://www.notion.so/page-abc12345678901234567890123456789"},
                )
            )


# ---------------------------------------------------------------------------
# Task 30: H1 extraction from GitHub .md
# ---------------------------------------------------------------------------


class TestGitHubH1Extraction:

    async def test_md_with_h1_uses_h1_as_title(self):
        """DC-8: GitHub .md with H1 → title = H1 text."""
        md_content = "# My Spec Title\n\nSome body text."
        mock_adapter = AsyncMock()
        mock_adapter.read_content = AsyncMock(return_value=md_content)
        svc = _make_service(source_adapter=mock_adapter)

        result = await svc.upsert_document(
            _base_doc_data(
                title="",
                source={"type": "github", "uri": _GITHUB_URL},
            )
        )
        entity = result if isinstance(result, Entity) else getattr(result, "entity", result)
        assert entity.name == "My Spec Title"

    async def test_md_without_h1_uses_filename(self):
        """DC-9: GitHub .md without H1 → title = filename."""
        md_content = "## Second heading\n\nContent without H1."
        mock_adapter = AsyncMock()
        mock_adapter.read_content = AsyncMock(return_value=md_content)
        svc = _make_service(source_adapter=mock_adapter)

        result = await svc.upsert_document(
            _base_doc_data(
                title="",
                source={"type": "github", "uri": _GITHUB_URL},
            )
        )
        entity = result if isinstance(result, Entity) else getattr(result, "entity", result)
        assert entity.name == "SPEC-xxx.md"

    async def test_github_404_uses_filename_and_sets_stale(self):
        """DC-10: GitHub 404 → title = filename, sources[0]['status'] = 'stale'."""
        mock_adapter = AsyncMock()
        mock_adapter.read_content = AsyncMock(side_effect=FileNotFoundError("404"))
        svc = _make_service(source_adapter=mock_adapter)

        result = await svc.upsert_document(
            _base_doc_data(
                title="",
                source={"type": "github", "uri": _GITHUB_URL},
            )
        )
        entity = result if isinstance(result, Entity) else getattr(result, "entity", result)
        assert entity.name == "SPEC-xxx.md"
        assert entity.sources[0]["status"] == "stale"
