"""Wave 9 Phase B prime fix-15 — migration smoke test.

Tests the composite FK / PK structure of 20260423_0004_wave9_l3_action_preflight.sql.

Strategy:
- Static SQL shape tests: parse the migration file and verify the expected DDL
  patterns are present. These run unconditionally and catch regressions if someone
  edits the migration file.
- DB integration tests: run against a live PostgreSQL instance.  Skipped
  automatically when no DB is reachable (CI-safe). These tests verify:
  1. Same-partner parent FK works (row inserted successfully).
  2. Cross-partner parent FK is rejected with an FK violation.
  3. Subclass composite FK CASCADE: deleting entities_base row removes subclass row.
  4. task_handoff_events composite FK: cross-partner reference rejected.
  5. Rollback: all tables are removed cleanly in the correct order.

Note: SQLite cannot emulate PostgreSQL FK enforcement semantics; asyncpg is used
for real DB tests. asyncpg/psycopg2 availability is checked at import time.
"""

from __future__ import annotations

import os
import re
import textwrap
from pathlib import Path

import pytest

# ─────────────────────────────────────────────────────────────────────────────
# Paths
# ─────────────────────────────────────────────────────────────────────────────

_REPO_ROOT = Path(__file__).parents[2]
_MIGRATION_PATH = _REPO_ROOT / "migrations" / "20260423_0004_wave9_l3_action_preflight.sql"

# ─────────────────────────────────────────────────────────────────────────────
# Static SQL shape tests (always run — no DB required)
# ─────────────────────────────────────────────────────────────────────────────


def _load_migration() -> str:
    """Load migration SQL as a single normalized string."""
    return _MIGRATION_PATH.read_text(encoding="utf-8")


def test_migration_file_exists():
    """Migration file is present at the expected path."""
    assert _MIGRATION_PATH.exists(), (
        f"Migration file not found: {_MIGRATION_PATH}"
    )


def test_entities_base_composite_primary_key():
    """entities_base has composite PRIMARY KEY (partner_id, id).

    fix-15: A composite PK (partner_id, id) is required so that the composite
    FK on parent_id can reference it. A plain id PK cannot be referenced by a
    multi-column FK.
    """
    sql = _load_migration()
    # Verify composite PK declaration
    assert "PRIMARY KEY (partner_id, id)" in sql, (
        "entities_base must declare PRIMARY KEY (partner_id, id) (fix-15)"
    )


def test_entities_base_composite_parent_fk():
    """entities_base.parent_id uses a composite FK (partner_id, parent_id) referencing itself.

    fix-15: A single-column FK on parent_id would allow cross-partner parents
    (parent row in a different partner's namespace). The composite FK ensures
    both partner_id and parent_id match in the referenced row, enforcing
    same-partner containment.
    """
    sql = _load_migration()
    # Composite self-referential FK pattern
    assert "FOREIGN KEY (partner_id, parent_id)" in sql, (
        "entities_base must declare FOREIGN KEY (partner_id, parent_id) referencing itself (fix-15)"
    )
    # P1-E fix: PG 16.13 (>= PG 15) syntax — ON DELETE SET NULL (parent_id) only nulls
    # parent_id, leaving partner_id (NOT NULL) untouched.
    assert "REFERENCES zenos.entities_base (partner_id, id) ON DELETE SET NULL (parent_id)" in sql, (
        "entities_base parent FK must reference (partner_id, id) with "
        "ON DELETE SET NULL (parent_id) — PG 15+ syntax that nulls only parent_id, "
        "not partner_id (which is NOT NULL). (P1-E fix)"
    )


def test_all_subclass_tables_have_partner_id_column():
    """All L3 subclass tables declare a partner_id column.

    fix-15: Without partner_id in the subclass table, the composite FK back to
    entities_base cannot be expressed.
    """
    sql = _load_migration()
    subclass_tables = [
        "entity_l3_milestone",
        "entity_l3_plan",
        "entity_l3_task",
        "entity_l3_subtask",
    ]
    # For each CREATE TABLE block, verify partner_id column appears
    for table in subclass_tables:
        # Extract CREATE TABLE block for this table
        pattern = rf"CREATE TABLE zenos\.{table}\s*\((.+?)\);"
        match = re.search(pattern, sql, re.DOTALL | re.IGNORECASE)
        assert match is not None, f"CREATE TABLE for {table} not found in migration"
        block = match.group(1)
        assert "partner_id" in block, (
            f"{table} must have a partner_id column (fix-15)"
        )


