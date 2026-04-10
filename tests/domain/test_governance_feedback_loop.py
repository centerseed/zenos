"""Tests for governance feedback loop features (P0-1, P0-2, P1-1, P1-2, P1-3).

DC coverage:
  DC-1 ~ DC-5:  P1-2 (impacts target validity enriched format)
  DC-6 ~ DC-10: P0-2 (quality correction priority)
  DC-11 ~ DC-15: P0-1 (layer_decision gate via OntologyService)
  DC-16 ~ DC-19: P1-3 (document consistency detection)
  DC-20 ~ DC-23: P1-1 (task signal blindspot inference)
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import pytest

from zenos.domain.governance import (
    HEALTH_THRESHOLDS,
    _blindspot_threshold,
    _kpi_level,
    _task_problem_tokens,
    _tasks_are_similar,
    check_impacts_target_validity,
    compute_health_kpis,
    compute_quality_correction_priority,
    detect_stale_documents_from_consistency,
    determine_recommended_action,
)
from zenos.domain.knowledge import Entity, EntityStatus, EntityType, Relationship, RelationshipType, Tags
from zenos.application.knowledge.governance_service import GovernanceService
from zenos.application.knowledge.ontology_service import OntologyService


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

_NOW = datetime(2026, 3, 28, tzinfo=timezone.utc)


def _entity(
    entity_id: str,
    name: str,
    entity_type: str = EntityType.MODULE,
    status: str = EntityStatus.ACTIVE,
    summary: str = "Test summary",
    parent_id: str | None = None,
    details: dict | None = None,
    tags: Tags | None = None,
    updated_at: datetime | None = None,
) -> Entity:
    return Entity(
        id=entity_id,
        name=name,
        type=entity_type,
        status=status,
        summary=summary,
        parent_id=parent_id,
        details=details,
        tags=tags or Tags(what="test", why="test why", how="test how", who="pm"),
        updated_at=updated_at or _NOW,
        created_at=_NOW,
    )


def _impacts_rel(
    source: str,
    target: str,
    rel_id: str = "r1",
    description: str = "A 改了什麼→B 的什麼要跟著看",
) -> Relationship:
    return Relationship(
        id=rel_id,
        source_entity_id=source,
        target_id=target,
        type=RelationshipType.IMPACTS,
        description=description,
    )


# ─────────────────────────────────────────────
# P1-2: impacts target validity enriched format (DC-1 ~ DC-5)
# ─────────────────────────────────────────────

class TestImpactsTargetValidityEnrichedFormat:

    def test_dc1_impacts_description_present(self):
        """DC-1: broken impact contains impacts_description from rel.description."""
        m1 = _entity("m1", "Module A")
        rel = _impacts_rel("m1", "ghost", description="pricing 改了→billing 要看")
        result = check_impacts_target_validity([m1], [rel])
        assert len(result) == 1
        broken = result[0]["broken_impacts"]
        assert broken[0]["impacts_description"] == "pricing 改了→billing 要看"

    def test_dc2_target_entity_name_present_when_found(self):
        """DC-2: broken impact contains target_entity_name when target exists."""
        m1 = _entity("m1", "Module A")
        m2 = _entity("m2", "Module B", status=EntityStatus.STALE)
        rel = _impacts_rel("m1", "m2")
        result = check_impacts_target_validity([m1, m2], [rel])
        broken = result[0]["broken_impacts"]
        assert broken[0]["target_entity_name"] == "Module B"

    def test_dc2_target_entity_name_none_when_missing(self):
        """DC-2: target_entity_name is None when target entity does not exist."""
        m1 = _entity("m1", "Module A")
        rel = _impacts_rel("m1", "ghost")
        result = check_impacts_target_validity([m1], [rel])
        broken = result[0]["broken_impacts"]
        assert broken[0]["target_entity_name"] is None

    def test_dc3_reason_target_missing(self):
        """DC-3: reason='target_missing' when target entity not found."""
        m1 = _entity("m1", "Module A")
        rel = _impacts_rel("m1", "ghost")
        result = check_impacts_target_validity([m1], [rel])
        assert result[0]["broken_impacts"][0]["reason"] == "target_missing"

    def test_dc3_reason_target_stale(self):
        """DC-3: reason='target_stale' when target status is stale."""
        m1 = _entity("m1", "Module A")
        m2 = _entity("m2", "Module B", status=EntityStatus.STALE)
        rel = _impacts_rel("m1", "m2")
        result = check_impacts_target_validity([m1, m2], [rel])
        assert result[0]["broken_impacts"][0]["reason"] == "target_stale"

    def test_dc3_reason_target_draft(self):
        """DC-3: reason='target_draft' when target status is draft."""
        m1 = _entity("m1", "Module A")
        m2 = _entity("m2", "Module B", status=EntityStatus.DRAFT)
        rel = _impacts_rel("m1", "m2")
        result = check_impacts_target_validity([m1, m2], [rel])
        assert result[0]["broken_impacts"][0]["reason"] == "target_draft"

    def test_dc4_suggested_action_target_missing(self):
        """DC-4: suggested_action corresponds to target_missing reason."""
        m1 = _entity("m1", "Module A")
        rel = _impacts_rel("m1", "ghost")
        result = check_impacts_target_validity([m1], [rel])
        action = result[0]["broken_impacts"][0]["suggested_action"]
        assert "不存在" in action or "移除" in action

    def test_dc4_suggested_action_target_stale(self):
        """DC-4: suggested_action corresponds to target_stale reason."""
        m1 = _entity("m1", "Module A")
        m2 = _entity("m2", "Module B", status=EntityStatus.STALE)
        rel = _impacts_rel("m1", "m2")
        result = check_impacts_target_validity([m1, m2], [rel])
        action = result[0]["broken_impacts"][0]["suggested_action"]
        assert "stale" in action or "替代" in action

    def test_dc4_suggested_action_target_draft(self):
        """DC-4: suggested_action corresponds to target_draft reason."""
        m1 = _entity("m1", "Module A")
        m2 = _entity("m2", "Module B", status=EntityStatus.DRAFT)
        rel = _impacts_rel("m1", "m2")
        result = check_impacts_target_validity([m1, m2], [rel])
        action = result[0]["broken_impacts"][0]["suggested_action"]
        assert "draft" in action or "confirm" in action


# ─────────────────────────────────────────────
# P0-2: quality correction priority (DC-6 ~ DC-10)
# ─────────────────────────────────────────────

class TestQualityCorrectionPriority:

    def test_dc6_pure_function_no_external_deps(self):
        """DC-6: compute_quality_correction_priority is a pure function."""
        # Can be called with just entities + relationships
        m = _entity("m1", "Module A", status=EntityStatus.DRAFT, summary="Short")
        result = compute_quality_correction_priority([m], [])
        assert isinstance(result, list)
        assert len(result) == 1

    def test_dc7_three_dimensions_present(self):
        """DC-7: ranked items contain all three dimensions."""
        m = _entity("m1", "Module A", status=EntityStatus.DRAFT, summary="Short")
        result = compute_quality_correction_priority([m], [])
        assert len(result) == 1
        dims = result[0]["dimensions"]
        assert "impacts_vagueness" in dims
        assert "summary_generality" in dims
        assert "three_q_confidence" in dims

    def test_dc7_impacts_vagueness_2_when_no_impacts(self):
        """DC-7: impacts_vagueness=2 when entity has no outgoing impacts."""
        m = _entity("m1", "Module A", status=EntityStatus.DRAFT)
        result = compute_quality_correction_priority([m], [])
        assert result[0]["dimensions"]["impacts_vagueness"] == 2

    def test_dc7_impacts_vagueness_0_when_concrete_impacts(self):
        """DC-7: impacts_vagueness=0 when entity has concrete impacts."""
        m1 = _entity("m1", "Module A", status=EntityStatus.ACTIVE)
        m2 = _entity("m2", "Module B", status=EntityStatus.ACTIVE)
        rel = _impacts_rel("m1", "m2", description="A 改了→B 的什麼要看")
        result = compute_quality_correction_priority([m1, m2], [rel])
        m1_result = next(r for r in result if r["entity_id"] == "m1")
        assert m1_result["dimensions"]["impacts_vagueness"] == 0

    def test_dc7_impacts_vagueness_1_when_vague_impacts(self):
        """DC-7: impacts_vagueness=1 when entity has impacts but without arrow."""
        m1 = _entity("m1", "Module A", status=EntityStatus.ACTIVE)
        m2 = _entity("m2", "Module B", status=EntityStatus.ACTIVE)
        rel = _impacts_rel("m1", "m2", description="A impacts B vaguely")
        result = compute_quality_correction_priority([m1, m2], [rel])
        m1_result = next(r for r in result if r["entity_id"] == "m1")
        assert m1_result["dimensions"]["impacts_vagueness"] == 1

    def test_dc7_summary_generality_2_when_short_summary(self):
        """DC-7: summary_generality=2 when summary < 30 chars."""
        m = _entity("m1", "Module A", status=EntityStatus.DRAFT, summary="Short")
        result = compute_quality_correction_priority([m], [])
        assert result[0]["dimensions"]["summary_generality"] == 2

    def test_dc7_summary_generality_0_when_technical_terms(self):
        """DC-7: summary_generality=0 when summary has technical terms."""
        m = _entity("m1", "Module A", status=EntityStatus.ACTIVE,
                    summary="Uses LLM for inference with API calls and schema validation")
        result = compute_quality_correction_priority([m], [])
        assert result[0]["dimensions"]["summary_generality"] == 0

    def test_dc7_three_q_confidence_2_draft_no_tags(self):
        """DC-7: three_q_confidence=2.0 for draft entity with no why/how."""
        m = _entity("m1", "Module A", status=EntityStatus.DRAFT,
                    tags=Tags(what="test", why="", how="", who="pm"))
        result = compute_quality_correction_priority([m], [])
        assert result[0]["dimensions"]["three_q_confidence"] == 2.0

    def test_dc7_three_q_confidence_0_active_with_tags(self):
        """DC-7: three_q_confidence=0.0 for active entity with why+how."""
        m = _entity("m1", "Module A", status=EntityStatus.ACTIVE,
                    tags=Tags(what="test", why="revenue reason", how="rules engine", who="pm"))
        result = compute_quality_correction_priority([m], [])
        assert result[0]["dimensions"]["three_q_confidence"] == 0.0

    def test_dc7_three_q_confidence_half_draft_with_layer_decision(self):
        """DC-7: three_q_confidence=0.5 for draft entity with layer_decision."""
        m = _entity("m1", "Module A", status=EntityStatus.DRAFT,
                    tags=Tags(what="test", why="", how="", who="pm"),
                    details={"layer_decision": {"q1_persistent": True}})
        result = compute_quality_correction_priority([m], [])
        assert result[0]["dimensions"]["three_q_confidence"] == 0.5

    def test_dc7_three_q_confidence_list_tags_no_attributeerror(self):
        """DC-7: tags.why/how as list must not raise AttributeError."""
        m = _entity("m1", "Module A", status=EntityStatus.ACTIVE,
                    tags=Tags(what=["feat"], why=["revenue reason"], how=["rules engine"], who=["pm"]))
        result = compute_quality_correction_priority([m], [])
        assert result[0]["dimensions"]["three_q_confidence"] == 0.0

    def test_dc7_three_q_confidence_empty_list_tags(self):
        """DC-7: empty list tags treated as missing why/how."""
        m = _entity("m1", "Module A", status=EntityStatus.DRAFT,
                    tags=Tags(what=[], why=[], how=[], who=[]))
        result = compute_quality_correction_priority([m], [])
        assert result[0]["dimensions"]["three_q_confidence"] == 2.0

    def test_dc8_score_formula_and_order(self):
        """DC-8: score = iv*0.5 + sg*0.3 + tq*0.2, sorted descending."""
        # High score: no impacts(2), short summary(2), draft no tags(2.0)
        high = _entity("h1", "High Score", status=EntityStatus.DRAFT,
                       summary="Short",
                       tags=Tags(what="x", why="", how="", who="pm"))
        # Low score: has concrete impacts(0), technical summary(0), active with tags(0)
        low = _entity("l1", "Low Score", status=EntityStatus.ACTIVE,
                      summary="Uses LLM for inference",
                      tags=Tags(what="x", why="revenue", how="llm", who="pm"))
        rel = _impacts_rel("l1", "h1")
        result = compute_quality_correction_priority([high, low], [rel])
        scores = [r["score"] for r in result]
        assert scores == sorted(scores, reverse=True)
        high_r = next(r for r in result if r["entity_id"] == "h1")
        low_r = next(r for r in result if r["entity_id"] == "l1")
        assert high_r["score"] > low_r["score"]
        # Verify formula: high = 2*0.5 + 2*0.3 + 2.0*0.2 = 1.0+0.6+0.4 = 2.0
        assert high_r["score"] == pytest.approx(2.0, abs=0.01)

    def test_dc9_top_repair_action_present(self):
        """DC-9 (from quality): ranked items have top_repair_action."""
        m = _entity("m1", "Module A", status=EntityStatus.DRAFT, summary="Short",
                    tags=Tags(what="x", why="", how="", who="pm"))
        result = compute_quality_correction_priority([m], [])
        assert "top_repair_action" in result[0]
        assert len(result[0]["top_repair_action"]) > 0

    def test_only_module_type_evaluated(self):
        """Only MODULE entities are evaluated, not product/goal/document."""
        prod = _entity("p1", "Product A", entity_type=EntityType.PRODUCT)
        mod = _entity("m1", "Module A", entity_type=EntityType.MODULE, status=EntityStatus.DRAFT)
        result = compute_quality_correction_priority([prod, mod], [])
        assert len(result) == 1
        assert result[0]["entity_id"] == "m1"

    def test_completed_modules_excluded(self):
        """Completed modules are not evaluated."""
        m = _entity("m1", "Module A", entity_type=EntityType.MODULE,
                    status=EntityStatus.COMPLETED)
        result = compute_quality_correction_priority([m], [])
        assert len(result) == 0


# ─────────────────────────────────────────────
# P0-1: layer_decision gate in OntologyService (DC-11 ~ DC-15)
# ─────────────────────────────────────────────

def _make_ontology_service() -> tuple:
    """Create OntologyService with mock repos."""
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

    parent = Entity(
        id="prod-1", name="Product", type="product",
        summary="Product", tags=Tags(what="x", why="x", how="x", who="x"),
    )
    entity_repo.get_by_id = AsyncMock(return_value=parent)

    svc = OntologyService(
        entity_repo=entity_repo,
        relationship_repo=relationship_repo,
        document_repo=AsyncMock(),
        protocol_repo=AsyncMock(),
        blindspot_repo=AsyncMock(),
    )
    return svc, entity_repo


_VALID_MODULE_DATA = {
    "name": "新模組",
    "type": "module",
    "summary": "公司共識概念，跨角色通用",
    "tags": {"what": "test", "why": "revenue", "how": "rules", "who": "pm"},
    "parent_id": "prod-1",
}

_VALID_LAYER_DECISION = {
    "q1_persistent": True,
    "q2_cross_role": True,
    "q3_company_consensus": True,
    "impacts_draft": "A 改了→B 的什麼要跟著看",
}


class TestLayerDecisionGate:

    async def test_dc11_new_module_without_layer_decision_raises(self):
        """DC-11: new MODULE without layer_decision and force=False raises LAYER_DECISION_REQUIRED."""
        svc, _ = _make_ontology_service()
        with pytest.raises(ValueError, match="LAYER_DECISION_REQUIRED"):
            await svc.upsert_entity(_VALID_MODULE_DATA)

    async def test_dc12_layer_decision_all_pass_writes_successfully(self):
        """DC-12 (pass case): layer_decision with all True → writes without error."""
        svc, _ = _make_ontology_service()
        data = {**_VALID_MODULE_DATA, "layer_decision": _VALID_LAYER_DECISION}
        result = await svc.upsert_entity(data)
        assert result.entity is not None
        assert result.entity.type == "module"

    async def test_dc12_layer_decision_q1_false_raises(self):
        """DC-12: layer_decision with q1=False → raises LAYER_DOWNGRADE_REQUIRED."""
        svc, _ = _make_ontology_service()
        layer_decision = {**_VALID_LAYER_DECISION, "q1_persistent": False}
        data = {**_VALID_MODULE_DATA, "layer_decision": layer_decision}
        with pytest.raises(ValueError, match="LAYER_DOWNGRADE_REQUIRED"):
            await svc.upsert_entity(data)

    async def test_dc12_layer_decision_q2_false_raises(self):
        """DC-12: layer_decision with q2=False → raises LAYER_DOWNGRADE_REQUIRED."""
        svc, _ = _make_ontology_service()
        layer_decision = {**_VALID_LAYER_DECISION, "q2_cross_role": False}
        data = {**_VALID_MODULE_DATA, "layer_decision": layer_decision}
        with pytest.raises(ValueError, match="LAYER_DOWNGRADE_REQUIRED"):
            await svc.upsert_entity(data)

    async def test_dc16a_layer_decision_all_pass_but_empty_impacts_draft_raises(self):
        """DC-16a: layer_decision with all True but empty impacts_draft → raises IMPACTS_DRAFT_REQUIRED."""
        svc, _ = _make_ontology_service()
        layer_decision = {
            "q1_persistent": True,
            "q2_cross_role": True,
            "q3_company_consensus": True,
            "impacts_draft": "",  # empty
        }
        data = {**_VALID_MODULE_DATA, "layer_decision": layer_decision}
        with pytest.raises(ValueError, match="IMPACTS_DRAFT_REQUIRED"):
            await svc.upsert_entity(data)

    async def test_dc16b_layer_decision_all_pass_but_missing_impacts_draft_raises(self):
        """DC-16b: layer_decision with all True but missing impacts_draft key → raises IMPACTS_DRAFT_REQUIRED."""
        svc, _ = _make_ontology_service()
        layer_decision = {
            "q1_persistent": True,
            "q2_cross_role": True,
            "q3_company_consensus": True,
            # impacts_draft missing
        }
        data = {**_VALID_MODULE_DATA, "layer_decision": layer_decision}
        with pytest.raises(ValueError, match="IMPACTS_DRAFT_REQUIRED"):
            await svc.upsert_entity(data)

    async def test_dc13_force_with_reason_bypasses_layer_decision(self):
        """DC-13: force=True + manual_override_reason → bypass succeeds, warning contains bypass message."""
        svc, _ = _make_ontology_service()
        data = {
            **_VALID_MODULE_DATA,
            "force": True,
            "manual_override_reason": "bootstrapping phase, no peers yet",
        }
        result = await svc.upsert_entity(data)
        assert result.entity is not None
        assert result.warnings is not None
        assert any("bypass layer_decision check" in w for w in result.warnings)

    async def test_dc14_update_existing_module_no_layer_decision_required(self):
        """DC-14: updating existing MODULE entity doesn't require layer_decision."""
        entity_repo = AsyncMock()
        existing_module = Entity(
            id="mod-1", name="Existing Module", type="module",
            summary="已存在的模組", parent_id="prod-1",
            tags=Tags(what="x", why="x", how="x", who="pm"),
            status="draft",
        )
        parent = Entity(
            id="prod-1", name="Product", type="product",
            summary="Product", tags=Tags(what="x", why="x", how="x", who="x"),
        )
        entity_repo.get_by_id = AsyncMock(
            side_effect=lambda eid: parent if eid == "prod-1" else existing_module
        )
        entity_repo.get_by_name = AsyncMock(return_value=None)
        entity_repo.list_all = AsyncMock(return_value=[parent, existing_module])
        entity_repo.upsert = AsyncMock(side_effect=lambda e: e)
        entity_repo.list_by_parent = AsyncMock(return_value=[])
        relationship_repo = AsyncMock()
        relationship_repo.list_by_entity = AsyncMock(return_value=[])
        relationship_repo.find_duplicate = AsyncMock(return_value=None)

        svc = OntologyService(
            entity_repo=entity_repo,
            relationship_repo=relationship_repo,
            document_repo=AsyncMock(),
            protocol_repo=AsyncMock(),
            blindspot_repo=AsyncMock(),
        )
        # Update should succeed without layer_decision
        result = await svc.upsert_entity({
            "id": "mod-1",
            "name": "Existing Module",
            "type": "module",
            "summary": "更新後的摘要",
            "tags": {"what": "x", "why": "x", "how": "x", "who": "pm"},
            "parent_id": "prod-1",
        })
        assert result.entity is not None

    async def test_dc15_layer_decision_stored_in_details(self):
        """DC-15: layer_decision value is stored in entity.details['layer_decision']."""
        svc, _ = _make_ontology_service()
        data = {**_VALID_MODULE_DATA, "layer_decision": _VALID_LAYER_DECISION}
        result = await svc.upsert_entity(data)
        assert result.entity.details is not None
        assert "layer_decision" in result.entity.details
        assert result.entity.details["layer_decision"]["q1_persistent"] is True


