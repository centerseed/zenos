"""MCP tool: task — create, update, and list action items."""

from __future__ import annotations

import json
import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any

from zenos.domain.knowledge.collaboration_roots import is_collaboration_root_entity
from zenos.domain.task_rules import normalize_task_status
from zenos.interface.mcp._auth import _current_partner, _apply_workspace_override
from zenos.interface.mcp._common import (
    _serialize,
    _unified_response,
    _enrich_task_result,
    _error_response,
)
from zenos.interface.mcp._audit import _audit_log

logger = logging.getLogger(__name__)

_VALID_ATTACHMENT_TYPES = {"image", "file", "link"}


def _normalize_project_scope(value: object) -> str:
    """Normalize partner project scope input from MCP callers."""
    if value is None:
        return ""
    return str(value).strip().lower()


def _validate_attachments(
    attachments: list[dict],
    partner_id: str | None,
    existing_attachments: list[dict] | None = None,
) -> list[dict] | dict:
    """Validate and normalize attachment items.

    Args:
        attachments: Attachment items from caller.
        partner_id: Authenticated partner ID for uploaded_by.
        existing_attachments: Current attachments from DB; server-side fields
            (gcs_path, content_type, uploaded, created_at) are merged back so
            callers don't need to round-trip them.

    Returns:
        A list of validated attachments, or an error dict.
    """
    validated = []
    for att in attachments:
        att_type = att.get("type", "file")
        if att_type not in _VALID_ATTACHMENT_TYPES:
            return _error_response(
                status="rejected",
                error_code="INVALID_INPUT",
                message=f"Invalid attachment type '{att_type}'. Must be one of: {', '.join(_VALID_ATTACHMENT_TYPES)}",
            )
        if att_type == "link":
            if not att.get("url"):
                return _error_response(
                    status="rejected",
                    error_code="INVALID_INPUT",
                    message="Link attachment requires 'url' field",
                )
            item = {
                "id": att.get("id") or uuid.uuid4().hex,
                "type": "link",
                "url": att["url"],
                "filename": att.get("filename", att["url"]),
                "description": att.get("description", ""),
                "uploaded_by": partner_id or "",
                "created_at": att.get("created_at") or datetime.now(timezone.utc).isoformat(),
            }
        else:
            # image or file: must have attachment_id from prior upload
            if not att.get("attachment_id") and not att.get("id"):
                return _error_response(
                    status="rejected",
                    error_code="INVALID_INPUT",
                    message=f"'{att_type}' attachment requires 'attachment_id' (from upload_attachment)",
                )
            # Start from caller's data
            item = dict(att)
            if "attachment_id" in item and "id" not in item:
                item["id"] = item.pop("attachment_id")

            # Merge back server-side fields from existing attachment
            if existing_attachments:
                existing = next(
                    (a for a in existing_attachments if a.get("id") == item.get("id")), None
                )
                if existing:
                    for key in ("gcs_path", "content_type", "uploaded", "created_at"):
                        if key not in item and key in existing:
                            item[key] = existing[key]

            # Normalize: accept mime_type as alias for content_type
            if "mime_type" in item and "content_type" not in item:
                item["content_type"] = item.pop("mime_type")

            item["uploaded_by"] = partner_id or item.get("uploaded_by", "")
        validated.append(item)
    return validated


def _cleanup_removed_attachments(
    old_attachments: list[dict], new_attachments: list[dict],
) -> None:
    """Delete GCS blobs for attachments removed during update (best-effort)."""
    new_ids = {a.get("id") for a in new_attachments}
    for old in old_attachments:
        if old.get("id") not in new_ids and old.get("gcs_path"):
            try:
                from zenos.infrastructure.gcs_client import delete_blob, get_default_bucket
                delete_blob(get_default_bucket(), old["gcs_path"])
            except Exception:
                logger.warning("Failed to cleanup attachment %s", old.get("id"), exc_info=True)


