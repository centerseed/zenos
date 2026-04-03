"""Tests for domain model changes: new RelationshipType values and Entity.level field."""

from __future__ import annotations

import pytest

from zenos.domain.models import (
    AccessPolicy,
    AgentPrincipal,
    AgentScope,
    Classification,
    Entity,
    EntityEntry,
    EntryStatus,
    EntryType,
    EntityType,
    InheritanceMode,
    Relationship,
    RelationshipType,
    Tags,
    UserPrincipal,
)


# ──────────────────────────────────────────────
# RelationshipType — new enum values
# ──────────────────────────────────────────────

class TestRelationshipTypeNewValues:
    def test_impacts_value(self):
        assert RelationshipType.IMPACTS == "impacts"

    def test_enables_value(self):
        assert RelationshipType.ENABLES == "enables"

    def test_impacts_is_str(self):
        assert isinstance(RelationshipType.IMPACTS, str)

    def test_enables_is_str(self):
        assert isinstance(RelationshipType.ENABLES, str)

    def test_all_original_values_still_present(self):
        original = {
            RelationshipType.DEPENDS_ON,
            RelationshipType.SERVES,
            RelationshipType.OWNED_BY,
            RelationshipType.PART_OF,
            RelationshipType.BLOCKS,
            RelationshipType.RELATED_TO,
        }
        assert len(original) == 6

    def test_total_relationship_types(self):
        assert len(RelationshipType) == 8  # 6 original + 2 new


# ──────────────────────────────────────────────
# Entity.level field
# ──────────────────────────────────────────────

def _make_tags() -> Tags:
    return Tags(what="test", why="testing", how="automated", who="developer")


class TestEntityLevelField:
    def test_level_defaults_to_none(self):
        entity = Entity(
            name="TestProduct",
            type=EntityType.PRODUCT,
            summary="A test product",
            tags=_make_tags(),
        )
        assert entity.level is None

    def test_level_set_to_1_for_product(self):
        entity = Entity(
            name="Paceriz",
            type=EntityType.PRODUCT,
            summary="Running coach app",
            tags=_make_tags(),
            level=1,
        )
        assert entity.level == 1

    def test_level_set_to_2_for_module(self):
        entity = Entity(
            name="Training Load",
            type=EntityType.MODULE,
            summary="Consensus concept for training load",
            tags=_make_tags(),
            level=2,
        )
        assert entity.level == 2

    def test_level_set_to_3_for_document(self):
        entity = Entity(
            name="API Spec",
            type=EntityType.DOCUMENT,
            summary="API specification document",
            tags=_make_tags(),
            level=3,
        )
        assert entity.level == 3

    def test_level_accepts_none_explicitly(self):
        entity = Entity(
            name="Unknown",
            type=EntityType.MODULE,
            summary="Entity with no assigned level",
            tags=_make_tags(),
            level=None,
        )
        assert entity.level is None


# ──────────────────────────────────────────────
# EntityEntry domain model
# ──────────────────────────────────────────────

class TestEntityEntryModel:
    def test_entry_type_enum_values(self):
        assert EntryType.DECISION == "decision"
        assert EntryType.INSIGHT == "insight"
        assert EntryType.LIMITATION == "limitation"
        assert EntryType.CHANGE == "change"
        assert EntryType.CONTEXT == "context"
        assert len(EntryType) == 5

    def test_entry_status_enum_values(self):
        assert EntryStatus.ACTIVE == "active"
        assert EntryStatus.SUPERSEDED == "superseded"
        assert EntryStatus.ARCHIVED == "archived"
        assert len(EntryStatus) == 3

    def test_entity_entry_defaults(self):
        entry = EntityEntry(
            id="e1",
            partner_id="p1",
            entity_id="ent1",
            type=EntryType.DECISION,
            content="A decision was made",
        )
        assert entry.status == "active"
        assert entry.context is None
        assert entry.author is None
        assert entry.department is None
        assert entry.source_task_id is None
        assert entry.superseded_by is None
        assert entry.created_at is not None

    def test_entity_entry_all_fields(self):
        from datetime import datetime, timezone
        ts = datetime(2026, 3, 28, tzinfo=timezone.utc)
        entry = EntityEntry(
            id="e1",
            partner_id="p1",
            entity_id="ent1",
            type=EntryType.INSIGHT,
            content="An insight about the domain",
            status=EntryStatus.SUPERSEDED,
            context="Additional context here",
            author="Barry",
            source_task_id="task-99",
            superseded_by="e2",
            created_at=ts,
        )
        assert entry.type == "insight"
        assert entry.status == "superseded"
        assert entry.superseded_by == "e2"
        assert entry.author == "Barry"
        assert entry.created_at == ts

    def test_entry_type_is_str_enum(self):
        """EntryType members are also plain strings (str, Enum)."""
        assert isinstance(EntryType.DECISION, str)
        assert EntryType.DECISION == "decision"

    def test_entry_status_is_str_enum(self):
        assert isinstance(EntryStatus.ACTIVE, str)
        assert EntryStatus.ACTIVE == "active"


class TestPermissionGovernanceModels:
    def test_user_principal_defaults(self):
        principal = UserPrincipal(user_id="u1", partner_id="p1")
        assert principal.role_ids == []
        assert principal.department_ids == []
        assert principal.is_admin is False

    def test_agent_scope_defaults(self):
        scope = AgentScope()
        assert scope.read_classification_max == Classification.OPEN
        assert scope.write_classification_max == Classification.INTERNAL

    def test_access_policy_inherit_disallows_custom_scope(self):
        policy = AccessPolicy(
            classification=Classification.INTERNAL,
            inheritance_mode=InheritanceMode.INHERIT,
            allowed_role_ids=["engineering"],
        )
        assert policy.validate_custom_scope() is False

    def test_access_policy_cannot_weaken_parent_classification(self):
        policy = AccessPolicy(classification=Classification.INTERNAL)
        assert policy.validate_transition_from_parent(Classification.RESTRICTED) is False

    def test_agent_principal_keeps_scope(self):
        principal = AgentPrincipal(agent_id="a1", owner_user_id="u1", partner_id="p1")
        assert principal.scope.read_classification_max == Classification.OPEN


# ──────────────────────────────────────────────
# Relationship.verb field
# ──────────────────────────────────────────────

class TestRelationshipVerbField:
    def test_verb_defaults_to_none(self):
        rel = Relationship(
            source_entity_id="a",
            target_id="b",
            type=RelationshipType.IMPACTS,
            description="A impacts B",
        )
        assert rel.verb is None

    def test_verb_can_be_set(self):
        rel = Relationship(
            source_entity_id="a",
            target_id="b",
            type=RelationshipType.IMPACTS,
            description="A impacts B",
            verb="校準",
        )
        assert rel.verb == "校準"

    def test_verb_accepts_none_explicitly(self):
        rel = Relationship(
            source_entity_id="a",
            target_id="b",
            type=RelationshipType.ENABLES,
            description="A enables B",
            verb=None,
        )
        assert rel.verb is None

    def test_verb_and_other_fields_coexist(self):
        rel = Relationship(
            source_entity_id="src-1",
            target_id="tgt-1",
            type=RelationshipType.DEPENDS_ON,
            description="depends on",
            id="rel-1",
            confirmed_by_user=True,
            verb="觸發",
        )
        assert rel.id == "rel-1"
        assert rel.confirmed_by_user is True
        assert rel.verb == "觸發"
