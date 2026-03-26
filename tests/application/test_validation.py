"""Tests for write-path validation in OntologyService and TaskService.

Uses in-memory mock repositories to verify that validation raises ValueError
with descriptive messages before any persistence occurs.
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock

import pytest

from zenos.application.ontology_service import OntologyService
from zenos.application.task_service import TaskService
from zenos.application.governance_ai import GovernanceInference, InferredRel
from zenos.domain.models import Blindspot, Entity, Protocol, Relationship, Tags, Task


# ---------------------------------------------------------------------------
# Mock repository factory
# ---------------------------------------------------------------------------

def _mock_repos() -> dict:
    """Build a set of AsyncMock repositories for OntologyService."""
    entity_repo = AsyncMock()
    entity_repo.get_by_id = AsyncMock(return_value=None)
    entity_repo.get_by_name = AsyncMock(return_value=None)
    entity_repo.list_all = AsyncMock(return_value=[])
    entity_repo.upsert = AsyncMock(side_effect=lambda e: e)

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


def _make_service(repos: dict | None = None) -> OntologyService:
    r = repos or _mock_repos()
    return OntologyService(**r)


def _valid_entity_data(**overrides) -> dict:
    """Minimal valid entity data dict."""
    defaults = {
        "name": "Paceriz",
        "type": "product",
        "summary": "A running coach app",
        "tags": {"what": "app", "why": "coaching", "how": "AI", "who": "runners"},
        "status": "active",
    }
    defaults.update(overrides)
    return defaults


# ---------------------------------------------------------------------------
# upsert_entity validation
# ---------------------------------------------------------------------------

class TestUpsertEntityValidation:

    async def test_name_too_short(self):
        svc = _make_service()
        with pytest.raises(ValueError, match="2-80 characters"):
            await svc.upsert_entity(_valid_entity_data(name="X"))

    async def test_name_empty(self):
        svc = _make_service()
        with pytest.raises(ValueError, match="2-80 characters"):
            await svc.upsert_entity(_valid_entity_data(name=""))

    async def test_name_too_long(self):
        svc = _make_service()
        with pytest.raises(ValueError, match="2-80 characters"):
            await svc.upsert_entity(_valid_entity_data(name="A" * 81))

    async def test_name_with_parenthetical(self):
        svc = _make_service()
        with pytest.raises(ValueError, match="parenthetical"):
            await svc.upsert_entity(_valid_entity_data(name="Training Plan (iOS)"))

    async def test_name_with_parenthetical_english(self):
        svc = _make_service()
        with pytest.raises(ValueError, match="parenthetical"):
            await svc.upsert_entity(_valid_entity_data(name="Paceriz (English)"))

    async def test_name_stripped(self):
        """Leading/trailing whitespace should be stripped before validation."""
        repos = _mock_repos()
        svc = _make_service(repos)
        result = await svc.upsert_entity(_valid_entity_data(name="  Paceriz  "))
        assert result.entity.name == "Paceriz"

    async def test_invalid_type(self):
        svc = _make_service()
        with pytest.raises(ValueError, match="Invalid entity type"):
            await svc.upsert_entity(_valid_entity_data(type="widget"))

    async def test_invalid_status(self):
        svc = _make_service()
        with pytest.raises(ValueError, match="Invalid entity status"):
            await svc.upsert_entity(_valid_entity_data(status="deleted"))

    async def test_tags_missing_dimension(self):
        svc = _make_service()
        with pytest.raises(ValueError, match="Tags missing required dimensions"):
            await svc.upsert_entity(_valid_entity_data(
                tags={"what": "app", "why": "coaching"}
            ))

    async def test_tags_not_dict(self):
        svc = _make_service()
        with pytest.raises(ValueError, match="Tags must be a dict"):
            await svc.upsert_entity(_valid_entity_data(tags="invalid"))

    async def test_module_without_parent_id(self):
        svc = _make_service()
        with pytest.raises(ValueError, match="parent_id"):
            await svc.upsert_entity(_valid_entity_data(type="module"))

    async def test_module_with_parent_id_passes(self):
        repos = _mock_repos()
        parent = Entity(
            id="parent-1", name="Product", type="product",
            summary="Parent", tags=Tags(what="x", why="x", how="x", who="x"),
        )
        repos["entity_repo"].get_by_id = AsyncMock(return_value=parent)
        repos["entity_repo"].get_by_name = AsyncMock(return_value=None)
        svc = _make_service(repos)
        result = await svc.upsert_entity(
            _valid_entity_data(type="module", parent_id="parent-1")
        )
        assert result.entity.type == "module"

    async def test_new_l2_without_concrete_impacts_is_rejected(self):
        repos = _mock_repos()
        parent = Entity(
            id="parent-1", name="Product", type="product",
            summary="Parent", tags=Tags(what="x", why="x", how="x", who="x"),
        )
        repos["entity_repo"].get_by_id = AsyncMock(return_value=parent)
        repos["entity_repo"].get_by_name = AsyncMock(return_value=None)
        repos["entity_repo"].list_all = AsyncMock(return_value=[parent])

        class _Gov:
            def infer_all(self, entity_data, existing_entities, unlinked_docs):
                return GovernanceInference(
                    rels=[],
                    impacts_context_status="insufficient",
                    impacts_context_gaps=["缺少候選下游實體摘要"],
                )

        svc = OntologyService(
            entity_repo=repos["entity_repo"],
            relationship_repo=repos["relationship_repo"],
            document_repo=repos["document_repo"],
            protocol_repo=repos["protocol_repo"],
            blindspot_repo=repos["blindspot_repo"],
            governance_ai=_Gov(),
        )
        with pytest.raises(ValueError, match="Context gaps: 缺少候選下游實體摘要"):
            await svc.upsert_entity(_valid_entity_data(type="module", parent_id="parent-1"))

    async def test_new_l2_with_concrete_impacts_passes_hard_rule(self):
        repos = _mock_repos()
        parent = Entity(
            id="parent-1", name="Product", type="product",
            summary="Parent", tags=Tags(what="x", why="x", how="x", who="x"),
        )
        repos["entity_repo"].get_by_id = AsyncMock(return_value=parent)
        repos["entity_repo"].get_by_name = AsyncMock(return_value=None)
        repos["entity_repo"].list_all = AsyncMock(return_value=[parent])

        class _Gov:
            def infer_all(self, entity_data, existing_entities, unlinked_docs):
                return GovernanceInference(
                    rels=[
                        InferredRel(
                            target="parent-1",
                            type="impacts",
                            description="A 改了規則→B 的監控指標要跟著看",
                        )
                    ]
                )

        svc = OntologyService(
            entity_repo=repos["entity_repo"],
            relationship_repo=repos["relationship_repo"],
            document_repo=repos["document_repo"],
            protocol_repo=repos["protocol_repo"],
            blindspot_repo=repos["blindspot_repo"],
            governance_ai=_Gov(),
        )
        result = await svc.upsert_entity(_valid_entity_data(type="module", parent_id="parent-1"))
        assert result.entity.type == "module"

    async def test_nonexistent_parent_id(self):
        svc = _make_service()
        with pytest.raises(ValueError, match="does not exist"):
            await svc.upsert_entity(
                _valid_entity_data(type="module", parent_id="nonexistent")
            )

    async def test_duplicate_name_type(self):
        repos = _mock_repos()
        existing = Entity(
            id="ent-1", name="Paceriz", type="product",
            summary="Old", tags=Tags(what="x", why="x", how="x", who="x"),
        )
        repos["entity_repo"].get_by_name = AsyncMock(return_value=existing)
        svc = _make_service(repos)
        with pytest.raises(ValueError, match="already exists"):
            await svc.upsert_entity(_valid_entity_data())

    async def test_update_existing_entity_skips_duplicate_check(self):
        """Providing id= should skip duplicate name+type check."""
        repos = _mock_repos()
        existing = Entity(
            id="ent-1", name="Paceriz", type="product",
            summary="Old", tags=Tags(what="x", why="x", how="x", who="x"),
        )
        repos["entity_repo"].get_by_id = AsyncMock(return_value=existing)
        repos["entity_repo"].get_by_name = AsyncMock(return_value=existing)
        svc = _make_service(repos)
        # Should not raise because id is provided
        result = await svc.upsert_entity(_valid_entity_data(id="ent-1"))
        assert result.entity.name == "Paceriz"

    async def test_valid_entity_passes(self):
        repos = _mock_repos()
        svc = _make_service(repos)
        result = await svc.upsert_entity(_valid_entity_data())
        assert result.entity.name == "Paceriz"
        assert result.tag_confidence is not None


# ---------------------------------------------------------------------------
# add_relationship validation
# ---------------------------------------------------------------------------

class TestAddRelationshipValidation:

    async def test_nonexistent_source(self):
        svc = _make_service()
        with pytest.raises(ValueError, match="Source entity"):
            await svc.add_relationship("bad-id", "ent-2", "depends_on", "test")

    async def test_nonexistent_target(self):
        repos = _mock_repos()
        source = Entity(
            id="ent-1", name="A", type="product",
            summary="X", tags=Tags(what="x", why="x", how="x", who="x"),
        )
        repos["entity_repo"].get_by_id = AsyncMock(
            side_effect=lambda eid: source if eid == "ent-1" else None
        )
        svc = _make_service(repos)
        with pytest.raises(ValueError, match="Target entity"):
            await svc.add_relationship("ent-1", "bad-id", "depends_on", "test")

    async def test_invalid_rel_type(self):
        repos = _mock_repos()
        entity = Entity(
            id="ent-1", name="A", type="product",
            summary="X", tags=Tags(what="x", why="x", how="x", who="x"),
        )
        repos["entity_repo"].get_by_id = AsyncMock(return_value=entity)
        svc = _make_service(repos)
        with pytest.raises(ValueError, match="Invalid relationship type"):
            await svc.add_relationship("ent-1", "ent-2", "likes", "test")

    async def test_valid_relationship_passes(self):
        repos = _mock_repos()
        entity = Entity(
            id="ent-1", name="A", type="product",
            summary="X", tags=Tags(what="x", why="x", how="x", who="x"),
        )
        repos["entity_repo"].get_by_id = AsyncMock(return_value=entity)
        svc = _make_service(repos)
        result = await svc.add_relationship("ent-1", "ent-2", "depends_on", "test")
        assert result.type == "depends_on"


# ---------------------------------------------------------------------------
# add_blindspot validation
# ---------------------------------------------------------------------------

class TestAddBlindspotValidation:

    async def test_invalid_severity(self):
        svc = _make_service()
        with pytest.raises(ValueError, match="Invalid severity"):
            await svc.add_blindspot({
                "description": "Missing docs",
                "severity": "purple",
                "suggested_action": "Add docs",
            })

    async def test_empty_description(self):
        svc = _make_service()
        with pytest.raises(ValueError, match="description is required"):
            await svc.add_blindspot({
                "description": "",
                "severity": "red",
                "suggested_action": "Fix it",
            })

    async def test_empty_suggested_action(self):
        svc = _make_service()
        with pytest.raises(ValueError, match="suggested_action is required"):
            await svc.add_blindspot({
                "description": "Something wrong",
                "severity": "yellow",
                "suggested_action": "",
            })

    async def test_nonexistent_related_entity(self):
        svc = _make_service()
        with pytest.raises(ValueError, match="not found"):
            await svc.add_blindspot({
                "description": "Missing docs",
                "severity": "red",
                "suggested_action": "Add docs",
                "related_entity_ids": ["nonexistent"],
            })

    async def test_valid_blindspot_passes(self):
        svc = _make_service()
        result = await svc.add_blindspot({
            "description": "Missing monitoring",
            "severity": "red",
            "suggested_action": "Add monitoring",
        })
        assert result.severity == "red"

    async def test_duplicate_blindspot_returns_existing(self):
        repos = _mock_repos()
        existing = Blindspot(
            id="bs-1",
            description="Missing monitoring",
            severity="red",
            related_entity_ids=["ent-1"],
            suggested_action="Add monitoring",
            status="open",
            confirmed_by_user=False,
        )
        repos["blindspot_repo"].list_all = AsyncMock(return_value=[existing])
        repos["blindspot_repo"].add = AsyncMock(side_effect=lambda b: b)

        # Make related entity valid for input validation
        repos["entity_repo"].get_by_id = AsyncMock(
            return_value=Entity(
                id="ent-1",
                name="Paceriz",
                type="product",
                summary="x",
                tags=Tags(what="x", why="x", how="x", who="x"),
            )
        )
        svc = _make_service(repos)

        result = await svc.add_blindspot({
            "description": "  Missing   monitoring  ",
            "severity": "red",
            "related_entity_ids": ["ent-1"],
            "suggested_action": "Add monitoring",
        })

        assert result.id == "bs-1"
        repos["blindspot_repo"].add.assert_not_called()


# ---------------------------------------------------------------------------
# upsert_protocol validation
# ---------------------------------------------------------------------------

class TestUpsertProtocolValidation:

    async def test_nonexistent_entity_id(self):
        svc = _make_service()
        with pytest.raises(ValueError, match="not found"):
            await svc.upsert_protocol({
                "entity_id": "nonexistent",
                "entity_name": "Paceriz",
                "content": {"what": {}, "why": {}, "how": {}, "who": {}},
            })

    async def test_content_missing_dimension(self):
        repos = _mock_repos()
        entity = Entity(
            id="ent-1", name="Paceriz", type="product",
            summary="X", tags=Tags(what="x", why="x", how="x", who="x"),
        )
        repos["entity_repo"].get_by_id = AsyncMock(return_value=entity)
        svc = _make_service(repos)
        with pytest.raises(ValueError, match="Protocol content missing"):
            await svc.upsert_protocol({
                "entity_id": "ent-1",
                "entity_name": "Paceriz",
                "content": {"what": {}, "why": {}},
            })

    async def test_valid_protocol_passes(self):
        repos = _mock_repos()
        entity = Entity(
            id="ent-1", name="Paceriz", type="product",
            summary="X", tags=Tags(what="x", why="x", how="x", who="x"),
        )
        repos["entity_repo"].get_by_id = AsyncMock(return_value=entity)
        svc = _make_service(repos)
        result = await svc.upsert_protocol({
            "entity_id": "ent-1",
            "entity_name": "Paceriz",
            "content": {"what": {}, "why": {}, "how": {}, "who": {}},
        })
        assert result.entity_name == "Paceriz"


# ---------------------------------------------------------------------------
# confirm() protocol id semantics
# ---------------------------------------------------------------------------

class TestConfirmProtocolSemantics:

    async def test_confirm_protocol_by_protocol_id(self):
        repos = _mock_repos()
        protocol = Protocol(
            id="proto-1",
            entity_id="ent-1",
            entity_name="Paceriz",
            content={"what": {}, "why": {}, "how": {}, "who": {}},
            confirmed_by_user=False,
        )
        repos["protocol_repo"].get_by_id = AsyncMock(return_value=protocol)
        repos["protocol_repo"].get_by_entity = AsyncMock(return_value=None)
        repos["protocol_repo"].upsert = AsyncMock(side_effect=lambda p: p)
        svc = _make_service(repos)

        result = await svc.confirm("protocols", "proto-1")

        assert result["confirmed_by_user"] is True
        repos["protocol_repo"].get_by_id.assert_called_once_with("proto-1")
        repos["protocol_repo"].upsert.assert_called_once()

    async def test_confirm_protocol_by_entity_id_fallback(self):
        repos = _mock_repos()
        protocol = Protocol(
            id="proto-2",
            entity_id="ent-2",
            entity_name="ZenOS",
            content={"what": {}, "why": {}, "how": {}, "who": {}},
            confirmed_by_user=False,
        )
        repos["protocol_repo"].get_by_id = AsyncMock(return_value=None)
        repos["protocol_repo"].get_by_entity = AsyncMock(return_value=protocol)
        repos["protocol_repo"].upsert = AsyncMock(side_effect=lambda p: p)
        svc = _make_service(repos)

        result = await svc.confirm("protocols", "ent-2")

        assert result["confirmed_by_user"] is True
        repos["protocol_repo"].get_by_id.assert_called_once_with("ent-2")
        repos["protocol_repo"].get_by_entity.assert_called_once_with("ent-2")


# ---------------------------------------------------------------------------
# New relationship types: impacts / enables
# ---------------------------------------------------------------------------

class TestNewRelationshipTypes:

    def _make_service_with_entities(self) -> OntologyService:
        repos = _mock_repos()
        entity = Entity(
            id="ent-1", name="A", type="product",
            summary="X", tags=Tags(what="x", why="x", how="x", who="x"),
        )
        repos["entity_repo"].get_by_id = AsyncMock(return_value=entity)
        return _make_service(repos)

    async def test_impacts_relationship_is_accepted(self):
        svc = self._make_service_with_entities()
        result = await svc.add_relationship("ent-1", "ent-2", "impacts", "A changed → B must check")
        assert result.type == "impacts"

    async def test_enables_relationship_is_accepted(self):
        svc = self._make_service_with_entities()
        result = await svc.add_relationship("ent-1", "ent-2", "enables", "A makes B possible")
        assert result.type == "enables"

    async def test_unknown_rel_type_still_rejected(self):
        svc = self._make_service_with_entities()
        with pytest.raises(ValueError, match="Invalid relationship type"):
            await svc.add_relationship("ent-1", "ent-2", "likes", "test")


# ---------------------------------------------------------------------------
# Auto-level logic in upsert_entity
# ---------------------------------------------------------------------------

class TestAutoLevel:

    async def test_product_gets_level_1(self):
        repos = _mock_repos()
        svc = _make_service(repos)
        result = await svc.upsert_entity(_valid_entity_data(type="product"))
        assert result.entity.level == 1

    async def test_module_gets_level_2(self):
        repos = _mock_repos()
        parent = Entity(
            id="parent-1", name="Product", type="product",
            summary="P", tags=Tags(what="x", why="x", how="x", who="x"),
        )
        repos["entity_repo"].get_by_id = AsyncMock(return_value=parent)
        repos["entity_repo"].get_by_name = AsyncMock(return_value=None)
        svc = _make_service(repos)
        result = await svc.upsert_entity(
            _valid_entity_data(type="module", parent_id="parent-1")
        )
        assert result.entity.level == 2

    async def test_document_gets_level_3(self):
        repos = _mock_repos()
        svc = _make_service(repos)
        result = await svc.upsert_entity(
            _valid_entity_data(type="document", status="current")
        )
        assert result.entity.level == 3

    async def test_goal_gets_level_3(self):
        repos = _mock_repos()
        svc = _make_service(repos)
        result = await svc.upsert_entity(_valid_entity_data(type="goal"))
        assert result.entity.level == 3

    async def test_role_gets_level_3(self):
        repos = _mock_repos()
        svc = _make_service(repos)
        result = await svc.upsert_entity(_valid_entity_data(type="role"))
        assert result.entity.level == 3

    async def test_project_gets_level_3(self):
        repos = _mock_repos()
        svc = _make_service(repos)
        result = await svc.upsert_entity(_valid_entity_data(type="project"))
        assert result.entity.level == 3

    async def test_caller_provided_level_is_respected(self):
        """If caller explicitly passes level, it overrides the auto-computed value."""
        repos = _mock_repos()
        svc = _make_service(repos)
        result = await svc.upsert_entity(_valid_entity_data(type="product", level=99))
        assert result.entity.level == 99


# ---------------------------------------------------------------------------
# upsert_document validation
# ---------------------------------------------------------------------------

class TestUpsertDocumentValidation:

    async def test_invalid_source_type(self):
        svc = _make_service()
        with pytest.raises(ValueError, match="Invalid source type"):
            await svc.upsert_document({
                "title": "Doc",
                "source": {"type": "ftp", "uri": "/x", "adapter": "ftp"},
                "tags": {"what": ["x"], "why": "y", "how": "z", "who": ["a"]},
                "summary": "test",
            })

    async def test_nonexistent_linked_entity(self):
        svc = _make_service()
        with pytest.raises(ValueError, match="not found"):
            await svc.upsert_document({
                "title": "Doc",
                "source": {"type": "github", "uri": "/x", "adapter": "git"},
                "tags": {"what": ["x"], "why": "y", "how": "z", "who": ["a"]},
                "summary": "test",
                "linked_entity_ids": ["nonexistent"],
            })

    async def test_valid_document_passes(self):
        svc = _make_service()
        result = await svc.upsert_document({
            "title": "API Spec",
            "source": {"type": "github", "uri": "/x", "adapter": "git"},
            "tags": {"what": ["api"], "why": "ref", "how": "REST", "who": ["dev"]},
            "summary": "API spec doc",
        })
        # upsert_document now returns Entity(type="document")
        assert result.name == "API Spec"
        assert result.type == "document"

    async def test_source_uri_is_idempotent_and_reuses_existing_document_entity(self):
        repos = _mock_repos()
        existing_doc = Entity(
            id="doc-existing",
            name="Old Title",
            type="document",
            summary="old",
            tags=Tags(what=["x"], why="y", how="z", who=["a"]),
            sources=[{"uri": "https://github.com/acme/repo/blob/main/docs/spec.md", "label": "spec.md", "type": "github"}],
        )
        repos["entity_repo"].list_all = AsyncMock(return_value=[existing_doc])
        repos["entity_repo"].get_by_id = AsyncMock(return_value=existing_doc)
        svc = _make_service(repos)

        result = await svc.upsert_document({
            "title": "API Spec Updated",
            "source": {
                "type": "github",
                "uri": "https://github.com/acme/repo/blob/main/docs/spec.md",
                "adapter": "github",
            },
            "tags": {"what": ["api"], "why": "ref", "how": "REST", "who": ["dev"]},
            "summary": "updated summary",
        })

        assert result.id == "doc-existing"

    async def test_sparse_update_preserves_existing_fields(self):
        repos = _mock_repos()
        existing = Entity(
            id="doc-1",
            name="Spec v1",
            type="document",
            summary="old summary",
            tags=Tags(what=["api"], why="ref", how="rest", who=["dev"]),
            status="current",
            parent_id="mod-1",
            confirmed_by_user=True,
            owner="Barry",
            visibility="restricted",
            details={"k": "v"},
            sources=[{"uri": "/old.md", "label": "old", "type": "github"}],
        )
        module = Entity(
            id="mod-1",
            name="Module",
            type="module",
            summary="m",
            tags=Tags(what=["api"], why="y", how="h", who=["w"]),
            parent_id="prod-1",
        )
        repos["entity_repo"].get_by_id = AsyncMock(
            side_effect=lambda eid: {"doc-1": existing, "mod-1": module}.get(eid)
        )
        svc = _make_service(repos)

        result = await svc.upsert_document({
            "id": "doc-1",
            "summary": "new summary only",
        })

        assert result.parent_id == "mod-1"
        assert result.confirmed_by_user is True
        assert result.owner == "Barry"
        assert result.visibility == "restricted"
        assert result.details == {"k": "v"}
        assert result.summary == "new summary only"

    async def test_source_uri_only_update_keeps_parent_and_metadata(self):
        repos = _mock_repos()
        existing = Entity(
            id="doc-1",
            name="Spec v1",
            type="document",
            summary="old summary",
            tags=Tags(what=["api"], why="ref", how="rest", who=["dev"]),
            status="current",
            parent_id="mod-1",
            confirmed_by_user=True,
            owner="Barry",
            visibility="restricted",
            details={"k": "v"},
            sources=[{"uri": "/old.md", "label": "old", "type": "github"}],
        )
        module = Entity(
            id="mod-1",
            name="Module",
            type="module",
            summary="m",
            tags=Tags(what=["api"], why="y", how="h", who=["w"]),
            parent_id="prod-1",
        )
        repos["entity_repo"].get_by_id = AsyncMock(
            side_effect=lambda eid: {"doc-1": existing, "mod-1": module}.get(eid)
        )
        svc = _make_service(repos)

        result = await svc.upsert_document({
            "id": "doc-1",
            "source": {"uri": "/new.md"},
        })

        assert result.parent_id == "mod-1"
        assert result.confirmed_by_user is True
        assert result.owner == "Barry"
        assert result.visibility == "restricted"
        assert result.details == {"k": "v"}
        assert result.sources[0]["uri"] == "/new.md"

    async def test_linked_entity_ids_accepts_single_string(self):
        repos = _mock_repos()
        existing = Entity(
            id="doc-1",
            name="Spec v1",
            type="document",
            summary="old summary",
            tags=Tags(what=["api"], why="ref", how="rest", who=["dev"]),
            status="current",
            parent_id="mod-old",
        )
        module = Entity(
            id="mod-1",
            name="Module",
            type="module",
            summary="m",
            tags=Tags(what=["api"], why="y", how="h", who=["w"]),
            parent_id="prod-1",
        )
        repos["entity_repo"].get_by_id = AsyncMock(
            side_effect=lambda eid: {"doc-1": existing, "mod-1": module}.get(eid)
        )
        svc = _make_service(repos)

        result = await svc.upsert_document({
            "id": "doc-1",
            "linked_entity_ids": "mod-1",
        })
        assert result.parent_id == "mod-1"

    async def test_linked_entity_ids_accepts_json_array_string(self):
        repos = _mock_repos()
        existing = Entity(
            id="doc-1",
            name="Spec v1",
            type="document",
            summary="old summary",
            tags=Tags(what=["api"], why="ref", how="rest", who=["dev"]),
            status="current",
            parent_id="mod-old",
        )
        module = Entity(
            id="mod-1",
            name="Module",
            type="module",
            summary="m",
            tags=Tags(what=["api"], why="y", how="h", who=["w"]),
            parent_id="prod-1",
        )
        related = Entity(
            id="goal-1",
            name="Goal",
            type="goal",
            summary="g",
            tags=Tags(what=["api"], why="y", how="h", who=["w"]),
            parent_id="mod-1",
        )
        repos["entity_repo"].get_by_id = AsyncMock(
            side_effect=lambda eid: {
                "doc-1": existing,
                "mod-1": module,
                "goal-1": related,
            }.get(eid)
        )
        svc = _make_service(repos)

        result = await svc.upsert_document({
            "id": "doc-1",
            "linked_entity_ids": "[\"mod-1\", \"goal-1\"]",
        })
        assert result.parent_id == "mod-1"

    async def test_linked_entity_ids_invalid_json_string_rejected(self):
        repos = _mock_repos()
        existing = Entity(
            id="doc-1",
            name="Spec v1",
            type="document",
            summary="old summary",
            tags=Tags(what=["api"], why="ref", how="rest", who=["dev"]),
            status="current",
            parent_id="mod-old",
        )
        repos["entity_repo"].get_by_id = AsyncMock(
            side_effect=lambda eid: {"doc-1": existing}.get(eid)
        )
        svc = _make_service(repos)

        with pytest.raises(ValueError, match="linked_entity_ids JSON string is invalid"):
            await svc.upsert_document({
                "id": "doc-1",
                "linked_entity_ids": "[bad json",
            })

    async def test_linked_entity_ids_list_updates_primary_parent(self):
        repos = _mock_repos()
        existing = Entity(
            id="doc-1",
            name="Spec v1",
            type="document",
            summary="old summary",
            tags=Tags(what=["api"], why="ref", how="rest", who=["dev"]),
            status="current",
            parent_id="mod-old",
        )
        module = Entity(
            id="mod-1",
            name="Module",
            type="module",
            summary="m",
            tags=Tags(what=["api"], why="y", how="h", who=["w"]),
            parent_id="prod-1",
        )
        related = Entity(
            id="goal-1",
            name="Goal",
            type="goal",
            summary="g",
            tags=Tags(what=["api"], why="y", how="h", who=["w"]),
            parent_id="mod-1",
        )
        repos["entity_repo"].get_by_id = AsyncMock(
            side_effect=lambda eid: {
                "doc-1": existing,
                "mod-1": module,
                "goal-1": related,
            }.get(eid)
        )
        svc = _make_service(repos)

        result = await svc.upsert_document({
            "id": "doc-1",
            "linked_entity_ids": ["mod-1", "goal-1"],
        })
        assert result.parent_id == "mod-1"


class TestDocumentSyncGovernance:

    async def test_sync_dry_run_preview(self):
        repos = _mock_repos()
        existing = Entity(
            id="doc-1",
            name="Spec v1",
            type="document",
            summary="old summary",
            tags=Tags(what=["api"], why="ref", how="rest", who=["dev"]),
            status="current",
            parent_id="mod-1",
            sources=[{"uri": "/old.md", "label": "old", "type": "github"}],
        )
        module1 = Entity(
            id="mod-1",
            name="Module 1",
            type="module",
            summary="m1",
            tags=Tags(what=["api"], why="y", how="h", who=["w"]),
            parent_id="prod-1",
        )
        module2 = Entity(
            id="mod-2",
            name="Module 2",
            type="module",
            summary="m2",
            tags=Tags(what=["api"], why="y", how="h", who=["w"]),
            parent_id="prod-1",
        )
        repos["entity_repo"].get_by_id = AsyncMock(
            side_effect=lambda eid: {
                "doc-1": existing,
                "mod-1": module1,
                "mod-2": module2,
            }.get(eid)
        )
        repos["relationship_repo"].list_by_entity = AsyncMock(
            return_value=[Relationship(
                source_entity_id="doc-1",
                target_id="mod-1",
                type="part_of",
                description="document primary linkage",
            )]
        )
        svc = _make_service(repos)

        preview = await svc.sync_document_governance({
            "sync_mode": "reclassify",
            "id": "doc-1",
            "linked_entity_ids": ["mod-2"],
            "dry_run": True,
        })
        assert preview.dry_run is True
        assert preview.before["parent_id"] == "mod-1"
        assert preview.after["parent_id"] == "mod-2"

    async def test_sync_repair_executes_relationship_cleanup(self):
        repos = _mock_repos()
        existing = Entity(
            id="doc-1",
            name="Spec v1",
            type="document",
            summary="old summary",
            tags=Tags(what=["api"], why="ref", how="rest", who=["dev"]),
            status="current",
            parent_id="mod-2",
            sources=[{"uri": "/old.md", "label": "old", "type": "github"}],
        )
        module2 = Entity(
            id="mod-2",
            name="Module 2",
            type="module",
            summary="m2",
            tags=Tags(what=["api"], why="y", how="h", who=["w"]),
            parent_id="prod-1",
        )
        repos["entity_repo"].get_by_id = AsyncMock(
            side_effect=lambda eid: {
                "doc-1": existing,
                "mod-2": module2,
            }.get(eid)
        )
        repos["relationship_repo"].list_by_entity = AsyncMock(
            return_value=[Relationship(
                source_entity_id="doc-1",
                target_id="mod-1",
                type="part_of",
                description="document primary linkage",
            )]
        )
        repos["relationship_repo"].remove = AsyncMock(return_value=1)
        svc = _make_service(repos)

        result = await svc.sync_document_governance({
            "sync_mode": "sync_repair",
            "id": "doc-1",
            "dry_run": False,
        })
        assert result.dry_run is False
        assert any(c["type"] == "part_of" for c in result.relationship_changes["removed"])

    async def test_archive_sync_sets_archived_status_in_preview(self):
        repos = _mock_repos()
        existing = Entity(
            id="doc-1",
            name="Spec v1",
            type="document",
            summary="old summary",
            tags=Tags(what=["api"], why="ref", how="rest", who=["dev"]),
            status="current",
            parent_id="mod-1",
            sources=[{"uri": "/old.md", "label": "old", "type": "github"}],
        )
        module = Entity(
            id="mod-1",
            name="Module",
            type="module",
            summary="m",
            tags=Tags(what=["api"], why="y", how="h", who=["w"]),
            parent_id="prod-1",
        )
        repos["entity_repo"].get_by_id = AsyncMock(
            side_effect=lambda eid: {"doc-1": existing, "mod-1": module}.get(eid)
        )
        repos["relationship_repo"].list_by_entity = AsyncMock(return_value=[])
        svc = _make_service(repos)

        preview = await svc.sync_document_governance({
            "sync_mode": "archive",
            "id": "doc-1",
            "dry_run": True,
        })
        assert preview.after["status"] == "archived"


# ---------------------------------------------------------------------------
# TaskService priority validation
# ---------------------------------------------------------------------------

class TestTaskPriorityValidation:

    async def test_invalid_priority(self):
        repos = _mock_repos()
        task_repo = AsyncMock()
        task_repo.upsert = AsyncMock(side_effect=lambda t: t)
        svc = TaskService(
            task_repo=task_repo,
            entity_repo=repos["entity_repo"],
            blindspot_repo=repos["blindspot_repo"],
        )
        with pytest.raises(ValueError, match="Invalid priority"):
            await svc.create_task({
                "title": "Fix bug",
                "created_by": "architect",
                "priority": "ultra",
            })

    async def test_valid_priority_passes(self):
        repos = _mock_repos()
        task_repo = AsyncMock()
        task_repo.upsert = AsyncMock(side_effect=lambda t: t)
        svc = TaskService(
            task_repo=task_repo,
            entity_repo=repos["entity_repo"],
            blindspot_repo=repos["blindspot_repo"],
        )
        result = await svc.create_task({
            "title": "Fix bug",
            "created_by": "architect",
            "priority": "high",
        })
        assert result.task.priority == "high"

    async def test_none_priority_uses_recommendation(self):
        """When priority is None, AI recommendation is used (no error)."""
        repos = _mock_repos()
        task_repo = AsyncMock()
        task_repo.upsert = AsyncMock(side_effect=lambda t: t)
        svc = TaskService(
            task_repo=task_repo,
            entity_repo=repos["entity_repo"],
            blindspot_repo=repos["blindspot_repo"],
        )
        result = await svc.create_task({
            "title": "Fix bug",
            "created_by": "architect",
        })
        # Should not raise, priority comes from recommend_priority
        assert result.task.priority is not None


class TestTaskSchemaAlignedValidation:

    async def test_create_with_blocked_by_and_todo_requires_blocked_reason(self):
        repos = _mock_repos()
        task_repo = AsyncMock()
        task_repo.upsert = AsyncMock(side_effect=lambda t: t)
        svc = TaskService(
            task_repo=task_repo,
            entity_repo=repos["entity_repo"],
            blindspot_repo=repos["blindspot_repo"],
        )
        with pytest.raises(ValueError, match="blocked_reason is required"):
            await svc.create_task({
                "title": "Wait on API contract",
                "created_by": "architect",
                "status": "todo",
                "blocked_by": ["task-123"],
            })

    async def test_create_with_blocked_by_and_reason_persists_blocked_reason(self):
        repos = _mock_repos()
        task_repo = AsyncMock()
        task_repo.upsert = AsyncMock(side_effect=lambda t: t)
        svc = TaskService(
            task_repo=task_repo,
            entity_repo=repos["entity_repo"],
            blindspot_repo=repos["blindspot_repo"],
        )
        result = await svc.create_task({
            "title": "Wait on API contract",
            "created_by": "architect",
            "status": "todo",
            "blocked_by": ["task-123"],
            "blocked_reason": "Waiting for upstream API decision",
        })
        assert result.task.status == "blocked"
        assert result.task.blocked_reason == "Waiting for upstream API decision"

    async def test_update_to_review_requires_result(self):
        repos = _mock_repos()
        task_repo = AsyncMock()
        task_repo.get_by_id = AsyncMock(return_value=Task(
            id="task-1",
            title="Ship docs",
            status="in_progress",
            priority="high",
            created_by="architect",
        ))
        task_repo.upsert = AsyncMock(side_effect=lambda t: t)
        task_repo.list_blocked_by = AsyncMock(return_value=[])
        svc = TaskService(
            task_repo=task_repo,
            entity_repo=repos["entity_repo"],
            blindspot_repo=repos["blindspot_repo"],
        )
        with pytest.raises(ValueError, match="result is required when status is 'review'"):
            await svc.update_task("task-1", {"status": "review"})


# ===========================================================================
# Fuzzy similarity check — prevent semantically duplicate entities
# ===========================================================================


class TestFuzzySimilarityCheck:
    """Verify that creating an entity with a name similar to an existing one
    raises ValueError with context about the similar entities."""

    @pytest.mark.asyncio
    async def test_substring_match_blocks(self):
        """'Paceriz' should be blocked if 'Paceriz API Service' already exists."""
        repos = _mock_repos()
        existing = Entity(
            name="Paceriz API Service", type="product", summary="Backend API",
            tags=Tags(what="API", why="serve", how="Flask", who="devs"),
            id="existing-1", confirmed_by_user=True,
        )
        repos["entity_repo"].get_by_name = AsyncMock(return_value=None)
        repos["entity_repo"].list_all = AsyncMock(return_value=[existing])
        svc = _make_service(repos)

        with pytest.raises(ValueError, match="similar"):
            await svc.upsert_entity(_valid_entity_data(name="Paceriz"))

    @pytest.mark.asyncio
    async def test_reverse_substring_match_blocks(self):
        """'Paceriz API Service' should be blocked if 'Paceriz' already exists."""
        repos = _mock_repos()
        existing = Entity(
            name="Paceriz", type="product", summary="Running app",
            tags=Tags(what="app", why="coach", how="AI", who="runners"),
            id="existing-1", confirmed_by_user=True,
        )
        repos["entity_repo"].get_by_name = AsyncMock(return_value=None)
        repos["entity_repo"].list_all = AsyncMock(return_value=[existing])
        svc = _make_service(repos)

        with pytest.raises(ValueError, match="similar"):
            await svc.upsert_entity(_valid_entity_data(name="Paceriz API Service"))

    @pytest.mark.asyncio
    async def test_token_overlap_blocks(self):
        """'Paceriz iOS App' should be blocked if 'Paceriz API Service' exists
        because they share the token 'paceriz'."""
        repos = _mock_repos()
        existing = Entity(
            name="Paceriz API Service", type="product", summary="Backend",
            tags=Tags(what="API", why="serve", how="Flask", who="devs"),
            id="existing-1", confirmed_by_user=True,
        )
        repos["entity_repo"].get_by_name = AsyncMock(return_value=None)
        repos["entity_repo"].list_all = AsyncMock(return_value=[existing])
        svc = _make_service(repos)

        with pytest.raises(ValueError, match="similar"):
            await svc.upsert_entity(_valid_entity_data(name="Paceriz iOS App"))

    @pytest.mark.asyncio
    async def test_error_includes_context(self):
        """Error message should include existing entity's summary, tags, modules."""
        repos = _mock_repos()
        existing = Entity(
            name="Paceriz API Service", type="product",
            summary="Flask backend for running coach",
            tags=Tags(what="REST API", why="serve data", how="Flask+Firestore", who="iOS app"),
            id="existing-1", confirmed_by_user=True,
        )
        repos["entity_repo"].get_by_name = AsyncMock(return_value=None)
        repos["entity_repo"].list_all = AsyncMock(return_value=[existing])
        svc = _make_service(repos)

        with pytest.raises(ValueError) as exc_info:
            await svc.upsert_entity(_valid_entity_data(name="Paceriz"))

        msg = str(exc_info.value)
        assert "Paceriz API Service" in msg
        assert "existing-1" in msg
        assert "Flask backend" in msg
        assert "REST API" in msg

    @pytest.mark.asyncio
    async def test_force_bypasses_fuzzy_check(self):
        """force=true in data should skip the fuzzy similarity check."""
        repos = _mock_repos()
        existing = Entity(
            name="Paceriz API Service", type="product", summary="Backend",
            tags=Tags(what="API", why="serve", how="Flask", who="devs"),
            id="existing-1", confirmed_by_user=True,
        )
        repos["entity_repo"].get_by_name = AsyncMock(return_value=None)
        repos["entity_repo"].list_all = AsyncMock(return_value=[existing])
        svc = _make_service(repos)

        result = await svc.upsert_entity(
            _valid_entity_data(name="Paceriz", force=True)
        )
        assert result.entity.name == "Paceriz"

    @pytest.mark.asyncio
    async def test_completely_different_name_passes(self):
        """'ZenOS' should not be flagged when 'Paceriz' exists."""
        repos = _mock_repos()
        existing = Entity(
            name="Paceriz", type="product", summary="Running app",
            tags=Tags(what="app", why="coach", how="AI", who="runners"),
            id="existing-1", confirmed_by_user=True,
        )
        repos["entity_repo"].get_by_name = AsyncMock(return_value=None)
        repos["entity_repo"].list_all = AsyncMock(return_value=[existing])
        svc = _make_service(repos)

        result = await svc.upsert_entity(
            _valid_entity_data(name="ZenOS", summary="Knowledge ontology")
        )
        assert result.entity.name == "ZenOS"


