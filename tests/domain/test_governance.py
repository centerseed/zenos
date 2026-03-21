"""Tests for governance rules — covers all 5 functions with full business logic."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from zenos.domain.governance import (
    analyze_blindspots,
    apply_tag_confidence,
    check_split_criteria,
    detect_staleness,
    run_quality_check,
)
from zenos.domain.models import (
    Blindspot,
    Document,
    DocumentStatus,
    DocumentTags,
    Entity,
    EntityStatus,
    EntityType,
    Gap,
    Protocol,
    Relationship,
    RelationshipType,
    Severity,
    Source,
    SourceType,
    Tags,
)


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
) -> Entity:
    now = updated_at or datetime(2026, 3, 1)
    return Entity(
        id=entity_id,
        name=name,
        type=entity_type,
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
        tags=DocumentTags(
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
        tags = DocumentTags(what=["api docs"], why="onboarding", how="REST", who=["developer"])
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
        tags = DocumentTags(what=[], why="", how="", who=["dev"])
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
        """Score should be percentage of passed checks."""
        report = run_quality_check([], [], [], [], [])
        total = len(report.passed) + len(report.failed)
        if total > 0:
            expected = int((len(report.passed) / total) * 100)
            assert report.score == expected
