from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch


def _make_request(body: dict | None = None) -> MagicMock:
    req = MagicMock()
    req.method = "POST"
    req.headers = {}
    req.path_params = {}
    req.query_params = {}
    req.body = AsyncMock(return_value=json.dumps(body or {}).encode("utf-8"))
    return req


async def test_google_workspace_connector_health_uses_override_config():
    from zenos.interface.dashboard_api import google_workspace_connector_health

    request = _make_request({
        "sidecar_base_url": "http://gw-sidecar.internal:8787",
        "sidecar_token": "gwsc-override",
    })

    with (
        patch("zenos.interface.dashboard_api._verify_firebase_token", new=AsyncMock(return_value={"email": "owner@example.com"})),
        patch("zenos.interface.dashboard_api._get_partner_by_email_sql", new=AsyncMock(return_value={
            "id": "partner-1",
            "email": "owner@example.com",
            "display_name": "Owner",
            "shared_partner_id": None,
            "authorized_entity_ids": [],
            "workspace_role": "owner",
            "access_mode": "internal",
            "is_admin": True,
            "preferences": {},
        })),
        patch("zenos.interface.dashboard_api.resolve_active_workspace_id", return_value="partner-1"),
        patch("zenos.interface.dashboard_api.active_partner_view", return_value=({
            "id": "partner-1",
            "email": "owner@example.com",
            "displayName": "Owner",
            "workspaceRole": "owner",
            "preferences": {},
        }, None)),
        patch("zenos.interface.dashboard_api.SourceService") as mock_service_cls,
    ):
        mock_service = mock_service_cls.return_value
        mock_service.check_google_workspace_connector_health = AsyncMock(return_value={
            "ok": True,
            "status": "ok",
            "message": "connector ready",
        })
        response = await google_workspace_connector_health(request)

    assert response.status_code == 200
    body = json.loads(response.body)
    assert body["ok"] is True
    mock_service.check_google_workspace_connector_health.assert_awaited_once()
    _, kwargs = mock_service.check_google_workspace_connector_health.await_args
    assert kwargs["override_config"] == {
        "sidecar_base_url": "http://gw-sidecar.internal:8787",
        "sidecar_token": "gwsc-override",
    }