# ===========================================================================
# Relationship dedup — prevent duplicate relationships
# ===========================================================================


class TestRelationshipDedup:
    """Verify that add_relationship returns existing relationship instead of
    creating a duplicate when source+target+type match."""

    @pytest.mark.asyncio
    async def test_duplicate_relationship_returns_existing(self):
        """If a relationship with same source+target+type exists, return it."""
        repos = _mock_repos()
        entity = Entity(
            id="ent-1", name="A", type="product",
            summary="X", tags=Tags(what="x", why="x", how="x", who="x"),
        )
        existing_rel = Relationship(
            id="rel-existing",
            source_entity_id="ent-1",
            target_id="ent-2",
            type="depends_on",
            description="original",
        )
        repos["entity_repo"].get_by_id = AsyncMock(return_value=entity)
        repos["relationship_repo"].find_duplicate = AsyncMock(return_value=existing_rel)
        svc = _make_service(repos)

        result = await svc.add_relationship("ent-1", "ent-2", "depends_on", "duplicate attempt")
        assert result.id == "rel-existing"
        assert result.description == "original"
        # add should NOT have been called
        repos["relationship_repo"].add.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_duplicate_creates_new(self):
        """If no duplicate exists, create normally."""
        repos = _mock_repos()
        entity = Entity(
            id="ent-1", name="A", type="product",
            summary="X", tags=Tags(what="x", why="x", how="x", who="x"),
        )
        repos["entity_repo"].get_by_id = AsyncMock(return_value=entity)
        repos["relationship_repo"].find_duplicate = AsyncMock(return_value=None)
        svc = _make_service(repos)

        result = await svc.add_relationship("ent-1", "ent-2", "depends_on", "new rel")
        assert result.type == "depends_on"
        repos["relationship_repo"].add.assert_called_once()


