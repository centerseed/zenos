"""MCP tool: write — create/update ontology entries."""

from __future__ import annotations

import logging
import inspect

from zenos.application.knowledge.ontology_service import DocumentLinkageValidationError, SnapshotTooLargeError
from zenos.domain.doc_types import is_known_doc_type
from zenos.domain.source_uri_validator import validate_source_uri
from zenos.infrastructure.github_adapter import GitHubAdapter
from zenos.infrastructure.context import current_partner_id
from zenos.infrastructure.sql_common import SCHEMA, get_pool

from zenos.domain.knowledge import EntityEntry
from zenos.infrastructure.context import (
    current_partner_department,
)

from zenos.interface.mcp._auth import _current_partner, _apply_workspace_override
from zenos.interface.mcp._common import (
    _serialize,
    _document_linkage_fields,
    _load_document_relationships,
    _new_id,
    _unified_response,
    _error_response,
    _build_governance_hints,
    _build_context_bundle,
    _enrich_task_result,
    _format_not_found,
)
from zenos.interface.mcp._visibility import (
    _check_write_visibility,
    _guest_write_rejection,
    _is_entity_visible,
)
from zenos.interface.mcp._audit import _audit_log
from zenos.interface.mcp._entry_quality import VALID_ENTRY_TYPES, entry_quality_issue

logger = logging.getLogger(__name__)

_PATCH_BATCH_MAX = 20
_DOCUMENT_REPAIR_PATCH_ALLOWED_FIELDS = {
    "id",
    "create_index_document",
    "title",
    "status",
    "doc_role",
    "linked_entity_ids",
    "sources",
    "add_source",
    "bundle_highlights",
    "summary",
    "change_summary",
    "tags",
    "details",
    "formal_entry",
}
_DOCUMENT_CREATE_SOURCE_PATCH_ALLOWED_FIELDS = {
    "source_id",
    "type",
    "uri",
    "label",
    "doc_type",
    "doc_status",
    "note",
    "is_primary",
    "retrieval_mode",
    "content_access",
}
_DOCUMENT_SOURCE_REPAIR_PATCH_ALLOWED_FIELDS = {
    "type",
    "uri",
    "label",
    "doc_type",
    "doc_status",
    "note",
    "is_primary",
    "retrieval_mode",
    "content_access",
}


def _document_contract_rejection(data: dict) -> dict | None:
    """Validate MCP-level document invariants before mutating metadata."""
    sources = data.get("sources")
    if isinstance(sources, list):
        primary_count = sum(1 for src in sources if isinstance(src, dict) and bool(src.get("is_primary")))
        if primary_count > 1:
            return _unified_response(
                status="rejected",
                data={"error": "MULTIPLE_PRIMARY_SOURCES"},
                rejection_reason="multiple primary sources are not allowed",
            )

    source_ids = {
        str(src.get("source_id")).strip()
        for src in (sources or [])
        if isinstance(src, dict) and src.get("source_id")
    }
    add_source = data.get("add_source")
    if isinstance(add_source, dict) and add_source.get("source_id"):
        source_ids.add(str(add_source["source_id"]).strip())
    update_source = data.get("update_source")
    if isinstance(update_source, dict) and update_source.get("source_id"):
        source_ids.add(str(update_source["source_id"]).strip())

    highlights = data.get("bundle_highlights")
    if highlights:
        if not isinstance(highlights, list):
            return _unified_response(
                status="rejected",
                data={"error": "INVALID_BUNDLE_HIGHLIGHTS"},
                rejection_reason="bundle_highlights must be a list",
            )
        has_primary = False
        for item in highlights:
            if not isinstance(item, dict):
                return _unified_response(
                    status="rejected",
                    data={"error": "INVALID_BUNDLE_HIGHLIGHTS"},
                    rejection_reason="bundle_highlights items must be objects",
                )
            if item.get("priority") == "primary":
                has_primary = True
            sid = str(item.get("source_id") or "").strip()
            if source_ids and sid and sid not in source_ids:
                return _unified_response(
                    status="rejected",
                    data={"error": "BUNDLE_HIGHLIGHT_SOURCE_NOT_FOUND", "source_id": sid},
                    rejection_reason="bundle_highlights source_id must belong to this document",
                )
        if not has_primary:
            return _unified_response(
                status="rejected",
                data={"error": "BUNDLE_HIGHLIGHTS_PRIMARY_REQUIRED"},
                rejection_reason="bundle_highlights requires at least one priority=primary item",
            )

    doc_role = str(data.get("doc_role") or "").strip()
    status = str(data.get("status") or "").strip()
    formal_entry = bool(data.get("formal_entry") or (isinstance(data.get("details"), dict) and data["details"].get("formal_entry")))
    if doc_role == "index" and status == "current" and formal_entry and not highlights:
        return _unified_response(
            status="rejected",
            data={"error": "CURRENT_INDEX_REQUIRES_PRIMARY_HIGHLIGHT"},
            suggestions=[{
                "type": "bundle_highlights_suggestion",
                "message": "current formal-entry index document requires bundle_highlights with priority=primary",
            }],
            rejection_reason="current index document requires bundle_highlights",
        )
    return None


def _validate_create_index_sources(
    patch_data: dict,
    *,
    doc_id: str,
    index: int,
) -> dict | None:
    sources = patch_data.get("sources")
    if not isinstance(sources, list) or not sources:
        return {"index": index, "reason": "patch_create_index_sources_required"}

    source_ids: set[str] = set()
    primary_count = 0
    for source_index, source in enumerate(sources):
        if not isinstance(source, dict):
            return {
                "index": index,
                "reason": "patch_create_index_source_must_be_object",
                "source_index": source_index,
            }
        disallowed = sorted(set(source) - _DOCUMENT_CREATE_SOURCE_PATCH_ALLOWED_FIELDS)
        if disallowed:
            return {
                "index": index,
                "reason": "patch_create_index_source_has_disallowed_fields",
                "source_index": source_index,
                "fields": disallowed,
            }
        if source.get("type") != "zenos_native":
            return {
                "index": index,
                "reason": "patch_create_index_source_must_be_zenos_native",
                "source_index": source_index,
            }
        expected_uri = f"/docs/{doc_id}"
        if source.get("uri") != expected_uri:
            return {
                "index": index,
                "reason": "patch_create_index_source_uri_must_match_document",
                "source_index": source_index,
                "expected_uri": expected_uri,
            }
        is_valid_uri, uri_error = validate_source_uri("zenos_native", str(source.get("uri") or ""))
        if not is_valid_uri:
            return {
                "index": index,
                "reason": "patch_create_index_source_invalid_uri",
                "source_index": source_index,
                "message": uri_error,
            }
        if source.get("is_primary") is True:
            primary_count += 1
        retrieval_mode = source.get("retrieval_mode")
        if retrieval_mode is not None and retrieval_mode not in {
            "direct",
            "snapshot",
            "per_user_live",
        }:
            return {
                "index": index,
                "reason": "patch_create_index_source_invalid_retrieval_mode",
                "source_index": source_index,
            }
        content_access = source.get("content_access")
        if content_access is not None and content_access not in {"summary", "full", "none"}:
            return {
                "index": index,
                "reason": "patch_create_index_source_invalid_content_access",
                "source_index": source_index,
            }
        doc_type = source.get("doc_type")
        if doc_type is not None and not is_known_doc_type(str(doc_type)):
            return {
                "index": index,
                "reason": "patch_create_index_source_invalid_doc_type",
                "source_index": source_index,
            }
        source_id = str(source.get("source_id") or "").strip()
        if not source_id:
            return {
                "index": index,
                "reason": "patch_create_index_source_id_required",
                "source_index": source_index,
            }
        source_ids.add(source_id)

    if primary_count != 1:
        return {
            "index": index,
            "reason": "patch_create_index_requires_one_primary_source",
        }

    highlights = patch_data.get("bundle_highlights")
    if not isinstance(highlights, list) or not highlights:
        return {"index": index, "reason": "patch_create_index_highlights_required"}
    if not any(isinstance(item, dict) and item.get("priority") == "primary" for item in highlights):
        return {"index": index, "reason": "patch_create_index_primary_highlight_required"}
    for highlight_index, item in enumerate(highlights):
        if not isinstance(item, dict):
            return {
                "index": index,
                "reason": "patch_create_index_highlight_must_be_object",
                "highlight_index": highlight_index,
            }
        source_id = str(item.get("source_id") or "").strip()
        if source_id and source_id not in source_ids:
            return {
                "index": index,
                "reason": "patch_create_index_highlight_source_id_not_found",
                "highlight_index": highlight_index,
            }
        if not str(item.get("headline") or "").strip():
            return {
                "index": index,
                "reason": "patch_create_index_highlight_headline_required",
                "highlight_index": highlight_index,
            }
        if not str(item.get("reason_to_read") or "").strip():
            return {
                "index": index,
                "reason": "patch_create_index_highlight_reason_required",
                "highlight_index": highlight_index,
            }
    return None


