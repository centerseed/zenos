from __future__ import annotations

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock

from zenos.application.knowledge.governance_service import GovernanceService
from zenos.application.knowledge.ontology_service import OntologyService
from zenos.domain.governance import run_quality_check
from zenos.domain.knowledge import Entity, Relationship, RelationshipType, Tags


def _entity(**overrides) -> Entity:
    defaults = dict(
        id="ent-1",
        name="ZenOS",
        type="product",
        summary="AI context layer",
        tags=Tags(what=["platform"], why="shared context", how="mcp", who=["pm"]),
        status="active",
    )
    defaults.update(overrides)
    return Entity(**defaults)


async def test_infer_l2_backfill_proposals_flags_missing_impacts_and_technical_summary():
    product = _entity(id="prod-1", name="ZenOS", type="product")
    module_a = _entity(
        id="mod-a",
        name="Ontology Engine",
        type="module",
        parent_id="prod-1",
        summary="Uses API and schema rules to coordinate governance",
        tags=Tags(what=["governance", "context"], why="keep ontology consistent", how="pipeline", who=["pm", "developer"]),
    )
    module_b = _entity(
        id="mod-b",
        name="Action Layer",
        type="module",
        parent_id="prod-1",
        summary="Turns knowledge into actions",
        tags=Tags(what=["governance", "tasks"], why="execute work", how="workflow", who=["pm"]),
    )
    doc = _entity(
        id="doc-1",
        name="SPEC-l2-entity-redefinition.md",
        type="document",
        parent_id="mod-a",
        summary="Defines company-consensus L2 concept",
        tags=Tags(what=["governance"], why="guide redesign", how="spec", who=["architect"]),
        sources=[{"uri": "docs/specs/SPEC-l2-entity-redefinition.md"}],
        status="current",
    )

    entity_repo = AsyncMock()
    entity_repo.list_all = AsyncMock(return_value=[product, module_a, module_b, doc])
    relationship_repo = AsyncMock()
    relationship_repo.list_by_entity = AsyncMock(return_value=[])
    protocol_repo = AsyncMock()
    blindspot_repo = AsyncMock()

    service = GovernanceService(
        entity_repo=entity_repo,
        relationship_repo=relationship_repo,
        protocol_repo=protocol_repo,
        blindspot_repo=blindspot_repo,
    )

    proposals = await service.infer_l2_backfill_proposals()

    assert len(proposals) == 2
    target = next(p for p in proposals if p["entity_id"] == "mod-a")
    assert any("缺少具體 impacts" in issue for issue in target["issues"])
    assert any("技術語言" in issue for issue in target["issues"])
    assert target["candidate_impacts"][0]["target_id"] == "mod-b"
    assert "→" in target["candidate_impacts"][0]["description"]
    assert target["source_documents"][0]["id"] == "doc-1"


async def test_run_quality_correction_priority_returns_correct_structure():
    """DC-9 & DC-10: run_quality_correction_priority returns ranked list and needs_immediate_review."""
    module_a = _entity(
        id="mod-a",
        name="High Priority Module",
        type="module",
        status="draft",
        summary="Short",  # short summary → high score
        tags=Tags(what=["x"], why="", how="", who=["pm"]),  # no why/how → high 3Q score
        parent_id="prod-1",
    )
    module_b = _entity(
        id="mod-b",
        name="Low Priority Module",
        type="module",
        status="active",
        summary="Uses LLM for inference with API calls",  # tech terms → score 0
        tags=Tags(what=["x"], why="revenue reason", how="pipeline", who=["pm"]),  # has why+how
        parent_id="prod-1",
    )

    entity_repo = AsyncMock()
    entity_repo.list_all = AsyncMock(return_value=[module_a, module_b])
    relationship_repo = AsyncMock()
    relationship_repo.list_by_entity = AsyncMock(return_value=[])

    service = GovernanceService(
        entity_repo=entity_repo,
        relationship_repo=relationship_repo,
        protocol_repo=AsyncMock(),
        blindspot_repo=AsyncMock(),
    )

    result = await service.run_quality_correction_priority()

    assert "total_l2_entities" in result
    assert "ranked" in result
    assert "needs_immediate_review" in result
    assert result["total_l2_entities"] == 2
    # module_a should be ranked first (higher score)
    assert result["ranked"][0]["entity_id"] == "mod-a"
    # needs_immediate_review counts score > 1.5
    assert result["needs_immediate_review"] >= 0


async def test_run_staleness_check_returns_dict_with_consistency_warnings():
    """run_staleness_check now returns dict with both staleness and document_consistency_warnings."""
    entity_repo = AsyncMock()
    entity_repo.list_all = AsyncMock(return_value=[])
    relationship_repo = AsyncMock()
    relationship_repo.list_by_entity = AsyncMock(return_value=[])

    service = GovernanceService(
        entity_repo=entity_repo,
        relationship_repo=relationship_repo,
        protocol_repo=AsyncMock(),
        blindspot_repo=AsyncMock(),
    )

    result = await service.run_staleness_check()

    assert "warnings" in result
    assert "document_consistency_warnings" in result
    assert isinstance(result["warnings"], list)
    assert isinstance(result["document_consistency_warnings"], list)


