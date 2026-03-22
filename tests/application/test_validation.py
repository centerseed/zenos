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
from zenos.domain.models import Entity, Tags


# ---------------------------------------------------------------------------
# Mock repository factory
# ---------------------------------------------------------------------------

def _mock_repos() -> dict:
    """Build a set of AsyncMock repositories for OntologyService."""
    entity_repo = AsyncMock()
    entity_repo.get_by_id = AsyncMock(return_value=None)
    entity_repo.get_by_name = AsyncMock(return_value=None)
    entity_repo.upsert = AsyncMock(side_effect=lambda e: e)

    relationship_repo = AsyncMock()
    relationship_repo.add = AsyncMock(side_effect=lambda r: r)
    relationship_repo.list_by_entity = AsyncMock(return_value=[])

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
        assert result.title == "API Spec"


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
