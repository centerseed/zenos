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
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any

import asyncpg  # type: ignore[import-untyped]

from zenos.domain.models import (
    Blindspot,
    Document,
    DocumentTags,
    Entity,
    EntityEntry,
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
    """Return a shared asyncpg connection pool, creating it on first call.

    Supports Cloud SQL socket URLs (``?host=/cloudsql/...``) by extracting
    the Unix socket path from the query string and passing it to asyncpg
    as the ``host`` parameter.
    """
    global _pool  # noqa: PLW0603
    if _pool is None:
        from urllib.parse import urlparse, parse_qs

        database_url = os.environ["DATABASE_URL"]
        parsed = urlparse(database_url)
        socket_host = parse_qs(parsed.query).get("host", [None])[0]

        if socket_host:
            _pool = await asyncpg.create_pool(
                user=parsed.username,
                password=parsed.password,
                database=parsed.path.lstrip("/"),
                host=socket_host,
                min_size=2,
                max_size=10,
            )
        else:
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
# Connection helpers
# ---------------------------------------------------------------------------


@asynccontextmanager
async def _acquire(pool: asyncpg.Pool, conn: asyncpg.Connection | None):
    """Yield an existing connection or acquire one from the pool."""
    if conn is not None:
        yield conn
        return
    c = await pool.acquire()
    try:
        yield c
    finally:
        await pool.release(c)


@asynccontextmanager
async def _acquire_with_tx(pool: asyncpg.Pool, conn: asyncpg.Connection | None):
    """Like _acquire, but also starts a transaction when using a pool connection."""
    if conn is not None:
        yield conn
        return
    c = await pool.acquire()
    try:
        async with c.transaction():
            yield c
    finally:
        await pool.release(c)


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
        visible_to_roles=list(row["visible_to_roles"] or []) if "visible_to_roles" in row else [],
        visible_to_members=list(row["visible_to_members"] or []) if "visible_to_members" in row else [],
        visible_to_departments=list(row["visible_to_departments"] or []) if "visible_to_departments" in row else [],
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
                f"SELECT * FROM {SCHEMA}.entities WHERE LOWER(name) = LOWER($1) AND partner_id = $2 LIMIT 1",
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

    async def upsert(self, entity: Entity, *, conn: asyncpg.Connection | None = None) -> Entity:
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

        async with _acquire(self._pool, conn) as _conn:
            await _conn.execute(
                f"""
                INSERT INTO {SCHEMA}.entities (
                    id, partner_id, name, type, level, parent_id, status, summary,
                    tags_json, details_json, confirmed_by_user, owner, sources_json,
                    visibility, visible_to_roles, visible_to_members,
                    visible_to_departments, last_reviewed_at, created_at, updated_at
                ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9::jsonb,$10::jsonb,$11,$12,$13::jsonb,$14,$15,$16,$17,$18,$19,$20)
                ON CONFLICT (id) DO UPDATE SET
                    name=EXCLUDED.name, type=EXCLUDED.type, level=EXCLUDED.level,
                    parent_id=EXCLUDED.parent_id, status=EXCLUDED.status,
                    summary=EXCLUDED.summary, tags_json=EXCLUDED.tags_json,
                    details_json=EXCLUDED.details_json,
                    confirmed_by_user=EXCLUDED.confirmed_by_user,
                    owner=EXCLUDED.owner, sources_json=EXCLUDED.sources_json,
                    visibility=EXCLUDED.visibility,
                    visible_to_roles=EXCLUDED.visible_to_roles,
                    visible_to_members=EXCLUDED.visible_to_members,
                    visible_to_departments=EXCLUDED.visible_to_departments,
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
                entity.visibility, entity.visible_to_roles,
                entity.visible_to_members, entity.visible_to_departments,
                entity.last_reviewed_at,
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

    async def update_source_status(self, entity_id: str, new_status: str) -> None:
        """Update sources[0].status for a document entity."""
        pid = _get_partner_id()
        async with self._pool.acquire() as conn:
            await conn.execute(
                f"""UPDATE {SCHEMA}.entities
                    SET sources_json = jsonb_set(
                        sources_json,
                        '{{0,status}}',
                        $1::jsonb,
                        true
                    ),
                    updated_at = now()
                    WHERE id = $2 AND partner_id = $3""",
                json.dumps(new_status), entity_id, pid,
            )

    async def archive_entity(self, entity_id: str) -> None:
        """Archive an entity by setting its status to 'archived' (exits search space).

        Used for dead-link document entities that cannot be recovered. Unlike 'stale',
        'archived' unambiguously marks the entity as intentionally removed from the
        search space due to an unresolvable source link.
        """
        pid = _get_partner_id()
        async with self._pool.acquire() as conn:
            await conn.execute(
                f"""UPDATE {SCHEMA}.entities
                    SET status = 'archived',
                        updated_at = now()
                    WHERE id = $1 AND partner_id = $2""",
                entity_id, pid,
            )


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
        verb=row.get("verb"),
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

    async def add(self, rel: Relationship, *, conn: asyncpg.Connection | None = None) -> Relationship:
        pid = _get_partner_id()
        now = _now()
        if rel.id is None:
            rel.id = _new_id()

        async with _acquire(self._pool, conn) as _conn:
            await _conn.execute(
                f"""
                INSERT INTO {SCHEMA}.relationships (
                    id, partner_id, source_entity_id, target_entity_id,
                    type, description, confirmed_by_user, created_at, updated_at, verb
                ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)
                ON CONFLICT (id) DO UPDATE SET
                    source_entity_id=EXCLUDED.source_entity_id,
                    target_entity_id=EXCLUDED.target_entity_id,
                    type=EXCLUDED.type, description=EXCLUDED.description,
                    confirmed_by_user=EXCLUDED.confirmed_by_user,
                    updated_at=EXCLUDED.updated_at,
                    verb=EXCLUDED.verb
                WHERE relationships.partner_id = EXCLUDED.partner_id
                """,
                rel.id, pid, rel.source_entity_id, rel.target_id,
                rel.type, rel.description, rel.confirmed_by_user, now, now, rel.verb,
            )
        return rel

    async def remove(self, source_entity_id: str, target_id: str, rel_type: str) -> int:
        """Delete a relationship edge by source/target/type. Returns rowcount."""
        pid = _get_partner_id()
        async with self._pool.acquire() as conn:
            result = await conn.execute(
                f"""DELETE FROM {SCHEMA}.relationships
                    WHERE source_entity_id = $1 AND target_entity_id = $2
                    AND type = $3 AND partner_id = $4""",
                source_entity_id, target_id, rel_type, pid,
            )
        return int(result.split()[-1])


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

    async def list_all(self, confirmed_only: bool | None = None) -> list[OntologyProtocol]:
        """Fetch all protocols for the current partner in a single query.

        Args:
            confirmed_only: If True, return only confirmed protocols.
                            If False, return only unconfirmed protocols.
                            If None, return all protocols.
        """
        pid = _get_partner_id()
        async with self._pool.acquire() as conn:
            if confirmed_only is None:
                rows = await conn.fetch(
                    f"SELECT * FROM {SCHEMA}.protocols WHERE partner_id = $1",
                    pid,
                )
            else:
                rows = await conn.fetch(
                    f"SELECT * FROM {SCHEMA}.protocols WHERE partner_id = $1 AND confirmed_by_user = $2",
                    pid, confirmed_only,
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

    async def add(self, blindspot: Blindspot, *, conn: asyncpg.Connection | None = None) -> Blindspot:
        pid = _get_partner_id()
        now = _now()
        if blindspot.created_at is None:  # type: ignore[comparison-overlap]
            blindspot.created_at = now
        if blindspot.id is None:
            blindspot.id = _new_id()

        async with _acquire_with_tx(self._pool, conn) as _conn:
            await _conn.execute(
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
            await _conn.execute(
                f"DELETE FROM {SCHEMA}.blindspot_entities WHERE blindspot_id = $1 AND partner_id = $2",
                blindspot.id, pid,
            )
            if blindspot.related_entity_ids:
                await _conn.executemany(
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
    plan_id = row["plan_id"] if "plan_id" in row else None
    plan_order = row["plan_order"] if "plan_order" in row else None
    depends_json = row["depends_on_task_ids_json"] if "depends_on_task_ids_json" in row else None
    source_metadata_json = row["source_metadata_json"] if "source_metadata_json" in row else None
    return Task(
        id=row["id"],
        title=row["title"],
        description=row["description"],
        status=row["status"],
        priority=row["priority"],
        priority_reason=row["priority_reason"],
        assignee=row["assignee"],
        assignee_role_id=row["assignee_role_id"],
        plan_id=plan_id,
        plan_order=plan_order,
        depends_on_task_ids=_json_loads_safe(depends_json) or [],
        created_by=row["created_by"],
        updated_by=row["updated_by"] if "updated_by" in row else None,
        linked_entities=linked_entities,
        linked_protocol=row["linked_protocol"],
        linked_blindspot=row["linked_blindspot"],
        source_type=row["source_type"],
        source_metadata=_json_loads_safe(source_metadata_json) or {},
        context_summary=row["context_summary"],
        due_date=_to_dt(row["due_date"]),
        blocked_by=blocked_by,
        blocked_reason=row["blocked_reason"],
        acceptance_criteria=_json_loads_safe(row["acceptance_criteria_json"]) or [],
        completed_by=row["completed_by"],
        creator_name=row["creator_name"] if "creator_name" in row else None,
        assignee_name=row["assignee_name"] if "assignee_name" in row else None,
        confirmed_by_creator=row["confirmed_by_creator"],
        rejection_reason=row["rejection_reason"],
        result=row["result"],
        project=row["project"],
        project_id=row["project_id"] if "project_id" in row else None,
        attachments=_json_loads_safe(row["attachments"] if "attachments" in row else None) or [],
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
                f"""SELECT t.*,
                           COALESCE(NULLIF(NULLIF(p1.display_name, ''), 'Unknown'), p1.email, p1.id, t.created_by) as creator_name,
                           COALESCE(NULLIF(NULLIF(p2.display_name, ''), 'Unknown'), p2.email, p2.id, t.assignee) as assignee_name
                    FROM {SCHEMA}.tasks t
                    LEFT JOIN {SCHEMA}.partners p1 ON t.created_by = p1.id
                    LEFT JOIN {SCHEMA}.partners p2 ON t.assignee = p2.id
                    WHERE t.id = $1 AND t.partner_id = $2""",
                task_id, pid,
            )
            if not row:
                return None
            linked_entities, blocked_by = await self._fetch_task_relations(conn, task_id, pid)
        return _row_to_task(row, linked_entities, blocked_by)

    async def upsert(self, task: Task, *, conn: asyncpg.Connection | None = None) -> Task:
        pid = _get_partner_id()
        now = _now()
        task.updated_at = now
        if task.id is None:
            task.id = _new_id()
            task.created_at = now

        async with _acquire_with_tx(self._pool, conn) as _conn:
            await _conn.execute(
                f"""
                INSERT INTO {SCHEMA}.tasks (
                    id, partner_id, title, description, status, priority,
                    priority_reason, assignee, assignee_role_id, created_by, updated_by,
                    plan_id, plan_order, depends_on_task_ids_json,
                    linked_protocol, linked_blindspot, source_type, source_metadata_json, context_summary,
                    due_date, blocked_reason, acceptance_criteria_json, completed_by,
                    confirmed_by_creator, rejection_reason, result, project, project_id,
                    attachments,
                    created_at, updated_at, completed_at
                ) VALUES (
                    $1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,
                    $12,$13,$14::jsonb,$15,$16,$17,$18::jsonb,$19,$20,$21,$22::jsonb,$23,$24,$25,$26,$27,$28,
                    $29::jsonb,
                    $30,$31,$32
                )
                ON CONFLICT (id) DO UPDATE SET
                    title=EXCLUDED.title, description=EXCLUDED.description,
                    status=EXCLUDED.status, priority=EXCLUDED.priority,
                    priority_reason=EXCLUDED.priority_reason,
                    assignee=EXCLUDED.assignee,
                    assignee_role_id=EXCLUDED.assignee_role_id,
                    updated_by=EXCLUDED.updated_by,
                    plan_id=EXCLUDED.plan_id,
                    plan_order=EXCLUDED.plan_order,
                    depends_on_task_ids_json=EXCLUDED.depends_on_task_ids_json,
                    linked_protocol=EXCLUDED.linked_protocol,
                    linked_blindspot=EXCLUDED.linked_blindspot,
                    source_type=EXCLUDED.source_type,
                    source_metadata_json=EXCLUDED.source_metadata_json,
                    context_summary=EXCLUDED.context_summary,
                    due_date=EXCLUDED.due_date,
                    blocked_reason=EXCLUDED.blocked_reason,
                    acceptance_criteria_json=EXCLUDED.acceptance_criteria_json,
                    completed_by=EXCLUDED.completed_by,
                    confirmed_by_creator=EXCLUDED.confirmed_by_creator,
                    rejection_reason=EXCLUDED.rejection_reason,
                    result=EXCLUDED.result, project=EXCLUDED.project,
                    project_id=EXCLUDED.project_id,
                    attachments=EXCLUDED.attachments,
                    updated_at=EXCLUDED.updated_at,
                    completed_at=EXCLUDED.completed_at
                WHERE tasks.partner_id = EXCLUDED.partner_id
                """,
                task.id, pid, task.title, task.description, task.status,
                task.priority, task.priority_reason, task.assignee,
                task.assignee_role_id, task.created_by, task.updated_by,
                task.plan_id, task.plan_order, _dumps(task.depends_on_task_ids),
                task.linked_protocol, task.linked_blindspot,
                task.source_type, _dumps(task.source_metadata), task.context_summary, task.due_date,
                task.blocked_reason, _dumps(task.acceptance_criteria),
                task.completed_by, task.confirmed_by_creator,
                task.rejection_reason, task.result, task.project, task.project_id,
                _dumps(task.attachments),
                task.created_at, task.updated_at, task.completed_at,
            )
            # Sync task_entities join table
            await _conn.execute(
                f"DELETE FROM {SCHEMA}.task_entities WHERE task_id = $1 AND partner_id = $2",
                task.id, pid,
            )
            if task.linked_entities:
                await _conn.executemany(
                    f"INSERT INTO {SCHEMA}.task_entities (task_id, entity_id, partner_id)"
                    f" VALUES ($1, $2, $3) ON CONFLICT DO NOTHING",
                    [(task.id, eid, pid) for eid in task.linked_entities],
                )
            # Sync task_blockers join table
            await _conn.execute(
                f"DELETE FROM {SCHEMA}.task_blockers WHERE task_id = $1 AND partner_id = $2",
                task.id, pid,
            )
            if task.blocked_by:
                await _conn.executemany(
                    f"INSERT INTO {SCHEMA}.task_blockers (task_id, blocker_task_id, partner_id)"
                    f" VALUES ($1, $2, $3) ON CONFLICT DO NOTHING",
                    [(task.id, bid, pid) for bid in task.blocked_by],
                )
        return task

    async def find_task_by_attachment_id(self, attachment_id: str) -> Task | None:
        """Find a task containing an attachment with the given ID."""
        pid = _get_partner_id()
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                f"""SELECT t.*,
                           COALESCE(NULLIF(NULLIF(p1.display_name, ''), 'Unknown'), p1.email, p1.id, t.created_by) as creator_name,
                           COALESCE(NULLIF(NULLIF(p2.display_name, ''), 'Unknown'), p2.email, p2.id, t.assignee) as assignee_name
                    FROM {SCHEMA}.tasks t
                    LEFT JOIN {SCHEMA}.partners p1 ON t.created_by = p1.id
                    LEFT JOIN {SCHEMA}.partners p2 ON t.assignee = p2.id
                    WHERE t.partner_id = $1
                      AND t.attachments @> $2::jsonb""",
                pid, json.dumps([{"id": attachment_id}]),
            )
            if not row:
                return None
            linked_entities, blocked_by = await self._fetch_task_relations(conn, row["id"], pid)
        return _row_to_task(row, linked_entities, blocked_by)

    async def list_all(
        self,
        *,
        assignee: str | None = None,
        created_by: str | None = None,
        status: list[str] | None = None,
        priority: str | None = None,
        linked_entity: str | None = None,
        include_archived: bool = False,
        limit: int = 200,
        offset: int = 0,
        project: str | None = None,
        plan_id: str | None = None,
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
        if plan_id is not None:
            conditions.append(f"t.plan_id = ${idx}")
            params.append(plan_id)
            idx += 1
        # Track whether caller explicitly filtered by status
        explicit_status_filter = status is not None

        if status is not None:
            normalized = []
            for s in status:
                mapped = {"backlog": "todo", "blocked": "in_progress", "archived": "done"}.get(s, s)
                if mapped not in normalized:
                    normalized.append(mapped)
            status = normalized
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

        select_cols = (
            f"DISTINCT t.*, "
            f"COALESCE(NULLIF(NULLIF(p1.display_name, ''), 'Unknown'), p1.email, p1.id, t.created_by) as creator_name, "
            f"COALESCE(NULLIF(NULLIF(p2.display_name, ''), 'Unknown'), p2.email, p2.id, t.assignee) as assignee_name"
        )
        from_clause = (
            f"{SCHEMA}.tasks t "
            f"{join_clause} "
            f"LEFT JOIN {SCHEMA}.partners p1 ON t.created_by = p1.id "
            f"LEFT JOIN {SCHEMA}.partners p2 ON t.assignee = p2.id"
        )

        # Build LIMIT/OFFSET clause
        limit_idx = idx
        params.append(limit)
        idx += 1
        offset_idx = idx
        params.append(offset)
        idx += 1

        if not explicit_status_filter:
            # Split query: active tickets unlimited (up to limit), done/cancelled capped at 5 each
            active_where = f"{where_clause} AND t.status NOT IN ('done', 'cancelled')"
            done_where = f"{where_clause} AND t.status = 'done'"
            cancelled_where = f"{where_clause} AND t.status = 'cancelled'"
            sql = (
                f"SELECT * FROM ("
                f"  (SELECT {select_cols} FROM {from_clause} WHERE {active_where} ORDER BY t.created_at DESC LIMIT ${limit_idx} OFFSET ${offset_idx})"
                f"  UNION ALL"
                f"  (SELECT {select_cols} FROM {from_clause} WHERE {done_where} ORDER BY t.updated_at DESC LIMIT 5)"
                f"  UNION ALL"
                f"  (SELECT {select_cols} FROM {from_clause} WHERE {cancelled_where} ORDER BY t.updated_at DESC LIMIT 5)"
                f") combined ORDER BY created_at DESC"
            )
        else:
            sql = (
                f"SELECT {select_cols} "
                f"FROM {from_clause} "
                f"WHERE {where_clause} ORDER BY t.created_at DESC LIMIT ${limit_idx} OFFSET ${offset_idx}"
            )

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
# PostgresTaskCommentRepository
# ===================================================================

class PostgresTaskCommentRepository:
    """CRUD operations for task comments."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def create(self, task_id: str, partner_id: str, content: str) -> dict:
        """Create a comment and return its dict representation, including author_name."""
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                f"""INSERT INTO {SCHEMA}.task_comments (task_id, partner_id, content)
                    VALUES ($1, $2, $3)
                    RETURNING id, task_id, partner_id, content, created_at""",
                task_id, partner_id, content,
            )
            author_row = await conn.fetchrow(
                f"SELECT display_name FROM {SCHEMA}.partners WHERE id = $1",
                partner_id,
            )
        return {
            "id": str(row["id"]),
            "task_id": str(row["task_id"]),
            "partner_id": row["partner_id"],
            "content": row["content"],
            "created_at": row["created_at"].isoformat(),
            "author_name": author_row["display_name"] if author_row else partner_id,
        }

    async def list_by_task(self, task_id: str) -> list[dict]:
        """Return all comments for a task, joined with partner display name, oldest-first."""
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                f"""SELECT c.id, c.task_id, c.partner_id, c.content, c.created_at,
                           COALESCE(NULLIF(p.display_name, ''), p.email, c.partner_id) AS author_name
                    FROM {SCHEMA}.task_comments c
                    LEFT JOIN {SCHEMA}.partners p ON c.partner_id = p.id
                    WHERE c.task_id = $1
                    ORDER BY c.created_at ASC""",
                task_id,
            )
        return [
            {
                "id": str(r["id"]),
                "task_id": str(r["task_id"]),
                "partner_id": r["partner_id"],
                "content": r["content"],
                "author_name": r["author_name"] or r["partner_id"],
                "created_at": r["created_at"].isoformat(),
            }
            for r in rows
        ]

    async def get_by_id(self, comment_id: str) -> dict | None:
        """Return a single comment dict (includes partner_id for auth checks), or None."""
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                f"""SELECT id, task_id, partner_id, content, created_at
                    FROM {SCHEMA}.task_comments
                    WHERE id = $1""",
                comment_id,
            )
        if not row:
            return None
        return {
            "id": str(row["id"]),
            "task_id": str(row["task_id"]),
            "partner_id": row["partner_id"],
            "content": row["content"],
            "created_at": row["created_at"].isoformat(),
        }

    async def delete(self, comment_id: str) -> bool:
        """Delete a comment. Returns True if a row was deleted."""
        async with self._pool.acquire() as conn:
            result = await conn.execute(
                f"DELETE FROM {SCHEMA}.task_comments WHERE id = $1",
                comment_id,
            )
        # asyncpg execute returns "DELETE N" where N is row count
        return result == "DELETE 1"


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
                               shared_partner_id, default_project, roles, department
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
                        "defaultProject": row["default_project"] or "",
                        "roles": list(row["roles"] or []) if "roles" in row else [],
                        "department": (row["department"] or "all") if "department" in row else "all",
                    }
            self._cache = new_cache
            self._cache_ts = time.time()
            logger.info("Partner cache refreshed from SQL: %d active keys", len(new_cache))
        except Exception:
            logger.exception("Failed to refresh partner cache from SQL")
            if not self._cache:
                self._cache_ts = time.time()


