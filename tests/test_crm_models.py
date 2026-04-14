"""Tests for CRM domain models — enum validation and dataclass construction."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from zenos.domain.crm_models import (
    Activity,
    ActivityType,
    Company,
    Contact,
    Deal,
    DealSource,
    DealType,
    FunnelStage,
)


# ── FunnelStage ────────────────────────────────────────────────────────

class TestFunnelStage:
    def test_all_values_defined(self):
        stages = [s.value for s in FunnelStage]
        assert "潛在客戶" in stages
        assert "需求訪談" in stages
        assert "提案報價" in stages
        assert "合約議價" in stages
        assert "導入中" in stages
        assert "結案" in stages

    def test_is_str_enum(self):
        assert isinstance(FunnelStage.PROSPECT, str)
        assert FunnelStage.PROSPECT == "潛在客戶"

    def test_from_value(self):
        stage = FunnelStage("提案報價")
        assert stage == FunnelStage.PROPOSAL

    def test_invalid_value_raises(self):
        with pytest.raises(ValueError):
            FunnelStage("不存在的階段")


# ── DealType ───────────────────────────────────────────────────────────

class TestDealType:
    def test_all_values(self):
        values = {dt.value for dt in DealType}
        assert "一次性專案" in values
        assert "顧問合約" in values
        assert "Retainer" in values

    def test_str_enum(self):
        assert DealType.ONE_TIME == "一次性專案"


# ── DealSource ─────────────────────────────────────────────────────────

class TestDealSource:
    def test_all_values(self):
        values = {ds.value for ds in DealSource}
        assert "轉介紹" in values
        assert "自開發" in values
        assert "合作夥伴" in values
        assert "社群" in values
        assert "活動" in values


# ── ActivityType ───────────────────────────────────────────────────────

class TestActivityType:
    def test_all_values(self):
        values = {at.value for at in ActivityType}
        assert "電話" in values
        assert "Email" in values
        assert "會議" in values
        assert "Demo" in values
        assert "備忘" in values
        assert "系統" in values

    def test_system_type(self):
        assert ActivityType.SYSTEM == "系統"


# ── Company dataclass ──────────────────────────────────────────────────

class TestCompany:
    def test_minimal_construction(self):
        company = Company(id="c1", partner_id="p1", name="台灣科技股份有限公司")
        assert company.id == "c1"
        assert company.partner_id == "p1"
        assert company.name == "台灣科技股份有限公司"
        assert company.industry is None
        assert company.zenos_entity_id is None

    def test_full_construction(self):
        company = Company(
            id="c1",
            partner_id="p1",
            name="測試公司",
            industry="科技",
            size_range="11-50",
            region="台北",
            notes="測試備忘",
            zenos_entity_id="e123",
        )
        assert company.industry == "科技"
        assert company.size_range == "11-50"
        assert company.region == "台北"
        assert company.zenos_entity_id == "e123"

    def test_default_timestamps_are_aware(self):
        company = Company(id="c1", partner_id="p1", name="Test")
        assert company.created_at.tzinfo is not None
        assert company.updated_at.tzinfo is not None


# ── Contact dataclass ──────────────────────────────────────────────────

class TestContact:
    def test_minimal_construction(self):
        contact = Contact(id="ct1", partner_id="p1", company_id="c1", name="王小明")
        assert contact.id == "ct1"
        assert contact.company_id == "c1"
        assert contact.title is None
        assert contact.zenos_entity_id is None

    def test_full_construction(self):
        contact = Contact(
            id="ct1",
            partner_id="p1",
            company_id="c1",
            name="王小明",
            title="CTO",
            email="wang@example.com",
            phone="0912345678",
        )
        assert contact.title == "CTO"
        assert contact.email == "wang@example.com"


# ── Deal dataclass ─────────────────────────────────────────────────────

class TestDeal:
    def test_minimal_construction(self):
        deal = Deal(
            id="d1",
            partner_id="p1",
            title="AI 導入顧問案",
            company_id="c1",
            owner_partner_id="p1",
        )
        assert deal.funnel_stage == FunnelStage.PROSPECT
        assert deal.is_closed_lost is False
        assert deal.is_on_hold is False
        assert deal.deliverables == []
        assert deal.zenos_entity_id is None  # default: bridge not yet created

    def test_with_stage(self):
        deal = Deal(
            id="d1",
            partner_id="p1",
            title="Test Deal",
            company_id="c1",
            owner_partner_id="p1",
            funnel_stage=FunnelStage.PROPOSAL,
        )
        assert deal.funnel_stage == FunnelStage.PROPOSAL
        assert deal.funnel_stage.value == "提案報價"

    def test_inactive_flags(self):
        deal = Deal(
            id="d1",
            partner_id="p1",
            title="Lost Deal",
            company_id="c1",
            owner_partner_id="p1",
            is_closed_lost=True,
        )
        assert deal.is_closed_lost is True


# ── Activity dataclass ─────────────────────────────────────────────────

class TestActivity:
    def test_construction(self):
        now = datetime.now(timezone.utc)
        activity = Activity(
            id="a1",
            partner_id="p1",
            deal_id="d1",
            activity_type=ActivityType.MEETING,
            activity_at=now,
            summary="初次拜訪，討論需求",
            recorded_by="p1",
        )
        assert activity.is_system is False
        assert activity.activity_type == ActivityType.MEETING

    def test_system_activity(self):
        now = datetime.now(timezone.utc)
        activity = Activity(
            id="a1",
            partner_id="p1",
            deal_id="d1",
            activity_type=ActivityType.SYSTEM,
            activity_at=now,
            summary="階段從「潛在客戶」更新為「需求訪談」",
            recorded_by="p1",
            is_system=True,
        )
        assert activity.is_system is True
        assert activity.activity_type.value == "系統"


# ── EntityType extension ───────────────────────────────────────────────

class TestEntityTypeExtension:
    def test_company_and_person_in_entity_type(self):
        from zenos.domain.knowledge import EntityType
        assert EntityType.COMPANY == "company"
        assert EntityType.PERSON == "person"

    def test_deal_in_entity_type(self):
        from zenos.domain.knowledge import EntityType
        assert EntityType.DEAL == "deal"

    def test_original_types_still_present(self):
        from zenos.domain.knowledge import EntityType
        assert EntityType.PRODUCT == "product"
        assert EntityType.MODULE == "module"
        assert EntityType.DOCUMENT == "document"