# ===========================================================================
# Entity sources dedup — prevent duplicate URIs in sources
# ===========================================================================


class TestSourcesDedup:
    """Verify that sources are deduplicated by URI on entity creation."""

    @pytest.mark.asyncio
    async def test_duplicate_uris_removed(self):
        """Duplicate URIs in sources should be collapsed to one."""
        repos = _mock_repos()
        svc = _make_service(repos)

        result = await svc.upsert_entity(_valid_entity_data(
            sources=[
                {"uri": "https://example.com/a.md", "label": "A", "type": "github"},
                {"uri": "https://example.com/a.md", "label": "A copy", "type": "github"},
                {"uri": "https://example.com/b.md", "label": "B", "type": "github"},
            ]
        ))
        assert len(result.entity.sources) == 2
        uris = [s["uri"] for s in result.entity.sources]
        assert uris == ["https://example.com/a.md", "https://example.com/b.md"]

    @pytest.mark.asyncio
    async def test_append_sources_dedup(self):
        """append_sources should not add URIs that already exist on entity."""
        repos = _mock_repos()
        existing = Entity(
            id="ent-1", name="Paceriz", type="product",
            summary="App", tags=Tags(what="x", why="x", how="x", who="x"),
            sources=[{"uri": "https://example.com/a.md", "label": "A", "type": "github"}],
        )
        repos["entity_repo"].get_by_id = AsyncMock(return_value=existing)
        svc = _make_service(repos)

        result = await svc.upsert_entity({
            "id": "ent-1",
            "append_sources": [
                {"uri": "https://example.com/a.md", "label": "A dup", "type": "github"},
                {"uri": "https://example.com/new.md", "label": "New", "type": "github"},
            ],
        })
        assert len(result.entity.sources) == 2
        uris = [s.get("uri") for s in result.entity.sources]
        assert "https://example.com/a.md" in uris
        assert "https://example.com/new.md" in uris


