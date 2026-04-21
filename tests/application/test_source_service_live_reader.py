from __future__ import annotations

from unittest.mock import patch

import pytest

from zenos.application.knowledge.source_service import SourceService


class _Response:
    def __init__(self, status_code: int, payload: dict):
        self.status_code = status_code
        self._payload = payload

    @property
    def is_success(self) -> bool:
        return 200 <= self.status_code < 300

    def json(self) -> dict:
        return self._payload


class _AsyncClient:
    def __init__(self, *args, **kwargs) -> None:
        self.calls = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, url: str, *, headers: dict | None = None):
        self.calls.append(("GET", url, headers, None))
        return _Response(200, {"status": "ok", "message": "healthy"})

    async def post(self, url: str, *, headers: dict | None = None, json: dict | None = None):
        self.calls.append(("POST", url, headers, json))
        return _Response(200, {"content": "live body", "content_type": "text/plain"})


@pytest.mark.asyncio
async def test_read_source_live_returns_required_when_sidecar_missing():
    svc = SourceService(entity_repo=None, source_adapter=None)

    result = await svc.read_source_live(
        "doc-1",
        source_uri="https://drive.google.com/file/d/1abcXYZ/view",
        source={"type": "gdrive", "source_id": "src-1"},
        partner={"id": "partner-1", "email": "user@example.com", "preferences": {}},
    )

    assert result["error"] == "LIVE_RETRIEVAL_REQUIRED"


@pytest.mark.asyncio
async def test_read_source_live_posts_partner_principal_to_sidecar():
    svc = SourceService(entity_repo=None, source_adapter=None)
    client = _AsyncClient()
    partner = {
        "id": "partner-1",
        "email": "user@example.com",
        "displayName": "User",
        "preferences": {
            "googleWorkspace": {
                "sidecar_base_url": "http://gw-sidecar.internal:8787",
                "sidecar_token": "gwsc-token",
            }
        },
    }

    with patch("zenos.application.knowledge.source_service.httpx.AsyncClient", return_value=client):
        result = await svc.read_source_live(
            "doc-1",
            source_uri="https://drive.google.com/file/d/1abcXYZ/view",
            source={"type": "gdrive", "source_id": "src-1"},
            partner=partner,
        )

    assert result == {"content": "live body", "content_type": "text/plain"}
    method, url, headers, payload = client.calls[-1]
    assert method == "POST"
    assert url == "http://gw-sidecar.internal:8787/read-source"
    assert headers["X-Zenos-Connector-Token"] == "gwsc-token"
    assert payload["principal"]["email"] == "user@example.com"
    assert payload["principal"]["partner_id"] == "partner-1"
    assert payload["source_id"] == "src-1"


@pytest.mark.asyncio
async def test_google_workspace_connector_health_uses_sidecar_health_endpoint():
    svc = SourceService(entity_repo=None, source_adapter=None)
    client = _AsyncClient()
    partner = {
        "id": "partner-1",
        "email": "user@example.com",
        "preferences": {
            "googleWorkspace": {
                "sidecar_base_url": "http://gw-sidecar.internal:8787",
                "sidecar_token": "gwsc-token",
            }
        },
    }

    with patch("zenos.application.knowledge.source_service.httpx.AsyncClient", return_value=client):
        result = await svc.check_google_workspace_connector_health(partner)

    assert result["ok"] is True
    assert result["status"] == "ok"
    method, url, headers, _ = client.calls[-1]
    assert method == "GET"
    assert url == "http://gw-sidecar.internal:8787/health"
    assert headers["X-Zenos-Connector-Token"] == "gwsc-token"
