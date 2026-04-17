"""Merge two document entities into one bundle-first winner.

Usage:
    PYTHONPATH=src .venv/bin/python3.13 scripts/merge_document_entities.py \
      --winner <doc_id> --loser <doc_id> [--live]

Default is dry-run.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from datetime import datetime, timezone

import asyncpg  # type: ignore[import-untyped]

from zenos.infrastructure.sql_common import SCHEMA, get_pool


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Merge two document entities.")
    parser.add_argument("--winner", required=True, help="Document entity ID to keep")
    parser.add_argument("--loser", required=True, help="Document entity ID to supersede")
    parser.add_argument("--live", action="store_true", help="Execute the merge")
    return parser.parse_args()


def _loads_json(value):
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        return json.loads(value)
    return value


def _normalize_sources(value) -> list[dict]:
    loaded = _loads_json(value)
    if not loaded:
        return []
    return [dict(item) for item in loaded if isinstance(item, dict)]


def _normalize_details(value) -> dict:
    loaded = _loads_json(value)
    if not loaded:
        return {}
    return dict(loaded)


def _build_highlights(sources: list[dict]) -> list[dict]:
    highlights: list[dict] = []
    primary_assigned = False
    for source in sources:
        label = str(source.get("label") or source.get("uri") or "document").strip()
        uri = str(source.get("uri") or "").strip().lower()
        is_ref = label.lower().startswith("ref-") or "/reference/" in uri
        priority = "supporting" if is_ref else "primary"
        if priority == "primary" and primary_assigned:
            priority = "supporting"
        if priority == "primary":
            primary_assigned = True
        highlights.append(
            {
                "source_id": str(source.get("source_id") or "").strip(),
                "headline": f"{label} 是 ZenOS 治理路徑總覽 bundle 的{'補充入口' if is_ref else '主要入口'}",
                "reason_to_read": (
                    "先讀這份規格理解治理路徑主流程"
                    if not is_ref
                    else "用這份 reference 補充對照與索引"
                ),
                "priority": priority,
            }
        )
    if highlights and not primary_assigned:
        highlights[0]["priority"] = "primary"
    return highlights


async def fetch_docs(conn: asyncpg.Connection, winner: str, loser: str) -> dict[str, asyncpg.Record]:
    rows = await conn.fetch(
        f"""
        SELECT id, partner_id, parent_id, name, status, sources_json, details_json
        FROM {SCHEMA}.entities
        WHERE id = ANY($1::text[])
        """,
        [winner, loser],
    )
    return {str(row["id"]): row for row in rows}


async def run(winner: str, loser: str, *, live: bool) -> int:
    pool = await get_pool()
    async with pool.acquire() as conn:
        docs = await fetch_docs(conn, winner, loser)
        if winner not in docs or loser not in docs:
            raise SystemExit("winner or loser not found")

        winner_row = docs[winner]
        loser_row = docs[loser]
        winner_sources = _normalize_sources(winner_row["sources_json"])
        loser_sources = _normalize_sources(loser_row["sources_json"])
        existing_uris = {str(item.get("uri") or "").strip() for item in winner_sources}
        merged_sources = winner_sources + [
            item for item in loser_sources
            if str(item.get("uri") or "").strip() not in existing_uris
        ]
        merged_highlights = _build_highlights(merged_sources)

        loser_details = _normalize_details(loser_row["details_json"])
        loser_details["superseded_by"] = winner
        loser_details["merged_into"] = winner

        summary = {
            "winner": winner,
            "loser": loser,
            "winner_name": winner_row["name"],
            "loser_name": loser_row["name"],
            "merged_source_count": len(merged_sources),
            "merged_highlight_count": len(merged_highlights),
        }
        print(json.dumps(summary, ensure_ascii=False, indent=2))

        if not live:
            print("[DRY RUN] no write executed.")
            return 0

        now = datetime.now(timezone.utc)
        async with conn.transaction():
            await conn.execute(
                f"""
                UPDATE {SCHEMA}.entities
                SET sources_json = $1::jsonb,
                    bundle_highlights_json = $2::jsonb,
                    highlights_updated_at = $3,
                    change_summary = $4,
                    summary_updated_at = $3,
                    updated_at = $3
                WHERE id = $5
                """,
                json.dumps(merged_sources, ensure_ascii=False),
                json.dumps(merged_highlights, ensure_ascii=False),
                now,
                "Merged REF-governance-paths-overview into the main governance paths bundle.",
                winner,
            )
            await conn.execute(
                f"""
                UPDATE {SCHEMA}.entities
                SET status = 'stale',
                    details_json = $1::jsonb,
                    change_summary = $2,
                    summary_updated_at = $3,
                    updated_at = $3
                WHERE id = $4
                """,
                json.dumps(loser_details, ensure_ascii=False),
                f"Superseded by {winner} during bundle merge.",
                now,
                loser,
            )

        print("[LIVE] merge executed.")
        return 0


if __name__ == "__main__":
    args = parse_args()
    raise SystemExit(asyncio.run(run(args.winner, args.loser, live=args.live)))
