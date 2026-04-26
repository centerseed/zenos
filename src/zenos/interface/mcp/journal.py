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
        tags=tags or [],
    )
    count = await jr.count(partner_id=partner_id)
    compressed = False
    if count > 20:
        await _compress_journal(partner_id)
        compressed = True

    return _unified_response(
        data={"id": entry_id, "created_at": datetime.now(timezone.utc).isoformat(), "compressed": compressed},
        warnings=entry_warnings,
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
