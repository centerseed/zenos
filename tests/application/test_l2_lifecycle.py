"""Tests for L2 (module) entity lifecycle state machine.

Covers DC-1 through DC-11 from the L2 lifecycle technical design.
Uses in-memory mock repositories; no external services required.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from zenos.application.ontology_service import OntologyService
from zenos.application.governance_ai import GovernanceInference, InferredRel
from zenos.domain.models import Entity, Relationship, RelationshipType, Tags


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_repos() -> dict:
    entity_repo = AsyncMock()
    entity_repo.get_by_id = AsyncMock(return_value=None)
    entity_repo.get_by_name = AsyncMock(return_value=None)
    entity_repo.list_all = AsyncMock(return_value=[])
    entity_repo.upsert = AsyncMock(side_effect=lambda e: e)
    entity_repo.list_by_parent = AsyncMock(return_value=[])

    relationship_repo = AsyncMock()
    relationship_repo.add = AsyncMock(side_effect=lambda r: r)
    relationship_repo.list_by_entity = AsyncMock(return_value=[])
    relationship_repo.find_duplicate = AsyncMock(return_value=None)

    document_repo = AsyncMock()
    document_repo.list_by_entity = AsyncMock(return_value=[])
    document_repo.upsert = AsyncMock(side_effect=lambda d: d)

    protocol_repo = AsyncMock()
    protocol_repo.upsert = AsyncMock(side_effect=lambda p: p)

    blindspot_repo = AsyncMock()
    blindspot_repo.add = AsyncMock(side_effect=lambda b: b)

    return {
        "entity_repo": entity_repo,
        "relationship_repo": relationship_repo,
        "document_repo": document_repo,
        "protocol_repo": protocol_repo,
        "blindspot_repo": blindspot_repo,
    }


def _make_service(repos: dict | None = None, governance_ai=None) -> OntologyService:
    r = repos or _mock_repos()
    return OntologyService(**r, governance_ai=governance_ai)


def _module_data(**overrides) -> dict:
    defaults = {
        "name": "Pricing Rules",
        "type": "module",
        "summary": "定義方案與升降級規則",
        "tags": {"what": "pricing", "why": "revenue", "how": "rules", "who": "pm"},
        "parent_id": "prod-1",
        # P0-1: layer_decision required for new L2 writes
        "layer_decision": {
            "q1_persistent": True,
            "q2_cross_role": True,
            "q3_company_consensus": True,
            "impacts_draft": "pricing 規則改了→billing 相關流程要跟著看",
        },
    }
    defaults.update(overrides)
    return defaults


def _make_parent(parent_id: str = "prod-1") -> Entity:
    return Entity(
        id=parent_id, name="ZenOS", type="product",
        summary="Context layer", tags=Tags(what="platform", why="ai", how="ontology", who="sme"),
    )


# ---------------------------------------------------------------------------
# DC-1: Module status validation allows draft and stale
# ---------------------------------------------------------------------------

class TestModuleStatusValidation:

    async def test_module_draft_status_is_valid(self):
        """DC-1: module entity accepts 'draft' status."""
        repos = _mock_repos()
        parent = _make_parent()
        repos["entity_repo"].get_by_id = AsyncMock(return_value=parent)
        repos["entity_repo"].get_by_name = AsyncMock(return_value=None)
        repos["entity_repo"].list_all = AsyncMock(return_value=[parent])
        # Provide an id so it is treated as update (bypasses new-L2-always-draft rule)
        existing = Entity(
            id="mod-1", name="Pricing Rules", type="module",
            summary="Rules", tags=Tags(what="pricing", why="rev", how="rules", who="pm"),
            status="draft", parent_id="prod-1",
        )
        repos["entity_repo"].get_by_id = AsyncMock(
            side_effect=lambda eid: parent if eid == "prod-1" else existing
        )
        svc = _make_service(repos)
        # draft → draft (no transition to active) should succeed
        result = await svc.upsert_entity(_module_data(id="mod-1", status="draft"))
        assert result.entity.status == "draft"

    async def test_module_stale_status_is_valid(self):
        """DC-1: module entity accepts 'stale' status."""
        repos = _mock_repos()
        parent = _make_parent()
        existing = Entity(
            id="mod-1", name="Pricing Rules", type="module",
            summary="Rules", tags=Tags(what="pricing", why="rev", how="rules", who="pm"),
            status="active", parent_id="prod-1",
        )
        repos["entity_repo"].get_by_id = AsyncMock(
            side_effect=lambda eid: parent if eid == "prod-1" else existing
        )
        repos["entity_repo"].get_by_name = AsyncMock(return_value=None)
        repos["entity_repo"].list_all = AsyncMock(return_value=[parent, existing])
        svc = _make_service(repos)
        # DC-7 (active → stale is allowed)
        result = await svc.upsert_entity(_module_data(id="mod-1", status="stale"))
        assert result.entity.status == "stale"

    async def test_invalid_status_for_module_raises(self):
        """Non-module statuses like 'current' are invalid for module."""
        repos = _mock_repos()
        parent = _make_parent()
        repos["entity_repo"].get_by_id = AsyncMock(return_value=parent)
        repos["entity_repo"].get_by_name = AsyncMock(return_value=None)
        repos["entity_repo"].list_all = AsyncMock(return_value=[parent])
        svc = _make_service(repos)
        with pytest.raises(ValueError, match="Invalid entity status"):
            await svc.upsert_entity(_module_data(status="current"))


# ---------------------------------------------------------------------------
# DC-2: New module always starts as draft
# ---------------------------------------------------------------------------

class TestNewModuleAlwaysDraft:

    async def test_new_module_without_governance_ai_is_draft(self):
        """DC-2: new module without governance_ai still gets status=draft."""
        repos = _mock_repos()
        parent = _make_parent()
        repos["entity_repo"].get_by_id = AsyncMock(return_value=parent)
        repos["entity_repo"].get_by_name = AsyncMock(return_value=None)
        repos["entity_repo"].list_all = AsyncMock(return_value=[parent])
        svc = _make_service(repos, governance_ai=None)
        result = await svc.upsert_entity(_module_data())
        assert result.entity.status == "draft"

    async def test_new_module_active_status_overridden_to_draft(self):
        """DC-2: caller passing status='active' is overridden to 'draft' for new L2."""
        repos = _mock_repos()
        parent = _make_parent()
        repos["entity_repo"].get_by_id = AsyncMock(return_value=parent)
        repos["entity_repo"].get_by_name = AsyncMock(return_value=None)
        repos["entity_repo"].list_all = AsyncMock(return_value=[parent])
        svc = _make_service(repos, governance_ai=None)
        result = await svc.upsert_entity(_module_data(status="active"))
        assert result.entity.status == "draft"

    async def test_new_module_draft_warning_present(self):
        """DC-2: new module creation includes a warning about draft state."""
        repos = _mock_repos()
        parent = _make_parent()
        repos["entity_repo"].get_by_id = AsyncMock(return_value=parent)
        repos["entity_repo"].get_by_name = AsyncMock(return_value=None)
        repos["entity_repo"].list_all = AsyncMock(return_value=[parent])
        svc = _make_service(repos, governance_ai=None)
        result = await svc.upsert_entity(_module_data())
        assert result.warnings is not None
        assert any("draft" in w for w in result.warnings)


# ---------------------------------------------------------------------------
# DC-3: write new L2 without impacts → no raise, just warning
# ---------------------------------------------------------------------------

class TestNewModuleNoImpactsWarning:

    async def test_new_l2_without_impacts_does_not_raise(self):
        """DC-3: no ValueError when governance AI finds no impacts; returns draft + warning."""
        repos = _mock_repos()
        parent = _make_parent()
        repos["entity_repo"].get_by_id = AsyncMock(return_value=parent)
        repos["entity_repo"].get_by_name = AsyncMock(return_value=None)
        repos["entity_repo"].list_all = AsyncMock(return_value=[parent])

        class _NoImpactsGov:
            def infer_all(self, entity_data, existing_entities, unlinked_docs):
                return GovernanceInference(rels=[], impacts_context_status="insufficient",
                                           impacts_context_gaps=["no context"])

        svc = _make_service(repos, governance_ai=_NoImpactsGov())
        result = await svc.upsert_entity(_module_data())
        assert result.entity.status == "draft"
        assert result.warnings is not None

    async def test_new_l2_with_inferred_impacts_warns_and_is_draft(self):
        """DC-2+DC-3: even with inferred impacts, entity stays draft until confirmed."""
        repos = _mock_repos()
        parent = _make_parent()
        repos["entity_repo"].get_by_id = AsyncMock(return_value=parent)
        repos["entity_repo"].get_by_name = AsyncMock(return_value=None)
        repos["entity_repo"].list_all = AsyncMock(return_value=[parent])

        class _HasImpactsGov:
            def infer_all(self, entity_data, existing_entities, unlinked_docs):
                return GovernanceInference(
                    rels=[InferredRel(target="prod-1", type="impacts",
                                     description="pricing 變→billing 監控要跟著看")]
                )

        svc = _make_service(repos, governance_ai=_HasImpactsGov())
        result = await svc.upsert_entity(_module_data())
        assert result.entity.status == "draft"
        assert result.warnings is not None
        assert any("confirm" in w.lower() or "draft" in w.lower() for w in result.warnings)


# ---------------------------------------------------------------------------
# DC-4: confirm module with impacts → active; without → ValueError
# ---------------------------------------------------------------------------

class TestConfirmModuleImpactsGate:

    async def test_confirm_module_with_concrete_impacts_sets_active(self):
        """DC-4: confirm on draft module with concrete impacts → status=active."""
        repos = _mock_repos()
        module = Entity(
            id="mod-1", name="Pricing Rules", type="module",
            summary="Rules", tags=Tags(what="pricing", why="rev", how="rules", who="pm"),
            status="draft", parent_id="prod-1",
            details={"layer_decision": {"q1_persistent": True, "q2_cross_role": True, "q3_company_consensus": True}},
        )
        concrete_rel = Relationship(
            id="rel-1", source_entity_id="mod-1", target_id="prod-1",
            type=RelationshipType.IMPACTS,
            description="pricing 改了→billing 監控要跟著看",
        )
        repos["entity_repo"].get_by_id = AsyncMock(return_value=module)
        repos["relationship_repo"].list_by_entity = AsyncMock(return_value=[concrete_rel])
        svc = _make_service(repos)
        result = await svc.confirm("entities", "mod-1")
        assert result["confirmed_by_user"] is True
        # Verify the upserted entity had status=active
        upserted = repos["entity_repo"].upsert.call_args[0][0]
        assert upserted.status == "active"
        assert upserted.confirmed_by_user is True

    async def test_confirm_module_without_impacts_raises(self):
        """DC-4: confirm on module with no concrete impacts raises ValueError."""
        repos = _mock_repos()
        module = Entity(
            id="mod-1", name="Pricing Rules", type="module",
            summary="Rules", tags=Tags(what="pricing", why="rev", how="rules", who="pm"),
            status="draft", parent_id="prod-1",
            details={"layer_decision": {"q1_persistent": True, "q2_cross_role": True, "q3_company_consensus": True}},
        )
        repos["entity_repo"].get_by_id = AsyncMock(return_value=module)
        repos["relationship_repo"].list_by_entity = AsyncMock(return_value=[])
        svc = _make_service(repos)
        with pytest.raises(ValueError, match="L2 confirm 失敗"):
            await svc.confirm("entities", "mod-1")

    async def test_confirm_module_with_non_impacts_relationship_raises(self):
        """DC-4: confirm rejects when only non-impacts relationships exist."""
        repos = _mock_repos()
        module = Entity(
            id="mod-1", name="Pricing Rules", type="module",
            summary="Rules", tags=Tags(what="pricing", why="rev", how="rules", who="pm"),
            status="draft", parent_id="prod-1",
            details={"layer_decision": {"q1_persistent": True, "q2_cross_role": True, "q3_company_consensus": True}},
        )
        non_concrete_rel = Relationship(
            id="rel-2", source_entity_id="mod-1", target_id="prod-1",
            type=RelationshipType.DEPENDS_ON,
            description="depends on product",
        )
        repos["entity_repo"].get_by_id = AsyncMock(return_value=module)
        repos["relationship_repo"].list_by_entity = AsyncMock(return_value=[non_concrete_rel])
        svc = _make_service(repos)
        with pytest.raises(ValueError, match="L2 confirm 失敗"):
            await svc.confirm("entities", "mod-1")

    async def test_confirm_module_stale_with_impacts_becomes_active(self):
        """DC-4: stale module with concrete impacts also transitions to active on confirm."""
        repos = _mock_repos()
        module = Entity(
            id="mod-1", name="Pricing Rules", type="module",
            summary="Rules", tags=Tags(what="pricing", why="rev", how="rules", who="pm"),
            status="stale", parent_id="prod-1",
            details={"layer_decision": {"q1_persistent": True, "q2_cross_role": True, "q3_company_consensus": True}},
        )
        concrete_rel = Relationship(
            id="rel-1", source_entity_id="mod-1", target_id="prod-1",
            type=RelationshipType.IMPACTS,
            description="price 改了→checkout flow 要重新審",
        )
        repos["entity_repo"].get_by_id = AsyncMock(return_value=module)
        repos["relationship_repo"].list_by_entity = AsyncMock(return_value=[concrete_rel])
        svc = _make_service(repos)
        result = await svc.confirm("entities", "mod-1")
        assert result["confirmed_by_user"] is True
        upserted = repos["entity_repo"].upsert.call_args[0][0]
        assert upserted.status == "active"

    async def test_confirm_non_module_entity_is_unaffected_by_impacts_gate(self):
        """DC-6: confirm on a product entity does not require impacts gate."""
        repos = _mock_repos()
        product = Entity(
            id="prod-1", name="ZenOS", type="product",
            summary="Platform", tags=Tags(what="platform", why="ai", how="onto", who="sme"),
            status="active",
        )
        repos["entity_repo"].get_by_id = AsyncMock(return_value=product)
        repos["relationship_repo"].list_by_entity = AsyncMock(return_value=[])
        svc = _make_service(repos)
        result = await svc.confirm("entities", "prod-1")
        assert result["confirmed_by_user"] is True


class TestConfirmModuleThreeQuestionGate:
    """三問判斷 gate: confirm L2 requires complete layer_decision."""

    async def test_confirm_l2_without_layer_decision_raises(self):
        """L2 confirm 應在缺少 layer_decision 時拋出 ValueError。"""
        repos = _mock_repos()
        module = Entity(
            id="mod-1", name="Pricing Rules", type="module",
            summary="Rules", tags=Tags(what="pricing", why="rev", how="rules", who="pm"),
            status="draft", parent_id="prod-1",
            details=None,
        )
        repos["entity_repo"].get_by_id = AsyncMock(return_value=module)
        repos["relationship_repo"].list_by_entity = AsyncMock(return_value=[])
        svc = _make_service(repos)
        with pytest.raises(ValueError, match="layer_decision"):
            await svc.confirm("entities", "mod-1")

    async def test_confirm_l2_with_empty_details_raises(self):
        """L2 confirm 應在 details 為空 dict（無 layer_decision）時拋出 ValueError。"""
        repos = _mock_repos()
        module = Entity(
            id="mod-1", name="Pricing Rules", type="module",
            summary="Rules", tags=Tags(what="pricing", why="rev", how="rules", who="pm"),
            status="draft", parent_id="prod-1",
            details={},
        )
        repos["entity_repo"].get_by_id = AsyncMock(return_value=module)
        repos["relationship_repo"].list_by_entity = AsyncMock(return_value=[])
        svc = _make_service(repos)
        with pytest.raises(ValueError, match="layer_decision"):
            await svc.confirm("entities", "mod-1")

    async def test_confirm_l2_with_q1_false_raises(self):
        """L2 confirm 應在 q1_persistent=False 時拋出 ValueError。"""
        repos = _mock_repos()
        module = Entity(
            id="mod-1", name="Pricing Rules", type="module",
            summary="Rules", tags=Tags(what="pricing", why="rev", how="rules", who="pm"),
            status="draft", parent_id="prod-1",
            details={"layer_decision": {"q1_persistent": False, "q2_cross_role": True, "q3_company_consensus": True}},
        )
        repos["entity_repo"].get_by_id = AsyncMock(return_value=module)
        repos["relationship_repo"].list_by_entity = AsyncMock(return_value=[])
        svc = _make_service(repos)
        with pytest.raises(ValueError, match="三問判斷未全通過"):
            await svc.confirm("entities", "mod-1")

    async def test_confirm_l2_with_q3_false_raises(self):
        """L2 confirm 應在 q3_company_consensus=False 時拋出 ValueError。"""
        repos = _mock_repos()
        module = Entity(
            id="mod-1", name="Pricing Rules", type="module",
            summary="Rules", tags=Tags(what="pricing", why="rev", how="rules", who="pm"),
            status="draft", parent_id="prod-1",
            details={"layer_decision": {"q1_persistent": True, "q2_cross_role": True, "q3_company_consensus": False}},
        )
        repos["entity_repo"].get_by_id = AsyncMock(return_value=module)
        repos["relationship_repo"].list_by_entity = AsyncMock(return_value=[])
        svc = _make_service(repos)
        with pytest.raises(ValueError, match="三問判斷未全通過"):
            await svc.confirm("entities", "mod-1")

    async def test_confirm_l2_with_complete_layer_decision_and_impacts_succeeds(self):
        """L2 confirm 三問全通過 + 有具體 impacts → 成功。"""
        repos = _mock_repos()
        module = Entity(
            id="mod-1", name="Pricing Rules", type="module",
            summary="Rules", tags=Tags(what="pricing", why="rev", how="rules", who="pm"),
            status="draft", parent_id="prod-1",
            details={"layer_decision": {"q1_persistent": True, "q2_cross_role": True, "q3_company_consensus": True}},
        )
        concrete_rel = Relationship(
            id="rel-1", source_entity_id="mod-1", target_id="prod-1",
            type=RelationshipType.IMPACTS,
            description="pricing 改了→billing 監控要跟著看",
        )
        repos["entity_repo"].get_by_id = AsyncMock(return_value=module)
        repos["relationship_repo"].list_by_entity = AsyncMock(return_value=[concrete_rel])
        svc = _make_service(repos)
        result = await svc.confirm("entities", "mod-1")
        assert result["confirmed_by_user"] is True


# ---------------------------------------------------------------------------
# DC-5: write update cannot transition module from draft to active
# ---------------------------------------------------------------------------

class TestModuleDraftToActiveBlocked:

    async def test_write_update_draft_to_active_raises(self):
        """DC-5: updating module status from draft to active via write is rejected."""
        repos = _mock_repos()
        parent = _make_parent()
        existing_module = Entity(
            id="mod-1", name="Pricing Rules", type="module",
            summary="Rules", tags=Tags(what="pricing", why="rev", how="rules", who="pm"),
            status="draft", parent_id="prod-1",
        )
        repos["entity_repo"].get_by_id = AsyncMock(
            side_effect=lambda eid: parent if eid == "prod-1" else existing_module
        )
        repos["entity_repo"].get_by_name = AsyncMock(return_value=None)
        repos["entity_repo"].list_all = AsyncMock(return_value=[parent, existing_module])
        svc = _make_service(repos)
        with pytest.raises(ValueError, match="draft 直接升為 active"):
            await svc.upsert_entity(_module_data(id="mod-1", status="active"))

    async def test_write_update_active_to_stale_is_allowed(self):
        """DC-5 complement: active → stale transition is permitted via write."""
        repos = _mock_repos()
        parent = _make_parent()
        existing_module = Entity(
            id="mod-1", name="Pricing Rules", type="module",
            summary="Rules", tags=Tags(what="pricing", why="rev", how="rules", who="pm"),
            status="active", parent_id="prod-1",
        )
        repos["entity_repo"].get_by_id = AsyncMock(
            side_effect=lambda eid: parent if eid == "prod-1" else existing_module
        )
        repos["entity_repo"].get_by_name = AsyncMock(return_value=None)
        repos["entity_repo"].list_all = AsyncMock(return_value=[parent, existing_module])
        svc = _make_service(repos)
        result = await svc.upsert_entity(_module_data(id="mod-1", status="stale"))
        assert result.entity.status == "stale"

    async def test_write_update_draft_to_paused_is_allowed(self):
        """DC-5: draft → paused is fine (only draft → active is blocked)."""
        repos = _mock_repos()
        parent = _make_parent()
        existing_module = Entity(
            id="mod-1", name="Pricing Rules", type="module",
            summary="Rules", tags=Tags(what="pricing", why="rev", how="rules", who="pm"),
            status="draft", parent_id="prod-1",
        )
        repos["entity_repo"].get_by_id = AsyncMock(
            side_effect=lambda eid: parent if eid == "prod-1" else existing_module
        )
        repos["entity_repo"].get_by_name = AsyncMock(return_value=None)
        repos["entity_repo"].list_all = AsyncMock(return_value=[parent, existing_module])
        svc = _make_service(repos)
        result = await svc.upsert_entity(_module_data(id="mod-1", status="paused"))
        assert result.entity.status == "paused"


# ---------------------------------------------------------------------------
# DC-6: Existing active L2 entities are not downgraded
# ---------------------------------------------------------------------------

class TestExistingActiveL2NotDowngraded:

    async def test_update_active_module_stays_active_when_no_status_change(self):
        """DC-6: updating fields on active module doesn't change status."""
        repos = _mock_repos()
        parent = _make_parent()
        existing_module = Entity(
            id="mod-1", name="Pricing Rules", type="module",
            summary="Old summary", tags=Tags(what="pricing", why="rev", how="rules", who="pm"),
            status="active", confirmed_by_user=True, parent_id="prod-1",
        )
        repos["entity_repo"].get_by_id = AsyncMock(
            side_effect=lambda eid: parent if eid == "prod-1" else existing_module
        )
        repos["entity_repo"].get_by_name = AsyncMock(return_value=None)
        repos["entity_repo"].list_all = AsyncMock(return_value=[parent, existing_module])
        svc = _make_service(repos)
        result = await svc.upsert_entity(_module_data(id="mod-1", force=True))
        # status should remain active (not downgraded to draft)
        assert result.entity.status == "active"


