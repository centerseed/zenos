"""Tests for PolicySuggestionService.

All tests use mock repositories — no external service dependencies.
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock

from zenos.application.policy_suggestion_service import PolicySuggestionService
from zenos.domain.models import Entity, Tags


# ── Helpers ──────────────────────────────────────────────────────────────────


def _entity(**overrides) -> Entity:
    defaults = dict(
        id="ent-default",
        name="Default Entity",
        type="module",
        summary="",
        tags=Tags(what=["x"], why="y", how="z", who=["all"]),
        status="active",
        level=2,
        visibility="public",
        parent_id=None,
    )
    defaults.update(overrides)
    return Entity(**defaults)


def _make_repo(entity: Entity | None) -> AsyncMock:
    repo = AsyncMock()
    repo.get_by_id = AsyncMock(return_value=entity)
    return repo


# ── Tests ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_finance_keyword_suggests_restricted():
    """Entity name containing '薪資' should yield restricted with risk_score=0.7."""
    ent = _entity(id="ent-1", name="薪資結構說明", summary="")
    repo = _make_repo(ent)
    svc = PolicySuggestionService(entity_repo=repo)

    result = await svc.suggest("ent-1")

    assert result["entity_id"] == "ent-1"
    assert result["suggested_visibility"] == "restricted"
    assert result["risk_score"] == 0.7


@pytest.mark.asyncio
async def test_hr_keyword_english_suggests_restricted():
    """Entity name containing 'hr' should yield restricted (case-insensitive)."""
    ent = _entity(id="ent-2", name="HR Onboarding Process", summary="")
    repo = _make_repo(ent)
    svc = PolicySuggestionService(entity_repo=repo)

    result = await svc.suggest("ent-2")

    assert result["suggested_visibility"] == "restricted"
    assert result["risk_score"] == 0.7


@pytest.mark.asyncio
async def test_l3_entity_inherits_parent_visibility():
    """L3 entity with a parent should inherit the parent's visibility."""
    parent = _entity(id="parent-1", name="Parent Module", level=2, visibility="restricted")
    child = _entity(id="child-1", name="Child Detail", level=3, parent_id="parent-1", visibility="public")

    repo = AsyncMock()
    repo.get_by_id = AsyncMock(side_effect=lambda eid: {
        "child-1": child,
        "parent-1": parent,
    }.get(eid))

    svc = PolicySuggestionService(entity_repo=repo)
    result = await svc.suggest("child-1")

    assert result["suggested_visibility"] == "restricted"
    assert result["risk_score"] == 0.2
    assert "繼承" in result["reason"]


@pytest.mark.asyncio
async def test_l3_entity_no_parent_fallback_public():
    """L3 entity without parent_id should fall back to public."""
    ent = _entity(id="ent-3", name="Orphan Detail", level=3, parent_id=None)
    repo = _make_repo(ent)
    svc = PolicySuggestionService(entity_repo=repo)

    result = await svc.suggest("ent-3")

    assert result["suggested_visibility"] == "public"
    assert result["risk_score"] == 0.0


@pytest.mark.asyncio
async def test_general_entity_suggests_public():
    """Regular L2 entity with no sensitive keywords should suggest public with risk_score=0.0."""
    ent = _entity(id="ent-4", name="Product Roadmap Overview", summary="General roadmap", level=2)
    repo = _make_repo(ent)
    svc = PolicySuggestionService(entity_repo=repo)

    result = await svc.suggest("ent-4")

    assert result["entity_id"] == "ent-4"
    assert result["suggested_visibility"] == "public"
    assert result["risk_score"] == 0.0


@pytest.mark.asyncio
async def test_document_type_with_sensitive_name_triggers_rule1():
    """Entity with type='document' and sensitive name triggers rule 1 (restricted), not rule 2."""
    parent = _entity(id="parent-2", name="Legal Documents", level=2, visibility="confidential")
    doc = _entity(
        id="doc-1",
        name="Contract Draft",  # "contract" is a sensitive keyword → rule 1 fires
        type="document",
        level=3,
        parent_id="parent-2",
        visibility="public",
    )

    repo = AsyncMock()
    repo.get_by_id = AsyncMock(side_effect=lambda eid: {
        "doc-1": doc,
        "parent-2": parent,
    }.get(eid))

    svc = PolicySuggestionService(entity_repo=repo)
    result = await svc.suggest("doc-1")

    # Rule 1 (sensitive keyword) takes priority over rule 2 (inherit)
    assert result["suggested_visibility"] == "restricted"
    assert result["risk_score"] == 0.7


@pytest.mark.asyncio
async def test_document_type_inherits_parent_non_sensitive():
    """type='document' entity (non-sensitive name) inherits parent visibility=confidential."""
    parent = _entity(id="parent-3", name="Archive", level=2, visibility="confidential")
    doc = _entity(
        id="doc-2",
        name="Meeting Notes 2024",
        type="document",
        level=3,
        parent_id="parent-3",
        visibility="public",
    )

    repo = AsyncMock()
    repo.get_by_id = AsyncMock(side_effect=lambda eid: {
        "doc-2": doc,
        "parent-3": parent,
    }.get(eid))

    svc = PolicySuggestionService(entity_repo=repo)
    result = await svc.suggest("doc-2")

    assert result["suggested_visibility"] == "confidential"
    assert result["risk_score"] == 0.2
    assert "繼承" in result["reason"]


@pytest.mark.asyncio
async def test_entity_not_found_returns_public():
    """When entity is not found, return public with risk_score=0.0."""
    repo = _make_repo(None)
    svc = PolicySuggestionService(entity_repo=repo)

    result = await svc.suggest("nonexistent-id")

    assert result["entity_id"] == "nonexistent-id"
    assert result["suggested_visibility"] == "public"
    assert result["risk_score"] == 0.0


@pytest.mark.asyncio
async def test_summary_contains_sensitive_keyword():
    """Sensitive keyword in summary (not name) should also trigger restricted."""
    ent = _entity(id="ent-5", name="Q4 Planning", summary="Includes salary bands and finance projections")
    repo = _make_repo(ent)
    svc = PolicySuggestionService(entity_repo=repo)

    result = await svc.suggest("ent-5")

    assert result["suggested_visibility"] == "restricted"
    assert result["risk_score"] == 0.7
