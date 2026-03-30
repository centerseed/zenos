"""Tests for CRM dashboard REST API error handling."""

from __future__ import annotations

import json
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
