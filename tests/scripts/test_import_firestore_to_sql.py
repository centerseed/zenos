"""Tests for scripts/import_firestore_to_sql.py.

Covers:
- Enum validation (fail-fast on illegal values)
- Field transformation (camelCase → snake_case)
- Join table expansion (document_entities, blindspot_entities, task_entities, task_blockers)
- project_id derivation (root product/project, child entities, orphan warning)
- partner_id derivation from authorizedEntityIds
- Reconciliation report generation and formatting
- Idempotent SQL helpers (dry-run path)

All SQL writes are exercised through the dry-run path (no real DB needed).
Firestore reads are mocked with in-memory data fixtures.

⚠️  Mock test note: SQL writes are not tested against a real PostgreSQL instance.
The upsert SQL strings are verified by inspection and the dry-run counter path.
"""

from __future__ import annotations

import asyncio
import io
import sys
from contextlib import redirect_stdout
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Import helpers under test (avoid running main())
# ---------------------------------------------------------------------------
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parents[2] / "scripts"))

from import_firestore_to_sql import (  # noqa: E402
    ImportCounts,
    ReconciliationReport,
    _build_entity_to_partner_index,
    _clean_str,
    _derive_project_ids,
    _get,
    _to_dt,
    _to_json,
    _upsert_blindspot_entities,
    _upsert_document_entities,
    _upsert_task_blockers,
    _upsert_task_entities,
    _validate_enum,
    VALID_ENTITY_TYPE,
    VALID_ENTITY_STATUS,
    VALID_RELATIONSHIP_TYPE,
    VALID_DOCUMENT_STATUS,
    VALID_BLINDSPOT_SEVERITY,
    VALID_BLINDSPOT_STATUS,
    VALID_TASK_STATUS,
    VALID_TASK_PRIORITY,
    VALID_PARTNER_STATUS,
    VALID_SOURCE_TYPE,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_report() -> ReconciliationReport:
    return ReconciliationReport()


def _make_conn() -> MagicMock:
    """Fake asyncpg connection that records execute() calls."""
    conn = MagicMock()
    conn.execute = AsyncMock(return_value=None)
    return conn


def _partner(pid: str, entity_ids: list[str] | None = None) -> dict[str, Any]:
    return {
        "id": pid,
        "email": f"{pid}@example.com",
        "displayName": pid,
        "apiKey": "key-" + pid,  # pragma: allowlist secret
        "authorizedEntityIds": entity_ids or [],
        "status": "active",
        "isAdmin": False,
    }


def _entity(eid: str, etype: str = "module", parent_id: str | None = None) -> dict[str, Any]:
    return {
        "id": eid,
        "name": eid,
        "type": etype,
        "status": "active",
        "summary": "summary",
        "tags": {"what": ["x"], "why": "y", "how": "h", "who": ["z"]},
        "parentId": parent_id,
    }


def _document(
    doc_id: str,
    linked_ids: list[str] | None = None,
    partner_id: str | None = None,
) -> dict[str, Any]:
    return {
        "id": doc_id,
        "title": "Doc " + doc_id,
        "source": {"type": "github", "uri": "https://example.com", "adapter": "github"},
        "tags": {},
        "summary": "summary",
        "status": "current",
        "linkedEntityIds": linked_ids or [],
        "partnerId": partner_id,
    }


def _blindspot(
    bid: str,
    related_ids: list[str] | None = None,
    partner_id: str | None = None,
) -> dict[str, Any]:
    return {
        "id": bid,
        "description": "blind spot " + bid,
        "severity": "yellow",
        "suggestedAction": "fix it",
        "status": "open",
        "relatedEntityIds": related_ids or [],
        "partnerId": partner_id,
    }


def _task(
    tid: str,
    partner_id: str,
    linked: list[str] | None = None,
    blocked_by: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "id": tid,
        "_partner_id": partner_id,
        "title": "Task " + tid,
        "status": "todo",
        "priority": "medium",
        "createdBy": "user1",
        "linkedEntities": linked or [],
        "blockedBy": blocked_by or [],
    }


# ---------------------------------------------------------------------------
# Enum validation
# ---------------------------------------------------------------------------

class TestValidateEnum:
    def test_valid_value_passes(self):
        assert _validate_enum("active", VALID_ENTITY_STATUS, "ctx") == "active"

    def test_illegal_value_raises(self):
        with pytest.raises(ValueError, match="illegal enum value 'unknown'"):
            _validate_enum("unknown", VALID_ENTITY_TYPE, "entity x.type")

    def test_none_value_raises(self):
        with pytest.raises(ValueError, match="value is None"):
            _validate_enum(None, VALID_ENTITY_TYPE, "entity x.type")

    def test_all_entity_types(self):
        for val in VALID_ENTITY_TYPE:
            assert _validate_enum(val, VALID_ENTITY_TYPE, "ctx") == val

    def test_all_entity_statuses(self):
        for val in VALID_ENTITY_STATUS:
            assert _validate_enum(val, VALID_ENTITY_STATUS, "ctx") == val

    def test_all_relationship_types(self):
        for val in VALID_RELATIONSHIP_TYPE:
            assert _validate_enum(val, VALID_RELATIONSHIP_TYPE, "ctx") == val

    def test_all_document_statuses(self):
        for val in VALID_DOCUMENT_STATUS:
            assert _validate_enum(val, VALID_DOCUMENT_STATUS, "ctx") == val

    def test_all_blindspot_severities(self):
        for val in VALID_BLINDSPOT_SEVERITY:
            assert _validate_enum(val, VALID_BLINDSPOT_SEVERITY, "ctx") == val

    def test_all_blindspot_statuses(self):
        for val in VALID_BLINDSPOT_STATUS:
            assert _validate_enum(val, VALID_BLINDSPOT_STATUS, "ctx") == val

    def test_all_task_statuses(self):
        for val in VALID_TASK_STATUS:
            assert _validate_enum(val, VALID_TASK_STATUS, "ctx") == val

    def test_all_task_priorities(self):
        for val in VALID_TASK_PRIORITY:
            assert _validate_enum(val, VALID_TASK_PRIORITY, "ctx") == val

    def test_all_partner_statuses(self):
        for val in VALID_PARTNER_STATUS:
            assert _validate_enum(val, VALID_PARTNER_STATUS, "ctx") == val

    def test_all_source_types(self):
        for val in VALID_SOURCE_TYPE:
            assert _validate_enum(val, VALID_SOURCE_TYPE, "ctx") == val


# ---------------------------------------------------------------------------
# Field conversion helpers
# ---------------------------------------------------------------------------

class TestGetHelper:
    def test_returns_first_matching_key(self):
        doc = {"camelKey": "val"}
        assert _get(doc, "camelKey", "snake_key") == "val"

    def test_falls_back_to_second_key(self):
        doc = {"snake_key": "val2"}
        assert _get(doc, "camelKey", "snake_key") == "val2"

    def test_returns_default_when_missing(self):
        assert _get({}, "missing", default="fallback") == "fallback"

    def test_returns_none_default_by_default(self):
        assert _get({}, "missing") is None


class TestToJson:
    def test_dict_serializes(self):
        result = _to_json({"key": "val"})
        assert '"key"' in result
        assert '"val"' in result

    def test_list_serializes(self):
        result = _to_json(["a", "b"])
        assert '"a"' in result

    def test_none_becomes_null(self):
        assert _to_json(None) == "null"


class TestToDt:
    def test_datetime_with_tz_returned_as_is(self):
        dt = datetime(2024, 1, 1, tzinfo=timezone.utc)
        assert _to_dt(dt) == dt

    def test_naive_datetime_gets_utc(self):
        dt = datetime(2024, 1, 1)
        result = _to_dt(dt)
        assert result.tzinfo is not None

    def test_none_returns_none(self):
        assert _to_dt(None) is None

    def test_non_datetime_returns_none(self):
        assert _to_dt("not-a-date") is None


class TestCleanStr:
    def test_none_returns_default(self):
        assert _clean_str(None) == ""

    def test_str_returned_as_is(self):
        assert _clean_str("hello") == "hello"

    def test_int_cast_to_str(self):
        assert _clean_str(42) == "42"

    def test_custom_default(self):
        assert _clean_str(None, "fallback") == "fallback"


# ---------------------------------------------------------------------------
# Partner-to-entity index
# ---------------------------------------------------------------------------

class TestBuildEntityToPartnerIndex:
    def test_maps_entity_ids_to_partner(self):
        partners = [_partner("p1", ["e1", "e2"]), _partner("p2", ["e3"])]
        index = _build_entity_to_partner_index(partners)
        assert index == {"e1": "p1", "e2": "p1", "e3": "p2"}

    def test_first_partner_wins_on_conflict(self):
        partners = [_partner("p1", ["e1"]), _partner("p2", ["e1"])]
        index = _build_entity_to_partner_index(partners)
        assert index["e1"] == "p1"

    def test_empty_partners(self):
        assert _build_entity_to_partner_index([]) == {}

    def test_partner_with_no_entities(self):
        index = _build_entity_to_partner_index([_partner("p1", [])])
        assert index == {}

    def test_camel_case_field_name(self):
        partners = [{"id": "p1", "authorizedEntityIds": ["e1"]}]
        index = _build_entity_to_partner_index(partners)
        assert index["e1"] == "p1"


# ---------------------------------------------------------------------------
# project_id derivation
# ---------------------------------------------------------------------------

class TestDeriveProjectIds:
    def test_product_entity_self_references(self):
        entities = [_entity("prod1", etype="product")]
        report = _make_report()
        result = _derive_project_ids(entities, report)
        assert result["prod1"] == "prod1"

    def test_project_entity_self_references(self):
        entities = [_entity("proj1", etype="project")]
        report = _make_report()
        result = _derive_project_ids(entities, report)
        assert result["proj1"] == "proj1"

    def test_child_entity_finds_root_product(self):
        entities = [
            _entity("prod1", etype="product"),
            _entity("mod1", etype="module", parent_id="prod1"),
        ]
        report = _make_report()
        result = _derive_project_ids(entities, report)
        assert result["mod1"] == "prod1"

    def test_deep_child_entity_finds_root(self):
        entities = [
            _entity("prod1", etype="product"),
            _entity("mod1", etype="module", parent_id="prod1"),
            _entity("goal1", etype="goal", parent_id="mod1"),
        ]
        report = _make_report()
        result = _derive_project_ids(entities, report)
        assert result["goal1"] == "prod1"

    def test_orphan_entity_gets_none_and_warning(self):
        entities = [_entity("orphan", etype="module")]
        report = _make_report()
        result = _derive_project_ids(entities, report)
        assert result["orphan"] is None
        assert any("orphan" in w for w in report.warnings)

    def test_cycle_guard(self):
        """Entities with circular parent references should not infinite loop."""
        entities = [
            {"id": "a", "name": "a", "type": "module", "parentId": "b"},
            {"id": "b", "name": "b", "type": "module", "parentId": "a"},
        ]
        report = _make_report()
        result = _derive_project_ids(entities, report)
        # Should produce None without crashing
        assert result["a"] is None
        assert result["b"] is None


# ---------------------------------------------------------------------------
# Join table expansion: document_entities
# ---------------------------------------------------------------------------

class TestUpsertDocumentEntities:
    def test_expands_linked_entity_ids(self):
        conn = _make_conn()
        doc = _document("doc1", linked_ids=["e1", "e2"], partner_id="p1")
        entity_to_partner = {"e1": "p1", "e2": "p1"}
        report = _make_report()
        asyncio.get_event_loop().run_until_complete(
            _upsert_document_entities(conn, [doc], entity_to_partner, report, dry_run=False)
        )
        assert conn.execute.call_count == 2
        assert report.counts["document_entities"].sql == 2

    def test_skips_empty_linked_ids(self):
        conn = _make_conn()
        doc = _document("doc1", linked_ids=[], partner_id="p1")
        report = _make_report()
        asyncio.get_event_loop().run_until_complete(
            _upsert_document_entities(conn, [doc], {}, report, dry_run=False)
        )
        assert conn.execute.call_count == 0

    def test_dry_run_skips_writes_but_counts(self):
        conn = _make_conn()
        doc = _document("doc1", linked_ids=["e1", "e2"], partner_id="p1")
        report = _make_report()
        asyncio.get_event_loop().run_until_complete(
            _upsert_document_entities(conn, [doc], {"e1": "p1", "e2": "p1"}, report, dry_run=True)
        )
        assert conn.execute.call_count == 0
        assert report.counts["document_entities"].sql == 2

    def test_warns_on_unknown_entity(self):
        conn = _make_conn()
        doc = _document("doc1", linked_ids=["e_missing"], partner_id="p1")
        report = _make_report()
        asyncio.get_event_loop().run_until_complete(
            _upsert_document_entities(conn, [doc], {}, report, dry_run=False)
        )
        assert any("e_missing" in w for w in report.warnings)

    def test_skips_doc_without_partner_id(self):
        conn = _make_conn()
        doc = _document("doc1", linked_ids=["e1"], partner_id=None)
        report = _make_report()
        asyncio.get_event_loop().run_until_complete(
            _upsert_document_entities(conn, [doc], {}, report, dry_run=False)
        )
        assert conn.execute.call_count == 0


# ---------------------------------------------------------------------------
# Join table expansion: blindspot_entities
# ---------------------------------------------------------------------------

class TestUpsertBlindspotEntities:
    def test_expands_related_entity_ids(self):
        conn = _make_conn()
        bs = _blindspot("b1", related_ids=["e1", "e2"], partner_id="p1")
        report = _make_report()
        asyncio.get_event_loop().run_until_complete(
            _upsert_blindspot_entities(conn, [bs], {"e1": "p1", "e2": "p1"}, report, dry_run=False)
        )
        assert conn.execute.call_count == 2
        assert report.counts["blindspot_entities"].sql == 2

    def test_derives_partner_id_from_related_entities(self):
        conn = _make_conn()
        bs = _blindspot("b1", related_ids=["e1"], partner_id=None)
        report = _make_report()
        asyncio.get_event_loop().run_until_complete(
            _upsert_blindspot_entities(conn, [bs], {"e1": "p1"}, report, dry_run=False)
        )
        assert conn.execute.call_count == 1

    def test_dry_run_skips_writes(self):
        conn = _make_conn()
        bs = _blindspot("b1", related_ids=["e1"], partner_id="p1")
        report = _make_report()
        asyncio.get_event_loop().run_until_complete(
            _upsert_blindspot_entities(conn, [bs], {"e1": "p1"}, report, dry_run=True)
        )
        assert conn.execute.call_count == 0
        assert report.counts["blindspot_entities"].sql == 1


# ---------------------------------------------------------------------------
# Join table expansion: task_entities and task_blockers
# ---------------------------------------------------------------------------

class TestUpsertTaskEntities:
    def test_expands_linked_entities(self):
        conn = _make_conn()
        task = _task("t1", "p1", linked=["e1", "e2"])
        report = _make_report()
        asyncio.get_event_loop().run_until_complete(
            _upsert_task_entities(conn, [task], report, dry_run=False)
        )
        assert conn.execute.call_count == 2
        assert report.counts["task_entities"].sql == 2

    def test_dry_run_skips_writes(self):
        conn = _make_conn()
        task = _task("t1", "p1", linked=["e1"])
        report = _make_report()
        asyncio.get_event_loop().run_until_complete(
            _upsert_task_entities(conn, [task], report, dry_run=True)
        )
        assert conn.execute.call_count == 0
        assert report.counts["task_entities"].sql == 1

    def test_skips_empty_entity_ids(self):
        conn = _make_conn()
        task = _task("t1", "p1", linked=["", None])
        report = _make_report()
        asyncio.get_event_loop().run_until_complete(
            _upsert_task_entities(conn, [task], report, dry_run=False)
        )
        assert conn.execute.call_count == 0


class TestUpsertTaskBlockers:
    def test_expands_blocked_by(self):
        conn = _make_conn()
        task = _task("t1", "p1", blocked_by=["t2", "t3"])
        report = _make_report()
        asyncio.get_event_loop().run_until_complete(
            _upsert_task_blockers(conn, [task], report, dry_run=False)
        )
        assert conn.execute.call_count == 2
        assert report.counts["task_blockers"].sql == 2

    def test_skips_self_reference(self):
        conn = _make_conn()
        task = _task("t1", "p1", blocked_by=["t1"])
        report = _make_report()
        asyncio.get_event_loop().run_until_complete(
            _upsert_task_blockers(conn, [task], report, dry_run=False)
        )
        assert conn.execute.call_count == 0

    def test_dry_run(self):
        conn = _make_conn()
        task = _task("t1", "p1", blocked_by=["t2"])
        report = _make_report()
        asyncio.get_event_loop().run_until_complete(
            _upsert_task_blockers(conn, [task], report, dry_run=True)
        )
        assert conn.execute.call_count == 0
        assert report.counts["task_blockers"].sql == 1


# ---------------------------------------------------------------------------
# Reconciliation report
# ---------------------------------------------------------------------------

class TestReconciliationReport:
    def test_counts_match_shows_ok(self):
        report = _make_report()
        cnt = report.add("partners")
        cnt.firestore = 5
        cnt.sql = 5
        buf = io.StringIO()
        with redirect_stdout(buf):
            report.print_report()
        output = buf.getvalue()
        assert "OK" in output
        assert "partners" in output

    def test_counts_mismatch_shows_mismatch(self):
        report = _make_report()
        cnt = report.add("entities")
        cnt.firestore = 10
        cnt.sql = 9
        buf = io.StringIO()
        with redirect_stdout(buf):
            report.print_report()
        output = buf.getvalue()
        assert "MISMATCH" in output

    def test_derived_tables_shown_as_derived(self):
        report = _make_report()
        report.add("document_entities").sql = 35
        buf = io.StringIO()
        with redirect_stdout(buf):
            report.print_report()
        output = buf.getvalue()
        assert "(derived)" in output

    def test_warnings_displayed(self):
        report = _make_report()
        report.warn("entity abc has no project_id")
        buf = io.StringIO()
        with redirect_stdout(buf):
            report.print_report()
        assert "entity abc has no project_id" in buf.getvalue()

    def test_no_warnings_shows_none(self):
        report = _make_report()
        buf = io.StringIO()
        with redirect_stdout(buf):
            report.print_report()
        assert "(none)" in buf.getvalue()

    def test_errors_displayed(self):
        report = _make_report()
        report.error("critical failure")
        buf = io.StringIO()
        with redirect_stdout(buf):
            report.print_report()
        assert "critical failure" in buf.getvalue()

    def test_add_idempotent(self):
        report = _make_report()
        c1 = report.add("partners")
        c2 = report.add("partners")
        assert c1 is c2


# ---------------------------------------------------------------------------
# Enum coverage: illegal values in real import paths (fail fast verification)
# ---------------------------------------------------------------------------

class TestEnumFailFastInUpsertPaths:
    """Verify that illegal enum values in Firestore data raise ValueError."""

    def test_illegal_entity_type_raises(self):
        from import_firestore_to_sql import _upsert_entities
        conn = _make_conn()
        bad_entity = _entity("e1", etype="illegal_type")
        bad_entity["partnerId"] = "p1"
        report = _make_report()
        with pytest.raises(ValueError, match="illegal enum value 'illegal_type'"):
            asyncio.get_event_loop().run_until_complete(
                _upsert_entities(conn, [bad_entity], {"e1": "p1"}, {"e1": None}, report, dry_run=False)
            )

    def test_illegal_entity_status_raises(self):
        from import_firestore_to_sql import _upsert_entities
        conn = _make_conn()
        bad_entity = _entity("e1", etype="module")
        bad_entity["status"] = "ghost"
        bad_entity["partnerId"] = "p1"
        report = _make_report()
        with pytest.raises(ValueError, match="illegal enum value 'ghost'"):
            asyncio.get_event_loop().run_until_complete(
                _upsert_entities(conn, [bad_entity], {"e1": "p1"}, {"e1": None}, report, dry_run=False)
            )

    def test_illegal_relationship_type_raises(self):
        from import_firestore_to_sql import _upsert_relationships
        conn = _make_conn()
        bad_rel = {
            "id": "r1",
            "_source_entity_id": "e1",
            "targetEntityId": "e2",
            "type": "hates",
            "partnerId": "p1",
        }
        report = _make_report()
        with pytest.raises(ValueError, match="illegal enum value 'hates'"):
            asyncio.get_event_loop().run_until_complete(
                _upsert_relationships(conn, [bad_rel], {"e1": "p1"}, report, dry_run=False)
            )

    def test_illegal_task_status_raises(self):
        from import_firestore_to_sql import _upsert_tasks
        conn = _make_conn()
        bad_task = _task("t1", "p1")
        bad_task["status"] = "limbo"
        report = _make_report()
        with pytest.raises(ValueError, match="illegal enum value 'limbo'"):
            asyncio.get_event_loop().run_until_complete(
                _upsert_tasks(conn, [bad_task], report, dry_run=False)
            )

    def test_illegal_task_priority_raises(self):
        from import_firestore_to_sql import _upsert_tasks
        conn = _make_conn()
        bad_task = _task("t1", "p1")
        bad_task["priority"] = "urgent"
        report = _make_report()
        with pytest.raises(ValueError, match="illegal enum value 'urgent'"):
            asyncio.get_event_loop().run_until_complete(
                _upsert_tasks(conn, [bad_task], report, dry_run=False)
            )

    def test_illegal_blindspot_severity_raises(self):
        from import_firestore_to_sql import _upsert_blindspots
        conn = _make_conn()
        bad_bs = _blindspot("b1", partner_id="p1")
        bad_bs["severity"] = "orange"
        report = _make_report()
        with pytest.raises(ValueError, match="illegal enum value 'orange'"):
            asyncio.get_event_loop().run_until_complete(
                _upsert_blindspots(conn, [bad_bs], {"b1": "p1"}, report, dry_run=False)
            )

    def test_illegal_document_status_raises(self):
        from import_firestore_to_sql import _upsert_documents
        conn = _make_conn()
        bad_doc = _document("d1", partner_id="p1")
        bad_doc["status"] = "forbidden"
        report = _make_report()
        with pytest.raises(ValueError, match="illegal enum value 'forbidden'"):
            asyncio.get_event_loop().run_until_complete(
                _upsert_documents(conn, [bad_doc], {}, report, dry_run=False)
            )

    def test_illegal_source_type_raises(self):
        from import_firestore_to_sql import _upsert_documents
        conn = _make_conn()
        bad_doc = _document("d1", partner_id="p1")
        bad_doc["source"] = {"type": "google_drive", "uri": "https://drive.google.com"}
        report = _make_report()
        with pytest.raises(ValueError, match="illegal enum value 'google_drive'"):
            asyncio.get_event_loop().run_until_complete(
                _upsert_documents(conn, [bad_doc], {}, report, dry_run=False)
            )


# ---------------------------------------------------------------------------
# Dry-run integration: run_import with mocked Firestore
# ---------------------------------------------------------------------------

class TestRunImportDryRun:
    """Smoke test the full pipeline in dry-run mode with mocked Firestore."""

    def test_dry_run_returns_report_with_counts(self):
        """Full dry-run should produce a report with expected collection names."""
        # Build minimal fake data
        partners = [_partner("p1", ["e1"])]
        entities = [_entity("e1", etype="product")]
        relationships = []
        documents = [_document("d1", linked_ids=["e1"], partner_id="p1")]
        protocols = []
        blindspots = []
        tasks = [_task("t1", "p1", linked=["e1"])]
        usage_logs = []

        async def _run():
            from import_firestore_to_sql import run_import
            with (
                patch("import_firestore_to_sql._read_partners", return_value=partners),
                patch("import_firestore_to_sql._read_entities", return_value=entities),
                patch("import_firestore_to_sql._read_relationships", return_value=relationships),
                patch("import_firestore_to_sql._read_documents", return_value=documents),
                patch("import_firestore_to_sql._read_protocols", return_value=protocols),
                patch("import_firestore_to_sql._read_blindspots", return_value=blindspots),
                patch("import_firestore_to_sql._read_tasks", return_value=tasks),
                patch("import_firestore_to_sql._read_usage_logs", return_value=usage_logs),
                patch("import_firestore_to_sql.firestore.AsyncClient"),
            ):
                return await run_import(dry_run=True)

        report = asyncio.get_event_loop().run_until_complete(_run())

        assert "partners" in report.counts
        assert "entities" in report.counts
        assert "tasks" in report.counts
        assert report.counts["partners"].firestore == 1
        assert report.counts["entities"].firestore == 1
        assert report.counts["tasks"].firestore == 1
        # No errors in clean data
        assert report.errors == []


# ---------------------------------------------------------------------------
# _read_usage_logs: failure behavior
# ---------------------------------------------------------------------------

class TestReadUsageLogs:
    """Verify _read_usage_logs returns empty list and logs a warning on error."""

    def test_returns_empty_list_on_firestore_error(self):
        """Simulated Firestore failure should return [] without raising."""
        from import_firestore_to_sql import _read_usage_logs

        async def _fail_get():
            raise RuntimeError("Firestore unavailable")

        mock_db = MagicMock()
        mock_collection = MagicMock()
        mock_collection.get = _fail_get
        mock_db.collection = MagicMock(return_value=mock_collection)

        result = asyncio.get_event_loop().run_until_complete(_read_usage_logs(mock_db))
        assert result == []

    def test_logs_warning_on_firestore_error(self):
        """Warning must be emitted (not silently swallowed) when Firestore fails."""
        import logging
        from import_firestore_to_sql import _read_usage_logs

        async def _fail_get():
            raise RuntimeError("connection refused")

        mock_db = MagicMock()
        mock_collection = MagicMock()
        mock_collection.get = _fail_get
        mock_db.collection = MagicMock(return_value=mock_collection)

        with patch("import_firestore_to_sql.logger") as mock_logger:
            asyncio.get_event_loop().run_until_complete(_read_usage_logs(mock_db))
            mock_logger.warning.assert_called_once()
            warning_args = mock_logger.warning.call_args[0]
            assert "usage_logs" in warning_args[0]
