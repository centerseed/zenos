"""Tests for CRM dashboard REST API error handling."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import patch


def _make_request(
    method: str = "GET",
    headers: dict | None = None,
    path_params: dict | None = None,
    query_params: dict | None = None,
):
    class _Req:
        pass

    req = _Req()
    req.method = method
    req.headers = headers or {}
    req.path_params = path_params or {}
    req.query_params = query_params or {}
    return req


class TestCrmDashboardApi:
    def test_deal_to_dict_includes_last_activity_at(self):
        from zenos.domain.crm_models import Deal
        from zenos.interface.crm_dashboard_api import _deal_to_dict

        activity_at = datetime(2026, 4, 21, 12, 30, tzinfo=timezone.utc)
        deal = Deal(
            id="deal-1",
            partner_id="tenant-1",
            title="ZenOS CRM",
            company_id="company-1",
            owner_partner_id="owner-1",
            last_activity_at=activity_at,
        )

        payload = _deal_to_dict(deal)

        assert payload["lastActivityAt"] == activity_at.isoformat()

    async def test_list_companies_returns_json_error_with_cors_on_failure(self):
        from zenos.interface.crm_dashboard_api import list_companies

        request = _make_request(
            headers={
                "authorization": "Bearer fake-token",
                "origin": "https://zenos-naruvia.web.app",
            }
        )

        with patch(
            "zenos.interface.crm_dashboard_api._crm_auth",
            return_value=("tenant-1", "actor-1"),
        ), patch(
            "zenos.interface.crm_dashboard_api._ensure_crm_service",
            side_effect=RuntimeError("crm schema missing"),
        ):
            resp = await list_companies(request)

        assert resp.status_code == 500
        assert resp.headers["access-control-allow-origin"] == "https://zenos-naruvia.web.app"
        body = json.loads(resp.body)
        assert body["error"] == "INTERNAL_ERROR"
        assert "crm schema missing" in body["message"]
