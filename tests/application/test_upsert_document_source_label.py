"""Tests for upsert_document() source label resolution.

Verifies that the legacy source format (with adapter="github") does NOT result
in label="github". Instead, the label should be derived from:
  1. source_data.get("label") — explicit label in source dict
  2. data.get("title")        — document title as fallback
  3. existing_source.get("label", "") — existing source label as last resort

Bug: Previously the code used source_data.get("adapter", ...) which would
return "github" for all GitHub sources, making all external sources display
as "github" with no useful information.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from zenos.application.knowledge.ontology_service import OntologyService
from zenos.domain.knowledge import Entity, EntityType, Tags


# ---------------------------------------------------------------------------
# Mock repository factory
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


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestUpsertDocumentSourceLabel:

    async def test_legacy_adapter_github_uses_title_as_label(self):
        """When source has adapter="github" but no label, label should be the document title."""
        svc = _make_service()
        result = await svc.upsert_document({
            "title": "CLAUDE.md (Setup Guide)",
            "summary": "Setup guide document",
            "tags": {"what": ["doc"], "why": "guide", "how": "markdown", "who": ["dev"]},
            "linked_entity_ids": ["mod-1"],
            "source": {
                "type": "github",
                "uri": "https://github.com/org/repo/blob/main/CLAUDE.md",
                "adapter": "github",
            },
        })
        assert len(result.sources) == 1
        label = result.sources[0]["label"]
        assert label != "github", f"label should not be 'github', got: {label!r}"
        assert label == "CLAUDE.md (Setup Guide)"

    async def test_explicit_label_in_source_takes_priority(self):
        """When source has an explicit label, it should be used as-is."""
        svc = _make_service()
        result = await svc.upsert_document({
            "title": "Some Other Title",
            "summary": "Test document",
            "tags": {"what": ["doc"], "why": "test", "how": "markdown", "who": ["dev"]},
            "linked_entity_ids": ["mod-1"],
            "source": {
                "type": "github",
                "uri": "https://github.com/org/repo/blob/main/README.md",
                "label": "README",
            },
        })
        assert len(result.sources) == 1
        assert result.sources[0]["label"] == "README"

    async def test_no_source_data_produces_no_sources(self):
        """When no source dict is provided, sources list remains empty."""
        svc = _make_service()
        result = await svc.upsert_document({
            "title": "Untitled Doc",
            "summary": "No source",
            "tags": {"what": ["doc"], "why": "test", "how": "manual", "who": ["qa"]},
            "linked_entity_ids": ["mod-1"],
        })
        assert result.sources == []

    async def test_title_fallback_when_no_label_in_source(self):
        """When source has neither label nor adapter, title is used as fallback."""
        svc = _make_service()
        result = await svc.upsert_document({
            "title": "Architecture Decision Record",
            "summary": "ADR for database selection",
            "tags": {"what": ["adr"], "why": "decision", "how": "doc", "who": ["architect"]},
            "linked_entity_ids": ["mod-1"],
            "source": {
                "type": "github",
                "uri": "https://github.com/org/repo/blob/main/docs/adr-001.md",
            },
        })
        assert len(result.sources) == 1
        label = result.sources[0]["label"]
        assert label != "github"
        assert label == "Architecture Decision Record"
