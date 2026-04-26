"""Static checks for DF-20260424-4 entities_base legacy entity backfill."""

from __future__ import annotations

from pathlib import Path


_REPO_ROOT = Path(__file__).parents[2]
_MIGRATION_PATH = (
    _REPO_ROOT / "migrations" / "20260424_0006_entities_base_legacy_entity_backfill.sql"
)


def _load_migration() -> str:
    return _MIGRATION_PATH.read_text(encoding="utf-8")


def test_migration_file_exists():
    assert _MIGRATION_PATH.exists()


def test_backfills_legacy_entities_into_entities_base():
    sql = _load_migration()

    assert "INSERT INTO zenos.entities_base" in sql
    assert "FROM zenos.entities e" in sql
    assert "ON CONFLICT (partner_id, id) DO UPDATE SET" in sql


def test_excludes_goal_entities_for_milestone_path():
    sql = _load_migration()

    assert "WHERE e.type <> 'goal'" in sql
    assert "entity_l3_milestone" in sql
    assert "type_label='milestone'" in sql


def test_preserves_visibility_arrays_and_level_one_parent_rule():
    sql = _load_migration()

    assert "COALESCE(e.visible_to_roles, '{}'::text[])" in sql
    assert "COALESCE(e.visible_to_members, '{}'::text[])" in sql
    assert "COALESCE(e.visible_to_departments, '{}'::text[])" in sql
    assert "WHEN 'module' THEN 2" in sql
    assert "WHEN 'document' THEN 3" in sql
    assert "WHEN 'product' THEN 1" in sql
    assert "WHEN 'deal' THEN 1" in sql
    assert "WHEN 'person' THEN 1" in sql
    assert "WHEN 'company' THEN 1" in sql
    assert "THEN NULL" in sql
    assert "ELSE e.parent_id" in sql
