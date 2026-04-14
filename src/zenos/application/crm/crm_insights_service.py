"""CRM Insights Service — server-side real-time deal health computation.

Computes stale deal warnings and pipeline summary for a given partner.
No results are persisted; every call recalculates from live deal data.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from zenos.domain.crm_models import Deal, FunnelStage

# ── Default stale thresholds (days without activity) ──────────────────

DEFAULT_THRESHOLDS: dict[str, int] = {
    FunnelStage.PROSPECT.value: 7,
    FunnelStage.DISCOVERY.value: 10,
    FunnelStage.PROPOSAL.value: 14,
    FunnelStage.NEGOTIATION.value: 14,
    FunnelStage.ONBOARDING.value: 21,
}

# Suggestion copy keyed by funnel stage value
_SUGGESTIONS: dict[str, str] = {
    FunnelStage.PROSPECT.value: "建議儘快安排初次接觸",
    FunnelStage.DISCOVERY.value: "建議安排下一次需求討論",
    FunnelStage.PROPOSAL.value: "建議主動聯繫確認報價進度",
    FunnelStage.NEGOTIATION.value: "建議跟進合約議價進度",
    FunnelStage.ONBOARDING.value: "建議確認導入進度並回報客戶",
}

# Stages excluded from stale analysis
_EXCLUDED_STAGES = {FunnelStage.CLOSED_WON.value}

SETTINGS_KEY_STALE_THRESHOLDS = "stale_thresholds"


def _days_since(dt: datetime, now: datetime) -> int:
    """Return whole days elapsed since *dt* (floor)."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    delta = now - dt
    return max(0, delta.days)


def _reference_date(deal: Deal) -> datetime:
    """Return the date used to measure staleness: last activity or created_at."""
    if deal.last_activity_at is not None:
        return deal.last_activity_at
    return deal.created_at


def _is_active(deal: Deal) -> bool:
    """Return True if the deal should be considered for stale analysis."""
    if deal.is_closed_lost or deal.is_on_hold:
        return False
    if deal.funnel_stage.value in _EXCLUDED_STAGES:
        return False
    return True


def _compute_stale_warnings(
    deals: list[Deal],
    thresholds: dict[str, int],
    now: datetime,
) -> list[dict[str, Any]]:
    """Return one stale_warning insight per qualifying deal, sorted by urgency."""
    warnings: list[tuple[float, dict[str, Any]]] = []

    for deal in deals:
        if not _is_active(deal):
            continue

        stage_value = deal.funnel_stage.value
        threshold = thresholds.get(stage_value)
        if threshold is None:
            # Stage not in threshold map; skip (e.g., unknown future stage)
            continue

        days_stale = _days_since(_reference_date(deal), now)
        if days_stale <= threshold:
            continue

        urgency_ratio = days_stale / threshold
        warnings.append((urgency_ratio, {
            "type": "stale_warning",
            "deal_id": deal.id,
            "deal_title": deal.title,
            "company_name": None,  # filled by caller if needed; omit for now
            "days_stale": days_stale,
            "stage": stage_value,
            "threshold_days": threshold,
            "suggestion": _SUGGESTIONS.get(stage_value, ""),
        }))

    # Sort by urgency ratio descending (most urgent first)
    warnings.sort(key=lambda t: t[0], reverse=True)
    return [w for _, w in warnings]


def _compute_pipeline_summary(
    deals: list[Deal],
    insights: list[dict[str, Any]],
    now: datetime,
) -> dict[str, Any]:
    """Return pipeline-level aggregate metrics."""
    active_deals = [d for d in deals if _is_active(d)]

    # Monthly close estimate: deals with expected_close_date in current month
    current_month = now.month
    current_year = now.year
    monthly_close_twd = sum(
        (d.amount_twd or 0)
        for d in active_deals
        if d.expected_close_date is not None
        and d.expected_close_date.month == current_month
        and d.expected_close_date.year == current_year
    )

    return {
        "active_deals": len(active_deals),
        "estimated_monthly_close_twd": monthly_close_twd,
        "deals_needing_attention": len(insights),
    }


class CrmInsightsService:
    """Computes deal health insights from live deal data.

    Accepts a repository that knows how to fetch deals and settings.
    All computation is pure / in-memory; nothing is persisted.
    """

    def __init__(self, crm_repo: Any) -> None:
        self._crm = crm_repo

    async def get_stale_thresholds(self, partner_id: str) -> dict[str, int]:
        """Return effective stale thresholds: DB override merged over defaults."""
        try:
            stored = await self._crm.get_setting(partner_id, SETTINGS_KEY_STALE_THRESHOLDS)
        except Exception:
            stored = None

        if stored and isinstance(stored, dict):
            merged = {**DEFAULT_THRESHOLDS, **stored}
            return merged
        return dict(DEFAULT_THRESHOLDS)

    async def save_stale_thresholds(self, partner_id: str, thresholds: dict[str, int]) -> None:
        """Persist custom stale thresholds for a partner."""
        await self._crm.upsert_setting(partner_id, SETTINGS_KEY_STALE_THRESHOLDS, thresholds)

    async def compute_insights(
        self,
        partner_id: str,
        *,
        _now: datetime | None = None,
    ) -> dict[str, Any]:
        """Compute deal health insights for the given partner.

        Returns a dict with 'insights' list and 'pipeline_summary' dict.
        Always succeeds; returns empty insights + zero summary when no deals exist.

        _now is injectable for testing; production callers leave it as None.
        """
        # Fetch all deals including inactive so we can apply our own filters
        deals: list[Deal] = await self._crm.list_deals(partner_id, include_inactive=True)

        # Build company_id → company_name lookup to enrich insights
        company_name_by_id: dict[str, str] = {}
        try:
            companies = await self._crm.list_companies(partner_id)
            company_name_by_id = {c.id: c.name for c in companies}
        except Exception:
            pass  # company name enrichment is best-effort; don't fail insights

        thresholds = await self.get_stale_thresholds(partner_id)
        now = _now if _now is not None else datetime.now(timezone.utc)

        insights = _compute_stale_warnings(deals, thresholds, now)

        # Enrich insights with company name
        for insight in insights:
            deal_id = insight["deal_id"]
            deal = next((d for d in deals if d.id == deal_id), None)
            if deal:
                insight["company_name"] = company_name_by_id.get(deal.company_id)

        pipeline_summary = _compute_pipeline_summary(deals, insights, now)

        return {
            "insights": insights,
            "pipeline_summary": pipeline_summary,
        }