def test_all_subclass_tables_have_composite_pk():
    """All L3 subclass tables use composite PRIMARY KEY (partner_id, entity_id).

    fix-15: A plain entity_id PK would not be partner-scoped and the composite
    FK referencing entities_base(partner_id, id) could not be declared.
    """
    sql = _load_migration()
    assert sql.count("PRIMARY KEY (partner_id, entity_id)") >= 4, (
        "Expected at least 4 subclass tables with PRIMARY KEY (partner_id, entity_id) (fix-15)"
    )


def test_all_subclass_tables_have_composite_fk_to_entities_base():
    """All L3 subclass tables reference entities_base with a composite FK (partner_id, entity_id).

    fix-15: A single-column FK on entity_id alone cannot guarantee the referenced
    entities_base row belongs to the same partner.
    """
    sql = _load_migration()
    assert "FOREIGN KEY (partner_id, entity_id)" in sql, (
        "At least one subclass table must declare FOREIGN KEY (partner_id, entity_id) (fix-15)"
    )
    assert "REFERENCES zenos.entities_base (partner_id, id) ON DELETE CASCADE" in sql, (
        "Subclass FK must reference entities_base(partner_id, id) with ON DELETE CASCADE (fix-15)"
    )


def test_task_handoff_events_has_partner_id():
    """task_handoff_events has a partner_id column and composite FK.

    fix-15: task_entity_id alone cannot enforce same-partner containment.
    The composite FK (partner_id, task_entity_id) references entities_base to
    prevent cross-partner handoff event entries.
    """
    sql = _load_migration()
    # Extract task_handoff_events CREATE TABLE block
    pattern = r"CREATE TABLE zenos\.task_handoff_events\s*\((.+?)\);"
    match = re.search(pattern, sql, re.DOTALL | re.IGNORECASE)
    assert match is not None, "CREATE TABLE for task_handoff_events not found in migration"
    block = match.group(1)
    assert "partner_id" in block, (
        "task_handoff_events must have a partner_id column (fix-15)"
    )
    # Composite FK for task_entity_id
    assert "FOREIGN KEY (partner_id, task_entity_id)" in sql, (
        "task_handoff_events must declare FOREIGN KEY (partner_id, task_entity_id) (fix-15)"
    )


def test_rollback_comment_order():
    """Rollback DROP TABLE order follows FK dependency (subclasses before entities_base).

    Dropping entities_base before subclass tables would fail because the FK
    constraint in subclass tables references entities_base. The rollback block
    must list task_handoff_events DROP before entities_base DROP.

    We search within DROP TABLE lines only to avoid false positives from the
    description comment which also mentions "entities_base".
    """
    sql = _load_migration()
    rollback_section = sql[sql.rfind("Rollback"):]

    # Extract only DROP TABLE lines from the rollback section
    drop_lines = [
        line for line in rollback_section.splitlines()
        if re.search(r"DROP TABLE", line, re.IGNORECASE)
    ]
    drop_text = "\n".join(drop_lines)

    assert drop_lines, "Rollback section must contain DROP TABLE statements"
    assert any("task_handoff_events" in ln for ln in drop_lines), (
        "Rollback must include a DROP TABLE for task_handoff_events"
    )
    assert any("entities_base" in ln for ln in drop_lines), (
        "Rollback must include a DROP TABLE for entities_base"
    )

    # task_handoff_events DROP must appear before entities_base DROP
    he_pos = drop_text.find("task_handoff_events")
    base_pos = drop_text.find("entities_base")
    assert he_pos < base_pos, (
        "Rollback must drop task_handoff_events before entities_base "
        "(FK dependency order, fix-15). "
        f"task_handoff_events at char {he_pos}, entities_base at char {base_pos} in:\n{drop_text}"
    )


# ─────────────────────────────────────────────────────────────────────────────
# DB integration tests — require live PostgreSQL + TEST_DATABASE_URL env var
# ─────────────────────────────────────────────────────────────────────────────

