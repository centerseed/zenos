"""Tests for GovernanceAI — LLM-based write-path inference.

Unit tests mock the LLM client. Integration tests mock GovernanceAI itself
to verify OntologyService and TaskService integration.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from zenos.application.governance_ai import (
    GovernanceAI,
    GovernanceInference,
    InferredRel,
    TaskLinkInference,
)
from zenos.application.ontology_service import OntologyService
from zenos.application.task_service import TaskService
from zenos.domain.models import Entity, Tags


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_repos() -> dict:
    """Build AsyncMock repositories for OntologyService."""
    entity_repo = AsyncMock()
    entity_repo.get_by_id = AsyncMock(return_value=None)
    entity_repo.get_by_name = AsyncMock(return_value=None)
    entity_repo.upsert = AsyncMock(side_effect=lambda e: e)
    entity_repo.list_all = AsyncMock(return_value=[])

    relationship_repo = AsyncMock()
    relationship_repo.add = AsyncMock(side_effect=lambda r: r)
    relationship_repo.list_by_entity = AsyncMock(return_value=[])
    relationship_repo.find_duplicate = AsyncMock(return_value=None)

    document_repo = AsyncMock()
    document_repo.list_by_entity = AsyncMock(return_value=[])
    document_repo.list_all = AsyncMock(return_value=[])
    document_repo.upsert = AsyncMock(side_effect=lambda d: d)
    document_repo.update_linked_entities = AsyncMock()

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


def _valid_entity_data(**overrides) -> dict:
    defaults = {
        "name": "Paceriz",
        "type": "product",
        "summary": "A running coach app",
        "tags": {"what": "app", "why": "coaching", "how": "AI", "who": "runners"},
        "status": "active",
    }
    defaults.update(overrides)
    return defaults


def _make_entity(name="Paceriz", eid="ent-1", etype="product", **kw) -> Entity:
    return Entity(
        id=eid, name=name, type=etype,
        summary=kw.get("summary", "test"),
        tags=Tags(what="x", why="x", how="x", who="x"),
        **{k: v for k, v in kw.items() if k != "summary"},
    )


# ===========================================================================
# 1. _rule_classify unit tests (no LLM, no mock needed)
# ===========================================================================


class TestRuleClassify:

    def test_android_prefix_is_module(self):
        ai = GovernanceAI(MagicMock())
        t, p = ai._rule_classify("Android Auth", [
            {"id": "p1", "name": "Paceriz", "type": "product"},
        ])
        assert t == "module"
        assert p == "p1"

    def test_ios_prefix_is_module(self):
        ai = GovernanceAI(MagicMock())
        t, p = ai._rule_classify("iOS App", [
            {"id": "p1", "name": "Paceriz", "type": "product"},
        ])
        assert t == "module"
        assert p == "p1"

    def test_web_prefix_is_module(self):
        ai = GovernanceAI(MagicMock())
        t, p = ai._rule_classify("Web Dashboard", [
            {"id": "p1", "name": "MyApp", "type": "product"},
        ])
        assert t == "module"
        assert p == "p1"

    def test_no_prefix_returns_none(self):
        ai = GovernanceAI(MagicMock())
        t, p = ai._rule_classify("TrainingPlan", [
            {"id": "p1", "name": "Paceriz", "type": "product"},
        ])
        assert t is None
        assert p is None

    def test_multiple_products_no_parent(self):
        ai = GovernanceAI(MagicMock())
        t, p = ai._rule_classify("Android Auth", [
            {"id": "p1", "name": "Paceriz", "type": "product"},
            {"id": "p2", "name": "ZenOS", "type": "product"},
        ])
        assert t == "module"
        assert p is None  # ambiguous, can't auto-assign

    def test_no_products_no_parent(self):
        ai = GovernanceAI(MagicMock())
        t, p = ai._rule_classify("Android Auth", [])
        assert t == "module"
        assert p is None


# ===========================================================================
# 2. infer_all unit tests (mock LLM)
# ===========================================================================


class TestInferAll:

    def test_returns_inference(self):
        llm = MagicMock()
        llm.chat_structured.return_value = GovernanceInference(
            type="module",
            parent_id="p1",
            duplicate_of=None,
            rels=[InferredRel(target="m1", type="related_to")],
            doc_links=["d1"],
        )
        ai = GovernanceAI(llm)
        result = ai.infer_all(
            {"name": "Auth", "summary": "User auth"},
            [{"id": "p1", "name": "Paceriz", "type": "product"}],
            [{"id": "d1", "title": "Auth spec"}],
        )
        assert result is not None
        assert result.type == "module"
        assert result.parent_id == "p1"
        assert len(result.rels) == 1
        assert result.doc_links == ["d1"]

    def test_returns_none_on_exception(self):
        llm = MagicMock()
        llm.chat_structured.side_effect = RuntimeError("LLM down")
        ai = GovernanceAI(llm)
        result = ai.infer_all(
            {"name": "X", "summary": "Y"},
            [{"id": "e1", "name": "E", "type": "product"}],
            [],
        )
        assert result is None

    def test_returns_none_on_empty_inputs(self):
        llm = MagicMock()
        ai = GovernanceAI(llm)
        result = ai.infer_all({"name": "X", "summary": "Y"}, [], [])
        assert result is None
        llm.chat_structured.assert_not_called()

    def test_duplicate_detection(self):
        llm = MagicMock()
        llm.chat_structured.return_value = GovernanceInference(
            duplicate_of="ent-1",
        )
        ai = GovernanceAI(llm)
        result = ai.infer_all(
            {"name": "Auth Module", "summary": "auth"},
            [{"id": "ent-1", "name": "Authentication", "type": "module"}],
            [],
        )
        assert result is not None
        assert result.duplicate_of == "ent-1"


# ===========================================================================
# 3. infer_task_links unit tests (mock LLM)
# ===========================================================================


class TestInferTaskLinks:

    def test_returns_entity_ids(self):
        llm = MagicMock()
        llm.chat_structured.return_value = TaskLinkInference(
            entity_ids=["ent-1"],
        )
        ai = GovernanceAI(llm)
        result = ai.infer_task_links(
            "Fix auth bug", "Login broken",
            [{"id": "ent-1", "name": "Auth", "type": "module"}],
        )
        assert result == ["ent-1"]

    def test_returns_empty_on_exception(self):
        llm = MagicMock()
        llm.chat_structured.side_effect = RuntimeError("LLM down")
        ai = GovernanceAI(llm)
        result = ai.infer_task_links("X", "Y", [{"id": "e1", "name": "E", "type": "module"}])
        assert result == []

    def test_returns_empty_on_no_entities(self):
        llm = MagicMock()
        ai = GovernanceAI(llm)
        result = ai.infer_task_links("X", "Y", [])
        assert result == []
        llm.chat_structured.assert_not_called()


# ===========================================================================
# 4. OntologyService integration tests (mock GovernanceAI)
# ===========================================================================


class TestOntologyServiceGovernanceAI:

    async def test_upsert_without_type_rule_classify(self):
        """When type is missing and rule matches, _rule_classify fills it."""
        repos = _mock_repos()

        def _set_id(e):
            e.id = e.id or "auto-id"
            return e
        repos["entity_repo"].upsert = AsyncMock(side_effect=_set_id)

        # Need a product entity for rule_classify to find parent
        product = _make_entity("Paceriz", "p1", "product")
        repos["entity_repo"].list_all = AsyncMock(return_value=[product])
        repos["entity_repo"].get_by_id = AsyncMock(return_value=product)

        gov_ai = MagicMock()
        gov_ai._rule_classify.return_value = ("module", "p1")
        gov_ai.infer_all.return_value = None

        svc = OntologyService(**repos, governance_ai=gov_ai)
        data = _valid_entity_data(name="Android Auth")
        del data["type"]
        result = await svc.upsert_entity(data)
        gov_ai._rule_classify.assert_called_once()
        assert result.entity.type == "module"
        assert result.warnings is not None
        assert any("規則分類" in w for w in result.warnings)

    async def test_upsert_without_type_llm_fallback(self):
        """When rule can't classify, infer_all is used for classification."""
        repos = _mock_repos()

        def _set_id(e):
            e.id = e.id or "auto-id"
            return e
        repos["entity_repo"].upsert = AsyncMock(side_effect=_set_id)

        gov_ai = MagicMock()
        gov_ai._rule_classify.return_value = (None, None)
        # Pre-save infer_all for classify
        gov_ai.infer_all.side_effect = [
            GovernanceInference(type="product"),  # pre-save classify
            None,  # post-save rels+docs
        ]

        svc = OntologyService(**repos, governance_ai=gov_ai)
        data = _valid_entity_data()
        del data["type"]
        result = await svc.upsert_entity(data)
        assert result.entity.type == "product"
        assert result.warnings is not None
        assert any("推薦 type=" in w for w in result.warnings)

    async def test_upsert_with_type_skips_classify(self):
        """When type is provided, classify should NOT be called."""
        repos = _mock_repos()
        gov_ai = MagicMock()
        gov_ai.infer_all.return_value = None

        svc = OntologyService(**repos, governance_ai=gov_ai)
        result = await svc.upsert_entity(_valid_entity_data(type="product"))
        assert result.entity.type == "product"
        gov_ai._rule_classify.assert_not_called()

    async def test_upsert_auto_infers_relationships(self):
        """After saving, infer_all returns rels that get created."""
        repos = _mock_repos()
        existing = _make_entity("DataModule", "ent-2", "module")
        repos["entity_repo"].list_all = AsyncMock(return_value=[existing])
        repos["entity_repo"].get_by_id = AsyncMock(return_value=existing)

        def _set_id(e):
            e.id = e.id or "new-ent-id"
            return e
        repos["entity_repo"].upsert = AsyncMock(side_effect=_set_id)

        gov_ai = MagicMock()
        gov_ai.infer_all.return_value = GovernanceInference(
            rels=[InferredRel(target="ent-2", type="depends_on")],
        )

        svc = OntologyService(**repos, governance_ai=gov_ai)
        result = await svc.upsert_entity(_valid_entity_data())
        assert result.warnings is not None
        assert any("自動建立關係" in w for w in result.warnings)
        repos["relationship_repo"].add.assert_called_once()

    async def test_upsert_confirmed_entity_merge_only(self):
        """Updating a confirmed entity only fills empty fields."""
        repos = _mock_repos()
        confirmed = Entity(
            id="ent-1", name="Paceriz", type="product",
            summary="Original summary",
            tags=Tags(what="app", why="", how="AI", who="runners"),
            confirmed_by_user=True,
        )
        repos["entity_repo"].get_by_id = AsyncMock(return_value=confirmed)
        repos["entity_repo"].get_by_name = AsyncMock(return_value=confirmed)

        svc = OntologyService(**repos)
        result = await svc.upsert_entity(_valid_entity_data(
            id="ent-1",
            summary="New summary",
            tags={"what": "new-what", "why": "coaching", "how": "new-how", "who": "new-who"},
        ))
        assert result.entity.summary == "Original summary"
        assert result.entity.tags.why == "coaching"
        assert result.entity.tags.what == "app"
        assert result.warnings is not None
        assert any("已確認" in w for w in result.warnings)

    async def test_governance_ai_none_preserves_existing_behavior(self):
        """When governance_ai=None, all existing behavior is unchanged."""
        repos = _mock_repos()
        svc = OntologyService(**repos, governance_ai=None)
        result = await svc.upsert_entity(_valid_entity_data())
        assert result.entity.name == "Paceriz"

    async def test_upsert_duplicate_detected_returns_existing(self):
        """When infer_all detects duplicate during classify, return existing entity."""
        repos = _mock_repos()
        existing = _make_entity("Paceriz", "ent-1", "product")
        repos["entity_repo"].get_by_id = AsyncMock(return_value=existing)
        repos["entity_repo"].list_all = AsyncMock(return_value=[existing])

        gov_ai = MagicMock()
        gov_ai._rule_classify.return_value = (None, None)
        gov_ai.infer_all.return_value = GovernanceInference(
            type="product",
            duplicate_of="ent-1",
        )

        svc = OntologyService(**repos, governance_ai=gov_ai)
        data = _valid_entity_data()
        del data["type"]
        result = await svc.upsert_entity(data)
        assert result.entity.id == "ent-1"
        assert result.warnings is not None
        assert any("語意重複" in w for w in result.warnings)

    async def test_auto_link_documents_via_infer_all(self):
        """infer_all doc_links trigger relationship creation for document entities."""
        repos = _mock_repos()
        # Create a document entity (type="document") instead of legacy Document
        doc_entity = _make_entity("Auth spec", "doc-1", "document")
        repos["entity_repo"].list_all = AsyncMock(return_value=[doc_entity])

        def _set_id(e):
            e.id = e.id or "new-ent-id"
            return e
        repos["entity_repo"].upsert = AsyncMock(side_effect=_set_id)
        repos["entity_repo"].get_by_id = AsyncMock(return_value=doc_entity)

        gov_ai = MagicMock()
        gov_ai.infer_all.return_value = GovernanceInference(
            doc_links=["doc-1"],
        )

        svc = OntologyService(**repos, governance_ai=gov_ai)
        result = await svc.upsert_entity(_valid_entity_data())
        # Document links now create relationships instead of update_linked_entities
        repos["relationship_repo"].add.assert_called_once()


