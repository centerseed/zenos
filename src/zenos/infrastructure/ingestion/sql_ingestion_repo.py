"""PostgreSQL-backed ingestion repository."""

from __future__ import annotations

from datetime import datetime

import asyncpg  # type: ignore[import-untyped]

from zenos.infrastructure.sql_common import (
    SCHEMA,
    _acquire_with_tx,
    _dumps,
    _get_partner_id,
    _json_loads_safe,
    _new_id,
)


def _row_to_signal(row: asyncpg.Record) -> dict:
    return {
        "id": row["id"],
        "workspace_id": row["workspace_id"],
        "product_id": row["product_id"],
        "external_user_id": row["external_user_id"],
        "external_signal_id": row["external_signal_id"],
        "event_type": row["event_type"],
        "raw_ref": row["raw_ref"],
        "summary": row["summary"],
        "intent": row["intent"],
        "confidence": float(row["confidence"]),
        "occurred_at": row["occurred_at"],
        "created_at": row["created_at"],
    }


def _row_to_candidate(row: asyncpg.Record) -> dict:
    return {
        "id": row["id"],
        "batch_id": row["batch_id"],
        "candidate_type": row["candidate_type"],
        "status": row["status"],
        "payload": _json_loads_safe(row["payload_json"]) or {},
        "reason": row["reason"] or "",
        "confidence": float(row["confidence"] or 0.0),
        "created_at": row["created_at"],
    }


def _row_to_review_item(row: asyncpg.Record) -> dict:
    return {
        "id": row["id"],
        "workspace_id": row["workspace_id"],
        "product_id": row["product_id"],
        "batch_id": row["batch_id"],
        "candidate_id": row["candidate_id"],
        "review_type": row["review_type"],
        "status": row["status"],
        "note": row["note"] or "",
        "candidate": _json_loads_safe(row["candidate_payload_json"]),
        "created_at": row["created_at"],
        "reviewed_by": row["reviewed_by"],
        "reviewed_at": row["reviewed_at"],
    }