async def test_run_quality_check_scopes_to_entity_subtree_without_global_noise():
    product = _entity(id="prod-1", name="Dogfood", type="product", level=1)
    module = _entity(
        id="mod-1",
        name="Dogfood MCP Friction",
        type="module",
        level=2,
        parent_id="prod-1",
        summary="Dogfood MCP Friction captures tool contract issues that block agent governance decisions.",
    )
    other_product = _entity(id="prod-2", name="Other Product", type="product", level=1)
    other_module = _entity(
        id="mod-2",
        name="Other Module",
        type="module",
        level=2,
        parent_id="prod-2",
        summary="Other Module should not appear in scoped Dogfood quality details.",
    )
    rel = Relationship(
        id="rel-1",
        source_entity_id="mod-1",
        target_id="mod-2",
        type="impacts",
        description="Dogfood MCP contract changes -> Other Module reviews tool response compatibility",
    )

    entity_repo = AsyncMock()
    entity_repo.list_all = AsyncMock(return_value=[product, module, other_product, other_module])
    relationship_repo = AsyncMock()
    relationship_repo.list_by_entity = AsyncMock(
        side_effect=lambda entity_id: [rel] if entity_id in {"mod-1", "mod-2"} else []
    )
    protocol_repo = AsyncMock()
    protocol_repo.get_by_entity = AsyncMock(return_value=None)
    blindspot_repo = AsyncMock()
    blindspot_repo.list_all = AsyncMock(return_value=[])

    service = GovernanceService(
        entity_repo=entity_repo,
        relationship_repo=relationship_repo,
        protocol_repo=protocol_repo,
        blindspot_repo=blindspot_repo,
    )

    report = await service.run_quality_check(entity_id="prod-1")
    details = " ".join(item.detail for item in [*report.failed, *report.warnings, *report.passed])

    assert report.metadata["scope"]["entity_id"] == "prod-1"
    assert report.metadata["scope"]["entity_count"] == 2
    assert "Other Product" not in details
    assert "Other Module" not in details


def test_quality_check_counts_l3_document_relationship_links_for_bundle_first_coverage():
    module = _entity(
        id="mod-1",
        name="Order Fulfillment",
        type="module",
        parent_id="prod-1",
        summary="Coordinates order delivery work across operations and support.",
    )
    doc = _entity(
        id="doc-1",
        name="Order Fulfillment Knowledge Index",
        type="document",
        parent_id="other-mod",
        summary="Bundle entry for order fulfillment decisions and tests.",
        status="current",
    )
    rel = Relationship(
        id="rel-1",
        source_entity_id="doc-1",
        target_id="mod-1",
        type=RelationshipType.RELATED_TO,
        description="Document index covers Order Fulfillment governance decisions",
    )

    report = run_quality_check(
        entities=[module],
        documents=[doc],
        protocols=[],
        blindspots=[],
        relationships=[rel],
    )

    split_check = next(item for item in [*report.passed, *report.failed] if item.name == "split_granularity")
    assert split_check.passed
    assert "1-10 doc range" in split_check.detail


# ──────────────────────────────────────────────────────────────────────────────
# _build_infer_all_inputs: entity_dicts must only contain PRODUCT + MODULE
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_build_infer_all_inputs_entity_dicts_only_skeleton_types():
    """entity_dicts must only contain PRODUCT and MODULE entities, not DOCUMENT/GOAL/ROLE."""
    product = _entity(id="prod-1", name="ZenOS", type="product")
    module = _entity(id="mod-1", name="Ontology Engine", type="module", parent_id="prod-1")
    goal = _entity(id="goal-1", name="Revenue Goal", type="goal")
    role = _entity(id="role-1", name="PM", type="role")
    doc = _entity(
        id="doc-1",
        name="spec.md",
        type="document",
        parent_id="mod-1",
        sources=[{"uri": "docs/spec.md"}],
    )

    relationship_repo = AsyncMock()
    relationship_repo.list_by_entity = AsyncMock(return_value=[])

    service = OntologyService(
        entity_repo=AsyncMock(),
        relationship_repo=relationship_repo,
        document_repo=AsyncMock(),
        protocol_repo=AsyncMock(),
        blindspot_repo=AsyncMock(),
    )

    entity_dicts, unlinked_dicts = await service._build_infer_all_inputs(
        all_entities=[product, module, goal, role, doc]
    )

    entity_ids = {d["id"] for d in entity_dicts}
    assert "prod-1" in entity_ids, "PRODUCT must be in entity_dicts"
    assert "mod-1" in entity_ids, "MODULE must be in entity_dicts"
    assert "goal-1" not in entity_ids, "GOAL must not be in entity_dicts"
    assert "role-1" not in entity_ids, "ROLE must not be in entity_dicts"
    assert "doc-1" not in entity_ids, "DOCUMENT must not be in entity_dicts"

    # DOCUMENT should still appear in unlinked_dicts (the doc_entities path)
    unlinked_ids = {d["id"] for d in unlinked_dicts}
    assert "doc-1" in unlinked_ids, "DOCUMENT must still appear in unlinked_dicts"


@pytest.mark.asyncio
async def test_build_infer_all_inputs_excludes_given_entity_id():
    """exclude_entity_id must remove that entity from entity_dicts."""
    product = _entity(id="prod-1", name="ZenOS", type="product")
    module = _entity(id="mod-1", name="Engine", type="module", parent_id="prod-1")

    relationship_repo = AsyncMock()
    relationship_repo.list_by_entity = AsyncMock(return_value=[])

    service = OntologyService(
        entity_repo=AsyncMock(),
        relationship_repo=relationship_repo,
        document_repo=AsyncMock(),
        protocol_repo=AsyncMock(),
        blindspot_repo=AsyncMock(),
    )

    entity_dicts, _ = await service._build_infer_all_inputs(
        all_entities=[product, module],
        exclude_entity_id="mod-1",
    )

    entity_ids = {d["id"] for d in entity_dicts}
    assert "prod-1" in entity_ids
    assert "mod-1" not in entity_ids
