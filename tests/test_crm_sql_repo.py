"""Integration tests for CrmSqlRepository.

These tests require a live Cloud SQL connection and are therefore skipped in
CI. They serve as a blueprint for manual verification and future integration
test runs with a test database.
"""

from __future__ import annotations

from datetime import datetime, timezone

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
