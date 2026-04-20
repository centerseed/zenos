"""MCP tool: recent_updates — recent change surfacing."""

from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone

from zenos.application.knowledge.ontology_service import _collect_subtree_ids
from zenos.domain.knowledge import Entity
from zenos.infrastructure.context import current_partner_id as _current_partner_id

from zenos.interface.mcp._auth import _apply_workspace_override
from zenos.interface.mcp._audit import _schedule_tool_event
from zenos.interface.mcp._common import _error_response, _serialize, _unified_response

logger = logging.getLogger(__name__)

_DEFAULT_RECENT_WINDOW_DAYS = 14
_DEFAULT_LIMIT = 20
_MAX_LIMIT = 50


def _normalize_text(value: object | None) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return " ".join(_normalize_text(item) for item in value if item is not None)
    if isinstance(value, dict):
        return " ".join(_normalize_text(item) for item in value.values() if item is not None)
    return str(value)


def _parse_since(since: str | None, since_days: int | None) -> datetime:
    """Parse the recent window into an aware UTC datetime."""
    now = datetime.now(timezone.utc)
    if since:
        value = since.strip()
        if re.fullmatch(r"\d+d", value.lower()):
            days = int(value[:-1])
            return now - timedelta(days=days)
        normalized = value.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(normalized)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    days = since_days if since_days is not None else _DEFAULT_RECENT_WINDOW_DAYS
    return now - timedelta(days=max(0, days))


def _normalize_limit(limit: int | None) -> int:
    if limit is None:
        return _DEFAULT_LIMIT
    return max(1, min(int(limit), _MAX_LIMIT))


def _topic_match(topic: str | None, fields: dict[str, object | None]) -> tuple[bool, list[str]]:
    normalized = (topic or "").strip().lower()
    if not normalized:
        return True, []
    matched_fields: list[str] = []
    for field_name, value in fields.items():
        haystack = _normalize_text(value).lower()
        if haystack and normalized in haystack:
            matched_fields.append(field_name)
    return bool(matched_fields), matched_fields


def _entry_text_blob(entry: dict, entity_dict: dict | None = None, parent_dict: dict | None = None) -> dict[str, object | None]:
    return {
        "content": entry.get("content"),
        "context": entry.get("context"),
        "entity_name": (entity_dict or {}).get("name"),
        "entity_summary": (entity_dict or {}).get("summary"),
        "entity_tags": (entity_dict or {}).get("tags"),
        "parent_name": (parent_dict or {}).get("name"),
        "parent_summary": (parent_dict or {}).get("summary"),
    }


def _entity_text_blob(entity: dict, parent_dict: dict | None = None) -> dict[str, object | None]:
    return {
        "name": entity.get("name"),
        "summary": entity.get("summary"),
        "change_summary": entity.get("change_summary"),
        "type": entity.get("type"),
        "tags": entity.get("tags"),
        "parent_name": (parent_dict or {}).get("name"),
        "parent_summary": (parent_dict or {}).get("summary"),
    }


def _why_document_change(doc: dict, related_entity_names: list[str], topic: str | None, has_entry_pair: bool) -> str:
    title = str(doc.get("name") or doc.get("title") or "document").strip()
    if related_entity_names:
        related = ", ".join(related_entity_names)
    else:
        related = "related downstream work"
    if has_entry_pair:
        return f"{title} 這次的文件與 change entry 已對齊，會影響 {related} 的後續作業。"
    if topic:
        return f"{title} 的變更和主題 {topic} 有關，請確認 {related} 是否需要同步。"
    return f"{title} 有新的變更摘要，請留意 {related} 是否受影響。"


def _why_entity_change(entity_name: str, topic: str | None, source: str = "entry") -> str:
    if topic:
        return f"{entity_name} 的變更對主題 {topic} 有直接影響，後續作業要跟著改。"
    if source == "journal":
        return "只有 journal 證據，知識層缺口仍存在，請補齊 change_summary 或 change entry。"
    return f"{entity_name} 的做法已更新，後續工作要以這筆 change entry 為準。"


def _as_iso(dt: object) -> str:
    if isinstance(dt, datetime):
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc).isoformat()
        return dt.astimezone(timezone.utc).isoformat()
    if hasattr(dt, "isoformat"):
        return dt.isoformat()  # type: ignore[no-any-return]
    return str(dt)


