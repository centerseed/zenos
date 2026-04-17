"""Backfill bundle-first fields for existing L3 document entities.

Usage:
    python scripts/rebundle_document_entities.py --dry-run
    python scripts/rebundle_document_entities.py --live

What it does safely:
1. Promote legacy/null/single document entities to doc_role=index
2. Backfill minimal bundle_highlights when missing
3. Report merge candidates: sibling document entities under the same L2 that
   probably belong to the same semantic bundle

What it does NOT do automatically:
- Merge multiple document entities into one bundle
- Delete or archive existing document entities
- Rewrite relationships across entities
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from urllib.parse import urlparse

import asyncpg  # type: ignore[import-untyped]

from zenos.infrastructure.sql_common import SCHEMA, get_pool


PREFIX_PATTERNS = [
    r"^SPEC-",
    r"^ADR-\d+-",
    r"^ADR-",
    r"^DECISION-",
    r"^TD-",
    r"^DESIGN-",
    r"^PB-",
    r"^GUIDE-",
    r"^SC-",
    r"^REF-",
    r"^REFERENCE-",
    r"^TEST-",
    r"^PLAN-",
    r"^REPORT-",
    r"^CONTRACT-",
    r"^MEETING-",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Backfill bundle-first fields for existing document entities.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Print what would change without writing. Default behavior.",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Execute the UPDATEs. Overrides --dry-run.",
    )
    return parser.parse_args()


def normalize_topic_key(name: str) -> str:
    value = (name or "").strip()
    for pattern in PREFIX_PATTERNS:
        value = re.sub(pattern, "", value, flags=re.IGNORECASE)
    value = re.sub(r"\bbundle\b|\bindex\b|\bdocs?\b", "", value, flags=re.IGNORECASE)
    value = re.sub(r"[_\-\s]+", " ", value).strip().lower()
    return value


def choose_primary_source(sources: list[dict]) -> dict | None:
    if not sources:
        return None
    for source in sources:
        if source.get("is_primary"):
            return source
    for source in sources:
        if source.get("source_status", source.get("status")) == "valid":
            return source
    return sources[0]


def normalize_source_label(source: dict) -> str:
    label = str(source.get("label") or "").strip()
    if label and label.lower() != "github":
        return label

    uri = str(source.get("uri") or "").strip()
    if uri:
        parsed = urlparse(uri)
        path = parsed.path.rstrip("/")
        if path:
            tail = path.split("/")[-1]
            if tail:
                return tail
    return "document"


def normalize_sources(sources: list[dict]) -> tuple[list[dict], bool]:
    changed = False
    normalized: list[dict] = []
    for source in sources:
        if not isinstance(source, dict):
            normalized.append(source)
            continue
        item = dict(source)
        sid = str(item.get("source_id") or "").strip()
        if not sid:
            item["source_id"] = str(uuid.uuid4())
            changed = True
        normalized_label = normalize_source_label(item)
        if normalized_label != str(item.get("label") or "").strip():
            item["label"] = normalized_label
            changed = True
        normalized.append(item)
    return normalized, changed


def default_highlights(sources: list[dict]) -> list[dict]:
    primary = choose_primary_source(sources)
    if not primary:
        return []
    label = normalize_source_label(primary)
    source_id = str(primary.get("source_id") or "").strip()
    if not source_id:
        return []
    return [
        {
            "source_id": source_id,
            "headline": f"{label} 是這個主題目前最直接的文件入口",
            "reason_to_read": "先用這份文件建立全局理解，再決定要不要深入其他來源",
            "priority": "primary",
        }
    ]


async def fetch_documents(conn: asyncpg.Connection) -> list[asyncpg.Record]:
    return await conn.fetch(
        f"""
        SELECT id, partner_id, parent_id, name, doc_role,
               sources_json, bundle_highlights_json
        FROM {SCHEMA}.entities
        WHERE type = 'document'
        ORDER BY partner_id, parent_id, name
        """
    )


async def run(dry_run: bool) -> int:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await fetch_documents(conn)
        updates: list[tuple[str, str, str, str]] = []
        merge_candidates: dict[tuple[str, str, str], list[str]] = defaultdict(list)

        for row in rows:
            doc_id = str(row["id"])
            partner_id = str(row["partner_id"])
            parent_id = str(row["parent_id"] or "")
            name = str(row["name"] or "")
            doc_role = row["doc_role"]
            sources = json.loads(row["sources_json"]) if row["sources_json"] else []
            sources, sources_changed = normalize_sources(sources)
            bundle_highlights = (
                json.loads(row["bundle_highlights_json"])
                if row.get("bundle_highlights_json") else []
            )

            topic_key = normalize_topic_key(name)
            if parent_id and topic_key:
                merge_candidates[(partner_id, parent_id, topic_key)].append(doc_id)

            needs_role_backfill = doc_role in (None, "", "single")
            needs_highlight_backfill = not bundle_highlights and bool(sources)

            if not needs_role_backfill and not needs_highlight_backfill and not sources_changed:
                continue

            new_role = "index" if needs_role_backfill else str(doc_role)
            new_highlights = default_highlights(sources) if needs_highlight_backfill else bundle_highlights
            updates.append((
                doc_id,
                new_role,
                json.dumps(sources, ensure_ascii=False),
                json.dumps(new_highlights, ensure_ascii=False),
            ))

        print(f"documents scanned: {len(rows)}")
        print(f"documents needing safe backfill: {len(updates)}")

        if updates:
            for doc_id, new_role, sources_json, highlights_json in updates[:50]:
                print(f"  - {doc_id}: doc_role -> {new_role}, sources -> {sources_json}, bundle_highlights -> {highlights_json}")
            if len(updates) > 50:
                print(f"  ... and {len(updates) - 50} more")

        risky_groups = [
            (partner_id, parent_id, topic_key, doc_ids)
            for (partner_id, parent_id, topic_key), doc_ids in merge_candidates.items()
            if len(doc_ids) > 1
        ]
        print(f"merge candidates needing review: {len(risky_groups)}")
        for partner_id, parent_id, topic_key, doc_ids in risky_groups[:50]:
            print(f"  - partner={partner_id} parent={parent_id} topic='{topic_key}' docs={doc_ids}")
        if len(risky_groups) > 50:
            print(f"  ... and {len(risky_groups) - 50} more")

        if dry_run:
            print("\n[DRY RUN] no write executed.")
            return 0

        now = datetime.now(timezone.utc)
        async with conn.transaction():
            for doc_id, new_role, sources_json, highlights_json in updates:
                await conn.execute(
                    f"""
                    UPDATE {SCHEMA}.entities
                    SET doc_role = $1,
                        sources_json = $2::jsonb,
                        bundle_highlights_json = $3::jsonb,
                        highlights_updated_at = CASE
                            WHEN (bundle_highlights_json IS NULL OR bundle_highlights_json = '[]'::jsonb)
                            THEN $4
                            ELSE highlights_updated_at
                        END,
                        updated_at = $4
                    WHERE id = $5
                    """,
                    new_role,
                    sources_json,
                    highlights_json,
                    now,
                    doc_id,
                )

        print(f"\n[LIVE] updated {len(updates)} document entities.")
        return 0


if __name__ == "__main__":
    args = parse_args()
    effective_dry_run = not args.live
    raise SystemExit(asyncio.run(run(dry_run=effective_dry_run)))
