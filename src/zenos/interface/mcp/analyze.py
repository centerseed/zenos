"""MCP tool: analyze — governance health checks."""

from __future__ import annotations

import logging
import re

from zenos.application.knowledge.ontology_service import _collect_subtree_ids
from zenos.domain.doc_types import canonical_type, generate_source_id
from zenos.domain.document_linkage import get_document_linked_entity_ids
from zenos.domain.governance import (
    compute_search_unused_signals,
    detect_document_bundle_governance_issues,
    detect_invalid_document_titles,
    score_summary_quality,
)

from zenos.interface.mcp._common import _serialize, _unified_response, _error_response, _format_not_found, _new_id

logger = logging.getLogger(__name__)

_INVALID_DOCUMENT_BUNDLE_ISSUE_LIMIT = 50


def _bundle_issue_sort_key(issue: dict) -> tuple:
    severity_rank = {"red": 0, "yellow": 1, "green": 2}
    type_rank = {
        "index_missing_sources": 0,
        "index_missing_bundle_highlights": 1,
        "index_missing_primary_highlight": 2,
        "l2_missing_current_index_document": 3,
        "index_missing_change_summary": 4,
        "index_summary_not_retrieval_map": 5,
    }
    return (
        severity_rank.get(str(issue.get("severity", "")).lower(), 9),
        type_rank.get(str(issue.get("issue_type", "")), 9),
        str(issue.get("title") or issue.get("linked_entity_id") or issue.get("entity_id") or ""),
    )


def _doc_primary_source(doc: object) -> dict | None:
    sources = list(getattr(doc, "sources", None) or [])
    if not sources:
        return None
    return next((src for src in sources if src.get("is_primary")), sources[0])


def _compact_text(value: object, *, limit: int = 120) -> str:
    text = re.sub(r"\s+", " ", str(value or "").strip())
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def _source_label(source: dict) -> str:
    return str(
        source.get("label")
        or source.get("uri")
        or source.get("source_id")
        or "source"
    ).strip()


def _source_role_line(source: dict) -> str:
    label = _source_label(source)
    doc_type = _source_doc_type(source, object())
    status = str(source.get("doc_status") or source.get("source_status") or source.get("status") or "valid").strip()
    snapshot = _compact_text(source.get("snapshot_summary"), limit=110)
    note = _compact_text(source.get("note"), limit=90)
    primary = "primary, " if source.get("is_primary") else ""
    details = f"{primary}{doc_type}, {status}"
    if snapshot:
        details += f", 摘要：{snapshot}"
    elif note:
        details += f", note：{note}"
    return f"{label}（{details}）"


def _source_routing_text(sources: list[dict], *, limit: int = 5) -> str:
    if not sources:
        return "目前尚未登錄可 routing 的 source"
    return "；".join(_source_role_line(src) for src in sources[:limit])


def _doc_context_line(doc: object) -> str:
    title = str(getattr(doc, "name", "") or "未命名文件").strip()
    role = str(getattr(doc, "doc_role", "") or "single").strip()
    status = str(getattr(doc, "status", "") or "current").strip()
    summary = _compact_text(getattr(doc, "summary", ""), limit=100)
    sources = list(getattr(doc, "sources", None) or [])
    source_text = _source_routing_text(sources, limit=2)
    if summary:
        return f"{title}（{status}/{role}）：{summary}；sources：{source_text}"
    return f"{title}（{status}/{role}）：sources：{source_text}"


def _source_doc_type(source: dict | None, doc: object) -> str:
    source = source or {}
    raw_doc_type = str(source.get("doc_type") or "").strip().upper()
    if raw_doc_type:
        return canonical_type(raw_doc_type)
    return _infer_doc_type_from_text(
        source.get("label"),
        source.get("uri"),
        getattr(doc, "name", ""),
    )


def _doc_type_read_reason(doc_type: str, title: str) -> str:
    reasons = {
        "SPEC": f"需要理解「{title}」的需求、驗收邊界或功能規格時先讀。",
        "DESIGN": f"需要理解「{title}」的技術設計、實作邊界或架構取捨時先讀。",
        "DECISION": f"需要理解「{title}」的決策背景、替代方案或後續影響時先讀。",
        "REPORT": f"需要理解「{title}」的研究結論、分析依據或決策參考時先讀。",
        "TEST": f"需要理解「{title}」的測試情境、驗收覆蓋或品質風險時先讀。",
        "PLAN": f"需要理解「{title}」的階段目標、完成邊界或排程脈絡時先讀。",
        "GUIDE": f"需要理解「{title}」的操作步驟、治理規則或日常流程時先讀。",
        "REFERENCE": f"需要查找「{title}」的背景資料、外部依據或補充脈絡時先讀。",
        "CONTRACT": f"需要確認「{title}」的約束、承諾或服務邊界時先讀。",
        "MEETING": f"需要理解「{title}」的會議決議、討論脈絡或後續行動時先讀。",
    }
    return reasons.get(doc_type, f"需要理解「{title}」的主要內容、閱讀入口或相關脈絡時先讀。")


def _doc_tags(doc: object) -> dict:
    tags = getattr(doc, "tags", None)
    if tags is None:
        return {}
    if isinstance(tags, dict):
        return tags
    return {
        "what": getattr(tags, "what", None),
        "why": getattr(tags, "why", None),
        "how": getattr(tags, "how", None),
        "who": getattr(tags, "who", None),
    }


def _tag_text(value: object, *, limit: int = 90) -> str:
    if isinstance(value, list):
        return _compact_text("、".join(str(v) for v in value if str(v).strip()), limit=limit)
    return _compact_text(value, limit=limit)


