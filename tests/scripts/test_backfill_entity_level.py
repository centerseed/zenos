"""Tests for scripts/backfill_entity_level.py.

Test strategy
-------------
All DB interactions are exercised through AsyncMock / in-memory state — no
real PostgreSQL required.  The script's core logic (classify_rows, build_by_type,
report builders) is tested directly as pure functions; the async DB layer is
tested by patching ``asyncpg.Connection`` methods.

Tests
-----
1. test_dry_run_reports_level_null_entities          — report structure correctness
2. test_dry_run_does_not_mutate_db                   — no execute() called in dry-run
3. test_apply_updates_inferable_entities             — correct UPDATE issued per row
4. test_apply_skips_unresolvable_types               — unknown types listed, not updated
5. test_apply_writes_snapshot                        — snapshot JSONL content correct
6. test_apply_refuses_without_snapshot_path          — parse_args exits on missing flag
7. test_default_type_levels_contains_all_l1_crm_types — product/company/person/deal → 1
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

# ---------------------------------------------------------------------------
# Bootstrap: put scripts/ on sys.path so we can import the module
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "scripts"))
sys.path.insert(0, str(_REPO_ROOT / "src"))

import backfill_entity_level as bfe  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def _make_row(
    entity_id: str,
    entity_type: str,
    name: str = "Test Entity",
    level: int | None = None,
    parent_id: str | None = None,
) -> dict[str, Any]:
    return {
        "id": entity_id,
        "name": name,
        "type": entity_type,
        "level": level,
        "parent_id": parent_id,
    }


def _make_conn(rows: list[dict] | None = None) -> MagicMock:
    """Fake asyncpg connection.

    ``fetch`` returns the given rows; ``execute`` records calls and returns
    'UPDATE 1' so _parse_command_tag_count works correctly.
    """
    conn = MagicMock()
    conn.fetch = AsyncMock(return_value=rows or [])
    conn.execute = AsyncMock(return_value="UPDATE 1")
    return conn


# ---------------------------------------------------------------------------
# 1. test_dry_run_reports_level_null_entities
# ---------------------------------------------------------------------------

def test_dry_run_reports_level_null_entities(tmp_path: Path) -> None:
    """Dry-run produces a report with correct structure and counts."""
    rows = [
        _make_row("aaa", "product"),
        _make_row("bbb", "company"),
        _make_row("ccc", "unknown_alien_type"),
    ]
    conn = _make_conn(rows)

    report_file = tmp_path / "report.json"

    async def _run() -> None:
        await bfe.run_dry_run(conn, str(report_file))

    asyncio.run(_run())

    assert report_file.exists(), "Report file should be created when --output is given"
    report = json.loads(report_file.read_text())

    assert report["mode"] == "dry-run"
    assert report["total"] == 3
    assert report["by_type"] == {"product": 1, "company": 1, "unknown_alien_type": 1}
    assert report["snapshot_path"] is None

    # Two resolvable rows
    assert len(report["would_update"]) == 2
    update_ids = {r["id"] for r in report["would_update"]}
    assert update_ids == {"aaa", "bbb"}

    new_levels = {r["id"]: r["new_level"] for r in report["would_update"]}
    assert new_levels["aaa"] == 1
    assert new_levels["bbb"] == 1

    # One unresolvable row
    assert len(report["unresolvable"]) == 1
    assert report["unresolvable"][0]["id"] == "ccc"
    assert report["unresolvable"][0]["type"] == "unknown_alien_type"


# ---------------------------------------------------------------------------
# 2. test_dry_run_does_not_mutate_db
# ---------------------------------------------------------------------------

def test_dry_run_does_not_mutate_db() -> None:
    """Dry-run must not call conn.execute() (no UPDATEs issued)."""
    rows = [
        _make_row("x1", "product"),
        _make_row("x2", "module"),
    ]
    conn = _make_conn(rows)

    async def _run() -> None:
        await bfe.run_dry_run(conn, None)

    asyncio.run(_run())

    conn.execute.assert_not_called()


# ---------------------------------------------------------------------------
# 3. test_apply_updates_inferable_entities
# ---------------------------------------------------------------------------

def test_apply_updates_inferable_entities(tmp_path: Path) -> None:
    """Apply mode issues one UPDATE per resolvable row with the correct level."""
    rows = [
        _make_row("e1", "product"),
        _make_row("e2", "module"),
        _make_row("e3", "document"),
    ]
    conn = _make_conn(rows)
    snap = tmp_path / "snap.jsonl"

    async def _run() -> None:
        await bfe.run_apply(conn, str(snap), None)

    asyncio.run(_run())

    # Three entities, all resolvable → three UPDATEs
    assert conn.execute.call_count == 3

    # Verify each call used the correct level
    expected = {
        "e1": 1,   # product
        "e2": 2,   # module
        "e3": 3,   # document
    }
    for c in conn.execute.call_args_list:
        sql, level, entity_id = c.args
        assert "SET level" in sql, "SQL must be an UPDATE SET level statement"
        assert level == expected[entity_id], (
            f"Entity {entity_id}: expected level {expected[entity_id]}, got {level}"
        )


# ---------------------------------------------------------------------------
# 4. test_apply_skips_unresolvable_types
# ---------------------------------------------------------------------------

def test_apply_skips_unresolvable_types(tmp_path: Path) -> None:
    """Unknown types must NOT be updated and must appear in skipped_unresolvable."""
    rows = [
        _make_row("good1", "company"),
        _make_row("bad1", "widget"),
        _make_row("bad2", "foobar"),
    ]
    conn = _make_conn(rows)
    snap = tmp_path / "snap.jsonl"
    report_file = tmp_path / "report.json"

    async def _run() -> None:
        await bfe.run_apply(conn, str(snap), str(report_file))

    asyncio.run(_run())

    # Only one UPDATE — for the resolvable "company" row
    assert conn.execute.call_count == 1
    _, level, entity_id = conn.execute.call_args.args
    assert entity_id == "good1"
    assert level == 1

    report = json.loads(report_file.read_text())
    assert report["updated"] == 1
    assert len(report["skipped_unresolvable"]) == 2
    skipped_ids = {r["id"] for r in report["skipped_unresolvable"]}
    assert skipped_ids == {"bad1", "bad2"}
    skipped_types = {r["type"] for r in report["skipped_unresolvable"]}
    assert skipped_types == {"widget", "foobar"}


# ---------------------------------------------------------------------------
# 5. test_apply_writes_snapshot
# ---------------------------------------------------------------------------

def test_apply_writes_snapshot(tmp_path: Path) -> None:
    """Snapshot JSONL must be written before any UPDATE, one line per resolvable row."""
    rows = [
        _make_row("snap1", "person"),
        _make_row("snap2", "deal"),
    ]
    conn = _make_conn(rows)
    snap = tmp_path / "rollback.jsonl"

    async def _run() -> None:
        await bfe.run_apply(conn, str(snap), None)

    asyncio.run(_run())

    assert snap.exists(), "Snapshot file must be created"
    lines = snap.read_text().strip().splitlines()
    assert len(lines) == 2, "One snapshot line per resolvable entity"

    parsed = [json.loads(line) for line in lines]
    snap_ids = {p["id"] for p in parsed}
    assert snap_ids == {"snap1", "snap2"}

    # Every snapshot entry must record level=null (the pre-backfill state)
    for p in parsed:
        assert p["level"] is None, "Snapshot must preserve old level (null)"


# ---------------------------------------------------------------------------
# 6. test_apply_refuses_without_snapshot_path
# ---------------------------------------------------------------------------

def test_apply_refuses_without_snapshot_path() -> None:
    """--apply without --snapshot-path must exit with non-zero code and clear error."""
    with pytest.raises(SystemExit) as exc_info:
        bfe.parse_args(["--apply"])
    assert exc_info.value.code != 0, "Should exit with non-zero code"


def test_apply_refuses_without_snapshot_path_error_message(capsys: pytest.CaptureFixture) -> None:
    """Error message should mention --snapshot-path."""
    with pytest.raises(SystemExit):
        bfe.parse_args(["--apply"])
    captured = capsys.readouterr()
    # argparse writes to stderr
    assert "snapshot-path" in captured.err, (
        "Error message must mention --snapshot-path so the user knows what to add"
    )


# ---------------------------------------------------------------------------
# 7. test_default_type_levels_contains_all_l1_crm_types
# ---------------------------------------------------------------------------

def test_default_type_levels_contains_all_l1_crm_types() -> None:
    """product, company, person, deal must all map to level 1 (AC-L1SSOT-01 prerequisite)."""
    from zenos.domain.knowledge.entity_levels import DEFAULT_TYPE_LEVELS

    l1_crm_types = {"product", "company", "person", "deal"}
    for t in l1_crm_types:
        assert t in DEFAULT_TYPE_LEVELS, f"'{t}' missing from DEFAULT_TYPE_LEVELS"
        assert DEFAULT_TYPE_LEVELS[t] == 1, f"'{t}' must map to level 1, got {DEFAULT_TYPE_LEVELS[t]}"


# ---------------------------------------------------------------------------
# Additional unit tests for pure helpers
# ---------------------------------------------------------------------------

def test_classify_rows_known_types() -> None:
    """classify_rows correctly splits by DEFAULT_TYPE_LEVELS membership."""
    rows = [
        _make_row("a", "product"),
        _make_row("b", "module"),
        _make_row("c", "role"),
        _make_row("d", "mystery_type"),
    ]
    resolvable, unresolvable = bfe.classify_rows(rows)

    assert len(resolvable) == 3
    assert len(unresolvable) == 1
    assert unresolvable[0]["id"] == "d"
    assert unresolvable[0]["type"] == "mystery_type"

    level_by_id = {r["id"]: r["new_level"] for r in resolvable}
    assert level_by_id["a"] == 1   # product
    assert level_by_id["b"] == 2   # module
    assert level_by_id["c"] == 3   # role


def test_classify_rows_never_defaults_unknown_to_one() -> None:
    """Unknown types must NEVER be silently defaulted to level 1."""
    rows = [_make_row("x", "totally_unknown_type")]
    resolvable, unresolvable = bfe.classify_rows(rows)

    assert len(resolvable) == 0, "Unknown type must NOT appear in resolvable"
    assert len(unresolvable) == 1
    # Crucially: no new_level key on unresolvable rows
    assert "new_level" not in unresolvable[0]


def test_build_by_type() -> None:
    rows = [
        _make_row("1", "product"),
        _make_row("2", "product"),
        _make_row("3", "company"),
    ]
    result = bfe.build_by_type(rows)
    assert result == {"product": 2, "company": 1}


def test_dry_run_report_structure_snapshot_path_is_null() -> None:
    """Dry-run report always has snapshot_path: null."""
    rows = [_make_row("id1", "product")]
    resolvable, unresolvable = bfe.classify_rows(rows)
    report = bfe.build_dry_run_report(rows, resolvable, unresolvable)
    assert report["snapshot_path"] is None
    assert report["mode"] == "dry-run"


def test_apply_report_includes_snapshot_path() -> None:
    """Apply report must include the actual snapshot path."""
    rows = [_make_row("id1", "product")]
    resolvable, unresolvable = bfe.classify_rows(rows)
    report = bfe.build_apply_report(rows, resolvable, unresolvable, 1, "/tmp/snap.jsonl")
    assert report["snapshot_path"] == "/tmp/snap.jsonl"
    assert report["mode"] == "apply"
    assert report["updated"] == 1


def test_default_level_for_type_helper() -> None:
    """default_level_for_type returns correct values and None for unknown."""
    from zenos.domain.knowledge.entity_levels import default_level_for_type

    assert default_level_for_type("product") == 1
    assert default_level_for_type("company") == 1
    assert default_level_for_type("module") == 2
    assert default_level_for_type("document") == 3
    assert default_level_for_type("nonexistent") is None


# ---------------------------------------------------------------------------
# QA-added: blind spot coverage
# ---------------------------------------------------------------------------

def test_emit_report_stdout_path(capsys: pytest.CaptureFixture) -> None:
    """emit_report(report, output_path=None) writes valid JSON to stdout."""
    report = {
        "mode": "dry-run",
        "total": 2,
        "by_type": {"product": 2},
        "unresolvable": [],
        "would_update": [],
        "snapshot_path": None,
    }
    bfe.emit_report(report, None)
    captured = capsys.readouterr()
    parsed = json.loads(captured.out)
    assert parsed["mode"] == "dry-run"
    assert parsed["total"] == 2
    assert parsed["snapshot_path"] is None


def test_emit_report_file_path(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    """emit_report(report, output_path=<file>) writes to file, not stdout."""
    report = {"mode": "apply", "total": 1}
    out_file = tmp_path / "out.json"
    bfe.emit_report(report, str(out_file))
    captured = capsys.readouterr()
    # File must exist and be valid JSON
    assert out_file.exists()
    assert json.loads(out_file.read_text())["mode"] == "apply"
    # Nothing written to stdout
    assert captured.out == ""
    # Confirmation message goes to stderr
    assert "Report written to" in captured.err


def test_parse_command_tag_count_edge_cases() -> None:
    """_parse_command_tag_count handles normal, zero, empty, and malformed tags."""
    # Normal asyncpg tags
    assert bfe._parse_command_tag_count("UPDATE 1") == 1
    assert bfe._parse_command_tag_count("UPDATE 5") == 5
    # Zero-row update (entity already had a level or was deleted between scan and apply)
    assert bfe._parse_command_tag_count("UPDATE 0") == 0
    # Empty string — must return 0, not raise
    assert bfe._parse_command_tag_count("") == 0
    # Non-numeric last token — must return 0, not raise
    assert bfe._parse_command_tag_count("UPDATE NOTANUMBER") == 0
    # Completely unexpected tag format — must return 0
    assert bfe._parse_command_tag_count("SOME_TAG") == 0
    # INSERT tag (wrong command, defensive) — last token is a number, still parsed
    assert bfe._parse_command_tag_count("INSERT 0 1") == 1


def test_apply_refuses_without_database_url(monkeypatch: pytest.MonkeyPatch) -> None:
    """main() exits non-zero when DATABASE_URL is not set."""
    monkeypatch.delenv("DATABASE_URL", raising=False)

    ns = bfe.parse_args(["--dry-run"])
    with pytest.raises(SystemExit) as exc_info:
        asyncio.run(bfe.main(ns))
    assert exc_info.value.code != 0
