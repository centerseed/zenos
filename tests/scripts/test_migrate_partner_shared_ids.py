"""Tests for scripts/migrate_partner_shared_ids.py.

Coverage
--------
- fetch_admin_partner: success, no admin, multiple admins
- fetch_partners_missing_shared_id: returns only unshared non-admin partners
- run_migration dry-run: prints summary, makes no writes
- run_migration live: executes UPDATE in a transaction
- _parse_command_tag_count: normal values and edge cases
- main: missing DATABASE_URL exits with error

All SQL interactions are mocked via AsyncMock — no real DB required.

⚠️  Mock test note: SQL writes are not tested against a real PostgreSQL instance.
The UPDATE statement is verified by inspecting call arguments on the mocked
connection.  A real integration test would require a running PostgreSQL with
the zenos schema.
"""

from __future__ import annotations

import asyncio
import io
import sys
from contextlib import redirect_stdout
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(__import__("pathlib").Path(__file__).parents[2] / "scripts"))

from migrate_partner_shared_ids import (  # noqa: E402
    _parse_command_tag_count,
    fetch_admin_partner,
    fetch_partners_missing_shared_id,
    run_migration,
)

ADMIN_ID = "admin-partner-001"
ADMIN_EMAIL = "admin@example.com"
AGENT_ID = "agent-partner-002"
AGENT_EMAIL = "agent@example.com"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_record(**kwargs) -> MagicMock:
    """Build a minimal mock asyncpg.Record."""
    rec = MagicMock()
    rec.__getitem__ = lambda self, key: kwargs[key]
    rec.__contains__ = lambda self, key: key in kwargs
    return rec


def _make_admin_record() -> MagicMock:
    return _make_record(id=ADMIN_ID, email=ADMIN_EMAIL)


def _make_agent_record() -> MagicMock:
    return _make_record(id=AGENT_ID, email=AGENT_EMAIL)


def _make_conn(
    fetch_side_effect=None,
    execute_return: str = "UPDATE 0",
) -> AsyncMock:
    """Build a minimal mock asyncpg.Connection."""
    conn = AsyncMock()

    if fetch_side_effect is not None:
        conn.fetch.side_effect = fetch_side_effect
    else:
        conn.fetch.return_value = []

    conn.execute.return_value = execute_return

    txn = MagicMock()
    txn.__aenter__ = AsyncMock(return_value=txn)
    txn.__aexit__ = AsyncMock(return_value=False)
    conn.transaction = MagicMock(return_value=txn)

    return conn


# ---------------------------------------------------------------------------
# _parse_command_tag_count
# ---------------------------------------------------------------------------

class TestParseCommandTagCount:
    def test_update_tag(self):
        assert _parse_command_tag_count("UPDATE 3") == 3

    def test_update_zero(self):
        assert _parse_command_tag_count("UPDATE 0") == 0

    def test_unexpected_format_returns_zero(self):
        assert _parse_command_tag_count("") == 0
        assert _parse_command_tag_count("ERROR") == 0

    def test_large_number(self):
        assert _parse_command_tag_count("UPDATE 10000") == 10000


# ---------------------------------------------------------------------------
# fetch_admin_partner
# ---------------------------------------------------------------------------

class TestFetchAdminPartner:
    @pytest.mark.asyncio
    async def test_returns_admin_record(self):
        conn = _make_conn(fetch_side_effect=[([_make_admin_record()])])
        conn.fetch.return_value = [_make_admin_record()]
        result = await fetch_admin_partner(conn)
        assert result["id"] == ADMIN_ID
        assert result["email"] == ADMIN_EMAIL

    @pytest.mark.asyncio
    async def test_raises_when_no_admin(self):
        conn = _make_conn()
        conn.fetch.return_value = []
        with pytest.raises(RuntimeError, match="No admin partner found"):
            await fetch_admin_partner(conn)

    @pytest.mark.asyncio
    async def test_raises_when_multiple_admins(self):
        conn = _make_conn()
        conn.fetch.return_value = [_make_admin_record(), _make_admin_record()]
        with pytest.raises(RuntimeError, match="Multiple admin partners found"):
            await fetch_admin_partner(conn)


# ---------------------------------------------------------------------------
# fetch_partners_missing_shared_id
# ---------------------------------------------------------------------------

class TestFetchPartnersMissingSharedId:
    @pytest.mark.asyncio
    async def test_returns_unshared_partners(self):
        conn = _make_conn()
        conn.fetch.return_value = [_make_agent_record()]
        result = await fetch_partners_missing_shared_id(conn, ADMIN_ID)
        assert len(result) == 1
        assert result[0]["id"] == AGENT_ID

    @pytest.mark.asyncio
    async def test_returns_empty_when_all_shared(self):
        conn = _make_conn()
        conn.fetch.return_value = []
        result = await fetch_partners_missing_shared_id(conn, ADMIN_ID)
        assert result == []

    @pytest.mark.asyncio
    async def test_query_passes_admin_id(self):
        conn = _make_conn()
        conn.fetch.return_value = []
        await fetch_partners_missing_shared_id(conn, ADMIN_ID)
        call_args = conn.fetch.call_args
        assert ADMIN_ID in call_args.args, "admin_id must be passed as query parameter"