# ===================================================================
# EntityEntry Repository
# ===================================================================


def _row_to_entry(row: asyncpg.Record) -> EntityEntry:
    return EntityEntry(
        id=row["id"],
        partner_id=row["partner_id"],
        entity_id=row["entity_id"],
        type=row["type"],
        content=row["content"],
        context=row["context"],
        author=row["author"],
        department=row["department"] if "department" in row else None,
        source_task_id=row["source_task_id"],
        status=row["status"],
        superseded_by=row["superseded_by"],
        archive_reason=row["archive_reason"],
        created_at=_to_dt(row["created_at"]) or _now(),
    )


class SqlEntityEntryRepository:
    """PostgreSQL-backed repository for entity knowledge entries.

    All queries are scoped by partner_id to enforce multi-tenant isolation.
    """

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def create(self, entry: EntityEntry) -> EntityEntry:
        """Insert a new entry and return it."""
        pid = _get_partner_id()
        async with self._pool.acquire() as conn:
            await conn.execute(
                f"""
                INSERT INTO {SCHEMA}.entity_entries (
                    id, partner_id, entity_id, type, content,
                    context, author, department, source_task_id, status,
                    superseded_by, created_at
                ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)
                """,
                entry.id, pid, entry.entity_id, entry.type, entry.content,
                entry.context, entry.author, entry.department, entry.source_task_id, entry.status,
                entry.superseded_by, entry.created_at,
            )
        return entry

    async def get_by_id(self, entry_id: str) -> EntityEntry | None:
        """Fetch a single entry by ID, scoped to the current partner."""
        pid = _get_partner_id()
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                f"SELECT * FROM {SCHEMA}.entity_entries WHERE id = $1 AND partner_id = $2",
                entry_id, pid,
            )
        return _row_to_entry(row) if row else None

    async def list_by_entity(
        self, entity_id: str, status: str | None = "active", department: str | None = None
    ) -> list[EntityEntry]:
        """List entries for an entity. Defaults to active only; pass None for all."""
        pid = _get_partner_id()
        conditions = ["partner_id = $1", "entity_id = $2"]
        params: list[object] = [pid, entity_id]
        idx = 3
        if status is not None:
            conditions.append(f"status = ${idx}")
            params.append(status)
            idx += 1
        if department and department != "all":
            conditions.append(f"(department = ${idx} OR department = 'all' OR department IS NULL)")
            params.append(department)
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                f"""SELECT * FROM {SCHEMA}.entity_entries
                    WHERE {' AND '.join(conditions)}
                    ORDER BY created_at DESC""",
                *params,
            )
        return [_row_to_entry(r) for r in rows]

    async def update_status(
        self, entry_id: str, status: str, superseded_by: str | None = None,
        archive_reason: str | None = None,
    ) -> EntityEntry | None:
        """Update entry status, superseded_by, and archive_reason. Returns updated entry or None."""
        pid = _get_partner_id()
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                f"""UPDATE {SCHEMA}.entity_entries
                    SET status = $1, superseded_by = $2, archive_reason = $3
                    WHERE id = $4 AND partner_id = $5
                    RETURNING *""",
                status, superseded_by, archive_reason, entry_id, pid,
            )
        return _row_to_entry(row) if row else None

    async def list_saturated_entities(self, threshold: int = 20) -> list[dict]:
        """Return entities that have >= threshold active entries.

        Returns list of dicts: {entity_id, entity_name, active_count}.
        """
        pid = _get_partner_id()
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                f"""SELECT ee.entity_id, e.name AS entity_name, COUNT(*) AS active_count
                    FROM {SCHEMA}.entity_entries ee
                    JOIN {SCHEMA}.entities e
                      ON e.id = ee.entity_id AND e.partner_id = ee.partner_id
                    WHERE ee.partner_id = $1 AND ee.status = 'active'
                    GROUP BY ee.entity_id, e.name
                    HAVING COUNT(*) >= $2
                    ORDER BY active_count DESC""",
                pid, threshold,
            )
        return [
            {
                "entity_id": r["entity_id"],
                "entity_name": r["entity_name"],
                "active_count": int(r["active_count"]),
            }
            for r in rows
        ]

    async def count_active_by_entity(self, entity_id: str, department: str | None = None) -> int:
        """Count active entries for an entity. Used for saturation check."""
        pid = _get_partner_id()
        conditions = ["partner_id = $1", "entity_id = $2", "status = 'active'"]
        params: list[object] = [pid, entity_id]
        if department and department != "all":
            conditions.append("(department = $3 OR department = 'all' OR department IS NULL)")
            params.append(department)
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                f"""SELECT COUNT(*) as cnt FROM {SCHEMA}.entity_entries
                    WHERE {' AND '.join(conditions)}""",
                *params,
            )
        return int(row["cnt"]) if row else 0

    async def search_content(self, query: str, limit: int = 20, department: str | None = None) -> list[dict]:
        """Search entries by content keyword, returning entries with entity context.

        Returns a list of dicts: {entry: EntityEntry, entity_id: str}.
        The caller can enrich with entity names via entity_repo.
        """
        pid = _get_partner_id()
        query_lower = f"%{query.lower()}%"
        conditions = ["ee.partner_id = $1", "LOWER(ee.content) LIKE $2"]
        params: list[object] = [pid, query_lower]
        idx = 3
        if department and department != "all":
            conditions.append(f"(ee.department = ${idx} OR ee.department = 'all' OR ee.department IS NULL)")
            params.append(department)
            idx += 1
        params.append(limit)
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                f"""SELECT ee.*, e.name AS entity_name
                    FROM {SCHEMA}.entity_entries ee
                    JOIN {SCHEMA}.entities e
                      ON e.id = ee.entity_id AND e.partner_id = ee.partner_id
                    WHERE {' AND '.join(conditions)}
                    ORDER BY ee.created_at DESC
                    LIMIT ${idx}""",
                *params,
            )
        results = []
        for row in rows:
            entry = _row_to_entry(row)
            results.append({
                "entry": entry,
                "entity_name": row["entity_name"],
            })
        return results