def _doc_question_text(doc: object, doc_type: str) -> str:
    title = str(getattr(doc, "name", "") or "此主題").strip()
    tags = _doc_tags(doc)
    what = _tag_text(tags.get("what"), limit=90)
    why = _tag_text(tags.get("why"), limit=120)
    how = _tag_text(tags.get("how"), limit=70)
    subject = what or title
    if doc_type == "SPEC":
        return f"它主要回答「{subject}」的需求範圍、驗收邊界與實作前提。"
    if doc_type == "DESIGN":
        return f"它主要回答「{subject}」的架構設計、技術取捨與實作邊界。"
    if doc_type == "DECISION":
        return f"它主要回答「{subject}」的決策背景、替代方案與後續影響。"
    if doc_type == "GUIDE":
        return f"它主要回答「{subject}」的操作流程、治理規則與日常執行方式。"
    if doc_type == "REFERENCE":
        return f"它主要回答「{subject}」有哪些背景資料、補充依據與索引入口。"
    if doc_type == "TEST":
        return f"它主要回答「{subject}」的測試情境、驗收覆蓋與品質風險。"
    if why:
        return f"它主要回答「{subject}」的脈絡與用途：{why}。"
    if how:
        return f"它主要回答「{subject}」在 {how} 面向的閱讀入口與判斷依據。"
    return f"它主要回答「{title}」有哪些正式資料、閱讀順序與 source 邊界。"


def _doc_usage_text(doc: object, doc_type: str) -> str:
    tags = _doc_tags(doc)
    who = _tag_text(tags.get("who"), limit=70)
    how = _tag_text(tags.get("how"), limit=70)
    if who and how:
        return f"適合 {who} 在處理 {how} 任務時先讀。"
    if who:
        return f"適合 {who} 需要判斷此主題時先讀。"
    return _doc_type_read_reason(doc_type, str(getattr(doc, "name", "") or "此主題"))


def _doc_primary_highlight(doc: object) -> dict | None:
    primary_source = _doc_primary_source(doc)
    if primary_source is None:
        return None
    source_id = primary_source.get("source_id")
    title = str(getattr(doc, "name", "") or "此文件群")
    label = primary_source.get("label") or primary_source.get("uri") or "primary source"
    doc_type = _source_doc_type(primary_source, doc)
    if not source_id:
        return None
    return {
        "source_id": source_id,
        "headline": f"{label} 是這個 L3 index 的 primary source",
        "reason_to_read": _doc_type_read_reason(doc_type, title),
        "priority": "primary",
    }


def _doc_retrieval_summary(doc: object) -> str:
    title = str(getattr(doc, "name", "") or "未命名文件")
    sources = list(getattr(doc, "sources", None) or [])
    primary_source = _doc_primary_source(doc)
    primary_doc_type = _source_doc_type(primary_source, doc)
    primary_label = (
        _source_label(primary_source)
        if primary_source else "primary source"
    )
    source_text = _source_routing_text(sources)
    question_text = _doc_question_text(doc, primary_doc_type)
    usage_text = _doc_usage_text(doc, primary_doc_type)
    return (
        f"這個 L3 index 是「{title}」的文件群 retrieval map。"
        f"{question_text}"
        f"{usage_text}"
        f"Primary source 是 {primary_label}。目前 source routing：{source_text}。"
        f"Primary source 類型判定為 {primary_doc_type}，閱讀時應以該類型的治理邊界判斷用途。"
        "Agent 找到對應 L2 後，應先讀本 summary 與 bundle_highlights，再依任務選讀 source。"
    )


def _doc_change_summary(doc: object) -> str:
    source_count = len(list(getattr(doc, "sources", None) or []))
    highlight_count = len(list(getattr(doc, "bundle_highlights", None) or []))
    title = str(getattr(doc, "name", "") or "此文件群")
    return (
        f"L3 document governance analyzer 建議：將「{title}」整理成可掃描的文件群入口，"
        f"目前有 {source_count} 個 source、{highlight_count} 個 highlight；"
        "本次補齊 summary / change_summary，讓 agent 能先判斷閱讀順序與 source 邊界。"
    )


def _index_create_summary(entity_name: str, existing_docs: list[object]) -> str:
    doc_lines = [
        _doc_context_line(doc)
        for doc in existing_docs[:5]
        if str(getattr(doc, "name", "") or "").strip()
    ]
    doc_text = "；".join(doc_lines) if doc_lines else "目前已掛載到此 L2 的文件尚未提供足夠 summary/source metadata"
    return (
        f"這個 L3 index 是「{entity_name}」的文件群 retrieval map。"
        f"它用來回答此 L2 有哪些正式文件、哪份 source 應先讀、以及各 source 的閱讀邊界。"
        f"目前可先整理的既有文件與 source 線索：{doc_text}。"
        "Primary source 是 ZenOS native delivery，用來承載這個文件群索引本身。"
        "Agent 找到此 L2 後，應先讀本 summary 與 bundle_highlights，再依任務選讀既有文件或後續補充 source。"
    )


def _infer_doc_type_from_text(*parts: object) -> str:
    text = " ".join(str(part or "") for part in parts).strip()
    upper = text.upper()
    prefix_match = re.search(
        r"(?:^|[/\s_\-:：])"
        r"(SPEC|PRD|FRD|DESIGN|DECISION|ADR|TD|TEST|TC|PLAN|REPORT|CONTRACT|GUIDE|PB|PLAYBOOK|MEETING|REFERENCE|REF)"
        r"(?:$|[/\s_\-:：.])",
        upper,
    )
    if prefix_match:
        prefix = prefix_match.group(1)
        if prefix in {"PRD", "FRD"}:
            return "SPEC"
        if prefix == "PLAYBOOK":
            return "GUIDE"
        return canonical_type(prefix)

    keyword_rules = [
        ("DECISION", ("決策", "選型", "ADR")),
        ("DESIGN", ("設計", "架構", "實作", "IMPLEMENTATION", "HANDOFF")),
        ("SPEC", ("規格", "需求", "REQUIREMENT", "PRD", "FRD")),
        ("TEST", ("測試", "驗收", "QA")),
        ("PLAN", ("計畫", "企劃", "排程", "ROADMAP")),
        ("REPORT", ("報告", "分析", "回顧")),
        ("CONTRACT", ("合約", "協議", "SLA")),
        ("MEETING", ("會議", "MEETING")),
        ("REFERENCE", ("參考", "REFERENCE")),
        ("GUIDE", ("指南", "手冊", "SOP", "PLAYBOOK", "規範", "治理")),
    ]
    for doc_type, keywords in keyword_rules:
        if any(keyword in upper or keyword in text for keyword in keywords):
            return doc_type
    return "OTHER"