def _normalize_repair_patch(item: object) -> dict | None:
    if not isinstance(item, dict):
        return None
    suggested = item.get("suggested_write_patch")
    if isinstance(suggested, dict):
        return suggested
    return item


def _validate_document_repair_patch(item: object, index: int) -> tuple[dict | None, dict | None]:
    patch = _normalize_repair_patch(item)
    if not isinstance(patch, dict):
        return None, {"index": index, "reason": "patch_must_be_object"}

    if patch.get("tool") != "write":
        return None, {"index": index, "reason": "patch_tool_must_be_write"}
    if patch.get("collection") != "documents":
        return None, {"index": index, "reason": "patch_collection_must_be_documents"}
    if patch.get("needs_agent_review") is not True:
        return None, {"index": index, "reason": "patch_must_be_analyzer_reviewable"}

    patch_data = patch.get("data")
    if not isinstance(patch_data, dict):
        return None, {"index": index, "reason": "patch_data_must_be_object"}
    doc_id = str(patch_data.get("id") or "").strip()
    if not doc_id:
        return None, {"index": index, "reason": "patch_data_id_required"}

    disallowed = sorted(set(patch_data) - _DOCUMENT_REPAIR_PATCH_ALLOWED_FIELDS)
    if disallowed:
        return None, {
            "index": index,
            "reason": "patch_data_has_disallowed_fields",
            "fields": disallowed,
        }

    create_index_document = patch_data.get("create_index_document") is True
    if "sources" in patch_data and not create_index_document:
        return None, {"index": index, "reason": "patch_sources_only_allowed_for_index_create"}
    if create_index_document:
        if patch_data.get("doc_role") != "index":
            return None, {"index": index, "reason": "patch_create_index_doc_role_must_be_index"}
        if patch_data.get("status") != "current":
            return None, {"index": index, "reason": "patch_create_index_status_must_be_current"}
        linked_ids = patch_data.get("linked_entity_ids")
        if not isinstance(linked_ids, list) or not linked_ids:
            return None, {"index": index, "reason": "patch_create_index_linked_entity_ids_required"}
        for field in ("title", "summary", "change_summary", "tags"):
            if not patch_data.get(field):
                return None, {"index": index, "reason": f"patch_create_index_{field}_required"}
        source_error = _validate_create_index_sources(patch_data, doc_id=doc_id, index=index)
        if source_error is not None:
            return None, source_error

    add_source = patch_data.get("add_source")
    if add_source is not None:
        if not isinstance(add_source, dict):
            return None, {"index": index, "reason": "patch_add_source_must_be_object"}
        disallowed_source_fields = sorted(
            set(add_source) - _DOCUMENT_SOURCE_REPAIR_PATCH_ALLOWED_FIELDS
        )
        if disallowed_source_fields:
            return None, {
                "index": index,
                "reason": "patch_add_source_has_disallowed_fields",
                "fields": disallowed_source_fields,
            }
        if add_source.get("type") != "zenos_native":
            return None, {"index": index, "reason": "patch_add_source_must_be_zenos_native"}
        expected_uri = f"/docs/{doc_id}"
        if add_source.get("uri") != expected_uri:
            return None, {
                "index": index,
                "reason": "patch_add_source_uri_must_match_document",
                "expected_uri": expected_uri,
            }
        if add_source.get("is_primary") is not True:
            return None, {"index": index, "reason": "patch_add_source_must_be_primary"}
        retrieval_mode = add_source.get("retrieval_mode")
        if retrieval_mode is not None and retrieval_mode not in {
            "direct",
            "snapshot",
            "per_user_live",
        }:
            return None, {"index": index, "reason": "patch_add_source_invalid_retrieval_mode"}
        content_access = add_source.get("content_access")
        if content_access is not None and content_access not in {"summary", "full", "none"}:
            return None, {"index": index, "reason": "patch_add_source_invalid_content_access"}
        doc_type = add_source.get("doc_type")
        if doc_type is not None and not is_known_doc_type(str(doc_type)):
            return None, {"index": index, "reason": "patch_add_source_invalid_doc_type"}

    return {
        "tool": "write",
        "collection": "documents",
        "data": dict(patch_data),
        "needs_agent_review": True,
    }, None


def _validate_document_repair_patch_batch(data: dict) -> tuple[list[dict], list[dict]]:
    patches = data.get("patches")
    if not isinstance(patches, list):
        return [], [{"index": None, "reason": "patches_must_be_list"}]
    if not patches:
        return [], [{"index": None, "reason": "patches_must_not_be_empty"}]
    if len(patches) > _PATCH_BATCH_MAX:
        return [], [{
            "index": None,
            "reason": "patch_batch_too_large",
            "max_patches": _PATCH_BATCH_MAX,
            "received": len(patches),
        }]

    validated: list[dict] = []
    errors: list[dict] = []
    for index, item in enumerate(patches):
        patch, error = _validate_document_repair_patch(item, index)
        if error is not None:
            errors.append(error)
        elif patch is not None:
            validated.append(patch)
    return validated, errors


def _patch_batch_error_suggestions(errors: list[dict]) -> list[str]:
    suggestions: list[str] = []
    reasons = {str(error.get("reason") or "") for error in errors}
    if reasons & {
        "patch_must_be_object",
        "patch_tool_must_be_write",
        "patch_collection_must_be_documents",
        "patch_data_must_be_object",
        "patch_data_id_required",
    }:
        suggestions.append(
            "請直接傳 analyze 回傳的 suggested_write_patch；patch 必須是 tool=write、collection=documents，且 data.id 必填。"
        )
    if "patch_must_be_analyzer_reviewable" in reasons:
        suggestions.append(
            "請保留 analyze 回傳 patch 的 needs_agent_review=true；不要手動重組時漏掉這個欄位。"
        )
    if "patch_data_has_disallowed_fields" in reasons:
        suggestions.append(
            "patch.data 只能包含 analyzer repair 允許欄位；請直接使用 analyze 回傳的 suggested_write_patch。"
        )
    if "patches_must_be_list" in reasons or "patches_must_not_be_empty" in reasons:
        suggestions.append(
            "請用 data={dry_run=true, patches=[analyze 回傳的 suggested_write_patch, ...]} 先做 dry-run。"
        )
    if any(reason.startswith("patch_create_index_") for reason in reasons):
        suggestions.append(
            "create-index patch 只能使用 analyzer 產生的安全格式：current index、/docs/{doc_id} zenos_native primary source、對應 primary highlight。"
        )
    if any(reason.startswith("patch_add_source_") for reason in reasons):
        suggestions.append(
            "add_source repair patch 目前只允許 analyzer 產生的 zenos_native primary source；外部 Git/Drive/Notion source 請改走 write(collection='documents') 的人工更新路徑。"
        )
    return suggestions


def _snapshot_too_large_rejection(exc: SnapshotTooLargeError) -> dict:
    return _unified_response(
        status="rejected",
        data={
            "error": {
                "code": "SNAPSHOT_TOO_LARGE",
                "http_status": 413,
            },
        },
        rejection_reason=str(exc),
    )


def _document_linkage_rejection(exc: DocumentLinkageValidationError) -> dict:
    suggestions = []
    if exc.code == "LINKED_ENTITY_IDS_REQUIRED":
        suggestions.append("先用 search(collection='entities') 找到要掛載的 entity IDs")
    elif exc.code == "LINKED_ENTITY_NOT_FOUND":
        suggestions.append("請重新 search(collection='entities') 確認每個 linked_entity_id 都存在")

    data = {
        "error": {
            "code": exc.code,
        },
        "message": str(exc),
    }
    if exc.missing_entity_ids:
        data["error"]["missing_entity_ids"] = exc.missing_entity_ids

    return _unified_response(
        status="rejected",
        data=data,
        suggestions=suggestions,
        rejection_reason=str(exc),
    )


