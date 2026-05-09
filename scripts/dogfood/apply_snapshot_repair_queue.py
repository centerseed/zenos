"""
apply_snapshot_repair_queue.py

Executes a snapshot repair queue produced by build_snapshot_repair_queue.py.

Each queue item is resolved to its owning partner/workspace via SQL, then
published using the same internal document-delivery primitive as the Dashboard.

Output:
- /tmp/zenos-dogfood/{DF-ID}/snapshot-repair-results.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from zenos.infrastructure.github_adapter import GitHubAdapter
from zenos.infrastructure.sql_common import SCHEMA, get_pool
from zenos.interface.dashboard_api import _publish_document_snapshot_internal


DEFAULT_OUT_ROOT = Path("/tmp/zenos-dogfood")


def _read_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


async def _load_partner_ids(doc_ids: list[str]) -> dict[str, str]:
    if not doc_ids:
        return {}
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f"""
            SELECT id, partner_id
            FROM {SCHEMA}.entities
            WHERE id = ANY($1::text[])
            """,
            doc_ids,
        )
    return {
        str(row["id"] or "").strip(): str(row["partner_id"] or "").strip()
        for row in rows
        if str(row["id"] or "").strip() and str(row["partner_id"] or "").strip()
    }


async def apply_snapshot_repair_queue(
    *,
    df_id: str,
    queue_json: str | Path,
    out_root: str | Path = DEFAULT_OUT_ROOT,
    partner_id: str | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    queue_payload = _read_json(queue_json)
    queue = queue_payload.get("queue") or []
    if not isinstance(queue, list):
        queue = []

    doc_ids = [
        str(item.get("doc_id") or "").strip()
        for item in queue
        if isinstance(item, dict) and str(item.get("doc_id") or "").strip()
    ]
    partner_ids = (
        {doc_id: partner_id for doc_id in doc_ids}
        if partner_id
        else await _load_partner_ids(doc_ids)
    )

    results: list[dict[str, Any]] = []
    success_count = 0
    failed_count = 0
    skipped_count = 0

    for item in queue:
        if not isinstance(item, dict):
            continue
        doc_id = str(item.get("doc_id") or "").strip()
        if not doc_id:
            continue
        partner_id = partner_ids.get(doc_id)
        if not partner_id:
            skipped_count += 1
            results.append({
                "doc_id": doc_id,
                "title": item.get("title"),
                "status": "skipped",
                "error": "MISSING_PARTNER_ID",
            })
            continue

        if dry_run:
            success_count += 1
            results.append({
                "doc_id": doc_id,
                "title": item.get("title"),
                "status": "dry_run",
                "partner_id": partner_id,
                "repair_action": item.get("repair_action"),
            })
            continue

        try:
            payload = await _publish_document_snapshot_internal(
                effective_id=partner_id,
                doc_id=doc_id,
            )
            success_count += 1
            results.append({
                "doc_id": doc_id,
                "title": item.get("title"),
                "status": "ok",
                "partner_id": partner_id,
                "payload": payload,
            })
        except FileNotFoundError:
            source_uri = str(item.get("source_uri") or "").strip()
            alternatives: list[str] = []
            if source_uri:
                try:
                    alternatives = await GitHubAdapter().search_alternatives_for_uri(source_uri)
                except Exception:
                    alternatives = []
            failed_count += 1
            results.append({
                "doc_id": doc_id,
                "title": item.get("title"),
                "status": "failed",
                "partner_id": partner_id,
                "error": "SOURCE_NOT_FOUND",
                **({"source_uri": source_uri} if source_uri else {}),
                **({"alternative_uris": alternatives[:10]} if alternatives else {}),
            })
        except PermissionError:
            failed_count += 1
            results.append({
                "doc_id": doc_id,
                "title": item.get("title"),
                "status": "failed",
                "partner_id": partner_id,
                "error": "SOURCE_FORBIDDEN",
            })
        except ValueError as exc:
            failed_count += 1
            results.append({
                "doc_id": doc_id,
                "title": item.get("title"),
                "status": "failed",
                "partner_id": partner_id,
                "error": "INVALID_INPUT",
                "message": str(exc),
            })
        except RuntimeError as exc:
            failed_count += 1
            results.append({
                "doc_id": doc_id,
                "title": item.get("title"),
                "status": "failed",
                "partner_id": partner_id,
                "error": "SOURCE_ERROR",
                "message": str(exc),
            })
        except Exception as exc:  # pragma: no cover - defensive envelope
            failed_count += 1
            results.append({
                "doc_id": doc_id,
                "title": item.get("title"),
                "status": "failed",
                "partner_id": partner_id,
                "error": "UNEXPECTED_ERROR",
                "message": str(exc),
            })

    out_dir = Path(out_root) / df_id
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "snapshot-repair-results.json"
    payload = {
        "df_id": df_id,
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "source_queue_json": str(queue_json),
        "dry_run": dry_run,
        "success_count": success_count,
        "failed_count": failed_count,
        "skipped_count": skipped_count,
        "results": results,
    }
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {
        "df_id": df_id,
        "out_path": str(out_path),
        "success_count": success_count,
        "failed_count": failed_count,
        "skipped_count": skipped_count,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply snapshot repair queue via internal publish primitive")
    parser.add_argument("--df-id", required=True)
    parser.add_argument("--queue-json", required=True)
    parser.add_argument("--out-root", default=str(DEFAULT_OUT_ROOT))
    parser.add_argument("--partner-id", help="Override partner/workspace id for every doc in the queue")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    result = asyncio.run(
        apply_snapshot_repair_queue(
            df_id=args.df_id,
            queue_json=args.queue_json,
            out_root=args.out_root,
            partner_id=args.partner_id,
            dry_run=args.dry_run,
        )
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