# ---------------------------------------------------------------------------
# DC-7 & DC-8: force=true requires manual_override_reason; result is still draft
# ---------------------------------------------------------------------------

class TestForceModuleWithOverrideReason:

    async def test_force_l2_without_reason_raises(self):
        """DC-8: force=true on new L2 without manual_override_reason raises ValueError."""
        repos = _mock_repos()
        parent = _make_parent()
        repos["entity_repo"].get_by_id = AsyncMock(return_value=parent)
        repos["entity_repo"].get_by_name = AsyncMock(return_value=None)
        repos["entity_repo"].list_all = AsyncMock(return_value=[parent])

        class _NoImpactsGov:
            def infer_all(self, entity_data, existing_entities, unlinked_docs):
                return GovernanceInference(rels=[])

        svc = _make_service(repos, governance_ai=_NoImpactsGov())
        with pytest.raises(ValueError, match="manual_override_reason"):
            await svc.upsert_entity(_module_data(force=True))

    async def test_force_l2_with_reason_creates_draft_with_details(self):
        """DC-7+DC-9: force=true + reason → status=draft, details contains reason and timestamp."""
        repos = _mock_repos()
        parent = _make_parent()
        repos["entity_repo"].get_by_id = AsyncMock(return_value=parent)
        repos["entity_repo"].get_by_name = AsyncMock(return_value=None)
        repos["entity_repo"].list_all = AsyncMock(return_value=[parent])

        class _NoImpactsGov:
            def infer_all(self, entity_data, existing_entities, unlinked_docs):
                return GovernanceInference(rels=[])

        svc = _make_service(repos, governance_ai=_NoImpactsGov())
        result = await svc.upsert_entity(_module_data(
            force=True,
            manual_override_reason="PM 明確指示先建，impacts 後補",
        ))
        assert result.entity.status == "draft"
        assert isinstance(result.entity.details, dict)
        assert result.entity.details["manual_override_reason"] == "PM 明確指示先建，impacts 後補"
        assert "manual_override_at" in result.entity.details

    async def test_force_l2_with_reason_warning_contains_reason(self):
        """DC-7: force mode warning mentions the override reason."""
        repos = _mock_repos()
        parent = _make_parent()
        repos["entity_repo"].get_by_id = AsyncMock(return_value=parent)
        repos["entity_repo"].get_by_name = AsyncMock(return_value=None)
        repos["entity_repo"].list_all = AsyncMock(return_value=[parent])

        class _NoImpactsGov:
            def infer_all(self, entity_data, existing_entities, unlinked_docs):
                return GovernanceInference(rels=[])

        svc = _make_service(repos, governance_ai=_NoImpactsGov())
        result = await svc.upsert_entity(_module_data(
            force=True,
            manual_override_reason="bootstrapping phase, no peers yet",
        ))
        assert result.warnings is not None
        assert any("force" in w.lower() for w in result.warnings)


