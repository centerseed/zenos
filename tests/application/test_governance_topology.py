"""Tests for governance topology analysis, verb completeness, and suggest_relationship_verb."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock

from zenos.application.governance_service import GovernanceService, LEVERAGE_THRESHOLD
from zenos.domain.models import (
    Entity,
    EntityType,
    Relationship,
    RelationshipType,
    Tags,
)


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

def _entity(**overrides) -> Entity:
    defaults = dict(
        id="ent-1",
        name="Test Entity",
        type="module",
        summary="A test entity",
        tags=Tags(what=["context"], why="keep context", how="pipeline", who=["pm"]),
        status="active",
    )
    defaults.update(overrides)
    return Entity(**defaults)


def _rel(source_id: str, target_id: str, **overrides) -> Relationship:
    defaults = dict(
        id=f"rel-{source_id}-{target_id}",
        source_entity_id=source_id,
        target_id=target_id,
        type=RelationshipType.IMPACTS,
        description="A impacts B",
    )
    defaults.update(overrides)
    return Relationship(**defaults)


def _make_service(
    entities: list,
    relationships: list | None = None,
    governance_ai=None,
) -> GovernanceService:
    entity_repo = AsyncMock()
    entity_repo.list_all = AsyncMock(return_value=entities)
    relationship_repo = AsyncMock()
    relationship_repo.list_by_entity = AsyncMock(return_value=relationships or [])
    blindspot_repo = AsyncMock()
    blindspot_repo.list_all = AsyncMock(return_value=[])
    blindspot_repo.add = AsyncMock(side_effect=lambda b: b)
    protocol_repo = AsyncMock()
    protocol_repo.list_all = AsyncMock(return_value=[])
    protocol_repo.get_by_entity = AsyncMock(return_value=None)
    return GovernanceService(
        entity_repo=entity_repo,
        relationship_repo=relationship_repo,
        protocol_repo=protocol_repo,
        blindspot_repo=blindspot_repo,
        governance_ai=governance_ai,
    )


# ──────────────────────────────────────────────
# LEVERAGE_THRESHOLD constant
# ──────────────────────────────────────────────

def test_leverage_threshold_constant_is_three():
    assert LEVERAGE_THRESHOLD == 3


# ──────────────────────────────────────────────
# analyze_graph_topology: isolated node
# ──────────────────────────────────────────────

async def test_analyze_graph_topology_detects_isolated_node():
    """An entity with no relationships should be flagged as isolated_node."""
    isolated = _entity(id="iso-1", name="Orphan Module", type="module")
    service = _make_service([isolated], relationships=[])

    issues = await service.analyze_graph_topology()

    isolated_issues = [i for i in issues if i["type"] == "isolated_node"]
    assert len(isolated_issues) == 1
    assert isolated_issues[0]["entity_id"] == "iso-1"
    assert "Orphan Module" in isolated_issues[0]["description"]


async def test_analyze_graph_topology_no_isolated_node_when_connected():
    """An entity connected via a relationship should NOT be flagged as isolated."""
    mod_a = _entity(id="mod-a", name="Module A", type="module")
    mod_b = _entity(id="mod-b", name="Module B", type="module")
    rel = _rel("mod-a", "mod-b")
    service = _make_service([mod_a, mod_b], relationships=[rel])

    issues = await service.analyze_graph_topology()

    isolated_issues = [i for i in issues if i["type"] == "isolated_node"]
    assert len(isolated_issues) == 0


async def test_analyze_graph_topology_parent_child_counts_as_connected():
    """A child linked only by parent_id should not be treated as isolated."""
    product = _entity(id="prod-1", name="Product", type=EntityType.PRODUCT)
    module = _entity(id="mod-1", name="Nested Module", type="module", parent_id="prod-1")
    service = _make_service([product, module], relationships=[])

    issues = await service.analyze_graph_topology()

    isolated_issues = [i for i in issues if i["type"] == "isolated_node"]
    assert not any(i["entity_id"] == "mod-1" for i in isolated_issues)


# ──────────────────────────────────────────────
# analyze_graph_topology: leverage node
# ──────────────────────────────────────────────

async def test_analyze_graph_topology_detects_leverage_node():
    """An entity with out-degree >= LEVERAGE_THRESHOLD should be flagged as leverage_node_no_docs."""
    mod_a = _entity(id="mod-a", name="Hub Module", type="module")
    targets = [_entity(id=f"tgt-{i}", name=f"Target {i}", type="module") for i in range(3)]
    rels = [_rel("mod-a", f"tgt-{i}") for i in range(3)]
    all_entities = [mod_a] + targets
    service = _make_service(all_entities, relationships=rels)

    issues = await service.analyze_graph_topology()

    leverage_issues = [i for i in issues if i["type"] == "leverage_node_no_docs"]
    assert any(i["entity_id"] == "mod-a" for i in leverage_issues)
    hub_issue = next(i for i in leverage_issues if i["entity_id"] == "mod-a")
    assert hub_issue["out_degree"] == 3


async def test_analyze_graph_topology_no_leverage_below_threshold():
    """An entity with out-degree < LEVERAGE_THRESHOLD should NOT be flagged."""
    mod_a = _entity(id="mod-a", name="Small Hub", type="module")
    targets = [_entity(id=f"tgt-{i}", name=f"Target {i}", type="module") for i in range(2)]
    rels = [_rel("mod-a", f"tgt-{i}") for i in range(2)]
    service = _make_service([mod_a] + targets, relationships=rels)

    issues = await service.analyze_graph_topology()

    leverage_issues = [i for i in issues if i["type"] == "leverage_node_no_docs" and i["entity_id"] == "mod-a"]
    assert len(leverage_issues) == 0


# ──────────────────────────────────────────────
# analyze_graph_topology: circular dependency
# ──────────────────────────────────────────────

async def test_analyze_graph_topology_detects_cycle():
    """A → B → C → A should be detected as a circular_dependency."""
    mod_a = _entity(id="mod-a", name="Node A", type="module")
    mod_b = _entity(id="mod-b", name="Node B", type="module")
    mod_c = _entity(id="mod-c", name="Node C", type="module")
    rels = [
        _rel("mod-a", "mod-b"),
        _rel("mod-b", "mod-c"),
        _rel("mod-c", "mod-a"),
    ]
    service = _make_service([mod_a, mod_b, mod_c], relationships=rels)

    issues = await service.analyze_graph_topology()

    cycle_issues = [i for i in issues if i["type"] == "circular_dependency"]
    assert len(cycle_issues) >= 1
    # Should contain node names in description
    assert any("Node" in i["description"] for i in cycle_issues)


async def test_analyze_graph_topology_no_cycle_in_dag():
    """A → B → C (no cycle) should NOT produce circular_dependency."""
    mod_a = _entity(id="mod-a", name="Node A", type="module")
    mod_b = _entity(id="mod-b", name="Node B", type="module")
    mod_c = _entity(id="mod-c", name="Node C", type="module")
    rels = [_rel("mod-a", "mod-b"), _rel("mod-b", "mod-c")]
    service = _make_service([mod_a, mod_b, mod_c], relationships=rels)

    issues = await service.analyze_graph_topology()

    cycle_issues = [i for i in issues if i["type"] == "circular_dependency"]
    assert len(cycle_issues) == 0


# ──────────────────────────────────────────────
# analyze_graph_topology: goal disconnected
# ──────────────────────────────────────────────

async def test_analyze_graph_topology_detects_goal_disconnected():
    """A module with no path to any GOAL entity should be flagged as goal_disconnected."""
    module = _entity(id="mod-1", name="Lost Module", type="module")
    other = _entity(id="other-1", name="Other Module", type="module")
    rel = _rel("mod-1", "other-1")
    service = _make_service([module, other], relationships=[rel])

    issues = await service.analyze_graph_topology()

    goal_issues = [i for i in issues if i["type"] == "goal_disconnected"]
    assert any(i["entity_id"] == "mod-1" for i in goal_issues)


async def test_analyze_graph_topology_no_goal_disconnected_when_reachable():
    """A module that can reach a GOAL entity should NOT be flagged as goal_disconnected."""
    module = _entity(id="mod-1", name="Connected Module", type="module")
    goal = _entity(id="goal-1", name="Revenue Goal", type=EntityType.GOAL)
    rel = _rel("mod-1", "goal-1")
    service = _make_service([module, goal], relationships=[rel])

    issues = await service.analyze_graph_topology()

    goal_issues = [i for i in issues if i["type"] == "goal_disconnected" and i["entity_id"] == "mod-1"]
    assert len(goal_issues) == 0


async def test_analyze_graph_topology_parent_path_to_goal_is_not_disconnected():
    """A module should inherit a valid goal path through its parent hierarchy."""
    goal = _entity(id="goal-1", name="North Star", type=EntityType.GOAL)
    product = _entity(id="prod-1", name="Product", type=EntityType.PRODUCT)
    module = _entity(id="mod-1", name="Child Module", type="module", parent_id="prod-1")
    rel = _rel("prod-1", "goal-1")
    service = _make_service([goal, product, module], relationships=[rel])

    issues = await service.analyze_graph_topology()

    goal_issues = [i for i in issues if i["type"] == "goal_disconnected" and i["entity_id"] == "mod-1"]
    assert len(goal_issues) == 0


async def test_analyze_graph_topology_skips_document_entities():
    """DOCUMENT type entities should not appear in topology analysis."""
    doc = _entity(id="doc-1", name="Some Doc", type=EntityType.DOCUMENT)
    service = _make_service([doc], relationships=[])

    issues = await service.analyze_graph_topology()

    # doc-1 should not appear in any issue
    assert not any(i.get("entity_id") == "doc-1" for i in issues)


# ──────────────────────────────────────────────
# suggest_relationship_verb: happy path
# ──────────────────────────────────────────────

async def test_suggest_relationship_verb_happy_path():
    """When LLM returns valid verbs, they should be returned as a list[str]."""
    from unittest.mock import MagicMock
    from pydantic import BaseModel

    source = _entity(id="src-1", name="Pricing Module")
    target = _entity(id="tgt-1", name="Order Flow")

    # Mock LLM client's chat_structured to return a verbs object
    mock_llm = MagicMock()

    class _MockVerbs:
        verbs = ["驅動", "校準", "影響"]

    mock_llm.chat_structured = MagicMock(return_value=_MockVerbs())

    mock_governance_ai = MagicMock()
    mock_governance_ai._llm = mock_llm

    service = _make_service([source, target], governance_ai=mock_governance_ai)

    result = await service.suggest_relationship_verb(source, target)

    assert isinstance(result, list)
    assert len(result) <= 3
    assert "驅動" in result
    mock_llm.chat_structured.assert_called_once()


async def test_suggest_relationship_verb_returns_empty_on_llm_failure():
    """When LLM raises an exception, suggest_relationship_verb should return []."""
    source = _entity(id="src-1", name="Pricing Module")
    target = _entity(id="tgt-1", name="Order Flow")

    mock_llm = MagicMock()
    mock_llm.chat_structured = MagicMock(side_effect=Exception("LLM connection failed"))

    mock_governance_ai = MagicMock()
    mock_governance_ai._llm = mock_llm

    service = _make_service([source, target], governance_ai=mock_governance_ai)

    result = await service.suggest_relationship_verb(source, target)

    assert result == []


async def test_suggest_relationship_verb_returns_empty_when_no_governance_ai():
    """When governance_ai is None, suggest_relationship_verb should return []."""
    source = _entity(id="src-1", name="Pricing Module")
    target = _entity(id="tgt-1", name="Order Flow")

    service = _make_service([source, target], governance_ai=None)

    result = await service.suggest_relationship_verb(source, target)

    assert result == []


# ──────────────────────────────────────────────
# run_quality_check: verb_completeness
# ──────────────────────────────────────────────

async def test_run_quality_check_verb_completeness_warning_when_all_verbs_missing():
    """Entity with relationships but no verbs should produce a verb_completeness warning."""
    module = _entity(id="mod-1", name="No Verb Module", type="module", status="active")
    goal = _entity(id="goal-1", name="Revenue Goal", type=EntityType.GOAL)
    rel = Relationship(
        id="rel-1",
        source_entity_id="mod-1",
        target_id="goal-1",
        type=RelationshipType.IMPACTS,
        description="Module impacts goal",
        verb=None,  # no verb
    )

    entity_repo = AsyncMock()
    entity_repo.list_all = AsyncMock(return_value=[module, goal])
    relationship_repo = AsyncMock()
    # list_by_entity returns the relationship for mod-1, empty for goal-1
    def _list_by_entity(eid):
        if eid == "mod-1":
            return [rel]
        return []
    relationship_repo.list_by_entity = AsyncMock(side_effect=_list_by_entity)
    blindspot_repo = AsyncMock()
    blindspot_repo.list_all = AsyncMock(return_value=[])
    protocol_repo = AsyncMock()
    protocol_repo.list_all = AsyncMock(return_value=[])
    protocol_repo.get_by_entity = AsyncMock(return_value=None)

    service = GovernanceService(
        entity_repo=entity_repo,
        relationship_repo=relationship_repo,
        protocol_repo=protocol_repo,
        blindspot_repo=blindspot_repo,
    )

    report = await service.run_quality_check()

    warning_names = [w.name for w in report.warnings]
    assert "relationship_verb_completeness" in warning_names
    verb_warning = next(w for w in report.warnings if w.name == "relationship_verb_completeness")
    assert "No Verb Module" in verb_warning.detail


async def test_run_quality_check_no_verb_warning_when_verbs_present():
    """Entity with relationships that all have verbs should NOT produce a warning."""
    module = _entity(id="mod-1", name="Verb Module", type="module", status="active")
    goal = _entity(id="goal-1", name="Revenue Goal", type=EntityType.GOAL)
    rel = Relationship(
        id="rel-1",
        source_entity_id="mod-1",
        target_id="goal-1",
        type=RelationshipType.IMPACTS,
        description="Module impacts goal",
        verb="驅動",  # has verb
    )

    entity_repo = AsyncMock()
    entity_repo.list_all = AsyncMock(return_value=[module, goal])
    relationship_repo = AsyncMock()
    def _list_by_entity(eid):
        if eid == "mod-1":
            return [rel]
        return []
    relationship_repo.list_by_entity = AsyncMock(side_effect=_list_by_entity)
    blindspot_repo = AsyncMock()
    blindspot_repo.list_all = AsyncMock(return_value=[])
    protocol_repo = AsyncMock()
    protocol_repo.list_all = AsyncMock(return_value=[])
    protocol_repo.get_by_entity = AsyncMock(return_value=None)

    service = GovernanceService(
        entity_repo=entity_repo,
        relationship_repo=relationship_repo,
        protocol_repo=protocol_repo,
        blindspot_repo=blindspot_repo,
    )

    report = await service.run_quality_check()

    # verb_completeness warning should be present but passed=True
    verb_warnings = [w for w in report.warnings if w.name == "relationship_verb_completeness"]
    assert len(verb_warnings) == 1
    assert verb_warnings[0].passed is True


async def test_run_quality_check_partner_verb_fill_rate_warning_below_50pct():
    """When < 50% of relationships have verbs, partner-level warning should appear."""
    module = _entity(id="mod-1", name="Hub Module", type="module", status="active")
    targets = [_entity(id=f"tgt-{i}", name=f"Target {i}", type="module") for i in range(4)]
    # 1 out of 4 relationships has a verb → 25% < 50%
    rels = [
        Relationship(
            id=f"rel-{i}",
            source_entity_id="mod-1",
            target_id=f"tgt-{i}",
            type=RelationshipType.IMPACTS,
            description=f"impacts {i}",
            verb="驅動" if i == 0 else None,
        )
        for i in range(4)
    ]

    entity_repo = AsyncMock()
    entity_repo.list_all = AsyncMock(return_value=[module] + targets)
    relationship_repo = AsyncMock()
    def _list_by_entity(eid):
        if eid == "mod-1":
            return rels
        return []
    relationship_repo.list_by_entity = AsyncMock(side_effect=_list_by_entity)
    blindspot_repo = AsyncMock()
    blindspot_repo.list_all = AsyncMock(return_value=[])
    protocol_repo = AsyncMock()
    protocol_repo.list_all = AsyncMock(return_value=[])
    protocol_repo.get_by_entity = AsyncMock(return_value=None)

    service = GovernanceService(
        entity_repo=entity_repo,
        relationship_repo=relationship_repo,
        protocol_repo=protocol_repo,
        blindspot_repo=blindspot_repo,
    )

    report = await service.run_quality_check()

    warning_names = [w.name for w in report.warnings]
    assert "partner_verb_fill_rate_low" in warning_names


# ──────────────────────────────────────────────
# run_blindspot_analysis: topology integration
# ──────────────────────────────────────────────

async def test_run_blindspot_analysis_includes_topology_blindspots():
    """run_blindspot_analysis should persist and return topology blindspots."""
    isolated = _entity(id="iso-1", name="Isolated Module", type="module")
    service = _make_service([isolated], relationships=[])

    blindspots = await service.run_blindspot_analysis()

    # Should include an isolated_node topology blindspot
    descriptions = [b.description for b in blindspots]
    assert any("Isolated Module" in d for d in descriptions)


# ──────────────────────────────────────────────
# run_blindspot_analysis: deduplication
# ──────────────────────────────────────────────

async def test_run_blindspot_analysis_deduplicates_topology_blindspots():
    """Calling run_blindspot_analysis twice should not re-add topology blindspots.

    On the second call all existing descriptions are already in blindspot_repo.list_all(),
    so blindspot_repo.add() must NOT be called again for any of them.
    """
    from zenos.domain.models import Blindspot, Severity

    # A module with no relationships will generate two topology issues:
    # 1) isolated_node  (no relationships at all)
    # 2) goal_disconnected  (no path to a GOAL entity)
    isolated = _entity(id="iso-1", name="Isolated Module", type="module")

    # Pre-populate blindspot_repo with ALL descriptions that analyze_graph_topology produces
    # for this entity so the second call finds them all and skips add().
    pre_existing = [
        Blindspot(
            description="「Isolated Module」沒有任何關聯，可能是孤立的知識節點或待整合的概念。",
            severity=Severity.YELLOW.value,
            related_entity_ids=["iso-1"],
            suggested_action="為此節點建立至少一條關聯，或確認是否需要整合到現有概念。",
            id="bs-1",
        ),
        Blindspot(
            description="「Isolated Module」無法追溯到任何目標節點，可能是與公司目標脫節的知識孤島。",
            severity=Severity.YELLOW.value,
            related_entity_ids=["iso-1"],
            suggested_action="為此節點建立通往目標節點的關聯路徑，確保與公司目標一致。",
            id="bs-2",
        ),
    ]

    entity_repo = AsyncMock()
    entity_repo.list_all = AsyncMock(return_value=[isolated])
    relationship_repo = AsyncMock()
    relationship_repo.list_by_entity = AsyncMock(return_value=[])
    blindspot_repo = AsyncMock()
    blindspot_repo.list_all = AsyncMock(return_value=pre_existing)
    blindspot_repo.add = AsyncMock(side_effect=lambda b: b)
    protocol_repo = AsyncMock()
    protocol_repo.list_all = AsyncMock(return_value=[])
    protocol_repo.get_by_entity = AsyncMock(return_value=None)

    service = GovernanceService(
        entity_repo=entity_repo,
        relationship_repo=relationship_repo,
        protocol_repo=protocol_repo,
        blindspot_repo=blindspot_repo,
    )

    await service.run_blindspot_analysis()

    # blindspot_repo.add must NOT have been called — all descriptions already exist
    blindspot_repo.add.assert_not_called()


async def test_run_blindspot_analysis_adds_new_topology_blindspot_when_not_duplicate():
    """When no existing blindspot matches, blindspot_repo.add() should be called once."""
    isolated = _entity(id="iso-1", name="Brand New Module", type="module")

    entity_repo = AsyncMock()
    entity_repo.list_all = AsyncMock(return_value=[isolated])
    relationship_repo = AsyncMock()
    relationship_repo.list_by_entity = AsyncMock(return_value=[])
    blindspot_repo = AsyncMock()
    blindspot_repo.list_all = AsyncMock(return_value=[])  # no existing blindspots
    blindspot_repo.add = AsyncMock(side_effect=lambda b: b)
    protocol_repo = AsyncMock()
    protocol_repo.list_all = AsyncMock(return_value=[])
    protocol_repo.get_by_entity = AsyncMock(return_value=None)

    service = GovernanceService(
        entity_repo=entity_repo,
        relationship_repo=relationship_repo,
        protocol_repo=protocol_repo,
        blindspot_repo=blindspot_repo,
    )

    await service.run_blindspot_analysis()

    # Should have been called at least once (for the isolated_node issue)
    assert blindspot_repo.add.call_count >= 1
