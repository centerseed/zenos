"""
AC tests for SPEC-journal-compression-resilience.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.asyncio

_PARTNER_ID = "partner-test-001"
_FIXED_TS = datetime(2026, 5, 1, 4, 50, 11, tzinfo=timezone.utc)


class _AcquireContext:
    def __init__(self, conn):
        self.conn = conn

    async def __aenter__(self):
        return self.conn

    async def __aexit__(self, exc_type, exc, tb):
        return False


def _entries() -> list[dict]:
    return [
        {
            "id": "j1",
            "created_at": _FIXED_TS,
            "project": "ZenOS",
            "flow_type": "governance",
            "summary": "Completed GovernanceAI chunking fallback",
            "tags": ["governance"],
        },
        {
            "id": "j2",
            "created_at": _FIXED_TS,
            "project": "ZenOS",
            "flow_type": "governance",
            "summary": "Completed MCP schema compatibility aliases",
            "tags": ["mcp"],
        },
    ]


def _repo(entries: list[dict]):
    repo = AsyncMock()
    conn = AsyncMock()
    conn.fetchval = AsyncMock(return_value=21)
    repo._pool = MagicMock()
    repo._pool.acquire = MagicMock(return_value=_AcquireContext(conn))
    repo.list_oldest_originals = AsyncMock(return_value=entries)
    repo.create_summary = AsyncMock(return_value="summary-uuid")
    repo.delete_by_ids = AsyncMock(return_value=None)
    return repo


@pytest.mark.spec("AC-JCR-01")
async def test_ac_jcr_01_llm_failure_creates_fallback_summary_and_deletes_originals():
    """LLM parse failure still compresses old originals through deterministic fallback."""
    import zenos.interface.mcp as mcp_root

    repo = _repo(_entries())
    llm = MagicMock()
    llm.chat_structured.side_effect = ValueError("JSONDecodeError")

    with (
        patch("zenos.interface.mcp._journal_repo", repo),
        patch("zenos.interface.mcp._ensure_journal_repo", AsyncMock()),
        patch("zenos.interface.mcp.create_llm_client", MagicMock(return_value=llm)),
    ):
        result = await mcp_root._compress_journal(_PARTNER_ID)

    assert result is True
    summary = repo.create_summary.call_args.kwargs["summary"]
    assert summary.startswith("Compressed 2 work journal entries.")
    assert "GovernanceAI chunking fallback" in summary
    repo.delete_by_ids.assert_awaited_once_with(partner_id=_PARTNER_ID, ids=["j1", "j2"])


@pytest.mark.spec("AC-JCR-02")
async def test_ac_jcr_02_llm_failure_warning_has_no_traceback_exc_info():
    """LLM summary failure warning omits exc_info=True traceback."""
    import zenos.interface.mcp as mcp_root

    repo = _repo(_entries())
    llm = MagicMock()
    llm.chat_structured.side_effect = ValueError("pydantic validation failed")

    with (
        patch("zenos.interface.mcp._journal_repo", repo),
        patch("zenos.interface.mcp._ensure_journal_repo", AsyncMock()),
        patch("zenos.interface.mcp.create_llm_client", MagicMock(return_value=llm)),
        patch("zenos.interface.mcp.logger") as logger,
    ):
        await mcp_root._compress_journal(_PARTNER_ID)

    logger.warning.assert_called_once()
    assert logger.warning.call_args.kwargs.get("exc_info") is not True


@pytest.mark.spec("AC-JCR-03")
async def test_ac_jcr_03_successful_llm_summary_is_used():
    """Successful structured summary wins over fallback text."""
    import zenos.interface.mcp as mcp_root

    repo = _repo(_entries())
    llm_result = MagicMock()
    llm_result.summary = "LLM summary from structured output"
    llm = MagicMock()
    llm.chat_structured.return_value = llm_result

    with (
        patch("zenos.interface.mcp._journal_repo", repo),
        patch("zenos.interface.mcp._ensure_journal_repo", AsyncMock()),
        patch("zenos.interface.mcp.create_llm_client", MagicMock(return_value=llm)),
    ):
        result = await mcp_root._compress_journal(_PARTNER_ID)

    assert result is True
    assert repo.create_summary.call_args.kwargs["summary"] == "LLM summary from structured output"


@pytest.mark.spec("AC-JCR-04")
async def test_ac_jcr_04_journal_write_returns_compressed_true_when_fallback_succeeds():
    """Tool response stays ok and compressed=True when fallback compression succeeds."""
    from zenos.interface.mcp.journal import journal_write

    repo = _repo(_entries())
    repo.create = AsyncMock(return_value="journal-new")
    repo.count = AsyncMock(return_value=21)
    repo.list_recent = AsyncMock(return_value=([], 0))
    llm = MagicMock()
    llm.chat_structured.side_effect = ValueError("structured output truncated")
    mock_pid = MagicMock()
    mock_pid.get.return_value = _PARTNER_ID
    mock_partner = MagicMock()
    mock_partner.get.return_value = {"id": _PARTNER_ID, "defaultProject": ""}

    with (
        patch("zenos.interface.mcp._journal_repo", repo),
        patch("zenos.interface.mcp._ensure_journal_repo", AsyncMock()),
        patch("zenos.interface.mcp.create_llm_client", MagicMock(return_value=llm)),
        patch("zenos.infrastructure.context.current_partner_id", mock_pid),
        patch("zenos.interface.mcp.journal._current_partner", mock_partner),
    ):
        result = await journal_write(summary="trigger compression")

    assert result["status"] == "ok"
    assert result["data"]["compressed"] is True
    repo.create_summary.assert_awaited_once()