# ---------------------------------------------------------------------------
# run_migration — dry-run mode
# ---------------------------------------------------------------------------

class TestRunMigrationDryRun:
    @pytest.mark.asyncio
    async def test_dry_run_does_not_call_execute(self):
        """Dry-run must not issue any UPDATE."""
        conn = _make_conn()
        conn.fetch.side_effect = [
            [_make_admin_record()],  # fetch_admin_partner
            [_make_agent_record()],  # fetch_partners_missing_shared_id
        ]

        buf = io.StringIO()
        with redirect_stdout(buf):
            await run_migration(conn, dry_run=True)

        conn.execute.assert_not_called()
        conn.transaction.assert_not_called()

    @pytest.mark.asyncio
    async def test_dry_run_prints_dry_run_label(self):
        conn = _make_conn()
        conn.fetch.side_effect = [
            [_make_admin_record()],
            [_make_agent_record()],
        ]

        buf = io.StringIO()
        with redirect_stdout(buf):
            await run_migration(conn, dry_run=True)

        assert "[DRY RUN]" in buf.getvalue()

    @pytest.mark.asyncio
    async def test_dry_run_nothing_to_do_when_no_affected(self):
        """Dry-run with no unshared partners prints nothing-to-do message."""
        conn = _make_conn()
        conn.fetch.side_effect = [
            [_make_admin_record()],
            [],  # no unshared partners
        ]

        buf = io.StringIO()
        with redirect_stdout(buf):
            await run_migration(conn, dry_run=True)

        assert "Nothing to do" in buf.getvalue()

    @pytest.mark.asyncio
    async def test_dry_run_prints_affected_partner_email(self):
        conn = _make_conn()
        conn.fetch.side_effect = [
            [_make_admin_record()],
            [_make_agent_record()],
        ]

        buf = io.StringIO()
        with redirect_stdout(buf):
            await run_migration(conn, dry_run=True)

        output = buf.getvalue()
        assert AGENT_EMAIL in output


# ---------------------------------------------------------------------------
# run_migration — live mode
# ---------------------------------------------------------------------------

class TestRunMigrationLive:
    @pytest.mark.asyncio
    async def test_live_calls_execute_with_admin_id(self):
        """Live mode must issue UPDATE with admin_id as first bind param."""
        conn = _make_conn(execute_return="UPDATE 1")
        conn.fetch.side_effect = [
            [_make_admin_record()],
            [_make_agent_record()],
        ]

        buf = io.StringIO()
        with redirect_stdout(buf):
            await run_migration(conn, dry_run=False)

        conn.execute.assert_called_once()
        call_args = conn.execute.call_args
        assert ADMIN_ID in call_args.args, (
            f"admin_id ({ADMIN_ID!r}) must be the first bind param in the UPDATE call"
        )

    @pytest.mark.asyncio
    async def test_live_uses_transaction(self):
        """All UPDATEs must happen inside a transaction."""
        conn = _make_conn(execute_return="UPDATE 1")
        conn.fetch.side_effect = [
            [_make_admin_record()],
            [_make_agent_record()],
        ]

        buf = io.StringIO()
        with redirect_stdout(buf):
            await run_migration(conn, dry_run=False)

        conn.transaction.assert_called_once()

    @pytest.mark.asyncio
    async def test_live_no_execute_when_nothing_to_do(self):
        """When all partners already have shared_partner_id, skip UPDATE."""
        conn = _make_conn()
        conn.fetch.side_effect = [
            [_make_admin_record()],
            [],  # no unshared partners
        ]

        buf = io.StringIO()
        with redirect_stdout(buf):
            await run_migration(conn, dry_run=False)

        conn.execute.assert_not_called()
        conn.transaction.assert_not_called()

    @pytest.mark.asyncio
    async def test_live_no_dry_run_label_in_output(self):
        conn = _make_conn(execute_return="UPDATE 1")
        conn.fetch.side_effect = [
            [_make_admin_record()],
            [_make_agent_record()],
        ]

        buf = io.StringIO()
        with redirect_stdout(buf):
            await run_migration(conn, dry_run=False)

        assert "[DRY RUN]" not in buf.getvalue()


# ---------------------------------------------------------------------------
# main — missing DATABASE_URL
# ---------------------------------------------------------------------------

class TestMain:
    def test_missing_database_url_exits(self):
        """main() must sys.exit(1) when DATABASE_URL is not set."""
        from migrate_partner_shared_ids import main as script_main

        import os
        with patch.dict("os.environ", {}, clear=True):
            os.environ.pop("DATABASE_URL", None)
            with pytest.raises(SystemExit) as exc_info:
                asyncio.run(script_main(dry_run=True))
            assert exc_info.value.code == 1