# ─────────────────────────────────────────────
# P1-3: document consistency detection (DC-16 ~ DC-19)
# ─────────────────────────────────────────────

class TestDocumentConsistencyDetection:

    def test_dc16_pure_function_returns_list(self):
        """DC-16: detect_stale_documents_from_consistency is a pure function."""
        result = detect_stale_documents_from_consistency([], [])
        assert isinstance(result, list)

    def test_dc17_version_lag_reason(self):
        """DC-17: version_lag reason when document version is >=2 major behind."""
        old_doc = _entity("d1", "設計文件 v1.0", entity_type=EntityType.DOCUMENT,
                          parent_id="mod-1", summary="v1.0 的設計")
        new_doc = _entity("d2", "設計文件 v3.0", entity_type=EntityType.DOCUMENT,
                          parent_id="mod-1", summary="v3.0 最新設計")
        mod = _entity("mod-1", "Module A")
        result = detect_stale_documents_from_consistency([old_doc, new_doc, mod], [])
        reasons = [w["reason"] for w in result]
        assert "version_lag" in reasons

    def test_dc17_contradictory_signal_reason(self):
        """DC-17: contradictory_signal reason when documents have opposing keywords."""
        doc1 = _entity("d1", "功能說明", entity_type=EntityType.DOCUMENT,
                       parent_id="mod-1", summary="此功能不支援大型資料集")
        doc2 = _entity("d2", "功能指南", entity_type=EntityType.DOCUMENT,
                       parent_id="mod-1", summary="此功能支援所有場景")
        mod = _entity("mod-1", "Module A")
        result = detect_stale_documents_from_consistency([doc1, doc2, mod], [])
        reasons = [w["reason"] for w in result]
        assert "contradictory_signal" in reasons

    def test_dc17_entity_updated_but_doc_stale_reason(self):
        """DC-17: entity_updated_but_doc_stale reason when L2 recently updated but doc is old."""
        recent = _NOW
        old_time = _NOW - timedelta(days=200)
        mod = _entity("mod-1", "Module A", entity_type=EntityType.MODULE,
                      updated_at=recent)
        old_doc = _entity("d1", "Old Documentation", entity_type=EntityType.DOCUMENT,
                          parent_id="mod-1", summary="Old doc",
                          updated_at=old_time)
        result = detect_stale_documents_from_consistency([mod, old_doc], [])
        reasons = [w["reason"] for w in result]
        assert "entity_updated_but_doc_stale" in reasons

    def test_dc17_warning_structure(self):
        """DC-17: each warning has required fields."""
        old_doc = _entity("d1", "設計文件 v1.0", entity_type=EntityType.DOCUMENT,
                          parent_id="mod-1", summary="v1.0 舊設計")
        new_doc = _entity("d2", "設計文件 v3.0", entity_type=EntityType.DOCUMENT,
                          parent_id="mod-1", summary="v3.0 新設計")
        mod = _entity("mod-1", "Module A")
        result = detect_stale_documents_from_consistency([old_doc, new_doc, mod], [])
        assert len(result) > 0
        warning = result[0]
        assert "document_id" in warning
        assert "document_title" in warning
        assert "reason" in warning
        assert "detail" in warning
        assert "suggested_action" in warning

    def test_no_false_positive_for_fresh_docs(self):
        """No warnings for fresh documents with no contradictions."""
        mod = _entity("mod-1", "Module A", updated_at=_NOW - timedelta(days=200))
        doc = _entity("d1", "Current Doc", entity_type=EntityType.DOCUMENT,
                      parent_id="mod-1", summary="This doc is current",
                      updated_at=_NOW - timedelta(days=10))
        result = detect_stale_documents_from_consistency([mod, doc], [])
        assert len(result) == 0