async def _task_handler(
    action: str,
    title: str | None = None,
    created_by: str | None = None,
    id: str | None = None,
    description: str | None = None,
    assignee: str | None = None,
    priority: str | None = None,
    status: str | None = None,
    linked_entities: list[str] | None = None,
    linked_protocol: str | None = None,
    linked_blindspot: str | None = None,
    source_type: str | None = None,
    source_metadata: dict | None = None,
    created_via_agent: bool | None = None,
    agent_name: str | None = None,
    due_date: str | None = None,
    blocked_by: list[str] | None = None,
    blocked_reason: str | None = None,
    acceptance_criteria: list[str] | None = None,
    result: str | None = None,
    project: str | None = None,
    product_id: str | None = None,
    assignee_role_id: str | None = None,
    plan_id: str | None = None,
    plan_order: int | None = None,
    depends_on_task_ids: list[str] | None = None,
    attachments: list[dict] | None = None,
    parent_task_id: str | None = None,
    dispatcher: str | None = None,
    handoff_events: Any | None = None,  # readonly — always stripped; use task(action="handoff") instead
    to_dispatcher: str | None = None,
    reason: str | None = None,
    output_ref: str | None = None,
    notes: str | None = None,
    conn: Any | None = None,
    # Wave 9 Phase B prime — optional L3TaskEntity input for dual-path dispatch.
    # When provided and action in ("create","update"), the service-layer
    # L3 adapter is used instead of the flat-dict path.  Response shape is
    # byte-equal with the legacy path (normalize-to-legacy strategy).
    l3_entity: Any | None = None,
    **kwargs: object,
) -> dict:
    """Core task handler logic — extracted for testability.

    Called by the ``task`` MCP tool wrapper. Tests import this function
    directly to avoid calling a ``FunctionTool`` object.
    """
    if "project_id" in kwargs:
        return _error_response(
            error_code="INVALID_INPUT",
            message="project_id parameter is not supported; use product_id (ADR-047)",
            status="rejected",
        )

    from zenos.interface.mcp import _ensure_services
    import zenos.interface.mcp as _mcp

    # Wave 9 Phase B prime — L3TaskEntity dual-path dispatch.
    # If caller passes an L3TaskEntity, delegate to the service-layer adapter
    # which normalizes it to the legacy dict and runs the same validation.
    # This block returns the same shape as the legacy path (byte-equal).
    from zenos.domain.action.models import L3TaskEntity as _L3TaskEntity
    if l3_entity is not None and isinstance(l3_entity, _L3TaskEntity):
        if _mcp.task_service is None:
            await _ensure_services()
        try:
            partner = _current_partner.get()
            actor_id = (partner or {}).get("id") or ""
            if action == "create":
                # fix-11: run the same product resolution as the legacy create path.
                # If caller omits product_id, resolve via project / partner.defaultProject.
                resolved_product_id = product_id
                if resolved_product_id is None:
                    partner_default_project = _normalize_project_scope(
                        partner.get("defaultProject", "") if partner else ""
                    )
                    effective_project = _normalize_project_scope(project) or partner_default_project
                    if effective_project:
                        entity_repo = _mcp.entity_repo or getattr(_mcp.task_service, "_entities", None)
                        if entity_repo is not None:
                            resolved_product = await entity_repo.get_by_name(str(effective_project).strip())
                            if resolved_product is not None and is_collaboration_root_entity(resolved_product):
                                resolved_product_id = resolved_product.id

                # Forward explicit hierarchy kwargs (fix-5, fix-6).
                # product_id is REQUIRED; plan_id / parent_task_id are optional.
                # Adapter does NOT infer hierarchy from entity.parent_id.
                # fix-10: also forward ontology links and provenance kwargs.
                task_result = await _mcp.task_service.create_task_via_l3_entity(
                    l3_entity,
                    created_by=actor_id or created_by or "",
                    product_id=resolved_product_id or "",
                    plan_id=plan_id,
                    parent_task_id=parent_task_id,
                    project=project,
                    linked_entities=linked_entities,
                    linked_protocol=linked_protocol,
                    linked_blindspot=linked_blindspot,
                    source_type=source_type or "",
                    source_metadata=source_metadata,
                    attachments=attachments,
                    conn=conn,
                )
                task_data = await _enrich_task_result(task_result.task)
                return _unified_response(data=task_data, warnings=[])
            elif action == "update":
                task_id = id or (l3_entity.id if l3_entity.id else None)
                if not task_id:
                    return _unified_response(
                        status="rejected", data={},
                        rejection_reason="id is required for update",
                    )
                # Forward hierarchy kwargs so caller can rehome a task (fix-7).
                # fix-14: also forward MCP mutable field kwargs so the L3 update path
                # has byte-equal parity with the legacy update path.
                # Normalize list fields the same way the legacy update branch does.
                normalized_linked_entities_l3: list[str] | None = None
                if linked_entities is not None:
                    _norm = _normalize_str_list(linked_entities, "linked_entities")
                    if isinstance(_norm, dict):
                        return _norm
                    normalized_linked_entities_l3 = _norm

                normalized_blocked_by_l3: list[str] | None = None
                if blocked_by is not None:
                    _norm_bb = _normalize_str_list(blocked_by, "blocked_by")
                    if isinstance(_norm_bb, dict):
                        return _norm_bb
                    normalized_blocked_by_l3 = _norm_bb

                task_result = await _mcp.task_service.update_task_via_l3_entity(
                    task_id,
                    l3_entity,
                    product_id=product_id,
                    plan_id=plan_id,
                    parent_task_id=parent_task_id,
                    linked_entities=normalized_linked_entities_l3,
                    linked_protocol=linked_protocol,
                    linked_blindspot=linked_blindspot,
                    source_type=source_type,
                    source_metadata=source_metadata,
                    attachments=attachments,
                    blocked_by=normalized_blocked_by_l3,
                )
                task_data = await _enrich_task_result(task_result.task)
                return _unified_response(data=task_data, warnings=[])
            # For other actions (handoff, etc.) fall through to legacy path
        except ValueError as _e:
            from zenos.application.action.task_service import TaskValidationError
            if isinstance(_e, TaskValidationError):
                return _error_response(
                    status="rejected",
                    error_code=_e.error_code,
                    message=str(_e),
                )
            return _unified_response(status="rejected", data={}, rejection_reason=str(_e))

    def _looks_like_markdown(text: str) -> bool:
        markers = ("# ", "## ", "- ", "* ", "1. ", "|", "```", "**", "[", "](")
        return any(m in text for m in markers)

    def _normalize_description_to_markdown(raw: str | None) -> str:
        text = (raw or "").strip()
        if not text:
            return ""
        if _looks_like_markdown(text):
            return text

        lines = [ln.strip() for ln in text.replace("\r\n", "\n").split("\n") if ln.strip()]
        if not lines:
            return ""

        title = lines[0]
        details = lines[1:]
        if not details and len(title) > 24:
            chunks = [seg.strip() for seg in re.split(r"[。；;]\s*", title) if seg.strip()]
            if len(chunks) > 1:
                title = chunks[0]
                details = chunks[1:]

        md_lines = [f"**需求摘要**：{title}"]
        if details:
            md_lines.append("")
            md_lines.append("**補充資訊**")
            md_lines.extend(f"- {d}" for d in details)
        return "\n".join(md_lines)

    def _merge_actor_metadata(meta: dict | None, partner_ctx: dict | None) -> dict:
        merged = dict(meta or {})
        via_agent = True if created_via_agent is None else bool(created_via_agent)
        merged["created_via_agent"] = via_agent
        if agent_name:
            merged["agent_name"] = agent_name
        elif via_agent and "agent_name" not in merged:
            merged["agent_name"] = "agent"
        if partner_ctx and partner_ctx.get("id"):
            merged["actor_partner_id"] = partner_ctx["id"]
        return merged

    def _normalize_status_with_warning(raw_status: str | None, warning_bucket: list[str]) -> str | None:
        if raw_status is None:
            return None
        normalized = normalize_task_status(raw_status)
        if normalized != raw_status:
            warning_bucket.append(
                f"legacy task status alias 已自動改寫：{raw_status}->{normalized}"
            )
        return normalized

    def _normalize_str_list(value: list[str] | str | None, field: str) -> list[str] | dict:  # dict = _unified_response(status="rejected")
        if value is None:
            return []
        if isinstance(value, list):
            if not all(isinstance(v, str) for v in value):
                return _unified_response(status="rejected", data={}, rejection_reason=f"{field} must be list[str]")
            return value
        if isinstance(value, str):
            text = value.strip()
            if not text:
                return []
            # Accept JSON array string for backward compatibility.
            if text.startswith("["):
                try:
                    parsed = json.loads(text)
                except json.JSONDecodeError:
                    return _unified_response(status="rejected", data={}, rejection_reason=f"{field} must be list[str] or JSON array string")
                if not isinstance(parsed, list) or not all(isinstance(v, str) for v in parsed):
                    return _unified_response(status="rejected", data={}, rejection_reason=f"{field} must be list[str]")
                return parsed
            return _unified_response(status="rejected", data={}, rejection_reason=f"{field} must be list[str], not plain string")
        return _unified_response(status="rejected", data={}, rejection_reason=f"{field} must be list[str]")

    try:
        # Resolve partner context once — used for auto-filling created_by and project
        partner = _current_partner.get()
        partner_default_project = _normalize_project_scope(
            partner.get("defaultProject", "") if partner else ""
        )
        mutation_warnings: list[str] = []

        # handoff_events is server-managed (append-only via task(action="handoff")).
        # If caller passes it on create/update, strip it and emit a warning.
        if handoff_events is not None:
            mutation_warnings.append("HANDOFF_EVENTS_READONLY")

        if action == "create":
            if not title:
                return _unified_response(status="rejected", data={}, rejection_reason="title is required for create")
            # In MCP context, creator identity must follow the authenticated
            # partner bound to the API key, not arbitrary caller input.
            if partner and partner.get("id"):
                created_by = partner.get("id")
            elif not created_by:
                # Backward-compat fallback for non-MCP/internal callers.
                created_by = None
            if not created_by:
                return _unified_response(status="rejected", data={}, rejection_reason="created_by is required for create")

            # Auto-fill project from partner's default_project if caller omits it
            effective_project = _normalize_project_scope(project) or partner_default_project

            if _mcp.task_service is None:
                await _ensure_services()

            entity_repo = _mcp.entity_repo or getattr(_mcp.task_service, "_entities", None)

            auto_resolved_product_id: str | None = None
            if product_id is None:
                if not effective_project:
                    return _error_response(
                        status="rejected",
                        error_code="MISSING_PRODUCT_ID",
                        message="product_id is required when project/defaultProject cannot be resolved to a collaboration root entity",
                    )
                if entity_repo is None:
                    return _error_response(
                        status="error",
                        error_code="BACKEND_UNAVAILABLE",
                        message="entity repository is unavailable for product resolution",
                    )
                resolved_product = await entity_repo.get_by_name(str(effective_project).strip())
                if resolved_product is None:
                    return _error_response(
                        status="rejected",
                        error_code="MISSING_PRODUCT_ID",
                        message=(
                            "product_id is required when project/defaultProject "
                            "cannot be resolved to a collaboration root entity"
                        ),
                    )
                if not is_collaboration_root_entity(resolved_product):
                    return _error_response(
                        status="rejected",
                        error_code="INVALID_PRODUCT_ID",
                        message=(
                            f"project/defaultProject '{effective_project}' resolved to "
                            f"non-collaboration-root entity '{resolved_product.id}'"
                        ),
                    )
                auto_resolved_product_id = resolved_product.id

            # Parse due_date string to datetime
            parsed_due = None
            if due_date:
                try:
                    parsed_due = datetime.fromisoformat(due_date)
                except (ValueError, TypeError):
                    return _unified_response(status="rejected", data={}, rejection_reason=f"Invalid due_date format: {due_date}")

            normalized_description = _normalize_description_to_markdown(description)
            normalized_linked_entities = _normalize_str_list(linked_entities, "linked_entities")
            if isinstance(normalized_linked_entities, dict):
                return normalized_linked_entities
            normalized_blocked_by = _normalize_str_list(blocked_by, "blocked_by")
            if isinstance(normalized_blocked_by, dict):
                return normalized_blocked_by
            normalized_acceptance_criteria = _normalize_str_list(acceptance_criteria, "acceptance_criteria")
            if isinstance(normalized_acceptance_criteria, dict):
                return normalized_acceptance_criteria
            normalized_depends_on = _normalize_str_list(depends_on_task_ids, "depends_on_task_ids")
            if isinstance(normalized_depends_on, dict):
                return normalized_depends_on

            data = {
                "title": title,
                "created_by": created_by,
                "updated_by": created_by,
                "description": normalized_description,
                "assignee": assignee,
                "priority": priority,
                "status": _normalize_status_with_warning(status or "todo", mutation_warnings) or "todo",
                "linked_entities": normalized_linked_entities,
                "linked_protocol": linked_protocol,
                "linked_blindspot": linked_blindspot,
                "source_type": source_type or "",
                "source_metadata": _merge_actor_metadata(source_metadata, partner),
                "due_date": parsed_due,
                "blocked_by": normalized_blocked_by,
                "blocked_reason": blocked_reason,
                "acceptance_criteria": normalized_acceptance_criteria,
                "project": effective_project,
                "product_id": product_id,
                "assignee_role_id": assignee_role_id,
                "plan_id": plan_id,
                "plan_order": plan_order,
                "depends_on_task_ids": normalized_depends_on,
                "parent_task_id": parent_task_id,
                "dispatcher": dispatcher,
            }

            # Validate and process attachments
            if attachments:
                validated = _validate_attachments(attachments, (partner or {}).get("id"))
                if isinstance(validated, dict) and validated.get("status") != "ok":
                    return validated
                data["attachments"] = validated

            task_result = await _mcp.task_service.create_task(data, conn=conn)
            task_data = await _enrich_task_result(task_result.task)
            if normalized_linked_entities and len(task_result.task.linked_entities) < len(normalized_linked_entities):
                mutation_warnings.append("LINKED_ENTITIES_PRODUCT_STRIPPED")
            if project is not None:
                normalized_input_project = _normalize_project_scope(project)
                normalized_saved_project = _normalize_project_scope(task_result.task.project)
                if normalized_input_project and normalized_saved_project and normalized_input_project != normalized_saved_project:
                    mutation_warnings.append("PROJECT_STRING_IGNORED")
            _audit_log(
                event_type="task.create",
                target={"collection": "tasks", "id": task_data.get("id")},
                changes={
                    "input": data,
                    "auto_resolved_product_id": auto_resolved_product_id,
                },
            )
            create_warnings: list[str] = list(mutation_warnings)
            if not task_result.task.linked_entities:
                create_warnings.append(
                    "linked_entities 為空：任務缺少 ontology context，governance_hints 將無法產生有效建議"
                )
            if not effective_project:
                create_warnings.append(
                    "未指定 project：票已建立但無法被 search(project=...) 過濾找到，建議傳入 project 參數（如 'zenos'）"
                )
            return _unified_response(data=task_data, warnings=create_warnings)

        elif action == "update":
            if not id:
                return _unified_response(status="rejected", data={}, rejection_reason="id is required for update")

            updates: dict = {}
            if status is not None:
                updates["status"] = _normalize_status_with_warning(status, mutation_warnings)
            actor_id = (partner or {}).get("id")
            if actor_id:
                updates["updated_by"] = actor_id
            if assignee is not None:
                updates["assignee"] = assignee
            if priority is not None:
                updates["priority"] = priority
            if description is not None:
                updates["description"] = description
            if blocked_reason is not None:
                updates["blocked_reason"] = blocked_reason
            if result is not None:
                updates["result"] = result
            if blocked_by is not None:
                normalized_blocked_by = _normalize_str_list(blocked_by, "blocked_by")
                if isinstance(normalized_blocked_by, dict):
                    return normalized_blocked_by
                updates["blocked_by"] = normalized_blocked_by
            if source_metadata is not None:
                updates["source_metadata"] = source_metadata
            if linked_entities is not None:
                normalized_linked_entities = _normalize_str_list(
                    linked_entities, "linked_entities"
                )
                if isinstance(normalized_linked_entities, dict):
                    return normalized_linked_entities
                updates["linked_entities"] = normalized_linked_entities
            if acceptance_criteria is not None:
                normalized_acceptance_criteria = _normalize_str_list(
                    acceptance_criteria, "acceptance_criteria"
                )
                if isinstance(normalized_acceptance_criteria, dict):
                    return normalized_acceptance_criteria
                updates["acceptance_criteria"] = normalized_acceptance_criteria
            if project is not None:
                updates["project"] = _normalize_project_scope(project)
            if product_id is not None:
                updates["product_id"] = product_id
            if due_date is not None:
                try:
                    updates["due_date"] = datetime.fromisoformat(due_date)
                except (ValueError, TypeError):
                    return _unified_response(status="rejected", data={}, rejection_reason=f"Invalid due_date: {due_date}")
            if plan_id is not None:
                updates["plan_id"] = plan_id
            if plan_order is not None:
                updates["plan_order"] = plan_order
            if depends_on_task_ids is not None:
                normalized_depends_on = _normalize_str_list(
                    depends_on_task_ids, "depends_on_task_ids"
                )
                if isinstance(normalized_depends_on, dict):
                    return normalized_depends_on
                updates["depends_on_task_ids"] = normalized_depends_on
            if parent_task_id is not None:
                updates["parent_task_id"] = parent_task_id
            if dispatcher is not None:
                updates["dispatcher"] = dispatcher

            # Attachments: full replacement with GCS cleanup for removed items
            if attachments is not None:
                # Fetch existing task first so we can merge server-side fields
                if _mcp.task_service is None:
                    await _ensure_services()
                old_task = await _mcp.task_service._tasks.get_by_id(id)
                existing_atts = old_task.attachments if old_task else None

                validated = _validate_attachments(
                    attachments, (partner or {}).get("id"), existing_attachments=existing_atts
                )
                if isinstance(validated, dict) and validated.get("status") != "ok":
                    return validated
                updates["attachments"] = validated

                # Best-effort cleanup of removed GCS blobs
                if old_task:
                    _cleanup_removed_attachments(old_task.attachments, validated)

            if _mcp.task_service is None:
                await _ensure_services()
            task_result = await _mcp.task_service.update_task(id, updates)
            task_data = await _enrich_task_result(task_result.task)
            if "linked_entities" in updates and len(task_result.task.linked_entities) < len(updates["linked_entities"]):
                mutation_warnings.append("LINKED_ENTITIES_PRODUCT_STRIPPED")
            if project is not None:
                normalized_input_project = _normalize_project_scope(project)
                normalized_saved_project = _normalize_project_scope(task_result.task.project)
                if normalized_input_project and normalized_saved_project and normalized_input_project != normalized_saved_project:
                    mutation_warnings.append("PROJECT_STRING_IGNORED")
            if task_result.cascade_updates:
                task_data["cascadeUpdates"] = [
                    {"taskId": c.task_id, "change": c.change, "reason": c.reason}
                    for c in task_result.cascade_updates
                ]
            cascade_suggestions = [
                {
                    "id": c.task_id,
                    "title": "follow-up task updated by cascade",
                    "reason": c.reason,
                }
                for c in (task_result.cascade_updates or [])
            ]
            _audit_log(
                event_type="task.update",
                target={"collection": "tasks", "id": id},
                changes={"updates": updates},
            )
            from zenos.interface.mcp._common import _build_governance_hints
            return _unified_response(
                data=task_data,
                warnings=mutation_warnings,
                suggestions=cascade_suggestions,
                governance_hints=_build_governance_hints(
                    suggested_follow_up_tasks=cascade_suggestions,
                ),
            )

        elif action == "handoff":
            if not id:
                return _unified_response(status="rejected", data={}, rejection_reason="id is required for handoff")
            if not to_dispatcher:
                return _unified_response(status="rejected", data={}, rejection_reason="to_dispatcher is required for handoff")
            if not reason:
                return _unified_response(status="rejected", data={}, rejection_reason="reason is required for handoff")

            if _mcp.task_service is None:
                await _ensure_services()
            task_result = await _mcp.task_service.handoff_task(
                id,
                to_dispatcher=to_dispatcher,
                reason=reason,
                output_ref=output_ref,
                notes=notes,
                updated_by=(partner or {}).get("id"),
            )
            task_data = await _enrich_task_result(task_result.task)
            _audit_log(
                event_type="ontology.task.handoff",
                target={"collection": "tasks", "id": id},
                changes={
                    "from_dispatcher": task_result.task.handoff_events[-1].from_dispatcher if task_result.task.handoff_events else None,
                    "to_dispatcher": to_dispatcher,
                    "reason": reason,
                    "output_ref": output_ref,
                    "notes": notes,
                },
            )
            return _unified_response(data=task_data, warnings=mutation_warnings)

        else:
            return _unified_response(
                status="rejected",
                data={},
                rejection_reason=f"Unknown action '{action}'. Use: create, update, handoff",
            )
    except ValueError as e:
        from zenos.application.action.task_service import TaskValidationError
        if isinstance(e, TaskValidationError):
            return _error_response(
                status="rejected",
                error_code=e.error_code,
                message=str(e),
            )
        return _unified_response(status="rejected", data={}, rejection_reason=str(e))


