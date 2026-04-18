"""Bug repro: entity.sources must count toward core coverage.

Before fix: entity with 2+ sources and 0 linked documents triggered red blindspot.
After fix: combined coverage (linked_docs + sources) >= 2 must NOT trigger.
"""
from __future__ import annotations

from zenos.domain.governance import analyze_blindspots
from zenos.domain.knowledge import (
    Entity,
    EntityStatus,
    EntityType,
    Tags,
)


def _make_core_entity(
    entity_id: str,
    name: str,
    sources: list[dict],
    entity_type: str = EntityType.MODULE,
) -> Entity:
    return Entity(
        id=entity_id,
        name=name,
        type=entity_type,
        status=EntityStatus.ACTIVE,
        summary="Test entity",
        tags=Tags(what="test", why="testing", how="automated", who="developer"),
        sources=sources,
        parent_id=None,
    )


def test_core_entity_with_two_external_sources_not_flagged():
    """Core module with 2+ sources should not produce coverage blindspot."""
    entity = _make_core_entity(
        entity_id="e1",
        name="Test Module",
        sources=[
            {"uri": "https://docs.google.com/doc1", "type": "gdoc"},
            {"uri": "https://docs.google.com/doc2", "type": "gdoc"},
        ],
    )
    blindspots = analyze_blindspots([entity], [], [])
    coverage_bs = [b for b in blindspots if "coverage" in b.description.lower()]
    assert len(coverage_bs) == 0, (
        f"Should not flag entity with 2 external sources; got: {coverage_bs}"
    )


def test_core_product_with_two_external_sources_not_flagged():
    """Core product with 2+ sources should also not produce coverage blindspot."""
    entity = _make_core_entity(
        entity_id="e2",
        name="Test Product",
        sources=[
            {"uri": "https://github.com/repo1", "type": "github"},
            {"uri": "https://github.com/repo2", "type": "github"},
            {"uri": "https://github.com/repo3", "type": "github"},
        ],
        entity_type=EntityType.PRODUCT,
    )
    blindspots = analyze_blindspots([entity], [], [])
    coverage_bs = [b for b in blindspots if "coverage" in b.description.lower()]
    assert len(coverage_bs) == 0, (
        f"Should not flag product with 3 sources; got: {coverage_bs}"
    )


def test_core_entity_with_zero_sources_and_zero_docs_still_flagged():
    """Regression guard: entity with 0 sources AND 0 docs must still produce blindspot."""
    entity = _make_core_entity(
        entity_id="e3",
        name="Empty Module",
        sources=[],
    )
    blindspots = analyze_blindspots([entity], [], [])
    coverage_bs = [
        b for b in blindspots
        if "combined coverage" in b.description.lower()
        or "adequate coverage" in b.description.lower()
    ]
    assert len(coverage_bs) == 1, (
        f"Should flag entity with 0 sources and 0 docs; got: {coverage_bs}"
    )


def test_core_entity_with_one_source_and_zero_docs_still_flagged():
    """Entity with combined coverage=1 (1 source, 0 docs) must still be flagged."""
    entity = _make_core_entity(
        entity_id="e4",
        name="Sparse Module",
        sources=[{"uri": "https://docs.google.com/only-one", "type": "gdoc"}],
    )
    blindspots = analyze_blindspots([entity], [], [])
    coverage_bs = [
        b for b in blindspots
        if "combined coverage" in b.description.lower()
        or "adequate coverage" in b.description.lower()
    ]
    assert len(coverage_bs) == 1, (
        f"Should flag entity with combined coverage=1; got: {coverage_bs}"
    )


def test_core_entity_with_sources_missing_uri_not_counted():
    """Sources without a 'uri' key must not count toward coverage."""
    entity = _make_core_entity(
        entity_id="e5",
        name="Bad Sources Module",
        sources=[
            {"label": "no uri here"},
            {"label": "also no uri"},
        ],
    )
    blindspots = analyze_blindspots([entity], [], [])
    coverage_bs = [
        b for b in blindspots
        if "combined coverage" in b.description.lower()
        or "adequate coverage" in b.description.lower()
    ]
    assert len(coverage_bs) == 1, (
        f"Sources without uri should not count; entity should still be flagged; got: {coverage_bs}"
    )
