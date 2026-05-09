"""
build_monitor_report.py

Builds a per-iteration dogfood monitor report by merging MCP traffic summary
with per-entity-type governance health payloads.

Inputs are exported MCP JSON payloads from tools like:
- analyze(check_type="quality")
- analyze(check_type="staleness")
- analyze(check_type="invalid_documents")
- search(collection="tasks", status="todo")
- search(collection="blindspots", severity="green")

Output:
- /tmp/zenos-dogfood/{DF-ID}/monitor.json
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


DEFAULT_OUT_ROOT = Path("/tmp/zenos-dogfood")


def _read_json(path: str | Path | None) -> dict[str, Any]:
    if not path:
        return {}
    file_path = Path(path)
    if not file_path.exists():
        return {}
    return json.loads(file_path.read_text(encoding="utf-8"))


def _unwrap_data(payload: dict[str, Any], key: str) -> dict[str, Any] | list[Any]:
    if not payload:
        return {}
    if key in payload:
        return payload[key]
    data = payload.get("data")
    if isinstance(data, dict) and key in data:
        return data[key]
    return {}


def _parse_iso(value: object) -> datetime | None:
    if not value:
        return None
    text = str(value).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _build_quality_summary(payload: dict[str, Any]) -> dict[str, Any]:
    quality = _unwrap_data(payload, "quality")
    if not isinstance(quality, dict):
        return {}
    failed = quality.get("failed") or []
    failed_checks = []
    for item in failed:
        if isinstance(item, dict):
            failed_checks.append(str(item.get("name") or "").strip())
    return {
        "score": quality.get("score"),
        "scope": quality.get("scope"),
        "active_l2_missing_impacts": int(quality.get("active_l2_missing_impacts") or 0),
        "entry_saturation_count": int(quality.get("entry_saturation_count") or 0),
        "failed_checks": [name for name in failed_checks if name],
    }


def _build_staleness_summary(payload: dict[str, Any]) -> dict[str, Any]:
    staleness = _unwrap_data(payload, "staleness")
    if not isinstance(staleness, dict):
        return {}
    return {
        "stale_count": int(staleness.get("count") or 0),
        "document_consistency_count": int(staleness.get("document_consistency_count") or 0),
    }


def _build_tasks_summary(payload: dict[str, Any]) -> dict[str, Any]:
    tasks = _unwrap_data(payload, "tasks")
    if not isinstance(tasks, list):
        return {}
    now = datetime.now(timezone.utc)
    stale_cutoff = now - timedelta(days=7)
    stalled = 0
    for task in tasks:
        if not isinstance(task, dict):
            continue
        status = str(task.get("status") or "").strip().lower()
        if status not in {"todo", "in_progress", "review"}:
            continue
        updated_at = _parse_iso(task.get("updated_at")) or _parse_iso(task.get("created_at"))
        if updated_at and updated_at < stale_cutoff:
            stalled += 1
    return {
        "todo_count": len(tasks),
        "stalled_open_count": stalled,
    }


def _build_invalid_documents_summary(payload: dict[str, Any]) -> dict[str, Any]:
    invalid_documents = _unwrap_data(payload, "invalid_documents")
    if not isinstance(invalid_documents, dict):
        return {}
    bundle_issues = invalid_documents.get("bundle_issues") or []
    if not isinstance(bundle_issues, list):
        bundle_issues = []

    missing_snapshot = 0
    stale_snapshot = 0
    for issue in bundle_issues:
        if not isinstance(issue, dict):
            continue
        issue_type = str(issue.get("issue_type") or "").strip()
        if issue_type == "current_formal_entry_missing_delivery_snapshot":
            missing_snapshot += 1
        elif issue_type == "current_formal_entry_stale_delivery_snapshot":
            stale_snapshot += 1

    return {
        "invalid_document_count": int(invalid_documents.get("count") or 0),
        "bundle_issue_count": int(invalid_documents.get("bundle_issue_count") or 0),
        "current_formal_entry_missing_delivery_snapshot": missing_snapshot,
        "current_formal_entry_stale_delivery_snapshot": stale_snapshot,
    }


def _build_source_repair_summary(payload: dict[str, Any]) -> dict[str, Any]:
    if not payload:
        return {}
    queue = payload.get("queue") or []
    if not isinstance(queue, list):
        queue = []

    source_not_found_count = 0
    alternative_uri_candidate_count = 0
    for item in queue:
        if not isinstance(item, dict):
            continue
        source_not_found_count += 1
        if item.get("alternative_uris"):
            alternative_uri_candidate_count += 1

    return {
        "source_not_found_count": source_not_found_count,
        "alternative_uri_candidate_count": alternative_uri_candidate_count,
    }


def _build_delivery_auth_summary(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict) or not payload:
        return {}
    status = str(payload.get("status") or "").strip().lower()
    error = str(payload.get("error") or "").strip()
    http_status = payload.get("http_status")
    return {
        "github_secret_status": status or None,
        "github_secret_error": error or None,
        "github_secret_http_status": http_status,
        "github_secret_invalid": bool(status == "rejected" and error == "INVALID_GITHUB_TOKEN"),
    }


def _build_blindspots_summary(payload: dict[str, Any]) -> dict[str, Any]:
    blindspots = _unwrap_data(payload, "blindspots")
    if not isinstance(blindspots, list):
        return {}
    green_open = 0
    for blindspot in blindspots:
        if not isinstance(blindspot, dict):
            continue
        severity = str(blindspot.get("severity") or "").strip().lower()
        status = str(blindspot.get("status") or "").strip().lower()
        if severity == "green" and status == "open":
            green_open += 1
    return {
        "green_open_count": green_open,
        "total_count": len(blindspots),
    }


def _build_findings(health: dict[str, Any], *, tool_contract: dict[str, Any] | None = None) -> list[str]:
    findings: list[str] = []
    l2 = health.get("l2_entities") or {}
    docs = health.get("l3_documents") or {}
    tasks = health.get("tasks") or {}
    blindspots = health.get("blindspots") or {}
    invalid_documents = health.get("invalid_documents") or {}
    source_governance = health.get("source_governance") or {}
    delivery_auth = health.get("delivery_auth") or {}

    if int(l2.get("active_l2_missing_impacts") or 0) > 0:
        findings.append(f"L2 missing impacts: {l2['active_l2_missing_impacts']}")
    if int(l2.get("entry_saturation_count") or 0) > 0:
        findings.append(f"L2 entry saturation candidates: {l2['entry_saturation_count']}")
    if int(docs.get("stale_count") or 0) > 0:
        findings.append(f"Stale documents: {docs['stale_count']}")
    if int(docs.get("document_consistency_count") or 0) > 0:
        findings.append(f"Document consistency warnings: {docs['document_consistency_count']}")
    if int(tasks.get("stalled_open_count") or 0) > 0:
        findings.append(f"Stalled open tasks (>7d): {tasks['stalled_open_count']}")
    if int(blindspots.get("green_open_count") or 0) > 0:
        findings.append(f"Open green blindspots: {blindspots['green_open_count']}")
    if int(invalid_documents.get("current_formal_entry_missing_delivery_snapshot") or 0) > 0:
        findings.append(
            "Current formal-entry missing delivery snapshot: "
            f"{invalid_documents['current_formal_entry_missing_delivery_snapshot']}"
        )
    if int(invalid_documents.get("current_formal_entry_stale_delivery_snapshot") or 0) > 0:
        findings.append(
            "Current formal-entry stale delivery snapshot: "
            f"{invalid_documents['current_formal_entry_stale_delivery_snapshot']}"
        )
    if int(source_governance.get("source_not_found_count") or 0) > 0:
        findings.append(
            "Current formal-entry SOURCE_NOT_FOUND during controlled replay: "
            f"{source_governance['source_not_found_count']}"
        )
    if int(source_governance.get("alternative_uri_candidate_count") or 0) > 0:
        findings.append(
            "Current formal-entry with alternative URI candidates: "
            f"{source_governance['alternative_uri_candidate_count']}"
        )
    if delivery_auth.get("github_secret_invalid"):
        http_status = delivery_auth.get("github_secret_http_status")
        suffix = f" ({http_status})" if http_status else ""
        findings.append(f"GitHub delivery secret invalid{suffix}")
    tool_contract = tool_contract or {}
    if bool(tool_contract.get("schema_freshness_blocker")):
        findings.append("Tool schema freshness blocker: expected preview param missing from transcript")
    return findings


def build_monitor_report(
    *,
    df_id: str,
    existing_monitor: str | Path | None = None,
    quality_json: str | Path | None = None,
    staleness_json: str | Path | None = None,
    invalid_documents_json: str | Path | None = None,
    source_repair_queue_json: str | Path | None = None,
    github_delivery_secret_health_json: str | Path | None = None,
    tasks_json: str | Path | None = None,
    blindspots_json: str | Path | None = None,
    out_root: str | Path = DEFAULT_OUT_ROOT,
) -> dict[str, Any]:
    base = _read_json(existing_monitor)
    out_dir = Path(out_root) / df_id
    out_dir.mkdir(parents=True, exist_ok=True)

    quality_payload = _read_json(quality_json)
    staleness_payload = _read_json(staleness_json)
    invalid_documents_payload = _read_json(invalid_documents_json)
    source_repair_payload = _read_json(source_repair_queue_json)
    github_delivery_secret_health_payload = _read_json(github_delivery_secret_health_json)
    tasks_payload = _read_json(tasks_json)
    blindspots_payload = _read_json(blindspots_json)

    health = {
        "l2_entities": _build_quality_summary(quality_payload),
        "l3_documents": _build_staleness_summary(staleness_payload),
        "invalid_documents": _build_invalid_documents_summary(invalid_documents_payload),
        "source_governance": _build_source_repair_summary(source_repair_payload),
        "delivery_auth": _build_delivery_auth_summary(github_delivery_secret_health_payload),
        "tasks": _build_tasks_summary(tasks_payload),
        "blindspots": _build_blindspots_summary(blindspots_payload),
    }
    findings = _build_findings(health, tool_contract=(base.get("tool_contract") or {}))

    merged = {
        **base,
        "df_id": df_id,
        "health": health,
        "findings": findings,
        "health_inputs": {
            "quality_json": str(quality_json) if quality_json else None,
            "staleness_json": str(staleness_json) if staleness_json else None,
            "invalid_documents_json": str(invalid_documents_json) if invalid_documents_json else None,
            "source_repair_queue_json": str(source_repair_queue_json) if source_repair_queue_json else None,
            "github_delivery_secret_health_json": (
                str(github_delivery_secret_health_json) if github_delivery_secret_health_json else None
            ),
            "tasks_json": str(tasks_json) if tasks_json else None,
            "blindspots_json": str(blindspots_json) if blindspots_json else None,
        },
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }

    out_path = Path(existing_monitor) if existing_monitor else (out_dir / "monitor.json")
    out_path.write_text(json.dumps(merged, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {
        "df_id": df_id,
        "out_path": str(out_path),
        "findings_count": len(findings),
        "health": health,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build dogfood health monitor report from MCP JSON payloads")
    parser.add_argument("--df-id", required=True)
    parser.add_argument("--existing-monitor", help="Existing monitor.json from build_iteration_artifacts.py")
    parser.add_argument("--quality-json")
    parser.add_argument("--staleness-json")
    parser.add_argument("--invalid-documents-json")
    parser.add_argument("--source-repair-queue-json")
    parser.add_argument("--github-delivery-secret-health-json")
    parser.add_argument("--tasks-json")
    parser.add_argument("--blindspots-json")
    parser.add_argument("--out-root", default=str(DEFAULT_OUT_ROOT))
    args = parser.parse_args()

    payload = build_monitor_report(
        df_id=args.df_id,
        existing_monitor=args.existing_monitor,
        quality_json=args.quality_json,
        staleness_json=args.staleness_json,
        invalid_documents_json=args.invalid_documents_json,
        source_repair_queue_json=args.source_repair_queue_json,
        github_delivery_secret_health_json=args.github_delivery_secret_health_json,
        tasks_json=args.tasks_json,
        blindspots_json=args.blindspots_json,
        out_root=args.out_root,
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