def _agent_friendly_entity_data(serialized: dict) -> dict:
    """Mirror core entity fields at data top-level while preserving data.entity."""
    entity = serialized.get("entity")
    if not isinstance(entity, dict):
        return serialized

    data = dict(serialized)
    for key in ("id", "name", "type", "level", "status", "parent_id"):
        if key in entity:
            data[key] = entity.get(key)
    if entity.get("id") is not None:
        data["entity_id"] = entity.get("id")
    if entity.get("name") is not None:
        data["entity_name"] = entity.get("name")
    return data


def _payload_explicit_formal_entry(data: dict) -> bool:
    if data.get("formal_entry") is not None:
        return bool(data.get("formal_entry"))
    details = data.get("details")
    if isinstance(details, dict) and details.get("formal_entry") is not None:
        return bool(details.get("formal_entry"))
    return False


def _payload_effective_status(data: dict) -> str:
    return str(data.get("status") or "current").strip().lower()


def _github_source_uris_from_payload(data: dict) -> list[str]:
    uris: list[str] = []

    source = data.get("source")
    if isinstance(source, dict) and str(source.get("type") or "").strip().lower() == "github":
        uri = str(source.get("uri") or "").strip()
        if uri:
            uris.append(uri)

    sources = data.get("sources")
    if isinstance(sources, list):
        for src in sources:
            if isinstance(src, dict) and str(src.get("type") or "").strip().lower() == "github":
                uri = str(src.get("uri") or "").strip()
                if uri:
                    uris.append(uri)

    for key in ("add_source", "update_source"):
        src = data.get(key)
        if isinstance(src, dict) and str(src.get("type") or "").strip().lower() == "github":
            uri = str(src.get("uri") or "").strip()
            if uri:
                uris.append(uri)

    deduped: list[str] = []
    seen: set[str] = set()
    for uri in uris:
        if uri not in seen:
            seen.add(uri)
            deduped.append(uri)
    return deduped


async def _check_github_source_remote_visibility(uri: str) -> tuple[bool, str, bool]:
    """Check whether a GitHub source is remotely readable.

    Returns:
        (is_visible, message, hard_failure)
        hard_failure=True means the source is definitively not shareable yet
        (e.g. 404 / permission denied / invalid URI) and current formal-entry
        writes should be rejected. Network/rate-limit uncertainty is soft.
    """
    try:
        await GitHubAdapter().read_content(uri)
        return True, "", False
    except FileNotFoundError:
        return False, f"GitHub source 尚未 remote 可見：{uri}", True
    except PermissionError:
        return False, f"GitHub source 目前無法被 ZenOS 讀取：{uri}", True
    except ValueError as exc:
        return False, f"GitHub source 無效：{exc}", True
    except RuntimeError as exc:
        return False, f"GitHub source remote 檢查暫時失敗：{exc}", False
    except Exception as exc:
        logger.warning("GitHub remote visibility check failed for %s", uri, exc_info=True)
        return False, f"GitHub source remote 檢查失敗：{exc}", False


async def _preflight_document_remote_visibility(data: dict) -> tuple[str | None, list[str]]:
    """Reject explicit current formal-entry GitHub docs when remote is unavailable."""
    if _payload_effective_status(data) != "current":
        return None, []
    if not _payload_explicit_formal_entry(data):
        return None, []

    warnings: list[str] = []
    for uri in _github_source_uris_from_payload(data):
        is_visible, message, hard_failure = await _check_github_source_remote_visibility(uri)
        if is_visible:
            continue
        if message:
            warnings.append(message)
        if hard_failure:
            return (
                "current formal-entry 文件的 GitHub source 尚未 remote 可見；請先 push，或改走 git + gcs 交付",
                warnings,
            )
    return None, warnings


def _looks_like_bundle_root_title(title: str) -> bool:
    lowered = (title or "").strip().lower()
    return any(token in lowered for token in ("知識庫", "索引", "index", "bundle", "文件群"))


async def _preflight_document_bundle_target(data: dict, ontology_service) -> dict | None:
    """Block raw uploaded files from becoming flat direct L2 document fanout."""
    if data.get("id") or data.get("sync_mode"):
        return None
    if data.get("add_source") or data.get("update_source") or data.get("remove_source"):
        return None
    if data.get("allow_l2_direct_document"):
        return None

    linked_ids = data.get("linked_entity_ids") or []
    try:
        linked_ids = ontology_service._normalize_linked_entity_ids(linked_ids)
    except Exception:
        return None
    if inspect.isawaitable(linked_ids):
        close = getattr(linked_ids, "close", None)
        if callable(close):
            close()
        return None
    if len(linked_ids) != 1:
        return None

    target_id = linked_ids[0]
    target = await ontology_service._entities.get_by_id(target_id)
    if target is None or str(getattr(target, "type", "")) != "module":
        return None

    title = str(data.get("title") or data.get("name") or "").strip()
    doc_role = str(data.get("doc_role") or "index").strip().lower()
    is_raw_file_upload = data.get("initial_content") is not None
    if doc_role == "index" and _looks_like_bundle_root_title(title):
        return None
    if not is_raw_file_upload and doc_role != "single":
        return None

    all_docs = await ontology_service._entities.list_all(type_filter="document")
    existing_indexes = [
        doc for doc in all_docs
        if getattr(doc, "parent_id", None) == target_id
        and str(getattr(doc, "doc_role", "") or "").lower() == "index"
        and str(getattr(doc, "status", "") or "").lower() == "current"
    ]
    if not existing_indexes:
        return None

    index_candidates = [
        {
            "id": doc.id,
            "title": doc.name,
        }
        for doc in existing_indexes[:8]
    ]
    return _unified_response(
        status="rejected",
        data={
            "error": {
                "code": "L2_DIRECT_DOCUMENT_REQUIRES_BUNDLE",
                "linked_entity_id": target_id,
                "linked_entity_name": target.name,
            },
            "index_candidates": index_candidates,
        },
        suggestions=[
            "這看起來是支援文件，不能再直接掛到 L2。請選一個既有 L3 index bundle，改用該 bundle 的 document id 做 parent/link。",
            "若你確定這份文件本身就是新的 L3 index 入口，title 請包含「知識庫」或「索引」，或明確傳 allow_l2_direct_document=true。",
        ],
        rejection_reason=(
            "raw/support document cannot be written directly under an L2 that already has current index bundles"
        ),
    )


def _is_formal_entry_document(serialized: dict) -> bool:
    details = serialized.get("details")
    if isinstance(details, dict) and details.get("formal_entry") is not None:
        return bool(details.get("formal_entry"))
    parent_id = str(serialized.get("parent_id") or "").strip()
    doc_role = str(serialized.get("doc_role") or "single").strip().lower()
    return bool(parent_id) and doc_role == "index"


async def _document_delivery_suggestions(serialized: dict) -> list[str]:
    """Return delivery-mode suggestions for current formal-entry docs."""
    doc_id = str(serialized.get("id") or "").strip()
    if not doc_id:
        return []
    partner = _current_partner.get()
    partner_id = str((partner or {}).get("id") or "").strip()
    if not partner_id:
        return []

    status = str(serialized.get("status") or "").strip().lower()
    sources = serialized.get("sources") or []
    has_github_source = any(
        isinstance(src, dict) and str(src.get("type") or "").strip().lower() == "github"
        for src in sources
    )
    is_formal_entry = _is_formal_entry_document(serialized)
    if status != "current" or not is_formal_entry:
        return []

    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            f"""
            SELECT primary_snapshot_revision_id, delivery_status
            FROM {SCHEMA}.entities
            WHERE partner_id = $1 AND id = $2
            """,
            partner_id,
            doc_id,
        )

    has_snapshot = bool(row and row["primary_snapshot_revision_id"])
    suggestions: list[str] = []
    if not has_snapshot:
        suggestions.append("current formal-entry 文件建議採 git + gcs；請補 delivery snapshot")
        if has_github_source:
            suggestions.append("GitHub source 若尚未 remote 可見，正式入口不得停在 git only")
    elif row and row["delivery_status"] == "stale":
        suggestions.append("delivery snapshot 目前為 stale；建議重新 publish current formal-entry 文件")
    return suggestions


