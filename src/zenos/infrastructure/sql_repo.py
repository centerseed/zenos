"""PostgreSQL implementations of all domain Repository protocols.

All tables live under the ``zenos`` schema. Every repository reads the
current ``partner_id`` from the ``current_partner_id`` ContextVar so
that callers never have to pass it explicitly.
"""

from __future__ import annotations

import json
import os
import time
import uuid
from datetime import datetime, timezone
from typing import Any

import asyncpg  # type: ignore[import-untyped]

from zenos.domain.models import (
    Blindspot,
    Document,
    DocumentTags,
    Entity,
    Gap,
    Protocol as OntologyProtocol,
    Relationship,
    Source,
    Tags,
    Task,
)
from zenos.infrastructure.context import current_partner_id

# ---------------------------------------------------------------------------
# Connection pool singleton
# ---------------------------------------------------------------------------

SCHEMA = "zenos"
_pool: asyncpg.Pool | None = None


async def get_pool() -> asyncpg.Pool:
    """Return a shared asyncpg connection pool, creating it on first call."""
    global _pool  # noqa: PLW0603
    if _pool is None:
        database_url = os.environ["DATABASE_URL"]
        _pool = await asyncpg.create_pool(database_url, min_size=2, max_size=10)
    return _pool


# ---------------------------------------------------------------------------
# Partner-ID helper
# ---------------------------------------------------------------------------


def _get_partner_id() -> str:
    pid = current_partner_id.get()
    if not pid:
        raise RuntimeError("No partner_id in context")
    return pid


# ---------------------------------------------------------------------------
# General helpers
# ---------------------------------------------------------------------------


def _new_id() -> str:
    """Generate a short unique ID (32-char hex UUID4)."""
    return uuid.uuid4().hex


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _to_dt(val: Any) -> datetime | None:
    if val is None:
        return None
    if isinstance(val, datetime):
        if val.tzinfo is None:
            return val.replace(tzinfo=timezone.utc)
        return val
    return None


def _json_loads_safe(raw: Any) -> Any:
    """Return parsed JSON or the value as-is (asyncpg may auto-decode JSONB)."""
    if raw is None:
        return None
    if isinstance(raw, (dict, list)):
        return raw
    if isinstance(raw, str):
        return json.loads(raw)
    return raw


def _dumps(obj: Any) -> str:
    return json.dumps(obj)


# ===================================================================
# Entity Repository
# ===================================================================


def _row_to_entity(row: asyncpg.Record) -> Entity:
    tags_raw = _json_loads_safe(row["tags_json"]) or {}
    return Entity(
        id=row["id"],
        name=row["name"],
        type=row["type"],
        level=row["level"],
        parent_id=row["parent_id"],
        status=row["status"],
        summary=row["summary"],
        tags=Tags(
            what=tags_raw.get("what", []),
            why=tags_raw.get("why", ""),
            how=tags_raw.get("how", ""),
            who=tags_raw.get("who", []),
        ),
        details=_json_loads_safe(row["details_json"]),
        confirmed_by_user=row["confirmed_by_user"],
        owner=row["owner"],
        sources=_json_loads_safe(row["sources_json"]) or [],
        visibility=row["visibility"],
        last_reviewed_at=_to_dt(row["last_reviewed_at"]),
        created_at=_to_dt(row["created_at"]) or _now(),
        updated_at=_to_dt(row["updated_at"]) or _now(),
    )