# ===================================================================
# UsageLog Repository
# ===================================================================


class SqlUsageLogRepository:
    """PostgreSQL-backed UsageLogRepository.

    Writes LLM usage records to the usage_logs table.
    This class has no partner_id context dependency; the partner_id is
    passed explicitly so it can be called from background tasks.
    """

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def write_usage_log(
        self,
        partner_id: str,
        feature: str,
        tokens_in: int,
        tokens_out: int,
        model: str,
    ) -> None:
        """Insert a usage log row. Silently ignores empty partner_id."""
        if not partner_id:
            return
        async with self._pool.acquire() as conn:
            await conn.execute(
                f"""INSERT INTO {SCHEMA}.usage_logs (partner_id, feature, model, tokens_in, tokens_out)
                    VALUES ($1, $2, $3, $4, $5)""",
                partner_id,
                feature,
                model,
                tokens_in,
                tokens_out,
            )


# ===================================================================
# Tool Event Repository
# ===================================================================


class SqlToolEventRepository:
    """PostgreSQL-backed ToolEventRepository.

    Tracks agent tool usage (search/get) per entity for feedback loop analysis.
    The partner_id is passed explicitly so it can be called from background tasks.
    """

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def log_tool_event(
        self,
        partner_id: str,
        tool_name: str,
        entity_id: str | None,
        query: str | None,
        result_count: int | None,
    ) -> None:
        """Insert a tool event row. Silently ignores empty partner_id."""
        if not partner_id:
            return
        async with self._pool.acquire() as conn:
            await conn.execute(
                f"""INSERT INTO {SCHEMA}.tool_events
                    (partner_id, tool_name, entity_id, query, result_count)
                    VALUES ($1, $2, $3, $4, $5)""",
                partner_id,
                tool_name,
                entity_id,
                query,
                result_count,
            )

    async def get_entity_usage_stats(
        self,
        partner_id: str,
        days: int = 30,
    ) -> list[dict]:
        """Return per-entity search/get counts for the past N days.

        Uses a parameterized interval to avoid SQL injection.
        """
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                f"""SELECT entity_id,
                           SUM(CASE WHEN tool_name = 'search' THEN 1 ELSE 0 END) AS search_count,
                           SUM(CASE WHEN tool_name = 'get' THEN 1 ELSE 0 END) AS get_count
                    FROM {SCHEMA}.tool_events
                    WHERE partner_id = $1
                      AND entity_id IS NOT NULL
                      AND created_at > now() - ($2 || ' days')::interval
                    GROUP BY entity_id""",
                partner_id,
                str(days),
            )
        return [
            {
                "entity_id": row["entity_id"],
                "search_count": int(row["search_count"]),
                "get_count": int(row["get_count"]),
            }
            for row in rows
        ]


