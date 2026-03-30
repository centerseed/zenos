"""Tests for scripts/fix_entity_partner_ids.py.

Coverage
--------
- UpdateSummary.record and print_report output
- fetch_admin_partner_id: success, no admin, multiple admins
- fetch_affected_counts: query shape and result aggregation
- run_fix dry-run: queries counts, returns summary, makes no writes
- run_fix live: executes UPDATEs inside a transaction, parses command tags
- _parse_command_tag_count: normal values and edge cases
- main: missing DATABASE_URL exits with error

All SQL interactions are mocked via AsyncMock — no real DB required.

⚠️  Mock test note: SQL writes are not tested against a real PostgreSQL
instance. The UPDATE statements are verified by inspecting call arguments on
the mocked connection. A real integration test would require a running
PostgreSQL with the zenos schema.
"""

from __future__ import annotations

import asyncio
import io
import sys
from contextlib import redirect_stdout
from unittest.mock import AsyncMock, MagicMock, call, patch

import pytest

sys.path.insert(0, str(__import__("pathlib").Path(__file__).parents[2] / "scripts"))

from fix_entity_partner_ids import (  # noqa: E402
    PARTNER_ID_TABLES,
    UpdateSummary,
    _parse_command_tag_count,
    fetch_admin_partner_id,
    fetch_affected_counts,
    run_fix,
)

ADMIN_ID = "admin-partner-001"
OTHER_ID = "other-partner-002"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_conn(
    fetch_rows=None,
    fetchrow_side_effect=None,
    execute_side_effect=None,
) -> AsyncMock:
    """Build a minimal mock asyncpg.Connection."""
    conn = AsyncMock()

    if fetch_rows is not None:
        conn.fetch.return_value = fetch_rows

    if fetchrow_side_effect is not None:
        conn.fetchrow.side_effect = fetchrow_side_effect
    else:
        # Default: return 0 for every COUNT query
        conn.fetchrow.return_value = {"n": 0}

    if execute_side_effect is not None:
        conn.execute.side_effect = execute_side_effect
    else:
        conn.execute.return_value = "UPDATE 0"

    # transaction() is a regular (synchronous) method that returns an object
    # usable as an async context manager.  MagicMock supports __aenter__ and
    # __aexit__ natively when configured as coroutines.
    txn = MagicMock()
    txn.__aenter__ = AsyncMock(return_value=txn)
    txn.__aexit__ = AsyncMock(return_value=False)
    conn.transaction = MagicMock(return_value=txn)

    return conn


# ---------------------------------------------------------------------------
# UpdateSummary
# ---------------------------------------------------------------------------

class TestUpdateSummary:
    def test_record_accumulates(self):
        s = UpdateSummary()
        s.record("entities", 5)
        s.record("entities", 3)
        assert s.counts["entities"] == 8

    def test_print_report_dry_run_label(self):
        s = UpdateSummary()
        s.record("entities", 10)
        buf = io.StringIO()
        with redirect_stdout(buf):
            s.print_report(dry_run=True)
        output = buf.getvalue()
        assert "[DRY RUN]" in output
        assert "entities" in output
        assert "10" in output

    def test_print_report_live_no_dry_run_label(self):
        s = UpdateSummary()
        buf = io.StringIO()
        with redirect_stdout(buf):
            s.print_report(dry_run=False)
        assert "[DRY RUN]" not in buf.getvalue()

    def test_print_report_totals(self):
        s = UpdateSummary()
        s.record("entities", 4)
        s.record("tasks", 6)
        buf = io.StringIO()
        with redirect_stdout(buf):
            s.print_report(dry_run=False)
        assert "10" in buf.getvalue()  # total


# ---------------------------------------------------------------------------
# _parse_command_tag_count
# ---------------------------------------------------------------------------

class TestParseCommandTagCount:
    def test_update_tag(self):
        assert _parse_command_tag_count("UPDATE 42") == 42

    def test_update_zero(self):
        assert _parse_command_tag_count("UPDATE 0") == 0

    def test_unexpected_format_returns_zero(self):
        assert _parse_command_tag_count("") == 0
        assert _parse_command_tag_count("ERROR") == 0

    def test_large_number(self):
        assert _parse_command_tag_count("UPDATE 100000") == 100000


