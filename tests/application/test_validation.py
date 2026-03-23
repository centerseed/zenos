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
from zenos.domain.models import Entity, Relationship, Tags


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
        # upsert_document now returns Entity(type="document")
        assert result.name == "API Spec"
        assert result.type == "document"


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