class TestEntityUpdateSemantics:
    """Update path should preserve omitted fields unless explicitly changed."""

    @pytest.mark.asyncio
    async def test_force_update_preserves_sources_when_omitted(self):
        repos = _mock_repos()
        existing = Entity(
            id="ent-1",
            name="Paceriz",
            type="product",
            summary="Old summary",
            tags=Tags(what="app", why="coach", how="AI", who="runners"),
            confirmed_by_user=True,
            sources=[{"uri": "https://example.com/spec.md", "label": "Spec", "type": "github"}],
        )
        repos["entity_repo"].get_by_id = AsyncMock(return_value=existing)
        repos["entity_repo"].list_by_parent = AsyncMock(return_value=[])
        svc = _make_service(repos)

        result = await svc.upsert_entity({
            "id": "ent-1",
            "summary": "New summary",
            "force": True,
        })

        assert result.entity.summary == "New summary"
        assert result.entity.sources == existing.sources
        repos["entity_repo"].upsert.assert_called_once()

    @pytest.mark.asyncio
    async def test_force_update_preserves_confirmed_flag_by_default(self):
        repos = _mock_repos()
        existing = Entity(
            id="ent-1",
            name="Paceriz",
            type="product",
            summary="Old summary",
            tags=Tags(what="app", why="coach", how="AI", who="runners"),
            confirmed_by_user=True,
        )
        repos["entity_repo"].get_by_id = AsyncMock(return_value=existing)
        repos["entity_repo"].list_by_parent = AsyncMock(return_value=[])
        svc = _make_service(repos)

        result = await svc.upsert_entity({
            "id": "ent-1",
            "name": "ZenOS",
            "force": True,
        })

        assert result.entity.name == "ZenOS"
        assert result.entity.confirmed_by_user is True

    @pytest.mark.asyncio
    async def test_partial_update_uses_existing_required_fields(self):
        repos = _mock_repos()
        existing = Entity(
            id="ent-1",
            name="Paceriz",
            type="product",
            summary="Old summary",
            tags=Tags(what="app", why="coach", how="AI", who="runners"),
            visibility="restricted",
        )
        repos["entity_repo"].get_by_id = AsyncMock(return_value=existing)
        repos["entity_repo"].list_by_parent = AsyncMock(return_value=[])
        svc = _make_service(repos)

        result = await svc.upsert_entity({
            "id": "ent-1",
            "summary": "Patched summary",
        })

        assert result.entity.name == "Paceriz"
        assert result.entity.type == "product"
        assert result.entity.tags.why == "coach"
        assert result.entity.visibility == "restricted"
        assert result.entity.summary == "Patched summary"