# ─────────────────────────────────────────────
# P1-1: task signal pure functions (DC-22)
# ─────────────────────────────────────────────

class TestTaskSignalPureFunctions:

    def test_dc22_task_problem_tokens_finds_keywords(self):
        """DC-22: _task_problem_tokens extracts problem keywords from text."""
        tokens = _task_problem_tokens(
            "遇到 workaround 問題無法繞過",
            "已知問題：LLM JSON 格式不穩定",
        )
        assert "workaround" in tokens or "問題" in tokens

    def test_dc22_task_problem_tokens_empty_for_clean_text(self):
        """DC-22: _task_problem_tokens returns empty set for clean task text."""
        tokens = _task_problem_tokens("完成了新功能開發", "實作自動化排程")
        # Should have no problem signal keywords
        from zenos.domain.governance import PROBLEM_SIGNAL_KEYWORDS
        assert len(tokens & PROBLEM_SIGNAL_KEYWORDS) == 0

    def test_dc22_tasks_are_similar_above_threshold(self):
        """DC-22: _tasks_are_similar returns True when overlap >= threshold."""
        tokens1 = {"workaround", "fail", "timeout"}
        tokens2 = {"workaround", "fail", "error"}
        assert _tasks_are_similar(tokens1, tokens2, threshold=2) is True

    def test_dc22_tasks_are_similar_below_threshold(self):
        """DC-22: _tasks_are_similar returns False when overlap < threshold."""
        tokens1 = {"workaround", "timeout"}
        tokens2 = {"error", "issue"}
        assert _tasks_are_similar(tokens1, tokens2, threshold=2) is False

    def test_dc22_blindspot_threshold_small_project(self):
        """DC-22: _blindspot_threshold returns 2 for < 20 tasks."""
        assert _blindspot_threshold(5) == 2
        assert _blindspot_threshold(19) == 2

    def test_dc22_blindspot_threshold_medium_project(self):
        """DC-22: _blindspot_threshold returns 3 for 20-100 tasks."""
        assert _blindspot_threshold(20) == 3
        assert _blindspot_threshold(100) == 3

    def test_dc22_blindspot_threshold_large_project(self):
        """DC-22: _blindspot_threshold returns 5 for > 100 tasks."""
        assert _blindspot_threshold(101) == 5
        assert _blindspot_threshold(500) == 5