# ---------------------------------------------------------------------------
# Task 7: confirm sets last_reviewed_at
# ---------------------------------------------------------------------------

class TestConfirmSetsLastReviewedAt:
    """DC-1: confirm operation should set entity.last_reviewed_at = now."""

    async def test_confirm_entity_sets_last_reviewed_at(self):
        """Confirming any entity should set last_reviewed_at to current time."""
        repos = _mock_repos()
        existing_entity = Entity(
            id="e1",
            name="Pricing Module",
            type="module",
            summary="Defines pricing rules",
            tags=Tags(what="pricing", why="revenue", how="rules", who="pm"),
            status="draft",
            confirmed_by_user=False,
            details={"layer_decision": {"q1_persistent": True, "q2_cross_role": True, "q3_company_consensus": True}},
        )
        # Confirm gate for L2: needs a concrete impacts relationship
        concrete_rel = Relationship(
            id="r1",
            source_entity_id="e1",
            target_id="e2",
            type=RelationshipType.IMPACTS,
            description="pricing policy changed→discount rules need review",
        )
        repos["entity_repo"].get_by_id = AsyncMock(return_value=existing_entity)
        repos["relationship_repo"].list_by_entity = AsyncMock(return_value=[concrete_rel])

        captured: list[Entity] = []

        async def _capture_upsert(e: Entity) -> Entity:
            captured.append(e)
            return e

        repos["entity_repo"].upsert = _capture_upsert
        svc = _make_service(repos)

        before = datetime.now(timezone.utc)
        await svc.confirm(collection="entities", item_id="e1")
        after = datetime.now(timezone.utc)

        assert len(captured) == 1
        saved = captured[0]
        assert saved.confirmed_by_user is True
        assert saved.last_reviewed_at is not None
        assert before <= saved.last_reviewed_at <= after

    async def test_confirm_module_transitions_to_active_and_sets_reviewed_at(self):
        """Confirm a draft L2 module: status → active AND last_reviewed_at set."""
        repos = _mock_repos()
        existing_entity = Entity(
            id="m1",
            name="Feature Module",
            type="module",
            summary="Handles feature flags",
            tags=Tags(what="features", why="control", how="flags", who="pm"),
            status="draft",
            confirmed_by_user=False,
            details={"layer_decision": {"q1_persistent": True, "q2_cross_role": True, "q3_company_consensus": True}},
        )
        concrete_rel = Relationship(
            id="r1",
            source_entity_id="m1",
            target_id="m2",
            type=RelationshipType.IMPACTS,
            description="feature flags changed→UI visibility must be updated",
        )
        repos["entity_repo"].get_by_id = AsyncMock(return_value=existing_entity)
        repos["relationship_repo"].list_by_entity = AsyncMock(return_value=[concrete_rel])

        captured: list[Entity] = []

        async def _capture(e: Entity) -> Entity:
            captured.append(e)
            return e

        repos["entity_repo"].upsert = _capture
        svc = _make_service(repos)
        await svc.confirm(collection="entities", item_id="m1")

        saved = captured[0]
        assert saved.status == "active"
        assert saved.last_reviewed_at is not None