class SqlEntityRepository:
    """PostgreSQL-backed EntityRepository."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def get_by_id(self, entity_id: str) -> Entity | None:
        pid = _get_partner_id()
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                f"SELECT * FROM {SCHEMA}.entities WHERE id = $1 AND partner_id = $2",
                entity_id, pid,
            )
        return _row_to_entity(row) if row else None

    async def get_by_name(self, name: str) -> Entity | None:
        pid = _get_partner_id()
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                f"SELECT * FROM {SCHEMA}.entities WHERE name = $1 AND partner_id = $2 LIMIT 1",
                name, pid,
            )
        return _row_to_entity(row) if row else None

    async def list_all(self, type_filter: str | None = None) -> list[Entity]:
        pid = _get_partner_id()
        async with self._pool.acquire() as conn:
            if type_filter is not None:
                rows = await conn.fetch(
                    f"SELECT * FROM {SCHEMA}.entities WHERE partner_id = $1 AND type = $2",
                    pid, type_filter,
                )
            else:
                rows = await conn.fetch(
                    f"SELECT * FROM {SCHEMA}.entities WHERE partner_id = $1",
                    pid,
                )
        return [_row_to_entity(r) for r in rows]

    async def upsert(self, entity: Entity) -> Entity:
        pid = _get_partner_id()
        now = _now()
        entity.updated_at = now
        if entity.id is None:
            entity.id = _new_id()
            entity.created_at = now

        tags_raw = {
            "what": entity.tags.what if isinstance(entity.tags.what, list) else [entity.tags.what],
            "why": entity.tags.why,
            "how": entity.tags.how,
            "who": entity.tags.who if isinstance(entity.tags.who, list) else [entity.tags.who],
        }

        async with self._pool.acquire() as conn:
            await conn.execute(
                f"""
                INSERT INTO {SCHEMA}.entities (
                    id, partner_id, name, type, level, parent_id, status, summary,
                    tags_json, details_json, confirmed_by_user, owner, sources_json,
                    visibility, last_reviewed_at, created_at, updated_at
                ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9::jsonb,$10::jsonb,$11,$12,$13::jsonb,$14,$15,$16,$17)
                ON CONFLICT (id) DO UPDATE SET
                    name=EXCLUDED.name, type=EXCLUDED.type, level=EXCLUDED.level,
                    parent_id=EXCLUDED.parent_id, status=EXCLUDED.status,
                    summary=EXCLUDED.summary, tags_json=EXCLUDED.tags_json,
                    details_json=EXCLUDED.details_json,
                    confirmed_by_user=EXCLUDED.confirmed_by_user,
                    owner=EXCLUDED.owner, sources_json=EXCLUDED.sources_json,
                    visibility=EXCLUDED.visibility,
                    last_reviewed_at=EXCLUDED.last_reviewed_at,
                    updated_at=EXCLUDED.updated_at
                WHERE entities.partner_id = EXCLUDED.partner_id
                """,
                entity.id, pid, entity.name, entity.type, entity.level,
                entity.parent_id, entity.status, entity.summary,
                _dumps(tags_raw),
                _dumps(entity.details) if entity.details is not None else None,
                entity.confirmed_by_user, entity.owner,
                _dumps(entity.sources),
                entity.visibility, entity.last_reviewed_at,
                entity.created_at, entity.updated_at,
            )
        return entity

    async def list_unconfirmed(self) -> list[Entity]:
        pid = _get_partner_id()
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                f"SELECT * FROM {SCHEMA}.entities WHERE confirmed_by_user = false AND partner_id = $1",
                pid,
            )
        return [_row_to_entity(r) for r in rows]

    async def list_by_parent(self, parent_id: str) -> list[Entity]:
        pid = _get_partner_id()
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                f"SELECT * FROM {SCHEMA}.entities WHERE parent_id = $1 AND partner_id = $2",
                parent_id, pid,
            )
        return [_row_to_entity(r) for r in rows]


# ===================================================================
# Relationship Repository
# ===================================================================


def _row_to_relationship(row: asyncpg.Record) -> Relationship:
    return Relationship(
        id=row["id"],
        source_entity_id=row["source_entity_id"],
        target_id=row["target_entity_id"],  # SQL col → domain field
        type=row["type"],
        description=row["description"],
        confirmed_by_user=row["confirmed_by_user"],
    )


class SqlRelationshipRepository:
    """PostgreSQL-backed RelationshipRepository."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def list_by_entity(self, entity_id: str) -> list[Relationship]:
        pid = _get_partner_id()
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                f"""SELECT * FROM {SCHEMA}.relationships
                    WHERE (source_entity_id = $1 OR target_entity_id = $1)
                    AND partner_id = $2""",
                entity_id, pid,
            )
        return [_row_to_relationship(r) for r in rows]

    async def list_all(self) -> list[Relationship]:
        pid = _get_partner_id()
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                f"SELECT * FROM {SCHEMA}.relationships WHERE partner_id = $1",
                pid,
            )
        return [_row_to_relationship(r) for r in rows]

    async def find_duplicate(
        self, source_entity_id: str, target_id: str, rel_type: str,
    ) -> Relationship | None:
        pid = _get_partner_id()
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                f"""SELECT * FROM {SCHEMA}.relationships
                    WHERE source_entity_id = $1 AND target_entity_id = $2
                    AND type = $3 AND partner_id = $4 LIMIT 1""",
                source_entity_id, target_id, rel_type, pid,
            )
        return _row_to_relationship(row) if row else None

    async def add(self, rel: Relationship) -> Relationship:
        pid = _get_partner_id()
        now = _now()
        if rel.id is None:
            rel.id = _new_id()

        async with self._pool.acquire() as conn:
            await conn.execute(
                f"""
                INSERT INTO {SCHEMA}.relationships (
                    id, partner_id, source_entity_id, target_entity_id,
                    type, description, confirmed_by_user, created_at, updated_at
                ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)
                ON CONFLICT (id) DO UPDATE SET
                    source_entity_id=EXCLUDED.source_entity_id,
                    target_entity_id=EXCLUDED.target_entity_id,
                    type=EXCLUDED.type, description=EXCLUDED.description,
                    confirmed_by_user=EXCLUDED.confirmed_by_user,
                    updated_at=EXCLUDED.updated_at
                WHERE relationships.partner_id = EXCLUDED.partner_id
                """,
                rel.id, pid, rel.source_entity_id, rel.target_id,
                rel.type, rel.description, rel.confirmed_by_user, now, now,
            )
        return rel


