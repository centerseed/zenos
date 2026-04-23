"""Tests for is_collaboration_root_entity — ADR-047 D1/D2.

Covers: type-agnostic L1 detection, strict level check (no level-null fallback),
parent_id exclusion, empty-string parent_id, camelCase parentId, duck typing.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from zenos.domain.knowledge.collaboration_roots import is_collaboration_root_entity


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_entity(**kwargs) -> SimpleNamespace:
    """Build a duck-typed entity with the given attributes."""
    return SimpleNamespace(**kwargs)


# ---------------------------------------------------------------------------
# 1. Any type with level=1 and no parent is L1
# ---------------------------------------------------------------------------

class TestAnyTypeWithLevel1AndNoParentIsL1:
    """ADR-047 D2: type is a UI label, not a gate."""

    @pytest.mark.parametrize("entity_type", [
        "product",
        "company",
        "person",
        "deal",
        "goal",
        "role",
    ])
    def test_any_type_with_level_1_and_no_parent_is_l1(self, entity_type: str) -> None:
        entity = make_entity(type=entity_type, level=1, parent_id=None)
        assert is_collaboration_root_entity(entity) is True


# ---------------------------------------------------------------------------
# 2. level=2 is never L1
# ---------------------------------------------------------------------------

class TestLevel2IsNotL1:

    @pytest.mark.parametrize("entity_type", ["product", "company", "module"])
    def test_level_2_is_not_l1(self, entity_type: str) -> None:
        entity = make_entity(type=entity_type, level=2, parent_id=None)
        assert is_collaboration_root_entity(entity) is False


# ---------------------------------------------------------------------------
# 3. level=None is NOT L1 (strict mode — ADR-047 D1 removes level-null fallback)
# ---------------------------------------------------------------------------

class TestLevelNoneIsNotL1:

    def test_level_none_regardless_of_type_is_not_l1(self) -> None:
        """After GATE A backfill, no entity should have level=None.
        Strict check: level=None must return False."""
        entity = make_entity(type="product", level=None, parent_id=None)
        assert is_collaboration_root_entity(entity) is False

    def test_missing_level_attribute_is_not_l1(self) -> None:
        """Entity with no level attribute at all must return False."""
        entity = make_entity(type="product", parent_id=None)
        assert is_collaboration_root_entity(entity) is False


# ---------------------------------------------------------------------------
# 4. level=1 WITH parent_id is NOT L1 (anomaly case)
# ---------------------------------------------------------------------------

class TestLevel1WithParentIdIsNotL1:

    def test_level_1_with_parent_id_is_not_l1(self) -> None:
        entity = make_entity(type="company", level=1, parent_id="some-parent-id")
        assert is_collaboration_root_entity(entity) is False


# ---------------------------------------------------------------------------
# 5. Empty-string parent_id is treated as no-parent → L1
# ---------------------------------------------------------------------------

class TestEmptyParentStringIsL1:

    def test_level_1_with_empty_parent_string_is_l1(self) -> None:
        """ADR-047: empty string parent_id is equivalent to None (no parent)."""
        entity = make_entity(type="product", level=1, parent_id="")
        assert is_collaboration_root_entity(entity) is True


# ---------------------------------------------------------------------------
# 6. None entity returns False
# ---------------------------------------------------------------------------

class TestNoneEntityReturnsFalse:

    def test_none_entity_returns_false(self) -> None:
        assert is_collaboration_root_entity(None) is False


# ---------------------------------------------------------------------------
# 7. camelCase parentId is recognised
# ---------------------------------------------------------------------------

class TestParentIdCamelCaseSupported:

    def test_parentId_camelCase_non_empty_excludes_from_l1(self) -> None:
        """Objects that expose parentId (camelCase) instead of parent_id must be
        handled correctly — a non-empty parentId means not L1."""
        entity = make_entity(type="product", level=1, parentId="some-parent-id")
        assert is_collaboration_root_entity(entity) is False

    def test_parentId_camelCase_empty_is_l1(self) -> None:
        entity = make_entity(type="product", level=1, parentId="")
        assert is_collaboration_root_entity(entity) is True

    def test_parentId_camelCase_none_is_l1(self) -> None:
        entity = make_entity(type="company", level=1, parentId=None)
        assert is_collaboration_root_entity(entity) is True


# ---------------------------------------------------------------------------
# 8. Duck typing via SimpleNamespace (plain dict proxy)
# ---------------------------------------------------------------------------

class TestAcceptsPlainDictViaDuckTyping:

    def test_simple_namespace_duck_typing_works(self) -> None:
        """Verify that any duck-typed object (not an Entity domain model) works."""
        obj = SimpleNamespace(level=1, parent_id=None, type="person")
        assert is_collaboration_root_entity(obj) is True

    def test_simple_namespace_with_level_2_returns_false(self) -> None:
        obj = SimpleNamespace(level=2, parent_id=None, type="product")
        assert is_collaboration_root_entity(obj) is False