# ===================================================================
# Partner Repository
# ===================================================================


def _row_to_partner_dict(row: asyncpg.Record) -> dict:
    """Convert a partners table row to a standardized partner dict."""
    return {
        "id": row["id"],
        "email": row["email"],
        "displayName": row["display_name"],
        "apiKey": row["api_key"],
        "authorizedEntityIds": list(row["authorized_entity_ids"] or []),
        "status": row["status"],
        "isAdmin": row["is_admin"],
        "sharedPartnerId": row["shared_partner_id"],
        "defaultProject": row["default_project"],
        "roles": list(row["roles"] or []) if "roles" in row else [],
        "department": (row["department"] or "all") if "department" in row else "all",
        "invitedBy": row["invited_by"],
        "createdAt": row["created_at"] if "created_at" in row else None,
        "updatedAt": row["updated_at"] if "updated_at" in row else None,
        "inviteExpiresAt": row["invite_expires_at"] if "invite_expires_at" in row else None,
    }


_PARTNER_SELECT_COLS = """id, email, display_name, api_key, authorized_entity_ids,
                       status, is_admin, shared_partner_id, default_project, invited_by,
                       roles, department, created_at, updated_at, invite_expires_at"""


class SqlPartnerRepository:
    """PostgreSQL-backed PartnerRepository."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def get_by_email(self, email: str) -> dict | None:
        """Fetch partner by email. Returns standardized dict or None."""
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                f"SELECT {_PARTNER_SELECT_COLS} FROM {SCHEMA}.partners WHERE email = $1 LIMIT 1",
                email,
            )
        return _row_to_partner_dict(row) if row else None

    async def get_by_id(self, partner_id: str) -> dict | None:
        """Fetch partner by ID. Returns standardized dict or None."""
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                f"SELECT {_PARTNER_SELECT_COLS} FROM {SCHEMA}.partners WHERE id = $1 LIMIT 1",
                partner_id,
            )
        return _row_to_partner_dict(row) if row else None

    async def list_all_in_tenant(self, tenant_id: str) -> list[dict]:
        """Fetch all partners whose tenant key matches tenant_id.

        Tenant key = shared_partner_id if set, else id.
        """
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                f"SELECT {_PARTNER_SELECT_COLS} FROM {SCHEMA}.partners"
            )
        results = []
        for row in rows:
            d = _row_to_partner_dict(row)
            row_tenant = d.get("sharedPartnerId") or d["id"]
            if row_tenant == tenant_id:
                results.append(d)
        return results

    async def create(self, data: dict) -> None:
        """Insert a new partner row."""
        async with self._pool.acquire() as conn:
            await conn.execute(
                f"""INSERT INTO {SCHEMA}.partners (
                        id, email, display_name, api_key, authorized_entity_ids,
                        status, is_admin, shared_partner_id, invited_by,
                        roles, department, created_at, updated_at, invite_expires_at
                    ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14)""",
                data["id"],
                data["email"],
                data["displayName"],
                data.get("apiKey", ""),
                data.get("authorizedEntityIds", []),
                data.get("status", "invited"),
                data.get("isAdmin", False),
                data.get("sharedPartnerId"),
                data.get("invitedBy", ""),
                data.get("roles", []),
                data.get("department", "all"),
                data["createdAt"],
                data["updatedAt"],
                data.get("inviteExpiresAt"),
            )

    async def list_departments(self, tenant_id: str) -> list[str]:
        """Return stored departments plus any in-use partner departments."""
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                f"""SELECT name FROM {SCHEMA}.partner_departments
                    WHERE tenant_id = $1
                    ORDER BY CASE WHEN name = 'all' THEN 0 ELSE 1 END, lower(name)""",
                tenant_id,
            )
            partner_rows = await conn.fetch(
                f"""SELECT department, shared_partner_id, id
                    FROM {SCHEMA}.partners"""
            )
        departments = {str(row["name"]) for row in rows if row["name"]}
        for row in partner_rows:
            row_tenant = row["shared_partner_id"] or row["id"]
            if row_tenant == tenant_id and row["department"]:
                departments.add(str(row["department"]))
        departments.add("all")
        return sorted(departments, key=lambda value: (value != "all", value.lower()))

    async def create_department(self, tenant_id: str, name: str) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                f"""INSERT INTO {SCHEMA}.partner_departments (tenant_id, name)
                    VALUES ($1, $2)
                    ON CONFLICT (tenant_id, name) DO NOTHING""",
                tenant_id,
                name,
            )

    async def rename_department(self, tenant_id: str, old_name: str, new_name: str) -> None:
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    f"""DELETE FROM {SCHEMA}.partner_departments
                        WHERE tenant_id = $1 AND name = $2""",
                    tenant_id,
                    old_name,
                )
                await conn.execute(
                    f"""INSERT INTO {SCHEMA}.partner_departments (tenant_id, name)
                        VALUES ($1, $2)
                        ON CONFLICT (tenant_id, name) DO NOTHING""",
                    tenant_id,
                    new_name,
                )
                await conn.execute(
                    f"""UPDATE {SCHEMA}.partners
                        SET department = $1
                        WHERE COALESCE(shared_partner_id, id) = $2
                          AND department = $3""",
                    new_name,
                    tenant_id,
                    old_name,
                )

    async def delete_department(self, tenant_id: str, name: str, fallback_department: str = "all") -> None:
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    f"""DELETE FROM {SCHEMA}.partner_departments
                        WHERE tenant_id = $1 AND name = $2""",
                    tenant_id,
                    name,
                )
                await conn.execute(
                    f"""UPDATE {SCHEMA}.partners
                        SET department = $1
                        WHERE COALESCE(shared_partner_id, id) = $2
                          AND department = $3""",
                    fallback_department,
                    tenant_id,
                    name,
                )

    async def update_fields(self, partner_id: str, fields: dict) -> None:
        """Update arbitrary partner fields by building a SET clause.

        Only keys present in ``fields`` are updated. ``updated_at`` is always
        refreshed to ``fields['updatedAt']`` if provided, else kept unchanged.
        """
        if not fields:
            return
        # Build parameterized SET clause
        col_map = {
            "status": "status",
            "isAdmin": "is_admin",
            "apiKey": "api_key",  # pragma: allowlist secret
            "displayName": "display_name",
            "roles": "roles",
            "department": "department",
            "authorizedEntityIds": "authorized_entity_ids",
            "updatedAt": "updated_at",
            "inviteExpiresAt": "invite_expires_at",
        }
        sets = []
        params: list = []
        idx = 1
        for key, col in col_map.items():
            if key in fields:
                sets.append(f"{col} = ${idx}")
                params.append(fields[key])
                idx += 1
        if not sets:
            return
        params.append(partner_id)
        sql = f"UPDATE {SCHEMA}.partners SET {', '.join(sets)} WHERE id = ${idx}"
        async with self._pool.acquire() as conn:
            await conn.execute(sql, *params)

    async def delete(self, partner_id: str) -> None:
        """Delete partner by ID."""
        async with self._pool.acquire() as conn:
            await conn.execute(
                f"DELETE FROM {SCHEMA}.partners WHERE id = $1",
                partner_id,
            )

    async def get_entity_tenant(self, entity_id: str) -> dict | None:
        """Return {partner_id, shared_partner_id} for the entity's owner partner."""
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                f"""SELECT e.partner_id, p.shared_partner_id
                    FROM {SCHEMA}.entities e
                    JOIN {SCHEMA}.partners p ON p.id = e.partner_id
                    WHERE e.id = $1
                    LIMIT 1""",
                entity_id,
            )
        if not row:
            return None
        return {
            "partner_id": row["partner_id"],
            "shared_partner_id": row["shared_partner_id"],
        }

    async def update_entity_visibility(
        self,
        entity_id: str,
        visibility: str,
        visible_to_roles: list[str],
        visible_to_members: list[str],
        visible_to_departments: list[str],
    ) -> None:
        """Update entity visibility fields."""
        async with self._pool.acquire() as conn:
            await conn.execute(
                f"""UPDATE {SCHEMA}.entities
                    SET visibility = $1,
                        visible_to_roles = $2,
                        visible_to_members = $3,
                        visible_to_departments = $4,
                        updated_at = $5
                    WHERE id = $6""",
                visibility,
                visible_to_roles,
                visible_to_members,
                visible_to_departments,
                _now(),
                entity_id,
            )


