"""Tests for CRM AI Insights — domain model, repository methods, service, and API endpoints."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from zenos.domain.crm_models import AiInsight, Deal, FunnelStage, InsightStatus, InsightType
from zenos.domain.knowledge import Entity, Tags


# ── Fixtures ───────────────────────────────────────────────────────────


def _make_insight(**kwargs) -> AiInsight:
    defaults = dict(
        id="ins-1",
        partner_id="p1",
        deal_id="d1",
        insight_type=InsightType.DEBRIEF,
        content="Sales debrief content",
        metadata={"source": "meeting"},
        activity_id=None,
        status=InsightStatus.ACTIVE,
        created_at=datetime(2026, 4, 14, 12, 0, 0, tzinfo=timezone.utc),
    )
    defaults.update(kwargs)
    return AiInsight(**defaults)


def _make_deal(**kwargs) -> Deal:
    defaults = dict(
        id="d1",
        partner_id="p1",
        title="企業流程導入",
        company_id="c1",
        owner_partner_id="p1",
        funnel_stage=FunnelStage.DISCOVERY,
        amount_twd=500000,
        zenos_entity_id="deal-entity-1",
    )
    defaults.update(kwargs)
    return Deal(**defaults)


def _make_entity(**kwargs) -> Entity:
    defaults = dict(
        id="deal-entity-1",
        name="企業流程導入",
        type="deal",
        level=1,
        summary="需求訪談 · NT$500,000",
        details={},
        tags=Tags(what=["deal"], why="CRM", how="crm", who=["業務"]),
    )
    defaults.update(kwargs)
    return Entity(**defaults)


@pytest.fixture
def mock_crm_repo():
    repo = MagicMock()
    repo.create_ai_insight = AsyncMock()
    repo.get_ai_insight = AsyncMock()
    repo.update_ai_insight = AsyncMock()
    repo.list_ai_insights_by_deal = AsyncMock()
    repo.update_ai_insight_status = AsyncMock()
    repo.delete_ai_insight = AsyncMock()
    # Existing methods used by CrmService constructor context
    repo.create_company = AsyncMock()
    repo.update_company = AsyncMock()
    repo.get_company = AsyncMock()
    repo.list_companies = AsyncMock()
    repo.create_contact = AsyncMock()
    repo.update_contact = AsyncMock()
    repo.get_contact = AsyncMock()
    repo.list_contacts = AsyncMock()
    repo.create_deal = AsyncMock()
    repo.update_deal = AsyncMock()
    repo.get_deal = AsyncMock()
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
    from zenos.application.crm.crm_service import CrmService
    return CrmService(mock_crm_repo, mock_entity_repo, mock_rel_repo)


# ── Domain model tests ─────────────────────────────────────────────────


class TestAiInsightDomainModel:
    def test_insight_type_enum_values(self):
        assert InsightType.BRIEFING.value == "briefing"
        assert InsightType.DEBRIEF.value == "debrief"
        assert InsightType.COMMITMENT.value == "commitment"

    def test_insight_status_enum_values(self):
        assert InsightStatus.ACTIVE.value == "active"
        assert InsightStatus.OPEN.value == "open"
        assert InsightStatus.DONE.value == "done"
        assert InsightStatus.ARCHIVED.value == "archived"

    def test_ai_insight_default_status_is_active(self):
        insight = AiInsight(
            id="i1", partner_id="p1", deal_id="d1",
            insight_type=InsightType.DEBRIEF,
        )
        assert insight.status == InsightStatus.ACTIVE

    def test_ai_insight_default_content_is_empty(self):
        insight = AiInsight(
            id="i1", partner_id="p1", deal_id="d1",
            insight_type=InsightType.COMMITMENT,
        )
        assert insight.content == ""

    def test_ai_insight_default_metadata_is_empty_dict(self):
        insight = AiInsight(
            id="i1", partner_id="p1", deal_id="d1",
            insight_type=InsightType.BRIEFING,
        )
        assert insight.metadata == {}

    def test_ai_insight_activity_id_optional(self):
        insight = _make_insight(activity_id="act-1")
        assert insight.activity_id == "act-1"

        insight_no_activity = _make_insight(activity_id=None)
        assert insight_no_activity.activity_id is None

    def test_insight_type_str_enum_equality(self):
        # str Enum should compare equal to its string value
        assert InsightType.DEBRIEF == "debrief"
        assert InsightStatus.DONE == "done"


# ── Repository unit tests (mock DB pool) ──────────────────────────────


def _make_mock_pool_with_conn(mock_conn):
    mock_pool = MagicMock()
    mock_pool.acquire = MagicMock(return_value=AsyncMock(
        __aenter__=AsyncMock(return_value=mock_conn),
        __aexit__=AsyncMock(return_value=None),
    ))
    return mock_pool


def _make_insight_row(**overrides) -> dict:
    base = {
        "id": "ins-1",
        "partner_id": "p1",
        "deal_id": "d1",
        "activity_id": None,
        "insight_type": "debrief",
        "content": "Some debrief",
        "metadata": {"source": "meeting"},
        "status": "active",
        "created_at": datetime(2026, 4, 14, 12, 0, 0, tzinfo=timezone.utc),
    }
    base.update(overrides)
    return base


class TestCrmSqlRepositoryAiInsights:
    @pytest.mark.asyncio
    async def test_create_ai_insight_calls_insert(self):
        from zenos.infrastructure.crm_sql_repo import CrmSqlRepository

        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock()
        mock_pool = _make_mock_pool_with_conn(mock_conn)

        repo = CrmSqlRepository(mock_pool)
        insight = _make_insight()
        result = await repo.create_ai_insight(insight)

        mock_conn.execute.assert_called_once()
        sql = mock_conn.execute.call_args[0][0].upper()
        assert "INSERT INTO" in sql
        assert "AI_INSIGHTS" in sql
        assert result is insight

    @pytest.mark.asyncio
    async def test_list_ai_insights_by_deal_no_type_filter(self):
        from zenos.infrastructure.crm_sql_repo import CrmSqlRepository

        row = _make_insight_row()
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[row])
        mock_pool = _make_mock_pool_with_conn(mock_conn)

        repo = CrmSqlRepository(mock_pool)
        results = await repo.list_ai_insights_by_deal("p1", "d1")

        assert len(results) == 1
        assert results[0].insight_type == InsightType.DEBRIEF
        assert results[0].deal_id == "d1"

        sql_args = mock_conn.fetch.call_args[0]
        assert "$1" in sql_args[0] and "$2" in sql_args[0]
        assert sql_args[1] == "p1"
        assert sql_args[2] == "d1"

    @pytest.mark.asyncio
    async def test_list_ai_insights_by_deal_with_type_filter(self):
        from zenos.infrastructure.crm_sql_repo import CrmSqlRepository

        row = _make_insight_row(insight_type="commitment", status="open")
        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[row])
        mock_pool = _make_mock_pool_with_conn(mock_conn)

        repo = CrmSqlRepository(mock_pool)
        results = await repo.list_ai_insights_by_deal("p1", "d1", insight_type="commitment")

        assert len(results) == 1
        assert results[0].insight_type == InsightType.COMMITMENT

        sql_args = mock_conn.fetch.call_args[0]
        assert "$3" in sql_args[0]
        assert sql_args[3] == "commitment"

    @pytest.mark.asyncio
    async def test_list_ai_insights_by_deal_empty_returns_empty_list(self):
        from zenos.infrastructure.crm_sql_repo import CrmSqlRepository

        mock_conn = AsyncMock()
        mock_conn.fetch = AsyncMock(return_value=[])
        mock_pool = _make_mock_pool_with_conn(mock_conn)

        repo = CrmSqlRepository(mock_pool)
        results = await repo.list_ai_insights_by_deal("p1", "no-such-deal")

        assert results == []

    @pytest.mark.asyncio
    async def test_get_ai_insight_returns_single_entry(self):
        from zenos.infrastructure.crm_sql_repo import CrmSqlRepository

        row = _make_insight_row(insight_type="briefing")
        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value=row)
        mock_pool = _make_mock_pool_with_conn(mock_conn)

        repo = CrmSqlRepository(mock_pool)
        result = await repo.get_ai_insight("p1", "ins-1")

        assert result is not None
        assert result.insight_type == InsightType.BRIEFING

    @pytest.mark.asyncio
    async def test_update_ai_insight_updates_content_and_metadata(self):
        from zenos.infrastructure.crm_sql_repo import CrmSqlRepository

        row = _make_insight_row(
            insight_type="briefing",
            content="updated briefing",
            metadata={"title": "會議準備"},
        )
        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value=row)
        mock_pool = _make_mock_pool_with_conn(mock_conn)

        repo = CrmSqlRepository(mock_pool)
        insight = _make_insight(
            insight_type=InsightType.BRIEFING,
            content="updated briefing",
            metadata={"title": "會議準備"},
        )
        result = await repo.update_ai_insight(insight)

        assert result is not None
        assert result.content == "updated briefing"
        assert result.metadata["title"] == "會議準備"

    @pytest.mark.asyncio
    async def test_update_ai_insight_status_returns_updated_insight(self):
        from zenos.infrastructure.crm_sql_repo import CrmSqlRepository

        row = _make_insight_row(status="done")
        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value=row)
        mock_pool = _make_mock_pool_with_conn(mock_conn)

        repo = CrmSqlRepository(mock_pool)
        result = await repo.update_ai_insight_status("p1", "ins-1", "done")

        assert result is not None
        assert result.status == InsightStatus.DONE

        sql_args = mock_conn.fetchrow.call_args[0]
        sql = sql_args[0].upper()
        assert "UPDATE" in sql
        assert "AI_INSIGHTS" in sql
        assert "RETURNING" in sql

    @pytest.mark.asyncio
    async def test_update_ai_insight_status_returns_none_when_not_found(self):
        from zenos.infrastructure.crm_sql_repo import CrmSqlRepository

        mock_conn = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value=None)
        mock_pool = _make_mock_pool_with_conn(mock_conn)

        repo = CrmSqlRepository(mock_pool)
        result = await repo.update_ai_insight_status("p1", "nonexistent", "done")

        assert result is None

    @pytest.mark.asyncio
    async def test_delete_ai_insight_returns_true_when_deleted(self):
        from zenos.infrastructure.crm_sql_repo import CrmSqlRepository

        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value="DELETE 1")
        mock_pool = _make_mock_pool_with_conn(mock_conn)

        repo = CrmSqlRepository(mock_pool)
        assert await repo.delete_ai_insight("p1", "ins-1") is True

    def test_row_to_ai_insight_handles_string_metadata(self):
        """Metadata stored as JSON string (older asyncpg versions) is parsed correctly."""
        import json
        from zenos.infrastructure.crm_sql_repo import CrmSqlRepository

        mock_pool = MagicMock()
        repo = CrmSqlRepository(mock_pool)

        row = _make_insight_row(metadata=json.dumps({"key": "value"}))
        insight = repo._row_to_ai_insight(row)

        assert insight.metadata == {"key": "value"}

    def test_row_to_ai_insight_handles_dict_metadata(self):
        """Metadata already a dict (asyncpg JSONB codec) is passed through."""
        from zenos.infrastructure.crm_sql_repo import CrmSqlRepository

        mock_pool = MagicMock()
        repo = CrmSqlRepository(mock_pool)

        row = _make_insight_row(metadata={"key": "value"})
        insight = repo._row_to_ai_insight(row)

        assert insight.metadata == {"key": "value"}

    def test_row_to_ai_insight_handles_none_metadata(self):
        """None metadata (edge case) defaults to empty dict."""
        from zenos.infrastructure.crm_sql_repo import CrmSqlRepository

        mock_pool = MagicMock()
        repo = CrmSqlRepository(mock_pool)

        row = _make_insight_row(metadata=None)
        insight = repo._row_to_ai_insight(row)

        assert insight.metadata == {}


# ── Service unit tests ─────────────────────────────────────────────────


class TestCrmServiceAiInsights:
    @pytest.mark.asyncio
    async def test_get_deal_ai_entries_categorises_by_type(self, svc, mock_crm_repo):
        briefing = _make_insight(id="i0", insight_type=InsightType.BRIEFING)
        debrief = _make_insight(id="i1", insight_type=InsightType.DEBRIEF)
        commitment = _make_insight(id="i2", insight_type=InsightType.COMMITMENT)
        mock_crm_repo.list_ai_insights_by_deal.return_value = [briefing, debrief, commitment]

        result = await svc.get_deal_ai_entries("p1", "d1")

        assert len(result["briefings"]) == 1
        assert result["briefings"][0].id == "i0"
        assert len(result["debriefs"]) == 1
        assert result["debriefs"][0].id == "i1"
        assert len(result["commitments"]) == 1
        assert result["commitments"][0].id == "i2"

    @pytest.mark.asyncio
    async def test_get_deal_ai_entries_includes_briefings(self, svc, mock_crm_repo):
        briefing = _make_insight(id="i3", insight_type=InsightType.BRIEFING)
        mock_crm_repo.list_ai_insights_by_deal.return_value = [briefing]

        result = await svc.get_deal_ai_entries("p1", "d1")

        assert result["briefings"] == [briefing]
        assert result["debriefs"] == []
        assert result["commitments"] == []

    @pytest.mark.asyncio
    async def test_get_deal_ai_entries_empty(self, svc, mock_crm_repo):
        mock_crm_repo.list_ai_insights_by_deal.return_value = []

        result = await svc.get_deal_ai_entries("p1", "d1")

        assert result == {"briefings": [], "debriefs": [], "commitments": []}

    @pytest.mark.asyncio
    async def test_create_ai_insight_builds_and_calls_repo(self, svc, mock_crm_repo):
        created = _make_insight()
        mock_crm_repo.create_ai_insight.return_value = created

        result = await svc.create_ai_insight("p1", {
            "deal_id": "d1",
            "insight_type": "debrief",
            "content": "Sales debrief",
            "metadata": {"source": "call"},
        })

        mock_crm_repo.create_ai_insight.assert_called_once()
        passed_insight = mock_crm_repo.create_ai_insight.call_args[0][0]
        assert passed_insight.partner_id == "p1"
        assert passed_insight.deal_id == "d1"
        assert passed_insight.insight_type == InsightType.DEBRIEF
        assert passed_insight.content == "Sales debrief"
        assert passed_insight.metadata == {"source": "call"}
        assert passed_insight.status == InsightStatus.ACTIVE
        assert len(passed_insight.id) > 0  # uuid4().hex was called

    @pytest.mark.asyncio
    async def test_create_debrief_syncs_deal_projection(self, svc, mock_crm_repo, mock_entity_repo):
        created = _make_insight(
            insight_type=InsightType.DEBRIEF,
            metadata={
                "next_steps": ["寄報價單"],
                "customer_concerns": ["預算有限"],
            },
        )
        mock_crm_repo.create_ai_insight.return_value = created
        mock_crm_repo.get_deal.return_value = _make_deal()
        mock_crm_repo.list_activities.return_value = []
        mock_crm_repo.list_ai_insights_by_deal.return_value = [created]
        mock_entity_repo.get_by_id.return_value = _make_entity()

        await svc.create_ai_insight("p1", {
            "deal_id": "d1",
            "insight_type": "debrief",
            "content": "Sales debrief",
            "metadata": created.metadata,
        })

        synced = mock_entity_repo.upsert.call_args[0][0]
        snapshot = synced.details["crm_snapshot"]
        assert snapshot["latest_next_step"] == "寄報價單"
        assert snapshot["latest_customer_concerns"] == ["預算有限"]
        assert snapshot["latest_debrief_at"] == created.created_at.isoformat()

    @pytest.mark.asyncio
    async def test_create_ai_insight_sets_activity_id_when_provided(self, svc, mock_crm_repo):
        created = _make_insight(activity_id="act-42")
        mock_crm_repo.create_ai_insight.return_value = created

        await svc.create_ai_insight("p1", {
            "deal_id": "d1",
            "insight_type": "commitment",
            "activity_id": "act-42",
        })

        passed = mock_crm_repo.create_ai_insight.call_args[0][0]
        assert passed.activity_id == "act-42"

    @pytest.mark.asyncio
    async def test_create_commitment_defaults_open_and_syncs_counts(self, svc, mock_crm_repo, mock_entity_repo):
        created = _make_insight(
            id="c1",
            insight_type=InsightType.COMMITMENT,
            status=InsightStatus.OPEN,
            metadata={"content": "提供報價單", "deadline": "2020-01-01"},
        )
        mock_crm_repo.create_ai_insight.return_value = created
        mock_crm_repo.get_deal.return_value = _make_deal()
        mock_crm_repo.list_activities.return_value = []
        mock_crm_repo.list_ai_insights_by_deal.return_value = [created]
        mock_entity_repo.get_by_id.return_value = _make_entity()

        await svc.create_ai_insight("p1", {
            "deal_id": "d1",
            "insight_type": "commitment",
            "content": "提供報價單",
            "metadata": {"content": "提供報價單", "deadline": "2020-01-01"},
        })

        passed = mock_crm_repo.create_ai_insight.call_args[0][0]
        assert passed.status == InsightStatus.OPEN
        synced = mock_entity_repo.upsert.call_args[0][0]
        snapshot = synced.details["crm_snapshot"]
        assert snapshot["open_commitments_count"] == 1
        assert snapshot["overdue_commitments_count"] == 1

    @pytest.mark.asyncio
    async def test_update_commitment_status_allows_open(self, svc, mock_crm_repo):
        updated = _make_insight(status=InsightStatus.OPEN)
        mock_crm_repo.update_ai_insight_status.return_value = updated

        result = await svc.update_commitment_status("p1", "ins-1", "open")

        mock_crm_repo.update_ai_insight_status.assert_called_once_with("p1", "ins-1", "open")
        assert result.status == InsightStatus.OPEN

    @pytest.mark.asyncio
    async def test_update_commitment_status_allows_done(self, svc, mock_crm_repo):
        updated = _make_insight(status=InsightStatus.DONE)
        mock_crm_repo.update_ai_insight_status.return_value = updated

        result = await svc.update_commitment_status("p1", "ins-1", "done")

        mock_crm_repo.update_ai_insight_status.assert_called_once_with("p1", "ins-1", "done")
        assert result.status == InsightStatus.DONE

    @pytest.mark.asyncio
    async def test_update_commitment_status_rejects_invalid_status(self, svc, mock_crm_repo):
        with pytest.raises(ValueError, match="only 'open' and 'done' are allowed"):
            await svc.update_commitment_status("p1", "ins-1", "archived")

        mock_crm_repo.update_ai_insight_status.assert_not_called()

    @pytest.mark.asyncio
    async def test_update_commitment_status_rejects_active(self, svc, mock_crm_repo):
        with pytest.raises(ValueError):
            await svc.update_commitment_status("p1", "ins-1", "active")

    @pytest.mark.asyncio
    async def test_update_commitment_status_returns_none_when_not_found(self, svc, mock_crm_repo):
        mock_crm_repo.update_ai_insight_status.return_value = None

        result = await svc.update_commitment_status("p1", "nonexistent", "done")

        assert result is None

    @pytest.mark.asyncio
    async def test_update_commitment_status_syncs_projection_counts(self, svc, mock_crm_repo, mock_entity_repo):
        updated = _make_insight(
            id="c1",
            insight_type=InsightType.COMMITMENT,
            status=InsightStatus.DONE,
            metadata={"content": "提供報價單", "deadline": "2020-01-01"},
        )
        mock_crm_repo.update_ai_insight_status.return_value = updated
        mock_crm_repo.get_deal.return_value = _make_deal()
        mock_crm_repo.list_activities.return_value = []
        mock_crm_repo.list_ai_insights_by_deal.return_value = [updated]
        mock_entity_repo.get_by_id.return_value = _make_entity()

        await svc.update_commitment_status("p1", "c1", "done")

        synced = mock_entity_repo.upsert.call_args[0][0]
        snapshot = synced.details["crm_snapshot"]
        assert snapshot["open_commitments_count"] == 0
        assert snapshot["overdue_commitments_count"] == 0

    @pytest.mark.asyncio
    async def test_update_briefing_updates_existing_briefing(self, svc, mock_crm_repo):
        existing = _make_insight(id="b1", insight_type=InsightType.BRIEFING)
        updated = _make_insight(
            id="b1",
            insight_type=InsightType.BRIEFING,
            content="updated",
            metadata={"title": "會議準備"},
        )
        mock_crm_repo.get_ai_insight.return_value = existing
        mock_crm_repo.update_ai_insight.return_value = updated

        result = await svc.update_briefing("p1", "b1", {
            "content": "updated",
            "metadata": {"title": "會議準備"},
        })

        assert result is updated
        mock_crm_repo.update_ai_insight.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_briefing_syncs_latest_briefing_at(self, svc, mock_crm_repo, mock_entity_repo):
        existing = _make_insight(id="b1", insight_type=InsightType.BRIEFING)
        updated = _make_insight(
            id="b1",
            insight_type=InsightType.BRIEFING,
            metadata={"saved_at": "2026-04-15T09:45:00+00:00"},
        )
        mock_crm_repo.get_ai_insight.return_value = existing
        mock_crm_repo.update_ai_insight.return_value = updated
        mock_crm_repo.get_deal.return_value = _make_deal()
        mock_crm_repo.list_activities.return_value = []
        mock_crm_repo.list_ai_insights_by_deal.return_value = [updated]
        mock_entity_repo.get_by_id.return_value = _make_entity()

        await svc.update_briefing("p1", "b1", {"metadata": updated.metadata})

        synced = mock_entity_repo.upsert.call_args[0][0]
        assert synced.details["crm_snapshot"]["latest_briefing_at"] == "2026-04-15T09:45:00+00:00"

    @pytest.mark.asyncio
    async def test_delete_briefing_returns_true_for_existing_briefing(self, svc, mock_crm_repo):
        mock_crm_repo.get_ai_insight.return_value = _make_insight(
            id="b1",
            insight_type=InsightType.BRIEFING,
        )
        mock_crm_repo.delete_ai_insight.return_value = True

        result = await svc.delete_briefing("p1", "b1")

        assert result is True
        mock_crm_repo.delete_ai_insight.assert_called_once_with("p1", "b1")


# ── API endpoint unit tests ────────────────────────────────────────────


def _make_request(method="GET", path_params=None, headers=None, body_data=None):
    class _Req:
        pass

    req = _Req()
    req.method = method
    req.headers = headers or {"origin": "https://zenos-naruvia.web.app"}
    req.path_params = path_params or {}
    req.query_params = {}

    if body_data is not None:
        import json as _json
        async def _json_method():
            return body_data
        req.json = _json_method

    return req


class TestCrmDashboardApiAiInsights:
    @pytest.mark.asyncio
    async def test_get_deal_ai_entries_returns_briefings_debriefs_and_commitments(self):
        from unittest.mock import patch, AsyncMock
        from zenos.interface.crm_dashboard_api import get_deal_ai_entries

        briefing = _make_insight(id="b1", insight_type=InsightType.BRIEFING)
        debrief = _make_insight(id="i1", insight_type=InsightType.DEBRIEF)
        commitment = _make_insight(id="i2", insight_type=InsightType.COMMITMENT)

        mock_svc = MagicMock()
        mock_svc.get_deal_ai_entries = AsyncMock(
            return_value={
                "briefings": [briefing],
                "debriefs": [debrief],
                "commitments": [commitment],
            }
        )

        request = _make_request(path_params={"id": "d1"})

        with patch("zenos.interface.crm_dashboard_api._crm_auth", return_value=("p1", "p1")), \
             patch("zenos.interface.crm_dashboard_api._ensure_crm_service", return_value=mock_svc), \
             patch("zenos.interface.crm_dashboard_api.current_partner_id") as mock_ctx:
            mock_ctx.set.return_value = "token"
            resp = await get_deal_ai_entries(request)

        import json
        body = json.loads(resp.body)
        assert "briefings" in body
        assert "debriefs" in body
        assert "commitments" in body
        assert body["briefings"][0]["id"] == "b1"
        assert body["debriefs"][0]["id"] == "i1"
        assert body["commitments"][0]["id"] == "i2"

    @pytest.mark.asyncio
    async def test_get_deal_ai_entries_returns_401_when_unauthorized(self):
        from unittest.mock import patch
        from zenos.interface.crm_dashboard_api import get_deal_ai_entries

        request = _make_request(path_params={"id": "d1"})

        with patch("zenos.interface.crm_dashboard_api._crm_auth", return_value=(None, None)):
            resp = await get_deal_ai_entries(request)

        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_create_deal_ai_insight_returns_201(self):
        from unittest.mock import patch, AsyncMock
        from zenos.interface.crm_dashboard_api import create_deal_ai_insight

        created = _make_insight()
        mock_svc = MagicMock()
        mock_svc.create_ai_insight = AsyncMock(return_value=created)

        request = _make_request(
            method="POST",
            path_params={"id": "d1"},
            body_data={"insight_type": "debrief", "content": "Sales call summary"},
        )

        with patch("zenos.interface.crm_dashboard_api._crm_auth", return_value=("p1", "p1")), \
             patch("zenos.interface.crm_dashboard_api._ensure_crm_service", return_value=mock_svc), \
             patch("zenos.interface.crm_dashboard_api.current_partner_id") as mock_ctx:
            mock_ctx.set.return_value = "token"
            resp = await create_deal_ai_insight(request)

        assert resp.status_code == 201
        import json
        body = json.loads(resp.body)
        assert body["id"] == "ins-1"
        assert body["insightType"] == "debrief"

    @pytest.mark.asyncio
    async def test_create_deal_ai_insight_returns_400_when_missing_insight_type(self):
        from unittest.mock import patch
        from zenos.interface.crm_dashboard_api import create_deal_ai_insight

        request = _make_request(
            method="POST",
            path_params={"id": "d1"},
            body_data={"content": "Missing insight_type"},
        )

        with patch("zenos.interface.crm_dashboard_api._crm_auth", return_value=("p1", "p1")), \
             patch("zenos.interface.crm_dashboard_api.current_partner_id") as mock_ctx:
            mock_ctx.set.return_value = "token"
            resp = await create_deal_ai_insight(request)

        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_patch_commitment_status_returns_updated_insight(self):
        from unittest.mock import patch, AsyncMock
        from zenos.interface.crm_dashboard_api import patch_commitment_status

        updated = _make_insight(status=InsightStatus.DONE)
        mock_svc = MagicMock()
        mock_svc.update_commitment_status = AsyncMock(return_value=updated)

        request = _make_request(
            method="PATCH",
            path_params={"id": "ins-1"},
            body_data={"status": "done"},
        )

        with patch("zenos.interface.crm_dashboard_api._crm_auth", return_value=("p1", "p1")), \
             patch("zenos.interface.crm_dashboard_api._ensure_crm_service", return_value=mock_svc), \
             patch("zenos.interface.crm_dashboard_api.current_partner_id") as mock_ctx:
            mock_ctx.set.return_value = "token"
            resp = await patch_commitment_status(request)

        assert resp.status_code == 200
        import json
        body = json.loads(resp.body)
        assert body["status"] == "done"

    @pytest.mark.asyncio
    async def test_patch_commitment_status_returns_404_when_not_found(self):
        from unittest.mock import patch, AsyncMock
        from zenos.interface.crm_dashboard_api import patch_commitment_status

        mock_svc = MagicMock()
        mock_svc.update_commitment_status = AsyncMock(return_value=None)

        request = _make_request(
            method="PATCH",
            path_params={"id": "nonexistent"},
            body_data={"status": "done"},
        )

        with patch("zenos.interface.crm_dashboard_api._crm_auth", return_value=("p1", "p1")), \
             patch("zenos.interface.crm_dashboard_api._ensure_crm_service", return_value=mock_svc), \
             patch("zenos.interface.crm_dashboard_api.current_partner_id") as mock_ctx:
            mock_ctx.set.return_value = "token"
            resp = await patch_commitment_status(request)

        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_patch_commitment_status_returns_400_when_missing_status(self):
        from unittest.mock import patch
        from zenos.interface.crm_dashboard_api import patch_commitment_status

        request = _make_request(
            method="PATCH",
            path_params={"id": "ins-1"},
            body_data={},
        )

        with patch("zenos.interface.crm_dashboard_api._crm_auth", return_value=("p1", "p1")), \
             patch("zenos.interface.crm_dashboard_api.current_partner_id") as mock_ctx:
            mock_ctx.set.return_value = "token"
            resp = await patch_commitment_status(request)

        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_patch_commitment_status_returns_400_when_invalid_status(self):
        from unittest.mock import patch, AsyncMock
        from zenos.interface.crm_dashboard_api import patch_commitment_status

        mock_svc = MagicMock()
        mock_svc.update_commitment_status = AsyncMock(
            side_effect=ValueError("Invalid status 'archived': only 'open' and 'done' are allowed")
        )

        request = _make_request(
            method="PATCH",
            path_params={"id": "ins-1"},
            body_data={"status": "archived"},
        )

        with patch("zenos.interface.crm_dashboard_api._crm_auth", return_value=("p1", "p1")), \
             patch("zenos.interface.crm_dashboard_api._ensure_crm_service", return_value=mock_svc), \
             patch("zenos.interface.crm_dashboard_api.current_partner_id") as mock_ctx:
            mock_ctx.set.return_value = "token"
            resp = await patch_commitment_status(request)

        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_patch_briefing_returns_updated_briefing(self):
        from unittest.mock import patch, AsyncMock
        from zenos.interface.crm_dashboard_api import patch_briefing

        updated = _make_insight(
            id="b1",
            insight_type=InsightType.BRIEFING,
            content="updated briefing",
            metadata={"title": "會議準備"},
        )
        mock_svc = MagicMock()
        mock_svc.update_briefing = AsyncMock(return_value=updated)

        request = _make_request(
            method="PATCH",
            path_params={"id": "b1"},
            body_data={"content": "updated briefing", "metadata": {"title": "會議準備"}},
        )

        with patch("zenos.interface.crm_dashboard_api._crm_auth", return_value=("p1", "p1")), \
             patch("zenos.interface.crm_dashboard_api._ensure_crm_service", return_value=mock_svc), \
             patch("zenos.interface.crm_dashboard_api.current_partner_id") as mock_ctx:
            mock_ctx.set.return_value = "token"
            resp = await patch_briefing(request)

        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_delete_briefing_returns_204(self):
        from unittest.mock import patch, AsyncMock
        from zenos.interface.crm_dashboard_api import delete_briefing

        mock_svc = MagicMock()
        mock_svc.delete_briefing = AsyncMock(return_value=True)

        request = _make_request(
            method="DELETE",
            path_params={"id": "b1"},
        )

        with patch("zenos.interface.crm_dashboard_api._crm_auth", return_value=("p1", "p1")), \
             patch("zenos.interface.crm_dashboard_api._ensure_crm_service", return_value=mock_svc), \
             patch("zenos.interface.crm_dashboard_api.current_partner_id") as mock_ctx:
            mock_ctx.set.return_value = "token"
            resp = await delete_briefing(request)

        assert resp.status_code == 204
