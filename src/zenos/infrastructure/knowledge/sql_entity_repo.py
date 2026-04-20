"""PostgreSQL-backed EntityRepository."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import asyncpg  # type: ignore[import-untyped]

from zenos.domain.knowledge import Entity, Tags
from zenos.infrastructure.sql_common import (
    SCHEMA,
    _acquire,
    _dumps,
    _get_partner_id,
    _json_loads_safe,
    _new_id,
    _now,
    _to_dt,
)


# Explicit column list for general entity reads.
# summary_embedding is intentionally excluded: it is a 768-float vector that
# callers retrieve only via get_embeddings_by_ids() or search_by_vector().
# Including it in every SELECT * would bloat every list_all / get_by_id response.
_ENTITY_COLS = (
    "id, partner_id, name, type, level, parent_id, status, summary, "
    "tags_json, details_json, confirmed_by_user, owner, sources_json, "
    "visibility, visible_to_roles, visible_to_members, visible_to_departments, "
    "last_reviewed_at, created_at, updated_at, "
    "doc_role, bundle_highlights_json, highlights_updated_at, "
    "change_summary, summary_updated_at, "
    "embedding_model, embedded_at, embedded_summary_hash"
)


def _row_to_entity(row: asyncpg.Record) -> Entity:
    def _optional(key: str, default: Any = None) -> Any:
        try:
            return row[key]
        except (KeyError, IndexError):
            return default

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
        visible_to_roles=list(_optional("visible_to_roles") or []),
        visible_to_members=list(_optional("visible_to_members") or []),
        visible_to_departments=list(_optional("visible_to_departments") or []),
        last_reviewed_at=_to_dt(row["last_reviewed_at"]),
        created_at=_to_dt(row["created_at"]) or _now(),
        updated_at=_to_dt(row["updated_at"]) or _now(),
        # ADR-022 Document Bundle fields
        doc_role=_optional("doc_role"),
        bundle_highlights=_json_loads_safe(_optional("bundle_highlights_json")) or [],
        highlights_updated_at=_to_dt(_optional("highlights_updated_at")),
        change_summary=_optional("change_summary"),
        summary_updated_at=_to_dt(_optional("summary_updated_at")),
        # ADR-041 Pillar A — embedding metadata
        embedded_summary_hash=_optional("embedded_summary_hash"),
        embedding_model=_optional("embedding_model"),
        embedded_at=_to_dt(_optional("embedded_at")),
    )


class SqlEntityRepository:
    """PostgreSQL-backed EntityRepository."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def get_by_id(self, entity_id: str) -> Entity | None:
        pid = _get_partner_id()
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                f"SELECT {_ENTITY_COLS} FROM {SCHEMA}.entities WHERE id = $1 AND partner_id = $2",
                entity_id, pid,
            )
        return _row_to_entity(row) if row else None

    async def get_by_name(self, name: str) -> Entity | None:
        pid = _get_partner_id()
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                f"SELECT {_ENTITY_COLS} FROM {SCHEMA}.entities WHERE LOWER(name) = LOWER($1) AND partner_id = $2 LIMIT 1",
                name, pid,
            )
        return _row_to_entity(row) if row else None

    async def list_all(self, type_filter: str | None = None) -> list[Entity]:
        pid = _get_partner_id()
        async with self._pool.acquire() as conn:
            if type_filter is not None:
                rows = await conn.fetch(
                    f"SELECT {_ENTITY_COLS} FROM {SCHEMA}.entities WHERE partner_id = $1 AND type = $2",
                    pid, type_filter,
                )
            else:
                rows = await conn.fetch(
                    f"SELECT {_ENTITY_COLS} FROM {SCHEMA}.entities WHERE partner_id = $1",
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
                    visible_to_departments, last_reviewed_at, created_at, updated_at,
                    doc_role, bundle_highlights_json, highlights_updated_at, change_summary, summary_updated_at
                ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9::jsonb,$10::jsonb,$11,$12,$13::jsonb,$14,$15,$16,$17,$18,$19,$20,$21,$22::jsonb,$23,$24,$25)
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
                    updated_at=EXCLUDED.updated_at,
                    doc_role=EXCLUDED.doc_role,
                    bundle_highlights_json=EXCLUDED.bundle_highlights_json,
                    highlights_updated_at=EXCLUDED.highlights_updated_at,
                    change_summary=EXCLUDED.change_summary,
                    summary_updated_at=EXCLUDED.summary_updated_at
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
                entity.doc_role, _dumps(entity.bundle_highlights), entity.highlights_updated_at,
                entity.change_summary, entity.summary_updated_at,
            )
        return entity

    async def list_unconfirmed(self) -> list[Entity]:
        pid = _get_partner_id()
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                f"SELECT {_ENTITY_COLS} FROM {SCHEMA}.entities WHERE confirmed_by_user = false AND partner_id = $1",
                pid,
            )
        return [_row_to_entity(r) for r in rows]

    async def list_by_ids(self, entity_ids: list[str]) -> list[Entity]:
        if not entity_ids:
            return []
        pid = _get_partner_id()
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                f"SELECT {_ENTITY_COLS} FROM {SCHEMA}.entities WHERE id = ANY($1) AND partner_id = $2",
                entity_ids, pid,
            )
        return [_row_to_entity(r) for r in rows]

    async def list_by_parent(self, parent_id: str) -> list[Entity]:
        pid = _get_partner_id()
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                f"SELECT {_ENTITY_COLS} FROM {SCHEMA}.entities WHERE parent_id = $1 AND partner_id = $2",
                parent_id, pid,
            )
        return [_row_to_entity(r) for r in rows]

    async def find_by_id_prefix(
        self, prefix: str, partner_id: str, limit: int = 11
    ) -> list[Entity]:
        """Return entities whose id starts with prefix, scoped to partner_id.

        limit=11 lets the caller distinguish "exactly 10" from "more than 10"
        (SPEC-mcp-id-ergonomics AC-MIDE-03/04).
        """
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                f"SELECT {_ENTITY_COLS} FROM {SCHEMA}.entities"
                f" WHERE id LIKE $1 || '%' AND partner_id = $2"
                f" ORDER BY id LIMIT $3",
                prefix, partner_id, limit,
            )
        return [_row_to_entity(r) for r in rows]

    async def update_source_status(
        self,
        entity_id: str,
        new_status: str,
        source_id: str | None = None,
    ) -> None:
        """Update source_status for a document entity's source.

        Args:
            entity_id: The entity to update.
            new_status: New source_status value (valid/stale/unresolvable).
            source_id: If provided, update only the source with this source_id.
                       If None, update sources[0] (backward compatible).
        """
        pid = _get_partner_id()
        async with self._pool.acquire() as conn:
            if source_id is None:
                # Legacy behavior: update first source
                await conn.execute(
                    f"""UPDATE {SCHEMA}.entities
                        SET sources_json = jsonb_set(
                            jsonb_set(
                                sources_json,
                                '{{0,status}}',
                                $1::jsonb,
                                true
                            ),
                            '{{0,source_status}}',
                            $1::jsonb,
                            true
                        ),
                        updated_at = now()
                        WHERE id = $2 AND partner_id = $3""",
                    json.dumps(new_status), entity_id, pid,
                )
            else:
                # Per-source update: find source by source_id and update its status
                row = await conn.fetchrow(
                    f"SELECT sources_json FROM {SCHEMA}.entities WHERE id = $1 AND partner_id = $2",
                    entity_id, pid,
                )
                if row is None:
                    return
                sources = json.loads(row["sources_json"]) if row["sources_json"] else []
                updated = False
                for src in sources:
                    if src.get("source_id") == source_id:
                        src["status"] = new_status
                        src["source_status"] = new_status
                        updated = True
                        break
                if updated:
                    await conn.execute(
                        f"""UPDATE {SCHEMA}.entities
                            SET sources_json = $1::jsonb, updated_at = now()
                            WHERE id = $2 AND partner_id = $3""",
                        json.dumps(sources), entity_id, pid,
                    )

    async def batch_update_source_uris(
        self,
        updates: list[dict],
        *,
        atomic: bool = False,
    ) -> dict:
        """Batch update source URIs for document entities.

        Supports two payload formats (can be mixed in one batch):
          - Legacy:  {"document_id": str, "new_uri": str}
                     Updates the primary source (is_primary=true), or first source.
          - New:     {"document_id": str, "source_id": str, "new_uri": str}
                     Updates the source matching source_id exactly.

        Args:
            updates: List of update dicts.
            atomic: If True, wrap in a transaction (all-or-nothing).

        Returns:
            {"updated": [...], "not_found": [...], "errors": [...]}
        """
        pid = _get_partner_id()
        updated = []
        not_found = []
        errors = []

        async def _do_updates(conn: asyncpg.Connection):
            for item in updates:
                doc_id = item["document_id"]
                new_uri = item["new_uri"]
                target_source_id = item.get("source_id")
                try:
                    row = await conn.fetchrow(
                        f"SELECT id, sources_json FROM {SCHEMA}.entities "
                        f"WHERE id = $1 AND partner_id = $2",
                        doc_id, pid,
                    )
                    if row is None:
                        if atomic:
                            raise ValueError(f"Document '{doc_id}' not found")
                        not_found.append(doc_id)
                        continue

                    current_sources = json.loads(row["sources_json"]) if row["sources_json"] else []
                    new_label = new_uri.rsplit("/", 1)[-1] if "/" in new_uri else new_uri

                    if target_source_id:
                        # New format: update by source_id
                        source_found = False
                        for src in current_sources:
                            if src.get("source_id") == target_source_id:
                                if src.get("uri") == new_uri:
                                    updated.append(doc_id)
                                    source_found = True
                                    break
                                src["uri"] = new_uri
                                src["label"] = new_label
                                canonical_status = src.get("source_status") or src.get("status") or "valid"
                                src["status"] = canonical_status
                                src["source_status"] = canonical_status
                                source_found = True
                                break
                        if not source_found:
                            if atomic:
                                raise ValueError(
                                    f"source_id '{target_source_id}' not found in document '{doc_id}'"
                                )
                            errors.append({
                                "document_id": doc_id,
                                "source_id": target_source_id,
                                "error": f"source_id '{target_source_id}' not found",
                            })
                            continue
                    else:
                        # Legacy format: update primary or first source
                        if not current_sources:
                            current_sources = [{
                                "uri": new_uri,
                                "label": new_label,
                                "type": "github",
                                "status": "valid",
                                "source_status": "valid",
                            }]
                        else:
                            # Find primary source, or fall back to first
                            target_idx = 0
                            for i, src in enumerate(current_sources):
                                if src.get("is_primary"):
                                    target_idx = i
                                    break
                            if current_sources[target_idx].get("uri") == new_uri:
                                updated.append(doc_id)
                                continue
                            current_sources[target_idx]["uri"] = new_uri
                            current_sources[target_idx]["label"] = new_label
                            canonical_status = (
                                current_sources[target_idx].get("source_status")
                                or current_sources[target_idx].get("status")
                                or "valid"
                            )
                            current_sources[target_idx]["status"] = canonical_status
                            current_sources[target_idx]["source_status"] = canonical_status

                    await conn.execute(
                        f"""UPDATE {SCHEMA}.entities
                            SET sources_json = $1::jsonb,
                                updated_at = now()
                            WHERE id = $2 AND partner_id = $3""",
                        json.dumps(current_sources), doc_id, pid,
                    )
                    updated.append(doc_id)
                except Exception as exc:
                    if atomic:
                        raise
                    errors.append({"document_id": doc_id, "error": str(exc)})

        if atomic:
            async with self._pool.acquire() as conn:
                async with conn.transaction():
                    await _do_updates(conn)
        else:
            async with self._pool.acquire() as conn:
                await _do_updates(conn)

        return {"updated": updated, "not_found": not_found, "errors": errors}

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

    # -------------------------------------------------------------------------
    # Embedding support (ADR-041 Pillar A, Phase 1)
    # summary_embedding is intentionally excluded from SELECT * reads;
    # it is a large vector payload that callers request explicitly via these methods.
    # -------------------------------------------------------------------------

    async def update_embedding(
        self,
        entity_id: str,
        embedding: list[float] | None,
        model: str,
        hash: str,
    ) -> None:
        """Atomically update the four embedding columns for an entity.

        Args:
            entity_id: The entity whose embedding columns are updated.
            embedding: 768-dim vector, or None when embedding failed / is empty.
            model: Model name (e.g. "gemini/gemini-embedding-001"), or "FAILED"/"EMPTY".
            hash: sha256(summary) hex string, or sentinel "FAILED" / "EMPTY".

        Note: partner_id scoping is applied; embedded_at is set to now() when
        embedding is not None and hash is not a sentinel value.
        """
        pid = _get_partner_id()
        embedded_at: datetime | None = (
            datetime.now(tz=timezone.utc)
            if (embedding is not None and hash not in ("FAILED", "EMPTY"))
            else None
        )
        # pgvector accepts a stringified literal "[v1,v2,...]" via asyncpg without
        # needing a custom codec; None maps to SQL NULL.
        embedding_lit: str | None = (
            "[" + ",".join(repr(float(v)) for v in embedding) + "]"
            if embedding is not None
            else None
        )
        async with self._pool.acquire() as conn:
            await conn.execute(
                f"""UPDATE {SCHEMA}.entities
                    SET summary_embedding = $1::zenos.vector,
                        embedding_model   = $2,
                        embedded_at       = $3,
                        embedded_summary_hash = $4,
                        updated_at        = now()
                    WHERE id = $5 AND partner_id = $6""",
                embedding_lit,
                model,
                embedded_at,
                hash,
                entity_id,
                pid,
            )

    async def get_embeddings_by_ids(
        self,
        ids: list[str],
    ) -> dict[str, list[float] | None]:
        """Batch-read summary_embedding for a list of entity IDs.

        Used by S04 neighbor ranking to avoid N+1 queries when scoring hop candidates.

        Returns:
            Mapping of entity_id -> 768-dim vector (or None if not yet embedded).
            IDs not found in the DB are omitted from the result dict.
        """
        if not ids:
            return {}
        pid = _get_partner_id()
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                f"""SELECT id, summary_embedding
                    FROM {SCHEMA}.entities
                    WHERE id = ANY($1) AND partner_id = $2""",
                ids,
                pid,
            )
        def _parse(v: Any) -> list[float] | None:
            if v is None:
                return None
            if isinstance(v, str):
                # pgvector returns "[1.0,2.0,...]" as string without codec registered
                return [float(x) for x in v.strip("[]").split(",") if x]
            return list(v)
        return {row["id"]: _parse(row["summary_embedding"]) for row in rows}

    async def search_by_vector(
        self,
        query_vec: list[float],
        limit: int,
        filters: dict | None = None,
    ) -> list[tuple[Entity, float]]:
        """Run pgvector cosine top-K search on summary_embedding.

        Used by S05 search semantic / hybrid mode.

        Args:
            query_vec: 768-dim query embedding.
            limit: Maximum number of results to return.
            filters: Optional WHERE conditions.  Supported keys:
                - "visibility": str  (equality match)
                - "workspace_id": str  (equality match on partner_id)

        Returns:
            List of (entity, cosine_similarity_score) pairs, ordered by score DESC.
            Only entities with a non-null summary_embedding are included.
        """
        pid = _get_partner_id()

        where_clauses = ["partner_id = $2", "summary_embedding IS NOT NULL"]
        query_lit = "[" + ",".join(repr(float(v)) for v in query_vec) + "]"
        params: list[Any] = [query_lit, pid]
        param_idx = 3

        if filters:
            if "visibility" in filters:
                where_clauses.append(f"visibility = ${param_idx}")
                params.append(filters["visibility"])
                param_idx += 1

        where_sql = " AND ".join(where_clauses)
        # pgvector cosine distance operator <=> returns distance (1 - similarity);
        # we convert to similarity score for caller convenience.
        # _ENTITY_COLS excludes summary_embedding from the entity payload while
        # still using it in the ORDER BY / score computation.
        sql = f"""
            SELECT {_ENTITY_COLS},
                   1 - (summary_embedding OPERATOR(zenos.<=>) $1::zenos.vector) AS cosine_score
            FROM {SCHEMA}.entities
            WHERE {where_sql}
            ORDER BY summary_embedding OPERATOR(zenos.<=>) $1::zenos.vector
            LIMIT ${param_idx}
        """
        params.append(limit)

        async with self._pool.acquire() as conn:
            rows = await conn.fetch(sql, *params)

        results: list[tuple[Entity, float]] = []
        for row in rows:
            entity = _row_to_entity(row)
            score: float = float(row["cosine_score"])
            results.append((entity, score))
        return results
