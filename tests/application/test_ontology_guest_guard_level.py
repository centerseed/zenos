"""Tests for level-based guest write guard in OntologyService.

ADR-047 S03: Guest guard now uses level == 1 (or DEFAULT_TYPE_LEVELS fallback)
instead of a type whitelist (_L1_TYPES). Any entity type at level 1 is rejected
for guests, not just product/company/person.
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock

from zenos.application.knowledge.ontology_service import OntologyService
from zenos.domain.knowledge import Entity, Tags
from zenos.domain.knowledge.entity_levels import DEFAULT_TYPE_LEVELS


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_repos() -> dict:
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


def _make_service(repos: dict) -> OntologyService:
    return OntologyService(
        entity_repo=repos["entity_repo"],
        relationship_repo=repos["relationship_repo"],
        document_repo=repos["document_repo"],
        protocol_repo=repos["protocol_repo"],
        blindspot_repo=repos["blindspot_repo"],
    )


def _guest_partner(authorized_l1_ids: list[str] | None = None) -> dict:
    return {
        "workspaceRole": "guest",
        "authorizedEntityIds": authorized_l1_ids or [],
        "isAdmin": False,
    }


def _entity_data(type: str, **kwargs) -> dict:
    base = {
        "type": type,
        "name": f"Test {type.title()}",
        "summary": f"A {type} entity",
        "tags": {
            "what": [type],
            "why": "test",
            "how": "test",
            "who": ["test"],
        },
    }
    base.update(kwargs)
    return base


# ---------------------------------------------------------------------------
# Level-based L1 gate tests (ADR-047 S03 core validation)
# ---------------------------------------------------------------------------

class TestGuestGuardLevelBased:
    """Verify the guard uses level, not type whitelist."""

    @pytest.mark.asyncio
    async def test_company_type_rejected_because_level_1(self):
        """company defaults to level=1 via DEFAULT_TYPE_LEVELS — must be rejected for guests."""
        assert DEFAULT_TYPE_LEVELS.get("company") == 1
        repos = _make_repos()
        svc = _make_service(repos)
        with pytest.raises(PermissionError, match="[Gg]uest"):
            await svc.upsert_entity(
                _entity_data("company"),
                partner=_guest_partner(authorized_l1_ids=["l1-prod"]),
            )

    @pytest.mark.asyncio
    async def test_person_type_rejected_because_level_1(self):
        """person defaults to level=1 via DEFAULT_TYPE_LEVELS — must be rejected for guests."""
        assert DEFAULT_TYPE_LEVELS.get("person") == 1
        repos = _make_repos()
        svc = _make_service(repos)
        with pytest.raises(PermissionError, match="[Gg]uest"):
            await svc.upsert_entity(
                _entity_data("person"),
                partner=_guest_partner(authorized_l1_ids=["l1-prod"]),
            )

    @pytest.mark.asyncio
    async def test_deal_type_rejected_because_level_1(self):
        """deal defaults to level=1 via DEFAULT_TYPE_LEVELS — must be rejected for guests."""
        assert DEFAULT_TYPE_LEVELS.get("deal") == 1
        repos = _make_repos()
        svc = _make_service(repos)
        with pytest.raises(PermissionError, match="[Gg]uest"):
            await svc.upsert_entity(
                _entity_data("deal"),
                partner=_guest_partner(authorized_l1_ids=["l1-prod"]),
            )

    @pytest.mark.asyncio
    async def test_product_type_rejected_because_level_1(self):
        """product defaults to level=1 via DEFAULT_TYPE_LEVELS — must be rejected for guests."""
        assert DEFAULT_TYPE_LEVELS.get("product") == 1
        repos = _make_repos()
        svc = _make_service(repos)
        with pytest.raises(PermissionError, match="[Gg]uest"):
            await svc.upsert_entity(
                _entity_data("product"),
                partner=_guest_partner(authorized_l1_ids=["l1-prod"]),
            )

    @pytest.mark.asyncio
    async def test_explicit_level_1_rejected_regardless_of_type(self):
        """Any entity with explicit level=1 must be rejected for guests, regardless of type."""
        repos = _make_repos()
        svc = _make_service(repos)
        # Use a novel type not in DEFAULT_TYPE_LEVELS but caller sets level=1 explicitly
        with pytest.raises(PermissionError, match="[Gg]uest"):
            await svc.upsert_entity(
                _entity_data("goal", level=1),
                partner=_guest_partner(authorized_l1_ids=["l1-prod"]),
            )

    @pytest.mark.asyncio
    async def test_module_type_rejected_as_l2(self):
        """module is L2 — still rejected for guests (not an L1 gate but L2 gate)."""
        repos = _make_repos()
        svc = _make_service(repos)
        with pytest.raises(PermissionError, match="[Gg]uest"):
            await svc.upsert_entity(
                _entity_data("module", parent_id="l1-prod"),
                partner=_guest_partner(authorized_l1_ids=["l1-prod"]),
            )


class TestGuestGuardNonGuestUnaffected:
    """Non-guest partners are not subject to the level-based guard."""

    @pytest.mark.asyncio
    async def test_member_can_create_l1_company(self):
        """member role can create L1 company entity without PermissionError."""
        repos = _make_repos()
        svc = _make_service(repos)
        # member partner — no PermissionError expected
        result = await svc.upsert_entity(
            _entity_data("company"),
            partner={"workspaceRole": "member", "isAdmin": False},
        )
        assert result.entity.type == "company"
