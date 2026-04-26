"""Tests for journal_write and journal_read MCP tools.

These are mock unit tests — no real DB or LLM connection required.
All DB interactions are mocked via SqlWorkJournalRepository.

⚠️ 僅 mock 測試：DB 操作和 _compress_journal 均被 mock，
無法驗證真實 SQL 執行。壓縮路徑的 LLM 呼叫未驗證真實格式。
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.asyncio

_PARTNER_ID = "partner-test-001"
_FIXED_TS = datetime(2026, 4, 4, 12, 0, 0, tzinfo=timezone.utc)


def _make_journal_repo(
    *,
    create_return: str = "uuid-1234-5678-abcd-efgh12345678",
    count_return: int = 1,
    list_recent_return: tuple | None = None,
) -> AsyncMock:
    repo = AsyncMock()
    repo.create = AsyncMock(return_value=create_return)
    repo.count = AsyncMock(return_value=count_return)
    if list_recent_return is None:
        list_recent_return = ([], 0)
    repo.list_recent = AsyncMock(return_value=list_recent_return)
    repo.list_oldest_originals = AsyncMock(return_value=[])
    repo.delete_by_ids = AsyncMock(return_value=None)
    repo.create_summary = AsyncMock(return_value="summary-uuid")
    return repo


def _make_partner_ctx(partner_id: str = _PARTNER_ID, partner_data: dict | None = None):
    """Build mock context vars for _current_partner_id and _current_partner."""
    mock_pid = MagicMock()
    mock_pid.get = MagicMock(return_value=partner_id)

    mock_partner = MagicMock()
    mock_partner.get = MagicMock(return_value=partner_data or {"id": partner_id, "defaultProject": ""})
    return mock_pid, mock_partner


# ---------------------------------------------------------------------------
# journal_write
# ---------------------------------------------------------------------------


async def test_journal_write_returns_ok_status():
    """journal_write returns status=ok with id and created_at fields."""
    from zenos.interface.mcp.journal import journal_write

    repo = _make_journal_repo()
    mock_pid, mock_partner = _make_partner_ctx()

    with (
        patch("zenos.interface.mcp._journal_repo", repo),
        patch("zenos.interface.mcp._ensure_journal_repo", AsyncMock()),
        patch("zenos.infrastructure.context.current_partner_id", mock_pid),
        patch("zenos.interface.mcp.journal._current_partner", mock_partner),
    ):
        result = await journal_write(summary="feature done")

    assert result["status"] == "ok"
    assert "id" in result["data"]
    assert "created_at" in result["data"]
    assert result["data"]["compressed"] is False


async def test_journal_write_truncates_summary_to_500_chars_with_warning():
    """journal_write truncates only at repository limit and warns."""
    from zenos.interface.mcp.journal import journal_write

    long_summary = "x" * 600
    repo = _make_journal_repo()
    mock_pid, mock_partner = _make_partner_ctx()

    with (
        patch("zenos.interface.mcp._journal_repo", repo),
        patch("zenos.interface.mcp._ensure_journal_repo", AsyncMock()),
        patch("zenos.infrastructure.context.current_partner_id", mock_pid),
        patch("zenos.interface.mcp.journal._current_partner", mock_partner),
    ):
        result = await journal_write(summary=long_summary)

    call_kwargs = repo.create.call_args[1]
    assert len(call_kwargs["summary"]) == 500
    assert "journal summary truncated to 500 chars" in result["warnings"]


async def test_journal_write_triggers_compress_when_over_20():
    """journal_write calls _compress_journal when count > 20."""
    from zenos.interface.mcp.journal import journal_write

    repo = _make_journal_repo(count_return=21)
    compress_mock = AsyncMock()
    mock_pid, mock_partner = _make_partner_ctx()

    with (
        patch("zenos.interface.mcp._journal_repo", repo),
        patch("zenos.interface.mcp._ensure_journal_repo", AsyncMock()),
        patch("zenos.interface.mcp._compress_journal", compress_mock),
        patch("zenos.infrastructure.context.current_partner_id", mock_pid),
        patch("zenos.interface.mcp.journal._current_partner", mock_partner),
    ):
        result = await journal_write(summary="another entry")

    compress_mock.assert_awaited_once_with(_PARTNER_ID)
    assert result["data"]["compressed"] is True


async def test_journal_write_does_not_compress_when_under_or_equal_20():
    """journal_write does not trigger compression when count <= 20."""
    from zenos.interface.mcp.journal import journal_write

    repo = _make_journal_repo(count_return=20)
    compress_mock = AsyncMock()
    mock_pid, mock_partner = _make_partner_ctx()

    with (
        patch("zenos.interface.mcp._journal_repo", repo),
        patch("zenos.interface.mcp._ensure_journal_repo", AsyncMock()),
        patch("zenos.interface.mcp._compress_journal", compress_mock),
        patch("zenos.infrastructure.context.current_partner_id", mock_pid),
        patch("zenos.interface.mcp.journal._current_partner", mock_partner),
    ):
        result = await journal_write(summary="another entry")

    compress_mock.assert_not_awaited()
    assert result["data"]["compressed"] is False


# ---------------------------------------------------------------------------
# journal_read
# ---------------------------------------------------------------------------


async def test_journal_read_returns_entries_and_total():
    """journal_read returns entries, count, and total in data."""
    from zenos.interface.mcp.journal import journal_read

    entry = {
        "id": "e1",
        "created_at": _FIXED_TS,
        "project": "ZenOS",
        "flow_type": "feature",
        "summary": "done",
        "tags": [],
        "is_summary": False,
    }
    repo = _make_journal_repo(list_recent_return=([entry], 5))
    mock_pid, mock_partner = _make_partner_ctx()

    with (
        patch("zenos.interface.mcp._journal_repo", repo),
        patch("zenos.interface.mcp._ensure_journal_repo", AsyncMock()),
        patch("zenos.infrastructure.context.current_partner_id", mock_pid),
        patch("zenos.interface.mcp.journal._current_partner", mock_partner),
    ):
        result = await journal_read(limit=10)

    assert result["status"] == "ok"
    assert result["data"]["total"] == 5
    assert result["data"]["count"] == 1
    assert len(result["data"]["entries"]) == 1
    assert result["data"]["entries"][0]["summary"] == "done"


async def test_journal_read_clamps_limit_to_50():
    """journal_read enforces limit <= 50."""
    from zenos.interface.mcp.journal import journal_read

    repo = _make_journal_repo()
    mock_pid, mock_partner = _make_partner_ctx()

    with (
        patch("zenos.interface.mcp._journal_repo", repo),
        patch("zenos.interface.mcp._ensure_journal_repo", AsyncMock()),
        patch("zenos.infrastructure.context.current_partner_id", mock_pid),
        patch("zenos.interface.mcp.journal._current_partner", mock_partner),
    ):
        await journal_read(limit=999)

    call_kwargs = repo.list_recent.call_args[1]
    assert call_kwargs["limit"] == 50


async def test_journal_read_passes_project_filter():
    """journal_read passes project filter to repository."""
    from zenos.interface.mcp.journal import journal_read

    repo = _make_journal_repo()
    mock_pid, mock_partner = _make_partner_ctx()

    with (
        patch("zenos.interface.mcp._journal_repo", repo),
        patch("zenos.interface.mcp._ensure_journal_repo", AsyncMock()),
        patch("zenos.infrastructure.context.current_partner_id", mock_pid),
        patch("zenos.interface.mcp.journal._current_partner", mock_partner),
    ):
        await journal_read(limit=10, project="ZenOS")

    call_kwargs = repo.list_recent.call_args[1]
    assert call_kwargs["project"] == "ZenOS"


async def test_journal_read_serializes_datetime_to_string():
    """journal_read converts created_at datetime to ISO string."""
    from zenos.interface.mcp.journal import journal_read

    entry = {
        "id": "e1",
        "created_at": _FIXED_TS,
        "project": None,
        "flow_type": None,
        "summary": "test",
        "tags": [],
        "is_summary": False,
    }
    repo = _make_journal_repo(list_recent_return=([entry], 1))
    mock_pid, mock_partner = _make_partner_ctx()

    with (
        patch("zenos.interface.mcp._journal_repo", repo),
        patch("zenos.interface.mcp._ensure_journal_repo", AsyncMock()),
        patch("zenos.infrastructure.context.current_partner_id", mock_pid),
        patch("zenos.interface.mcp.journal._current_partner", mock_partner),
    ):
        result = await journal_read()

    created_at = result["data"]["entries"][0]["created_at"]
    assert isinstance(created_at, str)
    assert "2026-04-04" in created_at


# ---------------------------------------------------------------------------
# defaultProject auto-fill (QA regression tests)
# ---------------------------------------------------------------------------

_PARTNER_WITH_DEFAULT = {"id": _PARTNER_ID, "defaultProject": "zenos"}
_PARTNER_NO_DEFAULT = {"id": _PARTNER_ID}


async def test_journal_write_autofills_default_project():
    """journal_write uses partner defaultProject when project not passed."""
    from zenos.interface.mcp.journal import journal_write

    repo = _make_journal_repo()
    mock_pid, mock_partner = _make_partner_ctx(partner_data=_PARTNER_WITH_DEFAULT)

    with (
        patch("zenos.interface.mcp._journal_repo", repo),
        patch("zenos.interface.mcp._ensure_journal_repo", AsyncMock()),
        patch("zenos.infrastructure.context.current_partner_id", mock_pid),
        patch("zenos.interface.mcp.journal._current_partner", mock_partner),
    ):
        await journal_write(summary="test auto-fill")

    call_kwargs = repo.create.call_args[1]
    assert call_kwargs["project"] == "zenos"


async def test_journal_write_explicit_project_overrides_default():
    """journal_write uses explicit project even when defaultProject exists."""
    from zenos.interface.mcp.journal import journal_write

    repo = _make_journal_repo()
    mock_pid, mock_partner = _make_partner_ctx(partner_data=_PARTNER_WITH_DEFAULT)

    with (
        patch("zenos.interface.mcp._journal_repo", repo),
        patch("zenos.interface.mcp._ensure_journal_repo", AsyncMock()),
        patch("zenos.infrastructure.context.current_partner_id", mock_pid),
        patch("zenos.interface.mcp.journal._current_partner", mock_partner),
    ):
        await journal_write(summary="override test", project="paceriz")

    call_kwargs = repo.create.call_args[1]
    assert call_kwargs["project"] == "paceriz"


async def test_journal_write_no_default_project_passes_none():
    """journal_write passes None when partner has no defaultProject and caller omits project."""
    from zenos.interface.mcp.journal import journal_write

    repo = _make_journal_repo()
    mock_pid, mock_partner = _make_partner_ctx(partner_data=_PARTNER_NO_DEFAULT)

    with (
        patch("zenos.interface.mcp._journal_repo", repo),
        patch("zenos.interface.mcp._ensure_journal_repo", AsyncMock()),
        patch("zenos.infrastructure.context.current_partner_id", mock_pid),
        patch("zenos.interface.mcp.journal._current_partner", mock_partner),
    ):
        await journal_write(summary="no default")

    call_kwargs = repo.create.call_args[1]
    assert call_kwargs["project"] is None


async def test_journal_read_autofills_default_project():
    """journal_read uses partner defaultProject when project not passed."""
    from zenos.interface.mcp.journal import journal_read

    repo = _make_journal_repo()
    mock_pid, mock_partner = _make_partner_ctx(partner_data=_PARTNER_WITH_DEFAULT)

    with (
        patch("zenos.interface.mcp._journal_repo", repo),
        patch("zenos.interface.mcp._ensure_journal_repo", AsyncMock()),
        patch("zenos.infrastructure.context.current_partner_id", mock_pid),
        patch("zenos.interface.mcp.journal._current_partner", mock_partner),
    ):
        await journal_read()

    call_kwargs = repo.list_recent.call_args[1]
    assert call_kwargs["project"] == "zenos"


async def test_journal_read_explicit_project_overrides_default():
    """journal_read uses explicit project even when defaultProject exists."""
    from zenos.interface.mcp.journal import journal_read

    repo = _make_journal_repo()
    mock_pid, mock_partner = _make_partner_ctx(partner_data=_PARTNER_WITH_DEFAULT)

    with (
        patch("zenos.interface.mcp._journal_repo", repo),
        patch("zenos.interface.mcp._ensure_journal_repo", AsyncMock()),
        patch("zenos.infrastructure.context.current_partner_id", mock_pid),
        patch("zenos.interface.mcp.journal._current_partner", mock_partner),
    ):
        await journal_read(project="paceriz")

    call_kwargs = repo.list_recent.call_args[1]
    assert call_kwargs["project"] == "paceriz"


async def test_journal_read_no_default_project_passes_none():
    """journal_read passes None when partner has no defaultProject and caller omits project."""
    from zenos.interface.mcp.journal import journal_read

    repo = _make_journal_repo()
    mock_pid, mock_partner = _make_partner_ctx(partner_data=_PARTNER_NO_DEFAULT)

    with (
        patch("zenos.interface.mcp._journal_repo", repo),
        patch("zenos.interface.mcp._ensure_journal_repo", AsyncMock()),
        patch("zenos.infrastructure.context.current_partner_id", mock_pid),
        patch("zenos.interface.mcp.journal._current_partner", mock_partner),
    ):
        await journal_read()

    call_kwargs = repo.list_recent.call_args[1]
    assert call_kwargs["project"] is None
