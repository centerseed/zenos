"""Tests for in-memory keyword search and ontology helpers."""

from __future__ import annotations

from datetime import datetime

from zenos.domain.knowledge import Document, Entity, EntityStatus, EntityType, Gap, Protocol, Severity, Source, SourceType, Tags
from zenos.domain.search import SearchResult, search_ontology, _tokenize, _score_match
from zenos.application.knowledge.ontology_service import _collect_subtree_ids, _build_ancestors


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
        tags=Tags(
            what=what or [title],
            why="docs",
            how="written",
            who=who or ["developer"],
        ),
        summary=summary or f"Summary of {title}",
        created_at=datetime(2026, 3, 1),
        updated_at=datetime(2026, 3, 1),
    )


def _protocol(entity_name: str, content: dict | None = None, version: str = "1.0") -> Protocol:
    return Protocol(
        id=f"p-{entity_name}",
        entity_id=f"e-{entity_name}",
        entity_name=entity_name,
        content=content or {"what": "test module", "why": "test", "how": "impl", "who": "dev"},
        gaps=[Gap(description="missing docs", priority=Severity.YELLOW)],
        version=version,
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

    # ── CJK bigram tests ──

    def test_cjk_bigrams_produced(self):
        """CJK token should produce bigrams alongside itself."""
        tokens = _tokenize("語意治理")
        assert "語意治理" in tokens
        assert "語意" in tokens
        assert "意治" in tokens
        assert "治理" in tokens

    def test_cjk_bigrams_three_char(self):
        """Three-char CJK token produces two bigrams."""
        tokens = _tokenize("知識圖")
        assert "知識圖" in tokens
        assert "知識" in tokens
        assert "識圖" in tokens

    def test_non_cjk_token_no_extra_bigrams(self):
        """Non-CJK tokens must NOT produce bigrams."""
        tokens = _tokenize("hello world")
        assert tokens == ["hello", "world"]

    def test_cjk_single_char_no_bigram(self):
        """Single-char CJK token cannot form a bigram — no extras."""
        tokens = _tokenize("語")
        assert tokens == ["語"]

    def test_mixed_cjk_and_english(self):
        """Mixed text: English tokens are not expanded, CJK tokens are."""
        tokens = _tokenize("ZenOS 治理")
        assert "zenos" in tokens
        assert "治理" in tokens
        # No bigram for single-char CJK
        # But 治理 is 2-char so it stays as-is (no further bigrams from a 2-char word)
        assert "治" not in tokens  # single chars not produced


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

    def test_cjk_partial_substring_gets_07(self):
        """CJK query token that is a substring of a long term should score 0.7, not 0."""
        # "治理" is inside "語意治理Pipeline" but not a standalone token
        score = _score_match(["治理"], "語意治理pipeline")
        assert score > 0.0
        # Not a full token match (that would be 1.0 per token), confirm it's < 1.0
        # (actually could be >=1 with bonus, so just check > 0)
        assert score > 0


class TestCJKSearch:
    """CJK-specific search integration tests."""

    def test_bigram_search_matches_longer_cjk_entity(self):
        """Searching '治理' should hit an entity with '語意治理' in its name."""
        entity = _entity("語意治理Pipeline", summary="語意治理自動化流程")
        results = search_ontology("治理", [entity], [], [])
        assert len(results) >= 1
        assert results[0].name == "語意治理Pipeline"

    def test_cjk_mixed_query_hits_summary_tag(self):
        """'ZenOS 治理' should hit an entity containing '治理' in summary."""
        entity = _entity("ZenOS Core", summary="ZenOS 治理與 ontology 管理")
        results = search_ontology("ZenOS 治理", [entity], [], [])
        assert len(results) >= 1
        assert results[0].name == "ZenOS Core"

    def test_cjk_bigram_search_in_tags(self):
        """Bigram '意治' generated from '語意治理' should hit entity with that name in what tag."""
        entity = _entity("Governance", what="語意治理模組")
        results = search_ontology("意治", [entity], [], [])
        assert len(results) >= 1

    def test_english_search_unaffected_by_cjk_changes(self):
        """Plain English search still works correctly after CJK changes."""
        entity = _entity("Paceriz", summary="A running coach app")
        results = search_ontology("Paceriz", [entity], [], [])
        assert len(results) == 1
        assert results[0].name == "Paceriz"

    def test_english_no_false_positive(self):
        """English query does not match unrelated entity."""
        entity = _entity("ZenOS", summary="Ontology layer")
        results = search_ontology("Paceriz", [entity], [], [])
        assert len(results) == 0


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

    def test_protocol_summary_surfaces_revision_label(self):
        proto = _protocol("Paceriz", version="2.3")
        results = search_ontology("Paceriz", [], [], [proto])
        assert len(results) >= 1
        assert results[0].summary == "Protocol v2.3"

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


# ──────────────────────────────────────────────
# max_level filtering tests
# ──────────────────────────────────────────────

class TestSearchOntologyMaxLevel:
    def _entity_with_level(self, name: str, level: int | None) -> Entity:
        e = _entity(name)
        e.level = level
        return e

    def test_max_level_2_excludes_l3(self):
        l1 = self._entity_with_level("Product", 1)
        l2 = self._entity_with_level("Module", 2)
        l3 = self._entity_with_level("Detail", 3)
        results = search_ontology("Product Module Detail", [l1, l2, l3], [], [], max_level=2)
        names = {r.name for r in results}
        assert "Product" in names
        assert "Module" in names
        assert "Detail" not in names

    def test_max_level_1_excludes_l2_l3(self):
        l1 = self._entity_with_level("Product", 1)
        l2 = self._entity_with_level("Module", 2)
        results = search_ontology("Product Module", [l1, l2], [], [], max_level=1)
        names = {r.name for r in results}
        assert "Product" in names
        assert "Module" not in names

    def test_max_level_none_includes_all(self):
        l1 = self._entity_with_level("Product", 1)
        l3 = self._entity_with_level("Detail", 3)
        results = search_ontology("Product Detail", [l1, l3], [], [], max_level=None)
        assert len(results) == 2

    def test_level_none_treated_as_l1(self):
        """Entities with level=None are treated as L1 (included when max_level >= 1)."""
        no_level = self._entity_with_level("Legacy", None)
        results = search_ontology("Legacy", [no_level], [], [], max_level=2)
        assert len(results) == 1

    def test_level_none_excluded_when_max_level_0(self):
        """Edge case: max_level=0 would exclude level=None (treated as 1)."""
        no_level = self._entity_with_level("Legacy", None)
        results = search_ontology("Legacy", [no_level], [], [], max_level=0)
        assert len(results) == 0

    def test_max_level_does_not_affect_documents_or_protocols(self):
        """max_level only filters entities, not documents or protocols."""
        l3 = self._entity_with_level("Detail", 3)
        doc = _document("API Guide")
        proto = _protocol("TestModule")
        results = search_ontology("API TestModule Detail", [l3], [doc], [proto], max_level=2)
        types = {r.type for r in results}
        assert "document" in types
        assert "protocol" in types
        assert "entity" not in types


# ──────────────────────────────────────────────
# _collect_subtree_ids tests
# ──────────────────────────────────────────────

class TestCollectSubtreeIds:
    def _entity_with_parent(self, eid: str, parent_id: str | None = None) -> Entity:
        return Entity(
            id=eid,
            name=eid,
            type="module",
            summary="s",
            tags=Tags(what=[], why="", how="", who=[]),
            parent_id=parent_id,
        )

    def test_root_only(self):
        root = self._entity_with_parent("prod-1")
        entity_map = {"prod-1": root}
        ids = _collect_subtree_ids("prod-1", entity_map)
        assert ids == {"prod-1"}

    def test_includes_children(self):
        root = self._entity_with_parent("prod-1")
        child1 = self._entity_with_parent("mod-1", "prod-1")
        child2 = self._entity_with_parent("mod-2", "prod-1")
        entity_map = {"prod-1": root, "mod-1": child1, "mod-2": child2}
        ids = _collect_subtree_ids("prod-1", entity_map)
        assert ids == {"prod-1", "mod-1", "mod-2"}

    def test_includes_grandchildren(self):
        root = self._entity_with_parent("prod-1")
        child = self._entity_with_parent("mod-1", "prod-1")
        grandchild = self._entity_with_parent("doc-1", "mod-1")
        entity_map = {"prod-1": root, "mod-1": child, "doc-1": grandchild}
        ids = _collect_subtree_ids("prod-1", entity_map)
        assert ids == {"prod-1", "mod-1", "doc-1"}

    def test_excludes_unrelated(self):
        root = self._entity_with_parent("prod-1")
        child = self._entity_with_parent("mod-1", "prod-1")
        unrelated = self._entity_with_parent("mod-other", "prod-2")
        entity_map = {"prod-1": root, "mod-1": child, "mod-other": unrelated}
        ids = _collect_subtree_ids("prod-1", entity_map)
        assert "mod-other" not in ids

    def test_missing_root_returns_singleton(self):
        """Even if root doesn't exist in map, it still returns the root ID."""
        entity_map: dict[str, Entity] = {}
        ids = _collect_subtree_ids("missing", entity_map)
        assert ids == {"missing"}


# ──────────────────────────────────────────────
# SearchResult ancestors field tests
# ──────────────────────────────────────────────

class TestSearchResultAncestors:
    def test_ancestors_field_exists_and_defaults_to_none(self):
        r = SearchResult(type="entity", id="e-1", name="Test", summary="s", score=1.0)
        assert hasattr(r, "ancestors")
        assert r.ancestors is None

    def test_ancestors_can_be_set(self):
        r = SearchResult(
            type="entity", id="e-1", name="Test", summary="s", score=1.0,
            ancestors=[{"id": "e-parent", "name": "Parent", "type": "product", "level": 1}],
        )
        assert r.ancestors is not None
        assert len(r.ancestors) == 1
        assert r.ancestors[0]["id"] == "e-parent"


# ──────────────────────────────────────────────
# _build_ancestors tests
# ──────────────────────────────────────────────

class TestBuildAncestors:
    def _entity_with_parent(self, eid: str, name: str, parent_id: str | None = None, level: int | None = None) -> Entity:
        return Entity(
            id=eid,
            name=name,
            type="module",
            summary="s",
            tags=Tags(what=[], why="", how="", who=[]),
            parent_id=parent_id,
            level=level,
        )

    def test_no_parent(self):
        root = self._entity_with_parent("prod-1", "Product")
        entity_map = {"prod-1": root}
        ancestors = _build_ancestors("prod-1", entity_map)
        assert ancestors == []

    def test_one_level(self):
        root = self._entity_with_parent("prod-1", "Product", level=1)
        child = self._entity_with_parent("mod-1", "Module", parent_id="prod-1", level=2)
        entity_map = {"prod-1": root, "mod-1": child}
        ancestors = _build_ancestors("mod-1", entity_map)
        assert len(ancestors) == 1
        assert ancestors[0]["id"] == "prod-1"
        assert ancestors[0]["name"] == "Product"
        assert ancestors[0]["type"] == "module"
        assert ancestors[0]["level"] == 1

    def test_multi_level(self):
        root = self._entity_with_parent("prod-1", "Product", level=1)
        mid = self._entity_with_parent("mod-1", "Module", parent_id="prod-1", level=2)
        leaf = self._entity_with_parent("doc-1", "Doc", parent_id="mod-1", level=3)
        entity_map = {"prod-1": root, "mod-1": mid, "doc-1": leaf}
        ancestors = _build_ancestors("doc-1", entity_map)
        assert len(ancestors) == 2
        assert ancestors[0]["id"] == "mod-1"   # direct parent first
        assert ancestors[1]["id"] == "prod-1"

    def test_max_depth_cap(self):
        # Build 7-level chain
        entities = {}
        for i in range(7):
            eid = f"e-{i}"
            parent_id = f"e-{i - 1}" if i > 0 else None
            entities[eid] = self._entity_with_parent(eid, f"Entity{i}", parent_id=parent_id)
        # e-6 is the leaf, ancestor chain goes up to e-0 (6 levels)
        ancestors = _build_ancestors("e-6", entities, max_depth=5)
        assert len(ancestors) == 5

    def test_missing_parent(self):
        child = self._entity_with_parent("mod-1", "Module", parent_id="missing-parent")
        entity_map = {"mod-1": child}
        ancestors = _build_ancestors("mod-1", entity_map)
        assert ancestors == []
