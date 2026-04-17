"""Tests for CrmService — uses mock repositories to verify business logic."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, call

import pytest

from zenos.application.crm.crm_service import CrmService
from zenos.domain.crm_models import (
    Activity,
    ActivityType,
    Company,
    Contact,
    Deal,
    FunnelStage,
)
from zenos.domain.knowledge import Entity, Relationship


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
    from zenos.domain.knowledge import Tags
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
    repo.create_ai_insight = AsyncMock()
    repo.get_ai_insight = AsyncMock()
    repo.update_ai_insight = AsyncMock()
    repo.list_ai_insights_by_deal = AsyncMock()
    repo.update_ai_insight_status = AsyncMock()
    repo.delete_ai_insight = AsyncMock()
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


# ── create_deal ────────────────────────────────────────────────────────

class TestCreateDeal:
    @pytest.mark.asyncio
    async def test_calls_crm_repo_create(self, svc, mock_crm_repo, mock_entity_repo, mock_rel_repo):
        deal = _make_deal()
        entity = _make_entity(id="deal-entity-1", type="deal", name="AI 導入案")
        company = _make_company(zenos_entity_id="company-entity-1")
        mock_crm_repo.create_deal.return_value = deal
        mock_entity_repo.upsert.return_value = entity
        mock_crm_repo.get_company.return_value = company
        mock_crm_repo.update_deal.return_value = deal

        await svc.create_deal("p1", {"title": "AI 導入案", "company_id": "c1"})

        mock_crm_repo.create_deal.assert_called_once()
        created_deal = mock_crm_repo.create_deal.call_args[0][0]
        assert created_deal.title == "AI 導入案"
        assert created_deal.partner_id == "p1"

    @pytest.mark.asyncio
    async def test_triggers_entity_upsert_with_type_deal(
        self, svc, mock_crm_repo, mock_entity_repo, mock_rel_repo
    ):
        deal = _make_deal()
        entity = _make_entity(id="deal-entity-1", type="deal", name="AI 導入案")
        company = _make_company(zenos_entity_id="company-entity-1")
        mock_crm_repo.create_deal.return_value = deal
        mock_entity_repo.upsert.return_value = entity
        mock_crm_repo.get_company.return_value = company
        mock_crm_repo.update_deal.return_value = deal

        await svc.create_deal("p1", {"title": "AI 導入案", "company_id": "c1"})

        mock_entity_repo.upsert.assert_called_once()
        upserted = mock_entity_repo.upsert.call_args[0][0]
        assert upserted.type == "deal"
        assert upserted.name == "AI 導入案"
        assert upserted.level == 1

    @pytest.mark.asyncio
    async def test_triggers_relationship_part_of_to_company(
        self, svc, mock_crm_repo, mock_entity_repo, mock_rel_repo
    ):
        deal = _make_deal()
        entity = _make_entity(id="deal-entity-1", type="deal")
        company = _make_company(zenos_entity_id="company-entity-1")
        mock_crm_repo.create_deal.return_value = deal
        mock_entity_repo.upsert.return_value = entity
        mock_crm_repo.get_company.return_value = company
        mock_crm_repo.update_deal.return_value = deal

        await svc.create_deal("p1", {"title": "AI 導入案", "company_id": "c1"})

        mock_rel_repo.add.assert_called_once()
        relationship = mock_rel_repo.add.call_args[0][0]
        assert relationship.source_entity_id == "deal-entity-1"
        assert relationship.target_id == "company-entity-1"
        assert relationship.type == "part_of"

    @pytest.mark.asyncio
    async def test_no_relationship_when_company_has_no_entity(
        self, svc, mock_crm_repo, mock_entity_repo, mock_rel_repo
    ):
        deal = _make_deal()
        entity = _make_entity(id="deal-entity-1", type="deal")
        company = _make_company(zenos_entity_id=None)  # no entity bridge
        mock_crm_repo.create_deal.return_value = deal
        mock_entity_repo.upsert.return_value = entity
        mock_crm_repo.get_company.return_value = company
        mock_crm_repo.update_deal.return_value = deal

        await svc.create_deal("p1", {"title": "AI 導入案", "company_id": "c1"})

        mock_rel_repo.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_backfills_zenos_entity_id(
        self, svc, mock_crm_repo, mock_entity_repo, mock_rel_repo
    ):
        deal = _make_deal()
        entity = _make_entity(id="deal-entity-xyz", type="deal")
        company = _make_company(zenos_entity_id="company-entity-1")
        mock_crm_repo.create_deal.return_value = deal
        mock_entity_repo.upsert.return_value = entity
        mock_crm_repo.get_company.return_value = company
        mock_crm_repo.update_deal.return_value = deal

        result = await svc.create_deal("p1", {"title": "AI 導入案", "company_id": "c1"})

        mock_crm_repo.update_deal.assert_called_once()
        updated = mock_crm_repo.update_deal.call_args[0][0]
        assert updated.zenos_entity_id == "deal-entity-xyz"

    @pytest.mark.asyncio
    async def test_entity_summary_includes_stage_and_amount(
        self, svc, mock_crm_repo, mock_entity_repo, mock_rel_repo
    ):
        deal = _make_deal(funnel_stage=FunnelStage.PROPOSAL, amount_twd=500000)
        entity = _make_entity(id="deal-entity-1", type="deal")
        company = _make_company(zenos_entity_id="company-entity-1")
        mock_crm_repo.create_deal.return_value = deal
        mock_entity_repo.upsert.return_value = entity
        mock_crm_repo.get_company.return_value = company
        mock_crm_repo.update_deal.return_value = deal

        await svc.create_deal(
            "p1",
            {"title": "AI 導入案", "company_id": "c1",
             "funnel_stage": "提案報價", "amount_twd": 500000},
        )

        upserted = mock_entity_repo.upsert.call_args[0][0]
        assert "提案報價" in upserted.summary
        assert "500,000" in upserted.summary

    @pytest.mark.asyncio
    async def test_entity_summary_handles_no_amount(
        self, svc, mock_crm_repo, mock_entity_repo, mock_rel_repo
    ):
        deal = _make_deal(amount_twd=None)
        entity = _make_entity(id="deal-entity-1", type="deal")
        company = _make_company(zenos_entity_id="company-entity-1")
        mock_crm_repo.create_deal.return_value = deal
        mock_entity_repo.upsert.return_value = entity
        mock_crm_repo.get_company.return_value = company
        mock_crm_repo.update_deal.return_value = deal

        await svc.create_deal("p1", {"title": "AI 導入案", "company_id": "c1"})

        upserted = mock_entity_repo.upsert.call_args[0][0]
        assert "金額未定" in upserted.summary

    @pytest.mark.asyncio
    async def test_entity_details_include_initial_crm_snapshot(
        self, svc, mock_crm_repo, mock_entity_repo, mock_rel_repo
    ):
        deal = _make_deal(funnel_stage=FunnelStage.DISCOVERY, amount_twd=300000)
        entity = _make_entity(id="deal-entity-1", type="deal")
        company = _make_company(zenos_entity_id="company-entity-1")
        mock_crm_repo.create_deal.return_value = deal
        mock_entity_repo.upsert.return_value = entity
        mock_crm_repo.get_company.return_value = company
        mock_crm_repo.update_deal.return_value = deal

        await svc.create_deal(
            "p1",
            {"title": "AI 導入案", "company_id": "c1", "funnel_stage": "需求訪談", "amount_twd": 300000},
        )

        upserted = mock_entity_repo.upsert.call_args[0][0]
        snapshot = upserted.details["crm_snapshot"]
        assert snapshot["funnel_stage"] == "需求訪談"
        assert snapshot["amount_twd"] == 300000
        assert snapshot["open_commitments_count"] == 0


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

    @pytest.mark.asyncio
    async def test_syncs_linked_deal_entity_projection(self, svc, mock_crm_repo, mock_entity_repo):
        deal = _make_deal(
            funnel_stage=FunnelStage.PROSPECT,
            amount_twd=500000,
            zenos_entity_id="deal-entity-1",
        )
        mock_crm_repo.get_deal.return_value = deal
        mock_crm_repo.update_deal.return_value = deal
        mock_crm_repo.create_activity.return_value = MagicMock()
        mock_crm_repo.list_activities.return_value = []
        mock_crm_repo.list_ai_insights_by_deal.return_value = []
        mock_entity_repo.get_by_id.return_value = _make_entity(
            id="deal-entity-1",
            type="deal",
            name="舊標題",
            details={"existing": "keep"},
        )

        await svc.update_deal_stage("p1", "d1", "需求訪談", "p1")

        synced = mock_entity_repo.upsert.call_args[0][0]
        assert synced.name == "AI 導入案"
        assert synced.summary.startswith("需求訪談 · NT$500,000")
        assert synced.details["existing"] == "keep"
        assert synced.details["crm_snapshot"]["funnel_stage"] == "需求訪談"


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

    @pytest.mark.asyncio
    async def test_syncs_linked_deal_projection_last_activity_at(
        self, svc, mock_crm_repo, mock_entity_repo
    ):
        activity_at = datetime(2026, 4, 15, 9, 30, tzinfo=timezone.utc)
        created_activity = Activity(
            id="act-1",
            partner_id="p1",
            deal_id="d1",
            activity_type=ActivityType.MEETING,
            activity_at=activity_at,
            summary="會議摘要",
            recorded_by="p1",
            is_system=False,
        )
        mock_crm_repo.create_activity.return_value = created_activity
        mock_crm_repo.get_deal.return_value = _make_deal(
            zenos_entity_id="deal-entity-1",
            funnel_stage=FunnelStage.DISCOVERY,
        )
        mock_crm_repo.list_activities.return_value = [created_activity]
        mock_crm_repo.list_ai_insights_by_deal.return_value = []
        mock_entity_repo.get_by_id.return_value = _make_entity(
            id="deal-entity-1",
            type="deal",
            details={},
        )

        await svc.create_activity(
            "p1",
            "d1",
            {"summary": "會議摘要", "activity_type": "會議", "activity_at": activity_at.isoformat()},
        )

        synced = mock_entity_repo.upsert.call_args[0][0]
        assert synced.details["crm_snapshot"]["last_activity_at"] == activity_at.isoformat()