def _parse_dt(value: object | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc) if value.tzinfo else value.replace(tzinfo=timezone.utc)
    text = str(value).strip()
    if not text:
        return None
    parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    return parsed.astimezone(timezone.utc) if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _change_summary_requires_presence(is_material_change: bool, change_summary: str | None) -> bool:
    """Contract helper for AC-RCS-01/03 style rules."""
    if not is_material_change:
        return True
    return bool((change_summary or "").strip())


def _non_material_change_keeps_existing_summary(
    existing_change_summary: str | None,
    incoming_change_summary: str | None,
    is_non_material_change: bool,
) -> str | None:
    """Contract helper for AC-RCS-02."""
    if is_non_material_change and not (incoming_change_summary or "").strip():
        return existing_change_summary
    return incoming_change_summary or existing_change_summary


def _resolve_summary_updated_at(
    incoming_change_summary: str | None,
    existing_summary_updated_at: datetime | None,
    now: datetime,
) -> datetime | None:
    """Contract helper for AC-RCS-01/02 timestamp behavior."""
    if (incoming_change_summary or "").strip():
        return now
    return existing_summary_updated_at


def _bundle_operation_is_complete(is_material_change: bool, change_summary: str | None) -> bool:
    """Contract helper for AC-RCS-03."""
    return _change_summary_requires_presence(is_material_change, change_summary)


def _should_emit_change_entry(impacts_l2: bool, l3_only: bool) -> bool:
    """Contract helper for AC-RCS-04/05."""
    return impacts_l2 and not l3_only


def _build_change_entry_content(
    change_summary: str,
    impacted_concept: str,
    audience: str,
) -> str:
    """Contract helper for AC-RCS-06."""
    content = f"{impacted_concept} 已更新：{change_summary}。"
    if audience:
        content += f" 受影響的是 {audience}。"
    return content[:200]


