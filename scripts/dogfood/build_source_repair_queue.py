"""
build_source_repair_queue.py

Builds a repair queue for current formal-entry docs whose snapshot publish
attempt failed due to broken / drifted source URIs.

Input:
- snapshot-repair-results.json from apply_snapshot_repair_queue.py

Output:
- /tmp/zenos-dogfood/{DF-ID}/source-repair-queue.json
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_OUT_ROOT = Path("/tmp/zenos-dogfood")


def _read_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def build_source_repair_queue(
    *,
    df_id: str,
    repair_results_json: str | Path,
    out_root: str | Path = DEFAULT_OUT_ROOT,
) -> dict[str, Any]:
    payload = _read_json(repair_results_json)
    results = payload.get("results") or []
    if not isinstance(results, list):
        results = []

    queue: list[dict[str, Any]] = []
    for item in results:
        if not isinstance(item, dict):
            continue
        if str(item.get("error") or "").strip() != "SOURCE_NOT_FOUND":
            continue
        doc_id = str(item.get("doc_id") or "").strip()
        if not doc_id:
            continue
        queue.append({
            "doc_id": doc_id,
            "title": str(item.get("title") or "").strip() or "未命名文件",
            "partner_id": str(item.get("partner_id") or "").strip() or None,
            "source_uri": str(item.get("source_uri") or "").strip() or None,
            "alternative_uris": list(item.get("alternative_uris") or []) or None,
            "repair_action": {
                "type": "review_or_update_document_source",
                "collection": "documents",
                "doc_id": doc_id,
                "target_field": "sources",
            },
            "suggested_action": (
                "目前 current formal-entry 的 GitHub source 在 publish replay 時回 SOURCE_NOT_FOUND。"
                "先確認 source URI 是否已漂移 / 被 archive / 改名，再更新 current doc source。"
            ),
        })

    out_dir = Path(out_root) / df_id
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "source-repair-queue.json"
    result = {
        "df_id": df_id,
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "source_repair_results_json": str(repair_results_json),
        "queue_count": len(queue),
        "queue": queue,
    }
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {
        "df_id": df_id,
        "out_path": str(out_path),
        "queue_count": len(queue),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build source repair queue from snapshot repair results")
    parser.add_argument("--df-id", required=True)
    parser.add_argument("--repair-results-json", required=True)
    parser.add_argument("--out-root", default=str(DEFAULT_OUT_ROOT))
    args = parser.parse_args()

    result = build_source_repair_queue(
        df_id=args.df_id,
        repair_results_json=args.repair_results_json,
        out_root=args.out_root,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