# ─────────────────────────────────────────────
# P1-1: GovernanceService task_repo injection (DC-20, DC-21, DC-23)
# ─────────────────────────────────────────────

class TestGovernanceServiceTaskRepo:

    def test_dc20_governance_service_accepts_task_repo(self):
        """DC-20: GovernanceService.__init__ accepts task_repo parameter."""
        mock_task_repo = AsyncMock()
        svc = GovernanceService(
            entity_repo=AsyncMock(),
            relationship_repo=AsyncMock(),
            protocol_repo=AsyncMock(),
            blindspot_repo=AsyncMock(),
            task_repo=mock_task_repo,
        )
        assert svc._tasks is mock_task_repo

    def test_dc20_governance_service_task_repo_defaults_none(self):
        """DC-20: GovernanceService works without task_repo (defaults to None)."""
        svc = GovernanceService(
            entity_repo=AsyncMock(),
            relationship_repo=AsyncMock(),
            protocol_repo=AsyncMock(),
            blindspot_repo=AsyncMock(),
        )
        assert svc._tasks is None

    async def test_dc23_infer_blindspots_empty_when_no_task_repo(self):
        """DC-23: infer_blindspots_from_tasks returns empty list when task_repo is None."""
        svc = GovernanceService(
            entity_repo=AsyncMock(),
            relationship_repo=AsyncMock(),
            protocol_repo=AsyncMock(),
            blindspot_repo=AsyncMock(),
            task_repo=None,
        )
        result = await svc.infer_blindspots_from_tasks()
        assert result == []

    async def test_dc23_infer_blindspots_with_task_repo_returns_list(self):
        """DC-23: infer_blindspots_from_tasks returns list when task_repo is set."""
        entity_repo = AsyncMock()
        entity_repo.list_all = AsyncMock(return_value=[])

        task_repo = AsyncMock()
        task_repo.list_all = AsyncMock(return_value=[])

        svc = GovernanceService(
            entity_repo=entity_repo,
            relationship_repo=AsyncMock(),
            protocol_repo=AsyncMock(),
            blindspot_repo=AsyncMock(),
            task_repo=task_repo,
        )
        result = await svc.infer_blindspots_from_tasks()
        assert isinstance(result, list)