# ===========================================================================
# Auto-infer module parent for L3 entities
# ===========================================================================


class TestAutoInferModuleParent:
    """Verify that L3 entities (document/goal/role/project) with parent_id
    pointing to a Product or null get auto-inferred to the best matching Module."""

    @pytest.mark.asyncio
    async def test_document_with_product_parent_auto_inferred_to_module(self):
        """parent_id pointing to a product should be auto-corrected to the
        best matching module under that product."""
        repos = _mock_repos()

        product = Entity(
            id="prod-1", name="Paceriz", type="product",
            summary="Running coach app",
            tags=Tags(what=["running", "coaching"], why="fitness", how="AI", who=["athletes"]),
        )
        module_training = Entity(
            id="mod-training", name="Training Plan", type="module",
            parent_id="prod-1",
            summary="AI training plan generation",
            tags=Tags(what=["training", "plan", "schedule"], why="periodization", how="AI", who=["coach"]),
        )
        module_data = Entity(
            id="mod-data", name="Data Integration", type="module",
            parent_id="prod-1",
            summary="Sport data ingestion",
            tags=Tags(what=["data", "integration", "sync"], why="tracking", how="API", who=["dev"]),
        )

        def mock_get_by_id(eid):
            lookup = {"prod-1": product, "mod-training": module_training, "mod-data": module_data}
            return lookup.get(eid)

        def mock_list_all(type_filter=None):
            if type_filter == "module":
                return [module_training, module_data]
            if type_filter == "document":
                return []  # no existing documents
            return [product, module_training, module_data]

        repos["entity_repo"].get_by_id = AsyncMock(side_effect=mock_get_by_id)
        repos["entity_repo"].get_by_name = AsyncMock(return_value=None)
        repos["entity_repo"].list_all = AsyncMock(side_effect=mock_list_all)
        repos["entity_repo"].list_by_parent = AsyncMock(return_value=[])

        svc = _make_service(repos)

        result = await svc.upsert_entity({
            "name": "Weekly Training Template",
            "type": "document",
            "summary": "Default weekly training schedule template",
            "tags": {"what": ["training", "template", "schedule"], "why": "reference", "how": "markdown", "who": ["coach"]},
            "parent_id": "prod-1",  # Points to product, should be corrected
        })

        # Should be re-parented to mod-training (best tags.what overlap)
        assert result.entity.parent_id == "mod-training"
        # Should have a warning about the auto-inference
        assert result.warnings is not None
        assert any("自動推斷" in w for w in result.warnings)

    @pytest.mark.asyncio
    async def test_document_with_null_parent_auto_inferred_to_module(self):
        """parent_id=null should be auto-inferred to the best matching module."""
        repos = _mock_repos()

        module_api = Entity(
            id="mod-api", name="API Service", type="module",
            parent_id="prod-1",
            summary="REST API endpoints",
            tags=Tags(what=["api", "rest", "endpoints"], why="integration", how="Flask", who=["dev"]),
        )
        module_ui = Entity(
            id="mod-ui", name="Dashboard UI", type="module",
            parent_id="prod-1",
            summary="Frontend dashboard",
            tags=Tags(what=["dashboard", "ui", "frontend"], why="visualization", how="React", who=["dev"]),
        )

        def mock_list_all(type_filter=None):
            if type_filter == "module":
                return [module_api, module_ui]
            if type_filter == "document":
                return []  # no existing documents
            return [module_api, module_ui]

        repos["entity_repo"].get_by_id = AsyncMock(return_value=None)
        repos["entity_repo"].get_by_name = AsyncMock(return_value=None)
        repos["entity_repo"].list_all = AsyncMock(side_effect=mock_list_all)
        repos["entity_repo"].list_by_parent = AsyncMock(return_value=[])

        svc = _make_service(repos)

        result = await svc.upsert_entity({
            "name": "API Authentication Guide",
            "type": "document",
            "summary": "How to authenticate with the REST API",
            "tags": {"what": ["api", "authentication", "rest"], "why": "reference", "how": "OAuth", "who": ["dev"]},
            # No parent_id — should be inferred
        })

        # Should be parented to mod-api (best tags.what overlap: "api", "rest")
        assert result.entity.parent_id == "mod-api"
        assert result.warnings is not None
        assert any("自動推斷" in w for w in result.warnings)

    @pytest.mark.asyncio
    async def test_document_with_module_parent_unchanged(self):
        """If parent_id already points to a module, no change should occur."""
        repos = _mock_repos()

        module = Entity(
            id="mod-1", name="Training Plan", type="module",
            parent_id="prod-1",
            summary="Training",
            tags=Tags(what=["training"], why="fitness", how="AI", who=["coach"]),
        )

        repos["entity_repo"].get_by_id = AsyncMock(return_value=module)
        repos["entity_repo"].get_by_name = AsyncMock(return_value=None)
        repos["entity_repo"].list_all = AsyncMock(return_value=[])
        repos["entity_repo"].list_by_parent = AsyncMock(return_value=[])

        svc = _make_service(repos)

        result = await svc.upsert_entity({
            "name": "Training Doc",
            "type": "document",
            "summary": "A doc about training",
            "tags": {"what": ["training"], "why": "ref", "how": "md", "who": ["coach"]},
            "parent_id": "mod-1",  # Already a module
        })

        assert result.entity.parent_id == "mod-1"
        # No auto-inference warning expected
        if result.warnings:
            assert not any("自動推斷" in w for w in result.warnings)

    @pytest.mark.asyncio
    async def test_product_entity_not_affected(self):
        """Product entities should not trigger module parent inference."""
        repos = _mock_repos()
        repos["entity_repo"].get_by_name = AsyncMock(return_value=None)
        repos["entity_repo"].list_all = AsyncMock(return_value=[])
        repos["entity_repo"].list_by_parent = AsyncMock(return_value=[])

        svc = _make_service(repos)

        result = await svc.upsert_entity({
            "name": "New Product",
            "type": "product",
            "summary": "A new product",
            "tags": {"what": ["product"], "why": "business", "how": "SaaS", "who": ["team"]},
        })

        assert result.entity.parent_id is None

    @pytest.mark.asyncio
    async def test_fallback_to_first_module_when_no_tag_overlap(self):
        """When no tags overlap but product_id is known, fall back to first module."""
        repos = _mock_repos()

        product = Entity(
            id="prod-1", name="Paceriz", type="product",
            summary="Running app",
            tags=Tags(what=["running"], why="fitness", how="AI", who=["athletes"]),
        )
        module = Entity(
            id="mod-1", name="Core Module", type="module",
            parent_id="prod-1",
            summary="Core",
            tags=Tags(what=["core", "engine"], why="foundation", how="Python", who=["dev"]),
        )

        def mock_get_by_id(eid):
            return {"prod-1": product, "mod-1": module}.get(eid)

        repos["entity_repo"].get_by_id = AsyncMock(side_effect=mock_get_by_id)
        repos["entity_repo"].get_by_name = AsyncMock(return_value=None)
        repos["entity_repo"].list_all = AsyncMock(return_value=[module])
        repos["entity_repo"].list_by_parent = AsyncMock(return_value=[])

        svc = _make_service(repos)

        result = await svc.upsert_entity({
            "name": "Completely Unrelated Doc",
            "type": "document",
            "summary": "Something with no tag overlap",
            "tags": {"what": ["zebra", "unicorn"], "why": "mystery", "how": "magic", "who": ["wizard"]},
            "parent_id": "prod-1",
        })

        # Should fall back to first module under the product
        assert result.entity.parent_id == "mod-1"