# ---------------------------------------------------------------------------
# Task 9: write path L2 summary tech-term scan
# ---------------------------------------------------------------------------

class TestL2SummaryTechTermScanOnWrite:
    """DC-6 through DC-11: write path should warn on technical terms in L2 summary."""

    async def test_tech_term_in_summary_adds_warning(self):
        """Writing a module with technical term in summary adds a warning."""
        repos = _mock_repos()
        parent = _make_parent()
        repos["entity_repo"].get_by_id = AsyncMock(return_value=parent)
        repos["entity_repo"].get_by_name = AsyncMock(return_value=None)
        repos["entity_repo"].list_all = AsyncMock(return_value=[parent])

        svc = _make_service(repos)
        result = await svc.upsert_entity(_module_data(
            summary="We use an API to connect all services.",
        ))
        assert result.warnings is not None
        warning_text = " ".join(result.warnings)
        assert "API" in warning_text

    async def test_tech_term_in_summary_forces_draft_for_new_module(self):
        """New (unconfirmed) module with tech-term summary is forced to draft status (DC-8)."""
        repos = _mock_repos()
        parent = _make_parent()
        repos["entity_repo"].get_by_id = AsyncMock(return_value=parent)
        repos["entity_repo"].get_by_name = AsyncMock(return_value=None)
        repos["entity_repo"].list_all = AsyncMock(return_value=[parent])

        svc = _make_service(repos)
        result = await svc.upsert_entity(_module_data(
            summary="We use REST and Docker for deployment.",
        ))
        assert result.entity.status == "draft"

    async def test_clean_summary_no_tech_term_warning(self):
        """Module with plain-language summary has no tech-term warning."""
        repos = _mock_repos()
        parent = _make_parent()
        repos["entity_repo"].get_by_id = AsyncMock(return_value=parent)
        repos["entity_repo"].get_by_name = AsyncMock(return_value=None)
        repos["entity_repo"].list_all = AsyncMock(return_value=[parent])

        svc = _make_service(repos)
        result = await svc.upsert_entity(_module_data(
            summary="定義方案與升降級規則的公司共識概念。",
        ))
        # Should not have tech-term warning (may have other warnings)
        warning_text = " ".join(result.warnings or [])
        assert "技術術語" not in warning_text

    async def test_tech_term_warning_does_not_block_write(self):
        """Tech-term scan adds warning but does not raise exception (DC-10)."""
        repos = _mock_repos()
        parent = _make_parent()
        repos["entity_repo"].get_by_id = AsyncMock(return_value=parent)
        repos["entity_repo"].get_by_name = AsyncMock(return_value=None)
        repos["entity_repo"].list_all = AsyncMock(return_value=[parent])

        svc = _make_service(repos)
        # Should not raise
        result = await svc.upsert_entity(_module_data(
            summary="This module uses Firestore and LLM under the hood.",
        ))
        assert result.entity is not None

    async def test_confirmed_entity_update_with_tech_term_warns_but_not_forced_draft(self):
        """Updating a confirmed module with tech-term warns but does not override status (DC-8 boundary)."""
        repos = _mock_repos()
        confirmed_entity = Entity(
            id="m1",
            name="Pricing Rules",
            type="module",
            summary="Old clean summary",
            tags=Tags(what="pricing", why="revenue", how="rules", who="pm"),
            status="active",
            confirmed_by_user=True,
        )
        repos["entity_repo"].get_by_id = AsyncMock(return_value=confirmed_entity)
        repos["entity_repo"].get_by_name = AsyncMock(return_value=None)
        repos["entity_repo"].list_all = AsyncMock(return_value=[confirmed_entity])
        repos["relationship_repo"].list_by_entity = AsyncMock(return_value=[])

        svc = _make_service(repos)
        result = await svc.upsert_entity({
            "id": "m1",
            "name": "Pricing Rules",
            "type": "module",
            "summary": "We call an API to get prices.",
            "tags": {"what": "pricing", "why": "revenue", "how": "rules", "who": "pm"},
            "parent_id": "prod-1",
        })
        # Warning should be present
        assert result.warnings is not None
        warning_text = " ".join(result.warnings)
        assert "API" in warning_text
        # Status NOT forced to draft for confirmed entity
        assert result.entity.status != "draft"


