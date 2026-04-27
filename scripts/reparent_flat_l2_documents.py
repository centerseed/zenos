"""Reparent flat support document entities under L3 index bundles.

This repairs the failure mode where bulk uploaded markdown files were written
directly under an L2 module instead of being routed through L3 index documents.

Usage:
    python scripts/reparent_flat_l2_documents.py --l2-id ea46... --dry-run
    python scripts/reparent_flat_l2_documents.py --l2-id ea46... --live
"""

from __future__ import annotations

import argparse
import asyncio
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

import asyncpg  # type: ignore[import-untyped]

from zenos.infrastructure.sql_common import SCHEMA, get_pool


DEFAULT_RAW_MATERIAL_L2_ID = "ea46dc3d3faf4851b12d26e13fc7b4fb"


@dataclass(frozen=True)
class Route:
    key: str
    reason: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Move flat L2 support docs under matching L3 index bundles.",
    )
    parser.add_argument("--l2-id", default=DEFAULT_RAW_MATERIAL_L2_ID)
    parser.add_argument("--dry-run", action="store_true", default=True)
    parser.add_argument("--live", action="store_true")
    return parser.parse_args()


def _norm(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip().lower()


def _index_key(title: str) -> str | None:
    text = _norm(title)
    if "floraglo" in text or "葉黃素" in text:
        return "floraglo"
    if "pureway" in text or "維生素c" in text or "vitamin-c" in text or "vitamin c" in text:
        return "pureway"
    if "tfda" in text and ("原料清單" in text or "食品原料" in text):
        return "tfda_raw"
    if "tfda" in text and ("規格標準" in text or "健康食品規格" in text):
        return "tfda_standards"
    if "tfda" in text and ("功效評估" in text or "保健功效" in text):
        return "tfda_methods"
    if "research_index" in text or text == "research index":
        return "research"
    if "mkt_global_market-cases" in text or "market-cases" in text:
        return "market"
    return None


def _route_doc(title: str, summary: str) -> Route | None:
    text = _norm(f"{title} {summary}")
    if any(token in text for token in ("floraglo", "lutein", "zeaxanthin", "葉黃素")):
        return Route("floraglo", "matched FloraGLO/lutein/zeaxanthin terms")
    if any(token in text for token in ("pureway", "lipopure", "vitamin-c", "vitamin c", "維生素c")):
        return Route("pureway", "matched PureWay-C/vitamin C terms")
    if any(token in text for token in ("規格標準", "健康食品規格")):
        return Route("tfda_standards", "matched TFDA health food standards terms")
    if any(token in text for token in ("功效評估", "保健功效")):
        return Route("tfda_methods", "matched TFDA efficacy evaluation terms")
    if any(token in text for token in ("tfda", "食品原料", "原料清單", "草、木本", "草木本")):
        return Route("tfda_raw", "matched TFDA raw material list terms")
    if text.startswith("mkt_") or "market" in text or "市場" in text:
        return Route("market", "matched market/case document terms")
    if text.startswith("rsc_") or "research" in text or "study" in text:
        return Route("research", "matched research document terms")
    return None


async def _load_l2(conn: asyncpg.Connection, l2_id: str) -> asyncpg.Record:
    row = await conn.fetchrow(
        f"SELECT id, partner_id, name FROM {SCHEMA}.entities WHERE id = $1 AND type = 'module'",
        l2_id,
    )
    if row is None:
        raise SystemExit(f"L2 module not found: {l2_id}")
    return row


async def _load_direct_docs(conn: asyncpg.Connection, l2_id: str, partner_id: str) -> list[asyncpg.Record]:
    return await conn.fetch(
        f"""
        SELECT id, name, summary, doc_role, status, parent_id
        FROM {SCHEMA}.entities
        WHERE partner_id = $1
          AND type = 'document'
          AND parent_id = $2
          AND status != 'archived'
        ORDER BY name
        """,
        partner_id,
        l2_id,
    )


async def run(l2_id: str, dry_run: bool) -> int:
    pool = await get_pool()
    async with pool.acquire() as conn:
        l2 = await _load_l2(conn, l2_id)
        partner_id = str(l2["partner_id"])
        rows = await _load_direct_docs(conn, l2_id, partner_id)

        index_by_key: dict[str, asyncpg.Record] = {}
        for row in rows:
            if str(row["doc_role"] or "").lower() != "index":
                continue
            key = _index_key(str(row["name"] or ""))
            if key:
                index_by_key.setdefault(key, row)

        planned: list[tuple[asyncpg.Record, asyncpg.Record, Route]] = []
        skipped: list[tuple[str, str]] = []
        index_ids = {str(row["id"]) for row in index_by_key.values()}
        for row in rows:
            doc_id = str(row["id"])
            if doc_id in index_ids:
                continue
            route = _route_doc(str(row["name"] or ""), str(row["summary"] or ""))
            if route is None:
                skipped.append((doc_id, "no_route"))
                continue
            target = index_by_key.get(route.key)
            if target is None:
                skipped.append((doc_id, f"missing_index:{route.key}"))
                continue
            planned.append((row, target, route))

        print(f"L2: {l2['name']} ({l2_id})")
        print(f"direct documents: {len(rows)}")
        print(f"index bundles: {', '.join(sorted(index_by_key)) or '-'}")
        print(f"planned reparent: {len(planned)}")
        for doc, target, route in planned[:80]:
            print(f"  - {doc['name']} -> {target['name']} [{route.reason}]")
        if len(planned) > 80:
            print(f"  ... and {len(planned) - 80} more")
        print(f"skipped: {len(skipped)}")
        for doc_id, reason in skipped[:40]:
            print(f"  - {doc_id}: {reason}")

        if dry_run:
            print("\n[DRY RUN] no write executed.")
            return 0

        now = datetime.now(timezone.utc)
        async with conn.transaction():
            for doc, target, route in planned:
                doc_id = str(doc["id"])
                target_id = str(target["id"])
                await conn.execute(
                    f"""
                    UPDATE {SCHEMA}.entities
                    SET parent_id = $1, updated_at = $2
                    WHERE partner_id = $3 AND id = $4
                    """,
                    target_id,
                    now,
                    partner_id,
                    doc_id,
                )
                await conn.execute(
                    f"""
                    DELETE FROM {SCHEMA}.relationships
                    WHERE partner_id = $1
                      AND source_entity_id = $2
                      AND target_entity_id = $3
                      AND type = 'part_of'
                    """,
                    partner_id,
                    doc_id,
                    l2_id,
                )
                await conn.execute(
                    f"""
                    INSERT INTO {SCHEMA}.relationships (
                        id, partner_id, source_entity_id, target_entity_id,
                        type, description, confirmed_by_user, created_at, updated_at
                    ) VALUES ($1,$2,$3,$4,'part_of',$5,true,$6,$6)
                    ON CONFLICT (partner_id, source_entity_id, target_entity_id, type)
                    DO UPDATE SET description = EXCLUDED.description, updated_at = EXCLUDED.updated_at
                    """,
                    str(uuid.uuid4()).replace("-", ""),
                    partner_id,
                    doc_id,
                    target_id,
                    f"document bundle routing: {route.reason}",
                    now,
                )

        print(f"\n[LIVE] reparented {len(planned)} documents.")
        return 0


if __name__ == "__main__":
    args = parse_args()
    raise SystemExit(asyncio.run(run(args.l2_id, dry_run=not args.live)))
