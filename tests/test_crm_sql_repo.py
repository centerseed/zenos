"""Integration tests for CrmSqlRepository.

These tests require a live Cloud SQL connection and are therefore skipped in
CI. They serve as a blueprint for manual verification and future integration
test runs with a test database.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from zenos.domain.crm_models import (
    Activity,
    ActivityType,
    Company,
    Contact,
    Deal,
    FunnelStage,
)


@pytest.mark.skip(reason="requires Cloud SQL")
class TestCrmSqlRepositoryCompanies:
    """Integration tests for company CRUD operations."""

    @pytest.mark.asyncio
    async def test_create_and_get_company(self, pool):
        from zenos.infrastructure.crm_sql_repo import CrmSqlRepository
        repo = CrmSqlRepository(pool)
        company = Company(id="test-c1", partner_id="test-p1", name="整合測試公司", industry="科技")
        created = await repo.create_company(company)
        assert created.id == "test-c1"

        fetched = await repo.get_company("test-p1", "test-c1")
        assert fetched is not None
        assert fetched.name == "整合測試公司"

    @pytest.mark.asyncio
    async def test_update_company(self, pool):
        from zenos.infrastructure.crm_sql_repo import CrmSqlRepository
        repo = CrmSqlRepository(pool)
        company = Company(id="test-c2", partner_id="test-p1", name="舊名稱")
        await repo.create_company(company)

        company.name = "新名稱"
        await repo.update_company(company)

        fetched = await repo.get_company("test-p1", "test-c2")
        assert fetched.name == "新名稱"

    @pytest.mark.asyncio
    async def test_list_companies_filters_by_partner(self, pool):
        from zenos.infrastructure.crm_sql_repo import CrmSqlRepository
        repo = CrmSqlRepository(pool)
        companies_p1 = await repo.list_companies("test-p1")
        companies_p2 = await repo.list_companies("different-partner")
        # Should not cross-contaminate between partners
        p2_ids = {c.id for c in companies_p2}
        for c in companies_p1:
            assert c.id not in p2_ids


@pytest.mark.skip(reason="requires Cloud SQL")
class TestCrmSqlRepositoryDeals:
    """Integration tests for deal CRUD and filtering."""

    @pytest.mark.asyncio
    async def test_list_deals_excludes_inactive_by_default(self, pool):
        from zenos.infrastructure.crm_sql_repo import CrmSqlRepository
        repo = CrmSqlRepository(pool)
        active = await repo.list_deals("test-p1", include_inactive=False)
        for deal in active:
            assert not deal.is_closed_lost
            assert not deal.is_on_hold

    @pytest.mark.asyncio
    async def test_list_deals_includes_inactive_when_requested(self, pool):
        from zenos.infrastructure.crm_sql_repo import CrmSqlRepository
        repo = CrmSqlRepository(pool)
        all_deals = await repo.list_deals("test-p1", include_inactive=True)
        active_deals = await repo.list_deals("test-p1", include_inactive=False)
        assert len(all_deals) >= len(active_deals)


@pytest.mark.skip(reason="requires Cloud SQL")
class TestCrmSqlRepositoryActivities:
    """Integration tests for activity log ordering."""

    @pytest.mark.asyncio
    async def test_list_activities_sorted_desc(self, pool):
        from zenos.infrastructure.crm_sql_repo import CrmSqlRepository
        repo = CrmSqlRepository(pool)
        activities = await repo.list_activities("test-p1", "test-d1")
        for i in range(len(activities) - 1):
            assert activities[i].activity_at >= activities[i + 1].activity_at


def _make_deal_row(overrides: dict) -> dict:
    """Return a minimal deal row dict suitable for _row_to_deal."""
    base = {
        "id": "deal-1",
        "partner_id": "partner-1",
        "title": "Test Deal",
        "company_id": None,
        "owner_partner_id": None,
        "funnel_stage": "prospect",
        "amount_twd": None,
        "deal_type": None,
        "source_type": None,
        "referrer": None,
        "expected_close_date": None,
        "signed_date": None,
        "scope_description": None,
        "deliverables": [],
        "notes": None,
        "is_closed_lost": False,
        "is_on_hold": False,
        "last_activity_at": None,
        "created_at": datetime(2024, 1, 1, tzinfo=timezone.utc),
        "updated_at": datetime(2024, 1, 1, tzinfo=timezone.utc),
    }
    base.update(overrides)
    return base


class TestRowToDealLastActivityAt:
    """Unit tests for _row_to_deal last_activity_at mapping."""

    def test_last_activity_at_mapped_when_present(self):
        from zenos.infrastructure.crm_sql_repo import _row_to_deal

        activity_time = datetime(2024, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        row = _make_deal_row({"last_activity_at": activity_time})
        deal = _row_to_deal(row)

        assert deal.last_activity_at == activity_time

    def test_last_activity_at_is_none_when_no_activities(self):
        from zenos.infrastructure.crm_sql_repo import _row_to_deal

        row = _make_deal_row({"last_activity_at": None})
        deal = _row_to_deal(row)

        assert deal.last_activity_at is None

    def test_last_activity_at_is_none_when_key_missing(self):
        """Row without last_activity_at key (e.g. direct SELECT *) should not crash."""
        from zenos.infrastructure.crm_sql_repo import _row_to_deal

        row = _make_deal_row({})
        # Remove the key to simulate a raw SELECT * row
        row.pop("last_activity_at")
        deal = _row_to_deal(row)

        assert deal.last_activity_at is None


class TestListDealsLastActivityAtSql:
    """Unit tests verifying list_deals SQL includes LEFT JOIN for last_activity_at."""

    @pytest.mark.asyncio
    async def test_list_deals_active_sql_includes_left_join(self):
        """list_deals active branch should query last_activity_at via LEFT JOIN."""
        from zenos.infrastructure.crm_sql_repo import CrmSqlRepository

        activity_time = datetime(2024, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        fake_row = _make_deal_row({"last_activity_at": activity_time})

        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[fake_row])
        mock_pool = MagicMock()
        mock_pool.acquire = MagicMock(return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=mock_conn),
            __aexit__=AsyncMock(return_value=None),
        ))

        repo = CrmSqlRepository(mock_pool)
        deals = await repo.list_deals("partner-1", include_inactive=False)

        assert len(deals) == 1
        assert deals[0].last_activity_at == activity_time

        called_sql = mock_conn.fetch.call_args[0][0].upper()
        assert "LEFT JOIN" in called_sql
        assert "LAST_ACTIVITY_AT" in called_sql

    @pytest.mark.asyncio
    async def test_list_deals_include_inactive_sql_includes_left_join(self):
        """list_deals include_inactive branch should also query last_activity_at."""
        from zenos.infrastructure.crm_sql_repo import CrmSqlRepository

        fake_row = _make_deal_row({"last_activity_at": None})

        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[fake_row])
        mock_pool = MagicMock()
        mock_pool.acquire = MagicMock(return_value=AsyncMock(
            __aenter__=AsyncMock(return_value=mock_conn),
            __aexit__=AsyncMock(return_value=None),
        ))

        repo = CrmSqlRepository(mock_pool)
        deals = await repo.list_deals("partner-1", include_inactive=True)

        assert len(deals) == 1
        assert deals[0].last_activity_at is None

        called_sql = mock_conn.fetch.call_args[0][0].upper()
        assert "LEFT JOIN" in called_sql
        assert "LAST_ACTIVITY_AT" in called_sql
