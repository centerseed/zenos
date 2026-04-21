"""Spec compliance tests for SPEC-google-workspace-per-user-retrieval."""

from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import AsyncMock, patch

import pytest

from zenos.domain.knowledge import Entity, Tags


def _make_doc(sources: list[dict], **overrides) -> Entity:
    defaults = dict(
        id="doc-1",
        name="Google Doc",
        type="document",
        summary="External doc",
        tags=Tags(what=["doc"], why="test", how="pytest", who=["dev"]),
        status="active",
        visibility="public",
        sources=sources,
    )
    defaults.update(overrides)
    return Entity(**defaults)


def _partner(*, connector_scopes: dict | None = None) -> dict:
    return {
        "id": "partner-1",
        "email": "dev@test.com",
        "displayName": "Dev",
        "status": "active",
        "isAdmin": False,
        "workspaceRole": "member",
        "accessMode": "internal",
        "authorizedEntityIds": [],
        "preferences": {"connectorScopes": connector_scopes or {}},
    }


@contextmanager
def _mcp_partner_context(partner: dict):
    from zenos.interface.mcp._auth import _current_partner

    token = _current_partner.set(partner)
    try:
        yield
    finally:
        _current_partner.reset(token)


@pytest.fixture(autouse=True)
def _mock_tool_bootstrap():
    with (
        patch("zenos.interface.mcp._ensure_services", new=AsyncMock(return_value=None)),
        patch("zenos.interface.mcp.ontology_service", new=AsyncMock()),
        patch("zenos.interface.mcp.task_service", new=AsyncMock()),
        patch("zenos.interface.mcp.entity_repo", new=AsyncMock()),
        patch("zenos.interface.mcp.entry_repo", new=AsyncMock()),
    ):
        yield


def _error_data(result: dict) -> dict:
    assert result["status"] in {"error", "rejected"}
    return result["data"]


def _ok_data(result: dict) -> dict:
    assert result["status"] == "ok"
    return result["data"]


@pytest.mark.asyncio
async def test_ac_gwpr_01_empty_connector_scope_conceals_document():
    """AC-GWPR-01: Given workspace 對 gdrive 已定義 connector scope 且 containers=[], When caller 讀取只含 gdrive source 的文件, Then MCP 與 Dashboard 都不得暴露該文件或其 source metadata"""
    from zenos.interface.mcp import get
    from zenos.interface.dashboard_api import _entity_to_dict

    doc = _make_doc([{
        "source_id": "src-1",
        "type": "gdrive",
        "uri": "https://drive.google.com/file/d/1abcXYZ/view",
        "container_id": "drive:finance",
        "retrieval_mode": "per_user_live",
        "content_access": "full",
    }])
    partner = _partner(connector_scopes={"gdrive": {"containers": []}})

    with (
        patch("zenos.interface.mcp.ontology_service") as mock_os,
        _mcp_partner_context(partner),
    ):
        mock_os.get_document = AsyncMock(return_value=doc)
        result = await get(collection="documents", id="doc-1")

    data = _error_data(result)
    assert data["error"] == "NOT_FOUND"
    assert _entity_to_dict(doc, partner)["sources"] == []


@pytest.mark.asyncio
async def test_ac_gwpr_02_read_source_out_of_scope_returns_not_found():
    """AC-GWPR-02: Given gdrive source 的 container_id 不在 workspace allowlist，When caller 執行 read_source(doc_id, source_id)，Then server 回 NOT_FOUND 或等價 concealment，而不是回 summary/full-content"""
    from zenos.interface.mcp import read_source

    doc = _make_doc([{
        "source_id": "src-1",
        "type": "gdrive",
        "uri": "https://drive.google.com/file/d/1abcXYZ/view",
        "container_id": "drive:finance",
        "retrieval_mode": "per_user_live",
        "content_access": "full",
    }])
    partner = _partner(connector_scopes={"gdrive": {"containers": ["drive:hr"]}})

    with (
        patch("zenos.interface.mcp.ontology_service") as mock_os,
        _mcp_partner_context(partner),
    ):
        mock_os.get_document = AsyncMock(return_value=doc)
        result = await read_source(doc_id="doc-1", source_id="src-1")

    data = _error_data(result)
    assert data["error"] == "NOT_FOUND"