# ---------------------------------------------------------------------------
# Cross-product auto-inferred related_to guard
# ---------------------------------------------------------------------------

class TestCrossProductRelatedToGuard:
    """Verify that auto-inferred related_to across different products is silently skipped."""

    def _make_entity(self, id: str, name: str, type: str, parent_id: str | None = None) -> Entity:
        return Entity(
            id=id,
            name=name,
            type=type,
            summary=f"Test {name}",
            tags=Tags(what=["test"], why="test", how="test", who=["test"]),
            parent_id=parent_id,
        )

    async def test_cross_product_auto_inferred_skipped(self):
        """Auto-inferred related_to across products should NOT be persisted."""
        repos = _mock_repos()
        # Product A, Module A under it
        prod_a = self._make_entity("prod-a", "Product A", "product")
        mod_a = self._make_entity("mod-a", "Module A", "module", parent_id="prod-a")
        # Product B, Module B under it
        prod_b = self._make_entity("prod-b", "Product B", "product")
        mod_b = self._make_entity("mod-b", "Module B", "module", parent_id="prod-b")

        entity_lookup = {
            "mod-a": mod_a,
            "mod-b": mod_b,
            "prod-a": prod_a,
            "prod-b": prod_b,
        }
        repos["entity_repo"].get_by_id = AsyncMock(side_effect=lambda eid: entity_lookup.get(eid))

        svc = _make_service(repos)
        result = await svc.add_relationship(
            source_id="mod-a",
            target_id="mod-b",
            rel_type="related_to",
            description="auto-inferred",
        )

        # Should return a relationship object but NOT persist it
        assert result.source_entity_id == "mod-a"
        assert result.target_id == "mod-b"
        repos["relationship_repo"].add.assert_not_called()
        repos["relationship_repo"].find_duplicate.assert_not_called()

    async def test_same_product_auto_inferred_allowed(self):
        """Auto-inferred related_to within the same product SHOULD be persisted."""
        repos = _mock_repos()
        prod_a = self._make_entity("prod-a", "Product A", "product")
        mod_a1 = self._make_entity("mod-a1", "Module A1", "module", parent_id="prod-a")
        mod_a2 = self._make_entity("mod-a2", "Module A2", "module", parent_id="prod-a")

        entity_lookup = {
            "mod-a1": mod_a1,
            "mod-a2": mod_a2,
            "prod-a": prod_a,
        }
        repos["entity_repo"].get_by_id = AsyncMock(side_effect=lambda eid: entity_lookup.get(eid))

        svc = _make_service(repos)
        await svc.add_relationship(
            source_id="mod-a1",
            target_id="mod-a2",
            rel_type="related_to",
            description="auto-inferred",
        )

        # Should be persisted
        repos["relationship_repo"].add.assert_called_once()

    async def test_manual_cross_product_allowed(self):
        """Manually created related_to across products SHOULD be persisted."""
        repos = _mock_repos()
        prod_a = self._make_entity("prod-a", "Product A", "product")
        mod_a = self._make_entity("mod-a", "Module A", "module", parent_id="prod-a")
        prod_b = self._make_entity("prod-b", "Product B", "product")
        mod_b = self._make_entity("mod-b", "Module B", "module", parent_id="prod-b")

        entity_lookup = {
            "mod-a": mod_a,
            "mod-b": mod_b,
            "prod-a": prod_a,
            "prod-b": prod_b,
        }
        repos["entity_repo"].get_by_id = AsyncMock(side_effect=lambda eid: entity_lookup.get(eid))

        svc = _make_service(repos)
        await svc.add_relationship(
            source_id="mod-a",
            target_id="mod-b",
            rel_type="related_to",
            description="These modules are strategically related",
        )

        # Manually created should be persisted
        repos["relationship_repo"].add.assert_called_once()


