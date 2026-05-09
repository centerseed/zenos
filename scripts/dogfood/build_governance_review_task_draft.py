"""
build_governance_review_task_draft.py

Build governance review task drafts from dogfood source-repair queues so the
next fixer iteration can open graph-first, high-quality tasks without manually
assembling context from raw JSON artifacts.

Input:
- /tmp/zenos-dogfood/{DF-ID}/source-repair-queue.json

Output:
- /tmp/zenos-dogfood/{DF-ID}/governance-review-task-drafts.json
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


def build_governance_review_task_drafts(
    *,
    df_id: str,
    source_repair_queue_json: str | Path,
    product_id: str,
    out_root: str | Path = DEFAULT_OUT_ROOT,
) -> dict[str, Any]:
    payload = _read_json(source_repair_queue_json)
    queue = payload.get("queue") or []
    if not isinstance(queue, list):
        queue = []

    drafts: list[dict[str, Any]] = []
    for item in queue:
        if not isinstance(item, dict):
            continue
        doc_id = str(item.get("doc_id") or "").strip()
        title = str(item.get("title") or "").strip() or "未命名文件"
        source_uri = str(item.get("source_uri") or "").strip()
        if not doc_id or not source_uri:
            continue
        alternative_uris = [str(uri).strip() for uri in (item.get("alternative_uris") or []) if str(uri).strip()]
        description_lines = [
            f"- current formal-entry doc_id: `{doc_id}`",
            f"- current source_uri: `{source_uri}`",
            "- 問題：controlled snapshot publish replay 命中 `SOURCE_NOT_FOUND`",
            "- 目標：確認 current formal-entry 的 GitHub source 是否已漂移、archive 或改名，並決定是否更新 sources",
        ]
        if alternative_uris:
            description_lines.append("- alternative URI candidates:")
            description_lines.extend([f"  - `{uri}`" for uri in alternative_uris])

        drafts.append({
            "title": f"檢查並修正 {title} 的 current source governance",
            "product_id": product_id,
            "description": "\n".join(description_lines),
            "acceptance_criteria": [
                "確認 current formal-entry 的 source URI 是否仍指向正式 current source",
                "若 source 已漂移 / archive / 改名，提出或套用正確 sources 更新方案",
                "重跑 controlled snapshot publish replay，不再回 SOURCE_NOT_FOUND",
            ],
            "linked_entities": [doc_id],
            "priority": "high",
            "dispatcher": "agent:architect",
            "source_metadata": {
                "created_via_agent": True,
                "agent_name": "dogfood",
                "artifact_type": "source_repair_queue",
                "artifact_df_id": df_id,
            },
        })

    out_dir = Path(out_root) / df_id
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "governance-review-task-drafts.json"
    result = {
        "df_id": df_id,
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "source_repair_queue_json": str(source_repair_queue_json),
        "draft_count": len(drafts),
        "drafts": drafts,
    }
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {
        "df_id": df_id,
        "out_path": str(out_path),
        "draft_count": len(drafts),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build governance review task drafts from source repair queue")
    parser.add_argument("--df-id", required=True)
    parser.add_argument("--source-repair-queue-json", required=True)
    parser.add_argument("--product-id", required=True)
    parser.add_argument("--out-root", default=str(DEFAULT_OUT_ROOT))
    args = parser.parse_args()

    result = build_governance_review_task_drafts(
        df_id=args.df_id,
        source_repair_queue_json=args.source_repair_queue_json,
        product_id=args.product_id,
        out_root=args.out_root,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