async def task(
    action: str,  # "create" | "update" | "handoff"
    title: str | None = None,
    created_by: str | None = None,
    id: str | None = None,
    id_prefix: str | None = None,
    description: str | None = None,
    assignee: str | None = None,
    priority: str | None = None,
    status: str | None = None,
    linked_entities: list[str] | None = None,
    linked_protocol: str | None = None,
    linked_blindspot: str | None = None,
    source_type: str | None = None,
    source_metadata: dict | None = None,
    created_via_agent: bool | None = None,
    agent_name: str | None = None,
    due_date: str | None = None,
    blocked_by: list[str] | None = None,
    blocked_reason: str | None = None,
    acceptance_criteria: list[str] | None = None,
    result: str | None = None,
    project: str | None = None,
    product_id: str | None = None,
    assignee_role_id: str | None = None,
    plan_id: str | None = None,
    plan_order: int | None = None,
    depends_on_task_ids: list[str] | None = None,
    attachments: list[dict] | None = None,
    parent_task_id: str | None = None,
    dispatcher: str | None = None,
    handoff_events: Any | None = None,  # readonly — pass triggers HANDOFF_EVENTS_READONLY warning
    to_dispatcher: str | None = None,
    reason: str | None = None,
    output_ref: str | None = None,
    notes: str | None = None,
    workspace_id: str | None = None,
    project_id: str | None = None,  # DEPRECATED: ADR-047 D3 — passing any value → INVALID_INPUT
) -> dict:
    """管理知識驅動的行動項目（Action Layer）。

    任務是 ontology 的 output 路徑——從知識洞察產生的具體行動。
    每個任務透過 linked_entities/linked_blindspot 連結回 ontology，
    讓收到任務的人/agent 自動獲得相關 context。

    使用時機：
    - 建任務 → action="create"（必填：title；created_by 由 server 依 API key context 寫入）
    - 改狀態 / 欄位 → action="update"（必填：id。改 status/assignee/priority 等）
    - Agent / human 交接 → action="handoff"（必填：id, to_dispatcher, reason）
    - 列任務 → 不要用這個，用 search(collection="tasks") 更靈活

    狀態流：todo → in_progress → review → done
            任何活躍狀態可 → cancelled。
    注意：不能用 update 把 status 改成 done（必須走 confirm 驗收流程）。
    補充限制：
    - create 時初始 status 只能是 todo
    - update 到 review 時，result 為必填（SQL schema 強制）
    - blocked_by 可記錄依賴，但不再使用 blocked 狀態欄
    - linked_protocol / linked_blindspot / assignee_role_id / linked_entities 會受資料庫外鍵限制，ID 必須存在於同租戶資料中
    - task 屬於某個 plan 時，建議帶 plan_id 與 plan_order，讓 agent 能按順序執行

    不要用這個工具的情境：
    - 查任務列表 → 用 search(collection="tasks")
    - 驗收任務 → 用 confirm(collection="tasks")

    Args:
        action: "create" 或 "update"
        title: 任務標題，動詞開頭（create 必填）
        created_by: 建立者 partner ID（create 時由 server 依 API key context 覆寫）
        id: 任務 ID（update 必填）
        description: 任務描述
        assignee: 被指派者 UID（具體的人或 agent）
        priority: critical/high/medium/low（不傳時 AI 自動推薦）
        status: create 時只能 todo；update 時需通過合法性驗證
        linked_entities: 關聯的 entity IDs，型別必須是 list[str]（不可傳單一字串）
        linked_protocol: 關聯的 Protocol ID
        linked_blindspot: 觸發的 blindspot ID
        source_type: 來源類型（如 "chat"、"doc"、"repo"、"spec"、"review"）
        source_metadata: 來源追溯與外部同步資訊（可選，dict）。
            ⚠️ 這是「來源追溯」用途，不是放附件的地方。附件請用 attachments 參數。
            推薦結構：
            {
              "provenance": [
                {
                  "type": "chat|doc|repo",
                  "label": "來源標題",
                  "snippet": "對話或代碼原文片段"
                }
              ]
            }
        created_via_agent: 是否由 agent 建立。預設 true（MCP 路徑）。
                           ⚠️ 此欄位與 agent_name 會合併寫入 source_metadata.agent_info。
        agent_name: agent 名稱（如 "architect-agent"）。created_via_agent=true 時建議帶入。
                    ⚠️ 此值不會獨立存為 task 欄位，而是合併寫入 source_metadata.agent_info。
        due_date: 到期日 ISO-8601（如 "2026-03-29"）
        blocked_by: 阻塞此任務的 task IDs，型別必須是 list[str]
        blocked_reason: 可選的依賴/阻塞說明（不再綁定 blocked 狀態）
        acceptance_criteria: 驗收條件列表，型別必須是 list[str]
        result: 完成產出描述（status=review 時必填）
        project: 所屬專案識別碼（如 "zenos"、"paceriz"），用於任務隔離。
            未傳時自動使用 partner 的 default_project，確保任務不會跨專案污染。
        product_id: 任務歸屬的 product entity ID。新 write path 應優先傳這個欄位。
        assignee_role_id: 指向 role entity 的 ID（可選），表達「這個任務需要什麼角色」而非「指派給誰」。
                          get 時會展開為角色的 name/summary context。
        plan_id: 任務群組 ID（PLAN 層識別）
        plan_order: 任務在 plan 內順序（>=1）
        depends_on_task_ids: 前置依賴 task IDs（可選，型別必須是 list[str]）
        attachments: 附件陣列（可選）。create 時傳入初始附件；update 時為全量覆寫。
            ⚠️ 附件必須用此參數，不能放在 source_metadata 裡。
            每個項目需有 type ("image"/"file"/"link")。
            - link 類型：需有 url 和 title。範例：{"type": "link", "url": "https://...", "title": "蝦皮旗艦館"}
            - image/file 類型：先呼叫 upload_attachment 取得 signed_put_url，用 curl PUT 上傳檔案後，再帶 attachment_id。
              範例：{"type": "image", "id": "<attachment_id>", "filename": "photo.jpg", "content_type": "image/jpeg"}
            update 時為全量覆寫——傳入的陣列會取代所有既有附件。

    系統欄位：
        updated_by: 不接受 caller 直接傳入；由 server 依當次 actor context 自動寫入
        workspace_id: 選填。切換到指定 workspace 執行任務操作（必須在你的可用列表內）。
        project_id: [DEPRECATED — ADR-047 D3] 此參數已完全移除語意。傳入任何非 None 值會立即
            回傳 {"status": "rejected", "data": {"error": "INVALID_INPUT"}}。
            請改用 product_id。
    """
    if project_id is not None:
        return _unified_response(
            status="rejected",
            data={
                "error": "INVALID_INPUT",
                "message": "project_id parameter is not supported; use product_id (ADR-047)",
            },
        )
    # AC-MIDE-05: task (handoff/update/delete) 絕對不支援 id_prefix
    if id_prefix is not None:
        return _unified_response(
            status="rejected",
            data={"hint": "write 類操作需完整 32-char id，避免 prefix 碰撞誤觸破壞性操作"},
            rejection_reason="id_prefix_not_allowed_for_write_ops",
        )
    if workspace_id:
        err = _apply_workspace_override(workspace_id)
        if err is not None:
            return err
    return await _task_handler(
        action=action,
        title=title,
        created_by=created_by,
        id=id,
        description=description,
        assignee=assignee,
        priority=priority,
        status=status,
        linked_entities=linked_entities,
        linked_protocol=linked_protocol,
        linked_blindspot=linked_blindspot,
        source_type=source_type,
        source_metadata=source_metadata,
        created_via_agent=created_via_agent,
        agent_name=agent_name,
        due_date=due_date,
        blocked_by=blocked_by,
        blocked_reason=blocked_reason,
        acceptance_criteria=acceptance_criteria,
        result=result,
        project=project,
        product_id=product_id,
        assignee_role_id=assignee_role_id,
        plan_id=plan_id,
        plan_order=plan_order,
        depends_on_task_ids=depends_on_task_ids,
        attachments=attachments,
        parent_task_id=parent_task_id,
        dispatcher=dispatcher,
        handoff_events=handoff_events,
        to_dispatcher=to_dispatcher,
        reason=reason,
        output_ref=output_ref,
        notes=notes,
    )