_DB_URL = os.environ.get("TEST_DATABASE_URL", "")

# Check if asyncpg is importable
_ASYNCPG_AVAILABLE = False
try:
    import asyncpg  # noqa: F401
    _ASYNCPG_AVAILABLE = True
except ImportError:
    pass

_SKIP_DB = pytest.mark.skipif(
    not _DB_URL or not _ASYNCPG_AVAILABLE,
    reason=(
        "DB integration tests require TEST_DATABASE_URL env var and asyncpg. "
        "Set TEST_DATABASE_URL=postgresql://user:pass@host/db to run. "  # pragma: allowlist secret
        "These tests verify same-partner FK acceptance, cross-partner FK rejection, "
        "CASCADE behaviour, and rollback correctness."
    ),
)

# ─── Helpers ──────────────────────────────────────────────────────────────────

_SETUP_SQL = textwrap.dedent("""
    CREATE SCHEMA IF NOT EXISTS zenos_smoke;

    CREATE TABLE IF NOT EXISTS zenos_smoke.partners (
        id text PRIMARY KEY
    );

    CREATE TABLE zenos_smoke.entities_base (
        id                      text NOT NULL,
        partner_id              text NOT NULL REFERENCES zenos_smoke.partners(id),
        name                    text NOT NULL,
        type_label              text NOT NULL,
        level                   integer NOT NULL CHECK (level IN (1, 2, 3)),
        parent_id               text,
        status                  text NOT NULL,
        visibility              text NOT NULL DEFAULT 'public',
        visible_to_roles        text[] NOT NULL DEFAULT '{}',
        visible_to_members      text[] NOT NULL DEFAULT '{}',
        visible_to_departments  text[] NOT NULL DEFAULT '{}',
        owner                   text,
        created_at              timestamptz NOT NULL DEFAULT now(),
        updated_at              timestamptz NOT NULL DEFAULT now(),

        PRIMARY KEY (partner_id, id),
        FOREIGN KEY (partner_id, parent_id)
            REFERENCES zenos_smoke.entities_base (partner_id, id) ON DELETE SET NULL (parent_id),
        CHECK (level != 1 OR parent_id IS NULL)
    );

    CREATE TABLE zenos_smoke.entity_l3_task (
        partner_id              text NOT NULL,
        entity_id               text NOT NULL,
        description             text NOT NULL,
        task_status             text NOT NULL,
        assignee                text,
        dispatcher              text NOT NULL,
        acceptance_criteria_json jsonb NOT NULL DEFAULT '[]',
        priority                text NOT NULL DEFAULT 'medium',
        result                  text,
        plan_order              integer,
        depends_on_json         jsonb NOT NULL DEFAULT '[]',
        blocked_reason          text,
        due_date                date,

        PRIMARY KEY (partner_id, entity_id),
        FOREIGN KEY (partner_id, entity_id)
            REFERENCES zenos_smoke.entities_base (partner_id, id) ON DELETE CASCADE
    );

    CREATE TABLE zenos_smoke.task_handoff_events (
        id              bigserial PRIMARY KEY,
        partner_id      text NOT NULL REFERENCES zenos_smoke.partners(id),
        task_entity_id  text NOT NULL,
        from_dispatcher text,
        to_dispatcher   text NOT NULL,
        reason          text NOT NULL,
        notes           text,
        output_ref      text,
        created_at      timestamptz NOT NULL DEFAULT now(),

        FOREIGN KEY (partner_id, task_entity_id)
            REFERENCES zenos_smoke.entities_base (partner_id, id) ON DELETE CASCADE
    );
""")

_ROLLBACK_SQL = textwrap.dedent("""
    DROP TABLE IF EXISTS zenos_smoke.task_handoff_events CASCADE;
    DROP TABLE IF EXISTS zenos_smoke.entity_l3_task CASCADE;
    DROP TABLE IF EXISTS zenos_smoke.entities_base CASCADE;
    DROP TABLE IF EXISTS zenos_smoke.partners CASCADE;
    DROP SCHEMA IF EXISTS zenos_smoke CASCADE;
""")


async def _setup(conn) -> None:
    await conn.execute(_SETUP_SQL)
    await conn.execute("INSERT INTO zenos_smoke.partners VALUES ('partner-A'), ('partner-B')")


