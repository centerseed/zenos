"""Tests for compute_impact_chain in OntologyService.

Strategy:
- Mock _relationships and _entities repositories so tests run without DB.
- Tests verify BFS traversal, cycle detection, max_depth guard,
  graceful fallback when entity is deleted (None), and empty-chain edge case.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from zenos.application.ontology_service import OntologyService
from zenos.domain.models import Entity, EntityType, Relationship, RelationshipType, Tags


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

def _make_entity(eid: str, name: str) -> Entity:
    return Entity(
        id=eid,
        name=name,
        type=EntityType.MODULE,
        summary="test entity",
        tags=Tags(what="x", why="y", how="z", who="w"),
    )


def _make_rel(
    src: str,
    tgt: str,
    rel_type: str = RelationshipType.IMPACTS,
    verb: str | None = None,
) -> Relationship:
    return Relationship(
        id=f"{src}->{tgt}",
        source_entity_id=src,
        target_id=tgt,
        type=rel_type,
        description="test",
        verb=verb,
    )


def _build_service(
    entities: dict[str, Entity | None],
    rels_by_entity: dict[str, list[Relationship]],
) -> OntologyService:
    """Build a minimal OntologyService with mocked repos."""
    svc = object.__new__(OntologyService)

    entity_repo = MagicMock()
    async def get_by_id(eid: str) -> Entity | None:
        return entities.get(eid)
    entity_repo.get_by_id = get_by_id

    rel_repo = MagicMock()
    async def list_by_entity(eid: str) -> list[Relationship]:
        return rels_by_entity.get(eid, [])
    rel_repo.list_by_entity = list_by_entity

    svc._entities = entity_repo
    svc._relationships = rel_repo
    return svc


# ──────────────────────────────────────────────
# Tests
# ──────────────────────────────────────────────

class TestComputeImpactChain:

    @pytest.mark.asyncio
    async def test_empty_chain_when_no_outgoing_edges(self):
        """A node with no outgoing relationships returns an empty list."""
        entities = {"a": _make_entity("a", "Alpha")}
        rels_by_entity = {"a": []}
        svc = _build_service(entities, rels_by_entity)

        result = await svc.compute_impact_chain("a")
        assert result == []

    @pytest.mark.asyncio
    async def test_single_hop(self):
        """A → B returns one hop entry with correct fields."""
        a = _make_entity("a", "Alpha")
        b = _make_entity("b", "Beta")
        rel_ab = _make_rel("a", "b", verb="校準")

        entities = {"a": a, "b": b}
        rels_by_entity = {"a": [rel_ab], "b": []}
        svc = _build_service(entities, rels_by_entity)

        result = await svc.compute_impact_chain("a")
        assert len(result) == 1
        hop = result[0]
        assert hop["from_id"] == "a"
        assert hop["from_name"] == "Alpha"
        assert hop["to_id"] == "b"
        assert hop["to_name"] == "Beta"
        assert hop["verb"] == "校準"
        assert hop["type"] == RelationshipType.IMPACTS

    @pytest.mark.asyncio
    async def test_multi_hop_chain(self):
        """A → B → C returns two hops in BFS order."""
        a = _make_entity("a", "Alpha")
        b = _make_entity("b", "Beta")
        c = _make_entity("c", "Gamma")
        rel_ab = _make_rel("a", "b", verb="觸發")
        rel_bc = _make_rel("b", "c", verb="驅動")

        entities = {"a": a, "b": b, "c": c}
        rels_by_entity = {
            "a": [rel_ab],
            "b": [rel_ab, rel_bc],  # list_by_entity returns both directions; only outgoing should be used
            "c": [],
        }
        svc = _build_service(entities, rels_by_entity)

        result = await svc.compute_impact_chain("a")
        assert len(result) == 2
        assert result[0]["from_id"] == "a"
        assert result[0]["to_id"] == "b"
        assert result[0]["verb"] == "觸發"
        assert result[1]["from_id"] == "b"
        assert result[1]["to_id"] == "c"
        assert result[1]["verb"] == "驅動"

    @pytest.mark.asyncio
    async def test_cycle_does_not_loop_infinitely(self):
        """A → B → C → A cycle must terminate without infinite recursion."""
        a = _make_entity("a", "Alpha")
        b = _make_entity("b", "Beta")
        c = _make_entity("c", "Gamma")
        rel_ab = _make_rel("a", "b")
        rel_bc = _make_rel("b", "c")
        rel_ca = _make_rel("c", "a")  # closes the cycle

        entities = {"a": a, "b": b, "c": c}
        rels_by_entity = {
            "a": [rel_ab],
            "b": [rel_bc],
            "c": [rel_ca],
        }
        svc = _build_service(entities, rels_by_entity)

        result = await svc.compute_impact_chain("a")
        # Should have exactly 2 hops (a→b, b→c); c→a is skipped because 'a' already visited
        assert len(result) == 2
        to_ids = [h["to_id"] for h in result]
        assert "b" in to_ids
        assert "c" in to_ids

    @pytest.mark.asyncio
    async def test_max_depth_limits_traversal(self):
        """Chain deeper than max_depth is not traversed beyond the limit."""
        # Build chain a → b → c → d → e (depth 4)
        nodes = {nid: _make_entity(nid, nid.upper()) for nid in ["a", "b", "c", "d", "e"]}
        chain = ["a", "b", "c", "d", "e"]
        rels_by_entity: dict[str, list[Relationship]] = {}
        for i, src in enumerate(chain[:-1]):
            tgt = chain[i + 1]
            rels_by_entity[src] = [_make_rel(src, tgt)]
        rels_by_entity["e"] = []

        svc = _build_service(nodes, rels_by_entity)

        # max_depth=2 → only a→b, b→c
        result = await svc.compute_impact_chain("a", max_depth=2)
        assert len(result) == 2
        assert result[-1]["to_id"] == "c"

    @pytest.mark.asyncio
    async def test_deleted_entity_falls_back_to_id(self):
        """When target entity is deleted (None), to_name falls back to entity_id."""
        a = _make_entity("a", "Alpha")
        rel_ab = _make_rel("a", "missing-id", verb="觸發")

        entities: dict[str, Entity | None] = {"a": a, "missing-id": None}
        rels_by_entity = {"a": [rel_ab], "missing-id": []}
        svc = _build_service(entities, rels_by_entity)

        result = await svc.compute_impact_chain("a")
        assert len(result) == 1
        assert result[0]["to_name"] == "missing-id"  # fallback to ID

    @pytest.mark.asyncio
    async def test_only_outgoing_edges_are_traversed(self):
        """Incoming edges (where current node is target) must be ignored."""
        a = _make_entity("a", "Alpha")
        b = _make_entity("b", "Beta")
        # rel_ba is incoming to a; it should NOT appear in result when starting from a
        rel_ba = _make_rel("b", "a")

        entities = {"a": a, "b": b}
        rels_by_entity = {
            "a": [rel_ba],  # list_by_entity returns it, but it's incoming to a
        }
        svc = _build_service(entities, rels_by_entity)

        result = await svc.compute_impact_chain("a")
        assert result == []

    @pytest.mark.asyncio
    async def test_verb_none_preserved_in_result(self):
        """Relationships without a verb are represented with verb=None in the result."""
        a = _make_entity("a", "Alpha")
        b = _make_entity("b", "Beta")
        rel_ab = _make_rel("a", "b", verb=None)

        entities = {"a": a, "b": b}
        rels_by_entity = {"a": [rel_ab], "b": []}
        svc = _build_service(entities, rels_by_entity)

        result = await svc.compute_impact_chain("a")
        assert result[0]["verb"] is None


class TestReverseImpactChain:

    @pytest.mark.asyncio
    async def test_reverse_single_hop(self):
        """B has incoming edge from A → reverse chain from B returns A."""
        a = _make_entity("a", "Alpha")
        b = _make_entity("b", "Beta")
        rel_ab = _make_rel("a", "b", verb="校準")

        entities = {"a": a, "b": b}
        rels_by_entity = {
            "a": [rel_ab],
            "b": [rel_ab],  # list_by_entity returns both directions
        }
        svc = _build_service(entities, rels_by_entity)

        result = await svc.compute_impact_chain("b", direction="reverse")
        assert len(result) == 1
        assert result[0]["from_id"] == "a"
        assert result[0]["from_name"] == "Alpha"
        assert result[0]["to_id"] == "b"
        assert result[0]["to_name"] == "Beta"
        assert result[0]["verb"] == "校準"

    @pytest.mark.asyncio
    async def test_reverse_multi_hop(self):
        """A→B→C: reverse from C returns B→C and A→B."""
        a = _make_entity("a", "Alpha")
        b = _make_entity("b", "Beta")
        c = _make_entity("c", "Gamma")
        rel_ab = _make_rel("a", "b", verb="觸發")
        rel_bc = _make_rel("b", "c", verb="驅動")

        entities = {"a": a, "b": b, "c": c}
        rels_by_entity = {
            "a": [rel_ab],
            "b": [rel_ab, rel_bc],
            "c": [rel_bc],
        }
        svc = _build_service(entities, rels_by_entity)

        result = await svc.compute_impact_chain("c", direction="reverse")
        assert len(result) == 2
        # BFS order: first hop is b→c, second is a→b
        assert result[0]["from_id"] == "b"
        assert result[0]["to_id"] == "c"
        assert result[1]["from_id"] == "a"
        assert result[1]["to_id"] == "b"

    @pytest.mark.asyncio
    async def test_reverse_empty_when_no_incoming(self):
        """A node with no incoming edges returns empty reverse chain."""
        a = _make_entity("a", "Alpha")
        rel_ab = _make_rel("a", "b")

        entities = {"a": a}
        rels_by_entity = {"a": [rel_ab]}
        svc = _build_service(entities, rels_by_entity)

        result = await svc.compute_impact_chain("a", direction="reverse")
        assert result == []

    @pytest.mark.asyncio
    async def test_forward_unchanged_with_direction_param(self):
        """Explicitly passing direction='forward' gives same result as default."""
        a = _make_entity("a", "Alpha")
        b = _make_entity("b", "Beta")
        rel_ab = _make_rel("a", "b")

        entities = {"a": a, "b": b}
        rels_by_entity = {"a": [rel_ab], "b": []}
        svc = _build_service(entities, rels_by_entity)

        default = await svc.compute_impact_chain("a")
        explicit = await svc.compute_impact_chain("a", direction="forward")
        assert default == explicit

    @pytest.mark.asyncio
    async def test_both_direction_returns_union(self):
        """direction='both' returns forward + reverse combined."""
        a = _make_entity("a", "Alpha")
        b = _make_entity("b", "Beta")
        c = _make_entity("c", "Gamma")
        rel_ab = _make_rel("a", "b")
        rel_cb = _make_rel("c", "b")

        entities = {"a": a, "b": b, "c": c}
        rels_by_entity = {
            "a": [rel_ab],
            "b": [rel_ab, rel_cb],
            "c": [rel_cb],
        }
        svc = _build_service(entities, rels_by_entity)

        result = await svc.compute_impact_chain("b", direction="both")
        # forward from b: nothing (b has no outgoing)
        # reverse to b: a→b and c→b
        assert len(result) == 2
