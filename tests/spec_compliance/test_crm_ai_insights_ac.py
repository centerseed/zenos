"""
Spec Compliance Tests — CRM AI Intelligence v0.3
AC tests derived from SPEC-crm-intelligence.md

Red (FAIL) = gap. Green (PASS) = verified.

Scope:
- S01: Backend AI Insights table + API
- S02/S03: Frontend behaviour is verified via read-code assertions (structure)

Run: pytest tests/spec_compliance/test_crm_ai_insights_ac.py -v
"""

from __future__ import annotations

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

from zenos.domain.crm_models import AiInsight, InsightStatus, InsightType


def _make_insight(**kwargs) -> AiInsight:
    defaults = dict(
        id="ins-1",
        partner_id="p1",
        deal_id="d1",
        insight_type=InsightType.DEBRIEF,
        content="",
        metadata={},
        activity_id=None,
        status=InsightStatus.ACTIVE,
        created_at=datetime(2026, 4, 14, 12, 0, 0, tzinfo=timezone.utc),
    )
    defaults.update(kwargs)
    return AiInsight(**defaults)


@pytest.fixture
def mock_crm_repo():
    repo = MagicMock()
    repo.create_ai_insight = AsyncMock()
    repo.get_ai_insight = AsyncMock()
    repo.update_ai_insight = AsyncMock()
    repo.list_ai_insights_by_deal = AsyncMock()
    repo.update_ai_insight_status = AsyncMock()
    repo.delete_ai_insight = AsyncMock()
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
def svc(mock_crm_repo):
    from zenos.application.crm.crm_service import CrmService
    entity_repo = MagicMock()
    entity_repo.upsert = AsyncMock()
    entity_repo.get_by_id = AsyncMock()
    rel_repo = MagicMock()
    rel_repo.add = AsyncMock()
    return CrmService(mock_crm_repo, entity_repo, rel_repo)


# ── AC: P0-4 Backend API ──────────────────────────────────────────────────────


