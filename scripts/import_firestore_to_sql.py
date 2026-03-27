#!/usr/bin/env python3
"""Admin script: import all ZenOS data from Firestore into PostgreSQL.

Usage:
    DATABASE_URL=postgresql://user:pass@host/db \\  # pragma: allowlist secret
        python scripts/import_firestore_to_sql.py [--dry-run]

The script is idempotent: repeated runs use INSERT ... ON CONFLICT DO UPDATE
(upsert) for main tables and INSERT ... ON CONFLICT DO NOTHING for join tables.
All enum values are validated before any write; illegal values cause a fast fail.

Firestore project: zenos-naruvia (overridable via GOOGLE_CLOUD_PROJECT env var).
PostgreSQL schema:  zenos (hardcoded to match the migration SQL).
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

import asyncpg
from google.cloud import firestore

# ---------------------------------------------------------------------------
# Enum allow-lists (fail fast on illegal values)
# ---------------------------------------------------------------------------

VALID_ENTITY_TYPE = {"product", "module", "goal", "role", "project", "document"}
VALID_ENTITY_STATUS = {
    "active", "paused", "completed", "planned",
    "current", "stale", "draft", "conflict",
}
VALID_RELATIONSHIP_TYPE = {
    "depends_on", "serves", "owned_by", "part_of",
    "blocks", "related_to", "impacts", "enables",
}
VALID_DOCUMENT_STATUS = {"current", "stale", "archived", "draft", "conflict"}
VALID_BLINDSPOT_SEVERITY = {"red", "yellow", "green"}
VALID_BLINDSPOT_STATUS = {"open", "acknowledged", "resolved"}
VALID_TASK_STATUS = {
    "backlog", "todo", "in_progress", "review",
    "done", "archived", "blocked", "cancelled",
}
VALID_TASK_PRIORITY = {"critical", "high", "medium", "low"}
VALID_PARTNER_STATUS = {"invited", "active", "suspended"}
VALID_SOURCE_TYPE = {"github", "gdrive", "notion", "upload"}


# ---------------------------------------------------------------------------
# Reconciliation counters
# ---------------------------------------------------------------------------

@dataclass
class ImportCounts:
    """Track Firestore vs SQL counts per collection."""
    firestore: int = 0
    sql: int = 0


@dataclass
class ReconciliationReport:
    """Accumulate counts and diagnostic messages during import."""
    counts: dict[str, ImportCounts] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def add(self, collection: str) -> ImportCounts:
        if collection not in self.counts:
            self.counts[collection] = ImportCounts()
        return self.counts[collection]

    def warn(self, msg: str) -> None:
        self.warnings.append(msg)

    def error(self, msg: str) -> None:
        self.errors.append(msg)

    def print_report(self) -> None:
        print("\n=== Reconciliation Report ===")
        header = f"{'Collection':<20} | {'Firestore':>9} | {'SQL':>6} | {'Match'}"
        print(header)
        print("-" * len(header))
        derived = {
            "document_entities", "blindspot_entities",
            "task_entities", "task_blockers", "usage_logs",
        }
        for name, cnt in self.counts.items():
            if name in derived:
                match = "(derived)"
            elif cnt.firestore == cnt.sql:
                match = "OK"
            else:
                match = "MISMATCH"
            fs_str = str(cnt.firestore) if cnt.firestore > 0 else "-"
            print(f"{name:<20} | {fs_str:>9} | {cnt.sql:>6} | {match}")

        if self.warnings:
            print("\n=== Warnings ===")
            for w in self.warnings:
                print(f"- {w}")
        else:
            print("\n=== Warnings ===\n(none)")

        if self.errors:
            print("\n=== Errors ===")
            for e in self.errors:
                print(f"- {e}")
        else:
            print("\n=== Errors ===\n(none)")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get(doc: dict[str, Any], *keys: str, default: Any = None) -> Any:
    """Return first matching key from doc (supports camelCase fallback)."""
    for key in keys:
        if key in doc:
            return doc[key]
    return default


def _to_dt(val: Any) -> datetime | None:
    """Coerce Firestore DatetimeWithNanoseconds or Python datetime to UTC datetime."""
    if val is None:
        return None
    if isinstance(val, datetime):
        if val.tzinfo is None:
            return val.replace(tzinfo=timezone.utc)
        return val
    return None


def _to_json(val: Any) -> str:
    """Serialize a Python value to JSON string for asyncpg JSONB columns."""
    if val is None:
        return "null"
    return json.dumps(val, ensure_ascii=False, default=str)


def _validate_enum(value: str | None, allowed: set[str], context: str) -> str:
    """Validate an enum value; raise ValueError with context on failure."""
    if value is None:
        raise ValueError(f"{context}: value is None, expected one of {allowed}")
    if value not in allowed:
        raise ValueError(
            f"{context}: illegal enum value '{value}', expected one of {sorted(allowed)}"
        )
    return value


def _clean_str(val: Any, default: str = "") -> str:
    """Return string value or default."""
    if val is None:
        return default
    return str(val)


# Track IDs that were successfully imported, for dangling FK checks.
# Structure: {collection: {(partner_id, id)}} for partner-scoped checks,
# plus a flat set {collection_flat: {id}} for quick id-only lookups.
_imported_ids: dict[str, set[str]] = {}
_imported_scoped: dict[str, set[tuple[str, str]]] = {}


def _register_imported(collection: str, doc_id: str, partner_id: str | None = None) -> None:
    """Track an ID that was successfully written to SQL."""
    _imported_ids.setdefault(collection, set()).add(doc_id)
    if partner_id:
        _imported_scoped.setdefault(collection, set()).add((partner_id, doc_id))


def _nullify_dangling_fk(
    fk_value: str | None,
    target_collection: str,
    context_id: str,
    report: ReconciliationReport,
    partner_id: str | None = None,
) -> str | None:
    """Return fk_value if its target exists in _imported_ids, else None + warn.

    If partner_id is provided, checks the composite (partner_id, id) for
    multi-tenant FK safety. Falls back to id-only check otherwise.
    """
    if fk_value is None:
        return None
    if partner_id:
        scoped = _imported_scoped.get(target_collection, set())
        if (partner_id, fk_value) not in scoped:
            report.warn(
                f"{context_id}: linked {target_collection} '{fk_value}' "
                f"not found for partner '{partner_id}' in SQL — setting to NULL"
            )
            return None
        return fk_value
    # Fallback: id-only check (no partner scope)
    known = _imported_ids.get(target_collection, set())
    if fk_value not in known:
        report.warn(
            f"{context_id}: linked {target_collection} '{fk_value}' not found in SQL — setting to NULL"
        )
        return None
    return fk_value


# ---------------------------------------------------------------------------
# Partner-to-entity index builder
# ---------------------------------------------------------------------------

def _build_entity_to_partner_index(
    partners_data: list[dict[str, Any]],
) -> dict[str, str]:
    """Return a mapping of entity_id -> partner_id.

    Built from each partner's authorizedEntityIds array.
    """
    index: dict[str, str] = {}
    for partner in partners_data:
        pid = partner["id"]
        auth_ids = partner.get("authorizedEntityIds") or partner.get("authorized_entity_ids") or []
        for eid in auth_ids:
            if eid not in index:
                index[eid] = pid
    return index


# ---------------------------------------------------------------------------
# project_id derivation for entities
# ---------------------------------------------------------------------------

def _derive_project_ids(
    entities_data: list[dict[str, Any]],
    report: ReconciliationReport,
) -> dict[str, str | None]:
    """Return mapping entity_id -> project_id by walking the parent tree.

    Rules:
    - product / project entity: project_id = entity id (self-reference)
    - other types: walk parent_id chain upward until a root is found
    - no root found: project_id = None, emit warning
    """
    # Build id -> raw doc index
    by_id: dict[str, dict[str, Any]] = {d["id"]: d for d in entities_data}

    result: dict[str, str | None] = {}

    def _find_root(eid: str, visited: set[str]) -> str | None:
        if eid in visited:
            return None  # cycle guard
        visited.add(eid)
        doc = by_id.get(eid)
        if doc is None:
            return None
        etype = _get(doc, "type", default="")
        if etype in ("product", "project"):
            return eid
        parent_id = _get(doc, "parentId", "parent_id")
        if not parent_id:
            return None
        return _find_root(parent_id, visited)

    for doc in entities_data:
        eid = doc["id"]
        etype = _get(doc, "type", default="")
        if etype in ("product", "project"):
            result[eid] = eid
        else:
            root = _find_root(eid, set())
            if root is None:
                report.warn(f"entity {eid} has no root product/project → project_id=null")
            result[eid] = root

    return result


# ---------------------------------------------------------------------------
# Firestore readers
# ---------------------------------------------------------------------------

async def _read_partners(db: firestore.AsyncClient) -> list[dict[str, Any]]:
    docs = await db.collection("partners").get()
    result = []
    for doc in docs:
        data = doc.to_dict() or {}
        data["id"] = doc.id
        result.append(data)
    return result


async def _read_entities(db: firestore.AsyncClient) -> list[dict[str, Any]]:
    docs = await db.collection("entities").get()
    result = []
    for doc in docs:
        data = doc.to_dict() or {}
        data["id"] = doc.id
        result.append(data)
    return result


async def _read_relationships(
    db: firestore.AsyncClient,
    entities_data: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Read all relationships from entity subcollections."""
    result = []
    for entity_doc in entities_data:
        eid = entity_doc["id"]
        rel_docs = await db.collection("entities").document(eid).collection("relationships").get()
        for rel_doc in rel_docs:
            data = rel_doc.to_dict() or {}
            data["id"] = rel_doc.id
            data["_source_entity_id"] = eid  # inject parent
            result.append(data)
    return result