async def _maybe_auto_publish_document(serialized: dict) -> list[str]:
    """Best-effort auto-publish for current formal-entry GitHub docs."""
    doc_id = str(serialized.get("id") or "").strip()
    if not doc_id:
        return []

    status = str(serialized.get("status") or "").strip().lower()
    sources = serialized.get("sources") or []
    has_github_source = any(
        isinstance(src, dict) and str(src.get("type") or "").strip().lower() == "github"
        for src in sources
    )
    is_formal_entry = _is_formal_entry_document(serialized)
    if status != "current" or not is_formal_entry or not has_github_source:
        return []

    partner = _current_partner.get()
    partner_id = current_partner_id.get() or str((partner or {}).get("id") or "").strip()
    if not partner_id:
        return []

    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            f"""
            SELECT primary_snapshot_revision_id
            FROM {SCHEMA}.entities
            WHERE partner_id = $1 AND id = $2
            """,
            partner_id,
            doc_id,
        )
    if row and row["primary_snapshot_revision_id"]:
        return []

    try:
        from zenos.interface.dashboard_api import _publish_document_snapshot_internal

        await _publish_document_snapshot_internal(effective_id=partner_id, doc_id=doc_id)
        return ["current formal-entry 文件已自動補上 delivery snapshot"]
    except Exception:
        logger.warning("Auto-publish failed for document %s", doc_id, exc_info=True)
        return ["current formal-entry 文件應採 git + gcs，但自動 publish 失敗；請檢查 GitHub source 是否已 push 並可讀"]