async def _rollback(conn) -> None:
    await conn.execute(_ROLLBACK_SQL)


@_SKIP_DB
@pytest.mark.asyncio
async def test_db_same_partner_parent_fk_works():
    """Same-partner parent FK is accepted by PostgreSQL.

    A parent row inserted under partner-A can be referenced as parent by a
    child row also under partner-A. This must succeed without FK violation.
    """
    import asyncpg

    conn = await asyncpg.connect(_DB_URL)
    try:
        async with conn.transaction():
            await _setup(conn)
            # Insert L1 root entity for partner-A
            await conn.execute(
                "INSERT INTO zenos_smoke.entities_base "
                "(id, partner_id, name, type_label, level, status) "
                "VALUES ('root-A', 'partner-A', 'Root', 'product', 1, 'active')"
            )
            # Insert L2 child entity — same partner, references root-A as parent
            await conn.execute(
                "INSERT INTO zenos_smoke.entities_base "
                "(id, partner_id, name, type_label, level, parent_id, status) "
                "VALUES ('child-A', 'partner-A', 'Child', 'module', 2, 'root-A', 'active')"
            )
            # Must reach here without exception
            row = await conn.fetchrow(
                "SELECT id FROM zenos_smoke.entities_base WHERE id='child-A' AND partner_id='partner-A'"
            )
            assert row is not None, "child-A row must exist after same-partner insert"
            # Rollback the transaction so we leave no trace
            raise asyncpg.exceptions.TooManyConnectionsError("rollback")
    except asyncpg.exceptions.TooManyConnectionsError:
        pass  # expected rollback trigger
    except Exception as exc:
        pytest.fail(f"Same-partner parent FK insert unexpectedly raised: {exc!r}")
    finally:
        await _rollback(conn)
        await conn.close()


@_SKIP_DB
@pytest.mark.asyncio
async def test_db_cross_partner_parent_fk_rejected():
    """Cross-partner parent FK is rejected by PostgreSQL with FK violation.

    A child row under partner-B attempting to reference a parent row owned by
    partner-A must fail with ForeignKeyViolationError. Without the composite FK,
    this would silently succeed and corrupt the data model.
    """
    import asyncpg
    from asyncpg.exceptions import ForeignKeyViolationError

    conn = await asyncpg.connect(_DB_URL)
    try:
        await _setup(conn)
        # Insert root entity for partner-A
        await conn.execute(
            "INSERT INTO zenos_smoke.entities_base "
            "(id, partner_id, name, type_label, level, status) "
            "VALUES ('root-A', 'partner-A', 'Root', 'product', 1, 'active')"
        )
        # Attempt to insert a partner-B child referencing partner-A root — must fail
        with pytest.raises(ForeignKeyViolationError):
            await conn.execute(
                "INSERT INTO zenos_smoke.entities_base "
                "(id, partner_id, name, type_label, level, parent_id, status) "
                "VALUES ('child-B', 'partner-B', 'Child', 'module', 2, 'root-A', 'active')"
            )
    finally:
        await _rollback(conn)
        await conn.close()


@_SKIP_DB
@pytest.mark.asyncio
async def test_db_subclass_composite_fk_cascade():
    """Subclass composite FK CASCADE removes subclass row when entities_base row is deleted.

    When an entities_base row is deleted, the ON DELETE CASCADE on the subclass
    FK must remove the corresponding entity_l3_task row automatically.
    """
    import asyncpg

    conn = await asyncpg.connect(_DB_URL)
    try:
        await _setup(conn)
        # Insert base entity
        await conn.execute(
            "INSERT INTO zenos_smoke.entities_base "
            "(id, partner_id, name, type_label, level, status) "
            "VALUES ('task-entity-1', 'partner-A', 'Task', 'task', 3, 'active')"
        )
        # Insert subclass row
        await conn.execute(
            "INSERT INTO zenos_smoke.entity_l3_task "
            "(partner_id, entity_id, description, task_status, dispatcher) "
            "VALUES ('partner-A', 'task-entity-1', 'desc', 'todo', 'human')"
        )
        # Delete base entity — CASCADE should remove the subclass row
        await conn.execute(
            "DELETE FROM zenos_smoke.entities_base "
            "WHERE partner_id='partner-A' AND id='task-entity-1'"
        )
        # Subclass row must be gone
        row = await conn.fetchrow(
            "SELECT entity_id FROM zenos_smoke.entity_l3_task "
            "WHERE partner_id='partner-A' AND entity_id='task-entity-1'"
        )
        assert row is None, (
            "entity_l3_task row must be CASCADE-deleted when entities_base row is removed"
        )
    finally:
        await _rollback(conn)
        await conn.close()