async def _read_documents(db: firestore.AsyncClient) -> list[dict[str, Any]]:
    docs = await db.collection("documents").get()
    result = []
    for doc in docs:
        data = doc.to_dict() or {}
        data["id"] = doc.id
        result.append(data)
    return result


async def _read_protocols(db: firestore.AsyncClient) -> list[dict[str, Any]]:
    docs = await db.collection("protocols").get()
    result = []
    for doc in docs:
        data = doc.to_dict() or {}
        data["id"] = doc.id
        result.append(data)
    return result


async def _read_blindspots(db: firestore.AsyncClient) -> list[dict[str, Any]]:
    docs = await db.collection("blindspots").get()
    result = []
    for doc in docs:
        data = doc.to_dict() or {}
        data["id"] = doc.id
        result.append(data)
    return result


async def _read_tasks(
    db: firestore.AsyncClient,
    partners_data: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Read tasks from each partner's subcollection."""
    result = []
    for partner_doc in partners_data:
        pid = partner_doc["id"]
        task_docs = await db.collection("partners").document(pid).collection("tasks").get()
        for task_doc in task_docs:
            data = task_doc.to_dict() or {}
            data["id"] = task_doc.id
            data["_partner_id"] = pid  # inject from path
            result.append(data)
    return result


async def _read_usage_logs(
    db: firestore.AsyncClient, partners_data: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Read usage_logs from partner subcollections (partners/{pid}/usage_logs).

    Falls back to root collection if no partner subcollection data found.
    """
    result = []
    # Primary path: partner subcollections (matches governance_ai.py write path)
    for partner_doc in partners_data:
        pid = partner_doc["id"]
        try:
            docs = await db.collection("partners").document(pid).collection("usage_logs").get()
            for doc in docs:
                data = doc.to_dict() or {}
                data["id"] = doc.id
                data["_partner_id"] = pid
                result.append(data)
        except Exception as e:
            logger.warning("_read_usage_logs: failed for partner %s: %s", pid, e)

    # Fallback: root collection (legacy path)
    if not result:
        try:
            docs = await db.collection("usage_logs").get()
            for doc in docs:
                data = doc.to_dict() or {}
                data["id"] = doc.id
                result.append(data)
        except Exception as e:
            logger.warning("_read_usage_logs: failed to read root usage_logs: %s", e)
    return result


# ---------------------------------------------------------------------------
# SQL upsert helpers
# ---------------------------------------------------------------------------

SCHEMA = "zenos"


async def _upsert_partners(
    conn: asyncpg.Connection,
    partners_data: list[dict[str, Any]],
    report: ReconciliationReport,
    dry_run: bool,
) -> None:
    cnt = report.add("partners")
    cnt.firestore = len(partners_data)

    for doc in partners_data:
        doc_id = doc["id"]
        status_raw = _clean_str(_get(doc, "status"), "active")
        status = _validate_enum(status_raw, VALID_PARTNER_STATUS, f"partner {doc_id}.status")

        row = (
            doc_id,
            _clean_str(_get(doc, "email"), ""),
            _clean_str(_get(doc, "displayName", "display_name"), doc_id),
            _clean_str(_get(doc, "apiKey", "api_key"), ""),
            _get(doc, "authorizedEntityIds", "authorized_entity_ids") or [],
            status,
            bool(_get(doc, "isAdmin", "is_admin", default=False)),
            _clean_str(_get(doc, "sharedPartnerId", "shared_partner_id")) or None,
            _clean_str(_get(doc, "defaultProject", "default_project")) or None,
            _clean_str(_get(doc, "invitedBy", "invited_by")) or None,
            _to_dt(_get(doc, "createdAt", "created_at")) or datetime.now(timezone.utc),
            _to_dt(_get(doc, "updatedAt", "updated_at")) or datetime.now(timezone.utc),
        )
        if not dry_run:
            await conn.execute(
                f"""
                INSERT INTO {SCHEMA}.partners
                    (id, email, display_name, api_key, authorized_entity_ids,
                     status, is_admin, shared_partner_id, default_project,
                     invited_by, created_at, updated_at)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)
                ON CONFLICT (id) DO UPDATE SET
                    email = EXCLUDED.email,
                    display_name = EXCLUDED.display_name,
                    api_key = EXCLUDED.api_key,
                    authorized_entity_ids = EXCLUDED.authorized_entity_ids,
                    status = EXCLUDED.status,
                    is_admin = EXCLUDED.is_admin,
                    shared_partner_id = EXCLUDED.shared_partner_id,
                    default_project = EXCLUDED.default_project,
                    invited_by = EXCLUDED.invited_by,
                    updated_at = EXCLUDED.updated_at
                """,
                *row,
            )
        _register_imported("partner", doc_id)
        cnt.sql += 1


async def _upsert_entities(
    conn: asyncpg.Connection,
    entities_data: list[dict[str, Any]],
    entity_to_partner: dict[str, str],
    project_ids: dict[str, str | None],
    report: ReconciliationReport,
    dry_run: bool,
) -> None:
    cnt = report.add("entities")
    cnt.firestore = len(entities_data)
    deferred_refs: list[tuple[str, str, str | None, str | None]] = []

    for doc in entities_data:
        doc_id = doc["id"]

        partner_id = (
            _clean_str(_get(doc, "partnerId", "partner_id")) or
            entity_to_partner.get(doc_id)
        )
        if not partner_id:
            report.warn(f"entity {doc_id}: no partner_id found — skipping")
            continue

        etype = _clean_str(_get(doc, "type"), "module")
        _validate_enum(etype, VALID_ENTITY_TYPE, f"entity {doc_id}.type")

        estatus = _clean_str(_get(doc, "status"), "active")
        _validate_enum(estatus, VALID_ENTITY_STATUS, f"entity {doc_id}.status")

        tags_raw = _get(doc, "tags")
        if isinstance(tags_raw, dict):
            tags_json = _to_json(tags_raw)
        else:
            tags_json = "{}"

        sources_raw = _get(doc, "sources")
        if isinstance(sources_raw, list):
            sources_json = _to_json(sources_raw)
        else:
            sources_json = "[]"

        details_raw = _get(doc, "details")
        details_json = _to_json(details_raw) if details_raw is not None else None

        level_raw = _get(doc, "level")
        level = int(level_raw) if level_raw is not None else None

        project_id = project_ids.get(doc_id)

        visibility_raw = _clean_str(_get(doc, "visibility"), "public")
        if visibility_raw not in ("public", "restricted"):
            visibility_raw = "public"

        parent_id = _clean_str(_get(doc, "parentId", "parent_id")) or None

        now = datetime.now(timezone.utc)
        # Phase 1: insert with parent_id and project_id set to NULL
        # to avoid self-referencing FK violations on insert order.
        row = (
            doc_id,
            partner_id,
            _clean_str(_get(doc, "name"), doc_id),
            etype,
            level,
            None,  # parent_id — deferred to phase 2
            None,  # project_id — deferred to phase 2
            estatus,
            _clean_str(_get(doc, "summary"), ""),
            tags_json,
            details_json,
            bool(_get(doc, "confirmedByUser", "confirmed_by_user", default=False)),
            _clean_str(_get(doc, "owner")) or None,
            sources_json,
            visibility_raw,
            _to_dt(_get(doc, "lastReviewedAt", "last_reviewed_at")),
            _to_dt(_get(doc, "createdAt", "created_at")) or now,
            _to_dt(_get(doc, "updatedAt", "updated_at")) or now,
        )
        if not dry_run:
            await conn.execute(
                f"""
                INSERT INTO {SCHEMA}.entities
                    (id, partner_id, name, type, level, parent_id, project_id,
                     status, summary, tags_json, details_json, confirmed_by_user,
                     owner, sources_json, visibility, last_reviewed_at,
                     created_at, updated_at)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10::jsonb,$11::jsonb,$12,
                        $13,$14::jsonb,$15,$16,$17,$18)
                ON CONFLICT (id) DO UPDATE SET
                    partner_id = EXCLUDED.partner_id,
                    name = EXCLUDED.name,
                    type = EXCLUDED.type,
                    level = EXCLUDED.level,
                    status = EXCLUDED.status,
                    summary = EXCLUDED.summary,
                    tags_json = EXCLUDED.tags_json,
                    details_json = EXCLUDED.details_json,
                    confirmed_by_user = EXCLUDED.confirmed_by_user,
                    owner = EXCLUDED.owner,
                    sources_json = EXCLUDED.sources_json,
                    visibility = EXCLUDED.visibility,
                    last_reviewed_at = EXCLUDED.last_reviewed_at,
                    updated_at = EXCLUDED.updated_at
                """,
                *row,
            )
        deferred_refs.append((doc_id, partner_id, parent_id, project_id))
        _register_imported("entity", doc_id, partner_id)
        cnt.sql += 1

    # Phase 2: backfill parent_id and project_id now that all entities exist.
    if not dry_run:
        for doc_id, partner_id, parent_id, project_id in deferred_refs:
            if parent_id or project_id:
                await conn.execute(
                    f"""
                    UPDATE {SCHEMA}.entities
                    SET parent_id = $1, project_id = $2, updated_at = $3
                    WHERE id = $4
                    """,
                    parent_id,
                    project_id,
                    datetime.now(timezone.utc),
                    doc_id,
                )


async def _upsert_relationships(
    conn: asyncpg.Connection,
    relationships_data: list[dict[str, Any]],
    entity_to_partner: dict[str, str],
    report: ReconciliationReport,
    dry_run: bool,
) -> None:
    cnt = report.add("relationships")
    cnt.firestore = len(relationships_data)

    for doc in relationships_data:
        doc_id = doc["id"]
        source_entity_id = doc.get("_source_entity_id", "")

        partner_id = (
            _clean_str(_get(doc, "partnerId", "partner_id")) or
            entity_to_partner.get(source_entity_id)
        )
        if not partner_id:
            report.warn(f"relationship {doc_id}: no partner_id — skipping")
            continue

        rtype = _clean_str(_get(doc, "type", "relType"), "related_to")
        _validate_enum(rtype, VALID_RELATIONSHIP_TYPE, f"relationship {doc_id}.type")

        target_id = _clean_str(
            _get(doc, "targetEntityId", "target_entity_id", "targetId", "target_id")
        )
        if not target_id:
            report.warn(f"relationship {doc_id}: missing target_entity_id — skipping")
            continue

        if source_entity_id == target_id:
            report.warn(f"relationship {doc_id}: self-loop (source==target) — skipping")
            continue

        now = datetime.now(timezone.utc)
        row = (
            doc_id,
            partner_id,
            source_entity_id,
            target_id,
            rtype,
            _clean_str(_get(doc, "description"), ""),
            bool(_get(doc, "confirmedByUser", "confirmed_by_user", default=False)),
            _to_dt(_get(doc, "createdAt", "created_at")) or now,
            _to_dt(_get(doc, "updatedAt", "updated_at")) or now,
        )
        if not dry_run:
            await conn.execute(
                f"""
                INSERT INTO {SCHEMA}.relationships
                    (id, partner_id, source_entity_id, target_entity_id, type,
                     description, confirmed_by_user, created_at, updated_at)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)
                ON CONFLICT (id) DO UPDATE SET
                    partner_id = EXCLUDED.partner_id,
                    source_entity_id = EXCLUDED.source_entity_id,
                    target_entity_id = EXCLUDED.target_entity_id,
                    type = EXCLUDED.type,
                    description = EXCLUDED.description,
                    confirmed_by_user = EXCLUDED.confirmed_by_user,
                    updated_at = EXCLUDED.updated_at
                """,
                *row,
            )
        cnt.sql += 1


async def _upsert_documents(
    conn: asyncpg.Connection,
    documents_data: list[dict[str, Any]],
    entity_to_partner: dict[str, str],
    report: ReconciliationReport,
    dry_run: bool,
) -> None:
    cnt = report.add("documents")
    cnt.firestore = len(documents_data)

    for doc in documents_data:
        doc_id = doc["id"]

        # Derive partner_id from linked entities if not on doc directly
        partner_id = _clean_str(_get(doc, "partnerId", "partner_id")) or None
        if not partner_id:
            linked = _get(doc, "linkedEntityIds", "linked_entity_ids") or []
            for eid in linked:
                if eid in entity_to_partner:
                    partner_id = entity_to_partner[eid]
                    break
        if not partner_id:
            report.warn(f"document {doc_id}: no partner_id — skipping")
            continue

        dstatus = _clean_str(_get(doc, "status"), "current")
        _validate_enum(dstatus, VALID_DOCUMENT_STATUS, f"document {doc_id}.status")

        source_raw = _get(doc, "source")
        if not isinstance(source_raw, dict):
            source_raw = {}
        source_type = source_raw.get("type")
        _validate_enum(source_type, VALID_SOURCE_TYPE, f"document {doc_id}.source.type")
        source_json = _to_json(source_raw)

        tags_raw = _get(doc, "tags")
        if not isinstance(tags_raw, dict):
            tags_raw = {}
        tags_json = _to_json(tags_raw)

        now = datetime.now(timezone.utc)
        row = (
            doc_id,
            partner_id,
            _clean_str(_get(doc, "title"), doc_id),
            source_json,
            tags_json,
            _clean_str(_get(doc, "summary"), ""),
            dstatus,
            bool(_get(doc, "confirmedByUser", "confirmed_by_user", default=False)),
            _to_dt(_get(doc, "lastReviewedAt", "last_reviewed_at")),
            _to_dt(_get(doc, "createdAt", "created_at")) or now,
            _to_dt(_get(doc, "updatedAt", "updated_at")) or now,
        )
        if not dry_run:
            await conn.execute(
                f"""
                INSERT INTO {SCHEMA}.documents
                    (id, partner_id, title, source_json, tags_json, summary,
                     status, confirmed_by_user, last_reviewed_at,
                     created_at, updated_at)
                VALUES ($1,$2,$3,$4::jsonb,$5::jsonb,$6,$7,$8,$9,$10,$11)
                ON CONFLICT (id) DO UPDATE SET
                    partner_id = EXCLUDED.partner_id,
                    title = EXCLUDED.title,
                    source_json = EXCLUDED.source_json,
                    tags_json = EXCLUDED.tags_json,
                    summary = EXCLUDED.summary,
                    status = EXCLUDED.status,
                    confirmed_by_user = EXCLUDED.confirmed_by_user,
                    last_reviewed_at = EXCLUDED.last_reviewed_at,
                    updated_at = EXCLUDED.updated_at
                """,
                *row,
            )
        cnt.sql += 1


async def _upsert_document_entities(
    conn: asyncpg.Connection,
    documents_data: list[dict[str, Any]],
    entity_to_partner: dict[str, str],
    report: ReconciliationReport,
    dry_run: bool,
) -> None:
    cnt = report.add("document_entities")

    for doc in documents_data:
        doc_id = doc["id"]
        partner_id = _clean_str(_get(doc, "partnerId", "partner_id")) or None
        if not partner_id:
            linked_for_pid = _get(doc, "linkedEntityIds", "linked_entity_ids") or []
            for eid in linked_for_pid:
                if eid in entity_to_partner:
                    partner_id = entity_to_partner[eid]
                    break
        if not partner_id:
            continue

        linked_ids = _get(doc, "linkedEntityIds", "linked_entity_ids") or []
        for entity_id in linked_ids:
            if not entity_id:
                continue
            if (partner_id, entity_id) not in _imported_scoped.get("entity", set()):
                report.warn(
                    f"document_entities: doc {doc_id} links entity '{entity_id}' not in SQL for partner — skipping"
                )
                continue
            if not dry_run:
                await conn.execute(
                    f"""
                    INSERT INTO {SCHEMA}.document_entities
                        (document_id, entity_id, partner_id)
                    VALUES ($1, $2, $3)
                    ON CONFLICT DO NOTHING
                    """,
                    doc_id, entity_id, partner_id,
                )
            cnt.sql += 1


async def _upsert_protocols(
    conn: asyncpg.Connection,
    protocols_data: list[dict[str, Any]],
    entity_to_partner: dict[str, str],
    report: ReconciliationReport,
    dry_run: bool,
) -> None:
    cnt = report.add("protocols")
    cnt.firestore = len(protocols_data)
    seen_pe: dict[tuple[str, str], str] = {}  # (partner_id, entity_id) → first protocol id

    for doc in protocols_data:
        doc_id = doc["id"]
        entity_id = _clean_str(_get(doc, "entityId", "entity_id")) or None

        # Validate entity_id exists and is in SQL before inserting
        if not entity_id:
            report.warn(f"protocol {doc_id}: empty entity_id — skipping")
            continue

        partner_id = _clean_str(_get(doc, "partnerId", "partner_id")) or None
        if not partner_id:
            partner_id = entity_to_partner.get(entity_id)
        if not partner_id:
            report.warn(f"protocol {doc_id}: no partner_id — skipping")
            continue

        if (partner_id, entity_id) not in _imported_scoped.get("entity", set()):
            report.warn(f"protocol {doc_id}: entity_id '{entity_id}' not in SQL for partner — skipping")
            continue

        content_raw = _get(doc, "content")
        if not isinstance(content_raw, dict):
            content_raw = {}
        content_json = _to_json(content_raw)

        gaps_raw = _get(doc, "gaps")
        if not isinstance(gaps_raw, list):
            gaps_raw = []
        gaps_json = _to_json(gaps_raw)

        now = datetime.now(timezone.utc)
        row = (
            doc_id,
            partner_id,
            entity_id,
            _clean_str(_get(doc, "entityName", "entity_name"), ""),
            content_json,
            gaps_json,
            _clean_str(_get(doc, "version"), "1.0"),
            bool(_get(doc, "confirmedByUser", "confirmed_by_user", default=False)),
            _to_dt(_get(doc, "generatedAt", "generated_at")) or now,
            _to_dt(_get(doc, "updatedAt", "updated_at")) or now,
        )
        # Dedup: if (partner_id, entity_id) already seen, skip this protocol
        pe_key = (partner_id, entity_id)
        if pe_key in seen_pe:
            report.warn(
                f"protocol {doc_id}: duplicate (partner_id, entity_id)={pe_key} "
                f"— keeping first protocol '{seen_pe[pe_key]}', skipping this one"
            )
            continue
        seen_pe[pe_key] = doc_id

        if not dry_run:
            await conn.execute(
                f"""
                INSERT INTO {SCHEMA}.protocols
                    (id, partner_id, entity_id, entity_name, content_json,
                     gaps_json, version, confirmed_by_user,
                     generated_at, updated_at)
                VALUES ($1,$2,$3,$4,$5::jsonb,$6::jsonb,$7,$8,$9,$10)
                ON CONFLICT (id) DO UPDATE SET
                    partner_id = EXCLUDED.partner_id,
                    entity_id = EXCLUDED.entity_id,
                    entity_name = EXCLUDED.entity_name,
                    content_json = EXCLUDED.content_json,
                    gaps_json = EXCLUDED.gaps_json,
                    version = EXCLUDED.version,
                    confirmed_by_user = EXCLUDED.confirmed_by_user,
                    updated_at = EXCLUDED.updated_at
                """,
                *row,
            )
        _register_imported("protocol", doc_id, partner_id)
        cnt.sql += 1


async def _upsert_blindspots(
    conn: asyncpg.Connection,
    blindspots_data: list[dict[str, Any]],
    entity_to_partner: dict[str, str],
    report: ReconciliationReport,
    dry_run: bool,
) -> None:
    cnt = report.add("blindspots")
    cnt.firestore = len(blindspots_data)

    for doc in blindspots_data:
        doc_id = doc["id"]

        partner_id = _clean_str(_get(doc, "partnerId", "partner_id")) or None
        if not partner_id:
            related = _get(doc, "relatedEntityIds", "related_entity_ids") or []
            for eid in related:
                if eid in entity_to_partner:
                    partner_id = entity_to_partner[eid]
                    break
        if not partner_id:
            report.warn(f"blindspot {doc_id}: no partner_id — skipping")
            continue

        severity = _clean_str(_get(doc, "severity"), "yellow")
        _validate_enum(severity, VALID_BLINDSPOT_SEVERITY, f"blindspot {doc_id}.severity")

        bstatus = _clean_str(_get(doc, "status"), "open")
        _validate_enum(bstatus, VALID_BLINDSPOT_STATUS, f"blindspot {doc_id}.status")

        now = datetime.now(timezone.utc)
        row = (
            doc_id,
            partner_id,
            _clean_str(_get(doc, "description"), ""),
            severity,
            _clean_str(_get(doc, "suggestedAction", "suggested_action"), ""),
            bstatus,
            bool(_get(doc, "confirmedByUser", "confirmed_by_user", default=False)),
            _to_dt(_get(doc, "createdAt", "created_at")) or now,
            _to_dt(_get(doc, "updatedAt", "updated_at")) or now,
        )
        if not dry_run:
            await conn.execute(
                f"""
                INSERT INTO {SCHEMA}.blindspots
                    (id, partner_id, description, severity, suggested_action,
                     status, confirmed_by_user, created_at, updated_at)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)
                ON CONFLICT (id) DO UPDATE SET
                    partner_id = EXCLUDED.partner_id,
                    description = EXCLUDED.description,
                    severity = EXCLUDED.severity,
                    suggested_action = EXCLUDED.suggested_action,
                    status = EXCLUDED.status,
                    confirmed_by_user = EXCLUDED.confirmed_by_user,
                    updated_at = EXCLUDED.updated_at
                """,
                *row,
            )
        _register_imported("blindspot", doc_id, partner_id)
        cnt.sql += 1


async def _upsert_blindspot_entities(
    conn: asyncpg.Connection,
    blindspots_data: list[dict[str, Any]],
    entity_to_partner: dict[str, str],
    report: ReconciliationReport,
    dry_run: bool,
) -> None:
    cnt = report.add("blindspot_entities")

    for doc in blindspots_data:
        doc_id = doc["id"]
        partner_id = _clean_str(_get(doc, "partnerId", "partner_id")) or None
        if not partner_id:
            related = _get(doc, "relatedEntityIds", "related_entity_ids") or []
            for eid in related:
                if eid in entity_to_partner:
                    partner_id = entity_to_partner[eid]
                    break
        if not partner_id:
            continue

        related_ids = _get(doc, "relatedEntityIds", "related_entity_ids") or []
        for entity_id in related_ids:
            if not entity_id:
                continue
            if (partner_id, entity_id) not in _imported_scoped.get("entity", set()):
                report.warn(f"blindspot_entities: blindspot {doc_id} links entity '{entity_id}' not in SQL for partner — skipping")
                continue
            if not dry_run:
                await conn.execute(
                    f"""
                    INSERT INTO {SCHEMA}.blindspot_entities
                        (blindspot_id, entity_id, partner_id)
                    VALUES ($1, $2, $3)
                    ON CONFLICT DO NOTHING
                    """,
                    doc_id, entity_id, partner_id,
                )
            cnt.sql += 1


async def _upsert_tasks(
    conn: asyncpg.Connection,
    tasks_data: list[dict[str, Any]],
    report: ReconciliationReport,
    dry_run: bool,
) -> None:
    cnt = report.add("tasks")
    cnt.firestore = len(tasks_data)

    for doc in tasks_data:
        doc_id = doc["id"]
        partner_id = _clean_str(doc.get("_partner_id") or _get(doc, "partnerId", "partner_id"))
        if not partner_id:
            report.warn(f"task {doc_id}: no partner_id — skipping")
            continue

        tstatus = _clean_str(_get(doc, "status"), "backlog")
        _validate_enum(tstatus, VALID_TASK_STATUS, f"task {doc_id}.status")

        tpriority = _clean_str(_get(doc, "priority"), "medium")
        _validate_enum(tpriority, VALID_TASK_PRIORITY, f"task {doc_id}.priority")

        ac_raw = _get(doc, "acceptanceCriteria", "acceptance_criteria")
        if not isinstance(ac_raw, list):
            ac_raw = []
        ac_json = _to_json(ac_raw)

        now = datetime.now(timezone.utc)

        # Satisfy DB constraints: done→completed_at, review→result, blocked→blocked_reason
        completed_at = _to_dt(_get(doc, "completedAt", "completed_at"))
        if tstatus == "done" and completed_at is None:
            completed_at = _to_dt(_get(doc, "updatedAt", "updated_at")) or now
            report.warn(f"task {doc_id}: status=done but no completed_at — backfilled from updatedAt")

        result_val = _clean_str(_get(doc, "result")) or None
        if tstatus == "review" and result_val is None:
            result_val = "(imported — no result recorded)"
            report.warn(f"task {doc_id}: status=review but no result — backfilled placeholder")

        blocked_reason = _clean_str(_get(doc, "blockedReason", "blocked_reason")) or None
        if tstatus == "blocked" and not blocked_reason:
            blocked_reason = "(imported — no reason recorded)"
            report.warn(f"task {doc_id}: status=blocked but no blocked_reason — backfilled placeholder")

        row = (
            doc_id,
            partner_id,
            _clean_str(_get(doc, "title"), doc_id),
            _clean_str(_get(doc, "description"), ""),
            tstatus,
            tpriority,
            _clean_str(_get(doc, "priorityReason", "priority_reason"), ""),
            _clean_str(_get(doc, "assignee")) or None,
            _nullify_dangling_fk(
                _clean_str(_get(doc, "assigneeRoleId", "assignee_role_id")) or None,
                "entity", doc_id, report, partner_id=partner_id,
            ),
            _clean_str(_get(doc, "createdBy", "created_by"), ""),
            _clean_str(_get(doc, "planId", "plan_id")) or None,
            _get(doc, "planOrder", "plan_order"),
            _to_json(_get(doc, "dependsOnTaskIds", "depends_on_task_ids") or []),
            _nullify_dangling_fk(
                _clean_str(_get(doc, "linkedProtocol", "linked_protocol")) or None,
                "protocol", doc_id, report, partner_id=partner_id,
            ),
            _nullify_dangling_fk(
                _clean_str(_get(doc, "linkedBlindspot", "linked_blindspot")) or None,
                "blindspot", doc_id, report, partner_id=partner_id,
            ),
            _clean_str(_get(doc, "sourceType", "source_type"), ""),
            _clean_str(_get(doc, "contextSummary", "context_summary"), ""),
            _to_dt(_get(doc, "dueDate", "due_date")),
            blocked_reason,
            ac_json,
            _clean_str(_get(doc, "completedBy", "completed_by")) or None,
            bool(_get(doc, "confirmedByCreator", "confirmed_by_creator", default=False)),
            _clean_str(_get(doc, "rejectionReason", "rejection_reason")) or None,
            result_val,
            _clean_str(_get(doc, "project"), ""),
            _nullify_dangling_fk(
                _clean_str(_get(doc, "projectId", "project_id")) or None,
                "entity", doc_id, report, partner_id=partner_id,
            ),
            _to_dt(_get(doc, "createdAt", "created_at")) or now,
            _to_dt(_get(doc, "updatedAt", "updated_at")) or now,
            completed_at,
        )
        if not dry_run:
            await conn.execute(
                f"""
                INSERT INTO {SCHEMA}.tasks
                    (id, partner_id, title, description, status, priority,
                     priority_reason, assignee, assignee_role_id, created_by,
                     plan_id, plan_order, depends_on_task_ids_json,
                     linked_protocol, linked_blindspot, source_type,
                     context_summary, due_date, blocked_reason,
                     acceptance_criteria_json, completed_by,
                     confirmed_by_creator, rejection_reason, result,
                     project, project_id, created_at, updated_at, completed_at)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,
                        $11,$12,$13::jsonb,$14,$15,$16,$17,$18,$19,$20::jsonb,
                        $21,$22,$23,$24,$25,$26,$27,$28,$29)
                ON CONFLICT (id) DO UPDATE SET
                    partner_id = EXCLUDED.partner_id,
                    title = EXCLUDED.title,
                    description = EXCLUDED.description,
                    status = EXCLUDED.status,
                    priority = EXCLUDED.priority,
                    priority_reason = EXCLUDED.priority_reason,
                    assignee = EXCLUDED.assignee,
                    assignee_role_id = EXCLUDED.assignee_role_id,
                    created_by = EXCLUDED.created_by,
                    plan_id = EXCLUDED.plan_id,
                    plan_order = EXCLUDED.plan_order,
                    depends_on_task_ids_json = EXCLUDED.depends_on_task_ids_json,
                    linked_protocol = EXCLUDED.linked_protocol,
                    linked_blindspot = EXCLUDED.linked_blindspot,
                    source_type = EXCLUDED.source_type,
                    context_summary = EXCLUDED.context_summary,
                    due_date = EXCLUDED.due_date,
                    blocked_reason = EXCLUDED.blocked_reason,
                    acceptance_criteria_json = EXCLUDED.acceptance_criteria_json,
                    completed_by = EXCLUDED.completed_by,
                    confirmed_by_creator = EXCLUDED.confirmed_by_creator,
                    rejection_reason = EXCLUDED.rejection_reason,
                    result = EXCLUDED.result,
                    project = EXCLUDED.project,
                    project_id = EXCLUDED.project_id,
                    updated_at = EXCLUDED.updated_at,
                    completed_at = EXCLUDED.completed_at
                """,
                *row,
            )
        _register_imported("task", doc_id, partner_id)
        cnt.sql += 1


async def _upsert_task_blockers(
    conn: asyncpg.Connection,
    tasks_data: list[dict[str, Any]],
    report: ReconciliationReport,
    dry_run: bool,
) -> None:
    cnt = report.add("task_blockers")

    for doc in tasks_data:
        doc_id = doc["id"]
        partner_id = _clean_str(doc.get("_partner_id") or _get(doc, "partnerId", "partner_id"))
        if not partner_id:
            continue

        blockers = _get(doc, "blockedBy", "blocked_by") or []
        for blocker_id in blockers:
            if not blocker_id or blocker_id == doc_id:
                continue
            if (partner_id, blocker_id) not in _imported_scoped.get("task", set()):
                report.warn(f"task_blockers: task {doc_id} blocked by '{blocker_id}' not in SQL for partner — skipping")
                continue
            if not dry_run:
                await conn.execute(
                    f"""
                    INSERT INTO {SCHEMA}.task_blockers
                        (task_id, blocker_task_id, partner_id)
                    VALUES ($1, $2, $3)
                    ON CONFLICT DO NOTHING
                    """,
                    doc_id, blocker_id, partner_id,
                )
            cnt.sql += 1


async def _upsert_task_entities(
    conn: asyncpg.Connection,
    tasks_data: list[dict[str, Any]],
    report: ReconciliationReport,
    dry_run: bool,
) -> None:
    cnt = report.add("task_entities")

    for doc in tasks_data:
        doc_id = doc["id"]
        partner_id = _clean_str(doc.get("_partner_id") or _get(doc, "partnerId", "partner_id"))
        if not partner_id:
            continue

        linked = _get(doc, "linkedEntities", "linked_entities") or []
        for entity_id in linked:
            if not entity_id:
                continue
            if (partner_id, entity_id) not in _imported_scoped.get("entity", set()):
                report.warn(f"task_entities: task {doc_id} links entity '{entity_id}' not in SQL for partner — skipping")
                continue
            if not dry_run:
                await conn.execute(
                    f"""
                    INSERT INTO {SCHEMA}.task_entities
                        (task_id, entity_id, partner_id)
                    VALUES ($1, $2, $3)
                    ON CONFLICT DO NOTHING
                    """,
                    doc_id, entity_id, partner_id,
                )
            cnt.sql += 1


async def _upsert_usage_logs(
    conn: asyncpg.Connection,
    usage_logs_data: list[dict[str, Any]],
    report: ReconciliationReport,
    dry_run: bool,
) -> None:
    cnt = report.add("usage_logs")
    cnt.firestore = len(usage_logs_data)

    for doc in usage_logs_data:
        partner_id = _clean_str(
            doc.get("_partner_id") or _get(doc, "partnerId", "partner_id")
        )
        if not partner_id:
            report.warn(f"usage_log {doc.get('id', '?')}: no partner_id — skipping")
            continue

        now = datetime.now(timezone.utc)
        row = (
            partner_id,
            _clean_str(_get(doc, "model"), "unknown"),
            int(_get(doc, "tokensIn", "tokens_in", default=0) or 0),
            int(_get(doc, "tokensOut", "tokens_out", default=0) or 0),
            _to_dt(_get(doc, "createdAt", "created_at")) or now,
        )
        if not dry_run:
            await conn.execute(
                f"""
                INSERT INTO {SCHEMA}.usage_logs
                    (partner_id, model, tokens_in, tokens_out, created_at)
                VALUES ($1,$2,$3,$4,$5)
                """,
                *row,
            )
        cnt.sql += 1


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------

async def run_import(dry_run: bool = False) -> ReconciliationReport:
    """Run the full Firestore → PostgreSQL import pipeline.

    Returns a ReconciliationReport; raises ValueError on enum validation failure.
    """
    database_url = os.environ.get("DATABASE_URL")
    if not database_url and not dry_run:
        raise RuntimeError("DATABASE_URL environment variable is required")

    project = os.environ.get("GOOGLE_CLOUD_PROJECT", "zenos-naruvia")
    print(f"Connecting to Firestore project: {project}")
    db = firestore.AsyncClient(project=project)

    report = ReconciliationReport()
    _imported_ids.clear()
    _imported_scoped.clear()

    # Step 1: read all data from Firestore
    print("Reading partners...")
    partners_data = await _read_partners(db)
    print(f"  {len(partners_data)} partners")

    print("Reading entities...")
    entities_data = await _read_entities(db)
    print(f"  {len(entities_data)} entities")

    print("Reading relationships (subcollections)...")
    relationships_data = await _read_relationships(db, entities_data)
    print(f"  {len(relationships_data)} relationships")

    print("Reading documents...")
    documents_data = await _read_documents(db)
    print(f"  {len(documents_data)} documents")

    print("Reading protocols...")
    protocols_data = await _read_protocols(db)
    print(f"  {len(protocols_data)} protocols")

    print("Reading blindspots...")
    blindspots_data = await _read_blindspots(db)
    print(f"  {len(blindspots_data)} blindspots")

    print("Reading tasks (partner subcollections)...")
    tasks_data = await _read_tasks(db, partners_data)
    print(f"  {len(tasks_data)} tasks")

    print("Reading usage_logs...")
    usage_logs_data = await _read_usage_logs(db, partners_data)
    print(f"  {len(usage_logs_data)} usage_logs")

    # Step 2: build derived indexes
    entity_to_partner = _build_entity_to_partner_index(partners_data)

    # Fallback: if authorizedEntityIds didn't cover any real entities,
    # assign all entities to the admin partner (single-tenant bootstrap).
    real_entity_ids = {e["id"] for e in entities_data}
    matched = real_entity_ids & set(entity_to_partner.keys())
    if not matched:
        admin_partners = [p for p in partners_data if p.get("isAdmin") or p.get("is_admin")]
        if admin_partners:
            admin_id = admin_partners[0]["id"]
            report.warn(
                f"authorizedEntityIds mapped 0 entities — "
                f"falling back to admin partner '{admin_id}' for all {len(entities_data)} entities"
            )
            for e in entities_data:
                entity_to_partner[e["id"]] = admin_id
        else:
            report.warn("authorizedEntityIds mapped 0 entities and no admin partner found")

    project_ids = _derive_project_ids(entities_data, report)

    if dry_run:
        print("\n[DRY RUN] Skipping SQL writes.")
        # Still populate counts for report
        report.add("partners").firestore = len(partners_data)
        report.add("entities").firestore = len(entities_data)
        report.add("relationships").firestore = len(relationships_data)
        report.add("documents").firestore = len(documents_data)
        report.add("document_entities")
        report.add("protocols").firestore = len(protocols_data)
        report.add("blindspots").firestore = len(blindspots_data)
        report.add("blindspot_entities")
        report.add("tasks").firestore = len(tasks_data)
        report.add("task_blockers")
        report.add("task_entities")
        report.add("usage_logs").firestore = len(usage_logs_data)
        return report

    # Step 3: write to PostgreSQL in dependency order
    print(f"\nConnecting to PostgreSQL...")
    conn = await asyncpg.connect(database_url)
    try:
        print("Importing partners...")
        await _upsert_partners(conn, partners_data, report, dry_run)

        print("Importing entities...")
        await _upsert_entities(conn, entities_data, entity_to_partner, project_ids, report, dry_run)

        print("Importing relationships...")
        await _upsert_relationships(conn, relationships_data, entity_to_partner, report, dry_run)

        print("Importing documents...")
        await _upsert_documents(conn, documents_data, entity_to_partner, report, dry_run)

        print("Importing document_entities...")
        await _upsert_document_entities(conn, documents_data, entity_to_partner, report, dry_run)

        print("Importing protocols...")
        await _upsert_protocols(conn, protocols_data, entity_to_partner, report, dry_run)

        print("Importing blindspots...")
        await _upsert_blindspots(conn, blindspots_data, entity_to_partner, report, dry_run)

        print("Importing blindspot_entities...")
        await _upsert_blindspot_entities(conn, blindspots_data, entity_to_partner, report, dry_run)

        print("Importing tasks...")
        await _upsert_tasks(conn, tasks_data, report, dry_run)

        print("Importing task_blockers...")
        await _upsert_task_blockers(conn, tasks_data, report, dry_run)

        print("Importing task_entities...")
        await _upsert_task_entities(conn, tasks_data, report, dry_run)

        print("Importing usage_logs...")
        await _upsert_usage_logs(conn, usage_logs_data, report, dry_run)

    finally:
        await conn.close()

    return report


async def main() -> None:
    dry_run = "--dry-run" in sys.argv
    if dry_run:
        print("=== DRY RUN MODE — no data will be written ===\n")

    report = await run_import(dry_run=dry_run)
    report.print_report()

    if report.errors:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
