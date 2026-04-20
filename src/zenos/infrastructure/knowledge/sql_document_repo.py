"""PostgreSQL-backed DocumentRepository."""

from __future__ import annotations

import asyncpg  # type: ignore[import-untyped]

from zenos.domain.knowledge import Document, DocumentTags, Source
from zenos.infrastructure.sql_common import (
    SCHEMA,
    _dumps,
    _get_partner_id,
    _json_loads_safe,
    _new_id,
    _now,
    _to_dt,
)


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

    async def find_by_id_prefix(
        self, prefix: str, partner_id: str, limit: int = 11
    ) -> list[Document]:
        """Return documents whose id starts with prefix, scoped to partner_id.

        limit=11 lets the caller distinguish "exactly 10" from "more than 10"
        (SPEC-mcp-id-ergonomics AC-MIDE-03/04).
        """
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                f"SELECT * FROM {SCHEMA}.documents"
                f" WHERE id LIKE $1 || '%' AND partner_id = $2"
                f" ORDER BY id LIMIT $3",
                prefix, partner_id, limit,
            )
            if not rows:
                return []
            doc_ids = [r["id"] for r in rows]
            link_rows = await conn.fetch(
                f"SELECT document_id, entity_id FROM {SCHEMA}.document_entities"
                f" WHERE partner_id = $1 AND document_id = ANY($2::text[])",
                partner_id, doc_ids,
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
