"""Tests for CrmService — uses mock repositories to verify business logic."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, call

import pytest

from zenos.application.crm_service import CrmService
from zenos.domain.crm_models import (
    Activity,
    ActivityType,
    Company,
    Contact,
    Deal,
    FunnelStage,
)
from zenos.domain.models import Entity, Relationship


# ── Fixtures ───────────────────────────────────────────────────────────


def _make_company(**kwargs) -> Company:
    defaults = dict(id="c1", partner_id="p1", name="測試公司", zenos_entity_id=None)
    defaults.update(kwargs)
    return Company(**defaults)


def _make_contact(**kwargs) -> Contact:
    defaults = dict(id="ct1", partner_id="p1", company_id="c1", name="王小明", zenos_entity_id=None)
    defaults.update(kwargs)
    return Contact(**defaults)


def _make_deal(**kwargs) -> Deal:
    defaults = dict(
        id="d1", partner_id="p1", title="AI 導入案",
        company_id="c1", owner_partner_id="p1",
        funnel_stage=FunnelStage.PROSPECT,
    )
    defaults.update(kwargs)
    return Deal(**defaults)


def _make_entity(**kwargs) -> Entity:
    from zenos.domain.models import Tags
    defaults = dict(
        id="e1", name="測試公司", type="company", level=1, summary="科技",
        tags=Tags(what=["company"], why="CRM", how="crm", who=["業務"]),
    )
    defaults.update(kwargs)
    return Entity(**defaults)


@pytest.fixture
def mock_crm_repo():
    repo = MagicMock()
    repo.create_company = AsyncMock()
    repo.get_company = AsyncMock()
    repo.update_company = AsyncMock()
    repo.list_companies = AsyncMock()
    repo.create_contact = AsyncMock()
    repo.get_contact = AsyncMock()
    repo.update_contact = AsyncMock()
    repo.list_contacts = AsyncMock()
    repo.create_deal = AsyncMock()
    repo.get_deal = AsyncMock()
    repo.update_deal = AsyncMock()
    repo.list_deals = AsyncMock()
    repo.create_activity = AsyncMock()
    repo.list_activities = AsyncMock()
    return repo


@pytest.fixture
def mock_entity_repo():
    repo = MagicMock()
    repo.upsert = AsyncMock()
    repo.get_by_id = AsyncMock()
    return repo


@pytest.fixture
def mock_rel_repo():
    repo = MagicMock()
    repo.add = AsyncMock()
    return repo


@pytest.fixture
def svc(mock_crm_repo, mock_entity_repo, mock_rel_repo):
    return CrmService(mock_crm_repo, mock_entity_repo, mock_rel_repo)


# ── create_company ─────────────────────────────────────────────────────

class TestCreateCompany:
    @pytest.mark.asyncio
    async def test_calls_crm_repo_create(self, svc, mock_crm_repo, mock_entity_repo):
        company = _make_company()
        entity = _make_entity()
        mock_crm_repo.create_company.return_value = company
        mock_entity_repo.upsert.return_value = entity
        mock_crm_repo.update_company.return_value = company

        await svc.create_company("p1", {"name": "測試公司"})

        mock_crm_repo.create_company.assert_called_once()
        created_company = mock_crm_repo.create_company.call_args[0][0]
        assert created_company.name == "測試公司"
        assert created_company.partner_id == "p1"

    @pytest.mark.asyncio
    async def test_triggers_entity_upsert_with_type_company(
        self, svc, mock_crm_repo, mock_entity_repo
    ):
        company = _make_company()
        entity = _make_entity()
        mock_crm_repo.create_company.return_value = company
        mock_entity_repo.upsert.return_value = entity
        mock_crm_repo.update_company.return_value = company

        await svc.create_company("p1", {"name": "測試公司"})

        mock_entity_repo.upsert.assert_called_once()
        upserted_entity = mock_entity_repo.upsert.call_args[0][0]
        assert upserted_entity.type == "company"

    @pytest.mark.asyncio
    async def test_backfills_zenos_entity_id(self, svc, mock_crm_repo, mock_entity_repo):
        company = _make_company()
        entity = _make_entity(id="entity-xyz")
        mock_crm_repo.create_company.return_value = company
        mock_entity_repo.upsert.return_value = entity
        mock_crm_repo.update_company.return_value = company

        result = await svc.create_company("p1", {"name": "測試公司"})

        mock_crm_repo.update_company.assert_called_once()
        # The company passed to update_company should have zenos_entity_id set
        updated = mock_crm_repo.update_company.call_args[0][0]
        assert updated.zenos_entity_id == "entity-xyz"


# ── create_contact ─────────────────────────────────────────────────────

class TestCreateContact:
    @pytest.mark.asyncio
    async def test_triggers_entity_upsert_with_type_person(
        self, svc, mock_crm_repo, mock_entity_repo, mock_rel_repo
    ):
        contact = _make_contact()
        company = _make_company(zenos_entity_id="company-entity-1")
        entity = _make_entity(id="person-entity-1", type="person", name="王小明")
        mock_crm_repo.create_contact.return_value = contact
        mock_crm_repo.get_company.return_value = company
        mock_entity_repo.upsert.return_value = entity
        mock_crm_repo.update_contact.return_value = contact

        await svc.create_contact("p1", {"name": "王小明", "company_id": "c1"})

        mock_entity_repo.upsert.assert_called_once()
        upserted = mock_entity_repo.upsert.call_args[0][0]
        assert upserted.type == "person"

    @pytest.mark.asyncio
    async def test_triggers_relationship_add_part_of(
        self, svc, mock_crm_repo, mock_entity_repo, mock_rel_repo
    ):
        contact = _make_contact()
        company = _make_company(zenos_entity_id="company-entity-1")
        entity = _make_entity(id="person-entity-1", type="person")
        mock_crm_repo.create_contact.return_value = contact
        mock_crm_repo.get_company.return_value = company
        mock_entity_repo.upsert.return_value = entity
        mock_crm_repo.update_contact.return_value = contact

        await svc.create_contact("p1", {"name": "王小明", "company_id": "c1"})

        mock_rel_repo.add.assert_called_once()
        relationship = mock_rel_repo.add.call_args[0][0]
        assert relationship.source_entity_id == "person-entity-1"
        assert relationship.target_id == "company-entity-1"
        assert relationship.type == "part_of"

    @pytest.mark.asyncio
    async def test_no_relationship_when_company_has_no_entity(
        self, svc, mock_crm_repo, mock_entity_repo, mock_rel_repo
    ):
        contact = _make_contact()
        company = _make_company(zenos_entity_id=None)  # no entity bridge
        entity = _make_entity(id="person-entity-1", type="person")
        mock_crm_repo.create_contact.return_value = contact
        mock_crm_repo.get_company.return_value = company
        mock_entity_repo.upsert.return_value = entity
        mock_crm_repo.update_contact.return_value = contact

        await svc.create_contact("p1", {"name": "王小明", "company_id": "c1"})

        mock_rel_repo.add.assert_not_called()


# ── update_deal_stage ──────────────────────────────────────────────────

class TestUpdateDealStage:
    @pytest.mark.asyncio
    async def test_creates_system_activity(self, svc, mock_crm_repo):
        deal = _make_deal(funnel_stage=FunnelStage.PROSPECT)
        mock_crm_repo.get_deal.return_value = deal
        mock_crm_repo.update_deal.return_value = deal
        mock_crm_repo.create_activity.return_value = MagicMock()

        await svc.update_deal_stage("p1", "d1", "需求訪談", "p1")

        mock_crm_repo.create_activity.assert_called_once()
        created_activity = mock_crm_repo.create_activity.call_args[0][0]
        assert created_activity.is_system is True
        assert created_activity.activity_type == ActivityType.SYSTEM

    @pytest.mark.asyncio
    async def test_system_activity_summary_contains_stages(self, svc, mock_crm_repo):
        deal = _make_deal(funnel_stage=FunnelStage.PROSPECT)
        mock_crm_repo.get_deal.return_value = deal
        mock_crm_repo.update_deal.return_value = deal
        mock_crm_repo.create_activity.return_value = MagicMock()

        await svc.update_deal_stage("p1", "d1", "需求訪談", "p1")

        activity = mock_crm_repo.create_activity.call_args[0][0]
        assert "潛在客戶" in activity.summary
        assert "需求訪談" in activity.summary

    @pytest.mark.asyncio
    async def test_deal_not_found_raises(self, svc, mock_crm_repo):
        mock_crm_repo.get_deal.return_value = None

        with pytest.raises(ValueError, match="not found"):
            await svc.update_deal_stage("p1", "missing-deal", "需求訪談", "p1")

    @pytest.mark.asyncio
    async def test_updates_funnel_stage(self, svc, mock_crm_repo):
        deal = _make_deal(funnel_stage=FunnelStage.PROSPECT)
        mock_crm_repo.get_deal.return_value = deal
        mock_crm_repo.update_deal.return_value = deal
        mock_crm_repo.create_activity.return_value = MagicMock()

        result = await svc.update_deal_stage("p1", "d1", "提案報價", "p1")

        assert result.funnel_stage == FunnelStage.PROPOSAL
        mock_crm_repo.update_deal.assert_called_once()


# ── list_deals ─────────────────────────────────────────────────────────

class TestListDeals:
    @pytest.mark.asyncio
    async def test_delegates_include_inactive_false(self, svc, mock_crm_repo):
        mock_crm_repo.list_deals.return_value = []
        await svc.list_deals("p1", include_inactive=False)
        mock_crm_repo.list_deals.assert_called_once_with("p1", False)

    @pytest.mark.asyncio
    async def test_delegates_include_inactive_true(self, svc, mock_crm_repo):
        mock_crm_repo.list_deals.return_value = []
        await svc.list_deals("p1", include_inactive=True)
        mock_crm_repo.list_deals.assert_called_once_with("p1", True)


# ── create_activity ────────────────────────────────────────────────────

class TestCreateActivity:
    @pytest.mark.asyncio
    async def test_is_not_system(self, svc, mock_crm_repo):
        mock_crm_repo.create_activity.return_value = MagicMock()

        await svc.create_activity(
            "p1", "d1",
            {"summary": "電話討論需求", "activity_type": "電話"}
        )

        created = mock_crm_repo.create_activity.call_args[0][0]
        assert created.is_system is False
        assert created.deal_id == "d1"
        assert created.partner_id == "p1"
        assert created.summary == "電話討論需求"

    @pytest.mark.asyncio
    async def test_default_type_is_note(self, svc, mock_crm_repo):
        mock_crm_repo.create_activity.return_value = MagicMock()

        await svc.create_activity("p1", "d1", {"summary": "備忘事項"})

        created = mock_crm_repo.create_activity.call_args[0][0]
        assert created.activity_type == ActivityType.NOTE
