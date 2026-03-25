from __future__ import annotations

from unittest.mock import AsyncMock

from zenos.application.governance_service import GovernanceService
from zenos.domain.models import Entity, Relationship, Tags


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

