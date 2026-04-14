"""Tests for CrmInsightsService — pure unit tests using mock CRM repository.

All tests use mock repos so they run without a DB connection.
The computation logic in crm_insights_service.py is the primary subject.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from zenos.application.crm.crm_insights_service import (
    DEFAULT_THRESHOLDS,
    CrmInsightsService,
    _compute_pipeline_summary,
    _compute_stale_warnings,
    _days_since,
    _is_active,
    _reference_date,
)
from zenos.domain.crm_models import Deal, FunnelStage


# ── Test helpers ───────────────────────────────────────────────────────

_NOW = datetime(2026, 4, 14, 12, 0, 0, tzinfo=timezone.utc)


def _dt(days_ago: int) -> datetime:
    """Return a timezone-aware datetime N days before _NOW."""
    return _NOW - timedelta(days=days_ago)


def _make_deal(**kwargs) -> Deal:
    defaults = dict(
        id="d1",
        partner_id="p1",
        title="AI 導入案",
        company_id="c1",
        owner_partner_id="p1",
        funnel_stage=FunnelStage.PROSPECT,
        is_closed_lost=False,
        is_on_hold=False,
        last_activity_at=None,
        created_at=_dt(5),
        updated_at=_dt(5),
    )
    defaults.update(kwargs)
    return Deal(**defaults)


def _make_insights_service(deals=None, setting=None, companies=None) -> CrmInsightsService:
    """Build a CrmInsightsService backed by a mock CRM repo."""
    repo = MagicMock()
    repo.list_deals = AsyncMock(return_value=deals or [])
    repo.list_companies = AsyncMock(return_value=companies or [])
    repo.get_setting = AsyncMock(return_value=setting)
    repo.upsert_setting = AsyncMock()
    return CrmInsightsService(repo)


# ── _days_since ────────────────────────────────────────────────────────

class TestDaysSince:
    def test_exact_days(self):
        past = _NOW - timedelta(days=10)
        assert _days_since(past, _NOW) == 10

    def test_zero_when_same_time(self):
        assert _days_since(_NOW, _NOW) == 0

    def test_naive_datetime_treated_as_utc(self):
        naive_past = datetime(2026, 4, 4, 12, 0, 0)  # 10 days ago, no tz
        result = _days_since(naive_past, _NOW)
        assert result == 10

    def test_never_negative(self):
        future = _NOW + timedelta(days=1)
        assert _days_since(future, _NOW) == 0


# ── _reference_date ────────────────────────────────────────────────────

class TestReferenceDate:
    def test_uses_last_activity_at_when_present(self):
        deal = _make_deal(last_activity_at=_dt(3), created_at=_dt(20))
        assert _reference_date(deal) == _dt(3)

    def test_falls_back_to_created_at_when_no_activity(self):
        deal = _make_deal(last_activity_at=None, created_at=_dt(20))
        assert _reference_date(deal) == _dt(20)


# ── _is_active ─────────────────────────────────────────────────────────

class TestIsActive:
    def test_active_deal_is_active(self):
        deal = _make_deal(funnel_stage=FunnelStage.PROPOSAL)
        assert _is_active(deal) is True

    def test_closed_lost_is_not_active(self):
        deal = _make_deal(is_closed_lost=True)
        assert _is_active(deal) is False

    def test_on_hold_is_not_active(self):
        deal = _make_deal(is_on_hold=True)
        assert _is_active(deal) is False

    def test_closed_won_stage_is_not_active(self):
        deal = _make_deal(funnel_stage=FunnelStage.CLOSED_WON)
        assert _is_active(deal) is False

    def test_prospect_is_active(self):
        deal = _make_deal(funnel_stage=FunnelStage.PROSPECT)
        assert _is_active(deal) is True


# ── _compute_stale_warnings ────────────────────────────────────────────

class TestComputeStaleWarnings:
    def test_empty_deals_returns_empty(self):
        result = _compute_stale_warnings([], DEFAULT_THRESHOLDS, _NOW)
        assert result == []

    def test_deal_within_threshold_not_flagged(self):
        # Prospect threshold=7; deal is 5 days stale → not stale
        deal = _make_deal(
            funnel_stage=FunnelStage.PROSPECT,
            last_activity_at=_dt(5),
        )
        result = _compute_stale_warnings([deal], DEFAULT_THRESHOLDS, _NOW)
        assert result == []

    def test_deal_exactly_at_threshold_not_flagged(self):
        # Prospect threshold=7; exactly 7 days → not stale (must exceed)
        deal = _make_deal(
            funnel_stage=FunnelStage.PROSPECT,
            last_activity_at=_dt(7),
        )
        result = _compute_stale_warnings([deal], DEFAULT_THRESHOLDS, _NOW)
        assert result == []

    def test_deal_exceeds_threshold_flagged(self):
        # Prospect threshold=7; 8 days stale → stale
        deal = _make_deal(
            id="d1",
            title="AI 導入案",
            funnel_stage=FunnelStage.PROSPECT,
            last_activity_at=_dt(8),
        )
        result = _compute_stale_warnings([deal], DEFAULT_THRESHOLDS, _NOW)
        assert len(result) == 1
        w = result[0]
        assert w["type"] == "stale_warning"
        assert w["deal_id"] == "d1"
        assert w["deal_title"] == "AI 導入案"
        assert w["days_stale"] == 8
        assert w["threshold_days"] == 7
        assert w["stage"] == "潛在客戶"
        assert "接觸" in w["suggestion"]

    def test_closed_lost_deal_excluded(self):
        deal = _make_deal(
            is_closed_lost=True,
            funnel_stage=FunnelStage.PROSPECT,
            last_activity_at=_dt(30),
        )
        result = _compute_stale_warnings([deal], DEFAULT_THRESHOLDS, _NOW)
        assert result == []

    def test_on_hold_deal_excluded(self):
        deal = _make_deal(
            is_on_hold=True,
            funnel_stage=FunnelStage.PROSPECT,
            last_activity_at=_dt(30),
        )
        result = _compute_stale_warnings([deal], DEFAULT_THRESHOLDS, _NOW)
        assert result == []

    def test_closed_won_stage_excluded(self):
        deal = _make_deal(
            funnel_stage=FunnelStage.CLOSED_WON,
            last_activity_at=_dt(30),
        )
        result = _compute_stale_warnings([deal], DEFAULT_THRESHOLDS, _NOW)
        assert result == []

    def test_uses_created_at_when_no_activity(self):
        # Deal created 20 days ago, no activities → stale vs prospect threshold 7
        deal = _make_deal(
            funnel_stage=FunnelStage.PROSPECT,
            last_activity_at=None,
            created_at=_dt(20),
        )
        result = _compute_stale_warnings([deal], DEFAULT_THRESHOLDS, _NOW)
        assert len(result) == 1
        assert result[0]["days_stale"] == 20

    def test_sorted_by_urgency_ratio_descending(self):
        # d1: 8 days stale vs threshold 7 → ratio 8/7 ≈ 1.14
        # d2: 20 days stale vs threshold 14 (proposal) → ratio 20/14 ≈ 1.43
        # d2 should come first
        d1 = _make_deal(
            id="d1", title="Deal1",
            funnel_stage=FunnelStage.PROSPECT,
            last_activity_at=_dt(8),
        )
        d2 = _make_deal(
            id="d2", title="Deal2",
            funnel_stage=FunnelStage.PROPOSAL,
            last_activity_at=_dt(20),
        )
        result = _compute_stale_warnings([d1, d2], DEFAULT_THRESHOLDS, _NOW)
        assert len(result) == 2
        assert result[0]["deal_id"] == "d2"
        assert result[1]["deal_id"] == "d1"

    def test_custom_thresholds_applied(self):
        # Override prospect threshold to 5 days
        custom = {**DEFAULT_THRESHOLDS, "潛在客戶": 5}
        deal = _make_deal(
            funnel_stage=FunnelStage.PROSPECT,
            last_activity_at=_dt(6),  # would not trigger at default 7, triggers at 5
        )
        result = _compute_stale_warnings([deal], custom, _NOW)
        assert len(result) == 1
        assert result[0]["threshold_days"] == 5

    def test_each_stage_has_correct_threshold(self):
        """Verify all active funnel stages use their correct default threshold."""
        stage_day_map = [
            (FunnelStage.PROSPECT, 8),       # threshold 7
            (FunnelStage.DISCOVERY, 11),      # threshold 10
            (FunnelStage.PROPOSAL, 15),       # threshold 14
            (FunnelStage.NEGOTIATION, 15),    # threshold 14
            (FunnelStage.ONBOARDING, 22),     # threshold 21
        ]
        for stage, days_stale in stage_day_map:
            deal = _make_deal(
                id=f"deal-{stage.value}",
                funnel_stage=stage,
                last_activity_at=_dt(days_stale),
            )
            result = _compute_stale_warnings([deal], DEFAULT_THRESHOLDS, _NOW)
            assert len(result) == 1, f"Stage {stage.value} should trigger at {days_stale} days"
            assert result[0]["threshold_days"] == DEFAULT_THRESHOLDS[stage.value]


# ── _compute_pipeline_summary ──────────────────────────────────────────

class TestComputePipelineSummary:
    def test_empty_deals_returns_zero_summary(self):
        result = _compute_pipeline_summary([], [], _NOW)
        assert result["active_deals"] == 0
        assert result["estimated_monthly_close_twd"] == 0
        assert result["deals_needing_attention"] == 0

    def test_counts_active_deals(self):
        deals = [
            _make_deal(id="d1", funnel_stage=FunnelStage.PROSPECT),
            _make_deal(id="d2", funnel_stage=FunnelStage.PROPOSAL),
            _make_deal(id="d3", is_closed_lost=True),    # excluded
            _make_deal(id="d4", is_on_hold=True),         # excluded
            _make_deal(id="d5", funnel_stage=FunnelStage.CLOSED_WON),  # excluded
        ]
        result = _compute_pipeline_summary(deals, [], _NOW)
        assert result["active_deals"] == 2

    def test_monthly_close_sums_this_month_only(self):
        this_month = date(_NOW.year, _NOW.month, 15)
        next_month_date = date(_NOW.year, _NOW.month + 1, 15) if _NOW.month < 12 else date(_NOW.year + 1, 1, 15)

        deals = [
            _make_deal(id="d1", funnel_stage=FunnelStage.PROPOSAL,
                       amount_twd=500000, expected_close_date=this_month),
            _make_deal(id="d2", funnel_stage=FunnelStage.PROSPECT,
                       amount_twd=300000, expected_close_date=this_month),
            _make_deal(id="d3", funnel_stage=FunnelStage.NEGOTIATION,
                       amount_twd=200000, expected_close_date=next_month_date),
        ]
        result = _compute_pipeline_summary(deals, [], _NOW)
        assert result["estimated_monthly_close_twd"] == 800000

    def test_deals_needing_attention_matches_insights_count(self):
        insights = [{"type": "stale_warning", "deal_id": "d1"}, {"type": "stale_warning", "deal_id": "d2"}]
        result = _compute_pipeline_summary([], insights, _NOW)
        assert result["deals_needing_attention"] == 2

    def test_deals_with_no_amount_treated_as_zero(self):
        this_month = date(_NOW.year, _NOW.month, 10)
        deal = _make_deal(id="d1", funnel_stage=FunnelStage.PROPOSAL,
                          amount_twd=None, expected_close_date=this_month)
        result = _compute_pipeline_summary([deal], [], _NOW)
        assert result["estimated_monthly_close_twd"] == 0

    def test_closed_lost_not_counted_in_monthly_estimate(self):
        this_month = date(_NOW.year, _NOW.month, 10)
        deal = _make_deal(
            id="d1", funnel_stage=FunnelStage.PROPOSAL,
            amount_twd=1000000, expected_close_date=this_month,
            is_closed_lost=True,
        )
        result = _compute_pipeline_summary([deal], [], _NOW)
        assert result["estimated_monthly_close_twd"] == 0


# ── CrmInsightsService ─────────────────────────────────────────────────

class TestCrmInsightsService:
    @pytest.mark.asyncio
    async def test_compute_insights_no_deals_returns_empty(self):
        svc = _make_insights_service(deals=[])
        result = await svc.compute_insights("p1", _now=_NOW)
        assert result["insights"] == []
        assert result["pipeline_summary"]["active_deals"] == 0
        assert result["pipeline_summary"]["estimated_monthly_close_twd"] == 0
        assert result["pipeline_summary"]["deals_needing_attention"] == 0

    @pytest.mark.asyncio
    async def test_compute_insights_stale_deal_produces_warning(self):
        deal = _make_deal(
            id="d1", title="AI 導入案",
            funnel_stage=FunnelStage.PROPOSAL,
            last_activity_at=_dt(20),  # 20 days > threshold 14
        )
        svc = _make_insights_service(deals=[deal])
        result = await svc.compute_insights("p1", _now=_NOW)
        assert len(result["insights"]) == 1
        w = result["insights"][0]
        assert w["type"] == "stale_warning"
        assert w["deal_id"] == "d1"
        assert w["days_stale"] == 20
        assert w["threshold_days"] == 14

    @pytest.mark.asyncio
    async def test_compute_insights_excludes_closed_lost(self):
        deal = _make_deal(
            funnel_stage=FunnelStage.PROSPECT,
            is_closed_lost=True,
            last_activity_at=_dt(30),
        )
        svc = _make_insights_service(deals=[deal])
        result = await svc.compute_insights("p1", _now=_NOW)
        assert result["insights"] == []

    @pytest.mark.asyncio
    async def test_compute_insights_excludes_on_hold(self):
        deal = _make_deal(
            funnel_stage=FunnelStage.PROSPECT,
            is_on_hold=True,
            last_activity_at=_dt(30),
        )
        svc = _make_insights_service(deals=[deal])
        result = await svc.compute_insights("p1", _now=_NOW)
        assert result["insights"] == []

    @pytest.mark.asyncio
    async def test_get_stale_thresholds_returns_defaults_when_no_db_row(self):
        svc = _make_insights_service()  # get_setting returns None
        thresholds = await svc.get_stale_thresholds("p1")
        assert thresholds == DEFAULT_THRESHOLDS

    @pytest.mark.asyncio
    async def test_get_stale_thresholds_merges_db_over_defaults(self):
        stored = {"潛在客戶": 3}  # override only one stage
        svc = _make_insights_service(setting=stored)
        thresholds = await svc.get_stale_thresholds("p1")
        assert thresholds["潛在客戶"] == 3
        # Other stages should still use defaults
        assert thresholds["需求訪談"] == DEFAULT_THRESHOLDS["需求訪談"]

    @pytest.mark.asyncio
    async def test_save_stale_thresholds_calls_upsert(self):
        svc = _make_insights_service()
        await svc.save_stale_thresholds("p1", {"潛在客戶": 5})
        svc._crm.upsert_setting.assert_called_once_with("p1", "stale_thresholds", {"潛在客戶": 5})

    @pytest.mark.asyncio
    async def test_custom_threshold_used_in_compute(self):
        """After saving a custom threshold, compute_insights uses it."""
        deal = _make_deal(
            funnel_stage=FunnelStage.PROSPECT,
            last_activity_at=_dt(6),  # default threshold 7 → not stale, custom 5 → stale
        )
        # Simulate DB already has custom threshold stored
        svc = _make_insights_service(deals=[deal], setting={"潛在客戶": 5})
        result = await svc.compute_insights("p1", _now=_NOW)
        assert len(result["insights"]) == 1
        assert result["insights"][0]["threshold_days"] == 5

    @pytest.mark.asyncio
    async def test_pipeline_summary_active_deals_count(self):
        deals = [
            _make_deal(id="d1", funnel_stage=FunnelStage.PROSPECT, last_activity_at=_dt(2)),
            _make_deal(id="d2", funnel_stage=FunnelStage.PROPOSAL, last_activity_at=_dt(2)),
            _make_deal(id="d3", is_closed_lost=True),
        ]
        svc = _make_insights_service(deals=deals)
        result = await svc.compute_insights("p1", _now=_NOW)
        assert result["pipeline_summary"]["active_deals"] == 2

    @pytest.mark.asyncio
    async def test_company_name_enriched_in_stale_warning(self):
        """Stale warning insights include company_name from companies lookup."""
        from zenos.domain.crm_models import Company

        deal = _make_deal(
            id="d1", company_id="c1",
            funnel_stage=FunnelStage.PROPOSAL,
            last_activity_at=_dt(20),
        )
        company = Company(id="c1", partner_id="p1", name="雅云行銷公司")
        svc = _make_insights_service(deals=[deal], companies=[company])
        result = await svc.compute_insights("p1", _now=_NOW)
        assert len(result["insights"]) == 1
        assert result["insights"][0]["company_name"] == "雅云行銷公司"

    @pytest.mark.asyncio
    async def test_company_name_none_when_company_not_found(self):
        """company_name is None if company lookup fails to find the company."""
        deal = _make_deal(
            id="d1", company_id="c-unknown",
            funnel_stage=FunnelStage.PROPOSAL,
            last_activity_at=_dt(20),
        )
        svc = _make_insights_service(deals=[deal], companies=[])
        result = await svc.compute_insights("p1", _now=_NOW)
        assert len(result["insights"]) == 1
        assert result["insights"][0]["company_name"] is None

    @pytest.mark.asyncio
    async def test_get_setting_exception_falls_back_to_defaults(self):
        """If DB access fails during threshold fetch, defaults are returned (no crash)."""
        repo = MagicMock()
        repo.list_deals = AsyncMock(return_value=[])
        repo.list_companies = AsyncMock(return_value=[])
        repo.get_setting = AsyncMock(side_effect=Exception("DB error"))
        repo.upsert_setting = AsyncMock()
        svc = CrmInsightsService(repo)

        thresholds = await svc.get_stale_thresholds("p1")
        assert thresholds == DEFAULT_THRESHOLDS