# ===================================================================
# Document Repository
# ===================================================================


def _row_to_document(row: asyncpg.Record, linked_entity_ids: list[str]) -> Document:
    source_raw = _json_loads_safe(row["source_json"]) or {}
    tags_raw = _json_loads_safe(row["tags_json"]) or {}
    return Document(
        id=row["id"],
        title=row["title"],
        source=Source(
            type=source_raw.get("type", ""),
            uri=source_raw.get("uri", ""),
            adapter=source_raw.get("adapter", ""),
        ),
        tags=DocumentTags(
            what=tags_raw.get("what", []),
            why=tags_raw.get("why", ""),
            how=tags_raw.get("how", ""),
            who=tags_raw.get("who", []),
        ),
        linked_entity_ids=linked_entity_ids,
        summary=row["summary"],
        status=row["status"],
        confirmed_by_user=row["confirmed_by_user"],
        last_reviewed_at=_to_dt(row["last_reviewed_at"]),
        created_at=_to_dt(row["created_at"]) or _now(),
        updated_at=_to_dt(row["updated_at"]) or _now(),
    )


class SqlDocumentRepository:
    """PostgreSQL-backed DocumentRepository."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def _fetch_linked_entity_ids(self, conn: asyncpg.Connection, doc_id: str, pid: str) -> list[str]:
        rows = await conn.fetch(
            f"SELECT entity_id FROM {SCHEMA}.document_entities WHERE document_id = $1 AND partner_id = $2",
            doc_id, pid,
        )
        return [r["entity_id"] for r in rows]

    async def get_by_id(self, doc_id: str) -> Document | None:
        pid = _get_partner_id()
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                f"SELECT * FROM {SCHEMA}.documents WHERE id = $1 AND partner_id = $2",
                doc_id, pid,
            )
            if not row:
                return None
            linked = await self._fetch_linked_entity_ids(conn, doc_id, pid)
        return _row_to_document(row, linked)

    async def list_all(self) -> list[Document]:
        pid = _get_partner_id()
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                f"SELECT * FROM {SCHEMA}.documents WHERE partner_id = $1",
                pid,
            )
            if not rows:
                return []
            doc_ids = [r["id"] for r in rows]
            link_rows = await conn.fetch(
                f"SELECT document_id, entity_id FROM {SCHEMA}.document_entities"
                f" WHERE partner_id = $1 AND document_id = ANY($2::text[])",
                pid, doc_ids,
            )
        links: dict[str, list[str]] = {}
        for lr in link_rows:
            links.setdefault(lr["document_id"], []).append(lr["entity_id"])
        return [_row_to_document(r, links.get(r["id"], [])) for r in rows]

    async def upsert(self, doc: Document) -> Document:
        pid = _get_partner_id()
        now = _now()
        doc.updated_at = now
        if doc.id is None:
            doc.id = _new_id()
            doc.created_at = now

        source_dict = {"type": doc.source.type, "uri": doc.source.uri, "adapter": doc.source.adapter}
        tags_dict = {"what": doc.tags.what, "why": doc.tags.why, "how": doc.tags.how, "who": doc.tags.who}

        async with self._pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    f"""
                INSERT INTO {SCHEMA}.documents (
                    id, partner_id, title, source_json, tags_json, summary,
                    status, confirmed_by_user, last_reviewed_at, created_at, updated_at
                ) VALUES ($1,$2,$3,$4::jsonb,$5::jsonb,$6,$7,$8,$9,$10,$11)
                ON CONFLICT (id) DO UPDATE SET
                    title=EXCLUDED.title, source_json=EXCLUDED.source_json,
                    tags_json=EXCLUDED.tags_json, summary=EXCLUDED.summary,
                    status=EXCLUDED.status, confirmed_by_user=EXCLUDED.confirmed_by_user,
                    last_reviewed_at=EXCLUDED.last_reviewed_at, updated_at=EXCLUDED.updated_at
                WHERE documents.partner_id = EXCLUDED.partner_id
                """,
                    doc.id, pid, doc.title, _dumps(source_dict), _dumps(tags_dict),
                    doc.summary, doc.status, doc.confirmed_by_user,
                    doc.last_reviewed_at, doc.created_at, doc.updated_at,
                )
                # Sync document_entities join table
                await conn.execute(
                    f"DELETE FROM {SCHEMA}.document_entities WHERE document_id = $1 AND partner_id = $2",
                    doc.id, pid,
                )
                if doc.linked_entity_ids:
                    await conn.executemany(
                        f"INSERT INTO {SCHEMA}.document_entities (document_id, entity_id, partner_id)"
                        f" VALUES ($1, $2, $3) ON CONFLICT DO NOTHING",
                        [(doc.id, eid, pid) for eid in doc.linked_entity_ids],
                    )
        return doc

    async def list_by_entity(self, entity_id: str) -> list[Document]:
        pid = _get_partner_id()
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                f"""SELECT d.* FROM {SCHEMA}.documents d
                    JOIN {SCHEMA}.document_entities de ON d.id = de.document_id
                    WHERE de.entity_id = $1 AND d.partner_id = $2""",
                entity_id, pid,
            )
            if not rows:
                return []
            doc_ids = [r["id"] for r in rows]
            link_rows = await conn.fetch(
                f"SELECT document_id, entity_id FROM {SCHEMA}.document_entities"
                f" WHERE partner_id = $1 AND document_id = ANY($2::text[])",
                pid, doc_ids,
            )
        links: dict[str, list[str]] = {}
        for lr in link_rows:
            links.setdefault(lr["document_id"], []).append(lr["entity_id"])
        return [_row_to_document(r, links.get(r["id"], [])) for r in rows]

    async def update_linked_entities(self, doc_id: str, linked_entity_ids: list[str]) -> None:
        """Replace the linked_entity_ids for a document without a full upsert."""
        pid = _get_partner_id()
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    f"DELETE FROM {SCHEMA}.document_entities WHERE document_id = $1 AND partner_id = $2",
                    doc_id, pid,
                )
                if linked_entity_ids:
                    await conn.executemany(
                        f"INSERT INTO {SCHEMA}.document_entities (document_id, entity_id, partner_id)"
                        f" VALUES ($1, $2, $3) ON CONFLICT DO NOTHING",
                        [(doc_id, eid, pid) for eid in linked_entity_ids],
                    )

    async def list_unconfirmed(self) -> list[Document]:
        pid = _get_partner_id()
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                f"SELECT * FROM {SCHEMA}.documents WHERE confirmed_by_user = false AND partner_id = $1",
                pid,
            )
            if not rows:
                return []
            doc_ids = [r["id"] for r in rows]
            link_rows = await conn.fetch(
                f"SELECT document_id, entity_id FROM {SCHEMA}.document_entities"
                f" WHERE partner_id = $1 AND document_id = ANY($2::text[])",
                pid, doc_ids,
            )
        links: dict[str, list[str]] = {}
        for lr in link_rows:
            links.setdefault(lr["document_id"], []).append(lr["entity_id"])
        return [_row_to_document(r, links.get(r["id"], [])) for r in rows]


# ===================================================================
# Protocol Repository
# ===================================================================


def _row_to_protocol(row: asyncpg.Record) -> OntologyProtocol:
    gaps_raw = _json_loads_safe(row["gaps_json"]) or []
    gaps = [
        Gap(description=g.get("description", ""), priority=g.get("priority", "green"))
        for g in gaps_raw
    ]
    return OntologyProtocol(
        id=row["id"],
        entity_id=row["entity_id"],
        entity_name=row["entity_name"],
        content=_json_loads_safe(row["content_json"]) or {},
        gaps=gaps,
        version=row["version"],
        confirmed_by_user=row["confirmed_by_user"],
        generated_at=_to_dt(row["generated_at"]) or _now(),
        updated_at=_to_dt(row["updated_at"]) or _now(),
    )


class SqlProtocolRepository:
    """PostgreSQL-backed ProtocolRepository."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def get_by_id(self, protocol_id: str) -> OntologyProtocol | None:
        pid = _get_partner_id()
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                f"SELECT * FROM {SCHEMA}.protocols WHERE id = $1 AND partner_id = $2",
                protocol_id, pid,
            )
        return _row_to_protocol(row) if row else None

    async def get_by_entity(self, entity_id: str) -> OntologyProtocol | None:
        pid = _get_partner_id()
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                f"SELECT * FROM {SCHEMA}.protocols WHERE entity_id = $1 AND partner_id = $2 LIMIT 1",
                entity_id, pid,
            )
        return _row_to_protocol(row) if row else None

    async def get_by_entity_name(self, name: str) -> OntologyProtocol | None:
        pid = _get_partner_id()
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                f"SELECT * FROM {SCHEMA}.protocols WHERE entity_name = $1 AND partner_id = $2 LIMIT 1",
                name, pid,
            )
        return _row_to_protocol(row) if row else None

    async def upsert(self, protocol: OntologyProtocol) -> OntologyProtocol:
        pid = _get_partner_id()
        now = _now()
        protocol.updated_at = now
        if protocol.id is None:
            protocol.id = _new_id()
            protocol.generated_at = now

        gaps_list = [{"description": g.description, "priority": g.priority} for g in protocol.gaps]

        async with self._pool.acquire() as conn:
            await conn.execute(
                f"""
                INSERT INTO {SCHEMA}.protocols (
                    id, partner_id, entity_id, entity_name, content_json,
                    gaps_json, version, confirmed_by_user, generated_at, updated_at
                ) VALUES ($1,$2,$3,$4,$5::jsonb,$6::jsonb,$7,$8,$9,$10)
                ON CONFLICT (id) DO UPDATE SET
                    entity_id=EXCLUDED.entity_id, entity_name=EXCLUDED.entity_name,
                    content_json=EXCLUDED.content_json, gaps_json=EXCLUDED.gaps_json,
                    version=EXCLUDED.version, confirmed_by_user=EXCLUDED.confirmed_by_user,
                    updated_at=EXCLUDED.updated_at
                WHERE protocols.partner_id = EXCLUDED.partner_id
                """,
                protocol.id, pid, protocol.entity_id, protocol.entity_name,
                _dumps(protocol.content), _dumps(gaps_list),
                protocol.version, protocol.confirmed_by_user,
                protocol.generated_at, protocol.updated_at,
            )
        return protocol

    async def list_unconfirmed(self) -> list[OntologyProtocol]:
        pid = _get_partner_id()
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                f"SELECT * FROM {SCHEMA}.protocols WHERE confirmed_by_user = false AND partner_id = $1",
                pid,
            )
        return [_row_to_protocol(r) for r in rows]