# ---------------------------------------------------------------------------
# fetch_admin_partner_id
# ---------------------------------------------------------------------------

class TestFetchAdminPartnerId:
    @pytest.mark.asyncio
    async def test_returns_admin_id(self):
        conn = _make_conn(fetch_rows=[{"id": ADMIN_ID}])
        result = await fetch_admin_partner_id(conn)
        assert result == ADMIN_ID

    @pytest.mark.asyncio
    async def test_raises_when_no_admin(self):
        conn = _make_conn(fetch_rows=[])
        with pytest.raises(RuntimeError, match="No admin partner found"):
            await fetch_admin_partner_id(conn)

    @pytest.mark.asyncio
    async def test_raises_when_multiple_admins(self):
        conn = _make_conn(fetch_rows=[{"id": "a1"}, {"id": "a2"}])
        with pytest.raises(RuntimeError, match="Multiple admin partners"):
            await fetch_admin_partner_id(conn)


# ---------------------------------------------------------------------------
# fetch_affected_counts
# ---------------------------------------------------------------------------

class TestFetchAffectedCounts:
    @pytest.mark.asyncio
    async def test_returns_count_per_table(self):
        # Return a different count for each table call
        counts_by_index = {i: i * 3 for i in range(len(PARTNER_ID_TABLES))}
        call_index = {"i": 0}

        async def fetchrow_side_effect(query, admin_id):
            n = counts_by_index[call_index["i"]]
            call_index["i"] += 1
            return {"n": n}

        conn = _make_conn(fetchrow_side_effect=fetchrow_side_effect)
        result = await fetch_affected_counts(conn, ADMIN_ID)

        assert len(result) == len(PARTNER_ID_TABLES)
        for idx, table in enumerate(PARTNER_ID_TABLES):
            assert result[table] == idx * 3

    @pytest.mark.asyncio
    async def test_query_uses_correct_param(self):
        conn = _make_conn()
        await fetch_affected_counts(conn, ADMIN_ID)
        # Every fetchrow call should pass ADMIN_ID as the partner_id param
        for c in conn.fetchrow.call_args_list:
            assert c.args[1] == ADMIN_ID


# ---------------------------------------------------------------------------
# run_fix — dry-run mode
# ---------------------------------------------------------------------------

class TestRunFixDryRun:
    @pytest.mark.asyncio
    async def test_dry_run_does_not_call_execute(self):
        """In dry-run mode, conn.execute must never be called (no writes)."""
        affected_counts = {t: 5 for t in PARTNER_ID_TABLES}

        async def fetchrow_side_effect(query, admin_id):
            return {"n": 5}

        conn = _make_conn(fetchrow_side_effect=fetchrow_side_effect)

        summary = await run_fix(conn, ADMIN_ID, dry_run=True)

        conn.execute.assert_not_called()
        conn.transaction.assert_not_called()

    @pytest.mark.asyncio
    async def test_dry_run_summary_reflects_counts(self):
        async def fetchrow_side_effect(query, admin_id):
            return {"n": 7}

        conn = _make_conn(fetchrow_side_effect=fetchrow_side_effect)
        summary = await run_fix(conn, ADMIN_ID, dry_run=True)

        for table in PARTNER_ID_TABLES:
            assert summary.counts.get(table, 0) == 7

    @pytest.mark.asyncio
    async def test_dry_run_nothing_to_do(self):
        """When all rows already use admin partner_id, summary should be all zeros."""
        conn = _make_conn()  # fetchrow default returns {"n": 0}
        buf = io.StringIO()
        with redirect_stdout(buf):
            summary = await run_fix(conn, ADMIN_ID, dry_run=True)
        assert "Nothing to do" in buf.getvalue()
        assert all(v == 0 for v in summary.counts.values())

    @pytest.mark.asyncio
    async def test_dry_run_prints_affected_rows(self):
        async def fetchrow_side_effect(query, admin_id):
            return {"n": 3}

        conn = _make_conn(fetchrow_side_effect=fetchrow_side_effect)
        buf = io.StringIO()
        with redirect_stdout(buf):
            await run_fix(conn, ADMIN_ID, dry_run=True)
        output = buf.getvalue()
        assert "[DRY RUN]" in output
        # At least one table should appear with count 3
        assert "3" in output


