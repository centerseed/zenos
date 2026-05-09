"""
build_snapshot_repair_queue.py

Builds a repair queue for current formal-entry documents whose delivery snapshot
coverage is missing or stale.

Input accepts either:
- full MCP response: {"status":"ok","data":{"invalid_documents":{...}}}
- direct payload: {"invalid_documents":{...}}
- raw invalid_documents payload: {"items":[...], "bundle_issues":[...]}

Output:
- /tmp/zenos-dogfood/{DF-ID}/snapshot-repair-queue.json
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_OUT_ROOT = Path("/tmp/zenos-dogfood")
_SUPPORTED_ISSUES = {
    "current_formal_entry_missing_delivery_snapshot": "high",
    "current_formal_entry_stale_delivery_snapshot": "medium",
}


def _read_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _unwrap_invalid_documents(payload: dict[str, Any]) -> dict[str, Any]:
    if "invalid_documents" in payload and isinstance(payload["invalid_documents"], dict):
        return payload["invalid_documents"]
    data = payload.get("data")
    if isinstance(data, dict) and isinstance(data.get("invalid_documents"), dict):
        return data["invalid_documents"]
    if isinstance(payload.get("bundle_issues"), list):
        return payload
    return {}


def build_snapshot_repair_queue(
    *,
    df_id: str,
    invalid_documents_json: str | Path,
    out_root: str | Path = DEFAULT_OUT_ROOT,
) -> dict[str, Any]:
    payload = _unwrap_invalid_documents(_read_json(invalid_documents_json))
    bundle_issues = payload.get("bundle_issues") or []
    if not isinstance(bundle_issues, list):
        bundle_issues = []

    queue: list[dict[str, Any]] = []
    for issue in bundle_issues:
        if not isinstance(issue, dict):
            continue
        issue_type = str(issue.get("issue_type") or "").strip()
        if issue_type not in _SUPPORTED_ISSUES:
            continue
        doc_id = str(issue.get("entity_id") or "").strip()
        if not doc_id:
            continue
        queue.append({
            "doc_id": doc_id,
            "title": str(issue.get("title") or "").strip() or "未命名文件",
            "issue_type": issue_type,
            "severity": str(issue.get("severity") or "").strip() or "red",
            "priority": _SUPPORTED_ISSUES[issue_type],
            "linked_entity_ids": list(issue.get("linked_entity_ids") or []),
            "source_uri": str(issue.get("source_uri") or "").strip() or None,
            "suspected_root_cause": str(issue.get("suspected_root_cause") or "").strip() or None,
            "alternative_uris": list(issue.get("alternative_uris") or []) or None,
            "suggested_action": str(issue.get("suggested_action") or "").strip(),
            "repair_action": {
                "type": "publish_delivery_snapshot",
                "method": "POST",
                "path": f"/api/docs/{doc_id}/publish",
                "expected_delivery_status": "ready",
            },
        })

    queue.sort(key=lambda item: (0 if item["priority"] == "high" else 1, item["doc_id"]))

    out_dir = Path(out_root) / df_id
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "snapshot-repair-queue.json"
    result = {
        "df_id": df_id,
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "source_invalid_documents_json": str(invalid_documents_json),
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
    parser = argparse.ArgumentParser(description="Build delivery-snapshot repair queue from invalid_documents JSON")
    parser.add_argument("--df-id", required=True)
    parser.add_argument("--invalid-documents-json", required=True)
    parser.add_argument("--out-root", default=str(DEFAULT_OUT_ROOT))
    args = parser.parse_args()

    result = build_snapshot_repair_queue(
        df_id=args.df_id,
        invalid_documents_json=args.invalid_documents_json,
        out_root=args.out_root,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