# ===================================================================
# Blindspot Repository
# ===================================================================


def _row_to_blindspot(row: asyncpg.Record, related_entity_ids: list[str]) -> Blindspot:
    return Blindspot(
        id=row["id"],
        description=row["description"],
        severity=row["severity"],
        related_entity_ids=related_entity_ids,
        suggested_action=row["suggested_action"],
        status=row["status"],
        confirmed_by_user=row["confirmed_by_user"],
        created_at=_to_dt(row["created_at"]) or _now(),
    )


class SqlBlindspotRepository:
    """PostgreSQL-backed BlindspotRepository."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def _fetch_related_entity_ids(self, conn: asyncpg.Connection, blindspot_id: str, pid: str) -> list[str]:
        rows = await conn.fetch(
            f"SELECT entity_id FROM {SCHEMA}.blindspot_entities WHERE blindspot_id = $1 AND partner_id = $2",
            blindspot_id, pid,
        )
        return [r["entity_id"] for r in rows]

    async def list_all(
        self,
        entity_id: str | None = None,
        severity: str | None = None,
    ) -> list[Blindspot]:
        pid = _get_partner_id()
        async with self._pool.acquire() as conn:
            if entity_id is not None and severity is not None:
                rows = await conn.fetch(
                    f"""SELECT DISTINCT b.* FROM {SCHEMA}.blindspots b
                        JOIN {SCHEMA}.blindspot_entities be ON b.id = be.blindspot_id
                        WHERE be.entity_id = $1 AND b.severity = $2 AND b.partner_id = $3""",
                    entity_id, severity, pid,
                )
            elif entity_id is not None:
                rows = await conn.fetch(
                    f"""SELECT DISTINCT b.* FROM {SCHEMA}.blindspots b
                        JOIN {SCHEMA}.blindspot_entities be ON b.id = be.blindspot_id
                        WHERE be.entity_id = $1 AND b.partner_id = $2""",
                    entity_id, pid,
                )
            elif severity is not None:
                rows = await conn.fetch(
                    f"SELECT * FROM {SCHEMA}.blindspots WHERE severity = $1 AND partner_id = $2",
                    severity, pid,
                )
            else:
                rows = await conn.fetch(
                    f"SELECT * FROM {SCHEMA}.blindspots WHERE partner_id = $1",
                    pid,
                )
            if not rows:
                return []
            bs_ids = [r["id"] for r in rows]
            link_rows = await conn.fetch(
                f"SELECT blindspot_id, entity_id FROM {SCHEMA}.blindspot_entities"
                f" WHERE partner_id = $1 AND blindspot_id = ANY($2::text[])",
                pid, bs_ids,
            )
        links: dict[str, list[str]] = {}
        for lr in link_rows:
            links.setdefault(lr["blindspot_id"], []).append(lr["entity_id"])
        return [_row_to_blindspot(r, links.get(r["id"], [])) for r in rows]

    async def add(self, blindspot: Blindspot) -> Blindspot:
        pid = _get_partner_id()
        now = _now()
        if blindspot.created_at is None:  # type: ignore[comparison-overlap]
            blindspot.created_at = now
        if blindspot.id is None:
            blindspot.id = _new_id()

        async with self._pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    f"""
                INSERT INTO {SCHEMA}.blindspots (
                    id, partner_id, description, severity, suggested_action,
                    status, confirmed_by_user, created_at, updated_at
                ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)
                ON CONFLICT (id) DO UPDATE SET
                    description=EXCLUDED.description, severity=EXCLUDED.severity,
                    suggested_action=EXCLUDED.suggested_action, status=EXCLUDED.status,
                    confirmed_by_user=EXCLUDED.confirmed_by_user,
                    updated_at=EXCLUDED.updated_at
                WHERE blindspots.partner_id = EXCLUDED.partner_id
                """,
                    blindspot.id, pid, blindspot.description, blindspot.severity,
                    blindspot.suggested_action, blindspot.status,
                    blindspot.confirmed_by_user, blindspot.created_at, now,
                )
                # Sync blindspot_entities join table
                await conn.execute(
                    f"DELETE FROM {SCHEMA}.blindspot_entities WHERE blindspot_id = $1 AND partner_id = $2",
                    blindspot.id, pid,
                )
                if blindspot.related_entity_ids:
                    await conn.executemany(
                        f"INSERT INTO {SCHEMA}.blindspot_entities (blindspot_id, entity_id, partner_id)"
                        f" VALUES ($1, $2, $3) ON CONFLICT DO NOTHING",
                        [(blindspot.id, eid, pid) for eid in blindspot.related_entity_ids],
                    )
        return blindspot

    async def list_unconfirmed(self) -> list[Blindspot]:
        pid = _get_partner_id()
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                f"SELECT * FROM {SCHEMA}.blindspots WHERE confirmed_by_user = false AND partner_id = $1",
                pid,
            )
            if not rows:
                return []
            bs_ids = [r["id"] for r in rows]
            link_rows = await conn.fetch(
                f"SELECT blindspot_id, entity_id FROM {SCHEMA}.blindspot_entities"
                f" WHERE partner_id = $1 AND blindspot_id = ANY($2::text[])",
                pid, bs_ids,
            )
        links: dict[str, list[str]] = {}
        for lr in link_rows:
            links.setdefault(lr["blindspot_id"], []).append(lr["entity_id"])
        return [_row_to_blindspot(r, links.get(r["id"], [])) for r in rows]

    async def get_by_id(self, blindspot_id: str) -> Blindspot | None:
        pid = _get_partner_id()
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                f"SELECT * FROM {SCHEMA}.blindspots WHERE id = $1 AND partner_id = $2",
                blindspot_id, pid,
            )
            if not row:
                return None
            related = await self._fetch_related_entity_ids(conn, blindspot_id, pid)
        return _row_to_blindspot(row, related)


# ===================================================================
# Task Repository
# ===================================================================


def _row_to_task(row: asyncpg.Record, linked_entities: list[str], blocked_by: list[str]) -> Task:
    return Task(
        id=row["id"],
        title=row["title"],
        description=row["description"],
        status=row["status"],
        priority=row["priority"],
        priority_reason=row["priority_reason"],
        assignee=row["assignee"],
        assignee_role_id=row["assignee_role_id"],
        created_by=row["created_by"],
        linked_entities=linked_entities,
        linked_protocol=row["linked_protocol"],
        linked_blindspot=row["linked_blindspot"],
        source_type=row["source_type"],
        context_summary=row["context_summary"],
        due_date=_to_dt(row["due_date"]),
        blocked_by=blocked_by,
        blocked_reason=row["blocked_reason"],
        acceptance_criteria=_json_loads_safe(row["acceptance_criteria_json"]) or [],
        completed_by=row["completed_by"],
        confirmed_by_creator=row["confirmed_by_creator"],
        rejection_reason=row["rejection_reason"],
        result=row["result"],
        project=row["project"],
        created_at=_to_dt(row["created_at"]) or _now(),
        updated_at=_to_dt(row["updated_at"]) or _now(),
        completed_at=_to_dt(row["completed_at"]),
    )


class SqlTaskRepository:
    """PostgreSQL-backed TaskRepository."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def _fetch_task_relations(
        self, conn: asyncpg.Connection, task_id: str, pid: str,
    ) -> tuple[list[str], list[str]]:
        entity_rows = await conn.fetch(
            f"SELECT entity_id FROM {SCHEMA}.task_entities WHERE task_id = $1 AND partner_id = $2",
            task_id, pid,
        )
        blocker_rows = await conn.fetch(
            f"SELECT blocker_task_id FROM {SCHEMA}.task_blockers WHERE task_id = $1 AND partner_id = $2",
            task_id, pid,
        )
        linked_entities = [r["entity_id"] for r in entity_rows]
        blocked_by = [r["blocker_task_id"] for r in blocker_rows]
        return linked_entities, blocked_by

    async def _batch_fetch_task_relations(
        self, conn: asyncpg.Connection, task_ids: list[str], pid: str,
    ) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
        """Batch-fetch linked_entities and blocked_by for a list of task IDs."""
        entity_rows = await conn.fetch(
            f"SELECT task_id, entity_id FROM {SCHEMA}.task_entities"
            f" WHERE partner_id = $1 AND task_id = ANY($2::text[])",
            pid, task_ids,
        )
        blocker_rows = await conn.fetch(
            f"SELECT task_id, blocker_task_id FROM {SCHEMA}.task_blockers"
            f" WHERE partner_id = $1 AND task_id = ANY($2::text[])",
            pid, task_ids,
        )
        linked_map: dict[str, list[str]] = {}
        for er in entity_rows:
            linked_map.setdefault(er["task_id"], []).append(er["entity_id"])
        blocker_map: dict[str, list[str]] = {}
        for br in blocker_rows:
            blocker_map.setdefault(br["task_id"], []).append(br["blocker_task_id"])
        return linked_map, blocker_map

    def _rows_to_tasks(
        self,
        rows: list[asyncpg.Record],
        linked_map: dict[str, list[str]],
        blocker_map: dict[str, list[str]],
    ) -> list[Task]:
        return [
            _row_to_task(r, linked_map.get(r["id"], []), blocker_map.get(r["id"], []))
            for r in rows
        ]

    async def get_by_id(self, task_id: str) -> Task | None:
        pid = _get_partner_id()
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                f"SELECT * FROM {SCHEMA}.tasks WHERE id = $1 AND partner_id = $2",
                task_id, pid,
            )
            if not row:
                return None
            linked_entities, blocked_by = await self._fetch_task_relations(conn, task_id, pid)
        return _row_to_task(row, linked_entities, blocked_by)

    async def upsert(self, task: Task) -> Task:
        pid = _get_partner_id()
        now = _now()
        task.updated_at = now
        if task.id is None:
            task.id = _new_id()
            task.created_at = now

        async with self._pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    f"""
                INSERT INTO {SCHEMA}.tasks (
                    id, partner_id, title, description, status, priority,
                    priority_reason, assignee, assignee_role_id, created_by,
                    linked_protocol, linked_blindspot, source_type, context_summary,
                    due_date, blocked_reason, acceptance_criteria_json, completed_by,
                    confirmed_by_creator, rejection_reason, result, project,
                    created_at, updated_at, completed_at
                ) VALUES (
                    $1,$2,$3,$4,$5,$6,$7,$8,$9,$10,
                    $11,$12,$13,$14,$15,$16,$17::jsonb,$18,$19,$20,$21,$22,$23,$24,$25
                )
                ON CONFLICT (id) DO UPDATE SET
                    title=EXCLUDED.title, description=EXCLUDED.description,
                    status=EXCLUDED.status, priority=EXCLUDED.priority,
                    priority_reason=EXCLUDED.priority_reason,
                    assignee=EXCLUDED.assignee,
                    assignee_role_id=EXCLUDED.assignee_role_id,
                    linked_protocol=EXCLUDED.linked_protocol,
                    linked_blindspot=EXCLUDED.linked_blindspot,
                    source_type=EXCLUDED.source_type,
                    context_summary=EXCLUDED.context_summary,
                    due_date=EXCLUDED.due_date,
                    blocked_reason=EXCLUDED.blocked_reason,
                    acceptance_criteria_json=EXCLUDED.acceptance_criteria_json,
                    completed_by=EXCLUDED.completed_by,
                    confirmed_by_creator=EXCLUDED.confirmed_by_creator,
                    rejection_reason=EXCLUDED.rejection_reason,
                    result=EXCLUDED.result, project=EXCLUDED.project,
                    updated_at=EXCLUDED.updated_at,
                    completed_at=EXCLUDED.completed_at
                WHERE tasks.partner_id = EXCLUDED.partner_id
                """,
                    task.id, pid, task.title, task.description, task.status,
                    task.priority, task.priority_reason, task.assignee,
                    task.assignee_role_id, task.created_by,
                    task.linked_protocol, task.linked_blindspot,
                    task.source_type, task.context_summary, task.due_date,
                    task.blocked_reason, _dumps(task.acceptance_criteria),
                    task.completed_by, task.confirmed_by_creator,
                    task.rejection_reason, task.result, task.project,
                    task.created_at, task.updated_at, task.completed_at,
                )
                # Sync task_entities join table
                await conn.execute(
                    f"DELETE FROM {SCHEMA}.task_entities WHERE task_id = $1 AND partner_id = $2",
                    task.id, pid,
                )
                if task.linked_entities:
                    await conn.executemany(
                        f"INSERT INTO {SCHEMA}.task_entities (task_id, entity_id, partner_id)"
                        f" VALUES ($1, $2, $3) ON CONFLICT DO NOTHING",
                        [(task.id, eid, pid) for eid in task.linked_entities],
                    )
                # Sync task_blockers join table
                await conn.execute(
                    f"DELETE FROM {SCHEMA}.task_blockers WHERE task_id = $1 AND partner_id = $2",
                    task.id, pid,
                )
                if task.blocked_by:
                    await conn.executemany(
                        f"INSERT INTO {SCHEMA}.task_blockers (task_id, blocker_task_id, partner_id)"
                        f" VALUES ($1, $2, $3) ON CONFLICT DO NOTHING",
                        [(task.id, bid, pid) for bid in task.blocked_by],
                    )
        return task

    async def list_all(
        self,
        *,
        assignee: str | None = None,
        created_by: str | None = None,
        status: list[str] | None = None,
        priority: str | None = None,
        linked_entity: str | None = None,
        include_archived: bool = False,
        limit: int = 50,
        project: str | None = None,
    ) -> list[Task]:
        pid = _get_partner_id()

        conditions = ["t.partner_id = $1"]
        params: list[Any] = [pid]
        idx = 2

        if assignee is not None:
            conditions.append(f"t.assignee = ${idx}")
            params.append(assignee)
            idx += 1
        if created_by is not None:
            conditions.append(f"t.created_by = ${idx}")
            params.append(created_by)
            idx += 1
        if priority is not None:
            conditions.append(f"t.priority = ${idx}")
            params.append(priority)
            idx += 1
        if project is not None:
            conditions.append(f"t.project = ${idx}")
            params.append(project)
            idx += 1
        if status is not None:
            placeholders = ", ".join(f"${i}" for i in range(idx, idx + len(status)))
            conditions.append(f"t.status IN ({placeholders})")
            params.extend(status)
            idx += len(status)
        elif not include_archived:
            conditions.append("t.status <> 'archived'")

        where_clause = " AND ".join(conditions)

        if linked_entity is not None:
            join_clause = f"JOIN {SCHEMA}.task_entities te ON t.id = te.task_id AND te.entity_id = ${idx}"
            params.append(linked_entity)
            idx += 1
        else:
            join_clause = ""

        sql = (
            f"SELECT DISTINCT t.* FROM {SCHEMA}.tasks t {join_clause}"
            f" WHERE {where_clause} LIMIT ${idx}"
        )
        params.append(limit)

        async with self._pool.acquire() as conn:
            rows = await conn.fetch(sql, *params)
            if not rows:
                return []
            task_ids = [r["id"] for r in rows]
            linked_map, blocker_map = await self._batch_fetch_task_relations(conn, task_ids, pid)

        return self._rows_to_tasks(rows, linked_map, blocker_map)

    async def list_blocked_by(self, task_id: str) -> list[Task]:
        """Return all tasks that are blocked by the given task_id."""
        pid = _get_partner_id()
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                f"""SELECT DISTINCT t.* FROM {SCHEMA}.tasks t
                    JOIN {SCHEMA}.task_blockers tb ON t.id = tb.task_id
                    WHERE tb.blocker_task_id = $1 AND t.partner_id = $2""",
                task_id, pid,
            )
            if not rows:
                return []
            task_ids = [r["id"] for r in rows]
            linked_map, blocker_map = await self._batch_fetch_task_relations(conn, task_ids, pid)

        return self._rows_to_tasks(rows, linked_map, blocker_map)

    async def list_pending_review(self) -> list[Task]:
        pid = _get_partner_id()
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                f"""SELECT * FROM {SCHEMA}.tasks
                    WHERE status = 'review' AND confirmed_by_creator = false
                    AND partner_id = $1""",
                pid,
            )
            if not rows:
                return []
            task_ids = [r["id"] for r in rows]
            linked_map, blocker_map = await self._batch_fetch_task_relations(conn, task_ids, pid)

        return self._rows_to_tasks(rows, linked_map, blocker_map)


