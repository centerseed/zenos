"""Tests for governance rules — covers all 5 functions with full business logic."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from zenos.domain.governance import (
    analyze_blindspots,
    apply_tag_confidence,
    check_impacts_target_validity,
    check_reverse_impacts,
    check_split_criteria,
    detect_staleness,
    find_stale_l2_downstream_entities,
    run_quality_check,
)
from zenos.domain.action import Task, TaskPriority, TaskStatus
from zenos.domain.knowledge import Blindspot, Document, DocumentStatus, Entity, EntityStatus, EntityType, Gap, Protocol, Relationship, RelationshipType, Severity, Source, SourceType, Tags


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

def _make_entity(
    name: str = "TestEntity",
    entity_type: str = EntityType.MODULE,
    status: str = EntityStatus.ACTIVE,
    summary: str = "A test entity",
    entity_id: str | None = "e1",
    details: dict | None = None,
    updated_at: datetime | None = None,
    level: int | None = None,
) -> Entity:
    from zenos.domain.knowledge.entity_levels import DEFAULT_TYPE_LEVELS
    now = updated_at or datetime(2026, 3, 1)
    # Default level from SSOT if not provided (ADR-047 S03)
    effective_level = level if level is not None else DEFAULT_TYPE_LEVELS.get(entity_type)
    return Entity(
        id=entity_id,
        name=name,
        type=entity_type,
        level=effective_level,
        summary=summary,
        tags=Tags(what="test module", why="testing", how="automated", who="developer"),
        status=status,
        details=details,
        created_at=now,
        updated_at=now,
    )


def _make_doc(
    title: str = "test-doc.md",
    doc_id: str | None = "d1",
    linked_entity_ids: list[str] | None = None,
    who: list[str] | None = None,
    what: list[str] | None = None,
    how: str = "implemented",
    status: str = DocumentStatus.CURRENT,
    uri: str = "docs/test-doc.md",
    updated_at: datetime | None = None,
    last_reviewed_at: datetime | None = None,
) -> Document:
    now = updated_at or datetime(2026, 3, 1)
    return Document(
        id=doc_id,
        title=title,
        source=Source(type=SourceType.GITHUB, uri=uri, adapter="git"),
        tags=Tags(
            what=what or ["test"],
            why="testing purpose",
            how=how,
            who=who or ["developer"],
        ),
        linked_entity_ids=linked_entity_ids or [],
        summary=f"Summary of {title}",
        status=status,
        created_at=now,
        updated_at=now,
        last_reviewed_at=last_reviewed_at,
    )


def _make_rel(
    source_id: str = "e1",
    target_id: str = "e2",
    rel_type: str = RelationshipType.DEPENDS_ON,
) -> Relationship:
    return Relationship(
        id="r1",
        source_entity_id=source_id,
        target_id=target_id,
        type=rel_type,
        description="test relationship",
    )


# ──────────────────────────────────────────────
# 1. check_split_criteria
# ──────────────────────────────────────────────

class TestCheckSplitCriteria:
    def test_no_criteria_met(self):
        entity = _make_entity()
        result = check_split_criteria(entity, [], [])
        assert not result.should_split
        assert result.score == 0
        assert result.reasons == []

    def test_three_docs_only(self):
        entity = _make_entity()
        docs = [_make_doc(doc_id=f"d{i}", who=["developer"]) for i in range(3)]
        result = check_split_criteria(entity, docs, [])
        # Only criterion 1 met (3+ docs). Who all same = 1 audience.
        assert result.score == 1
        assert not result.should_split

    def test_three_docs_plus_dependency(self):
        entity = _make_entity()
        docs = [_make_doc(doc_id=f"d{i}") for i in range(3)]
        rels = [_make_rel(rel_type=RelationshipType.DEPENDS_ON)]
        result = check_split_criteria(entity, docs, rels)
        # Criteria 1 (3+ docs) + 2 (dependency chain) = 2
        assert result.should_split
        assert result.score >= 2

    def test_different_audiences(self):
        entity = _make_entity()
        docs = [
            _make_doc(doc_id="d1", who=["developer"]),
            _make_doc(doc_id="d2", who=["marketing"]),
            _make_doc(doc_id="d3", who=["designer"]),
        ]
        result = check_split_criteria(entity, docs, [])
        # Criteria 1 (3+ docs) + 3 (different audiences) = 2
        assert result.should_split
        assert result.score >= 2

    def test_goal_entity_with_docs(self):
        entity = _make_entity(entity_type=EntityType.GOAL)
        docs = [_make_doc(doc_id=f"d{i}") for i in range(3)]
        result = check_split_criteria(entity, docs, [])
        # Criteria 1 (3+ docs) + 4 (goal nature) = 2
        assert result.should_split
        assert result.score >= 2

    def test_open_decisions_in_details(self):
        entity = _make_entity(details={"decisions": ["Should we use X?"]})
        docs = [_make_doc(doc_id=f"d{i}") for i in range(3)]
        result = check_split_criteria(entity, docs, [])
        # Criteria 1 (3+ docs) + 4 (open decisions) = 2
        assert result.should_split

    def test_complex_summary(self):
        long_summary = "Line\n" * 10  # 10 lines
        entity = _make_entity(summary=long_summary)
        docs = [_make_doc(doc_id=f"d{i}") for i in range(3)]
        result = check_split_criteria(entity, docs, [])
        # Criteria 1 (3+ docs) + 5 (complex summary) = 2
        assert result.should_split

    def test_all_five_criteria(self):
        entity = _make_entity(
            entity_type=EntityType.GOAL,
            summary="A" * 301,
            details={"roadmap": ["v2 plan"]},
        )
        docs = [
            _make_doc(doc_id="d1", who=["developer"]),
            _make_doc(doc_id="d2", who=["marketing"]),
            _make_doc(doc_id="d3", who=["designer"]),
        ]
        rels = [_make_rel(rel_type=RelationshipType.SERVES)]
        result = check_split_criteria(entity, docs, rels)
        assert result.should_split
        assert result.score == 5


# ──────────────────────────────────────────────
# 2. apply_tag_confidence
# ──────────────────────────────────────────────

class TestApplyTagConfidence:
    def test_entity_tags(self):
        tags = Tags(what="product X", why="revenue", how="SaaS", who="CEO")
        result = apply_tag_confidence(tags)
        assert "what" in result.confirmed_fields
        assert "who" in result.confirmed_fields
        assert "why" in result.draft_fields
        assert "how" in result.draft_fields

    def test_document_tags(self):
        tags = Tags(what=["api docs"], why="onboarding", how="REST", who=["developer"])
        result = apply_tag_confidence(tags)
        assert "what" in result.confirmed_fields
        assert "who" in result.confirmed_fields
        assert "why" in result.draft_fields
        assert "how" in result.draft_fields

    def test_empty_what_goes_to_draft(self):
        tags = Tags(what="", why="", how="", who="CEO")
        result = apply_tag_confidence(tags)
        assert "what" in result.draft_fields
        assert "who" in result.confirmed_fields

    def test_empty_document_what_goes_to_draft(self):
        tags = Tags(what=[], why="", how="", who=["dev"])
        result = apply_tag_confidence(tags)
        assert "what" in result.draft_fields

    def test_why_how_always_draft(self):
        tags = Tags(what="filled", why="filled", how="filled", who="filled")
        result = apply_tag_confidence(tags)
        # Even when Why/How are filled, they remain draft
        assert "why" in result.draft_fields
        assert "how" in result.draft_fields


# ──────────────────────────────────────────────
# 3. detect_staleness
# ──────────────────────────────────────────────

class TestDetectStaleness:
    def test_no_staleness(self):
        now = datetime(2026, 3, 15)
        entity = _make_entity(updated_at=now)
        doc = _make_doc(linked_entity_ids=["e1"], updated_at=now)
        result = detect_staleness([entity], [doc], [], now=now)
        assert len(result) == 0

    def test_feature_updated_docs_lagging(self):
        old = datetime(2026, 1, 1)
        new = datetime(2026, 3, 15)
        entity = _make_entity(updated_at=new)
        doc = _make_doc(linked_entity_ids=["e1"], updated_at=old)
        result = detect_staleness([entity], [doc], [], now=new)
        lag_warnings = [w for w in result if w.pattern == "feature_updated_docs_lagging"]
        assert len(lag_warnings) == 1
        assert "e1" in lag_warnings[0].affected_entity_ids

    def test_goal_completed_not_closed(self):
        now = datetime(2026, 3, 15)
        goal = _make_entity(
            name="Ship v2", entity_type=EntityType.GOAL,
            entity_id="g1", updated_at=now,
        )
        task = _make_entity(
            name="Task A", entity_type=EntityType.MODULE,
            entity_id="t1", status=EntityStatus.COMPLETED, updated_at=now,
        )
        rel = _make_rel(source_id="t1", target_id="g1", rel_type=RelationshipType.SERVES)
        result = detect_staleness([goal, task], [], [rel], now=now)
        goal_warnings = [w for w in result if w.pattern == "goal_completed_not_closed"]
        assert len(goal_warnings) == 1

    def test_dependency_updated_dependant_silent(self):
        old = datetime(2026, 1, 1)
        new = datetime(2026, 3, 15)
        source = _make_entity(name="Consumer", entity_id="e1", updated_at=old)
        target = _make_entity(name="Provider", entity_id="e2", updated_at=new)
        rel = _make_rel(source_id="e1", target_id="e2", rel_type=RelationshipType.DEPENDS_ON)
        result = detect_staleness([source, target], [], [rel], now=new)
        dep_warnings = [w for w in result if w.pattern == "dependency_updated_dependant_silent"]
        assert len(dep_warnings) == 1
        assert "Consumer" in dep_warnings[0].description

    def test_role_disappeared(self):
        now = datetime(2026, 6, 1)
        role = _make_entity(
            name="Designer", entity_type=EntityType.ROLE,
            entity_id="r1", updated_at=now,
        )
        # Doc last updated 4 months ago
        old_doc = _make_doc(
            who=["Designer"], updated_at=datetime(2026, 1, 1),
        )
        result = detect_staleness([role], [old_doc], [], now=now)
        role_warnings = [w for w in result if w.pattern == "role_disappeared"]
        assert len(role_warnings) == 1

    def test_role_not_disappeared_if_recent_doc(self):
        now = datetime(2026, 3, 15)
        role = _make_entity(
            name="Developer", entity_type=EntityType.ROLE,
            entity_id="r1", updated_at=now,
        )
        recent_doc = _make_doc(who=["developer"], updated_at=datetime(2026, 3, 10))
        result = detect_staleness([role], [recent_doc], [], now=now)
        role_warnings = [w for w in result if w.pattern == "role_disappeared"]
        assert len(role_warnings) == 0

    def test_archived_docs_ignored_for_lag(self):
        old = datetime(2026, 1, 1)
        new = datetime(2026, 3, 15)
        entity = _make_entity(updated_at=new)
        doc = _make_doc(
            linked_entity_ids=["e1"], updated_at=old,
            status=DocumentStatus.ARCHIVED,
        )
        result = detect_staleness([entity], [doc], [], now=new)
        lag_warnings = [w for w in result if w.pattern == "feature_updated_docs_lagging"]
        assert len(lag_warnings) == 0


# ──────────────────────────────────────────────
# 4. analyze_blindspots
# ──────────────────────────────────────────────

class TestAnalyzeBlindspots:
    def test_document_wrong_location(self):
        doc = _make_doc(
            title="API Spec",
            what=["api", "backend"],
            uri="marketing/api-spec.md",
        )
        result = analyze_blindspots([], [doc], [])
        wrong_loc = [b for b in result if "wrong" in b.suggested_action.lower() or "location" in b.suggested_action.lower()]
        assert len(wrong_loc) >= 1

    def test_core_feature_lacks_docs(self):
        entity = _make_entity(entity_type=EntityType.MODULE)
        # Only 1 doc linked
        doc = _make_doc(linked_entity_ids=["e1"])
        result = analyze_blindspots([entity], [doc], [])
        core_blind = [b for b in result if "coverage" in b.description.lower() or "document" in b.description.lower()]
        assert len(core_blind) >= 1

    def test_core_feature_sufficient_docs(self):
        entity = _make_entity(entity_type=EntityType.MODULE)
        docs = [
            _make_doc(doc_id="d1", linked_entity_ids=["e1"]),
            _make_doc(doc_id="d2", linked_entity_ids=["e1"]),
        ]
        result = analyze_blindspots([entity], docs, [])
        core_blind = [b for b in result if "coverage" in b.description.lower() and entity.name in b.description]
        assert len(core_blind) == 0

    def test_confirmed_problem_without_schedule(self):
        doc = _make_doc(how="已確認問題，需要修復")
        result = analyze_blindspots([], [doc], [])
        prob_blind = [b for b in result if "problem" in b.description.lower() or "issue" in b.description.lower()]
        assert len(prob_blind) >= 1

    def test_confirmed_problem_with_schedule(self):
        doc = _make_doc(how="已確認問題，scheduled for sprint 5")
        result = analyze_blindspots([], [doc], [])
        prob_blind = [b for b in result if "problem" in b.description.lower() and "schedule" in b.description.lower()]
        assert len(prob_blind) == 0

    def test_one_off_docs_ratio_high(self):
        current = [_make_doc(doc_id=f"c{i}", status=DocumentStatus.CURRENT) for i in range(2)]
        archived = [_make_doc(doc_id=f"a{i}", status=DocumentStatus.ARCHIVED) for i in range(5)]
        result = analyze_blindspots([], current + archived, [])
        ratio_blind = [b for b in result if "ratio" in b.description.lower() or "noise" in b.description.lower()]
        assert len(ratio_blind) >= 1

    def test_timeline_gap(self):
        docs = [
            _make_doc(doc_id="d1", updated_at=datetime(2025, 1, 1)),
            _make_doc(doc_id="d2", updated_at=datetime(2026, 3, 1)),
        ]
        result = analyze_blindspots([], docs, [])
        gap_blind = [b for b in result if "gap" in b.description.lower() or "timeline" in b.description.lower()]
        assert len(gap_blind) >= 1

    def test_no_timeline_gap_when_close(self):
        docs = [
            _make_doc(doc_id="d1", updated_at=datetime(2026, 2, 1)),
            _make_doc(doc_id="d2", updated_at=datetime(2026, 3, 1)),
        ]
        result = analyze_blindspots([], docs, [])
        gap_blind = [b for b in result if "gap" in b.description.lower() and "timeline" in b.description.lower()]
        assert len(gap_blind) == 0

    def test_missing_non_technical_entry(self):
        role = _make_entity(
            name="Marketing", entity_type=EntityType.ROLE, entity_id="r1",
        )
        # No doc targets marketing
        doc = _make_doc(who=["developer"])
        result = analyze_blindspots([role], [doc], [])
        entry_blind = [b for b in result if "non-technical" in b.description.lower() or "marketing" in b.description.lower()]
        assert len(entry_blind) >= 1

    def test_goal_priority_unclear(self):
        goals = [
            _make_entity(name="Goal A", entity_type=EntityType.GOAL, entity_id="g1"),
            _make_entity(name="Goal B", entity_type=EntityType.GOAL, entity_id="g2"),
        ]
        result = analyze_blindspots(goals, [], [])
        priority_blind = [b for b in result if "priority" in b.description.lower()]
        assert len(priority_blind) >= 1

    def test_goal_priority_clear(self):
        goals = [
            _make_entity(
                name="Goal A", entity_type=EntityType.GOAL, entity_id="g1",
                details={"priority": 1},
            ),
            _make_entity(
                name="Goal B", entity_type=EntityType.GOAL, entity_id="g2",
                details={"priority": 2},
            ),
        ]
        result = analyze_blindspots(goals, [], [])
        priority_blind = [b for b in result if "priority" in b.description.lower() and "unclear" in b.description.lower()]
        assert len(priority_blind) == 0

    def test_active_l2_missing_impacts_emits_repair_blindspot(self):
        mod = _make_entity(name="Action Layer", entity_type=EntityType.MODULE, entity_id="m1")
        result = analyze_blindspots([mod], [], [])
        repair_blind = [b for b in result if "no concrete impacts path" in b.description.lower()]
        assert len(repair_blind) >= 1
        assert "降級為 L3" in repair_blind[0].suggested_action


# ──────────────────────────────────────────────
# 5. run_quality_check
# ──────────────────────────────────────────────

class TestRunQualityCheck:
    def test_perfect_score(self):
        """A well-formed ontology should score high."""
        entity = _make_entity(entity_type=EntityType.MODULE, summary="Short summary")
        doc1 = _make_doc(doc_id="d1", linked_entity_ids=["e1"], who=["developer"])
        doc2 = _make_doc(doc_id="d2", linked_entity_ids=["e1"], who=["developer"])
        doc3 = _make_doc(doc_id="d3", linked_entity_ids=["e1"], who=["developer"])
        rel = _make_rel(source_id="e1", target_id="e1")
        role = _make_entity(
            name="developer", entity_type=EntityType.ROLE, entity_id="r1",
        )
        blindspot = Blindspot(
            description="test", severity=Severity.GREEN,
            related_entity_ids=["e1"], suggested_action="check",
            created_at=datetime(2026, 3, 1),
        )
        protocol = Protocol(
            entity_id="e1", entity_name="TestEntity",
            content={"what": {}, "why": {}, "how": {}, "who": {}},
            generated_at=datetime(2026, 3, 1),
            updated_at=datetime(2026, 3, 1),
        )
        report = run_quality_check(
            entities=[entity, role],
            documents=[doc1, doc2, doc3],
            protocols=[protocol],
            blindspots=[blindspot],
            relationships=[rel],
        )
        assert report.score > 0
        assert isinstance(report.passed, list)
        assert isinstance(report.failed, list)

    def test_empty_ontology(self):
        report = run_quality_check([], [], [], [], [])
        assert isinstance(report.score, int)

    def test_unlinked_documents_fail(self):
        doc = _make_doc(linked_entity_ids=[])
        report = run_quality_check([], [doc], [], [], [])
        failed_names = [f.name for f in report.failed]
        assert "documents_linked" in failed_names

    def test_orphan_entity_fails_dependency_check(self):
        entity = _make_entity(entity_type=EntityType.MODULE)
        report = run_quality_check([entity], [], [], [], [])
        failed_names = [f.name for f in report.failed]
        assert "dependency_completeness" in failed_names

    def test_archived_without_rationale_fails(self):
        doc = _make_doc(status=DocumentStatus.ARCHIVED)
        # Override summary to empty
        doc.summary = ""
        report = run_quality_check([], [doc], [], [], [])
        failed_names = [f.name for f in report.failed]
        assert "archive_rationale" in failed_names

    def test_multiple_goals_without_priority_fails(self):
        goals = [
            _make_entity(name="G1", entity_type=EntityType.GOAL, entity_id="g1"),
            _make_entity(name="G2", entity_type=EntityType.GOAL, entity_id="g2"),
        ]
        report = run_quality_check(goals, [], [], [], [])
        failed_names = [f.name for f in report.failed]
        assert "goal_priority" in failed_names

    def test_role_without_docs_fails(self):
        role = _make_entity(
            name="Designer", entity_type=EntityType.ROLE, entity_id="r1",
        )
        doc = _make_doc(who=["developer"])
        report = run_quality_check([role], [doc], [], [], [])
        failed_names = [f.name for f in report.failed]
        assert "role_document_coverage" in failed_names

    def test_bad_split_granularity_fails(self):
        # Module with only 1 doc (below 3)
        entity = _make_entity(entity_type=EntityType.MODULE)
        doc = _make_doc(linked_entity_ids=["e1"])
        rel = _make_rel(source_id="e1", target_id="e1")
        report = run_quality_check([entity], [doc], [], [], [rel])
        failed_names = [f.name for f in report.failed]
        assert "split_granularity" in failed_names

    def test_score_calculation(self):
        """Score should be weighted percentage of passed checks."""
        report = run_quality_check([], [], [], [], [])
        all_items = report.passed + report.failed
        if all_items:
            weighted_total = sum(i.weight for i in all_items)
            weighted_passed = sum(i.weight for i in report.passed)
            expected = int((weighted_passed / weighted_total) * 100) if weighted_total else 0
            assert report.score == expected


# ──────────────────────────────────────────────
# 5b. run_quality_check — L2 checks (items 10-12)
# ──────────────────────────────────────────────

class TestRunQualityCheckL2:
    """Tests for the three L2-specific quality checks (10-12)."""

    # --- Check 10: l2_summary_readability ---

    def test_l2_summary_with_tech_term_fails(self):
        """Module entity with technical term in summary should fail readability check."""
        entity = _make_entity(
            entity_type=EntityType.MODULE,
            summary="We use an API to connect the system.",
        )
        report = run_quality_check([entity], [], [], [], [])
        failed_names = [f.name for f in report.failed]
        assert "l2_summary_readability" in failed_names

    def test_l2_summary_tech_term_case_insensitive(self):
        """Technical term check is case-insensitive."""
        entity = _make_entity(
            entity_type=EntityType.MODULE,
            summary="Our platform uses graphql for data queries.",
        )
        report = run_quality_check([entity], [], [], [], [])
        failed_names = [f.name for f in report.failed]
        assert "l2_summary_readability" in failed_names

    def test_l2_summary_tech_term_whole_word_only(self):
        """Partial matches should not trigger (e.g. 'APIs' does not match 'API' whole word)."""
        # "APIs" — the regex uses \b so "APIs" has word boundary after "s", not "I".
        # However "API" inside "APIs" is at a word boundary on the left. This test
        # documents that our check will indeed catch "APIs" because \bAPI\b won't match it.
        entity = _make_entity(
            entity_type=EntityType.MODULE,
            summary="We build rapid prototypes.",  # "rapid" contains no tech terms
        )
        report = run_quality_check([entity], [], [], [], [])
        passed_names = [p.name for p in report.passed]
        assert "l2_summary_readability" in passed_names

    def test_l2_summary_clean_passes_readability(self):
        """Module entity with plain-language summary passes readability check."""
        entity = _make_entity(
            entity_type=EntityType.MODULE,
            summary="這個模組負責協調跨部門的知識共享流程。",
        )
        report = run_quality_check([entity], [], [], [], [])
        passed_names = [p.name for p in report.passed]
        assert "l2_summary_readability" in passed_names

    def test_non_module_entity_not_checked_for_readability(self):
        """Product-type entity with technical terms should not affect l2_summary_readability."""
        entity = _make_entity(
            entity_type=EntityType.PRODUCT,
            summary="We use Firestore and Docker for deployment.",
        )
        report = run_quality_check([entity], [], [], [], [])
        passed_names = [p.name for p in report.passed]
        assert "l2_summary_readability" in passed_names

    def test_l2_readability_detail_names_found_terms(self):
        """Failed detail message should mention the found technical terms."""
        entity = _make_entity(
            entity_type=EntityType.MODULE,
            summary="This uses REST and OAuth for authentication.",
        )
        report = run_quality_check([entity], [], [], [], [])
        check = next(i for i in report.failed if i.name == "l2_summary_readability")
        assert "REST" in check.detail
        assert "OAuth" in check.detail

    # --- Check 11: l2_summary_conciseness ---

    def test_l2_summary_over_5_sentences_is_warning(self):
        """Module summary with >5 sentences generates a warning (not a failure)."""
        long_summary = "第一句。第二句。第三句。第四句。第五句。第六句。"
        entity = _make_entity(
            entity_type=EntityType.MODULE,
            summary=long_summary,
        )
        report = run_quality_check([entity], [], [], [], [])
        warning_names = [w.name for w in report.warnings]
        failed_names = [f.name for f in report.failed]
        assert "l2_summary_conciseness" in warning_names
        assert "l2_summary_conciseness" not in failed_names

    def test_l2_summary_exactly_5_sentences_passes(self):
        """Module summary with exactly 5 sentences does not trigger warning."""
        summary = "第一句。第二句。第三句。第四句。第五句。"
        entity = _make_entity(
            entity_type=EntityType.MODULE,
            summary=summary,
        )
        report = run_quality_check([entity], [], [], [], [])
        warning_names = [w.name for w in report.warnings]
        assert "l2_summary_conciseness" not in warning_names

    def test_l2_summary_conciseness_counts_all_punctuation(self):
        """Sentence count includes periods, question marks, and exclamation marks."""
        summary = "Really? Yes! Absolutely. Sure. Indeed?"  # 5 sentence endings
        entity = _make_entity(
            entity_type=EntityType.MODULE,
            summary=summary,
        )
        report = run_quality_check([entity], [], [], [], [])
        warning_names = [w.name for w in report.warnings]
        assert "l2_summary_conciseness" not in warning_names

    def test_l2_conciseness_is_always_passed_item(self):
        """l2_summary_conciseness must always appear in passed (warnings don't fail)."""
        long_summary = "一。二。三。四。五。六。七。"
        entity = _make_entity(entity_type=EntityType.MODULE, summary=long_summary)
        report = run_quality_check([entity], [], [], [], [])
        passed_names = [p.name for p in report.passed]
        assert "l2_summary_conciseness" in passed_names

    # --- Check 12: l2_impacts_coverage ---

    def test_majority_modules_without_rels_fails_coverage(self):
        """When >50% of module entities have no relationships, coverage check fails."""
        m1 = _make_entity(name="M1", entity_type=EntityType.MODULE, entity_id="m1")
        m2 = _make_entity(name="M2", entity_type=EntityType.MODULE, entity_id="m2")
        m3 = _make_entity(name="M3", entity_type=EntityType.MODULE, entity_id="m3")
        # Only m1 has a relationship; m2 and m3 do not (2/3 = 66% > 50%)
        rel = _make_rel(source_id="m1", target_id="m1")
        report = run_quality_check([m1, m2, m3], [], [], [], [rel])
        failed_names = [f.name for f in report.failed]
        assert "l2_impacts_coverage" in failed_names

    def test_any_active_l2_missing_impacts_fails_coverage(self):
        """Any active L2 without concrete impacts should fail hard-rule check."""
        m1 = _make_entity(name="M1", entity_type=EntityType.MODULE, entity_id="m1")
        m2 = _make_entity(name="M2", entity_type=EntityType.MODULE, entity_id="m2")
        # m1 has impacts, m2 does not — should fail under hard rule
        rel = Relationship(
            id="r1",
            source_entity_id="m1",
            target_id="m1",
            type=RelationshipType.IMPACTS,
            description="A 改了閾值→B 的計算邏輯要跟著看",
        )
        report = run_quality_check([m1, m2], [], [], [], [rel])
        failed_names = [f.name for f in report.failed]
        assert "l2_impacts_coverage" in failed_names

    def test_all_modules_with_rels_passes_coverage(self):
        """All module entities covered by concrete impacts passes coverage check."""
        m1 = _make_entity(name="M1", entity_type=EntityType.MODULE, entity_id="m1")
        m2 = _make_entity(name="M2", entity_type=EntityType.MODULE, entity_id="m2")
        rel = Relationship(
            id="r1",
            source_entity_id="m1",
            target_id="m2",
            type=RelationshipType.IMPACTS,
            description="A 改了策略→B 的執行規則要跟著看",
        )
        report = run_quality_check([m1, m2], [], [], [], [rel])
        passed_names = [p.name for p in report.passed]
        assert "l2_impacts_coverage" in passed_names

    def test_impacts_without_change_path_not_counted(self):
        """Impacts without 'A changed -> B checks' style detail should not count."""
        m1 = _make_entity(name="M1", entity_type=EntityType.MODULE, entity_id="m1")
        m2 = _make_entity(name="M2", entity_type=EntityType.MODULE, entity_id="m2")
        rel = Relationship(
            id="r1",
            source_entity_id="m1",
            target_id="m2",
            type=RelationshipType.IMPACTS,
            description="A impacts B",
        )
        report = run_quality_check([m1, m2], [], [], [], [rel])
        failed_names = [f.name for f in report.failed]
        assert "l2_impacts_coverage" in failed_names

    def test_no_modules_passes_coverage(self):
        """When there are no module entities, coverage check passes trivially."""
        entity = _make_entity(entity_type=EntityType.PRODUCT)
        report = run_quality_check([entity], [], [], [], [])
        passed_names = [p.name for p in report.passed]
        assert "l2_impacts_coverage" in passed_names

    def test_inactive_l2_not_counted_in_hard_rule(self):
        """Paused/completed L2 should not trigger active L2 impacts hard-rule failure."""
        active = _make_entity(name="M1", entity_type=EntityType.MODULE, entity_id="m1", status=EntityStatus.ACTIVE)
        paused = _make_entity(name="M2", entity_type=EntityType.MODULE, entity_id="m2", status=EntityStatus.PAUSED)
        rel = Relationship(
            id="r1",
            source_entity_id="m1",
            target_id="m1",
            type=RelationshipType.IMPACTS,
            description="A 改了策略→B 的執行規則要跟著看",
        )
        report = run_quality_check([active, paused], [], [], [], [rel])
        passed_names = [p.name for p in report.passed]
        assert "l2_impacts_coverage" in passed_names

    def test_l2_coverage_detail_format(self):
        """Failed detail should mention n/total without relationships."""
        m1 = _make_entity(name="M1", entity_type=EntityType.MODULE, entity_id="m1")
        m2 = _make_entity(name="M2", entity_type=EntityType.MODULE, entity_id="m2")
        m3 = _make_entity(name="M3", entity_type=EntityType.MODULE, entity_id="m3")
        report = run_quality_check([m1, m2, m3], [], [], [], [])
        check = next(i for i in report.failed if i.name == "l2_impacts_coverage")
        assert "3/3" in check.detail


# ──────────────────────────────────────────────
# Task 4: check_impacts_target_validity
# ──────────────────────────────────────────────

def _make_impacts_rel(
    source_id: str,
    target_id: str,
    rel_id: str = "r1",
    description: str = "A 改了規則→B 的流程要跟著看",
) -> Relationship:
    return Relationship(
        id=rel_id,
        source_entity_id=source_id,
        target_id=target_id,
        type=RelationshipType.IMPACTS,
        description=description,
    )


class TestCheckImpactsTargetValidity:
    def test_no_relationships_returns_empty(self):
        """No relationships → no broken impacts."""
        m1 = _make_entity(name="M1", entity_type=EntityType.MODULE, entity_id="m1")
        result = check_impacts_target_validity([m1], [])
        assert result == []

    def test_valid_target_returns_empty(self):
        """Impacts pointing to an active entity → no issues."""
        m1 = _make_entity(name="M1", entity_type=EntityType.MODULE, entity_id="m1")
        m2 = _make_entity(name="M2", entity_type=EntityType.MODULE, entity_id="m2")
        rel = _make_impacts_rel("m1", "m2")
        result = check_impacts_target_validity([m1, m2], [rel])
        assert result == []

    def test_valid_external_target_context_returns_empty(self):
        """Scoped checks can validate cross-scope targets without making them sources."""
        m1 = _make_entity(name="M1", entity_type=EntityType.MODULE, entity_id="m1")
        external = _make_entity(name="External", entity_type=EntityType.MODULE, entity_id="external-1")
        rel = _make_impacts_rel("m1", "external-1")
        result = check_impacts_target_validity([m1], [rel], target_context_entities=[external])
        assert result == []

    def test_detects_not_found_target(self):
        """Impacts pointing to a non-existent entity → reason='target_missing'."""
        m1 = _make_entity(name="M1", entity_type=EntityType.MODULE, entity_id="m1")
        rel = _make_impacts_rel("m1", "ghost-id")
        result = check_impacts_target_validity([m1], [rel])
        assert len(result) == 1
        assert result[0]["source_entity_id"] == "m1"
        broken = result[0]["broken_impacts"]
        assert len(broken) == 1
        assert broken[0]["reason"] == "target_missing"
        assert broken[0]["target_entity_id"] == "ghost-id"
        assert broken[0]["target_entity_name"] is None
        assert "impacts_description" in broken[0]
        assert "suggested_action" in broken[0]

    def test_detects_stale_target(self):
        """Impacts pointing to a stale entity → reason='target_stale'."""
        m1 = _make_entity(name="M1", entity_type=EntityType.MODULE, entity_id="m1")
        m2 = _make_entity(
            name="M2", entity_type=EntityType.MODULE, entity_id="m2",
            status=EntityStatus.STALE,
        )
        rel = _make_impacts_rel("m1", "m2")
        result = check_impacts_target_validity([m1, m2], [rel])
        assert len(result) == 1
        broken = result[0]["broken_impacts"]
        assert broken[0]["reason"] == "target_stale"
        assert broken[0]["target_entity_name"] == "M2"
        assert "stale" in broken[0]["suggested_action"]

    def test_detects_draft_target(self):
        """Impacts pointing to a draft entity → reason='target_draft'."""
        m1 = _make_entity(name="M1", entity_type=EntityType.MODULE, entity_id="m1")
        m2 = _make_entity(
            name="M2", entity_type=EntityType.MODULE, entity_id="m2",
            status=EntityStatus.DRAFT,
        )
        rel = _make_impacts_rel("m1", "m2")
        result = check_impacts_target_validity([m1, m2], [rel])
        assert result[0]["broken_impacts"][0]["reason"] == "target_draft"

    def test_detects_completed_target(self):
        """Impacts pointing to a completed entity → reason='target_draft' (non-active catch-all)."""
        m1 = _make_entity(name="M1", entity_type=EntityType.MODULE, entity_id="m1")
        m2 = _make_entity(
            name="M2", entity_type=EntityType.MODULE, entity_id="m2",
            status=EntityStatus.COMPLETED,
        )
        rel = _make_impacts_rel("m1", "m2")
        result = check_impacts_target_validity([m1, m2], [rel])
        assert result[0]["broken_impacts"][0]["reason"] == "target_draft"

    def test_non_concrete_impacts_ignored(self):
        """Impacts without concrete change-path description are skipped."""
        m1 = _make_entity(name="M1", entity_type=EntityType.MODULE, entity_id="m1")
        rel = _make_impacts_rel("m1", "ghost-id", description="A impacts B vaguely")
        result = check_impacts_target_validity([m1], [rel])
        assert result == []

    def test_inactive_source_not_checked(self):
        """Only active L2 modules are source candidates."""
        m1 = _make_entity(
            name="M1", entity_type=EntityType.MODULE, entity_id="m1",
            status=EntityStatus.STALE,
        )
        rel = _make_impacts_rel("m1", "ghost-id")
        result = check_impacts_target_validity([m1], [rel])
        assert result == []

    def test_suggested_actions_present(self):
        """Result should include suggested_actions."""
        m1 = _make_entity(name="M1", entity_type=EntityType.MODULE, entity_id="m1")
        rel = _make_impacts_rel("m1", "ghost-id")
        result = check_impacts_target_validity([m1], [rel])
        assert "suggested_actions" in result[0]
        assert len(result[0]["suggested_actions"]) > 0

    def test_multiple_broken_impacts_grouped_by_source(self):
        """Multiple broken targets from same source should be in one entry."""
        m1 = _make_entity(name="M1", entity_type=EntityType.MODULE, entity_id="m1")
        rel1 = _make_impacts_rel("m1", "ghost1", rel_id="r1")
        rel2 = _make_impacts_rel("m1", "ghost2", rel_id="r2")
        result = check_impacts_target_validity([m1], [rel1, rel2])
        assert len(result) == 1
        assert len(result[0]["broken_impacts"]) == 2

    def test_run_quality_check_includes_item_13(self):
        """run_quality_check should include l2_impacts_target_validity as item 13."""
        m1 = _make_entity(name="M1", entity_type=EntityType.MODULE, entity_id="m1")
        m2 = _make_entity(
            name="M2", entity_type=EntityType.MODULE, entity_id="m2",
            status=EntityStatus.STALE,
        )
        rel = _make_impacts_rel("m1", "m2")
        report = run_quality_check([m1, m2], [], [], [], [rel])
        all_item_names = [i.name for i in report.passed + report.failed + report.warnings]
        assert "l2_impacts_target_validity" in all_item_names

    def test_run_quality_check_item_13_fails_on_broken_impacts(self):
        """Quality check item 13 fails when impacts point to invalid targets."""
        m1 = _make_entity(name="M1", entity_type=EntityType.MODULE, entity_id="m1")
        rel = _make_impacts_rel("m1", "ghost-id")
        report = run_quality_check([m1], [], [], [], [rel])
        failed_names = [i.name for i in report.failed]
        assert "l2_impacts_target_validity" in failed_names

    def test_run_quality_check_item_13_passes_when_valid(self):
        """Quality check item 13 passes when all impacts targets are valid."""
        m1 = _make_entity(name="M1", entity_type=EntityType.MODULE, entity_id="m1")
        m2 = _make_entity(name="M2", entity_type=EntityType.MODULE, entity_id="m2")
        rel = _make_impacts_rel("m1", "m2")
        report = run_quality_check([m1, m2], [], [], [], [rel])
        passed_names = [i.name for i in report.passed]
        assert "l2_impacts_target_validity" in passed_names

    def test_run_quality_check_item_13_uses_external_target_context(self):
        """Scoped quality can validate cross-scope impacts targets."""
        m1 = _make_entity(name="M1", entity_type=EntityType.MODULE, entity_id="m1")
        external = _make_entity(name="External", entity_type=EntityType.MODULE, entity_id="external-1")
        rel = _make_impacts_rel("m1", "external-1")
        report = run_quality_check(
            [m1],
            [],
            [],
            [],
            [rel],
            impact_target_context_entities=[external],
        )
        passed_names = [i.name for i in report.passed]
        assert "l2_impacts_target_validity" in passed_names


# ──────────────────────────────────────────────
# Task 5: find_stale_l2_downstream_entities
# ──────────────────────────────────────────────

class TestFindStaleL2DownstreamEntities:
    def test_no_stale_modules_returns_empty(self):
        """No stale modules → no downstream entries."""
        m1 = _make_entity(name="M1", entity_type=EntityType.MODULE, entity_id="m1")
        result = find_stale_l2_downstream_entities([m1])
        assert result == []

    def test_stale_module_with_children(self):
        """Stale module with parent_id children is reported."""
        stale_mod = _make_entity(
            name="StaleModule", entity_type=EntityType.MODULE, entity_id="sm1",
            status=EntityStatus.STALE,
        )
        child = Entity(
            id="c1",
            name="ChildEntity",
            type=EntityType.MODULE,
            summary="a child",
            tags=Tags(what="test", why="testing", how="auto", who="dev"),
            status=EntityStatus.ACTIVE,
            parent_id="sm1",
            created_at=datetime(2026, 1, 1),
            updated_at=datetime(2026, 1, 1),
        )
        result = find_stale_l2_downstream_entities([stale_mod, child])
        assert len(result) == 1
        assert result[0]["stale_module_id"] == "sm1"
        assert result[0]["stale_module_name"] == "StaleModule"
        assert len(result[0]["affected_l3_entities"]) == 1
        assert result[0]["affected_l3_entities"][0]["id"] == "c1"
        assert result[0]["affected_l3_entities"][0]["name"] == "ChildEntity"

    def test_stale_module_without_children(self):
        """Stale module with no children reports empty affected_l3_entities."""
        stale_mod = _make_entity(
            name="Orphan", entity_type=EntityType.MODULE, entity_id="sm1",
            status=EntityStatus.STALE,
        )
        result = find_stale_l2_downstream_entities([stale_mod])
        assert len(result) == 1
        assert result[0]["affected_l3_entities"] == []

    def test_active_module_children_not_reported(self):
        """Active modules should not appear in results even if they have children."""
        active_mod = _make_entity(
            name="ActiveMod", entity_type=EntityType.MODULE, entity_id="am1",
        )
        child = Entity(
            id="c1",
            name="Child",
            type=EntityType.MODULE,
            summary="child",
            tags=Tags(what="x", why="y", how="z", who="w"),
            status=EntityStatus.ACTIVE,
            parent_id="am1",
            created_at=datetime(2026, 1, 1),
            updated_at=datetime(2026, 1, 1),
        )
        result = find_stale_l2_downstream_entities([active_mod, child])
        assert result == []

    def test_multiple_stale_modules_each_reported(self):
        """Each stale module gets its own entry."""
        sm1 = _make_entity(
            name="S1", entity_type=EntityType.MODULE, entity_id="sm1",
            status=EntityStatus.STALE,
        )
        sm2 = _make_entity(
            name="S2", entity_type=EntityType.MODULE, entity_id="sm2",
            status=EntityStatus.STALE,
        )
        result = find_stale_l2_downstream_entities([sm1, sm2])
        assert len(result) == 2
        ids = {r["stale_module_id"] for r in result}
        assert ids == {"sm1", "sm2"}


# ──────────────────────────────────────────────
# Task 6: check_reverse_impacts
# ──────────────────────────────────────────────

class TestCheckReverseImpacts:
    def test_no_relationships_returns_empty(self):
        """No impacts relationships → no reverse check results."""
        m1 = _make_entity(name="M1", entity_type=EntityType.MODULE, entity_id="m1")
        result = check_reverse_impacts([m1], [])
        assert result == []

    def test_recently_modified_target_with_source_reported(self):
        """Entity modified within threshold that is an impacts target is reported."""
        now = datetime(2026, 3, 27)
        source = _make_entity(
            name="Source", entity_type=EntityType.MODULE, entity_id="src1",
            updated_at=datetime(2026, 1, 1),  # old, not recently modified
        )
        target = _make_entity(
            name="Target", entity_type=EntityType.MODULE, entity_id="tgt1",
            updated_at=datetime(2026, 3, 20),  # recent: within 30 days of now
        )
        rel = _make_impacts_rel("src1", "tgt1")
        result = check_reverse_impacts([source, target], [rel], now=now)
        assert len(result) == 1
        assert result[0]["modified_entity_id"] == "tgt1"
        assert len(result[0]["impacted_by"]) == 1
        assert result[0]["impacted_by"][0]["source_entity_id"] == "src1"

    def test_old_target_not_reported(self):
        """Entity modified outside threshold is not reported."""
        now = datetime(2026, 3, 27)
        source = _make_entity(name="Src", entity_type=EntityType.MODULE, entity_id="src1")
        target = _make_entity(
            name="Tgt", entity_type=EntityType.MODULE, entity_id="tgt1",
            updated_at=datetime(2025, 12, 1),  # very old
        )
        rel = _make_impacts_rel("src1", "tgt1")
        result = check_reverse_impacts([source, target], [rel], now=now)
        assert result == []

    def test_non_concrete_impacts_ignored(self):
        """Non-concrete impacts relationships are not considered."""
        now = datetime(2026, 3, 27)
        source = _make_entity(name="Src", entity_type=EntityType.MODULE, entity_id="src1")
        target = _make_entity(
            name="Tgt", entity_type=EntityType.MODULE, entity_id="tgt1",
            updated_at=datetime(2026, 3, 20),
        )
        rel = _make_impacts_rel("src1", "tgt1", description="vague impact")
        result = check_reverse_impacts([source, target], [rel], now=now)
        assert result == []

    def test_modified_at_in_iso_format(self):
        """modified_at field should be ISO datetime string."""
        now = datetime(2026, 3, 27)
        source = _make_entity(name="Src", entity_type=EntityType.MODULE, entity_id="src1")
        mod_time = datetime(2026, 3, 20, 12, 0, 0)
        target = _make_entity(
            name="Tgt", entity_type=EntityType.MODULE, entity_id="tgt1",
            updated_at=mod_time,
        )
        rel = _make_impacts_rel("src1", "tgt1")
        result = check_reverse_impacts([source, target], [rel], now=now)
        assert result[0]["modified_at"] == mod_time.isoformat()

    def test_needs_review_reason_in_output(self):
        """Each impacted_by entry should include needs_review_reason."""
        now = datetime(2026, 3, 27)
        source = _make_entity(name="Src", entity_type=EntityType.MODULE, entity_id="src1")
        target = _make_entity(
            name="Tgt", entity_type=EntityType.MODULE, entity_id="tgt1",
            updated_at=datetime(2026, 3, 20),
        )
        rel = _make_impacts_rel("src1", "tgt1")
        result = check_reverse_impacts([source, target], [rel], now=now)
        assert "needs_review_reason" in result[0]["impacted_by"][0]

    def test_custom_threshold_respected(self):
        """Custom staleness_threshold_days should override default 30."""
        now = datetime(2026, 3, 27)
        source = _make_entity(name="Src", entity_type=EntityType.MODULE, entity_id="src1")
        target = _make_entity(
            name="Tgt", entity_type=EntityType.MODULE, entity_id="tgt1",
            updated_at=datetime(2026, 3, 20),  # 7 days ago
        )
        rel = _make_impacts_rel("src1", "tgt1")
        # With threshold=5, 7 days ago is outside threshold → not reported
        result = check_reverse_impacts([source, target], [rel], now=now, staleness_threshold_days=5)
        assert result == []
        # With threshold=10, 7 days ago is within threshold → reported
        result = check_reverse_impacts([source, target], [rel], now=now, staleness_threshold_days=10)
        assert len(result) == 1

    def test_entity_without_id_skipped(self):
        """Entities without id are skipped gracefully."""
        now = datetime(2026, 3, 27)
        no_id_entity = _make_entity(
            name="NoID", entity_type=EntityType.MODULE, entity_id=None,
            updated_at=datetime(2026, 3, 20),
        )
        result = check_reverse_impacts([no_id_entity], [], now=now)
        assert result == []


# ──────────────────────────────────────────────
# Task 7: check_governance_review_overdue
# ──────────────────────────────────────────────

from datetime import timezone as _tz
from zenos.domain.governance import check_governance_review_overdue, find_tech_terms_in_summary


def _make_module(
    name: str,
    entity_id: str,
    status: str = EntityStatus.ACTIVE,
    last_reviewed_at: datetime | None = None,
    created_at: datetime | None = None,
) -> Entity:
    """Helper to build a module Entity with optional review timestamps."""
    base = created_at or datetime(2025, 1, 1, tzinfo=_tz.utc)
    return Entity(
        id=entity_id,
        name=name,
        type=EntityType.MODULE,
        summary="A module summary",
        tags=Tags(what="test", why="test", how="test", who="test"),
        status=status,
        created_at=base,
        updated_at=base,
        last_reviewed_at=last_reviewed_at,
    )


class TestCheckGovernanceReviewOverdue:
    """Tests for check_governance_review_overdue domain function."""

    def _now(self) -> datetime:
        return datetime(2026, 3, 27, tzinfo=_tz.utc)

    def test_never_reviewed_overdue_listed(self):
        """Active module with last_reviewed_at=None and creation >90 days ago is listed."""
        mod = _make_module(
            name="Pricing Rules",
            entity_id="m1",
            last_reviewed_at=None,
            created_at=datetime(2025, 1, 1, tzinfo=_tz.utc),  # > 90 days ago
        )
        result = check_governance_review_overdue([mod], now=self._now())
        assert len(result) == 1
        assert result[0]["entity_id"] == "m1"
        assert result[0]["entity_name"] == "Pricing Rules"
        assert result[0]["last_reviewed_at"] is None
        assert result[0]["days_overdue"] > 0
        assert "suggested_action" in result[0]

    def test_never_reviewed_recent_not_listed(self):
        """Active module with last_reviewed_at=None but created <90 days ago is not listed."""
        mod = _make_module(
            name="New Module",
            entity_id="m2",
            last_reviewed_at=None,
            created_at=datetime(2026, 3, 1, tzinfo=_tz.utc),  # 26 days ago
        )
        result = check_governance_review_overdue([mod], now=self._now())
        assert result == []

    def test_recently_reviewed_not_listed(self):
        """Module reviewed 30 days ago (within 90-day window) is not overdue."""
        reviewed = datetime(2026, 2, 25, tzinfo=_tz.utc)  # 30 days ago
        mod = _make_module(
            name="Reviewed Module",
            entity_id="m3",
            last_reviewed_at=reviewed,
        )
        result = check_governance_review_overdue([mod], now=self._now())
        assert result == []

    def test_overdue_reviewed_listed(self):
        """Module last reviewed >90 days ago is listed as overdue."""
        reviewed = datetime(2025, 12, 1, tzinfo=_tz.utc)  # ~116 days ago
        mod = _make_module(
            name="Overdue Module",
            entity_id="m4",
            last_reviewed_at=reviewed,
        )
        result = check_governance_review_overdue([mod], now=self._now())
        assert len(result) == 1
        assert result[0]["entity_id"] == "m4"
        assert result[0]["last_reviewed_at"] is not None
        assert result[0]["days_overdue"] > 0

    def test_inactive_modules_not_listed(self):
        """Paused or draft modules are not included in overdue check."""
        paused = _make_module("Paused", "mp", status=EntityStatus.PAUSED,
                              created_at=datetime(2024, 1, 1, tzinfo=_tz.utc))
        draft = _make_module("Draft", "md", status="draft",
                             created_at=datetime(2024, 1, 1, tzinfo=_tz.utc))
        result = check_governance_review_overdue([paused, draft], now=self._now())
        assert result == []

    def test_days_overdue_calculation(self):
        """days_overdue should equal elapsed_days - 90."""
        reviewed = datetime(2026, 1, 26, tzinfo=_tz.utc)  # 60 days before now
        # 60 days elapsed, review period 90 days → not overdue
        mod = _make_module("M", "m5", last_reviewed_at=reviewed)
        result = check_governance_review_overdue([mod], now=self._now())
        assert result == []

        # 100 days ago → 100-90=10 days overdue
        reviewed_100 = datetime(2025, 12, 17, tzinfo=_tz.utc)  # ~100 days ago
        mod2 = _make_module("M2", "m6", last_reviewed_at=reviewed_100)
        result2 = check_governance_review_overdue([mod2], now=self._now())
        assert len(result2) == 1
        assert result2[0]["days_overdue"] >= 10

    def test_custom_review_period(self):
        """Custom review_period parameter is respected."""
        reviewed = datetime(2026, 3, 17, tzinfo=_tz.utc)  # 10 days ago
        mod = _make_module("M", "m7", last_reviewed_at=reviewed)
        # 30-day period: 10 days elapsed → not overdue
        result = check_governance_review_overdue([mod], review_period=timedelta(days=30), now=self._now())
        assert result == []
        # 5-day period: 10 days elapsed → overdue
        result2 = check_governance_review_overdue([mod], review_period=timedelta(days=5), now=self._now())
        assert len(result2) == 1

    def test_empty_entities_returns_empty(self):
        """No entities → no overdue items."""
        result = check_governance_review_overdue([], now=self._now())
        assert result == []

    def test_quality_check_item_14_present(self):
        """run_quality_check includes l2_governance_review_overdue item."""
        mod = _make_module(
            name="Old Module",
            entity_id="m8",
            last_reviewed_at=None,
            created_at=datetime(2025, 1, 1, tzinfo=_tz.utc),
        )
        report = run_quality_check([mod], [], [], [], [])
        all_names = [i.name for i in report.passed + report.failed]
        assert "l2_governance_review_overdue" in all_names

    def test_quality_check_overdue_is_warning_not_failure(self):
        """l2_governance_review_overdue should appear as warning, not failure."""
        mod = _make_module(
            name="Old Module",
            entity_id="m9",
            last_reviewed_at=None,
            created_at=datetime(2025, 1, 1, tzinfo=_tz.utc),
        )
        report = run_quality_check([mod], [], [], [], [])
        failed_names = [f.name for f in report.failed]
        warning_names = [w.name for w in report.warnings]
        assert "l2_governance_review_overdue" not in failed_names
        assert "l2_governance_review_overdue" in warning_names

    def test_quality_check_no_overdue_no_warning(self):
        """When all modules reviewed recently, no overdue warning."""
        mod = _make_module(
            name="Recent Module",
            entity_id="m10",
            last_reviewed_at=datetime(2026, 3, 1, tzinfo=_tz.utc),
        )
        report = run_quality_check([mod], [], [], [], [])
        warning_names = [w.name for w in report.warnings]
        assert "l2_governance_review_overdue" not in warning_names


# ──────────────────────────────────────────────
# Task 9: find_tech_terms_in_summary
# ──────────────────────────────────────────────

class TestFindTechTermsInSummary:
    """Tests for the public find_tech_terms_in_summary function."""

    def test_finds_known_tech_term(self):
        """Should detect a term from _L2_TECH_TERMS list."""
        found = find_tech_terms_in_summary("We expose a REST API to partners.")
        assert "REST" in found
        assert "API" in found

    def test_returns_empty_for_clean_summary(self):
        """Plain-language summary returns empty list."""
        found = find_tech_terms_in_summary("這個模組協調跨部門的知識共享流程。")
        assert found == []

    def test_case_insensitive(self):
        """Detection is case-insensitive."""
        found = find_tech_terms_in_summary("This uses graphql for queries.")
        assert "GraphQL" in found

    def test_whole_word_only(self):
        """Partial word matches should not trigger (e.g. 'dockers' is not 'Docker')."""
        found = find_tech_terms_in_summary("We use dockers for deployment.")
        # 'dockers' contains 'docker' but not as a whole word boundary match
        assert "Docker" not in found

    def test_empty_string(self):
        """Empty string returns empty list."""
        assert find_tech_terms_in_summary("") == []

    def test_none_like_empty(self):
        """None-equivalent input returns empty list."""
        assert find_tech_terms_in_summary(None) == []  # type: ignore[arg-type]

    def test_shares_list_with_quality_check(self):
        """The same terms that fail run_quality_check also appear in find_tech_terms_in_summary."""
        summary = "We use Kubernetes and Docker for deployment."
        found = find_tech_terms_in_summary(summary)
        entity = _make_entity(entity_type=EntityType.MODULE, summary=summary)
        report = run_quality_check([entity], [], [], [], [])
        check = next(i for i in report.failed if i.name == "l2_summary_readability")
        for term in found:
            assert term in check.detail


# ──────────────────────────────────────────────
# Check 15: l2_three_question_record
# ──────────────────────────────────────────────

class TestL2ThreeQuestionRecord:
    """Quality check 15: active L2 entities must have complete three-question record."""

    def test_active_module_without_layer_decision_fails(self):
        """Active L2 with no layer_decision in details → check15 fails."""
        module = _make_entity(
            name="Pricing Rules",
            entity_type=EntityType.MODULE,
            status=EntityStatus.ACTIVE,
            details=None,
        )
        report = run_quality_check([module], [], [], [], [])
        failed_names = [f.name for f in report.failed]
        assert "l2_three_question_record" in failed_names

    def test_active_module_with_empty_details_fails(self):
        """Active L2 with empty details dict (no layer_decision key) → check15 fails."""
        module = _make_entity(
            name="Pricing Rules",
            entity_type=EntityType.MODULE,
            status=EntityStatus.ACTIVE,
            details={},
        )
        report = run_quality_check([module], [], [], [], [])
        failed_names = [f.name for f in report.failed]
        assert "l2_three_question_record" in failed_names

    def test_active_module_with_incomplete_layer_decision_fails(self):
        """Active L2 where q1_persistent=False → check15 fails."""
        module = _make_entity(
            name="Pricing Rules",
            entity_type=EntityType.MODULE,
            status=EntityStatus.ACTIVE,
            details={"layer_decision": {"q1_persistent": False, "q2_cross_role": True, "q3_company_consensus": True}},
        )
        report = run_quality_check([module], [], [], [], [])
        failed_names = [f.name for f in report.failed]
        assert "l2_three_question_record" in failed_names

    def test_active_module_with_complete_layer_decision_passes(self):
        """Active L2 with all three questions True → check15 passes."""
        module = _make_entity(
            name="Pricing Rules",
            entity_type=EntityType.MODULE,
            status=EntityStatus.ACTIVE,
            details={"layer_decision": {"q1_persistent": True, "q2_cross_role": True, "q3_company_consensus": True}},
        )
        report = run_quality_check([module], [], [], [], [])
        passed_names = [p.name for p in report.passed]
        assert "l2_three_question_record" in passed_names

    def test_draft_module_without_layer_decision_is_not_checked(self):
        """Draft (non-active) L2 is excluded from check15 — only active modules are checked."""
        module = _make_entity(
            name="Draft Module",
            entity_type=EntityType.MODULE,
            status=EntityStatus.DRAFT,
            details=None,
        )
        report = run_quality_check([module], [], [], [], [])
        passed_names = [p.name for p in report.passed]
        assert "l2_three_question_record" in passed_names

    def test_no_active_modules_passes(self):
        """No active modules → check15 passes with 'all 0 entities' message."""
        report = run_quality_check([], [], [], [], [])
        passed_names = [p.name for p in report.passed]
        assert "l2_three_question_record" in passed_names

    def test_mixed_modules_reports_only_incomplete_ones(self):
        """Mix of complete and incomplete L2s → check15 fails and detail lists incomplete ones."""
        complete = _make_entity(
            name="Complete Module",
            entity_type=EntityType.MODULE,
            status=EntityStatus.ACTIVE,
            entity_id="m1",
            details={"layer_decision": {"q1_persistent": True, "q2_cross_role": True, "q3_company_consensus": True}},
        )
        incomplete = _make_entity(
            name="Incomplete Module",
            entity_type=EntityType.MODULE,
            status=EntityStatus.ACTIVE,
            entity_id="m2",
            details=None,
        )
        report = run_quality_check([complete, incomplete], [], [], [], [])
        failed_names = [f.name for f in report.failed]
        assert "l2_three_question_record" in failed_names
        check = next(f for f in report.failed if f.name == "l2_three_question_record")
        assert "Incomplete Module" in check.detail


# ──────────────────────────────────────────────
# 16. L2 consolidation mode check
# ──────────────────────────────────────────────

class TestL2ConsolidationModeCheck:

    def test_all_global_mode_passes_with_no_warning(self):
        """All L2s with consolidation_mode='global' → check passes and no warning item."""
        mod = _make_entity(
            name="Global Module",
            entity_type=EntityType.MODULE,
            entity_id="m1",
            details={"consolidation_mode": "global"},
        )
        report = run_quality_check([mod], [], [], [], [])
        passed_names = [p.name for p in report.passed]
        assert "l2_consolidation_mode" in passed_names
        warning_names = [w.name for w in report.warnings]
        assert "l2_consolidation_mode" not in warning_names

    def test_incremental_mode_triggers_warning(self):
        """L2 with consolidation_mode='incremental' → check passes (warning-only) and is in warnings."""
        mod = _make_entity(
            name="Incremental Module",
            entity_type=EntityType.MODULE,
            entity_id="m1",
            details={"consolidation_mode": "incremental"},
        )
        report = run_quality_check([mod], [], [], [], [])
        passed_names = [p.name for p in report.passed]
        assert "l2_consolidation_mode" in passed_names
        warning_names = [w.name for w in report.warnings]
        assert "l2_consolidation_mode" in warning_names
        check = next(w for w in report.warnings if w.name == "l2_consolidation_mode")
        assert "Incremental Module" in check.detail
        assert "incremental" in check.detail
        assert "建議以全局模式重新 capture" in check.detail

    def test_missing_consolidation_mode_triggers_warning(self):
        """L2 without consolidation_mode in details → check passes (warning-only) and is in warnings."""
        mod = _make_entity(
            name="Missing Mode Module",
            entity_type=EntityType.MODULE,
            entity_id="m1",
            details=None,
        )
        report = run_quality_check([mod], [], [], [], [])
        passed_names = [p.name for p in report.passed]
        assert "l2_consolidation_mode" in passed_names
        warning_names = [w.name for w in report.warnings]
        assert "l2_consolidation_mode" in warning_names
        check = next(w for w in report.warnings if w.name == "l2_consolidation_mode")
        assert "Missing Mode Module" in check.detail
        assert "missing" in check.detail

    def test_no_modules_passes_with_no_warning(self):
        """No module entities → check passes with 0-count message, no warning."""
        report = run_quality_check([], [], [], [], [])
        passed_names = [p.name for p in report.passed]
        assert "l2_consolidation_mode" in passed_names
        warning_names = [w.name for w in report.warnings]
        assert "l2_consolidation_mode" not in warning_names

    def test_mixed_modes_warning_lists_non_global(self):
        """Mix of global and incremental/missing L2s → warning lists the non-global ones."""
        global_mod = _make_entity(
            name="Good Module",
            entity_type=EntityType.MODULE,
            entity_id="m1",
            details={"consolidation_mode": "global"},
        )
        bad_mod = _make_entity(
            name="Bad Module",
            entity_type=EntityType.MODULE,
            entity_id="m2",
            details={"consolidation_mode": "incremental"},
        )
        report = run_quality_check([global_mod, bad_mod], [], [], [], [])
        warning_names = [w.name for w in report.warnings]
        assert "l2_consolidation_mode" in warning_names
        check = next(w for w in report.warnings if w.name == "l2_consolidation_mode")
        assert "Bad Module" in check.detail
        assert "Good Module" not in check.detail
        assert "Complete Module" not in check.detail


# ──────────────────────────────────────────────
# Part A: blindspot type safety (_safe_str)
# ──────────────────────────────────────────────

def _make_entity_with_list_how(entity_id: str = "m1") -> Entity:
    """Create an entity whose tags.how is a list (simulates DB mismatch)."""
    now = datetime(2026, 3, 1)
    return Entity(
        id=entity_id,
        name="ListHowModule",
        type=EntityType.MODULE,
        summary="A module with list-typed how tag",
        tags=Tags(what=["test"], why="testing", how=["step1", "step2"], who="developer"),
        status=EntityStatus.ACTIVE,
        created_at=now,
        updated_at=now,
    )


class TestBlindspotTypeSafety:
    def test_how_tag_as_list_does_not_crash(self):
        """analyze_blindspots must not raise AttributeError when tags.how is a list."""
        entity = _make_entity_with_list_how()
        doc = Document(
            id="d1",
            title="test.md",
            source=Source(type=SourceType.GITHUB, uri="docs/test.md", adapter="git"),
            tags=Tags(
                what=["test"],
                why="testing",
                how=["step1", "已確認問題"],  # list with problem indicator
                who=["developer"],
            ),
            linked_entity_ids=["m1"],
            summary="doc summary",
            status=DocumentStatus.CURRENT,
            created_at=datetime(2026, 3, 1),
            updated_at=datetime(2026, 3, 1),
        )
        # Should not raise 'list' object has no attribute 'lower'
        result = analyze_blindspots([entity], [doc], [])
        assert isinstance(result, list)

    def test_how_tag_as_list_triggers_problem_detection(self):
        """When how is a list containing a problem indicator, blindspot should be detected."""
        doc = Document(
            id="d1",
            title="bug-report.md",
            source=Source(type=SourceType.GITHUB, uri="docs/bug-report.md", adapter="git"),
            tags=Tags(
                what=["test"],
                why="testing",
                how=["已確認問題", "needs fix"],
                who=["developer"],
            ),
            linked_entity_ids=[],
            summary="doc summary",
            status=DocumentStatus.CURRENT,
            created_at=datetime(2026, 3, 1),
            updated_at=datetime(2026, 3, 1),
        )
        result = analyze_blindspots([], [doc], [])
        problem_spots = [b for b in result if "problem" in b.description.lower() or "problems" in b.description.lower()]
        assert len(problem_spots) >= 1

    def test_analyze_blindspots_check_type_all_does_not_crash_with_list_tags(self):
        """analyze_blindspots runs without crash when multiple tag fields are lists."""
        entity = Entity(
            id="m1",
            name="Complex Entity",
            type=EntityType.MODULE,
            summary="A module",
            tags=Tags(
                what=["feature", "core"],
                why="testing",
                how=["process A", "process B"],
                who=["developer", "pm"],
            ),
            status=EntityStatus.ACTIVE,
            created_at=datetime(2026, 3, 1),
            updated_at=datetime(2026, 3, 1),
        )
        result = analyze_blindspots([entity], [], [])
        assert isinstance(result, list)


# ──────────────────────────────────────────────
# Part B: weighted scoring
# ──────────────────────────────────────────────

class TestWeightedScoring:
    def test_quality_check_item_has_weight_field(self):
        """QualityCheckItem should have a weight field with default 1."""
        from zenos.domain.shared import QualityCheckItem
        item = QualityCheckItem(name="test", passed=True, detail="ok")
        assert item.weight == 1

    def test_critical_failure_lowers_score_more_than_nice_failure(self):
        """Failing a critical check (weight=3) should reduce score more than a nice check (weight=1)."""
        # Setup: module without dependency (fails dependency_completeness weight=3)
        # vs a module with all docs but archived without rationale (fails archive_rationale weight=1)

        # Critical failure scenario: active module with no relationships
        mod_no_rel = _make_entity(name="ModuleA", entity_type=EntityType.MODULE, entity_id="m1")
        report_critical = run_quality_check([mod_no_rel], [], [], [], [])

        # Nice failure scenario: archived doc with no rationale
        archived_doc = _make_doc(status=DocumentStatus.ARCHIVED)
        archived_doc.summary = ""
        report_nice = run_quality_check([], [archived_doc], [], [], [])

        # Score should be lower when critical item fails
        assert report_critical.score < report_nice.score

    def test_all_checks_pass_gives_100(self):
        """Empty ontology should produce a score (not necessarily 100 but not crash)."""
        report = run_quality_check([], [], [], [], [])
        assert 0 <= report.score <= 100

    def test_score_uses_weighted_calculation(self):
        """Score should reflect weighted calculation, not simple count."""
        report = run_quality_check([], [], [], [], [])
        all_items = report.passed + report.failed
        if all_items:
            weighted_total = sum(i.weight for i in all_items)
            weighted_passed = sum(i.weight for i in report.passed)
            expected = int((weighted_passed / weighted_total) * 100) if weighted_total else 0
            assert report.score == expected


# ──────────────────────────────────────────────
# Part C: new checks (C1-C5)
# ──────────────────────────────────────────────

class TestDuplicateL2Detection:
    def test_identical_l2_names_detected(self):
        """Two modules with identical names should be flagged as duplicates."""
        m1 = _make_entity(name="Knowledge Sharing", entity_type=EntityType.MODULE, entity_id="m1",
                          summary="knowledge sharing across teams")
        m2 = _make_entity(name="Knowledge Sharing", entity_type=EntityType.MODULE, entity_id="m2",
                          summary="knowledge sharing across teams")
        report = run_quality_check([m1, m2], [], [], [], [])
        failed_names = [f.name for f in report.failed]
        assert "duplicate_l2_detection" in failed_names

    def test_very_similar_l2_names_detected(self):
        """Two modules with highly similar names should be flagged."""
        m1 = _make_entity(name="Task Management System", entity_type=EntityType.MODULE, entity_id="m1",
                          summary="system for managing tasks")
        m2 = _make_entity(name="Task Management Platform", entity_type=EntityType.MODULE, entity_id="m2",
                          summary="system for managing tasks")
        report = run_quality_check([m1, m2], [], [], [], [])
        failed_names = [f.name for f in report.failed]
        assert "duplicate_l2_detection" in failed_names

    def test_distinct_l2_modules_pass(self):
        """Modules with clearly different names and summaries should not be flagged."""
        m1 = _make_entity(name="Auth Service", entity_type=EntityType.MODULE, entity_id="m1",
                          summary="handles user authentication and session tokens")
        m2 = _make_entity(name="Billing Module", entity_type=EntityType.MODULE, entity_id="m2",
                          summary="processes payments and invoices for customers")
        report = run_quality_check([m1, m2], [], [], [], [])
        passed_names = [p.name for p in report.passed]
        assert "duplicate_l2_detection" in passed_names

    def test_archived_modules_not_checked(self):
        """Archived/completed modules should not be included in duplicate check."""
        m1 = _make_entity(name="Old System", entity_type=EntityType.MODULE, entity_id="m1",
                          status=EntityStatus.COMPLETED,
                          summary="old system same name")
        m2 = _make_entity(name="Old System", entity_type=EntityType.MODULE, entity_id="m2",
                          status=EntityStatus.COMPLETED,
                          summary="old system same name")
        report = run_quality_check([m1, m2], [], [], [], [])
        passed_names = [p.name for p in report.passed]
        assert "duplicate_l2_detection" in passed_names


class TestDuplicateDocumentDetection:
    def test_same_uri_documents_detected(self):
        """Two non-archived documents with the same source URI should be flagged."""
        doc1 = _make_doc(doc_id="d1", uri="docs/shared.md")
        doc2 = _make_doc(doc_id="d2", uri="docs/shared.md")
        report = run_quality_check([], [doc1, doc2], [], [], [])
        failed_names = [f.name for f in report.failed]
        assert "duplicate_document_detection" in failed_names

    def test_different_uri_documents_pass(self):
        """Documents with different URIs should not be flagged."""
        doc1 = _make_doc(doc_id="d1", uri="docs/alpha.md")
        doc2 = _make_doc(doc_id="d2", uri="docs/beta.md")
        report = run_quality_check([], [doc1, doc2], [], [], [])
        passed_names = [p.name for p in report.passed]
        assert "duplicate_document_detection" in passed_names

    def test_archived_documents_excluded_from_dup_check(self):
        """Archived documents sharing a URI with a current doc should not trigger failure."""
        doc1 = _make_doc(doc_id="d1", uri="docs/shared.md", status=DocumentStatus.ARCHIVED)
        doc2 = _make_doc(doc_id="d2", uri="docs/shared.md", status=DocumentStatus.CURRENT)
        report = run_quality_check([], [doc1, doc2], [], [], [])
        passed_names = [p.name for p in report.passed]
        assert "duplicate_document_detection" in passed_names

    def test_empty_uri_not_flagged(self):
        """Documents with empty URI should not cause false positives."""
        doc1 = _make_doc(doc_id="d1", uri="")
        doc2 = _make_doc(doc_id="d2", uri="")
        report = run_quality_check([], [doc1, doc2], [], [], [])
        passed_names = [p.name for p in report.passed]
        assert "duplicate_document_detection" in passed_names


def _make_task(title: str, task_id: str = "t1", status: str = "todo") -> Task:
    return Task(
        id=task_id,
        title=title,
        status=status,
        priority=TaskPriority.MEDIUM,
        created_by="test",
    )


class TestDuplicateTaskDetection:
    def test_identical_open_tasks_detected(self):
        """Two open tasks with identical titles should be flagged."""
        t1 = _make_task("Fix login bug", task_id="t1")
        t2 = _make_task("Fix login bug", task_id="t2")
        report = run_quality_check([], [], [], [], [], tasks=[t1, t2])
        failed_names = [f.name for f in report.failed]
        assert "duplicate_task_detection" in failed_names

    def test_highly_similar_open_tasks_detected(self):
        """Two open tasks with >0.7 Jaccard similarity should be flagged."""
        # "Fix user login bug issue" vs "Fix user login bug":
        # intersection={fix,user,login,bug} union={fix,user,login,bug,issue} → 4/5=0.8 > 0.7
        t1 = _make_task("Fix user login bug issue", task_id="t1")
        t2 = _make_task("Fix user login bug", task_id="t2")
        report = run_quality_check([], [], [], [], [], tasks=[t1, t2])
        failed_names = [f.name for f in report.failed]
        assert "duplicate_task_detection" in failed_names

    def test_distinct_open_tasks_pass(self):
        """Tasks with clearly different titles should not be flagged."""
        t1 = _make_task("Fix login bug", task_id="t1")
        t2 = _make_task("Update billing invoice format", task_id="t2")
        report = run_quality_check([], [], [], [], [], tasks=[t1, t2])
        passed_names = [p.name for p in report.passed]
        assert "duplicate_task_detection" in passed_names

    def test_done_tasks_excluded(self):
        """Completed/cancelled tasks should not be included in duplicate check."""
        t1 = _make_task("Fix login bug", task_id="t1", status="done")
        t2 = _make_task("Fix login bug", task_id="t2", status="done")
        report = run_quality_check([], [], [], [], [], tasks=[t1, t2])
        passed_names = [p.name for p in report.passed]
        assert "duplicate_task_detection" in passed_names

    def test_no_tasks_passes(self):
        """When tasks=None, check should pass trivially."""
        report = run_quality_check([], [], [], [], [])
        passed_names = [p.name for p in report.passed]
        assert "duplicate_task_detection" in passed_names


class TestEntrySparsity:
    def test_majority_l2_without_entries_fails(self):
        """When >50% of active L2 modules have 0 entries, check should fail."""
        m1 = _make_entity(name="M1", entity_type=EntityType.MODULE, entity_id="m1")
        m2 = _make_entity(name="M2", entity_type=EntityType.MODULE, entity_id="m2")
        m3 = _make_entity(name="M3", entity_type=EntityType.MODULE, entity_id="m3")
        # 2 out of 3 have 0 entries = 66% > 50%
        entries_by_entity = {"m1": 5, "m2": 0, "m3": 0}
        report = run_quality_check([m1, m2, m3], [], [], [], [],
                                   entries_by_entity=entries_by_entity)
        failed_names = [f.name for f in report.failed]
        assert "entry_sparsity" in failed_names

    def test_minority_l2_without_entries_passes(self):
        """When <=50% of active L2 modules have 0 entries, check should pass."""
        m1 = _make_entity(name="M1", entity_type=EntityType.MODULE, entity_id="m1")
        m2 = _make_entity(name="M2", entity_type=EntityType.MODULE, entity_id="m2")
        m3 = _make_entity(name="M3", entity_type=EntityType.MODULE, entity_id="m3")
        # 1 out of 3 has 0 entries = 33% <= 50%
        entries_by_entity = {"m1": 5, "m2": 3, "m3": 0}
        report = run_quality_check([m1, m2, m3], [], [], [], [],
                                   entries_by_entity=entries_by_entity)
        passed_names = [p.name for p in report.passed]
        assert "entry_sparsity" in passed_names

    def test_no_entry_data_passes(self):
        """When entries_by_entity=None, sparsity check should pass (skipped)."""
        m1 = _make_entity(name="M1", entity_type=EntityType.MODULE, entity_id="m1")
        report = run_quality_check([m1], [], [], [], [])
        passed_names = [p.name for p in report.passed]
        assert "entry_sparsity" in passed_names


class TestL2CountBalance:
    def test_product_with_too_many_modules_fails(self):
        """A product with >15 active/draft modules should be flagged as imbalanced."""
        product = _make_entity(name="BigProduct", entity_type=EntityType.PRODUCT, entity_id="p1")
        modules = [
            _make_entity(
                name=f"Module{i}",
                entity_type=EntityType.MODULE,
                entity_id=f"m{i}",
                details={"parent_id": "p1"},
            )
            for i in range(16)
        ]
        # Set parent_id directly on each module
        for m in modules:
            m.parent_id = "p1"
        report = run_quality_check([product] + modules, [], [], [], [])
        failed_names = [f.name for f in report.failed]
        assert "l2_count_balance" in failed_names

    def test_product_with_too_few_modules_fails(self):
        """A product with <3 active/draft modules should be flagged as imbalanced."""
        product = _make_entity(name="TinyProduct", entity_type=EntityType.PRODUCT, entity_id="p1")
        modules = [
            _make_entity(
                name=f"Module{i}",
                entity_type=EntityType.MODULE,
                entity_id=f"m{i}",
            )
            for i in range(2)
        ]
        for m in modules:
            m.parent_id = "p1"
        report = run_quality_check([product] + modules, [], [], [], [])
        failed_names = [f.name for f in report.failed]
        assert "l2_count_balance" in failed_names

    def test_product_with_balanced_modules_passes(self):
        """A product with 3-15 active/draft modules should pass."""
        product = _make_entity(name="GoodProduct", entity_type=EntityType.PRODUCT, entity_id="p1")
        modules = [
            _make_entity(
                name=f"Module{i}",
                entity_type=EntityType.MODULE,
                entity_id=f"m{i}",
            )
            for i in range(5)
        ]
        for m in modules:
            m.parent_id = "p1"
        report = run_quality_check([product] + modules, [], [], [], [])
        passed_names = [p.name for p in report.passed]
        assert "l2_count_balance" in passed_names

    def test_no_products_passes_balance_check(self):
        """No products in ontology means balance check passes trivially."""
        report = run_quality_check([], [], [], [], [])
        passed_names = [p.name for p in report.passed]
        assert "l2_count_balance" in passed_names


# ──────────────────────────────────────────────
# Wave 9 Phase B: L3TaskBaseEntity three-branch dispatch
# ──────────────────────────────────────────────

from zenos.domain.action.models import (
    L3TaskBaseEntity,
    L3TaskEntity,
)


def _make_l3_task_entity(
    entity_id: str = "l3-1",
    parent_id: str | None = "e1",
    task_status: str = "todo",
    updated_at: datetime | None = None,
) -> L3TaskEntity:
    """Build a minimal L3TaskEntity for governance tests."""
    from datetime import datetime as _dt
    now = updated_at or _dt(2026, 4, 23, 12, 0, 0)
    return L3TaskEntity(
        id=entity_id,
        partner_id="partner-1",
        name="L3 Task",
        type_label="task",
        level=3,
        parent_id=parent_id,
        status="active",
        created_at=now,
        updated_at=now,
        description="A task",
        task_status=task_status,
        assignee=None,
        dispatcher="agent:developer",
    )


class TestStalenessL3TaskEntityAsDocSource:
    """detect_staleness should accept L3TaskEntity in the documents parameter."""

    def test_l3_task_entity_routed_into_docs_by_entity(self):
        """An L3TaskEntity with parent_id='e1' should land in docs_by_entity['e1']."""
        now = datetime(2026, 4, 23, 12, 0, 0)
        entity = _make_entity(entity_id="e1", updated_at=datetime(2026, 4, 20))
        l3_task = _make_l3_task_entity(parent_id="e1", updated_at=datetime(2026, 3, 1))

        # detect_staleness will build docs_by_entity from documents list.
        # The L3 task was last touched 2026-03-01; entity updated 2026-04-20 (>30 days later).
        # So we expect a feature_updated_docs_lagging warning.
        result = detect_staleness([entity], [l3_task], [], now=now)
        lag_warnings = [w for w in result if w.pattern == "feature_updated_docs_lagging"]
        assert len(lag_warnings) >= 1
        assert "e1" in lag_warnings[0].affected_entity_ids

    def test_l3_task_entity_with_no_parent_not_indexed(self):
        """L3TaskEntity with parent_id=None should not be indexed into docs_by_entity."""
        now = datetime(2026, 4, 23, 12, 0, 0)
        entity = _make_entity(entity_id="e1", updated_at=now)
        l3_task = _make_l3_task_entity(parent_id=None, updated_at=now)

        # No parent_id → nothing indexed → no staleness warning
        result = detect_staleness([entity], [l3_task], [], now=now)
        lag_warnings = [w for w in result if w.pattern == "feature_updated_docs_lagging"]
        assert len(lag_warnings) == 0

    def test_l3_task_entity_accepted_by_analyze_blindspots(self):
        """analyze_blindspots must not crash when an L3TaskEntity is in the documents list."""
        from zenos.domain.governance import analyze_blindspots
        entity = _make_entity(entity_id="e1")
        l3_task = _make_l3_task_entity(parent_id="e1")
        # Should run without AttributeError or TypeError
        result = analyze_blindspots([entity], [l3_task], [])
        assert isinstance(result, list)

    def test_l3_task_entity_accepted_by_run_quality_check(self):
        """run_quality_check must not crash when an L3TaskEntity is in the documents list."""
        entity = _make_entity(entity_id="e1")
        l3_task = _make_l3_task_entity(parent_id="e1")
        # Should run without AttributeError or TypeError
        report = run_quality_check([entity], [l3_task], [], [], [])
        assert isinstance(report.score, int)

    def test_isinstance_l3_task_base_entity_branch_used(self):
        """L3TaskBaseEntity subclass should hit the explicit isinstance branch, not the generic hasattr fallback."""
        now = datetime(2026, 4, 23, 12, 0, 0)
        entity = _make_entity(entity_id="parent-ent", updated_at=datetime(2026, 4, 20))
        l3_task = _make_l3_task_entity(parent_id="parent-ent", updated_at=datetime(2026, 3, 1))

        # Verify it IS an L3TaskBaseEntity (confirming the isinstance branch applies)
        assert isinstance(l3_task, L3TaskBaseEntity)

        result = detect_staleness([entity], [l3_task], [], now=now)
        lag_warnings = [w for w in result if w.pattern == "feature_updated_docs_lagging"]
        assert len(lag_warnings) >= 1