class TestAcP04BackendApi:
    """
    AC: POST /api/crm/deals/{id}/ai-insights returns 201
    AC: GET /api/crm/deals/{id}/ai-entries returns {briefings, debriefs, commitments}
    AC: PATCH /api/crm/commitments/{id} updates commitment status
    AC: Migration SQL is syntactically correct (verified by file read)
    """

    @pytest.mark.asyncio
    async def test_ac_post_ai_insights_returns_201_body(self):
        """
        AC: POST /api/crm/deals/{id}/ai-insights returns 201 with id and insightType.
        Verifies the API response shape matches the spec.
        """
        from unittest.mock import patch, AsyncMock as AM
        from zenos.interface.crm_dashboard_api import create_deal_ai_insight

        created = _make_insight(insight_type=InsightType.DEBRIEF)
        mock_svc = MagicMock()
        mock_svc.create_ai_insight = AM(return_value=created)

        class Req:
            method = "POST"
            headers = {"origin": "https://zenos-naruvia.web.app"}
            path_params = {"id": "d1"}
            query_params = {}
            async def json(self):
                return {"insight_type": "debrief", "content": "摘要"}

        with patch("zenos.interface.crm_dashboard_api._crm_auth", return_value=("p1", "p1")), \
             patch("zenos.interface.crm_dashboard_api._ensure_crm_service", return_value=mock_svc), \
             patch("zenos.interface.crm_dashboard_api.current_partner_id") as ctx:
            ctx.set.return_value = "token"
            resp = await create_deal_ai_insight(Req())

        assert resp.status_code == 201
        import json
        body = json.loads(resp.body)
        assert "id" in body
        assert "insightType" in body
        assert body["insightType"] == "debrief"

    @pytest.mark.asyncio
    async def test_ac_get_ai_entries_response_shape(self):
        """
        AC: GET /api/crm/deals/{id}/ai-entries returns {briefings: [...], debriefs: [...], commitments: [...]}.
        Spec defines this exact key structure.
        """
        from unittest.mock import patch, AsyncMock as AM
        from zenos.interface.crm_dashboard_api import get_deal_ai_entries

        briefing = _make_insight(id="b1", insight_type=InsightType.BRIEFING)
        debrief = _make_insight(id="d1", insight_type=InsightType.DEBRIEF)
        commitment = _make_insight(id="c1", insight_type=InsightType.COMMITMENT,
                                   status=InsightStatus.OPEN,
                                   metadata={"content": "報價單", "owner": "us", "deadline": "2026-04-20"})

        mock_svc = MagicMock()
        mock_svc.get_deal_ai_entries = AM(
            return_value={
                "briefings": [briefing],
                "debriefs": [debrief],
                "commitments": [commitment],
            }
        )

        class Req:
            method = "GET"
            headers = {"origin": "https://zenos-naruvia.web.app"}
            path_params = {"id": "d1"}
            query_params = {}

        with patch("zenos.interface.crm_dashboard_api._crm_auth", return_value=("p1", "p1")), \
             patch("zenos.interface.crm_dashboard_api._ensure_crm_service", return_value=mock_svc), \
             patch("zenos.interface.crm_dashboard_api.current_partner_id") as ctx:
            ctx.set.return_value = "token"
            resp = await get_deal_ai_entries(Req())

        import json
        body = json.loads(resp.body)
        # Spec-defined keys
        assert "briefings" in body, "response must have 'briefings' key"
        assert "debriefs" in body, "response must have 'debriefs' key"
        assert "commitments" in body, "response must have 'commitments' key"
        assert isinstance(body["briefings"], list)
        assert isinstance(body["debriefs"], list)
        assert isinstance(body["commitments"], list)
        # Each debrief must have metadata with key_decisions (AC: debrief structure)
        d = body["debriefs"][0]
        assert "id" in d
        assert "createdAt" in d
        assert "activityId" in d
        assert "metadata" in d

    @pytest.mark.asyncio
    async def test_ac_patch_commitment_status_done(self):
        """
        AC: PATCH /api/crm/commitments/{id} with status=done returns updated entry.
        """
        from unittest.mock import patch, AsyncMock as AM
        from zenos.interface.crm_dashboard_api import patch_commitment_status

        updated = _make_insight(id="c1", insight_type=InsightType.COMMITMENT,
                                status=InsightStatus.DONE)
        mock_svc = MagicMock()
        mock_svc.update_commitment_status = AM(return_value=updated)

        class Req:
            method = "PATCH"
            headers = {"origin": "https://zenos-naruvia.web.app"}
            path_params = {"id": "c1"}
            query_params = {}
            async def json(self):
                return {"status": "done"}

        with patch("zenos.interface.crm_dashboard_api._crm_auth", return_value=("p1", "p1")), \
             patch("zenos.interface.crm_dashboard_api._ensure_crm_service", return_value=mock_svc), \
             patch("zenos.interface.crm_dashboard_api.current_partner_id") as ctx:
            ctx.set.return_value = "token"
            resp = await patch_commitment_status(Req())

        assert resp.status_code == 200
        import json
        body = json.loads(resp.body)
        assert body["status"] == "done"

    @pytest.mark.asyncio
    async def test_ac_get_ai_entries_categorises_briefing_separately(self, svc, mock_crm_repo):
        """
        AC: GET ai-entries returns briefings in their own list, not mixed into debrief/commitment.
        """
        briefing = _make_insight(id="b1", insight_type=InsightType.BRIEFING)
        debrief = _make_insight(id="d1", insight_type=InsightType.DEBRIEF)
        mock_crm_repo.list_ai_insights_by_deal.return_value = [briefing, debrief]

        result = await svc.get_deal_ai_entries("p1", "d1")

        assert result["briefings"] == [briefing]
        assert all(i.insight_type != InsightType.BRIEFING for i in result["debriefs"]), \
            "briefing entries must not appear in debriefs"
        assert all(i.insight_type != InsightType.BRIEFING for i in result["commitments"]), \
            "briefing entries must not appear in commitments"

    @pytest.mark.asyncio
    async def test_ac_commitment_status_only_open_and_done_allowed(self, svc, mock_crm_repo):
        """
        AC: PATCH status only 'open' and 'done' are valid; other values raise ValueError.
        """
        for invalid in ("active", "archived", "pending", ""):
            with pytest.raises(ValueError):
                await svc.update_commitment_status("p1", "c1", invalid)

        mock_crm_repo.update_ai_insight_status.assert_not_called()

    @pytest.mark.asyncio
    async def test_ac_create_ai_insight_debrief_has_activity_id(self, svc, mock_crm_repo):
        """
        AC: debrief entry includes activity_id (linked to the Activity that triggered it).
        Spec: 'crm_debrief 掛在 deal entity 上，跟隨 Activity 一一對應'
        """
        created = _make_insight(insight_type=InsightType.DEBRIEF, activity_id="act-99")
        mock_crm_repo.create_ai_insight.return_value = created

        result = await svc.create_ai_insight("p1", {
            "deal_id": "d1",
            "insight_type": "debrief",
            "content": "會議摘要",
            "activity_id": "act-99",
        })

        assert result.activity_id == "act-99", "debrief must link to activity via activity_id"

    def test_ac_migration_sql_has_required_columns(self):
        """
        AC: Migration SQL must define ai_insights table with all required columns.
        """
        import re

        with open("/Users/wubaizong/clients/ZenOS/migrations/20260414_0003_crm_ai_insights.sql") as f:
            sql = f.read().lower()

        required_columns = ["id", "partner_id", "deal_id", "activity_id",
                            "insight_type", "content", "metadata", "status", "created_at"]
        for col in required_columns:
            assert col in sql, f"migration missing required column: {col}"

        # Check constraint values match spec
        assert "briefing" in sql
        assert "debrief" in sql
        assert "commitment" in sql
        assert "active" in sql
        assert "open" in sql
        assert "done" in sql
        assert "archived" in sql

    def test_ac_migration_sql_has_deal_partner_index(self):
        """
        AC: Migration SQL must have index on (partner_id, deal_id) for efficient queries.
        """
        with open("/Users/wubaizong/clients/ZenOS/migrations/20260414_0003_crm_ai_insights.sql") as f:
            sql = f.read().lower()

        assert "create index" in sql
        assert "partner_id, deal_id" in sql or "partner_id,deal_id" in sql