# ===========================================================================
# 5. TaskService integration tests (mock GovernanceAI)
# ===========================================================================


class TestTaskServiceGovernanceAI:

    async def test_create_task_without_entities_triggers_auto_link(self):
        """When linked_entities is empty, GovernanceAI.infer_task_links is called."""
        repos = _mock_repos()
        task_repo = AsyncMock()
        task_repo.upsert = AsyncMock(side_effect=lambda t: t)

        existing = _make_entity("Auth", "ent-1")
        repos["entity_repo"].list_all = AsyncMock(return_value=[existing])
        repos["entity_repo"].get_by_id = AsyncMock(return_value=existing)

        gov_ai = MagicMock()
        gov_ai.infer_task_links.return_value = ["ent-1"]

        svc = TaskService(
            task_repo=task_repo,
            entity_repo=repos["entity_repo"],
            blindspot_repo=repos["blindspot_repo"],
            document_repo=repos["document_repo"],
            governance_ai=gov_ai,
        )
        result = await svc.create_task({
            "title": "Fix auth bug",
            "created_by": "dev",
            "description": "Login broken",
        })
        gov_ai.infer_task_links.assert_called_once()
        assert "ent-1" in result.task.linked_entities

    async def test_create_task_with_entities_skips_auto_link(self):
        """When linked_entities is provided, GovernanceAI is NOT called."""
        repos = _mock_repos()
        task_repo = AsyncMock()
        task_repo.upsert = AsyncMock(side_effect=lambda t: t)

        existing = _make_entity("Auth", "ent-1")
        repos["entity_repo"].get_by_id = AsyncMock(return_value=existing)

        gov_ai = MagicMock()

        svc = TaskService(
            task_repo=task_repo,
            entity_repo=repos["entity_repo"],
            blindspot_repo=repos["blindspot_repo"],
            governance_ai=gov_ai,
        )
        result = await svc.create_task({
            "title": "Fix auth bug",
            "created_by": "dev",
            "linked_entities": ["ent-1"],
        })
        gov_ai.infer_task_links.assert_not_called()
        assert "ent-1" in result.task.linked_entities

    async def test_create_task_governance_ai_none_works(self):
        """When governance_ai=None, existing behavior is preserved."""
        repos = _mock_repos()
        task_repo = AsyncMock()
        task_repo.upsert = AsyncMock(side_effect=lambda t: t)

        svc = TaskService(
            task_repo=task_repo,
            entity_repo=repos["entity_repo"],
            blindspot_repo=repos["blindspot_repo"],
            governance_ai=None,
        )
        result = await svc.create_task({
            "title": "Fix bug",
            "created_by": "dev",
        })
        assert result.task.title == "Fix bug"
