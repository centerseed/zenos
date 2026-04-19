"""Tests for source_uri validation in OntologyService.upsert_document().

Verifies that:
- Invalid source_uri raises ValueError before any DB write
- Valid source_uri results in sources[0] containing "status": "valid"
- Updating an existing document without providing source_uri skips validation
- Updating an existing document with a new source_uri validates the new URI

Uses in-memory mock repositories (no external DB required).
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from zenos.application.knowledge.ontology_service import OntologyService
from zenos.domain.knowledge import Entity, EntityType, Tags


# ---------------------------------------------------------------------------
# Mock repository factory (mirrors test_validation.py)
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


def _make_service(repos: dict | None = None) -> OntologyService:
    r = repos or _mock_repos()
    return OntologyService(**r)


def _base_doc_data(**overrides) -> dict:
    defaults = {
        "title": "Test Document",
        "summary": "A test summary",
        "tags": {"what": ["doc"], "why": "test", "how": "manual", "who": ["qa"]},
        "linked_entity_ids": ["mod-1"],
    }
    defaults.update(overrides)
    return defaults


# ---------------------------------------------------------------------------
# Criteria 1: relative path source_uri rejected, entity not written
# ---------------------------------------------------------------------------


class TestInvalidSourceUriRejected:

    async def test_github_relative_path_raises(self):
        """Criteria 1: relative path rejected, ValueError raised before DB write."""
        repos = _mock_repos()
        svc = _make_service(repos)
        with pytest.raises(ValueError, match="Invalid source URI"):
            await svc.upsert_document(
                _base_doc_data(
                    source={"type": "github", "uri": "docs/specs/file.md"}
                )
            )
        # Verify entity was NOT written to DB
        repos["entity_repo"].upsert.assert_not_called()

    async def test_notion_no_uuid_raises(self):
        """Criteria 3: Notion URL without UUID is rejected with clear message."""
        repos = _mock_repos()
        svc = _make_service(repos)
        with pytest.raises(ValueError, match="UUID"):
            await svc.upsert_document(
                _base_doc_data(
                    source={"type": "notion", "uri": "https://www.notion.so/title-only"}
                )
            )
        repos["entity_repo"].upsert.assert_not_called()

    async def test_gdrive_folder_url_raises(self):
        """Criteria 4: Google Drive folder URL is rejected."""
        repos = _mock_repos()
        svc = _make_service(repos)
        with pytest.raises(ValueError, match="Invalid source URI"):
            await svc.upsert_document(
                _base_doc_data(
                    source={
                        "type": "gdrive",
                        "uri": "https://drive.google.com/drive/folders/xyz",
                    }
                )
            )
        repos["entity_repo"].upsert.assert_not_called()

    async def test_wiki_no_https_raises(self):
        repos = _mock_repos()
        svc = _make_service(repos)
        with pytest.raises(ValueError, match="Invalid source URI"):
            await svc.upsert_document(
                _base_doc_data(
                    source={"type": "wiki", "uri": "wiki.example.com/page"}
                )
            )
        repos["entity_repo"].upsert.assert_not_called()


# ---------------------------------------------------------------------------
# Criteria 2: valid GitHub URL written with sources[0]["status"] == "valid"
# ---------------------------------------------------------------------------


class TestValidSourceUriAccepted:

    async def test_github_blob_url_written_with_status_valid(self):
        """Criteria 2: valid GitHub URL → entity written, sources[0] has status=valid."""
        repos = _mock_repos()
        svc = _make_service(repos)

        result = await svc.upsert_document(
            _base_doc_data(
                source={
                    "type": "github",
                    "uri": "https://github.com/owner/repo/blob/main/path/file.md",
                }
            )
        )

        assert result is not None
        entity = result if isinstance(result, Entity) else getattr(result, "entity", result)
        sources = entity.sources if hasattr(entity, "sources") else []
        assert len(sources) > 0, "Expected sources to be non-empty"
        assert sources[0].get("status") == "valid"

    async def test_notion_with_uuid_written_with_status_valid(self):
        repos = _mock_repos()
        svc = _make_service(repos)

        result = await svc.upsert_document(
            _base_doc_data(
                source={
                    "type": "notion",
                    "uri": "https://www.notion.so/My-Page-abc12345678901234567890123456789",
                }
            )
        )

        entity = result if isinstance(result, Entity) else getattr(result, "entity", result)
        sources = entity.sources if hasattr(entity, "sources") else []
        assert sources[0].get("status") == "valid"


# ---------------------------------------------------------------------------
# Criteria 5: update existing document
# ---------------------------------------------------------------------------


class TestUpdateExistingDocument:

    def _make_existing_entity(self, doc_id: str = "doc-001") -> Entity:
        return Entity(
            id=doc_id,
            name="Existing Doc",
            type=EntityType.DOCUMENT,
            summary="existing summary",
            tags=Tags(what=["doc"], why="test", how="manual", who=["qa"]),
            sources=[{"uri": "https://github.com/owner/repo/blob/main/old.md", "type": "github", "status": "valid"}],
        )

    async def test_update_without_source_uri_skips_validation(self):
        """Criteria 5a: updating summary without source → no validation, no error."""
        existing = self._make_existing_entity()
        repos = _mock_repos()
        repos["entity_repo"].get_by_id = AsyncMock(return_value=existing)
        repos["entity_repo"].list_all = AsyncMock(return_value=[existing])
        repos["entity_repo"].upsert = AsyncMock(side_effect=lambda e: e)
        svc = _make_service(repos)

        # Should not raise — no source_uri provided, only summary update
        result = await svc.upsert_document(
            {
                "id": "doc-001",
                "title": "Existing Doc",
                "summary": "updated summary",
                "linked_entity_ids": ["mod-1"],
            }
        )
        assert result is not None

    async def test_update_with_new_valid_source_uri_accepted(self):
        """Criteria 5b: updating with new valid source_uri → accepted, status=valid."""
        existing = self._make_existing_entity()
        repos = _mock_repos()
        parent = _make_parent_entity()
        repos["entity_repo"].get_by_id = AsyncMock(
            side_effect=lambda eid: {"doc-001": existing, "mod-1": parent}.get(eid)
        )
        repos["entity_repo"].list_all = AsyncMock(return_value=[existing])
        repos["entity_repo"].upsert = AsyncMock(side_effect=lambda e: e)
        svc = _make_service(repos)

        result = await svc.upsert_document(
            {
                "id": "doc-001",
                "title": "Existing Doc",
                "summary": "updated summary",
                "linked_entity_ids": ["mod-1"],
                "source": {
                    "type": "github",
                    "uri": "https://github.com/owner/repo/blob/main/new.md",
                },
            }
        )
        entity = result if isinstance(result, Entity) else getattr(result, "entity", result)
        sources = entity.sources if hasattr(entity, "sources") else []
        assert sources[0].get("status") == "valid"

    async def test_update_with_invalid_source_uri_raises(self):
        """Criteria 5c: updating with invalid source_uri → rejected."""
        existing = self._make_existing_entity()
        repos = _mock_repos()
        parent = _make_parent_entity()
        repos["entity_repo"].get_by_id = AsyncMock(
            side_effect=lambda eid: {"doc-001": existing, "mod-1": parent}.get(eid)
        )
        repos["entity_repo"].list_all = AsyncMock(return_value=[existing])
        repos["entity_repo"].upsert = AsyncMock(side_effect=lambda e: e)
        svc = _make_service(repos)

        with pytest.raises(ValueError, match="Invalid source URI"):
            await svc.upsert_document(
                {
                    "id": "doc-001",
                    "title": "Existing Doc",
                    "summary": "updated summary",
                    "linked_entity_ids": ["mod-1"],
                    "source": {
                        "type": "github",
                        "uri": "relative/path/file.md",
                    },
                }
            )