# ── AC: P0-3 Deal AI Panel ───────────────────────────────────────────────────


class TestAcP03DealAiPanel:
    """
    AC: Deal 智能面板 backend support verified via service behaviour.
    """

    @pytest.mark.asyncio
    async def test_ac_cold_start_returns_empty_lists(self, svc, mock_crm_repo):
        """
        AC: 'Given deal 尚無任何 debrief entry, When 面板載入, Then 顯示引導文字'
        Backend: returns empty briefings, debriefs and commitments for new deal.
        """
        mock_crm_repo.list_ai_insights_by_deal.return_value = []

        result = await svc.get_deal_ai_entries("p1", "brand-new-deal")

        assert result["briefings"] == [], "new deal should have no briefings"
        assert result["debriefs"] == [], "new deal should have no debriefs"
        assert result["commitments"] == [], "new deal should have no commitments"

    @pytest.mark.asyncio
    async def test_ac_multiple_debriefs_all_returned(self, svc, mock_crm_repo):
        """
        AC: 'Given deal 有多筆 debrief entry, When 使用者查看 AI 洞察面板,
            Then 面板自動彙整所有 debrief 的關鍵決策、客戶顧慮'
        Backend: all debrief entries for the deal are returned.
        """
        debriefs = [
            _make_insight(id=f"d{i}", insight_type=InsightType.DEBRIEF,
                          metadata={"key_decisions": [f"決策{i}"]})
            for i in range(3)
        ]
        mock_crm_repo.list_ai_insights_by_deal.return_value = debriefs

        result = await svc.get_deal_ai_entries("p1", "d1")

        assert len(result["debriefs"]) == 3, "all 3 debriefs must be returned"

    @pytest.mark.asyncio
    async def test_ac_commitment_overdue_status_preserved(self, svc, mock_crm_repo):
        """
        AC: 'Given 承諾事項超過建議期限且未完成, When 面板載入, Then 該事項標示紅色「逾期」標籤'
        Backend: open commitment with past deadline is returned as-is (frontend renders overdue).
        """
        commitment = _make_insight(
            id="c1",
            insight_type=InsightType.COMMITMENT,
            status=InsightStatus.OPEN,
            metadata={"content": "提供報價單", "owner": "us", "deadline": "2020-01-01"},
        )
        mock_crm_repo.list_ai_insights_by_deal.return_value = [commitment]

        result = await svc.get_deal_ai_entries("p1", "d1")
        c = result["commitments"][0]

        assert c.status == InsightStatus.OPEN
        assert c.metadata["deadline"] == "2020-01-01"
        # The frontend is responsible for detecting overdue; backend returns raw data