@pytest.mark.asyncio
async def test_ac_gwpr_03_mixed_doc_filters_blocked_sources():
    """AC-GWPR-03: Given document 同時有一個 in-scope gdrive source 與一個 out-of-scope gdrive source，When caller 讀取文件 metadata，Then 文件仍可見，但 response 只包含 in-scope source"""
    from zenos.interface.mcp import get
    from zenos.interface.dashboard_api import _entity_to_dict

    doc = _make_doc([
        {
            "source_id": "src-allow",
            "type": "gdrive",
            "uri": "https://drive.google.com/file/d/1allowed/view",
            "container_id": "drive:finance",
            "retrieval_mode": "per_user_live",
            "content_access": "full",
        },
        {
            "source_id": "src-block",
            "type": "gdrive",
            "uri": "https://drive.google.com/file/d/1blocked/view",
            "container_id": "drive:secret",
            "retrieval_mode": "per_user_live",
            "content_access": "full",
        },
    ])
    partner = _partner(connector_scopes={"gdrive": {"containers": ["drive:finance"]}})

    with (
        patch("zenos.interface.mcp.ontology_service") as mock_os,
        _mcp_partner_context(partner),
    ):
        mock_os.get_document = AsyncMock(return_value=doc)
        result = await get(collection="documents", id="doc-1")

    data = _ok_data(result)
    assert [s["source_id"] for s in data["sources"]] == ["src-allow"]
    assert [s["source_id"] for s in _entity_to_dict(doc, partner)["sources"]] == ["src-allow"]


@pytest.mark.asyncio
async def test_ac_gwpr_04_per_user_live_without_reader_returns_required():
    """AC-GWPR-04: Given gdrive source 設為 retrieval_mode=per_user_live 且 content_access=full，When read_source 執行但 live reader 或 user-scoped credential 未配置，Then server 回 LIVE_RETRIEVAL_REQUIRED"""
    from zenos.interface.mcp import read_source

    doc = _make_doc([{
        "source_id": "src-1",
        "type": "gdrive",
        "uri": "https://drive.google.com/file/d/1abcXYZ/view",
        "container_id": "drive:finance",
        "retrieval_mode": "per_user_live",
        "content_access": "full",
    }])
    partner = _partner(connector_scopes={"gdrive": {"containers": ["drive:finance"]}})

    with (
        patch("zenos.interface.mcp.ontology_service") as mock_os,
        patch("zenos.interface.mcp.source_service") as mock_ss,
        _mcp_partner_context(partner),
    ):
        mock_os.get_document = AsyncMock(return_value=doc)
        mock_ss.read_source_with_recovery = None
        mock_ss.read_source_live = None
        result = await read_source(doc_id="doc-1", source_id="src-1")

    data = _error_data(result)
    assert data["error"] == "LIVE_RETRIEVAL_REQUIRED"


@pytest.mark.asyncio
async def test_ac_gwpr_05_per_user_live_uses_live_reader():
    """AC-GWPR-05: Given gdrive source 設為 retrieval_mode=per_user_live 且 content_access=full，When live reader 可用，Then read_source 回傳 live fetched content，且不得回退到共享全文副本"""
    from zenos.interface.mcp import read_source

    doc = _make_doc([{
        "source_id": "src-1",
        "type": "gdrive",
        "uri": "https://drive.google.com/file/d/1abcXYZ/view",
        "container_id": "drive:finance",
        "retrieval_mode": "per_user_live",
        "content_access": "full",
        "snapshot_summary": "old summary",
    }])
    partner = _partner(connector_scopes={"gdrive": {"containers": ["drive:finance"]}})

    with (
        patch("zenos.interface.mcp.ontology_service") as mock_os,
        patch("zenos.interface.mcp.source_service") as mock_ss,
        _mcp_partner_context(partner),
    ):
        mock_os.get_document = AsyncMock(return_value=doc)
        mock_ss.read_source_with_recovery = None
        mock_ss.read_source_live = AsyncMock(return_value={"content": "live full content", "content_type": "text/markdown"})
        result = await read_source(doc_id="doc-1", source_id="src-1")

    data = _ok_data(result)
    assert data["content"] == "live full content"
    _, kwargs = mock_ss.read_source_live.call_args
    assert kwargs["partner"]["id"] == "partner-1"
    assert kwargs["source"]["source_id"] == "src-1"


@pytest.mark.asyncio
async def test_ac_gwpr_06_per_user_live_summary_mode_returns_snapshot():
    """AC-GWPR-06: Given gdrive source 設為 retrieval_mode=per_user_live 且 content_access=summary，When read_source 執行，Then server 只回 snapshot_summary 或 SNAPSHOT_UNAVAILABLE，不可回全文"""
    from zenos.interface.mcp import read_source

    doc = _make_doc([{
        "source_id": "src-1",
        "type": "gdrive",
        "uri": "https://drive.google.com/file/d/1abcXYZ/view",
        "container_id": "drive:finance",
        "retrieval_mode": "per_user_live",
        "content_access": "summary",
        "snapshot_summary": "summary only",
    }])
    partner = _partner(connector_scopes={"gdrive": {"containers": ["drive:finance"]}})

    with (
        patch("zenos.interface.mcp.ontology_service") as mock_os,
        patch("zenos.interface.mcp.source_service") as mock_ss,
        _mcp_partner_context(partner),
    ):
        mock_os.get_document = AsyncMock(return_value=doc)
        mock_ss.read_source_with_recovery = None
        mock_ss.read_source_live = AsyncMock(return_value={"content": "should-not-be-used"})
        result = await read_source(doc_id="doc-1", source_id="src-1")

    data = _ok_data(result)
    assert data["content"] == "summary only"
    mock_ss.read_source_live.assert_not_called()