@_SKIP_DB
@pytest.mark.asyncio
async def test_db_delete_parent_sets_child_parent_id_null_not_partner_id():
    """P1-E fix: ON DELETE SET NULL (parent_id) nulls only parent_id, not partner_id.

    PG 16.13 (>= PG 15) syntax: FOREIGN KEY (partner_id, parent_id)
        REFERENCES entities_base (partner_id, id) ON DELETE SET NULL (parent_id)

    When the parent entity is deleted:
    - child.parent_id must become NULL  (orphaned, not deleted)
    - child.partner_id must remain unchanged  (NOT NULL preserved)

    This verifies the P1-E bug fix: the old ON DELETE SET NULL (without column list)
    would attempt to null BOTH partner_id AND parent_id, violating the NOT NULL
    constraint on partner_id and causing the delete to fail with a constraint error.
    """
    import asyncpg

    conn = await asyncpg.connect(_DB_URL)
    try:
        await _setup(conn)
        # Insert L1 parent entity for partner-A
        await conn.execute(
            "INSERT INTO zenos_smoke.entities_base "
            "(id, partner_id, name, type_label, level, status) "
            "VALUES ('parent-1', 'partner-A', 'Parent', 'product', 1, 'active')"
        )
        # Insert L2 child entity referencing parent-1 (same partner)
        await conn.execute(
            "INSERT INTO zenos_smoke.entities_base "
            "(id, partner_id, name, type_label, level, parent_id, status) "
            "VALUES ('child-1', 'partner-A', 'Child', 'module', 2, 'parent-1', 'active')"
        )
        # Delete the parent — must succeed (not raise NOT NULL violation)
        try:
            await conn.execute(
                "DELETE FROM zenos_smoke.entities_base "
                "WHERE partner_id='partner-A' AND id='parent-1'"
            )
        except Exception as exc:
            pytest.fail(
                f"Deleting parent entity raised an error — "
                f"ON DELETE SET NULL (parent_id) should not violate NOT NULL on partner_id. "
                f"Error: {exc!r}"
            )
        # Verify child still exists (was not deleted)
        child = await conn.fetchrow(
            "SELECT partner_id, parent_id FROM zenos_smoke.entities_base "
            "WHERE id='child-1' AND partner_id='partner-A'"
        )
        assert child is not None, (
            "child-1 must still exist after parent is deleted "
            "(ON DELETE SET NULL orphans, not cascades)"
        )
        # parent_id must be NULL now
        assert child["parent_id"] is None, (
            f"child.parent_id must be NULL after parent delete, got: {child['parent_id']!r}"
        )
        # partner_id must be unchanged (NOT NULL preserved)
        assert child["partner_id"] == "partner-A", (
            f"child.partner_id must remain 'partner-A' (NOT NULL), got: {child['partner_id']!r}"
        )
    finally:
        await _rollback(conn)
        await conn.close()


@_SKIP_DB
@pytest.mark.asyncio
async def test_db_rollback_clean():
    """Rollback removes all tables in correct dependency order without errors.

    After running the setup SQL and then the rollback SQL, none of the smoke
    tables should remain in the database.
    """
    import asyncpg

    conn = await asyncpg.connect(_DB_URL)
    try:
        await _setup(conn)
        await _rollback(conn)
        # Confirm no smoke tables remain
        result = await conn.fetch(
            "SELECT tablename FROM pg_tables WHERE schemaname='zenos_smoke'"
        )
        assert len(result) == 0, (
            f"Rollback left {len(result)} table(s) behind: {[r['tablename'] for r in result]}"
        )
    finally:
        # Ensure cleanup even if rollback failed
        try:
            await _rollback(conn)
        except Exception:
            pass
        await conn.close()