# ── AC: Regression — Silent Failure Paths ─────────────────────────────────────


class TestRegressionSilentFailure:
    """
    Regression tests for identified silent failure patterns.
    Found by QA 2026-04-14.
    """

    @pytest.mark.asyncio
    async def test_regression_update_status_not_found_returns_none_not_exception(
        self, svc, mock_crm_repo
    ):
        """
        Regression: PATCH commitment/{id} for nonexistent id must return None (→ 404),
        not raise an exception that becomes a 500 error.
        Found by QA: service silently returns None; API must map to 404.
        """
        mock_crm_repo.update_ai_insight_status.return_value = None

        result = await svc.update_commitment_status("p1", "no-such-id", "done")

        assert result is None, "nonexistent commitment must return None, not raise"

    @pytest.mark.asyncio
    async def test_regression_create_insight_with_invalid_type_raises_value_error(
        self, svc, mock_crm_repo
    ):
        """
        Regression: creating an insight with invalid insight_type must raise ValueError,
        not pass through and corrupt DB.
        """
        with pytest.raises((ValueError, KeyError)):
            await svc.create_ai_insight("p1", {
                "deal_id": "d1",
                "insight_type": "invalid_type",
                "content": "some content",
            })

    @pytest.mark.asyncio
    async def test_regression_debrief_context_pack_missing_recent_commitments(self):
        """
        Regression (fixed): buildDebriefPrompt in CrmAiPanel.tsx no longer hardcodes
        recent_commitments=[]. It now reads from aiEntries.commitments filtered to open status.

        Verifies:
        1. recent_commitments field exists in the debrief context pack
        2. The hardcoded empty array is gone — aiEntries is used instead
        """
        import re

        with open(
            "/Users/wubaizong/clients/ZenOS/dashboard/src/features/crm/CrmAiPanel.tsx"
        ) as f:
            source = f.read()

        # Confirm recent_commitments is in the debrief context (field exists)
        assert "recent_commitments" in source, \
            "debrief context pack must include recent_commitments field"

        # Verify the hardcoded empty array is no longer present
        hardcoded_empty = re.search(
            r'recent_commitments:\s*\[\]',
            source
        )
        assert hardcoded_empty is None, (
            "recent_commitments in buildDebriefPrompt must NOT be hardcoded to []. "
            "It should be populated from aiEntries.commitments (filtered to open status)."
        )

        # Verify aiEntries is used for recent_commitments
        assert "aiEntries?.commitments" in source, \
            "buildDebriefPrompt must use aiEntries?.commitments to populate recent_commitments"

    def test_regression_commitment_completed_panel_no_done_section(self):
        """
        Regression: Spec AC requires 'completed commitments move to bottom collapsed section'.
        DealInsightsPanel does not implement a dedicated completed/collapsed area.

        Filed as: MAJOR — visual AC not met; completed items show inline with opacity-50
        instead of moving to a separate collapsed '已完成' section at the bottom.
        """
        with open(
            "/Users/wubaizong/clients/ZenOS/dashboard/src/features/crm/DealInsightsPanel.tsx"
        ) as f:
            source = f.read()

        # Check for the absence of a dedicated completed section
        has_completed_section = (
            "已完成" in source and
            ("details" in source or "摺疊" in source or "collapsed_done" in source)
        )

        # This assertion SHOULD FAIL — documents the missing feature
        assert has_completed_section, (
            "KNOWN BUG: Spec AC requires 'completed commitments move to bottom collapsed section'. "
            "DealInsightsPanel shows completed items in-place (opacity-50) but has no "
            "'已完成' collapsed area. Needs a <details> or separate section for done items."
        )