def _doc_native_source_patch(doc: object) -> dict:
    title = str(getattr(doc, "name", "") or "未命名文件")
    doc_id = str(getattr(doc, "id", "") or "").strip()
    doc_type = _infer_doc_type_from_text(title)
    return {
        "type": "zenos_native",
        "uri": f"/docs/{doc_id}",
        "label": f"{doc_type}: {title} ZenOS native delivery",
        "doc_type": doc_type,
        "doc_status": "current",
        "note": "Analyzer 建議先補 ZenOS native source，讓 current index 有可 routing 的 delivery 入口。",
        "is_primary": True,
        "retrieval_mode": "snapshot",
        "content_access": "full",
    }


def _build_document_bundle_repair_patch(issue: dict, doc: object | None) -> dict | None:
    """Build an executable-but-reviewable write patch for document bundle issues."""
    if doc is None or not getattr(doc, "id", None):
        return None
    issue_type = issue.get("issue_type")
    if issue_type not in {
        "index_missing_bundle_highlights",
        "index_missing_primary_highlight",
        "index_missing_sources",
        "index_summary_not_retrieval_map",
        "index_missing_change_summary",
    }:
        return None

    data: dict = {
        "id": doc.id,
        "title": getattr(doc, "name", "") or "未命名文件",
        "status": getattr(doc, "status", None) or "current",
        "doc_role": getattr(doc, "doc_role", None) or "index",
    }

    linked_ids = list(issue.get("linked_entity_ids") or [])
    if linked_ids:
        data["linked_entity_ids"] = linked_ids

    if issue_type == "index_missing_sources":
        data["add_source"] = _doc_native_source_patch(doc)
        data["change_summary"] = (
            "L3 document governance analyzer 建議：補上 ZenOS native source，"
            "讓此 current index 能先有可讀 delivery 入口，再補 bundle_highlights。"
        )

    if issue_type in {
        "index_missing_bundle_highlights",
        "index_missing_primary_highlight",
    }:
        existing_highlights = [
            item for item in list(getattr(doc, "bundle_highlights", None) or [])
            if isinstance(item, dict)
        ]
        primary_highlight = _doc_primary_highlight(doc)
        if primary_highlight is not None:
            non_primary = [
                item for item in existing_highlights
                if item.get("source_id") != primary_highlight["source_id"]
            ]
            data["bundle_highlights"] = [primary_highlight, *non_primary][:5]

    if issue_type == "index_summary_not_retrieval_map":
        data["summary"] = _doc_retrieval_summary(doc)

    if issue_type == "index_missing_change_summary":
        data["change_summary"] = _doc_change_summary(doc)

    if "summary" not in data and not (getattr(doc, "summary", "") or "").strip():
        data["summary"] = _doc_retrieval_summary(doc)
    if "change_summary" not in data and not (getattr(doc, "change_summary", "") or "").strip():
        data["change_summary"] = _doc_change_summary(doc)

    if issue_type in {
        "index_missing_bundle_highlights",
        "index_missing_primary_highlight",
    } and "bundle_highlights" not in data:
        return None
    if issue_type == "index_missing_sources" and "add_source" not in data:
        return None
    if issue_type == "index_summary_not_retrieval_map" and "summary" not in data:
        return None
    if issue_type == "index_missing_change_summary" and "change_summary" not in data:
        return None

    return {
        "tool": "write",
        "collection": "documents",
        "data": data,
        "needs_agent_review": True,
    }


def _build_l2_index_create_patch(
    issue: dict,
    linked_entity: object | None,
    existing_docs: list[object],
) -> dict | None:
    if issue.get("issue_type") != "l2_missing_current_index_document":
        return None
    linked_entity_id = str(issue.get("linked_entity_id") or "").strip()
    if not linked_entity_id:
        return None
    entity_name = str(getattr(linked_entity, "name", "") or linked_entity_id).strip()
    doc_id = _new_id()
    source_id = generate_source_id()
    title = f"{entity_name}：文件群索引"
    source = {
        "source_id": source_id,
        "type": "zenos_native",
        "uri": f"/docs/{doc_id}",
        "label": f"GUIDE: {title} ZenOS native delivery",
        "doc_type": "GUIDE",
        "doc_status": "current",
        "note": "Analyzer 建議建立 L3 index document，讓此 L2 有正式文件群入口。",
        "is_primary": True,
        "retrieval_mode": "snapshot",
        "content_access": "full",
    }
    return {
        "tool": "write",
        "collection": "documents",
        "needs_agent_review": True,
        "data": {
            "id": doc_id,
            "create_index_document": True,
            "title": title,
            "status": "current",
            "doc_role": "index",
            "formal_entry": True,
            "linked_entity_ids": [linked_entity_id],
            "tags": {
                "what": [entity_name, "L3 index", "文件群索引"],
                "why": "讓 agent 從 L2 快速找到正式文件與閱讀順序",
                "how": "以 summary / bundle_highlights / sources 作為 retrieval map",
                "who": ["agent"],
            },
            "summary": _index_create_summary(entity_name, existing_docs),
            "change_summary": "L3 document governance analyzer 建議：此 L2 缺 current index document，先建立文件群索引入口。",
            "sources": [source],
            "bundle_highlights": [{
                "source_id": source_id,
                "headline": f"{title} 是「{entity_name}」的 L3 文件群入口",
                "reason_to_read": _doc_type_read_reason("GUIDE", title),
                "priority": "primary",
            }],
        },
    }