# ──────────────────────────────────────────────
# ADR-020: Health Signal KPI tests
# ──────────────────────────────────────────────

from zenos.domain.knowledge import Blindspot, Protocol


def _health_entity(
    entity_id: str = "e1",
    confirmed: bool = False,
) -> Entity:
    """Entity helper for health KPI tests."""
    return Entity(
        id=entity_id,
        name=f"Entity-{entity_id}",
        type=EntityType.MODULE,
        status=EntityStatus.ACTIVE,
        summary="Test",
        tags=Tags(what="test", why="test", how="test", who="dev"),
        confirmed_by_user=confirmed,
        created_at=_NOW,
        updated_at=_NOW + timedelta(days=1) if confirmed else _NOW,
    )


def _health_protocol(entity_id: str = "e1", confirmed: bool = False) -> Protocol:
    return Protocol(
        entity_id=entity_id,
        entity_name="Test",
        content={"what": {}, "why": {}, "how": {}, "who": {}},
        confirmed_by_user=confirmed,
        generated_at=_NOW,
        updated_at=_NOW + timedelta(days=1) if confirmed else _NOW,
    )


def _health_blindspot(
    description: str = "test blindspot",
    severity: str = "yellow",
    confirmed: bool = False,
) -> Blindspot:
    return Blindspot(
        description=description,
        severity=severity,
        related_entity_ids=["e1"],
        suggested_action="fix it",
        confirmed_by_user=confirmed,
        created_at=_NOW,
    )