async def recent_updates(
    product: str | None = None,
    product_id: str | None = None,
    since: str | None = None,
    since_days: int | None = None,
    topic: str | None = None,
    limit: int = _DEFAULT_LIMIT,
    workspace_id: str | None = None,
) -> dict:
    """Return a curated recent-change view for a product or the whole workspace."""
    from zenos.interface.mcp import _ensure_journal_repo, _ensure_services
    import zenos.interface.mcp as _mcp

    if workspace_id:
        err = _apply_workspace_override(workspace_id)
        if err is not None:
            return err

    await _ensure_services()

    partner_id = _current_partner_id.get()
    if not partner_id:
        return _unified_response(
            status="rejected",
            data={},
            rejection_reason="No authenticated partner context",
        )

    limit_value = _normalize_limit(limit)
    cutoff = _parse_since(since, since_days)
    normalized_topic = (topic or "").strip().lower() or None

    entity_repo = _mcp.entity_repo
    entry_repo = _mcp.entry_repo
    if entity_repo is None or entry_repo is None:
        return _error_response(
            error_code="SERVICE_UNAVAILABLE",
            message="knowledge repositories are not initialized",
        )

    all_entities = await entity_repo.list_all()
    entity_map: dict[str, Entity] = {e.id: e for e in all_entities if e.id}

    scope_root: Entity | None = None
    scope_label = "workspace"
    scope_entity_ids: set[str] = set(entity_map)
    if product:
        scope_root = await entity_repo.get_by_name(product)
    elif product_id:
        scope_root = await entity_repo.get_by_id(product_id)

    if (product or product_id) and scope_root is None:
        return _unified_response(
            status="rejected",
            data={},
            rejection_reason="recent_updates product scope not found",
        )

    if scope_root is not None:
        if scope_root.type != "product" and (scope_root.level or 0) != 1:
            return _unified_response(
                status="rejected",
                data={},
                rejection_reason="recent_updates product scope must resolve to a product entity",
            )
        if not scope_root.id:
            return _unified_response(
                status="rejected",
                data={},
                rejection_reason="recent_updates product scope is missing an entity id",
            )
        scope_entity_ids = _collect_subtree_ids(scope_root.id, entity_map)
        scope_label = scope_root.name

    entity_by_id = {eid: _serialize(ent) for eid, ent in entity_map.items()}
    parent_names = {
        eid: entity_map[eid].name
        for eid in entity_map
    }

    def _entity_in_scope(entity_id: str | None) -> bool:
        return bool(entity_id and entity_id in scope_entity_ids)

    def _document_result(entity: dict) -> dict | None:
        entity_id = str(entity.get("id") or "")
        if not entity_id or not _entity_in_scope(entity_id):
            return None
        if not (entity.get("change_summary") or "").strip():
            return None
        updated_dt = _parse_dt(entity.get("summary_updated_at") or entity.get("updated_at"))
        if updated_dt is None:
            return None
        if updated_dt < cutoff:
            return None

        parent_id = entity.get("parent_id")
        parent_dict = entity_by_id.get(parent_id) if parent_id else None
        topic_ok, matched_fields = _topic_match(normalized_topic, _entity_text_blob(entity, parent_dict))
        if not topic_ok:
            return None

        related_entity_ids = [parent_id] if parent_id else [entity_id]
        related_entity_names = [
            parent_names[rid] for rid in related_entity_ids if rid and rid in parent_names
        ]
        return {
            "kind": "document_change",
            "title": entity.get("name") or entity.get("title") or entity_id,
            "updated_at": _as_iso(updated_dt),
            "topic_match": {
                "query": topic,
                "matched": topic_ok,
                "matched_fields": matched_fields,
            },
            "change_summary": entity.get("change_summary"),
            "why_it_matters": _why_document_change(entity, related_entity_names, topic, False),
            "related_entity_ids": related_entity_ids,
            "related_entity_names": related_entity_names,
            "primary_entity_id": entity_id,
            "source": "document.change_summary",
            "governance_gap": False,
            "related_change_entries": [],
        }

    doc_results = []
    for entity in entity_by_id.values():
        if entity.get("type") != "document":
            continue
        result = _document_result(entity)
        if result is not None:
            doc_results.append(result)

    entry_results = []
    entry_candidates: list[dict]
    if normalized_topic:
        search_limit = max(limit_value * 10, 50)
        raw_hits = await entry_repo.search_content(
            normalized_topic,
            limit=search_limit,
            department=None,
        )
        entry_candidates = []
        for hit in raw_hits:
            entry = hit.get("entry")
            if entry is None:
                continue
            entry_candidates.append(
                {
                    "entry": _serialize(entry),
                    "entity_name": hit.get("entity_name"),
                }
            )
    else:
        entry_candidates = []
        for entity_id in sorted(scope_entity_ids):
            raw_entries = await entry_repo.list_by_entity(entity_id, status="active", department=None)
            for entry in raw_entries:
                entry_candidates.append({"entry": _serialize(entry), "entity_name": entity_by_id.get(entity_id, {}).get("name")})

    for candidate in entry_candidates:
        entry = candidate["entry"]
        if entry.get("type") != "change":
            continue
        if str(entry.get("status") or "active") != "active":
            continue
        entity_id = str(entry.get("entity_id") or "")
        if not _entity_in_scope(entity_id):
            continue
        created_dt = _parse_dt(entry.get("created_at"))
        if created_dt is None:
            continue
        if created_dt < cutoff:
            continue

        entity_dict = entity_by_id.get(entity_id)
        parent_dict = entity_by_id.get(entity_dict.get("parent_id")) if entity_dict and entity_dict.get("parent_id") else None
        topic_ok, matched_fields = _topic_match(normalized_topic, _entry_text_blob(entry, entity_dict, parent_dict))
        if not topic_ok:
            continue

        entity_name = candidate.get("entity_name") or (entity_dict or {}).get("name") or entity_id
        entry_results.append(
            {
                "kind": "entity_change",
                "title": entity_name,
                "updated_at": _as_iso(created_dt),
                "topic_match": {
                    "query": topic,
                    "matched": topic_ok,
                    "matched_fields": matched_fields,
                },
                "content": entry.get("content"),
                "why_it_matters": _why_entity_change(entity_name, topic),
                "related_entity_ids": [entity_id],
                "entity_id": entity_id,
                "entry_type": entry.get("type"),
                "source": "entry(type=change)",
                "governance_gap": False,
            }
        )

    # Group entries onto the nearest matching document change when the same
    # downstream concept already has a document-level change summary.
    consumed_entry_indices: set[int] = set()
    for doc_idx, doc in enumerate(doc_results):
        doc_related_ids = {
            rid for rid in doc.get("related_entity_ids", []) if rid
        }
        matching_entry_indexes = [
            idx for idx, entry in enumerate(entry_results)
            if idx not in consumed_entry_indices and doc_related_ids.intersection(entry.get("related_entity_ids", []))
        ]
        if not matching_entry_indexes:
            continue
        related_entries = [entry_results[idx] for idx in matching_entry_indexes]
        consumed_entry_indices.update(matching_entry_indexes)
        doc["related_change_entries"] = related_entries
        doc_related_ids.update(
            rid for entry in related_entries for rid in entry.get("related_entity_ids", []) if rid
        )
        doc["related_entity_ids"] = sorted(doc_related_ids)
        related_names = [parent_names[rid] for rid in doc["related_entity_ids"] if rid in parent_names]
        doc["why_it_matters"] = _why_document_change(
            doc=entity_by_id.get(doc["primary_entity_id"], {}),
            related_entity_names=related_names,
            topic=topic,
            has_entry_pair=True,
        )
        doc_dt = _parse_dt(doc["updated_at"])
        if doc_dt is None:
            continue
        latest_related_dt = max(
            [doc_dt]
            + [dt for dt in (_parse_dt(entry["updated_at"]) for entry in related_entries) if dt is not None]
        )
        doc["updated_at"] = latest_related_dt.astimezone(timezone.utc).isoformat()

    remaining_entry_results = [
        entry for idx, entry in enumerate(entry_results)
        if idx not in consumed_entry_indices
    ]

    results = doc_results + remaining_entry_results
    results.sort(
        key=lambda item: datetime.fromisoformat(str(item["updated_at"]).replace("Z", "+00:00")),
        reverse=True,
    )
    results = results[:limit_value]

    fallback_used = False
    governance_gap = False
    if not results:
        from zenos.interface.mcp import _ensure_journal_repo

        await _ensure_journal_repo()
        journal_repo = _mcp._journal_repo
        if journal_repo is not None:
            journal_entries, _total = await journal_repo.list_recent(
                partner_id=partner_id,
                limit=limit_value,
                project=scope_label if scope_label != "workspace" else None,
                flow_type=None,
            )
            journal_results = []
            for journal in journal_entries:
                summary = str(journal.get("summary") or "").strip()
                if not summary:
                    continue
                if normalized_topic and normalized_topic not in summary.lower():
                    tags = _normalize_text(journal.get("tags")).lower()
                    if normalized_topic not in tags:
                        continue
                created_at = journal.get("created_at")
                created_dt = created_at if isinstance(created_at, datetime) else None
                if created_dt is None:
                    continue
                journal_results.append(
                    {
                        "kind": "entity_change",
                        "title": summary[:80],
                        "updated_at": _as_iso(created_dt),
                        "topic_match": {
                            "query": topic,
                            "matched": True,
                            "matched_fields": ["journal"],
                        },
                        "content": summary,
                        "why_it_matters": _why_entity_change(scope_label, topic, source="journal"),
                        "related_entity_ids": [scope_root.id] if scope_root and scope_root.id else [],
                        "entity_id": scope_root.id if scope_root and scope_root.id else None,
                        "entry_type": "journal",
                        "source": "journal",
                        "governance_gap": True,
                        "fallback_used": True,
                    }
                )
            results = journal_results[:limit_value]
            fallback_used = bool(results)
            governance_gap = bool(results)

    for item in results:
        _schedule_tool_event(
            "recent_updates",
            item.get("primary_entity_id") or item.get("entity_id"),
            topic or product or product_id,
            len(results),
        )

    return _unified_response(
        data={
            "scope": {
                "product": product,
                "product_id": product_id,
                "resolved_product": scope_root.name if scope_root else None,
            },
            "since": cutoff.astimezone(timezone.utc).isoformat(),
            "topic": topic,
            "limit": limit_value,
            "count": len(results),
            "fallback_used": fallback_used,
            "governance_gap": governance_gap,
            "results": results,
        },
        completeness="partial" if len(results) >= limit_value else "exhaustive",
    )
