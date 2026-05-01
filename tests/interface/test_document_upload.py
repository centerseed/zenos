"""Tests for upload_document_file MCP tool."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
async def test_upload_document_file_create_uses_initial_content(tmp_path):
    from zenos.interface.mcp.document_upload import upload_document_file

    doc_path = tmp_path / "spec.md"
    doc_path.write_text("# Spec\n\nBody", encoding="utf-8")

    mock_write = AsyncMock(return_value={"status": "ok", "data": {"doc_id": "doc-1"}})
    with patch("zenos.interface.mcp.write.write", mock_write):
        result = await upload_document_file(
            path=str(doc_path),
            title="Spec",
            linked_entity_ids=["entity-1"],
            type="SPEC",
            tags={"what": ["spec"]},
            workspace_id="ws-1",
        )

    assert result["status"] == "ok"
    data = mock_write.call_args.kwargs["data"]
    assert data["initial_content"] == "# Spec\n\nBody"
    assert "update_content" not in data
    assert data["linked_entity_ids"] == ["entity-1"]
    assert mock_write.call_args.kwargs["workspace_id"] == "ws-1"
    assert result["data"]["uploaded_from_path"] == str(doc_path)
    assert result["data"]["bytes"] == len("# Spec\n\nBody".encode("utf-8"))


@pytest.mark.asyncio
async def test_upload_document_file_update_uses_update_content(tmp_path):
    from zenos.interface.mcp.document_upload import upload_document_file

    doc_path = tmp_path / "guide.md"
    doc_path.write_text("# Guide", encoding="utf-8")

    mock_write = AsyncMock(return_value={"status": "ok", "data": {"doc_id": "doc-1"}})
    with patch("zenos.interface.mcp.write.write", mock_write):
        await upload_document_file(
            path=str(doc_path),
            title="Guide",
            linked_entity_ids=["entity-1"],
            id="doc-1",
        )

    data = mock_write.call_args.kwargs["data"]
    assert data["id"] == "doc-1"
    assert data["update_content"] == "# Guide"
    assert "initial_content" not in data


@pytest.mark.asyncio
async def test_upload_document_file_rejects_file_uri():
    from zenos.interface.mcp.document_upload import upload_document_file

    result = await upload_document_file(
        path="file:///tmp/spec.md",
        title="Spec",
        linked_entity_ids=["entity-1"],
    )

    assert result["status"] == "rejected"
    assert result["data"]["error"] == "INVALID_INPUT"
    assert "file://" in result["data"]["message"]


@pytest.mark.asyncio
async def test_upload_document_file_rejects_large_file(tmp_path):
    from zenos.interface.mcp.document_upload import upload_document_file

    doc_path = tmp_path / "large.md"
    doc_path.write_bytes(b"x" * 1_048_577)

    result = await upload_document_file(
        path=str(doc_path),
        title="Large",
        linked_entity_ids=["entity-1"],
    )

    assert result["status"] == "rejected"
    assert result["data"]["error"] == "INITIAL_CONTENT_TOO_LARGE"
    assert result["data"]["max_bytes"] == 1_048_576