# ---------------------------------------------------------------------------
# run_fix — live mode
# ---------------------------------------------------------------------------

class TestRunFixLive:
    @pytest.mark.asyncio
    async def test_live_calls_execute_for_each_table(self):
        """Live mode must issue one UPDATE per table."""
        async def fetchrow_side_effect(query, admin_id):
            return {"n": 2}

        execute_calls = []

        async def execute_side_effect(query, *args):
            execute_calls.append((query, args))
            return "UPDATE 2"

        conn = _make_conn(
            fetchrow_side_effect=fetchrow_side_effect,
            execute_side_effect=execute_side_effect,
        )

        await run_fix(conn, ADMIN_ID, dry_run=False)

        # All calls should be UPDATE statements — one per table
        update_calls = [c for c in execute_calls if "UPDATE" in c[0]]
        assert len(update_calls) == len(PARTNER_ID_TABLES)

    @pytest.mark.asyncio
    async def test_live_update_uses_admin_id_param(self):
        """Every UPDATE statement must pass admin_id as the bind parameter."""
        async def fetchrow_side_effect(query, admin_id):
            return {"n": 1}

        async def execute_side_effect(query, *args):
            return "UPDATE 1"

        conn = _make_conn(
            fetchrow_side_effect=fetchrow_side_effect,
            execute_side_effect=execute_side_effect,
        )
        await run_fix(conn, ADMIN_ID, dry_run=False)

        for c in conn.execute.call_args_list:
            if "UPDATE" in c.args[0]:
                assert ADMIN_ID in c.args, (
                    f"ADMIN_ID not found in execute call args: {c.args}"
                )

    @pytest.mark.asyncio
    async def test_live_summary_counts_parsed_from_tag(self):
        async def fetchrow_side_effect(query, admin_id):
            return {"n": 5}

        call_index = {"i": 0}

        async def execute_side_effect(query, *args):
            count = call_index["i"] + 1
            call_index["i"] += 1
            return f"UPDATE {count}"

        conn = _make_conn(
            fetchrow_side_effect=fetchrow_side_effect,
            execute_side_effect=execute_side_effect,
        )
        summary = await run_fix(conn, ADMIN_ID, dry_run=False)

        # Counts should be parsed from command tags, not from the pre-check
        assert sum(summary.counts.values()) == sum(range(1, len(PARTNER_ID_TABLES) + 1))

    @pytest.mark.asyncio
    async def test_live_uses_transaction(self):
        """All UPDATEs must happen inside a transaction context manager."""
        async def fetchrow_side_effect(query, admin_id):
            return {"n": 1}

        conn = _make_conn(fetchrow_side_effect=fetchrow_side_effect)
        await run_fix(conn, ADMIN_ID, dry_run=False)

        conn.transaction.assert_called_once()

    @pytest.mark.asyncio
    async def test_live_no_execute_when_nothing_to_do(self):
        """When all counts are 0, skip transaction and UPDATEs entirely."""
        conn = _make_conn()  # fetchrow returns {"n": 0}
        await run_fix(conn, ADMIN_ID, dry_run=False)
        conn.execute.assert_not_called()
        conn.transaction.assert_not_called()


# ---------------------------------------------------------------------------
# main — missing DATABASE_URL
# ---------------------------------------------------------------------------

class TestMain:
    def test_missing_database_url_exits(self):
        """main() must sys.exit(1) when DATABASE_URL is not set."""
        from fix_entity_partner_ids import main as script_main

        with patch.dict("os.environ", {}, clear=True):
            # Remove DATABASE_URL if present
            import os
            os.environ.pop("DATABASE_URL", None)
            with pytest.raises(SystemExit) as exc_info:
                asyncio.run(script_main(dry_run=True))
            assert exc_info.value.code == 1
