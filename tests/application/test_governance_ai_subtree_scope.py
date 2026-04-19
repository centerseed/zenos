"""Regression: GovernanceAI auto-link must scope to L1 product subtree.

DF-20260419-2 F6: New L2 "客戶外展系統" under "Dogfood Test Product" was
auto-linked to 9 relationships spanning Paceriz, ZenOS, and Naruvia subtrees.
Fix: _build_infer_all_inputs filters candidates to same L1 product subtree
when scope_entity_id is provided.
"""
from __future__ import annotations

from zenos.application.knowledge.ontology_service import (
    _collect_subtree_ids,
    _find_product_root,
)
from zenos.domain.knowledge.models import Entity, Tags


def _entity(id_: str, level: int, parent_id: str | None, type_: str = "module") -> Entity:
    return Entity(
        id=id_,
        name=id_,
        type=type_ if level != 1 else "product",
        level=level,
        parent_id=parent_id,
        status="active",
        summary="",
        tags=Tags(what=[], why="", how="", who=[]),
    )


def test_find_product_root_self_for_l1():
    p = _entity("P1", 1, None, type_="product")
    emap = {"P1": p}
    assert _find_product_root("P1", emap) == "P1"


def test_find_product_root_walks_chain():
    p = _entity("P1", 1, None, type_="product")
    m = _entity("M1", 2, "P1")
    d = _entity("D1", 3, "M1", type_="document")
    emap = {"P1": p, "M1": m, "D1": d}
    assert _find_product_root("D1", emap) == "P1"
    assert _find_product_root("M1", emap) == "P1"


def test_find_product_root_orphan_returns_none():
    m = _entity("M1", 2, None)
    emap = {"M1": m}
    assert _find_product_root("M1", emap) is None


def test_find_product_root_cycle_safe():
    """Protect against corrupted parent_id cycles."""
    a = _entity("A", 2, "B")
    b = _entity("B", 2, "A")
    emap = {"A": a, "B": b}
    assert _find_product_root("A", emap) is None


def test_collect_subtree_excludes_other_products():
    """Canonical case for F6: two L1 products, modules under each, subtree
    collection must not cross product boundary."""
    p1 = _entity("P1", 1, None, type_="product")
    p2 = _entity("P2", 1, None, type_="product")
    m1 = _entity("M1", 2, "P1")
    m2 = _entity("M2", 2, "P2")
    emap = {"P1": p1, "P2": p2, "M1": m1, "M2": m2}

    p1_subtree = _collect_subtree_ids("P1", emap)
    assert p1_subtree == {"P1", "M1"}
    assert "M2" not in p1_subtree
    assert "P2" not in p1_subtree
