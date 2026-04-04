"""Tests for analyze(check_type="invalid_documents") — Tasks 20 & 40.

Tests the pure `detect_invalid_document_titles` function from domain.governance
directly (no DB required), verifying:

DC-5: analyze invalid_documents returns correct format
DC-6: empty list returned when no invalid entities (not an error)
DC-11: valid GitHub source → proposed_title + action="propose_title"
DC-12: no/invalid URL → action="auto_archive"
DC-13: other valid URL → action="manual_review"
"""

from __future__ import annotations

import pytest

from zenos.domain.governance import detect_invalid_document_titles
from zenos.domain.models import Entity, EntityType, Tags
from zenos.domain.source_uri_validator import GITHUB_BLOB_PATTERN


def _make_doc_entity(
    entity_id: str = "doc-001",
    name: str = "Valid Title",
    source_uri: str = "",
    parent_id: str | None = None,
) -> Entity:
    sources = [{"uri": source_uri, "type": "github", "status": "valid"}] if source_uri else []
    return Entity(
        id=entity_id,
        name=name,
        type=EntityType.DOCUMENT,
        summary="A summary",
        tags=Tags(what=["doc"], why="test", how="manual", who=[]),
        sources=sources,
        parent_id=parent_id,
    )


# ---------------------------------------------------------------------------
# DC-7 / DC-6: no invalid entities → empty list
# ---------------------------------------------------------------------------


class TestNoInvalidDocuments:

    def test_returns_empty_list_when_all_titles_valid(self):
        """DC-7: no invalid entities → empty list (not an error)."""
        entities = [
            _make_doc_entity("doc-1", "Product Spec"),
            _make_doc_entity("doc-2", "Engineering ADR"),
        ]
        result = detect_invalid_document_titles(entities)
        assert result == []

    def test_empty_entity_list_returns_empty(self):
        """Empty input → empty output."""
        assert detect_invalid_document_titles([]) == []


# ---------------------------------------------------------------------------
# DC-5: format of returned items
# ---------------------------------------------------------------------------


class TestInvalidDocumentFormat:

    def test_empty_title_detected(self):
        """DC-5: entity with empty title is detected and returned with correct keys."""
        entities = [_make_doc_entity("doc-1", "")]
        result = detect_invalid_document_titles(entities)
        assert len(result) == 1
        item = result[0]
        assert "entity_id" in item
        assert "current_title" in item
        assert "source_uri" in item
        assert "linked_entity_ids" in item
        assert item["entity_id"] == "doc-1"
        assert item["current_title"] == ""

    def test_bare_domain_github_detected(self):
        """DC-5: entity with title='github' is detected."""
        entities = [_make_doc_entity("doc-2", "github")]
        result = detect_invalid_document_titles(entities)
        assert len(result) == 1
        assert result[0]["current_title"] == "github"

    def test_bare_domain_case_insensitive(self):
        """Bare domain check is case-insensitive."""
        entities = [_make_doc_entity("doc-3", "GitHub")]
        result = detect_invalid_document_titles(entities)
        assert len(result) == 1

    def test_all_bare_domains_detected(self):
        """All five bare domain names are detected."""
        bare_names = ["github", "notion", "drive", "wiki", "confluence"]
        entities = [_make_doc_entity(f"doc-{i}", name) for i, name in enumerate(bare_names)]
        result = detect_invalid_document_titles(entities)
        assert len(result) == len(bare_names)

    def test_source_uri_included_in_result(self):
        """source_uri is correctly extracted from entity sources."""
        uri = "https://github.com/owner/repo/blob/main/README.md"
        entity = _make_doc_entity("doc-1", "github", source_uri=uri)
        result = detect_invalid_document_titles([entity])
        assert result[0]["source_uri"] == uri

    def test_parent_id_included_in_linked_entity_ids(self):
        """parent_id is included in linked_entity_ids."""
        entity = _make_doc_entity("doc-1", "", parent_id="parent-999")
        result = detect_invalid_document_titles([entity])
        assert "parent-999" in result[0]["linked_entity_ids"]

    def test_no_source_results_in_empty_uri(self):
        """Entity with no sources → source_uri is empty string."""
        entity = _make_doc_entity("doc-1", "")
        # entity has no sources by default when source_uri=""
        result = detect_invalid_document_titles([entity])
        assert result[0]["source_uri"] == ""


# ---------------------------------------------------------------------------
# Task 40 enrichment: proposed_title + action
# ---------------------------------------------------------------------------


def _enrich_with_action(items: list[dict]) -> list[dict]:
    """Replicate the Task 40 enrichment logic from tools.py analyze()."""
    for doc in items:
        source_uri = doc["source_uri"]
        if source_uri and GITHUB_BLOB_PATTERN.match(source_uri):
            from zenos.infrastructure.github_adapter import parse_github_url
            try:
                _, _, path, _ = parse_github_url(source_uri)
                proposed_title = path.rsplit("/", 1)[-1]
            except Exception:
                proposed_title = None
            doc["proposed_title"] = proposed_title
            doc["action"] = "propose_title"
        elif not source_uri or not source_uri.startswith("http"):
            doc["proposed_title"] = None
            doc["action"] = "auto_archive"
        else:
            doc["proposed_title"] = None
            doc["action"] = "manual_review"
    return items


class TestInvalidDocumentEnrichment:

    def test_github_blob_url_gives_propose_title_action(self):
        """DC-11: valid GitHub blob URL → proposed_title + action='propose_title'."""
        uri = "https://github.com/owner/repo/blob/main/docs/SPEC-abc.md"
        entity = _make_doc_entity("doc-1", "github", source_uri=uri)
        items = detect_invalid_document_titles([entity])
        enriched = _enrich_with_action(items)
        assert len(enriched) == 1
        assert enriched[0]["action"] == "propose_title"
        assert enriched[0]["proposed_title"] == "SPEC-abc.md"

    def test_no_source_uri_gives_auto_archive(self):
        """DC-12: no source URI → action='auto_archive'."""
        entity = _make_doc_entity("doc-1", "")
        items = detect_invalid_document_titles([entity])
        enriched = _enrich_with_action(items)
        assert enriched[0]["action"] == "auto_archive"
        assert enriched[0]["proposed_title"] is None

    def test_non_url_source_gives_auto_archive(self):
        """DC-12: non-http source_uri → action='auto_archive'."""
        entity = _make_doc_entity("doc-1", "", source_uri="relative/path/file.md")
        items = detect_invalid_document_titles([entity])
        enriched = _enrich_with_action(items)
        assert enriched[0]["action"] == "auto_archive"

    def test_other_valid_url_gives_manual_review(self):
        """DC-13: non-GitHub https URL → action='manual_review'."""
        entity = _make_doc_entity(
            "doc-1", "", source_uri="https://www.notion.so/some-page-abc12345678901234567890123456789"
        )
        items = detect_invalid_document_titles([entity])
        enriched = _enrich_with_action(items)
        assert enriched[0]["action"] == "manual_review"
        assert enriched[0]["proposed_title"] is None
