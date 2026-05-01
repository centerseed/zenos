"""MCP tools: journal_write, journal_read — work journal management."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from zenos.interface.mcp._auth import _current_partner
from zenos.interface.mcp._common import _unified_response

logger = logging.getLogger(__name__)


async def journal_write(
    summary: str,
    project: str | None = None,
    flow_type: str | None = None,
    tags: list[str] | None = None,
    source_type: str | None = None,
    source_ref: str | None = None,
    change_kind: str | None = None,
) -> dict:
    """記錄工作日誌條目。

    使用時機：
    - 重大 flow 結束時呼叫，記錄本次完成的工作、遺留問題、重要決策。
    - 讓下次 session 開始時能快速恢復 context，減少用戶重新補充資訊的需要。
    - 不要在每個 task / handoff / 小修復後都寫；任務結果請放 task.result，長期知識請寫 entries。

    summary 會自動截斷至 500 字。超過 20 則日誌時，會自動觸發壓縮（舊條目合併為摘要）。

    Args:
        summary: 工作摘要（自動截斷至 500 字）
        project: 相關專案名稱（選填）
        flow_type: 工作類型，例如 feature/bugfix/review/research（選填）
        tags: 標籤列表（選填）

    Returns:
        dict — {id, created_at, compressed: bool}
    """
    import json as _json
    from zenos.interface.mcp import _ensure_journal_repo, _compress_journal
    import zenos.interface.mcp as _mcp
    from zenos.infrastructure.context import current_partner_id as _current_partner_id
    from zenos.interface.mcp._audit import _audit_log

    # Coerce tags: agent 有時會傳 JSON 字串而非 list
    if isinstance(tags, str):
        try:
            tags = _json.loads(tags)
        except (_json.JSONDecodeError, ValueError):
            tags = [t.strip() for t in tags.split(",") if t.strip()]

    await _ensure_journal_repo()
    jr = _mcp._journal_repo
    assert jr is not None
    partner_id = _current_partner_id.get()
    if not partner_id:
        return _unified_response(status="rejected", data={}, rejection_reason="No authenticated partner context")

    entry_warnings: list[str] = []
    summary = str(summary or "").strip()
    if not summary:
        return _unified_response(
            status="rejected",
            data={"error": "EMPTY_SUMMARY"},
            rejection_reason="journal summary is required",
        )
    valid_source_types = {"capture", "sync", "feature", "debug", "governance", "manual"}
    valid_change_kinds = {"knowledge_changed", "handoff_resume", "unresolved_gap"}
    if source_type is not None and source_type not in valid_source_types:
        return _unified_response(
            status="rejected",
            data={"error": "INVALID_SOURCE_TYPE", "allowed": sorted(valid_source_types)},
            rejection_reason="invalid journal source_type",
        )
    if change_kind is not None and change_kind not in valid_change_kinds:
        return _unified_response(
            status="rejected",
            data={"error": "INVALID_CHANGE_KIND", "allowed": sorted(valid_change_kinds)},
            rejection_reason="invalid journal change_kind",
        )
    if source_type in {"capture", "sync"} and (not source_ref or not change_kind):
        return _unified_response(
            status="rejected",
            data={"error": "MISSING_JOURNAL_GOVERNANCE_FIELDS"},
            rejection_reason="source_type=capture|sync requires source_ref and change_kind",
        )
    governance_tags = list(tags or [])
    if source_type:
        governance_tags.append(f"source_type:{source_type}")
    if source_ref:
        governance_tags.append(f"source_ref:{source_ref}")
    if change_kind:
        governance_tags.append(f"change_kind:{change_kind}")

    if source_type and source_ref and change_kind:
        recent_entries, _ = await jr.list_recent(partner_id=partner_id, limit=20)
        required = {f"source_type:{source_type}", f"source_ref:{source_ref}", f"change_kind:{change_kind}"}
        for entry in recent_entries:
            if required.issubset(set(entry.get("tags") or [])):
                _audit_log(
                    event_type="journal.write.rejected",
                    target={"collection": "journal", "id": None},
                    changes={"source_type": source_type, "source_ref": source_ref, "change_kind": change_kind},
                    governance={"reason": "duplicate_recent_journal"},
                )
                return _unified_response(
                    status="rejected",
                    data={"error": "DUPLICATE_JOURNAL_WRITE"},
                    rejection_reason="duplicate source_type/source_ref/change_kind journal write",
                )
    if len(summary) > 500:
        summary = summary[:500]
        entry_warnings.append("journal summary truncated to 500 chars")

    # Auto-fill project from partner context if caller omits it
    _partner = _current_partner.get()
    effective_project = project or (_partner.get("defaultProject", "") if _partner else "") or None

    entry_id = await jr.create(
        partner_id=partner_id,
        summary=summary,
        project=effective_project,
        flow_type=flow_type,
        tags=governance_tags,
    )
    compressed = False
    count_originals = getattr(jr, "count_originals", None) if hasattr(type(jr), "count_originals") else None
    raw_count = await count_originals(partner_id=partner_id) if count_originals is not None else await jr.count(partner_id=partner_id)
    if raw_count > 20:
        compressed = bool(await _compress_journal(partner_id))
        if compressed:
            _audit_log(
                event_type="journal.write.compressed",
                target={"collection": "journal", "id": entry_id},
                changes={"raw_count": raw_count},
            )

    return _unified_response(
        data={"id": entry_id, "created_at": datetime.now(timezone.utc).isoformat(), "compressed": compressed},
        warnings=entry_warnings,
        governance_hints={
            "distillation_required": compressed,
            "message": "compressed journal is Tier-2 material; distill into entries only after review" if compressed else "",
        },
    )


async def journal_read(
    limit: int = 10,
    project: str | None = None,
    flow_type: str | None = None,
) -> dict:
    """讀取近期工作日誌。

    使用時機：
    - session 開始時呼叫，快速回顧近期工作脈絡，取代讓用戶重新補充 context。
    - 了解上次 session 完成了什麼、遺留哪些問題、有哪些重要決策。

    Args:
        limit: 回傳筆數上限（預設 10，最大 50）
        project: 篩選特定專案（選填）
        flow_type: 篩選特定工作類型（選填）

    Returns:
        dict — {entries: [...], count: int, total: int}
        每個 entry 包含：id, created_at, project, flow_type, summary, tags, is_summary
    """
    from zenos.interface.mcp import _ensure_journal_repo
    import zenos.interface.mcp as _mcp
    from zenos.infrastructure.context import current_partner_id as _current_partner_id

    await _ensure_journal_repo()
    jr = _mcp._journal_repo
    assert jr is not None
    partner_id = _current_partner_id.get()
    if not partner_id:
        return _unified_response(status="rejected", data={}, rejection_reason="No authenticated partner context")

    limit = max(1, min(limit, 50))

    # Auto-fill project from partner context if caller omits it
    _partner = _current_partner.get()
    effective_project = project or (_partner.get("defaultProject", "") if _partner else "") or None

    entries, total = await jr.list_recent(
        partner_id=partner_id,
        limit=limit,
        project=effective_project,
        flow_type=flow_type,
    )
    # Convert datetime fields to ISO strings for JSON serialization
    serialized = [
        {**e, "created_at": e["created_at"].isoformat() if hasattr(e["created_at"], "isoformat") else e["created_at"]}
        for e in entries
    ]
    return _unified_response(
        data={"entries": serialized, "count": len(serialized), "total": total}
    )