class TestHealthKPIs:
    """ADR-020: compute_health_kpis pure function tests."""

    def test_all_green(self):
        """All KPIs within green thresholds."""
        entities = [
            _health_entity(entity_id=f"e{i}", confirmed=True)
            for i in range(5)
        ]
        protocols = [_health_protocol(f"e{i}", confirmed=True) for i in range(5)]
        blindspots = [_health_blindspot(f"issue {i}") for i in range(3)]

        result = compute_health_kpis(
            entities=entities,
            protocols=protocols,
            blindspots=blindspots,
            quality_score=80,
            l2_repairs_count=0,
        )

        assert result["overall_level"] == "green"
        assert result["recommended_action"] is None
        assert result["red_reasons"] == []
        assert result["kpis"]["quality_score"]["level"] == "green"

    def test_yellow_quality_score(self):
        """Quality score between 50 and 70 → yellow."""
        result = compute_health_kpis(
            entities=[_health_entity(confirmed=True)],
            protocols=[],
            blindspots=[],
            quality_score=60,
            l2_repairs_count=0,
        )

        assert result["kpis"]["quality_score"]["level"] == "yellow"
        assert result["kpis"]["quality_score"]["value"] == 60

    def test_red_quality_score(self):
        """Quality score below 50 → red."""
        result = compute_health_kpis(
            entities=[_health_entity(confirmed=True)],
            protocols=[],
            blindspots=[],
            quality_score=30,
            l2_repairs_count=0,
        )

        assert result["kpis"]["quality_score"]["level"] == "red"
        assert result["overall_level"] == "red"
        assert result["recommended_action"] == "run_governance"
        red_kpis = [r["kpi"] for r in result["red_reasons"]]
        assert "quality_score" in red_kpis

    def test_red_l2_missing_impacts(self):
        """active_l2_missing_impacts > 3 → red."""
        result = compute_health_kpis(
            entities=[_health_entity(confirmed=True)],
            protocols=[],
            blindspots=[],
            quality_score=80,
            l2_repairs_count=5,
        )

        kpi = result["kpis"]["active_l2_missing_impacts"]
        assert kpi["value"] == 5
        assert kpi["level"] == "red"
        assert result["overall_level"] == "red"
        red_kpis = [r["kpi"] for r in result["red_reasons"]]
        assert "active_l2_missing_impacts" in red_kpis

    def test_unconfirmed_ratio_high(self):
        """All items unconfirmed → high unconfirmed_ratio."""
        entities = [_health_entity(entity_id=f"e{i}", confirmed=False) for i in range(5)]
        result = compute_health_kpis(
            entities=entities,
            protocols=[],
            blindspots=[],
            quality_score=80,
            l2_repairs_count=0,
        )

        assert result["kpis"]["unconfirmed_ratio"]["value"] == 1.0
        assert result["kpis"]["unconfirmed_ratio"]["level"] == "red"

    def test_bootstrap_relaxes_unconfirmed_threshold(self):
        """Bootstrap mode uses relaxed thresholds for unconfirmed_ratio."""
        # 40% unconfirmed: normal → yellow, bootstrap → green
        entities = [
            _health_entity(entity_id=f"e{i}", confirmed=(i < 3))
            for i in range(5)
        ]
        result_normal = compute_health_kpis(
            entities=entities, protocols=[], blindspots=[],
            quality_score=80, l2_repairs_count=0, bootstrap=False,
        )
        result_bootstrap = compute_health_kpis(
            entities=entities, protocols=[], blindspots=[],
            quality_score=80, l2_repairs_count=0, bootstrap=True,
        )

        assert result_normal["kpis"]["unconfirmed_ratio"]["level"] == "yellow"
        assert result_bootstrap["kpis"]["unconfirmed_ratio"]["level"] == "green"

    def test_duplicate_blindspot_rate(self):
        """Duplicate blindspots are correctly detected."""
        blindspots = [
            _health_blindspot("same issue", "yellow"),
            _health_blindspot("same issue", "yellow"),
            _health_blindspot("different issue", "red"),
        ]
        result = compute_health_kpis(
            entities=[_health_entity()],
            protocols=[],
            blindspots=blindspots,
            quality_score=80,
            l2_repairs_count=0,
        )

        rate = result["kpis"]["duplicate_blindspot_rate"]["value"]
        assert rate > 0.3  # 1 duplicate out of 3

    def test_empty_ontology(self):
        """Empty ontology → green (no items to fail)."""
        result = compute_health_kpis(
            entities=[], protocols=[], blindspots=[],
            quality_score=80, l2_repairs_count=0,
        )

        assert result["overall_level"] == "green"
        assert result["kpis"]["unconfirmed_ratio"]["value"] == 0.0


class TestDetermineRecommendedAction:
    def test_green(self):
        assert determine_recommended_action("green") is None

    def test_yellow(self):
        assert determine_recommended_action("yellow") == "review_health"

    def test_red(self):
        assert determine_recommended_action("red") == "run_governance"


class TestKPILevel:
    def test_quality_score_levels(self):
        assert _kpi_level("quality_score", 80) == "green"
        assert _kpi_level("quality_score", 60) == "yellow"
        assert _kpi_level("quality_score", 40) == "red"

    def test_blindspot_total_levels(self):
        assert _kpi_level("blindspot_total", 10) == "green"
        assert _kpi_level("blindspot_total", 30) == "yellow"
        assert _kpi_level("blindspot_total", 60) == "red"