# ---------------------------------------------------------------------------
# Audit Event Repository
# ---------------------------------------------------------------------------


class SqlAuditEventRepository:
    """PostgreSQL-backed repository for immutable governance audit events."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def create(self, event: dict) -> None:
        """Write an audit event row. Failure must not propagate to caller."""
        async with self._pool.acquire() as conn:
            await conn.execute(
                f"""
                INSERT INTO {SCHEMA}.audit_events
                    (partner_id, actor_id, actor_type, operation, resource_type, resource_id, changes_json)
                VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb)
                """,
                event["partner_id"],
                event["actor_id"],
                event.get("actor_type", "partner"),
                event["operation"],
                event["resource_type"],
                event.get("resource_id"),
                json.dumps(event.get("changes_json") or {}, default=str),
            )

    async def list_events(
        self,
        partner_id: str,
        since: datetime | None = None,
        until: datetime | None = None,
        operation: str | None = None,
        actor_id: str | None = None,
        limit: int = 100,
    ) -> list[dict]:
        """Return audit events for a partner, optionally filtered."""
        conditions = ["partner_id = $1"]
        params: list = [partner_id]
        i = 2
        if since:
            conditions.append(f"timestamp >= ${i}")
            params.append(since)
            i += 1
        if until:
            conditions.append(f"timestamp <= ${i}")
            params.append(until)
            i += 1
        if operation:
            conditions.append(f"operation = ${i}")
            params.append(operation)
            i += 1
        if actor_id:
            conditions.append(f"actor_id = ${i}")
            params.append(actor_id)
            i += 1
        where = " AND ".join(conditions)
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                f"SELECT * FROM {SCHEMA}.audit_events WHERE {where} ORDER BY timestamp DESC LIMIT {limit}",
                *params,
            )
        return [dict(r) for r in rows]
