"""Static checks for Wave 9 Phase D03a legacy action shadow tables."""

from __future__ import annotations

from pathlib import Path


_REPO_ROOT = Path(__file__).parents[2]
_MIGRATION_PATH = _REPO_ROOT / "migrations" / "20260424_0001_wave9_legacy_action_shadow_tables.sql"


def _sql() -> str:
    return _MIGRATION_PATH.read_text(encoding="utf-8")


def test_shadow_table_migration_exists():
    assert _MIGRATION_PATH.exists()


def test_legacy_orphan_tasks_shape():
    sql = _sql()
    assert "CREATE TABLE IF NOT EXISTS zenos.legacy_orphan_tasks" in sql
    for column in (
        "task_id",
        "partner_id",
        "reason",
        "detected_at",
        "resolved_at",
        "resolver_partner_id",
        "manual_parent_id",
    ):
        assert column in sql
    assert "PRIMARY KEY (partner_id, task_id)" in sql


def test_legacy_parent_chain_warnings_shape():
    sql = _sql()
    assert "CREATE TABLE IF NOT EXISTS zenos.legacy_parent_chain_warnings" in sql
    for column in ("task_id", "partner_id", "chain_snapshot_json", "detected_at", "triaged_at"):
        assert column in sql
    assert "PRIMARY KEY (partner_id, task_id)" in sql


def test_shadow_tables_are_indexed_for_unresolved_triage():
    sql = _sql()
    assert "idx_legacy_orphan_tasks_unresolved" in sql
    assert "WHERE resolved_at IS NULL" in sql
    assert "idx_legacy_parent_chain_warnings_untriaged" in sql
    assert "WHERE triaged_at IS NULL" in sql