class _CaptureGovernanceAI:
    """Test double for capturing infer_all inputs."""

    def __init__(self) -> None:
        self.calls: list[tuple[dict, list[dict], list[dict]]] = []

    def _rule_classify(self, name: str, existing_entities: list[dict]):
        return (None, None)

    def infer_all(self, entity_data: dict, existing_entities: list[dict], unlinked_docs: list[dict]):
        self.calls.append((entity_data, existing_entities, unlinked_docs))
        return None


class TestGovernanceAIPromptInputFiltering:
    async def test_pre_save_infer_all_excludes_document_entities(self):
        repos = _mock_repos()
        repos["entity_repo"].list_by_parent = AsyncMock(return_value=[])
        doc = Entity(
            id="doc-1",
            name="Spec A",
            type="document",
            summary="doc",
            tags=Tags(what=["x"], why="x", how="x", who=["x"]),
            sources=[{"uri": "docs/spec-a.md"}],
        )
        module = Entity(
            id="mod-1",
            name="Module A",
            type="module",
            summary="module",
            tags=Tags(what=["x"], why="x", how="x", who=["x"]),
        )
        repos["entity_repo"].list_all = AsyncMock(return_value=[doc, module])

        gov = _CaptureGovernanceAI()
        svc = OntologyService(
            entity_repo=repos["entity_repo"],
            relationship_repo=repos["relationship_repo"],
            document_repo=repos["document_repo"],
            protocol_repo=repos["protocol_repo"],
            blindspot_repo=repos["blindspot_repo"],
            governance_ai=gov,
        )

        with pytest.raises(ValueError, match="Invalid entity type"):
            await svc.upsert_entity({
                "name": "New Without Type",
                "summary": "needs classify",
                "tags": {"what": ["x"], "why": "x", "how": "x", "who": ["x"]},
            })

        assert len(gov.calls) == 1
        _, existing_entities, unlinked_docs = gov.calls[0]
        assert {e["id"] for e in existing_entities} == {"mod-1"}
        assert all(e["type"] != "document" for e in existing_entities)
        assert {d["id"] for d in unlinked_docs} == {"doc-1"}
        assert unlinked_docs[0]["summary"] == "doc"
        assert unlinked_docs[0]["source_uri"] == "docs/spec-a.md"

    async def test_infer_all_excludes_document_entities_from_entity_table(self):
        repos = _mock_repos()
        repos["entity_repo"].list_by_parent = AsyncMock(return_value=[])

        saved = Entity(
            id="ent-new",
            name="New Product",
            type="product",
            summary="new",
            tags=Tags(what=["x"], why="x", how="x", who=["x"]),
        )
        module = Entity(
            id="mod-1",
            name="Module A",
            type="module",
            summary="module",
            tags=Tags(what=["x"], why="x", how="x", who=["x"]),
        )
        doc = Entity(
            id="doc-1",
            name="Spec A",
            type="document",
            summary="doc",
            tags=Tags(what=["x"], why="x", how="x", who=["x"]),
        )
        repos["entity_repo"].list_all = AsyncMock(return_value=[saved, module, doc])
        repos["entity_repo"].get_by_id = AsyncMock(return_value=saved)

        gov = _CaptureGovernanceAI()
        svc = OntologyService(
            entity_repo=repos["entity_repo"],
            relationship_repo=repos["relationship_repo"],
            document_repo=repos["document_repo"],
            protocol_repo=repos["protocol_repo"],
            blindspot_repo=repos["blindspot_repo"],
            governance_ai=gov,
        )

        await svc.upsert_entity(_valid_entity_data(
            id="ent-new",
            name="New Product",
            type="product",
            summary="new",
        ))

        assert len(gov.calls) == 1
        _, existing_entities, unlinked_docs = gov.calls[0]
        assert {e["id"] for e in existing_entities} == {"mod-1"}
        assert all(e["type"] != "document" for e in existing_entities)
        assert {d["id"] for d in unlinked_docs} == {"doc-1"}

    async def test_auto_inferred_relationship_uses_model_description(self):
        repos = _mock_repos()
        repos["entity_repo"].list_by_parent = AsyncMock(return_value=[])
        repos["entity_repo"].find_duplicate = AsyncMock(return_value=None)

        saved = Entity(
            id="ent-new",
            name="New Product",
            type="product",
            summary="new",
            tags=Tags(what=["x"], why="x", how="x", who=["x"]),
        )
        target = Entity(
            id="mod-1",
            name="Module A",
            type="module",
            summary="module",
            tags=Tags(what=["x"], why="x", how="x", who=["x"]),
        )
        repos["entity_repo"].list_all = AsyncMock(return_value=[saved, target])
        repos["entity_repo"].get_by_id = AsyncMock(side_effect=lambda eid: {"ent-new": saved, "mod-1": target}.get(eid))

        class _Gov:
            def infer_all(self, entity_data, existing_entities, unlinked_docs):
                return GovernanceInference(
                    rels=[
                        InferredRel(
                            target="mod-1",
                            type="impacts",
                            description="A 改了定價規則→B 的銷售話術要跟著看",
                        )
                    ]
                )

        svc = OntologyService(
            entity_repo=repos["entity_repo"],
            relationship_repo=repos["relationship_repo"],
            document_repo=repos["document_repo"],
            protocol_repo=repos["protocol_repo"],
            blindspot_repo=repos["blindspot_repo"],
            governance_ai=_Gov(),
        )

        await svc.upsert_entity(_valid_entity_data(
            id="ent-new",
            name="New Product",
            type="product",
            summary="new",
        ))

        added_rel = repos["relationship_repo"].add.call_args[0][0]
        assert added_rel.description == "A 改了定價規則→B 的銷售話術要跟著看"

    async def test_l2_hard_gate_pre_save_infer_all_includes_doc_context(self):
        repos = _mock_repos()
        repos["entity_repo"].list_by_parent = AsyncMock(return_value=[])
        parent = Entity(
            id="parent-1",
            name="Product",
            type="product",
            summary="Parent",
            tags=Tags(what=["x"], why="x", how="x", who=["x"]),
        )
        doc = Entity(
            id="doc-1",
            name="Spec A",
            type="document",
            summary="Document Summary",
            tags=Tags(what=["x"], why="x", how="x", who=["x"]),
            sources=[{"uri": "docs/spec-a.md"}],
        )
        repos["entity_repo"].get_by_id = AsyncMock(return_value=parent)
        repos["entity_repo"].get_by_name = AsyncMock(return_value=None)
        repos["entity_repo"].list_all = AsyncMock(return_value=[parent, doc])

        class _GovCapture:
            def __init__(self):
                self.calls = []

            def infer_all(self, entity_data, existing_entities, unlinked_docs):
                self.calls.append((entity_data, existing_entities, unlinked_docs))
                return GovernanceInference(
                    rels=[
                        InferredRel(
                            target="parent-1",
                            type="impacts",
                            description="A 改了策略→B 的優先級要跟著看",
                        )
                    ]
                )

        gov = _GovCapture()
        svc = OntologyService(
            entity_repo=repos["entity_repo"],
            relationship_repo=repos["relationship_repo"],
            document_repo=repos["document_repo"],
            protocol_repo=repos["protocol_repo"],
            blindspot_repo=repos["blindspot_repo"],
            governance_ai=gov,
        )

        await svc.upsert_entity(_valid_entity_data(type="module", parent_id="parent-1"))
        assert len(gov.calls) >= 1
        _, _, unlinked_docs = gov.calls[0]
        assert {d["id"] for d in unlinked_docs} == {"doc-1"}
        assert unlinked_docs[0]["summary"] == "Document Summary"
        assert unlinked_docs[0]["source_uri"] == "docs/spec-a.md"

    async def test_infer_all_payload_includes_global_context(self):
        repos = _mock_repos()
        repos["entity_repo"].list_by_parent = AsyncMock(return_value=[])
        saved = Entity(
            id="ent-new",
            name="計費模型",
            type="module",
            summary="定義方案與升降級規則",
            parent_id="prod-1",
            tags=Tags(what=["pricing"], why="revenue", how="rules", who=["pm"]),
        )
        product = Entity(
            id="prod-1",
            name="ZenOS",
            type="product",
            summary="AI context layer",
            tags=Tags(what=["platform"], why="shared context", how="mcp", who=["pm"]),
        )
        doc = Entity(
            id="doc-1",
            name="pricing-rules.md",
            type="document",
            summary="方案切換與升降級條件",
            tags=Tags(what=["pricing"], why="revenue", how="spec", who=["pm"]),
            sources=[{"uri": "docs/pricing-rules.md"}],
        )
        repos["entity_repo"].list_all = AsyncMock(return_value=[saved, product, doc])
        repos["entity_repo"].get_by_id = AsyncMock(side_effect=lambda eid: {"ent-new": saved, "prod-1": product, "doc-1": doc}.get(eid))

        gov = _CaptureGovernanceAI()
        svc = OntologyService(
            entity_repo=repos["entity_repo"],
            relationship_repo=repos["relationship_repo"],
            document_repo=repos["document_repo"],
            protocol_repo=repos["protocol_repo"],
            blindspot_repo=repos["blindspot_repo"],
            governance_ai=gov,
        )

        await svc.upsert_entity(_valid_entity_data(
            id="ent-new",
            name="計費模型",
            type="module",
            parent_id="prod-1",
            summary="定義方案與升降級規則",
            tags={"what": ["pricing"], "why": "revenue", "how": "rules", "who": ["pm"]},
        ))

        assert len(gov.calls) == 1
        entity_data, _, _ = gov.calls[0]
        global_context = entity_data.get("_global_context")
        assert isinstance(global_context, dict)
        assert global_context["entity_counts"]["product"] == 1
        assert global_context["document_count"] == 1
        assert isinstance(global_context["recurring_terms"], list)
        assert any("ZenOS" in line for line in global_context["active_products"])
        assert any("ZenOS" in line for line in global_context["impact_target_hints"])
