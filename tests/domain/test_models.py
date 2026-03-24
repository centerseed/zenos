"""Tests for domain model changes: new RelationshipType values and Entity.level field."""

from __future__ import annotations

import pytest

from zenos.domain.models import (
    Entity,
    EntityType,
    RelationshipType,
    Tags,
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
