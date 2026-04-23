"""Tests that CRM bridge uses DEFAULT_TYPE_LEVELS for entity level assignment.

ADR-047 S03: crm_service.py must not hardcode level=1. Instead it imports
DEFAULT_TYPE_LEVELS and uses DEFAULT_TYPE_LEVELS.get(entity_type) so that
future type changes only require updating the SSOT mapping.
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from zenos.application.crm.crm_service import CrmService
from zenos.domain.crm_models import Company, Contact, Deal, FunnelStage
from zenos.domain.knowledge import Entity, Relationship, Tags
from zenos.domain.knowledge.entity_levels import DEFAULT_TYPE_LEVELS


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _new_id_counter():
    i = 0
    def _new_id():
        nonlocal i
        i += 1
        return f"id-{i}"
    return _new_id


def _make_service():
    entity_repo = AsyncMock()
    relationship_repo = AsyncMock()
    crm_repo = AsyncMock()

    created_entities = []

    async def _upsert_entity(entity):
        created_entities.append(entity)
        return entity

    entity_repo.upsert = AsyncMock(side_effect=_upsert_entity)
    entity_repo.get_by_id = AsyncMock(return_value=None)

    relationship_repo.add = AsyncMock(side_effect=lambda r: r)

    return CrmService(
        crm_repo=crm_repo,
        entity_repo=entity_repo,
        relationship_repo=relationship_repo,
    ), entity_repo, crm_repo, created_entities


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestCrmServiceUsesDefaultTypeLevels:
    """Verify CRM bridge reads level from DEFAULT_TYPE_LEVELS SSOT."""

    @pytest.mark.asyncio
    async def test_create_company_entity_has_level_from_default_type_levels(self):
        """company entity created via CRM bridge must have level == DEFAULT_TYPE_LEVELS['company']."""
        svc, entity_repo, crm_repo, created_entities = _make_service()

        company = Company(
            id="co-1",
            partner_id="p1",
            name="Acme Corp",
        )
        crm_repo.create_company = AsyncMock(return_value=company)
        crm_repo.update_company = AsyncMock(return_value=company)

        await svc.create_company("p1", {"name": "Acme Corp"})

        assert len(created_entities) == 1
        entity = created_entities[0]
        assert entity.type == "company"
        assert entity.level == DEFAULT_TYPE_LEVELS.get("company")
        assert entity.level == 1  # sanity-check that SSOT value is as expected

    @pytest.mark.asyncio
    async def test_create_contact_entity_has_level_from_default_type_levels(self):
        """person entity created via CRM bridge must have level == DEFAULT_TYPE_LEVELS['person']."""
        svc, entity_repo, crm_repo, created_entities = _make_service()

        contact = Contact(
            id="ct-1",
            partner_id="p1",
            company_id="co-1",
            name="Alice Chen",
        )
        crm_repo.create_contact = AsyncMock(return_value=contact)
        crm_repo.get_company = AsyncMock(return_value=None)  # no company entity link
        crm_repo.update_contact = AsyncMock(return_value=contact)

        await svc.create_contact("p1", {"company_id": "co-1", "name": "Alice Chen"})

        assert len(created_entities) == 1
        entity = created_entities[0]
        assert entity.type == "person"
        assert entity.level == DEFAULT_TYPE_LEVELS.get("person")
        assert entity.level == 1

    @pytest.mark.asyncio
    async def test_create_deal_entity_has_level_from_default_type_levels(self):
        """deal entity created via CRM bridge must have level == DEFAULT_TYPE_LEVELS['deal']."""
        svc, entity_repo, crm_repo, created_entities = _make_service()

        deal = Deal(
            id="deal-1",
            partner_id="p1",
            title="Big Deal",
            company_id="co-1",
            owner_partner_id="p1",
            funnel_stage=FunnelStage.PROSPECT,
        )
        crm_repo.create_deal = AsyncMock(return_value=deal)
        crm_repo.get_company = AsyncMock(return_value=None)
        crm_repo.update_deal = AsyncMock(return_value=deal)
        crm_repo.list_contacts = AsyncMock(return_value=[])
        crm_repo.list_activities = AsyncMock(return_value=[])

        await svc.create_deal("p1", {
            "title": "Big Deal",
            "company_id": "co-1",
        })

        assert len(created_entities) == 1
        entity = created_entities[0]
        assert entity.type == "deal"
        assert entity.level == DEFAULT_TYPE_LEVELS.get("deal")
        assert entity.level == 1

    def test_company_level_in_default_type_levels_is_1(self):
        """Sanity: DEFAULT_TYPE_LEVELS must map company to 1."""
        assert DEFAULT_TYPE_LEVELS.get("company") == 1

    def test_person_level_in_default_type_levels_is_1(self):
        """Sanity: DEFAULT_TYPE_LEVELS must map person to 1."""
        assert DEFAULT_TYPE_LEVELS.get("person") == 1

    def test_deal_level_in_default_type_levels_is_1(self):
        """Sanity: DEFAULT_TYPE_LEVELS must map deal to 1."""
        assert DEFAULT_TYPE_LEVELS.get("deal") == 1
