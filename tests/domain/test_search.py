"""Tests for in-memory keyword search."""

from __future__ import annotations

from datetime import datetime

from zenos.domain.models import (
    Document,
    DocumentTags,
    Entity,
    EntityStatus,
    EntityType,
    Gap,
    Protocol,
    Severity,
    Source,
    SourceType,
    Tags,
)
from zenos.domain.search import SearchResult, search_ontology, _tokenize, _score_match


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

def _entity(name: str, summary: str = "", what: str = "", who: str = "") -> Entity:
    return Entity(
        id=f"e-{name}",
        name=name,
        type=EntityType.MODULE,
        summary=summary or f"Summary of {name}",
        tags=Tags(what=what or name, why="testing", how="impl", who=who or "developer"),
        status=EntityStatus.ACTIVE,
        created_at=datetime(2026, 3, 1),
        updated_at=datetime(2026, 3, 1),
    )


def _document(title: str, what: list[str] | None = None, who: list[str] | None = None, summary: str = "") -> Document:
    return Document(
        id=f"d-{title}",
        title=title,
        source=Source(type=SourceType.GITHUB, uri=f"docs/{title}", adapter="git"),
        tags=DocumentTags(
            what=what or [title],
            why="docs",
            how="written",
            who=who or ["developer"],
        ),
        summary=summary or f"Summary of {title}",
        created_at=datetime(2026, 3, 1),
        updated_at=datetime(2026, 3, 1),
    )


def _protocol(entity_name: str, content: dict | None = None) -> Protocol:
    return Protocol(
        id=f"p-{entity_name}",
        entity_id=f"e-{entity_name}",
        entity_name=entity_name,
        content=content or {"what": "test module", "why": "test", "how": "impl", "who": "dev"},
        gaps=[Gap(description="missing docs", priority=Severity.YELLOW)],
        generated_at=datetime(2026, 3, 1),
        updated_at=datetime(2026, 3, 1),
    )


# ──────────────────────────────────────────────
# Tokenizer tests
# ──────────────────────────────────────────────

class TestTokenize:
    def test_basic(self):
        assert _tokenize("hello world") == ["hello", "world"]

    def test_mixed_separators(self):
        tokens = _tokenize("hello-world/foo_bar")
        assert "hello" in tokens
        assert "world" in tokens
        assert "foo" in tokens
        assert "bar" in tokens

    def test_chinese(self):
        tokens = _tokenize("訓練計畫系統")
        assert "訓練計畫系統" in tokens

    def test_empty(self):
        assert _tokenize("") == []
        assert _tokenize("   ") == []

    def test_case_insensitive(self):
        tokens = _tokenize("Hello WORLD")
        assert tokens == ["hello", "world"]


# ──────────────────────────────────────────────
# Score match tests
# ──────────────────────────────────────────────

class TestScoreMatch:
    def test_full_match(self):
        score = _score_match(["hello", "world"], "hello world")
        assert score > 0

    def test_partial_match(self):
        score = _score_match(["hello", "missing"], "hello world")
        assert 0 < score < 1.0

    def test_no_match(self):
        score = _score_match(["xyz"], "hello world")
        assert score == 0.0

    def test_empty_query(self):
        score = _score_match([], "hello world")
        assert score == 0.0

    def test_substring_bonus(self):
        score_with = _score_match(["hello", "world"], "this is hello world here")
        score_without = _score_match(["hello", "world"], "world and hello separately")
        assert score_with > score_without


# ──────────────────────────────────────────────
# search_ontology tests
# ──────────────────────────────────────────────

class TestSearchOntology:
    def test_empty_query(self):
        results = search_ontology("", [_entity("X")], [], [])
        assert results == []

    def test_entity_match_by_name(self):
        results = search_ontology("Rizo", [_entity("Rizo AI"), _entity("ACWR")], [], [])
        assert len(results) >= 1
        assert results[0].name == "Rizo AI"
        assert results[0].type == "entity"

    def test_document_match_by_title(self):
        results = search_ontology("spec", [], [_document("api-spec.md")], [])
        assert len(results) >= 1
        assert results[0].type == "document"

    def test_document_match_by_what_tag(self):
        doc = _document("readme.md", what=["training plan", "architecture"])
        results = search_ontology("training", [], [doc], [])
        assert len(results) >= 1

    def test_protocol_match(self):
        proto = _protocol("Paceriz")
        results = search_ontology("Paceriz", [], [], [proto])
        assert len(results) >= 1
        assert results[0].type == "protocol"

    def test_mixed_results_sorted_by_score(self):
        entity = _entity("Training Plan", summary="The training plan module")
        doc = _document("training-overview.md", what=["training", "plan"])
        proto = _protocol("Other Module")

        results = search_ontology("training plan", [entity], [doc], [proto])
        assert len(results) >= 2
        # Should be sorted by score descending
        for i in range(len(results) - 1):
            assert results[i].score >= results[i + 1].score

    def test_no_match_returns_empty(self):
        results = search_ontology(
            "xyznonexistent",
            [_entity("Foo")],
            [_document("bar.md")],
            [_protocol("baz")],
        )
        assert results == []

    def test_who_tag_match(self):
        doc = _document("guide.md", who=["marketing", "sales"])
        results = search_ontology("marketing", [], [doc], [])
        assert len(results) >= 1

    def test_summary_match(self):
        entity = _entity("Module X", summary="handles ACWR safety calculations")
        results = search_ontology("ACWR safety", [entity], [], [])
        assert len(results) >= 1

    def test_case_insensitive_search(self):
        entity = _entity("Rizo AI")
        results = search_ontology("rizo ai", [entity], [], [])
        assert len(results) >= 1

    def test_protocol_gap_match(self):
        proto = _protocol("TestModule")
        proto.gaps = [Gap(description="缺少非技術文件", priority=Severity.RED)]
        results = search_ontology("非技術", [], [], [proto])
        assert len(results) >= 1

    def test_result_fields(self):
        entity = _entity("Test", summary="Test summary")
        results = search_ontology("test", [entity], [], [])
        assert len(results) == 1
        r = results[0]
        assert r.type == "entity"
        assert r.id == "e-Test"
        assert r.name == "Test"
        assert r.summary == "Test summary"
        assert r.score > 0