class SqlIngestionRepository:
    """SQL repository used by IngestionService in production runtime."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def ingest_signal(self, payload: dict) -> tuple[str, bool]:
        pid = _get_partner_id()
        signal_id = _new_id()
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                f"""
                INSERT INTO {SCHEMA}.external_signals (
                    id, partner_id, workspace_id, product_id, external_user_id,
                    external_signal_id, event_type, raw_ref, summary, intent,
                    confidence, occurred_at
                ) VALUES (
                    $1,$2,$3,$4,$5,
                    $6,$7,$8,$9,$10,
                    $11,$12
                )
                ON CONFLICT (partner_id, workspace_id, external_signal_id) DO NOTHING
                RETURNING id
                """,
                signal_id,
                pid,
                payload["workspace_id"],
                payload["product_id"],
                payload["external_user_id"],
                payload["external_signal_id"],
                payload["event_type"],
                payload["raw_ref"],
                payload["summary"],
                payload["intent"],
                payload["confidence"],
                payload["occurred_at"],
            )
            if row:
                return row["id"], False
            existing = await conn.fetchrow(
                f"""
                SELECT id FROM {SCHEMA}.external_signals
                WHERE partner_id = $1 AND workspace_id = $2 AND external_signal_id = $3
                """,
                pid,
                payload["workspace_id"],
                payload["external_signal_id"],
            )
        if not existing:
            raise RuntimeError("Idempotent signal replay lookup failed unexpectedly")
        return existing["id"], True

    async def list_signals_in_window(
        self,
        *,
        workspace_id: str,
        product_id: str,
        window_from: datetime,
        window_to: datetime,
        max_items: int,
    ) -> list[dict]:
        pid = _get_partner_id()
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                f"""
                SELECT * FROM {SCHEMA}.external_signals
                WHERE partner_id = $1
                  AND workspace_id = $2
                  AND product_id = $3
                  AND occurred_at >= $4
                  AND occurred_at <= $5
                ORDER BY occurred_at ASC
                LIMIT $6
                """,
                pid,
                workspace_id,
                product_id,
                window_from,
                window_to,
                max_items,
            )
        return [_row_to_signal(r) for r in rows]

    async def create_batch(
        self,
        *,
        workspace_id: str,
        product_id: str,
        window_from: datetime,
        window_to: datetime,
    ) -> str:
        pid = _get_partner_id()
        batch_id = _new_id()
        async with self._pool.acquire() as conn:
            await conn.execute(
                f"""
                INSERT INTO {SCHEMA}.ingestion_batches (
                    id, partner_id, workspace_id, product_id,
                    window_from, window_to, status, created_by
                ) VALUES ($1,$2,$3,$4,$5,$6,'draft',$7)
                """,
                batch_id,
                pid,
                workspace_id,
                product_id,
                window_from,
                window_to,
                pid,
            )
        return batch_id

    async def save_candidates(
        self,
        *,
        batch_id: str,
        candidate_type: str,
        candidates: list[dict],
    ) -> list[dict]:
        pid = _get_partner_id()
        out: list[dict] = []
        async with self._pool.acquire() as conn:
            for candidate in candidates:
                candidate_id = _new_id()
                row = await conn.fetchrow(
                    f"""
                    INSERT INTO {SCHEMA}.ingestion_candidates (
                        id, partner_id, batch_id, candidate_type,
                        payload_json, reason, confidence, status
                    ) VALUES ($1,$2,$3,$4,$5::jsonb,$6,$7,'draft')
                    RETURNING *
                    """,
                    candidate_id,
                    pid,
                    batch_id,
                    candidate_type,
                    _dumps(candidate),
                    str(candidate.get("reason") or ""),
                    float(candidate.get("confidence") or 0.0),
                )
                out.append(_row_to_candidate(row))
        return out

    async def enqueue_review_items(
        self,
        *,
        workspace_id: str,
        product_id: str,
        batch_id: str,
        items: list[dict],
        conn: asyncpg.Connection | None = None,
    ) -> list[dict]:
        pid = _get_partner_id()
        out: list[dict] = []
        async with _acquire_with_tx(self._pool, conn) as _conn:
            for item in items:
                review_id = _new_id()
                row = await _conn.fetchrow(
                    f"""
                    INSERT INTO {SCHEMA}.ingestion_review_queue (
                        id, partner_id, workspace_id, product_id, batch_id,
                        candidate_id, review_type, status, note, candidate_payload_json
                    ) VALUES (
                        $1,$2,$3,$4,$5,
                        $6,$7,'pending',$8,$9::jsonb
                    )
                    RETURNING *
                    """,
                    review_id,
                    pid,
                    workspace_id,
                    product_id,
                    batch_id,
                    item.get("candidate_id"),
                    item.get("review_type", "l2_update"),
                    item.get("note", ""),
                    _dumps(item.get("candidate")),
                )
                out.append(_row_to_review_item(row))
        return out

    async def list_review_queue(
        self,
        *,
        workspace_id: str,
        product_id: str,
        status: str | None,
        limit: int,
        offset: int,
    ) -> tuple[list[dict], int]:
        pid = _get_partner_id()
        where = [
            "partner_id = $1",
            "workspace_id = $2",
            "product_id = $3",
        ]
        params: list[object] = [pid, workspace_id, product_id]
        idx = 4
        if status:
            where.append(f"status = ${idx}")
            params.append(status)
            idx += 1

        where_sql = " AND ".join(where)
        async with self._pool.acquire() as conn:
            total = await conn.fetchval(
                f"SELECT COUNT(*) FROM {SCHEMA}.ingestion_review_queue WHERE {where_sql}",
                *params,
            )
            rows = await conn.fetch(
                f"""
                SELECT * FROM {SCHEMA}.ingestion_review_queue
                WHERE {where_sql}
                ORDER BY created_at DESC
                LIMIT ${idx} OFFSET ${idx + 1}
                """,
                *params,
                limit,
                offset,
            )
        return [_row_to_review_item(r) for r in rows], int(total or 0)