async def analyze(
    check_type: str = "all",
    entity_id: str | None = None,
) -> dict:
    """執行 ontology 治理健康檢查。

    分析整個知識庫的品質、新鮮度和潛在盲點。
    結果可用來發現問題、建立改善任務。

    使用時機：
    - 定期健檢 → analyze(check_type="all")
    - 輕量 KPI 快照 → analyze(check_type="health")
    - 只看品質分數 → analyze(check_type="quality")
    - 找過時內容 → analyze(check_type="staleness")
    - 推斷盲點 → analyze(check_type="blindspot")
    - 只看 impacts 斷鏈 → analyze(check_type="impacts")
    - 只看文件一致性 → analyze(check_type="document_consistency")
    - 分析能見度風險 → analyze(check_type="permission_risk")
    - 找無效文件條目 → analyze(check_type="invalid_documents")
    - 清理孤立關聯 → analyze(check_type="orphaned_relationships")
    - 檢查 server 端 LLM 依賴與 provider 健康 → analyze(check_type="llm_health")
    不要用這個工具的情境：
    - 搜尋或列出條目 → 用 search
    - 更新 ontology 內容 → 用 write

    Args:
        check_type: "all" / "health" / "quality" / "staleness" / "blindspot" / "impacts" /
                    "document_consistency" / "permission_risk" / "invalid_documents" /
                    "orphaned_relationships" / "llm_health"

    Returns:
        dict — 各 check_type 對應的子結構：
        - quality: {score, total_entities, issues[{entity_id, entity_name, defect}], ...}
                   含 L2 治理補充欄位（l2_impacts_repairs, l2_backfill_proposals, 等）
        - staleness: {warnings[{...}], count, document_consistency_warnings, document_consistency_count}
        - blindspots: {blindspots[{...}], count, task_signal_suggestions[{...}], task_signal_count}
        - permission_risk: {isolation_score, overexposure_score, warnings[{...}], summary}
        - impacts: quality.l2_impacts_validity（掛在 quality 子結構下）
        - document_consistency: {document_consistency_warnings[{...}], document_consistency_count}
        - invalid_documents: {items[{entity_id, current_title, source_uri, linked_entity_ids,
                             proposed_title, action}], count}
        - llm_health: {provider_status[{...}], dependency_points[{...}], findings[{...}], overall_level}
        - kpis: {total_items, unconfirmed_items, unconfirmed_ratio, blindspot_total,
                 duplicate_blindspots, duplicate_blindspot_rate, median_confirm_latency_days,
                 active_l2_missing_impacts, weekly_review_required}（check_type="all" 時包含）
    """
    from zenos.interface.mcp import _ensure_services, _ensure_governance_ai
    import zenos.interface.mcp as _mcp
    from zenos.infrastructure.context import current_partner_id as _current_partner_id
    from zenos.infrastructure.sql_common import get_pool, upsert_health_cache

    await _ensure_services()
    results: dict = {}
    l2_repairs: list[dict] = []

    def _is_concrete_impacts_description(description: str) -> bool:
        desc = (description or "").strip()
        if not desc:
            return False
        if "→" in desc:
            left, right = desc.split("→", 1)
            return bool(left.strip()) and bool(right.strip())
        if "->" in desc:
            left, right = desc.split("->", 1)
            return bool(left.strip()) and bool(right.strip())
        return False

    async def _infer_l2_repairs() -> list[dict]:
        all_entities = await _mcp.ontology_service._entities.list_all()
        active_modules = [
            e for e in all_entities
            if e.type == "module" and e.status == "active" and e.id
        ]
        draft_modules = [
            e for e in all_entities
            if e.type == "module" and e.status == "draft" and e.id
        ]
        if not active_modules and not draft_modules:
            return []

        impact_entity_ids: set[str] = set()
        seen_rel_ids: set[str | None] = set()
        for ent in all_entities:
            if not ent.id:
                continue
            rels = await _mcp.ontology_service._relationships.list_by_entity(ent.id)
            for rel in rels:
                if rel.id in seen_rel_ids:
                    continue
                seen_rel_ids.add(rel.id)
                if rel.type != "impacts":
                    continue
                if not _is_concrete_impacts_description(rel.description):
                    continue
                impact_entity_ids.add(rel.source_entity_id)
                impact_entity_ids.add(rel.target_id)

        repairs = []
        for mod in active_modules:
            if mod.id in impact_entity_ids:
                continue
            repairs.append({
                "entity_id": mod.id,
                "entity_name": mod.name,
                "severity": "red",
                "defect": "active_l2_missing_concrete_impacts",
                "repair_options": [
                    "補 impacts（A 改了什麼→B 的什麼要跟著看）",
                    "降級為 L3",
                    "重新切粒度",
                ],
            })
        for mod in draft_modules:
            override = (
                mod.details.get("manual_override_reason")
                if mod.details and isinstance(mod.details, dict)
                else None
            )
            repairs.append({
                "entity_id": mod.id,
                "entity_name": mod.name,
                "severity": "yellow",
                "defect": "draft_l2_pending_confirmation",
                "manual_override_reason": override,
                "repair_options": [
                    "補 impacts 後 confirm",
                    "降級為 L3",
                ],
            })
        return repairs

    async def _list_saturated_entities() -> list[dict]:
        """Fast listing of (entity, department) saturation groups (>= 20 active).

        Diagnose-only: no LLM call. Use _consolidate_one(entity_id) to run
        the actual LLM proposal for a single entity (DF-20260419-L2c).
        """
        _erepo = _mcp.entry_repo
        if _erepo is None:
            return []
        saturated = await _erepo.list_saturated_entities(threshold=20)
        return [
            {
                "entity_id": item["entity_id"],
                "entity_name": item["entity_name"],
                "active_count": item["active_count"],
                **({"department": item["department"]} if item.get("department") is not None else {}),
            }
            for item in saturated
        ]

    async def _consolidate_one(target_entity_id: str) -> dict | None:
        """Run LLM consolidation proposal for a single (entity, department) group.

        Returns {entity_id, entity_name, active_count, department, consolidation_proposal}
        or None if the entity isn't saturated / no LLM available.
        """
        _erepo = _mcp.entry_repo
        _gai = _mcp._governance_ai
        if _erepo is None or _gai is None:
            return None
        saturated = await _erepo.list_saturated_entities(threshold=20)
        match = next((s for s in saturated if s["entity_id"] == target_entity_id), None)
        if match is None:
            return None
        dept = match.get("department")
        all_entries = await _erepo.list_by_entity(target_entity_id, status="active")
        entries = [e for e in all_entries if e.department == dept]
        entry_dicts = [
            {"id": e.id, "type": e.type, "content": e.content}
            for e in entries
        ]
        proposal = _gai.consolidate_entries(target_entity_id, match["entity_name"], entry_dicts)
        result: dict = {
            "entity_id": target_entity_id,
            "entity_name": match["entity_name"],
            "active_count": match["active_count"],
            "consolidation_proposal": proposal.model_dump() if proposal else None,
        }
        if dept is not None:
            result["department"] = dept
        return result

    def _attach_impacts_repair_actions(validity_report: list[dict]) -> list[dict]:
        """Enrich broken impacts with executable repair payloads.

        The delete capability already exists in `write(collection="relationships")`.
        This helper turns validity diagnostics into an explicit repair path that
        agents can execute without reverse-engineering the interface contract.
        """
        enriched: list[dict] = []
        for module_entry in validity_report:
            repaired_entry = dict(module_entry)
            broken_repairs: list[dict] = []
            for broken in module_entry.get("broken_impacts", []):
                repaired_broken = dict(broken)
                relationship_id = broken.get("relationship_id")
                if relationship_id:
                    repaired_broken["repair_action"] = {
                        "tool": "write",
                        "collection": "relationships",
                        "id": relationship_id,
                        "data": {
                            "action": "delete",
                            "reason": (
                                "remove invalid impacts target "
                                f"({broken.get('reason', 'unknown_reason')})"
                            ),
                        },
                    }
                broken_repairs.append(repaired_broken)
            repaired_entry["broken_impacts"] = broken_repairs
            enriched.append(repaired_entry)
        return enriched

    # DF-20260419-L2c: single-entity consolidation proposal. Separated
    # diagnosis (check_type="quality" lists saturated entities, no LLM) from
    # execution (check_type="consolidate" runs one LLM call for one entity).
    # Previously analyze(quality) did both synchronously in a loop, timing
    # out on any entity with 40+ entries.
    if check_type == "consolidate":
        if not entity_id:
            return _error_response(
                status="rejected",
                error_code="INVALID_INPUT",
                message="analyze(check_type='consolidate') 需要 entity_id（先用 quality 列 saturated 再 targeted call）",
            )
        proposal = await _consolidate_one(entity_id)
        if proposal is None:
            return _error_response(
                status="rejected",
                error_code="NOT_FOUND",
                message=(
                    f"Entity '{entity_id}' 不在 saturation 清單（active entries < 20），"
                    "或 LLM 不可用。先跑 analyze(check_type='quality') 確認是否真的 saturated。"
                ),
            )
        return _unified_response(data=proposal)

    # DF-20260419-L2b: single-entity health audit.
    # Replaces Monitor's manual gather (get entity + list rels + list entries +
    # walk peer parents) with one server-side call. Returns six dimensions
    # per PLAN-zenos-dogfooding-loop L2 rules, plus rule-based anti-pattern
    # hits so governance audit can act without pulling the full corpus.
    if check_type == "entity_health":
        import re as _re

        if not entity_id:
            return _error_response(
                status="rejected",
                error_code="INVALID_INPUT",
                message="analyze(check_type='entity_health') 需要 entity_id",
            )
        entity = await _mcp.entity_repo.get_by_id(entity_id)
        if entity is None:
            return _error_response(
                status="rejected",
                error_code="NOT_FOUND",
                message=_format_not_found("Entity", entity_id),
            )

        partner_dept = "all"
        try:
            from zenos.infrastructure.context import current_partner_department as _cpd
            partner_dept = str(_cpd.get() or "all")
        except Exception:
            pass

        # Dim 1 — summary
        summary_text = entity.summary or ""
        summary_dim = {
            "present": bool(summary_text),
            "length": len(summary_text),
            "over_limit": len(summary_text) > 300,
        }

        # Dim 2 — tags 4-dim
        tags = entity.tags
        missing = []
        if tags:
            if not (tags.what and (tags.what if isinstance(tags.what, list) else [tags.what])):
                missing.append("what")
            if not tags.why:
                missing.append("why")
            if not tags.how:
                missing.append("how")
            if not (tags.who and (tags.who if isinstance(tags.who, list) else [tags.who])):
                missing.append("who")
        else:
            missing = ["what", "why", "how", "who"]
        tags_dim = {"complete": not missing, "missing_dimensions": missing}

        # Dim 3 — relationships
        rels = await _mcp.relationship_repo.list_by_entity(entity_id)
        out_count = sum(1 for r in rels if r.source_entity_id == entity_id)
        in_count = sum(1 for r in rels if r.source_entity_id != entity_id)
        out_confirmed = sum(1 for r in rels if r.source_entity_id == entity_id and r.confirmed_by_user)
        in_confirmed = sum(1 for r in rels if r.source_entity_id != entity_id and r.confirmed_by_user)
        total_confirmed = out_confirmed + in_confirmed

        # Cross-subtree check: walk peers' L1 roots
        all_ents = await _mcp.entity_repo.list_all()
        emap = {e.id: e for e in all_ents if e.id}
        from zenos.application.knowledge.ontology_service import _find_product_root
        self_l1 = _find_product_root(entity_id, emap) if entity_id else None
        cross_subtree = 0
        for r in rels:
            peer_id = r.target_id if r.source_entity_id == entity_id else r.source_entity_id
            peer_l1 = _find_product_root(peer_id, emap) if peer_id else None
            if self_l1 and peer_l1 and peer_l1 != self_l1:
                cross_subtree += 1
        rels_dim = {
            "outgoing": out_count,
            "incoming": in_count,
            "outgoing_confirmed": out_confirmed,
            "incoming_confirmed": in_confirmed,
            "total_confirmed": total_confirmed,
            "orphan": total_confirmed < 2,
            "cross_subtree_count": cross_subtree,
        }

        # Dim 4 — entries saturation & anti-pattern scan
        entries = await _mcp.entry_repo.list_by_entity(entity_id, status="active", department=partner_dept)
        active_count = len(entries)
        saturation_level = "red" if active_count >= 20 else ("yellow" if active_count >= 15 else "green")

        # Rule-based anti-pattern detection (regex, no LLM)
        _commit_re = _re.compile(r"\bcommit\s+[0-9a-f]{7,40}\b", _re.IGNORECASE)
        _sha_re = _re.compile(r"\b[0-9a-f]{7,40}\b")
        _file_line_re = _re.compile(r"\w+\.py[:\s]+L?\d+|:\s*\d{2,4}\b")
        _call_arrow_re = _re.compile(r"→.+→|->.+->")
        _func_dunder_re = _re.compile(r"\b_\w+\(\)")

        def _classify_anti_pattern(text: str) -> list[str]:
            hits = []
            if _commit_re.search(text):
                hits.append("#5_commit_sha")
            elif _sha_re.search(text) and "commit" in text.lower():
                hits.append("#5_commit_sha")
            if _file_line_re.search(text):
                hits.append("#1_code_path_trace")
            if _call_arrow_re.search(text):
                hits.append("#1_call_path")
            if _func_dunder_re.search(text):
                hits.append("#2_internal_func")
            return hits

        anti_pattern_hits = []
        for e in entries:
            text = (e.content or "") + " " + (e.context or "")
            hits = _classify_anti_pattern(text)
            if hits:
                anti_pattern_hits.append({
                    "entry_id": e.id,
                    "type": e.type,
                    "content_preview": (e.content or "")[:80],
                    "patterns": hits,
                })

        entries_dim = {
            "active_count": active_count,
            "threshold": 20,
            "saturation_level": saturation_level,
            "anti_pattern_candidates": anti_pattern_hits,
            "anti_pattern_count": len(anti_pattern_hits),
        }

        # Dim 5 — granularity signal (v1 proxy: entry count + type diversity)
        type_diversity = len({e.type for e in entries}) if entries else 0
        granularity_dim = {
            "active_entries": active_count,
            "type_diversity": type_diversity,
            "split_signal": active_count >= 30 or (active_count >= 20 and type_diversity >= 4),
            "split_reason": (
                "entries >= 30" if active_count >= 30
                else ("entries >= 20 + type diversity >= 4" if active_count >= 20 and type_diversity >= 4 else None)
            ),
        }

        # Verdict
        issues = []
        if not summary_dim["present"]: issues.append("summary_missing")
        if summary_dim["over_limit"]: issues.append("summary_over_300")
        if missing: issues.append("tags_incomplete")
        if rels_dim["orphan"]: issues.append("orphan_insufficient_confirmed_rels")
        if cross_subtree: issues.append("cross_subtree_rels")
        if saturation_level == "red": issues.append("entries_saturated")
        if anti_pattern_hits: issues.append("entries_anti_pattern")
        if granularity_dim["split_signal"]: issues.append("split_candidate")
        verdict = "healthy" if not issues else "needs_review"

        suggested_actions = []
        for h in anti_pattern_hits:
            suggested_actions.append({
                "action": "archive_entry",
                "entry_id": h["entry_id"],
                "reason": f"anti-pattern {','.join(h['patterns'])}",
            })
        if saturation_level == "red":
            suggested_actions.append({
                "action": "consolidate_entries",
                "reason": f"active_count {active_count} >= threshold 20",
            })
        if rels_dim["orphan"]:
            suggested_actions.append({
                "action": "review_relationships",
                "reason": f"only {total_confirmed} confirmed rels (need ≥2)",
            })
        if granularity_dim["split_signal"]:
            suggested_actions.append({
                "action": "consider_split",
                "reason": granularity_dim["split_reason"],
            })

        return _unified_response(data={
            "entity_id": entity_id,
            "name": entity.name,
            "type": entity.type,
            "level": entity.level,
            "dimensions": {
                "summary": summary_dim,
                "tags": tags_dim,
                "relationships": rels_dim,
                "entries": entries_dim,
                "granularity": granularity_dim,
            },
            "issues": issues,
            "verdict": verdict,
            "suggested_actions": suggested_actions,
        })

    # ADR-020: lightweight health check — KPIs only, no heavy analysis
    if check_type == "health":
        try:
            health_signal = await _mcp.governance_service.compute_health_signal(entity_id=entity_id)
        except ValueError as exc:
            return _error_response(
                status="rejected",
                error_code="NOT_FOUND",
                message=str(exc),
            )
        # ADR-021: persist to DB cache for Dashboard consumption
        try:
            pool = await get_pool()
            pid = _current_partner_id.get() or ""
            if pid and health_signal and not entity_id:
                await upsert_health_cache(pool, pid, health_signal.get("overall_level", "green"))
        except Exception:
            pass  # cache write is additive; never break the main operation
        return _unified_response(data=health_signal)

    if check_type in ("all", "llm_health"):
        from zenos.infrastructure.context import current_partner_id as _current_partner_id

        results["llm_health"] = await _mcp.governance_service.analyze_llm_health(
            _current_partner_id.get()
        )

    if check_type in ("all", "quality"):
        # Gather entry counts per entity for sparsity check
        _entries_by_entity: dict[str, int] | None = None
        if _mcp.entry_repo is not None:
            try:
                all_entities_for_sparsity = await _mcp.ontology_service._entities.list_all()
                active_module_ids = [
                    e.id for e in all_entities_for_sparsity
                    if e.type == "module" and e.status == "active" and e.id
                ]
                _entries_by_entity = {}
                for eid in active_module_ids:
                    try:
                        cnt = await _mcp.entry_repo.count_active_by_entity(eid)
                        _entries_by_entity[eid] = cnt
                    except Exception:
                        _entries_by_entity[eid] = 0
            except Exception:
                logger.warning("Entry sparsity data collection failed", exc_info=True)

        report = await _mcp.governance_service.run_quality_check(entries_by_entity=_entries_by_entity)
        results["quality"] = _serialize(report)
        try:
            l2_repairs = await _infer_l2_repairs()
            active_repairs = [r for r in l2_repairs if r.get("defect") == "active_l2_missing_concrete_impacts"]
            draft_repairs = [r for r in l2_repairs if r.get("defect") == "draft_l2_pending_confirmation"]
            results["quality"]["active_l2_missing_impacts"] = len(active_repairs)
            results["quality"]["draft_l2_pending_confirmation"] = len(draft_repairs)
            if l2_repairs:
                results["quality"]["l2_impacts_repairs"] = l2_repairs
        except Exception:
            # Repair suggestion is additive and should not break quality report.
            logger.warning("L2 repairs inference failed", exc_info=True)
        try:
            backfill = await _mcp.governance_service.infer_l2_backfill_proposals()
            results["quality"]["l2_backfill_proposals"] = backfill
            results["quality"]["l2_backfill_count"] = len(backfill)
        except Exception:
            logger.warning("L2 backfill proposals failed", exc_info=True)

        # L2 governance: impacts target validity
        try:
            validity_report = await _mcp.governance_service.check_impacts_target_validity()
            results["quality"]["l2_impacts_validity"] = _attach_impacts_repair_actions(validity_report)
        except Exception:
            logger.warning("L2 impacts target validity check failed", exc_info=True)

        # P0-2: quality correction priority
        try:
            priority_report = await _mcp.governance_service.run_quality_correction_priority()
            results["quality"]["quality_correction_priority"] = priority_report
        except Exception:
            logger.warning("Quality correction priority failed", exc_info=True)

        # L2 governance: stale L2 downstream (entity part from domain; task part here)
        try:
            downstream_entities = await _mcp.governance_service.find_stale_l2_downstream_entities()
            # Enrich with open tasks at interface layer (task_repo available here)
            _open_statuses = {"todo", "in_progress", "review"}
            all_tasks = await _mcp.task_service.list_tasks(limit=500)
            for entry in downstream_entities:
                mod_id = entry["stale_module_id"]
                affected_tasks = [
                    {"id": t.id, "title": t.title, "status": t.status}
                    for t in all_tasks
                    if mod_id in (t.linked_entities or [])
                    and t.status in _open_statuses
                ]
                entry["affected_tasks"] = affected_tasks
                entry["suggested_actions"] = [
                    "重新掛載到 active L2",
                    "更新引用",
                    "降級為 sources",
                ]
            results["quality"]["l2_stale_downstream"] = downstream_entities
        except Exception:
            logger.warning("L2 stale downstream check failed", exc_info=True)

        # L2 governance: reverse impacts check
        try:
            reverse_impacts = await _mcp.governance_service.check_reverse_impacts()
            results["quality"]["l2_reverse_impacts"] = reverse_impacts
        except Exception:
            logger.warning("L2 reverse impacts check failed", exc_info=True)

        # L2 governance: review overdue check
        try:
            overdue = await _mcp.governance_service.check_governance_review_overdue()
            results["quality"]["l2_governance_review_overdue"] = overdue
            results["quality"]["l2_review_overdue_count"] = len(overdue)
        except Exception:
            logger.warning("L2 governance review overdue check failed", exc_info=True)

        # Entry saturation detection (DF-20260419-L2c: list-only, no per-entity
        # LLM consolidate — that was the timeout source. Use
        # analyze(check_type="consolidate", entity_id=X) to generate a proposal
        # for a specific entity.)
        try:
            entry_saturation = await _list_saturated_entities()
            results["quality"]["entry_saturation"] = entry_saturation
            results["quality"]["entry_saturation_count"] = len(entry_saturation)
        except Exception:
            logger.warning("Entry saturation check failed", exc_info=True)

        # Search-unused signals
        try:
            if _mcp._tool_event_repo is not None:
                partner_id = _current_partner_id.get() or ""
                all_entities_for_signals = await _mcp.ontology_service._entities.list_all()
                usage_stats = await _mcp._tool_event_repo.get_entity_usage_stats(partner_id, days=30)
                search_unused = compute_search_unused_signals(usage_stats, all_entities_for_signals)
                if search_unused:
                    results["quality"]["search_unused_signals"] = search_unused
        except Exception:
            logger.warning("Search unused signals check failed", exc_info=True)

        # Summary quality flags
        try:
            all_entities_for_quality = await _mcp.ontology_service._entities.list_all()
            l2_entities = [
                e for e in all_entities_for_quality
                if e.type == "module" and e.status in ("active", "draft") and e.id
            ]
            summary_flags = []
            for e in l2_entities:
                quality = score_summary_quality(e.summary or "", e.type)
                if quality["quality_score"] != "good":
                    summary_flags.append({
                        "entity_id": e.id,
                        "entity_name": e.name,
                        **quality,
                    })
            if summary_flags:
                results["quality"]["summary_quality_flags"] = summary_flags
        except Exception:
            logger.warning("Summary quality flags check failed", exc_info=True)

    if check_type in ("all", "staleness", "document_consistency"):
        staleness_result = await _mcp.governance_service.run_staleness_check()
        staleness_warnings = staleness_result["warnings"]
        doc_consistency_warnings = staleness_result["document_consistency_warnings"]
        if check_type != "document_consistency":
            results["staleness"] = {
                "warnings": [_serialize(w) for w in staleness_warnings],
                "count": len(staleness_warnings),
                "document_consistency_warnings": doc_consistency_warnings,
                "document_consistency_count": len(doc_consistency_warnings),
            }
        if check_type == "document_consistency":
            results["document_consistency"] = {
                "document_consistency_warnings": doc_consistency_warnings,
                "document_consistency_count": len(doc_consistency_warnings),
            }

    if check_type in ("all", "blindspot"):
        blindspots = await _mcp.governance_service.run_blindspot_analysis()
        results["blindspots"] = {
            "blindspots": [_serialize(b) for b in blindspots],
            "count": len(blindspots),
        }
        try:
            task_signal_suggestions = await _mcp.governance_service.infer_blindspots_from_tasks()
            results["blindspots"]["task_signal_suggestions"] = task_signal_suggestions
            results["blindspots"]["task_signal_count"] = len(task_signal_suggestions)
        except Exception:
            logger.warning("Task signal blindspot inference failed", exc_info=True)
            results["blindspots"]["task_signal_suggestions"] = []
            results["blindspots"]["task_signal_count"] = 0

    if check_type == "impacts":
        try:
            validity_report = await _mcp.governance_service.check_impacts_target_validity()
            results.setdefault("quality", {})["l2_impacts_validity"] = _attach_impacts_repair_actions(validity_report)
        except Exception:
            logger.warning("Impacts target validity check failed (impacts check_type)", exc_info=True)

    if check_type in ("all", "permission_risk"):
        from zenos.application.identity.permission_risk_service import PermissionRiskService
        risk_svc = PermissionRiskService(
            entity_repo=_mcp.ontology_service._entities,
            task_repo=_mcp.task_service._tasks,
        )
        results["permission_risk"] = await risk_svc.analyze_risk()

    if check_type in ("all", "invalid_documents"):
        all_doc_entities = await _mcp.ontology_service._entities.list_all(type_filter="document")
        rel_repo = getattr(_mcp.ontology_service, "_relationships", None)
        rel_loader = getattr(rel_repo, "list_by_entity", None)
        relationships_by_doc: dict[str, list] = {}
        if rel_loader is not None:
            import inspect
            for doc in all_doc_entities:
                if not doc.id:
                    continue
                rel_result = rel_loader(doc.id)
                if inspect.isawaitable(rel_result):
                    rel_result = await rel_result
                relationships_by_doc[doc.id] = list(rel_result or [])
        scope_data = None
        if entity_id:
            all_entities_for_scope = await _mcp.ontology_service._entities.list_all()
            entity_map = {e.id: e for e in all_entities_for_scope if e.id}
            scope_root = entity_map.get(entity_id)
            if scope_root is None:
                return _error_response(
                    status="rejected",
                    error_code="NOT_FOUND",
                    message=_format_not_found("Entity", entity_id),
                )
            scope_ids = _collect_subtree_ids(entity_id, entity_map)
            all_doc_entities = [
                doc for doc in all_doc_entities
                if any(
                    linked_id in scope_ids
                    for linked_id in get_document_linked_entity_ids(
                        doc,
                        relationships_by_doc.get(doc.id or "", []),
                    )
                )
            ]
            scope_data = {
                "entity_id": scope_root.id,
                "entity_name": scope_root.name,
                "entity_type": scope_root.type,
                "mode": "subtree",
                "entity_count": len(scope_ids),
                "document_count": len(all_doc_entities),
            }
        invalid_docs = detect_invalid_document_titles(all_doc_entities)
        bundle_issues = detect_document_bundle_governance_issues(
            all_doc_entities,
            relationships_by_doc=relationships_by_doc,
        )
        doc_by_id = {doc.id: doc for doc in all_doc_entities if doc.id}
        entity_map_for_patches = locals().get("entity_map")
        if any(issue.get("issue_type") == "l2_missing_current_index_document" for issue in bundle_issues):
            if not isinstance(entity_map_for_patches, dict):
                all_entities_for_patches = await _mcp.ontology_service._entities.list_all()
                entity_map_for_patches = {
                    ent.id: ent for ent in all_entities_for_patches if ent.id
                }
        for issue in bundle_issues:
            patch = _build_document_bundle_repair_patch(
                issue,
                doc_by_id.get(str(issue.get("entity_id") or "")),
            )
            if patch is None and issue.get("issue_type") == "l2_missing_current_index_document":
                linked_entity_id = str(issue.get("linked_entity_id") or "")
                existing_docs = [
                    doc_by_id[doc_id]
                    for doc_id in issue.get("document_ids", [])
                    if doc_id in doc_by_id
                ]
                patch = _build_l2_index_create_patch(
                    issue,
                    entity_map_for_patches.get(linked_entity_id) if isinstance(entity_map_for_patches, dict) else None,
                    existing_docs,
                )
            if patch is not None:
                issue["suggested_write_patch"] = patch
        # Task 40: enrich each item with proposed_title and action
        from zenos.domain.source_uri_validator import GITHUB_BLOB_PATTERN
        for doc in invalid_docs:
            source_uri = doc["source_uri"]
            if source_uri and GITHUB_BLOB_PATTERN.match(source_uri):
                try:
                    from zenos.infrastructure.github_adapter import parse_github_url
                    _, _, path, _ = parse_github_url(source_uri)
                    proposed_title = path.rsplit("/", 1)[-1]
                except Exception:
                    proposed_title = None
                doc["proposed_title"] = proposed_title
                doc["action"] = "propose_title"
            elif not source_uri or not source_uri.startswith("http"):
                doc["proposed_title"] = None
                doc["action"] = "auto_archive"
            else:
                doc["proposed_title"] = None
                doc["action"] = "manual_review"
        results["invalid_documents"] = {
            "items": invalid_docs,
            "count": len(invalid_docs),
            "bundle_issues": sorted(bundle_issues, key=_bundle_issue_sort_key)[
                :_INVALID_DOCUMENT_BUNDLE_ISSUE_LIMIT
            ],
            "bundle_issue_count": len(bundle_issues),
            "bundle_issue_limit": _INVALID_DOCUMENT_BUNDLE_ISSUE_LIMIT,
            "bundle_issues_truncated": len(bundle_issues) > _INVALID_DOCUMENT_BUNDLE_ISSUE_LIMIT,
        }
        if scope_data is not None:
            results["invalid_documents"]["scope"] = scope_data

    if check_type in ("all", "orphaned_relationships"):
        try:
            orphan_result = await _mcp.ontology_service.remove_orphaned_relationships()
            results["orphaned_relationships"] = orphan_result
        except Exception:
            logger.warning("Orphaned relationships check failed", exc_info=True)

    if not results:
        return _error_response(
            status="rejected",
            error_code="INVALID_INPUT",
            message=(
                f"Unknown check_type '{check_type}'. "
                "Use: all, health, quality, staleness, blindspot, impacts, "
                "document_consistency, permission_risk, invalid_documents, "
                "orphaned_relationships, llm_health"
            ),
        )

    if check_type == "all":
        try:
            # ADR-020: delegate KPI computation to GovernanceService (single source of truth)
            health_signal = await _mcp.governance_service.compute_health_signal()
            kpi_data = health_signal.get("kpis", {})

            # Backward-compatible flat KPI format for existing consumers
            results["kpis"] = {
                "total_items": sum(
                    1 for _ in []  # placeholder — computed below
                ),
                "unconfirmed_items": 0,
                "unconfirmed_ratio": kpi_data.get("unconfirmed_ratio", {}).get("value", 0),
                "blindspot_total": kpi_data.get("blindspot_total", {}).get("value", 0),
                "duplicate_blindspots": 0,  # detail not tracked in health signal
                "duplicate_blindspot_rate": kpi_data.get("duplicate_blindspot_rate", {}).get("value", 0),
                "median_confirm_latency_days": kpi_data.get("median_confirm_latency_days", {}).get("value", 0),
                "active_l2_missing_impacts": kpi_data.get("active_l2_missing_impacts", {}).get("value", 0),
                "bundle_highlights_coverage": kpi_data.get("bundle_highlights_coverage", {}).get("value", 1.0),
                "weekly_review_required": (
                    kpi_data.get("quality_score", {}).get("value", 0) < 70
                    or kpi_data.get("active_l2_missing_impacts", {}).get("value", 0) > 0
                ),
            }
            # Enrich with health signal levels
            results["health_signal"] = health_signal
            if l2_repairs:
                results["governance_repairs"] = l2_repairs
        except Exception:
            # KPI should be additive; never break main governance checks.
            pass

    return _unified_response(data=results)
