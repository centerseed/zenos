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

from zenos.domain.governance import (
    detect_document_bundle_governance_issues,
    detect_invalid_document_titles,
)
from zenos.domain.knowledge import Entity, EntityType, Tags
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


def _make_index_doc(
    entity_id: str = "doc-index",
    summary: str = (
        "This bundle answers document governance questions across several sources: "
        "primary source guide, formal spec, reference material, delivery notes, and reading boundaries."
    ),
    parent_id: str = "module-1",
    status: str = "current",
    bundle_highlights: list[dict] | None = None,
    source_count: int = 2,
    change_summary: str | None = "Updated bundle routing.",
) -> Entity:
    return Entity(
        id=entity_id,
        name="Document Governance Index",
        type=EntityType.DOCUMENT,
        summary=summary,
        tags=Tags(what=["doc"], why="test", how="manual", who=[]),
        parent_id=parent_id,
        status=status,
        doc_role="index",
        bundle_highlights=bundle_highlights if bundle_highlights is not None else [{
            "source_id": "src-1",
            "headline": "Primary",
            "reason_to_read": "Start here",
            "priority": "primary",
        }],
        sources=[
            {"source_id": f"src-{idx}", "uri": f"docs/source-{idx}.md"}
            for idx in range(1, source_count + 1)
        ],
        change_summary=change_summary,
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


class TestDocumentBundleGovernanceIssues:

    def test_valid_current_index_returns_no_bundle_issues(self):
        doc = _make_index_doc()

        result = detect_document_bundle_governance_issues([doc])

        assert result == []

    def test_index_missing_sources_is_red_issue(self):
        doc = _make_index_doc(bundle_highlights=[], source_count=0)

        result = detect_document_bundle_governance_issues([doc])

        assert result[0]["issue_type"] == "index_missing_sources"
        assert result[0]["severity"] == "red"
        assert result[0]["linked_entity_ids"] == ["module-1"]

    def test_index_missing_bundle_highlights_is_red_issue(self):
        doc = _make_index_doc(bundle_highlights=[], source_count=1)

        result = detect_document_bundle_governance_issues([doc])

        assert result[0]["issue_type"] == "index_missing_bundle_highlights"
        assert result[0]["severity"] == "red"
        assert result[0]["linked_entity_ids"] == ["module-1"]

    def test_index_summary_must_be_retrieval_map(self):
        doc = _make_index_doc(summary="Short.", source_count=2)

        result = detect_document_bundle_governance_issues([doc])
        issue_types = {item["issue_type"] for item in result}

        assert "index_summary_not_retrieval_map" in issue_types

    def test_index_summary_plain_prose_is_not_retrieval_map(self):
        doc = _make_index_doc(
            summary=(
                "決策：在 Magic Link 登入成功後提供 SSO 綁定選項；放寬 Admin 權限，"
                "允許刪除 active/suspended 狀態的正式用戶，並處理相關 Task assignee 關聯。"
            ),
            source_count=1,
        )

        result = detect_document_bundle_governance_issues([doc])
        issue_types = {item["issue_type"] for item in result}

        assert "index_summary_not_retrieval_map" in issue_types

    def test_index_summary_generic_template_is_not_retrieval_map(self):
        doc = _make_index_doc(
            summary=(
                "這個 L3 index 是「Dashboard v1 完整規格」的文件群 retrieval map。"
                "它用來回答此主題有哪些正式文件、哪份 source 應先讀、以及各 source 的閱讀邊界。"
                "Primary source 是 SPEC-dashboard-v1.md；目前登錄 source 包含 SPEC-dashboard-v1.md。"
                "Agent 找到對應 L2 後，應先讀本 summary 與 bundle_highlights，再依任務選讀 source。"
            ),
            source_count=1,
        )

        result = detect_document_bundle_governance_issues([doc])
        issue_types = {item["issue_type"] for item in result}

        assert "index_summary_not_retrieval_map" in issue_types

    def test_multi_source_index_requires_change_summary(self):
        doc = _make_index_doc(source_count=2, change_summary=None)

        result = detect_document_bundle_governance_issues([doc])
        issue_types = {item["issue_type"] for item in result}

        assert "index_missing_change_summary" in issue_types

    def test_l2_with_only_single_doc_requires_current_index(self):
        doc = _make_doc_entity("doc-single", "Spec", parent_id="module-1")
        doc.doc_role = "single"
        doc.status = "current"

        result = detect_document_bundle_governance_issues([doc])

        assert result == [{
            "issue_type": "l2_missing_current_index_document",
            "linked_entity_id": "module-1",
            "document_ids": ["doc-single"],
            "severity": "red",
            "suggested_action": "將此 L2 的正式文件收斂到 current doc_role=index 文件，並補 summary / bundle_highlights。",
        }]

    def test_draft_index_is_not_reported_as_governance_failure(self):
        doc = _make_index_doc(status="draft", bundle_highlights=[], change_summary=None)

        result = detect_document_bundle_governance_issues([doc])

        assert result == []

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
