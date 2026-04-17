"""MCP tool: write — create/update ontology entries."""

from __future__ import annotations

import logging

from zenos.application.knowledge.ontology_service import DocumentLinkageValidationError
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
    _new_id,
    _unified_response,
    _error_response,
    _build_governance_hints,
    _build_context_bundle,
    _enrich_task_result,
)
from zenos.interface.mcp._visibility import (
    _check_write_visibility,
    _guest_write_rejection,
)
from zenos.interface.mcp._audit import _audit_log

logger = logging.getLogger(__name__)


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
    workspace_id: str | None = None,
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
               可用 sync_mode 做文件治理批次同步：
                 - rename: 文件改名
                 - reclassify: 重新分類（改 tags/type）
                 - archive: 歸檔（標記為不再使用）
                 - supersede: 被新版取代
                 - sync_repair: 修復同步問題
               搭配 dry_run=true 可先預覽變更。
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
        collection: entities/documents/protocols/blindspots/relationships/entries
        data: 集合對應的欄位（見上方說明）
        id: entries 更新 status 時提供既有 entry ID；其他集合新增時不提供
        workspace_id: 選填。切換到指定 workspace 執行寫入（必須在你的可用列表內）。
    """
    from zenos.interface.mcp import _ensure_services
    import zenos.interface.mcp as _mcp

    if workspace_id:
        err = _apply_workspace_override(workspace_id)
        if err is not None:
            return err
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
            # Detect rejected fields and set response status accordingly
            _warnings = result.warnings or []
            _rejected = [w for w in _warnings if w.startswith("REJECTED_FIELDS:")]
            _resp_status = "partial" if _rejected else "ok"
            _rejection_reason = _rejected[0] if _rejected else None
            return _unified_response(
                status=_resp_status,
                data=serialized,
                warnings=_warnings,
                similar_items=result.similar_items or [],
                context_bundle=context_bundle,
                governance_hints=governance_hints,
                rejection_reason=_rejection_reason,
            )

        elif collection == "documents":
            # Backward compat: collection="documents" now creates entity(type="document")
            if data.get("sync_mode"):
                result = await _mcp.ontology_service.sync_document_governance(data)
                serialized = _serialize(result)
                _audit_log(
                    event_type="ontology.document.sync",
                    target={"collection": collection, "id": serialized.get("document_id")},
                    changes={"input": data},
                )
                return _unified_response(data=serialized)
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
            try:
                result = await _mcp.ontology_service.upsert_document(
                    data,
                    partner=_current_partner.get(),
                )
            except DocumentLinkageValidationError as exc:
                return _document_linkage_rejection(exc)
            serialized = _serialize(result)
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
            return _unified_response(
                data=serialized,
                warnings=preflight_warnings or None,
                suggestions=(bundle_suggestions + delivery_suggestions + auto_publish_suggestions) or None,
                context_bundle=await _build_context_bundle(linked_entity_ids=linked_ids),
                governance_hints=_build_governance_hints(warnings=preflight_warnings),
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
                for eid in (result.related_entity_ids or []):
                    entity = await _mcp.entity_repo.get_by_id(eid)
                    if entity and entity.tags.who:
                        who = entity.tags.who
                        if isinstance(who, list):
                            assignee = who[0] if who else None
                        else:
                            assignee = who
                        break

                creator_id = (_partner_ctx or {}).get("id") or "system"
                auto_task_data = {
                    "title": f"處理盲點：{result.description[:30]}",
                    "source_type": "blindspot",
                    "source_metadata": {
                        "created_via_agent": True,
                        "agent_name": "system-auto",
                        "actor_partner_id": creator_id,
                    },
                    "linked_blindspot": result.id,
                    "linked_entities": result.related_entity_ids or [],
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
            result = await _mcp.ontology_service.add_relationship(
                source_id=data["source_entity_id"],
                target_id=data["target_entity_id"],
                rel_type=data["type"],
                description=data["description"],
                verb=data.get("verb"),
            )
            serialized = _serialize(result)
            _audit_log(
                event_type="ontology.relationship.upsert",
                target={"collection": collection, "id": serialized.get("id")},
                changes={"input": data},
            )
            # Suggest verbs when caller did not provide one
            if result.verb is None and _mcp.governance_service is not None:
                src_entity = await _mcp.entity_repo.get_by_id(data["source_entity_id"])
                tgt_entity = await _mcp.entity_repo.get_by_id(data["target_entity_id"])
                if src_entity is not None and tgt_entity is not None:
                    suggested_verbs = await _mcp.governance_service.suggest_relationship_verb(
                        src_entity, tgt_entity
                    )
                    serialized["suggested_verbs"] = suggested_verbs
                else:
                    serialized["suggested_verbs"] = []
            else:
                serialized["suggested_verbs"] = []
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
                        rejection_reason=f"Entry '{id}' not found",
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
            valid_types = {"decision", "insight", "limitation", "change", "context"}
            if entry_type not in valid_types:
                return _unified_response(status="rejected", data={}, rejection_reason=f"type 必須是 {valid_types} 之一")
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
                    f"Use: entities, documents, protocols, blindspots, relationships, entries"
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