# ---------------------------------------------------------------------------
# Consolidation mode tests
# ---------------------------------------------------------------------------

class TestL2ConsolidationMode:

    def _make_repos_with_parent(self):
        repos = _mock_repos()
        parent = _make_parent()
        repos["entity_repo"].get_by_id = AsyncMock(return_value=parent)
        repos["entity_repo"].get_by_name = AsyncMock(return_value=None)
        repos["entity_repo"].list_all = AsyncMock(return_value=[parent])
        return repos

    async def test_write_new_l2_with_global_mode_stores_in_details(self):
        """write L2 with consolidation_mode='global' → details['consolidation_mode'] == 'global'."""
        repos = self._make_repos_with_parent()
        svc = _make_service(repos)
        result = await svc.upsert_entity(_module_data(consolidation_mode="global"))
        assert result.entity is not None
        assert result.entity.details is not None
        assert result.entity.details.get("consolidation_mode") == "global"

    async def test_write_new_l2_with_incremental_mode_stores_in_details(self):
        """write L2 with consolidation_mode='incremental' → details['consolidation_mode'] == 'incremental'."""
        repos = self._make_repos_with_parent()
        svc = _make_service(repos)
        result = await svc.upsert_entity(_module_data(consolidation_mode="incremental"))
        assert result.entity is not None
        assert result.entity.details is not None
        assert result.entity.details.get("consolidation_mode") == "incremental"

    async def test_write_new_l2_with_invalid_mode_raises_value_error(self):
        """write L2 with consolidation_mode='invalid' → ValueError."""
        repos = self._make_repos_with_parent()
        svc = _make_service(repos)
        with pytest.raises(ValueError, match="consolidation_mode 必須是"):
            await svc.upsert_entity(_module_data(consolidation_mode="invalid"))

    async def test_write_new_l2_without_consolidation_mode_succeeds(self):
        """write L2 without consolidation_mode → no details key set (backward compatible)."""
        repos = self._make_repos_with_parent()
        svc = _make_service(repos)
        result = await svc.upsert_entity(_module_data())
        assert result.entity is not None
        # details may be None or a dict without consolidation_mode
        if result.entity.details:
            assert "consolidation_mode" not in result.entity.details

    async def test_update_existing_l2_can_set_consolidation_mode(self):
        """Updating an existing L2 with consolidation_mode stores it in details."""
        repos = _mock_repos()
        existing = Entity(
            id="mod-existing",
            name="Pricing Rules",
            type="module",
            summary="定義方案與升降級規則",
            tags=Tags(what="pricing", why="revenue", how="rules", who="pm"),
            status="draft",
            parent_id="prod-1",
        )
        parent = _make_parent()
        repos["entity_repo"].get_by_id = AsyncMock(return_value=existing)
        repos["entity_repo"].get_by_name = AsyncMock(return_value=None)
        repos["entity_repo"].list_all = AsyncMock(return_value=[parent, existing])
        repos["relationship_repo"].list_by_entity = AsyncMock(return_value=[])

        svc = _make_service(repos)
        result = await svc.upsert_entity({
            "id": "mod-existing",
            "name": "Pricing Rules",
            "type": "module",
            "summary": "定義方案與升降級規則",
            "tags": {"what": "pricing", "why": "revenue", "how": "rules", "who": "pm"},
            "parent_id": "prod-1",
            "consolidation_mode": "global",
        })
        assert result.entity is not None
        assert result.entity.details is not None
        assert result.entity.details.get("consolidation_mode") == "global"