# ===================================================================
# PartnerKeyValidator (SQL version)
# ===================================================================

class SqlPartnerKeyValidator:
    """Validates API keys against the SQL partners table.

    Caches active partner keys in memory with a configurable TTL to avoid
    a database round-trip on every request.
    """

    def __init__(self, ttl: int = 300) -> None:
        self._cache: dict[str, dict] = {}
        self._cache_ts: float = 0.0
        self._ttl = ttl

    async def validate(self, key: str) -> dict | None:
        """Return partner data dict if *key* belongs to an active partner."""
        now = time.time()
        if now - self._cache_ts > self._ttl:
            await self._refresh_cache()
        return self._cache.get(key)

    async def _refresh_cache(self) -> None:
        import logging
        logger = logging.getLogger(__name__)
        try:
            pool = await get_pool()
            async with pool.acquire() as conn:
                rows = await conn.fetch(
                    f"""SELECT id, email, display_name, api_key,
                               authorized_entity_ids, status, is_admin,
                               shared_partner_id, default_project
                        FROM {SCHEMA}.partners WHERE status = 'active'"""
                )
            new_cache: dict[str, dict] = {}
            for row in rows:
                api_key = row["api_key"]
                if api_key:
                    new_cache[api_key] = {
                        "id": row["id"],
                        "email": row["email"],
                        "displayName": row["display_name"],
                        "apiKey": row["api_key"],
                        "authorizedEntityIds": list(row["authorized_entity_ids"] or []),
                        "status": row["status"],
                        "isAdmin": row["is_admin"],
                        "sharedPartnerId": row["shared_partner_id"],
                        "defaultProject": row["default_project"],
                    }
            self._cache = new_cache
            self._cache_ts = time.time()
            logger.info("Partner cache refreshed from SQL: %d active keys", len(new_cache))
        except Exception:
            logger.exception("Failed to refresh partner cache from SQL")
            if not self._cache:
                self._cache_ts = time.time()