@pytest.mark.asyncio
async def test_ac_gwpr_07_blocked_document_behaves_as_not_found():
    """AC-GWPR-07: Given document 的所有 source 都被 connector scope 擋下，When caller 查 get(collection=\"documents\") 或 Dashboard docs metadata，Then 文件視同不存在，不得外洩 blocked source metadata"""
    from zenos.application.knowledge.ontology_service import OntologyService
    from zenos.interface.mcp import get

    doc = _make_doc([{
        "source_id": "src-1",
        "type": "gdrive",
        "uri": "https://drive.google.com/file/d/1abcXYZ/view",
        "retrieval_mode": "per_user_live",
        "content_access": "full",
        # Missing container_id -> fail closed once scope config exists
    }])
    partner = _partner(connector_scopes={"gdrive": {"containers": ["drive:finance"]}})

    assert OntologyService.is_entity_visible_for_partner(doc, partner) is False

    with (
        patch("zenos.interface.mcp.ontology_service") as mock_os,
        _mcp_partner_context(partner),
    ):
        mock_os.get_document = AsyncMock(return_value=doc)
        result = await get(collection="documents", id="doc-1")

    data = _error_data(result)
    assert data["error"] == "NOT_FOUND"


@pytest.mark.asyncio
async def test_ac_gwpr_08_write_preserves_source_access_fields():
    """AC-GWPR-08: Given source 帶 container_id、retrieval_mode、content_access，When helper 或 write mutation 更新 source，Then 新欄位被保留在 sources_json，供後續 runtime 使用"""
    from tests.application.test_document_bundle import _make_doc_entity, _make_entity_repo, _make_service

    existing = _make_doc_entity(doc_role="index")
    repo = _make_entity_repo()
    repo.get_by_id = AsyncMock(return_value=existing)
    svc = _make_service(entity_repo=repo)

    result = await svc.upsert_document({
        "id": "doc-test-1",
        "linked_entity_ids": ["parent-1"],
        "add_source": {
            "uri": "https://drive.google.com/file/d/1abcXYZ/view",
            "type": "gdrive",
            "label": "Roadmap",
            "container_id": "drive:finance",
            "retrieval_mode": "per_user_live",
            "content_access": "full",
        },
    })

    new_source = result.sources[-1]
    assert new_source["container_id"] == "drive:finance"
    assert new_source["retrieval_mode"] == "per_user_live"
    assert new_source["content_access"] == "full"


@pytest.mark.asyncio
async def test_ac_gwpr_11_live_reader_payload_uses_partner_principal():
    """AC-GWPR-11: Given gdrive source 設為 retrieval_mode=per_user_live 且 sidecar 已配置，When read_source 走 live path，Then ZenOS 對 sidecar 的 request payload 會帶當前 caller 的 email/principal，並只回 sidecar 的 live content"""
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
            self.payload = None
            self.headers = None

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url: str, *, headers: dict | None = None, json: dict | None = None):
            assert url == "http://gw-sidecar.internal:8787/read-source"
            self.headers = headers
            self.payload = json
            return _Response(200, {"content": "live content", "content_type": "text/plain"})

    partner = _partner(connector_scopes={"gdrive": {"containers": ["drive:finance"]}})
    partner["preferences"]["googleWorkspace"] = {
        "sidecar_base_url": "http://gw-sidecar.internal:8787",
        "sidecar_token": "gwsc-token",
        "principal_mode": "partner_email",
    }
    client = _AsyncClient()

    with patch("zenos.application.knowledge.source_service.httpx.AsyncClient", return_value=client):
        svc = SourceService(entity_repo=None, source_adapter=None)
        result = await svc.read_source_live(
            "doc-1",
            source_uri="https://drive.google.com/file/d/1abcXYZ/view",
            source={"type": "gdrive", "source_id": "src-1"},
            partner=partner,
        )

    assert result["content"] == "live content"
    assert client.headers["X-Zenos-Connector-Token"] == "gwsc-token"
    assert client.payload["principal"]["email"] == "dev@test.com"
    assert client.payload["principal"]["partner_id"] == "partner-1"
