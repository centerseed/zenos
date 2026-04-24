"""Tests for scripts/backfill_l3_action_parent_id.py."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "scripts"))

import backfill_l3_action_parent_id as backfill  # noqa: E402


def _task_row(**overrides):
    row = {
        "id": "task1",
        "partner_id": "p1",
        "parent_task_id": None,
        "plan_id": None,
        "product_id": None,
    }
    row.update(overrides)
    return row


def _conn(fetch_rows=None) -> MagicMock:
    conn = MagicMock()
    conn.fetch = AsyncMock(return_value=fetch_rows or [])
    conn.execute = AsyncMock(return_value="INSERT 0 1")
    conn.executemany = AsyncMock()
    tx = MagicMock()
    tx.__aenter__ = AsyncMock(return_value=None)
    tx.__aexit__ = AsyncMock(return_value=None)
    conn.transaction = MagicMock(return_value=tx)
    return conn


def test_compute_task_parent_id_prefers_subtask_then_plan_then_product():
    assert backfill.compute_task_parent_id(_task_row(parent_task_id="parent", plan_id="plan", product_id="prod")) == "parent"
    assert backfill.compute_task_parent_id(_task_row(plan_id="plan", product_id="prod")) == "plan"
    assert backfill.compute_task_parent_id(_task_row(product_id="prod")) == "prod"
    assert backfill.compute_task_parent_id(_task_row()) is None


def test_classify_task_rows_reports_orphans_without_guessing():
    rows = [
        _task_row(id="task-plan", plan_id="plan1"),
        _task_row(id="task-orphan"),
    ]
    resolvable, orphaned = backfill.classify_task_rows(rows)

    assert [r["id"] for r in resolvable] == ["task-plan"]
    assert resolvable[0]["computed_parent_id"] == "plan1"
    assert [r["id"] for r in orphaned] == ["task-orphan"]
    assert orphaned[0]["reason"] == "NO_PARENT_SOURCE"


def test_status_normalizers_match_phase_d_target_enums():
    assert backfill._status_to_task_status("backlog") == "todo"
    assert backfill._status_to_task_status("blocked") == "todo"
    assert backfill._status_to_task_status("archived") == "done"
    assert backfill._status_to_plan_status(None) == "draft"
    assert backfill._status_to_milestone_status("archived") == "cancelled"


def test_dry_run_returns_gate_failure_when_orphans_exist():
    task = _task_row(id="orphan")
    conn = _conn()
    conn.fetch = AsyncMock(side_effect=[[task], [], []])

    code = asyncio.run(backfill.run_dry_run(conn, None))

    assert code == 3
    conn.execute.assert_not_called()


def test_apply_uses_transaction_and_records_parent_chain_warnings():
    conn = _conn()
    conn.fetch = AsyncMock(side_effect=[
        [_task_row(id="task1", product_id="prod1")],  # fetch_task_candidates
        [],                                          # fetch_plan_candidates
        [],                                          # fetch_milestone_candidates
        [{"partner_id": "p1", "entity_id": "task1", "type_label": "task", "parent_id": None, "reason": "MISSING_PARENT_ID"}],
    ])

    code = asyncio.run(backfill.run_apply(conn, None))

    assert code == 3
    conn.transaction.assert_called_once()
    assert conn.execute.call_count >= 5
    conn.executemany.assert_called_once()