async def write(
    collection: str,
    data: dict,
    id: str | None = None,
    id_prefix: str | None = None,
    workspace_id: str | None = None,
    source: str | None = None,
) -> dict:
    """建立或更新 ontology 中的知識條目。

    當你需要記錄、更新或修改公司知識庫時用這個。
    根據 collection 參數決定寫入哪個集合，data 的格式因集合而異。

    使用時機：
    - 記錄新實體 → collection="entities"
    - 註冊文件 → collection="documents"
    - 建立 Protocol → collection="protocols"
    - 記錄盲點 → collection="blindspots"
    - 建立關係 → collection="relationships"
    - 記錄 entity 知識條目 → collection="entries"
    - 批次套用 analyze 產出的文件修復 patch → collection="patches"

    不要用這個工具的情境：
    - 管理任務（建立/更新） → 用 task
    - 確認 draft → 用 confirm
    - 分析 ontology 健康度 → 用 analyze

    各集合必填欄位：

    entities: name, type(product/module/goal/role/project/document), summary,
              tags({what, why, how, who})
              選填：parent_id（module 必須設為所屬 product 的 entity ID）
              選填：owner（負責人名稱，如 "Barry"）
              選填：sources([{uri, label, type}]) 或 append_sources（追加不覆蓋）
              選填：visibility（"public" | "restricted"，預設 public）
              選填：force（true 時可覆寫已確認 entity 的非空欄位）
              選填：consolidation_mode（"global" | "incremental"，標記 L2 建立時的統合模式）
              選填：layer_decision({q1_persistent, q2_cross_role, q3_company_consensus, impacts_draft})
                    — 新建 L2（type=module）時必填，除非 force=True
                    — 型別必須是 object（dict），不可傳 JSON 字串
                    — 三問（boolean）：
                      q1_persistent: bool — 持久性：是否為公司核心持久知識？（非臨時性、不隨 sprint 消失）
                      q2_cross_role: bool — 跨角色：是否跨角色共識？（不是某個人的個人筆記）
                      q3_company_consensus: bool — 全司共識：是否為經確認的公司知識？（在不同情境指向同一件事）
                    — impacts 門檻（三問全 true 後獨立驗證）：
                      impacts_draft: str | list[str] — 具體影響描述，格式「A 改了什麼 → B 的什麼要跟著看」（至少 1 條）
                    — 正確：
                      layer_decision={
                        "q1_persistent": true,
                        "q2_cross_role": true,
                        "q3_company_consensus": true,
                        "impacts_draft": "A 改了什麼→B 的什麼要跟著看"
                      }
                      layer_decision={
                        "q1_persistent": true,
                        "q2_cross_role": true,
                        "q3_company_consensus": true,
                        "impacts_draft": [
                          "A 改了什麼→B 的什麼要跟著看",
                          "C 改了什麼→D 的什麼要跟著看"
                        ]
                      }
                    — 錯誤（不要這樣傳）：
                      layer_decision="{\"q1_persistent\":true,...}"
    documents: title, source({type, uri, adapter}), tags({what[], why, how, who[]}),
               summary, linked_entity_ids（必填）。更新語意為 merge update（未提供欄位不清空）。
               linked_entity_ids canonical 格式為 list[str]，也接受 JSON array 字串（會正規化）。
               Bundle-first 硬規則：若 L2 已有 current doc_role=index 入口，
               支援文件/原始 md 不可再直接 linked 到該 L2；必須改掛正確 L3 index bundle。
               只有新的 bundle root（title 含「知識庫」/「索引」/index/bundle）
               或明確 allow_l2_direct_document=true 才允許直接掛 L2。
               選填：initial_content（string）— 建立新 doc 時同時把 markdown 寫進 GCS revision。
                 - 只支援 create（新建 doc）；update 既有 doc 請走 POST /api/docs/{doc_id}/content
                 - 與 sources 互斥（同時傳 → 400 INITIAL_CONTENT_REQUIRES_NO_SOURCES）
                 - 上限 1 MB（1048576 bytes）；超過 → 413 INITIAL_CONTENT_TOO_LARGE
                 - update 既有 doc_id 時傳入 → 400 INITIAL_CONTENT_CREATE_ONLY
                 - 成功時 response data 含 doc_id、revision_id、source_id
                 呼叫範例：
                   write(collection="documents", data={
                     "title": "FloraGLO® 研究文獻索引",
                     "type": "REFERENCE",
                     "doc_role": "index",
                     "linked_entity_ids": ["<L2 entity id>"],
                     "initial_content": "# FloraGLO® 研究文獻\n\n完整 markdown 內容..."
                   })
                   # response["data"] 含：
                   # { "doc_id": "abc123", "revision_id": "rev456", "source_id": "src789" }
                   # 建立後可直接呼叫 read_source(doc_id="abc123") 取得完整 markdown
               選填：material_change（bool）；當 true 時，change_summary 必填，否則視為未完成。
               可用 sync_mode 做文件治理批次同步：
                 - rename: 文件改名
                 - reclassify: 重新分類（改 tags/type）
                 - archive: 歸檔（標記為不再使用）
                 - supersede: 被新版取代
                 - sync_repair: 修復同步問題
               搭配 dry_run=true 可先預覽變更。
    patches: patches[{tool="write", collection="documents", data{...}, needs_agent_review=true}]
             只接受 analyze(check_type="invalid_documents") 產出的文件治理修復 patch。
             預設會實際套用；搭配 dry_run=true 只驗證不寫入。
    protocols: entity_id, entity_name, content({what, why, how, who})
    blindspots: description, severity(red/yellow/green), suggested_action
    relationships: source_entity_id, target_entity_id, type(depends_on/serves/
                   owned_by/part_of/blocks/related_to/impacts/enables), description
    entries: entity_id（必填）, type（必填）, content（必填：1-200 字元）
             選填：context（額外脈絡，最多 200 字元）, author, source_task_id
             type（必填）各類型區別：
               - decision: 團隊做出的決定（如「選用 PostgreSQL」）
               - insight: 發現的洞察（如「用戶主要在週末使用」）
               - limitation: 已知限制（如「API 不支援批量操作」）
               - change: 變更記錄（如「v2.0 移除了舊認證」）
               - context: 背景脈絡（如「此模組由外部團隊維護」）

             supersede 流程：
             1. 先建立新 entry（write collection="entries", data={entity_id, type, content, ...}）
             2. 拿到新 entry id 後，更新舊 entry 狀態：
                write collection="entries", id=<舊 entry id>,
                data={status="superseded", superseded_by=<新 entry id>}

    Args:
        collection: entities/documents/protocols/blindspots/relationships/entries/patches
        data: 集合對應的欄位（見上方說明）
        id: entries 更新 status 時提供既有 entry ID；其他集合新增時不提供
        workspace_id: 選填。切換到指定 workspace 執行寫入（必須在你的可用列表內）。
        source: 選填。批次 patch 來源標記；等同 data.source，方便 agent 傳遞 audit metadata。
    """
    from zenos.interface.mcp import _ensure_services
    import zenos.interface.mcp as _mcp

    if workspace_id:
        err = _apply_workspace_override(workspace_id)
        if err is not None:
            return err
    # AC-MIDE-05: write 絕對不支援 id_prefix — 防止 prefix 碰撞誤觸破壞性操作
    # Check BEFORE _ensure_services() so we never bootstrap SQL just to reject
    if id_prefix is not None:
        return _unified_response(
            status="rejected",
            data={"hint": "write 類操作需完整 32-char id，避免 prefix 碰撞誤觸破壞性操作"},
            rejection_reason="id_prefix_not_allowed_for_write_ops",
        )
    await _ensure_services()
    try:
        if id:
            data["id"] = id

        guest_rejection = _guest_write_rejection(collection)
        if guest_rejection is not None:
            return _unified_response(**guest_rejection)

        if collection == "entities":
            # --- Permission check: existing entity must be visible to caller ---
            existing_id = data.get("id")
            existing_name = data.get("name")
            existing_entity = None
            if existing_id:
                existing_entity = await _mcp.entity_repo.get_by_id(existing_id)
            elif existing_name:
                existing_entity = await _mcp.entity_repo.get_by_name(existing_name)
            if existing_entity:
                auth_error = _check_write_visibility(existing_entity, data)
                if auth_error:
                    return _error_response(
                        error_code=str(auth_error.get("error", "FORBIDDEN")),
                        message=str(auth_error.get("message", "Forbidden")),
                    )
                # Capture before-state for audit diff
                _before_visibility = {
                    "visibility": getattr(existing_entity, "visibility", "public"),
                    "visible_to_roles": list(getattr(existing_entity, "visible_to_roles", []) or []),
                    "visible_to_members": list(getattr(existing_entity, "visible_to_members", []) or []),
                    "visible_to_departments": list(getattr(existing_entity, "visible_to_departments", []) or []),
                }
            else:
                _before_visibility = None

            result = await _mcp.ontology_service.upsert_entity(data, partner=_current_partner.get())
            serialized = _serialize(result)
            entity_id = serialized.get("entity", {}).get("id")
            if entity_id:
                _mcp._schedule_embed(entity_id)

            # DF-20260419-L2d: L2 archive lifecycle warning. When a module is
            # moved to status=archived while it still has active entries,
            # surface the orphan-knowledge risk. Not a reject (deprecation
            # is sometimes intentional even with unresolved knowledge) but
            # the warning routes callers to consolidate/manual-archive first.
            _saved = result.entity if hasattr(result, "entity") else None
            if (
                _saved is not None
                and getattr(_saved, "type", None) == "module"
                and getattr(_saved, "status", None) == "archived"
                and entity_id
            ):
                try:
                    _orphan_entries = await _mcp.entry_repo.list_by_entity(
                        entity_id, status="active"
                    )
                except Exception:
                    _orphan_entries = []
                if _orphan_entries:
                    _count = len(_orphan_entries)
                    _orphan_warn = (
                        f"L2 '{_saved.name}' 已 archived，但仍有 {_count} 條 active entries。"
                        " 建議先跑 analyze(check_type='consolidate', entity_id=...) 或逐條手動 archive，"
                        "避免 orphan 知識殘留。"
                    )
                    if result.warnings is None:
                        result.warnings = [_orphan_warn]
                    else:
                        result.warnings.append(_orphan_warn)
            _audit_log(
                event_type="ontology.entity.upsert",
                target={"collection": collection, "id": entity_id},
                changes={"input": data},
                governance={"warnings": result.warnings or []},
            )
            context_bundle = await _build_context_bundle(
                linked_entity_ids=[entity_id] if entity_id else []
            )
            governance_hints = _build_governance_hints(
                warnings=result.warnings or [],
                similar_items=result.similar_items,
            )
            # --- Visibility change audit ---
            if _before_visibility is not None:
                result_entity = result.entity if hasattr(result, "entity") else None
                _after_visibility = {
                    "visibility": getattr(result_entity, "visibility", "public") if result_entity else data.get("visibility", "public"),
                    "visible_to_roles": list(getattr(result_entity, "visible_to_roles", []) or []) if result_entity else data.get("visible_to_roles", []),
                    "visible_to_members": list(getattr(result_entity, "visible_to_members", []) or []) if result_entity else data.get("visible_to_members", []),
                    "visible_to_departments": list(getattr(result_entity, "visible_to_departments", []) or []) if result_entity else data.get("visible_to_departments", []),
                }
                if _before_visibility != _after_visibility:
                    _audit_log(
                        event_type="governance.visibility.change",
                        target={"collection": collection, "id": entity_id},
                        changes={"before": _before_visibility, "after": _after_visibility},
                    )
            # Auto policy suggestion when visibility not specified
            policy_suggestion = None
            if "visibility" not in data:
                try:
                    from zenos.application.identity.policy_suggestion_service import PolicySuggestionService
                    _policy_svc = PolicySuggestionService(entity_repo=ontology_service._entities)
                    policy_suggestion = await _policy_svc.suggest(entity_id)
                except Exception:
                    pass  # never block write
            if policy_suggestion is not None:
                serialized["policy_suggestion"] = policy_suggestion
            response_data = _agent_friendly_entity_data(serialized)
            # Detect rejected fields and set response status accordingly
            _warnings = result.warnings or []
            _rejected = [w for w in _warnings if w.startswith("REJECTED_FIELDS:")]
            _resp_status = "ok"
            _rejection_reason = _rejected[0] if _rejected else None
            return _unified_response(
                status=_resp_status,
                data=response_data,
                warnings=_warnings,
                similar_items=result.similar_items or [],
                context_bundle=context_bundle,
                governance_hints=governance_hints,
                rejection_reason=_rejection_reason,
            )

        elif collection == "documents":
            # Backward compat: collection="documents" now creates entity(type="document")

            # --- initial_content validation (P0-5) ---
            initial_content = data.get("initial_content")
            if initial_content is not None:
                initial_content = str(initial_content)
                # AC-DNH-32: initial_content + sources are mutually exclusive
                if data.get("sources"):
                    return _unified_response(
                        status="rejected",
                        data={
                            "error": {
                                "code": "INITIAL_CONTENT_REQUIRES_NO_SOURCES",
                                "http_status": 400,
                            },
                            "message": (
                                "initial_content 與 sources 互斥：建立時只能二選一。"
                                " 若需要混合外部 source，請先建立 doc 再用 add_source 加入。"
                            ),
                        },
                        rejection_reason="initial_content_requires_no_sources",
                    )
                # AC-DNH-33: initial_content only allowed on create, not update
                if data.get("id"):
                    return _unified_response(
                        status="rejected",
                        data={
                            "error": {
                                "code": "INITIAL_CONTENT_CREATE_ONLY",
                                "http_status": 400,
                            },
                            "message": (
                                "initial_content 只能用於建立新文件，不可用於更新。"
                                " 若要更新既有文件的內容，請用 update_content 參數（需同時提供 id）"
                                " 或呼叫 POST /api/docs/{doc_id}/content。"
                            ),
                        },
                        rejection_reason="initial_content_create_only",
                    )
                # AC-DNH-31: size limit 1 MB
                if len(initial_content.encode("utf-8")) > 1_048_576:
                    return _unified_response(
                        status="rejected",
                        data={
                            "error": {
                                "code": "INITIAL_CONTENT_TOO_LARGE",
                                "http_status": 413,
                            },
                            "message": "initial_content 超過 1 MB 上限（1048576 bytes）。",
                        },
                        rejection_reason="initial_content_too_large",
                    )

            # --- update_content: write GCS revision for existing document ---
            update_content = data.get("update_content")
            if update_content is not None:
                update_content = str(update_content)
                if not data.get("id"):
                    return _unified_response(
                        status="rejected",
                        data={
                            "error": {
                                "code": "UPDATE_CONTENT_REQUIRES_ID",
                                "http_status": 400,
                            },
                            "message": (
                                "update_content 只能用於更新既有文件，必須同時提供 id。"
                                " 若要建立新文件並帶入內容，請用 initial_content（不需要帶 id）。"
                            ),
                        },
                        rejection_reason="update_content_requires_id",
                    )
                if len(update_content.encode("utf-8")) > 1_048_576:
                    return _unified_response(
                        status="rejected",
                        data={
                            "error": {
                                "code": "UPDATE_CONTENT_TOO_LARGE",
                                "http_status": 413,
                            },
                            "message": "update_content 超過 1 MB 上限（1048576 bytes）。",
                        },
                        rejection_reason="update_content_too_large",
                    )

            material_change = bool(data.get("material_change"))
            change_summary = str(data.get("change_summary") or "").strip()
            if material_change and not change_summary:
                return _unified_response(
                    status="rejected",
                    data={
                        "error": {
                            "code": "CHANGE_SUMMARY_REQUIRED",
                            "field": "change_summary",
                        },
                        "message": "material_change documents require change_summary",
                    },
                    rejection_reason="material_change_requires_change_summary",
                )
            contract_rejection = _document_contract_rejection(data)
            if contract_rejection is not None:
                return contract_rejection
            if data.get("sync_mode"):
                result = await _mcp.ontology_service.sync_document_governance(data)
                serialized = _serialize(result)
                _audit_log(
                    event_type="ontology.document.sync",
                    target={"collection": collection, "id": serialized.get("document_id")},
                    changes={"input": data},
                )
                return _unified_response(data=serialized)
            bundle_target_rejection = await _preflight_document_bundle_target(
                data,
                _mcp.ontology_service,
            )
            if bundle_target_rejection is not None:
                return bundle_target_rejection
            rejection_reason, preflight_warnings = await _preflight_document_remote_visibility(data)
            if rejection_reason is not None:
                return _unified_response(
                    status="rejected",
                    data={},
                    warnings=preflight_warnings,
                    suggestions=[
                        "請先把 GitHub source push 到 remote，再 capture current formal-entry 文件",
                        "若現在就需要讓別人讀，請改成 git + gcs 或直接補 delivery snapshot",
                    ],
                    governance_hints=_build_governance_hints(warnings=preflight_warnings),
                    rejection_reason=rejection_reason,
                )

            # --- AC-DNH-29: Prepare data for initial_content create path ---
            # Strip initial_content from data before upsert; inject zenos_native source.
            upsert_data = data
            if initial_content is not None:
                # We don't know doc_id yet; URI will be filled in after entity creation.
                # Inject a placeholder source; ontology_service normalises source_ids.
                upsert_data = {
                    k: v for k, v in data.items() if k != "initial_content"
                }
                # Override source to zenos_native (no GitHub validation needed)
                upsert_data["source"] = {
                    "type": "zenos_native",
                    "uri": "",  # placeholder; updated after entity creation
                    "label": data.get("title") or "ZenOS 原生文件",
                    "is_primary": True,
                    "source_status": "valid",
                    "status": "valid",
                }

            try:
                result = await _mcp.ontology_service.upsert_document(
                    upsert_data,
                    partner=_current_partner.get(),
                )
            except SnapshotTooLargeError as exc:
                return _snapshot_too_large_rejection(exc)
            except DocumentLinkageValidationError as exc:
                return _document_linkage_rejection(exc)
            serialized = _serialize(result)
            serialized.update(
                _document_linkage_fields(
                    result,
                    await _load_document_relationships(result.id),
                )
            )
            _audit_log(
                event_type="ontology.document.upsert",
                target={"collection": collection, "id": serialized.get("id")},
                changes={"input": data},
            )
            linked_ids = serialized.get("linked_entity_ids") or data.get("linked_entity_ids") or []
            # ADR-022: pick up bundle operation suggestions
            bundle_suggestions = getattr(result, "_bundle_suggestions", None) or []
            delivery_suggestions = await _document_delivery_suggestions(serialized)
            auto_publish_suggestions = await _maybe_auto_publish_document(serialized)

            # Helper Ingest Contract: noop detection + cross-doc duplicate warnings
            helper_meta = getattr(result, "_helper_upsert_meta", {}) or {}
            helper_warnings: list[str] = list(getattr(result, "_helper_warnings", None) or [])
            all_warnings = list(preflight_warnings or []) + helper_warnings
            resp_data = dict(serialized)
            if helper_meta.get("noop"):
                resp_data["noop"] = True

            # --- AC-DNH-29: GCS write for initial_content ---
            if initial_content is not None:
                doc_id_created = result.id
                # Resolve the source_id assigned during entity creation
                created_sources = getattr(result, "sources", None) or []
                native_src = next(
                    (s for s in created_sources if s.get("type") == "zenos_native"),
                    created_sources[0] if created_sources else {},
                )
                native_source_id = native_src.get("source_id")

                # Update the source URI to the canonical doc path now that we have doc_id
                native_uri = f"/docs/{doc_id_created}"
                try:
                    await _mcp.ontology_service.upsert_document(
                        {
                            "id": doc_id_created,
                            "linked_entity_ids": linked_ids or data.get("linked_entity_ids") or [],
                            "update_source": {
                                "source_id": native_source_id,
                                "uri": native_uri,
                            },
                        },
                        partner=_current_partner.get(),
                    )
                except Exception:
                    logger.warning(
                        "initial_content: failed to update zenos_native URI for doc %s",
                        doc_id_created,
                        exc_info=True,
                    )

                partner_id = current_partner_id.get() or str(
                    (_current_partner.get() or {}).get("id") or ""
                ).strip()
                revision_id_created: str | None = None
                delivery_status_native = "error"
                try:
                    from zenos.interface.dashboard_api import _write_native_snapshot
                    revision_id_created = await _write_native_snapshot(
                        partner_id=partner_id,
                        doc_id=doc_id_created,
                        source_id=native_source_id,
                        content=initial_content,
                    )
                    delivery_status_native = "ready"
                except Exception:
                    logger.error(
                        "initial_content: GCS write failed for doc %s",
                        doc_id_created,
                        exc_info=True,
                    )
                    _audit_log(
                        event_type="ontology.document.delivery_failure",
                        target={"collection": collection, "id": doc_id_created},
                        changes={"operation": "initial_content", "source_id": native_source_id},
                    )

                resp_data["doc_id"] = doc_id_created
                resp_data["source_id"] = native_source_id
                resp_data["revision_id"] = revision_id_created
                resp_data["delivery_status"] = delivery_status_native
                if delivery_status_native != "ready":
                    return _unified_response(
                        status="error",
                        data=resp_data,
                        warnings=[*all_warnings, "initial_content metadata was created but delivery snapshot failed"],
                        suggestions=[{
                            "type": "retry_delivery_snapshot",
                            "message": "retry write(initial_content=...) after fixing snapshot storage; do not treat this document as ready",
                        }],
                        governance_hints=_build_governance_hints(warnings=all_warnings),
                    )

            # --- update_content: GCS write for existing document ---
            if update_content is not None:
                doc_id_updated = result.id
                existing_sources = getattr(result, "sources", None) or []
                native_src = next(
                    (s for s in existing_sources if s.get("type") == "zenos_native"),
                    None,
                )
                # If no zenos_native source exists, add one
                if native_src is None:
                    native_uri = f"/docs/{doc_id_updated}"
                    try:
                        _updated = await _mcp.ontology_service.upsert_document(
                            {
                                "id": doc_id_updated,
                                "linked_entity_ids": linked_ids or [],
                                "add_source": {
                                    "type": "zenos_native",
                                    "uri": native_uri,
                                    "label": getattr(result, "title", None) or "ZenOS 原生文件",
                                    "is_primary": True,
                                    "source_status": "valid",
                                },
                            },
                            partner=_current_partner.get(),
                        )
                        native_src = next(
                            (s for s in (getattr(_updated, "sources", None) or [])
                             if s.get("type") == "zenos_native"),
                            None,
                        )
                    except Exception:
                        logger.warning(
                            "update_content: failed to add zenos_native source for doc %s",
                            doc_id_updated,
                            exc_info=True,
                        )
                native_source_id = (native_src or {}).get("source_id")
                partner_id = current_partner_id.get() or str(
                    (_current_partner.get() or {}).get("id") or ""
                ).strip()
                had_readable_revision = False
                snapshot_reader = getattr(_mcp.source_service, "read_source_with_snapshot", None)
                if snapshot_reader is not None and native_source_id:
                    try:
                        maybe = snapshot_reader(doc_id_updated, source_id=native_source_id, source_uri=f"/docs/{doc_id_updated}")
                        previous_snapshot = await maybe if inspect.isawaitable(maybe) else maybe
                        had_readable_revision = isinstance(previous_snapshot, dict) and bool(previous_snapshot.get("content"))
                    except Exception:
                        had_readable_revision = False
                revision_id_updated: str | None = None
                delivery_status_updated = "error"
                try:
                    from zenos.interface.dashboard_api import _write_native_snapshot
                    revision_id_updated = await _write_native_snapshot(
                        partner_id=partner_id,
                        doc_id=doc_id_updated,
                        source_id=native_source_id,
                        content=update_content,
                    )
                    delivery_status_updated = "ready"
                except Exception:
                    logger.error(
                        "update_content: GCS write failed for doc %s",
                        doc_id_updated,
                        exc_info=True,
                    )
                    _audit_log(
                        event_type="ontology.document.delivery_failure",
                        target={"collection": collection, "id": doc_id_updated},
                        changes={"operation": "update_content", "source_id": native_source_id},
                    )
                resp_data["doc_id"] = doc_id_updated
                resp_data["source_id"] = native_source_id
                resp_data["revision_id"] = revision_id_updated
                resp_data["delivery_status"] = delivery_status_updated
                if delivery_status_updated != "ready":
                    if had_readable_revision:
                        resp_data["delivery_status"] = "stale"
                        all_warnings.append("update_content snapshot failed; previous readable revision remains active")
                    else:
                        return _unified_response(
                            status="error",
                            data=resp_data,
                            warnings=[*all_warnings, "update_content failed and no previous readable revision was found"],
                            governance_hints=_build_governance_hints(warnings=all_warnings),
                        )

            return _unified_response(
                data=resp_data,
                warnings=all_warnings or None,
                suggestions=(bundle_suggestions + delivery_suggestions + auto_publish_suggestions) or None,
                context_bundle=await _build_context_bundle(linked_entity_ids=linked_ids),
                governance_hints=_build_governance_hints(warnings=all_warnings),
            )

        elif collection == "patches":
            validated, errors = _validate_document_repair_patch_batch(data)
            dry_run = bool(data.get("dry_run"))
            if errors:
                return _unified_response(
                    status="rejected",
                    data={
                        "dry_run": dry_run,
                        "validated_count": len(validated),
                        "errors": errors,
                    },
                    suggestions=_patch_batch_error_suggestions(errors) or None,
                    rejection_reason="invalid_patch_batch",
                )

            if dry_run:
                return _unified_response(
                    data={
                        "dry_run": True,
                        "validated_count": len(validated),
                        "patches": validated,
                    },
                    suggestions=["dry_run=true，未套用任何 patch；確認後可用 dry_run=false 批次套用。"],
                )

            applied: list[dict] = []
            rejected: list[dict] = []
            for index, patch in enumerate(validated):
                patch_data = dict(patch["data"])
                if patch_data.pop("create_index_document", False):
                    patch_data["allow_create_with_id"] = True
                result = await write(
                    collection="documents",
                    data=patch_data,
                    workspace_id=workspace_id,
                )
                row = {
                    "index": index,
                    "document_id": patch["data"].get("id"),
                    "status": result.get("status"),
                }
                if result.get("status") == "ok":
                    applied.append(row)
                else:
                    rejected.append({
                        **row,
                        "rejection_reason": result.get("rejection_reason"),
                        "data": result.get("data"),
                    })

            _audit_log(
                event_type="ontology.patch_batch.apply",
                target={"collection": "patches"},
                changes={
                    "source": source or data.get("source") or "manual",
                    "applied_count": len(applied),
                    "rejected_count": len(rejected),
                },
            )
            return _unified_response(
                status="ok",
                data={
                    "dry_run": False,
                    "applied_count": len(applied),
                    "rejected_count": len(rejected),
                    "applied": applied,
                    "rejected": rejected,
                    "partial_failures": rejected,
                },
                warnings=[
                    f"{len(rejected)} 個 patch 未套用，請查看 rejected"
                ] if rejected else None,
            )

        elif collection == "protocols":
            result = await _mcp.ontology_service.upsert_protocol(data)
            serialized = _serialize(result)
            _audit_log(
                event_type="ontology.protocol.upsert",
                target={"collection": collection, "id": serialized.get("id")},
                changes={"input": data},
            )
            return _unified_response(
                data=serialized,
                context_bundle=await _build_context_bundle(
                    linked_entity_ids=[serialized.get("entity_id")] if serialized.get("entity_id") else [],
                    protocol_id=serialized.get("id"),
                ),
                governance_hints=_build_governance_hints(),
            )

        elif collection == "blindspots":
            for eid in data.get("related_entity_ids", []) or []:
                entity = await _mcp.entity_repo.get_by_id(eid)
                if entity is None or not _is_entity_visible(entity):
                    return _unified_response(
                        status="rejected",
                        data={"error": "RELATED_ENTITY_NOT_VISIBLE", "entity_id": eid},
                        rejection_reason="related_entity_ids must exist and be visible",
                    )
            result = await _mcp.ontology_service.add_blindspot(data)
            serialized = _serialize(result)

            # Red blindspots auto-create a draft task for immediate attention
            if result.severity == "red":
                # Idempotency: avoid creating duplicate open tasks for same blindspot.
                _partner_ctx = _current_partner.get()
                effective_project = (
                    _partner_ctx.get("defaultProject", "") if _partner_ctx else ""
                )
                existing_tasks = await _mcp.task_service.list_tasks(
                    limit=200,
                    project=effective_project or None,
                )
                duplicate_open = next(
                    (
                        t
                        for t in existing_tasks
                        if t.linked_blindspot == result.id
                        and t.source_type == "blindspot"
                        and t.status not in {"done", "archived", "cancelled"}
                    ),
                    None,
                )
                if duplicate_open is not None:
                    _audit_log(
                        event_type="ontology.blindspot.upsert",
                        target={"collection": collection, "id": serialized.get("id")},
                        changes={"input": data},
                        governance={"auto_task": "skipped_existing_open"},
                    )
                    return _unified_response(
                        data={
                            **serialized,
                            "auto_created_task": _serialize(duplicate_open),
                            "auto_task_skipped": "EXISTING_OPEN_TASK",
                        },
                        suggestions=[{
                            "id": duplicate_open.id,
                            "title": duplicate_open.title,
                            "reason": "existing_open_task_for_blindspot",
                        }],
                        context_bundle=await _build_context_bundle(
                            linked_entity_ids=result.related_entity_ids,
                            blindspot_id=result.id,
                        ),
                        governance_hints=_build_governance_hints(
                            suggested_follow_up_tasks=[{
                                "id": duplicate_open.id,
                                "title": duplicate_open.title,
                                "reason": "existing_open_task_for_blindspot",
                            }]
                        ),
                    )

                # Infer assignee from related entities' who tag
                assignee = None
                auto_product_id = None
                for eid in (result.related_entity_ids or []):
                    entity = await _mcp.entity_repo.get_by_id(eid)
                    if entity and auto_product_id is None:
                        if getattr(entity, "type", None) == "product":
                            auto_product_id = entity.id
                        else:
                            auto_product_id = getattr(entity, "parent_id", None)
                    if entity and entity.tags.who:
                        who = entity.tags.who
                        if isinstance(who, list):
                            assignee = who[0] if who else None
                        else:
                            assignee = who
                        break

                creator_id = (_partner_ctx or {}).get("id") or "system"
                auto_task_data = {
                    "title": f"修復治理盲點：{result.description[:40]}",
                    "description": (
                        f"Blindspot: {result.description}\n\n"
                        f"Suggested action: {result.suggested_action}"
                    ),
                    "acceptance_criteria": [
                        "Root cause is identified and documented in task result.",
                        "Suggested action is implemented or a concrete follow-up task is linked.",
                        "Blindspot status can be moved toward acknowledged/resolved with evidence.",
                    ],
                    "source_type": "blindspot",
                    "source_metadata": {
                        "created_via_agent": True,
                        "agent_name": "system-auto",
                        "actor_partner_id": creator_id,
                    },
                    "linked_blindspot": result.id,
                    "linked_entities": result.related_entity_ids or [],
                    "product_id": auto_product_id,
                    "status": "todo",
                    "created_by": creator_id,
                    "updated_by": creator_id,
                    "assignee": assignee,
                }
                auto_task_result = await _mcp.task_service.create_task(auto_task_data)
                serialized["auto_created_task"] = _serialize(auto_task_result.task)

            _audit_log(
                event_type="ontology.blindspot.upsert",
                target={"collection": collection, "id": serialized.get("id")},
                changes={"input": data},
            )
            context_bundle = await _build_context_bundle(
                linked_entity_ids=result.related_entity_ids,
                blindspot_id=result.id,
            )
            follow_ups = []
            auto_created = serialized.get("auto_created_task")
            if isinstance(auto_created, dict):
                follow_ups.append({
                    "id": auto_created.get("id"),
                    "title": auto_created.get("title"),
                    "reason": "blindspot_requires_action",
                })
            return _unified_response(
                data=serialized,
                suggestions=follow_ups,
                context_bundle=context_bundle,
                governance_hints=_build_governance_hints(suggested_follow_up_tasks=follow_ups),
            )

        elif collection == "relationships":
            # Delete path: write(collection="relationships", id=<rel_id>,
            # data={"action": "delete", "reason": "..."}) removes a single
            # edge (used by governance cleanup to drop cross-subtree
            # auto-link contamination; DF-20260419-6 F14 fix).
            if id and data.get("action") == "delete":
                reason = data.get("reason") or "unspecified"
                rowcount = await _mcp.relationship_repo.remove_by_id(id)
                if rowcount == 0:
                    return _unified_response(
                        status="rejected",
                        data={},
                        rejection_reason=_format_not_found("Relationship", id),
                    )
                _audit_log(
                    event_type="ontology.relationship.delete",
                    target={"collection": collection, "id": id},
                    changes={"reason": reason},
                )
                return _unified_response(
                    data={"id": id, "deleted": True, "reason": reason},
                    governance_hints=_build_governance_hints(),
                )

            result = await _mcp.ontology_service.add_relationship(
                source_id=data["source_entity_id"],
                target_id=data["target_entity_id"],
                rel_type=data["type"],
                description=data["description"],
            )
            serialized = _serialize(result)
            _audit_log(
                event_type="ontology.relationship.upsert",
                target={"collection": collection, "id": serialized.get("id")},
                changes={"input": data},
            )
            return _unified_response(
                data=serialized,
                context_bundle=await _build_context_bundle(
                    linked_entity_ids=[data["source_entity_id"], data["target_entity_id"]],
                ),
                governance_hints=_build_governance_hints(),
            )

        elif collection == "entries":
            # Update status flow (e.g. supersede)
            if id:
                new_status = data.get("status")
                superseded_by = data.get("superseded_by")
                if not new_status:
                    return _unified_response(status="rejected", data={}, rejection_reason="entries 更新時 data 需提供 status")
                valid_statuses = {"active", "superseded", "archived"}
                if new_status not in valid_statuses:
                    return _unified_response(status="rejected", data={}, rejection_reason=f"status 必須是 {valid_statuses} 之一")
                if new_status == "superseded" and not superseded_by:
                    return _unified_response(status="rejected", data={}, rejection_reason="status=superseded 時必填 superseded_by")
                archive_reason = data.get("archive_reason")
                if new_status == "archived":
                    if not archive_reason:
                        return _unified_response(status="rejected", data={}, rejection_reason="status=archived 時必填 archive_reason")
                    if archive_reason not in ("merged", "manual"):
                        return _unified_response(status="rejected", data={}, rejection_reason="archive_reason 必須是 merged 或 manual")
                updated = await _mcp.entry_repo.update_status(id, new_status, superseded_by, archive_reason)
                if updated is None:
                    return _unified_response(
                        status="rejected",
                        data={},
                        rejection_reason=_format_not_found("Entry", id),
                    )
                serialized = _serialize(updated)
                return _unified_response(
                    data=serialized,
                    context_bundle=await _build_context_bundle(
                        linked_entity_ids=[serialized.get("entity_id")] if serialized.get("entity_id") else []
                    ),
                    governance_hints=_build_governance_hints(),
                )

            # Create new entry
            entity_id = data.get("entity_id")
            entry_type = data.get("type")
            content = data.get("content")
            if not entity_id or not entry_type or not content:
                return _unified_response(status="rejected", data={}, rejection_reason="entries 必填：entity_id, type, content")
            if not (1 <= len(content) <= 200):
                return _unified_response(status="rejected", data={}, rejection_reason="content 必須 1-200 字元")
            if entry_type not in VALID_ENTRY_TYPES:
                return _unified_response(status="rejected", data={}, rejection_reason=f"type 必須是 {VALID_ENTRY_TYPES} 之一")
            quality_issue = entry_quality_issue(content, entry_type)
            if quality_issue:
                return _unified_response(
                    status="rejected",
                    data={"error": "LOW_VALUE_ENTRY", "reason": quality_issue},
                    rejection_reason=(
                        "entry 應記錄 code/git log 讀不出的決策、限制、取捨或重要脈絡；"
                        f"目前內容被判定為 {quality_issue}"
                    ),
                    suggestions=[
                        "不要把 QA PASS、pytest、AC 通過、部署完成寫成 entry；這些留在 task result / journal / plan log。",
                        "改寫成可長期復用的原因、約束或決策邊界後再寫入。",
                    ],
                )
            context = data.get("context")
            if context and len(context) > 200:
                return _unified_response(status="rejected", data={}, rejection_reason="context 最多 200 字元")

            partner_ctx = _current_partner.get() or {}
            pid = partner_ctx.get("id", "")
            partner_department = str(partner_ctx.get("department") or current_partner_department.get() or "all")
            entry = EntityEntry(
                id=_new_id(),
                partner_id=pid,
                entity_id=entity_id,
                type=entry_type,
                content=content,
                context=context,
                author=data.get("author"),
                department=partner_department,
                source_task_id=data.get("source_task_id"),
            )
            result = await _mcp.entry_repo.create(entry)
            _audit_log(
                event_type="ontology.entry.create",
                target={"collection": collection, "id": result.id},
                changes={"input": data},
            )
            serialized = _serialize(result)
            active_count = await _mcp.entry_repo.count_active_by_entity(entity_id, department=partner_department)
            entry_warnings: list[str] = []
            if active_count >= 20:
                entry_warnings.append(
                    "此 entity 已達 20 條 active entries 上限，"
                    "建議執行 analyze(check_type='quality') 觸發歸納"
                )
            # ADR-020: entry saturation signal
            entry_saturation = {
                "active_count": active_count,
                "threshold": 20,
                "level": "red" if active_count >= 20 else ("yellow" if active_count >= 15 else "green"),
            }
            return _unified_response(
                data=serialized,
                warnings=entry_warnings,
                context_bundle=await _build_context_bundle(linked_entity_ids=[entity_id]),
                governance_hints=_build_governance_hints(
                    warnings=entry_warnings,
                    health_signal={"entry_saturation": entry_saturation},
                ),
            )

        else:
            return _unified_response(
                status="rejected",
                data={},
                rejection_reason=(
                    f"Unknown collection '{collection}'. "
                    f"Use: entities, documents, protocols, blindspots, relationships, entries, patches"
                ),
            )
    except PermissionError as e:
        return _unified_response(
            status="rejected",
            data={},
            rejection_reason=f"FORBIDDEN: {e}",
        )
    except (ValueError, KeyError, TypeError) as e:
        return _unified_response(status="rejected", data={}, rejection_reason=str(e))
