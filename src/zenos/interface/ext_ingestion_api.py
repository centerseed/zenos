"""External ingestion facade API for Zentropy -> ZenOS integration."""

from __future__ import annotations

from datetime import datetime
from typing import Awaitable, Callable
import logging

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from zenos.application.ingestion import (
    IngestionService,
    InMemoryIngestionRepository,
)
from zenos.interface.mcp._auth import _apply_workspace_override, _current_partner, _current_scopes

logger = logging.getLogger(__name__)

TaskAdapter = Callable[[str, dict], Awaitable[dict]]
EntryAdapter = Callable[[str, dict], Awaitable[dict]]

_service: IngestionService | None = None
_repo: object | None = None


async def _canonical_task_adapter(_workspace_id: str, payload: dict) -> dict:
    """Commit task candidate through canonical task handler."""
    from zenos.interface.mcp.task import _task_handler

    return await _task_handler(
        action="create",
        title=payload.get("title"),
        description=payload.get("description"),
        acceptance_criteria=payload.get("acceptance_criteria"),
        linked_entities=payload.get("linked_entities"),
        product_id=payload.get("product_id"),
        priority=payload.get("priority"),
        assignee=payload.get("assignee"),
        assignee_role_id=payload.get("assignee_role_id"),
        plan_id=payload.get("plan_id"),
        plan_order=payload.get("plan_order"),
        due_date=payload.get("due_date"),
        source_type="zentropy_ingestion",
        source_metadata=payload.get("source_metadata") or {},
    )


async def _canonical_entry_adapter(workspace_id: str, payload: dict) -> dict:
    """Commit entry candidate through canonical write(entries) path."""
    from zenos.interface.mcp.write import write as write_tool

    return await write_tool(
        collection="entries",
        data={
            "entity_id": payload.get("entity_id"),
            "type": payload.get("type"),
            "content": payload.get("content"),
            "context": payload.get("context"),
        },
        workspace_id=workspace_id,
    )


_task_adapter: TaskAdapter = _canonical_task_adapter
_entry_adapter: EntryAdapter = _canonical_entry_adapter


def _response(
    *,
    status_code: int = 200,
    status: str = "ok",
    data: dict | None = None,
    warnings: list[str] | None = None,
    suggestions: list[dict] | None = None,
    governance_hints: dict | None = None,
    rejection_reason: str | None = None,
) -> JSONResponse:
    payload: dict = {
        "status": status,
        "data": data or {},
        "warnings": warnings or [],
        "suggestions": suggestions or [],
        "governance_hints": governance_hints or {},
    }
    if rejection_reason is not None:
        payload["rejection_reason"] = rejection_reason
    return JSONResponse(_json_safe(payload), status_code=status_code)


def _json_safe(value: object) -> object:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    return value


def _invalid(message: str) -> JSONResponse:
    return _response(
        status_code=400,
        status="error",
        data={"error": "INVALID_REQUEST"},
        warnings=[message],
        rejection_reason="INVALID_REQUEST",
    )


def _backend_unavailable(message: str) -> JSONResponse:
    return _response(
        status_code=503,
        status="error",
        data={"error": "BACKEND_UNAVAILABLE"},
        warnings=[message],
        rejection_reason="BACKEND_UNAVAILABLE",
    )


def _scope_forbidden(required: str) -> JSONResponse:
    current = _current_scopes.get()
    granted = sorted(current) if current is not None else ["read", "write", "task"]
    return _response(
        status_code=403,
        status="error",
        data={"error": "FORBIDDEN"},
        warnings=[f"This operation requires '{required}' scope. Your credential only has: {granted}"],
        rejection_reason="FORBIDDEN_SCOPE",
    )


def _require_scope(required: str) -> JSONResponse | None:
    current = _current_scopes.get()
    if current is None:
        return None
    if required in current:
        return None
    return _scope_forbidden(required)


def _require_workspace(workspace_id: str | None) -> JSONResponse | None:
    if not workspace_id:
        return _invalid("workspace_id is required")
    switch_error = _apply_workspace_override(workspace_id)
    if switch_error is not None:
        return JSONResponse(switch_error, status_code=403)
    return None


def _ensure_authenticated() -> JSONResponse | None:
    if _current_partner.get() is None:
        return JSONResponse({"error": "UNAUTHORIZED"}, status_code=401)
    return None


async def _ensure_service() -> IngestionService:
    global _repo, _service  # noqa: PLW0603
    if _service is not None:
        return _service
    try:
        from zenos.infrastructure.sql_common import get_pool
        from zenos.infrastructure.ingestion import SqlIngestionRepository

        pool = await get_pool()
        if hasattr(pool, "acquire"):
            _repo = SqlIngestionRepository(pool)
            _service = IngestionService(_repo)
            return _service
        raise RuntimeError("Ingestion backend pool is unavailable")
    except Exception as exc:
        logger.exception("Failed to initialize SQL ingestion repository")
        raise RuntimeError("Ingestion backend unavailable") from exc


def _require_required_fields(body: dict, fields: tuple[str, ...]) -> str | None:
    for field in fields:
        if field not in body:
            return field
    return None


def _require_json_object(body: object) -> JSONResponse | None:
    if not isinstance(body, dict):
        return _invalid("Request body must be a JSON object")
    return None


def _required_non_empty_string(body: dict, field: str) -> tuple[str | None, JSONResponse | None]:
    value = body.get(field)
    if not isinstance(value, str) or not value.strip():
        return None, _invalid(f"{field} must be a non-empty string")
    return value.strip(), None


async def _commit_atomic(
    *,
    workspace_id: str,
    product_id: str,
    batch_id: str,
    validated_task_payloads: list[tuple[int, dict]],
    validated_entry_payloads: list[tuple[int, dict]],
    l2_update_candidates: list[dict],
) -> tuple[list[dict], list[dict]]:
    from zenos.domain.knowledge import EntityEntry
    from zenos.infrastructure.context import current_partner_department
    from zenos.infrastructure.sql_common import _new_id
    from zenos.infrastructure.unit_of_work import UnitOfWork
    from zenos.interface.mcp import _ensure_services
    from zenos.interface.mcp.task import _task_handler
    import zenos.interface.mcp as _mcp

    await _ensure_services()
    if _mcp.task_service is None or _mcp.entry_repo is None:
        raise RuntimeError("Core services unavailable for atomic commit")

    pool = getattr(_repo, "_pool", None)
    if pool is None or not hasattr(_repo, "enqueue_review_items"):
        raise RuntimeError("Atomic commit requires SQL ingestion backend")

    partner_ctx = _current_partner.get() or {}
    partner_id = str(partner_ctx.get("id") or "")
    if not partner_id:
        raise RuntimeError("Missing partner context")
    department = str(partner_ctx.get("department") or current_partner_department.get() or "all")

    committed: list[dict] = []
    queued_for_review: list[dict] = []
    async with UnitOfWork(pool) as uow:
        for idx, payload in validated_task_payloads:
            result = await _task_handler(
                action="create",
                title=payload.get("title"),
                description=payload.get("description"),
                acceptance_criteria=payload.get("acceptance_criteria"),
                linked_entities=payload.get("linked_entities"),
                product_id=payload.get("product_id") or product_id,
                priority=payload.get("priority"),
                assignee=payload.get("assignee"),
                assignee_role_id=payload.get("assignee_role_id"),
                plan_id=payload.get("plan_id"),
                plan_order=payload.get("plan_order"),
                due_date=payload.get("due_date"),
                source_type="zentropy_ingestion",
                source_metadata=payload.get("source_metadata") or {},
                conn=uow.conn,
            )
            if result.get("status") not in {"ok", "partial"}:
                reason = result.get("rejection_reason") or "task adapter rejected candidate"
                raise ValueError(f"task_candidate[{idx}] rejected: {reason}")
            committed.append(
                {
                    "candidate_type": "task",
                    "candidate_index": idx,
                    "status": "committed",
                    "target": result.get("data", {}),
                }
            )

        for idx, payload in validated_entry_payloads:
            saved = await _mcp.entry_repo.create(
                EntityEntry(
                    id=_new_id(),
                    partner_id=partner_id,
                    entity_id=str(payload.get("entity_id") or ""),
                    type=str(payload.get("type") or ""),
                    content=str(payload.get("content") or ""),
                    context=payload.get("context"),
                    department=department,
                ),
                conn=uow.conn,
            )
            committed.append(
                {
                    "candidate_type": "entry",
                    "candidate_index": idx,
                    "status": "committed",
                    "target": {
                        "id": saved.id,
                        "entity_id": saved.entity_id,
                        "type": saved.type,
                        "content": saved.content,
                    },
                }
            )

        review_items = [
            {
                "review_type": "l2_update",
                "candidate": c,
                "candidate_id": c.get("id") if isinstance(c, dict) else None,
                "note": "l2_update_candidate must go through review queue",
            }
            for c in l2_update_candidates
        ]
        if review_items:
            queued_for_review = await _repo.enqueue_review_items(
                workspace_id=workspace_id,
                product_id=product_id,
                batch_id=batch_id,
                items=review_items,
                conn=uow.conn,
            )

    return committed, queued_for_review


async def ingest_signal(request: Request) -> JSONResponse:
    unauth = _ensure_authenticated()
    if unauth is not None:
        return unauth
    denied = _require_scope("write")
    if denied is not None:
        return denied
    try:
        body = await request.json()
    except Exception:
        return _invalid("Request body must be valid JSON")
    shape_err = _require_json_object(body)
    if shape_err is not None:
        return shape_err

    missing = _require_required_fields(
        body,
        (
            "workspace_id",
            "product_id",
            "external_user_id",
            "external_signal_id",
            "event_type",
            "raw_ref",
            "summary",
            "intent",
            "confidence",
            "occurred_at",
        ),
    )
    if missing:
        return _invalid(f"{missing} is required")

    workspace_id = str(body.get("workspace_id") or "")
    ws_err = _require_workspace(workspace_id)
    if ws_err is not None:
        return ws_err
    product_id, err = _required_non_empty_string(body, "product_id")
    if err is not None:
        return err
    external_user_id, err = _required_non_empty_string(body, "external_user_id")
    if err is not None:
        return err
    external_signal_id, err = _required_non_empty_string(body, "external_signal_id")
    if err is not None:
        return err
    raw_ref, err = _required_non_empty_string(body, "raw_ref")
    if err is not None:
        return err

    event_type = body.get("event_type")
    if event_type not in {"task_input", "idea_input", "reflection_input"}:
        return _invalid("event_type must be one of: task_input, idea_input, reflection_input")
    intent = body.get("intent")
    if intent not in {"todo", "explore", "decide", "reflect"}:
        return _invalid("intent must be one of: todo, explore, decide, reflect")
    summary = str(body.get("summary") or "")
    if len(summary) > 280:
        return _invalid("summary must be <= 280 chars")
    try:
        confidence = float(body.get("confidence"))
    except Exception:
        return _invalid("confidence must be a number between 0.0 and 1.0")
    if confidence < 0.0 or confidence > 1.0:
        return _invalid("confidence must be a number between 0.0 and 1.0")

    try:
        service = await _ensure_service()
    except RuntimeError as exc:
        return _backend_unavailable(str(exc))
    occurred_at = service.parse_iso8601(str(body.get("occurred_at") or ""))
    if occurred_at is None:
        return _invalid("occurred_at must be ISO-8601 datetime")

    signal_id, replay = await service.ingest(
        {
            "workspace_id": workspace_id,
            "product_id": product_id,
            "external_user_id": external_user_id,
            "external_signal_id": external_signal_id,
            "event_type": event_type,
            "raw_ref": raw_ref,
            "summary": summary,
            "intent": intent,
            "confidence": confidence,
            "occurred_at": occurred_at,
        }
    )
    return _response(
        data={
            "signal_id": signal_id,
            "queued": True,
            "idempotent_replay": replay,
        }
    )


async def distill_signals(request: Request) -> JSONResponse:
    unauth = _ensure_authenticated()
    if unauth is not None:
        return unauth
    denied = _require_scope("write")
    if denied is not None:
        return denied
    try:
        body = await request.json()
    except Exception:
        return _invalid("Request body must be valid JSON")
    shape_err = _require_json_object(body)
    if shape_err is not None:
        return shape_err

    workspace_id = str(body.get("workspace_id") or "")
    ws_err = _require_workspace(workspace_id)
    if ws_err is not None:
        return ws_err
    product_id = str(body.get("product_id") or "")
    if not product_id:
        return _invalid("product_id is required")
    window = body.get("window") or {}
    if not isinstance(window, dict):
        return _invalid("window must be a JSON object")
    try:
        service = await _ensure_service()
    except RuntimeError as exc:
        return _backend_unavailable(str(exc))
    dt_from = service.parse_iso8601(str(window.get("from") or ""))
    dt_to = service.parse_iso8601(str(window.get("to") or ""))
    if dt_from is None or dt_to is None:
        return _invalid("window.from and window.to must be ISO-8601 datetime")
    if dt_from >= dt_to:
        return _invalid("window.from must be before window.to")
    try:
        max_items = int(body.get("max_items", 50))
    except Exception:
        return _invalid("max_items must be an integer")
    if max_items <= 0 or max_items > 200:
        return _invalid("max_items must be between 1 and 200")

    data = await service.distill(
        workspace_id=workspace_id,
        product_id=product_id,
        window_from=dt_from,
        window_to=dt_to,
        max_items=max_items,
    )
    return _response(data=data)


async def commit_candidates(request: Request) -> JSONResponse:
    unauth = _ensure_authenticated()
    if unauth is not None:
        return unauth
    try:
        body = await request.json()
    except Exception:
        return _invalid("Request body must be valid JSON")
    shape_err = _require_json_object(body)
    if shape_err is not None:
        return shape_err

    workspace_id = str(body.get("workspace_id") or "")
    ws_err = _require_workspace(workspace_id)
    if ws_err is not None:
        return ws_err
    product_id = str(body.get("product_id") or "")
    batch_id = str(body.get("batch_id") or "")
    if not product_id or not batch_id:
        return _invalid("product_id and batch_id are required")

    task_candidates = body.get("task_candidates") or []
    entry_candidates = body.get("entry_candidates") or []
    l2_update_candidates = body.get("l2_update_candidates") or []
    if not isinstance(task_candidates, list) or not isinstance(entry_candidates, list):
        return _invalid("task_candidates and entry_candidates must be arrays")

    if task_candidates:
        denied = _require_scope("task")
        if denied is not None:
            return denied
    if entry_candidates or l2_update_candidates:
        denied = _require_scope("write")
        if denied is not None:
            return denied

    atomic = bool(body.get("atomic", False))
    try:
        service = await _ensure_service()
    except RuntimeError as exc:
        return _backend_unavailable(str(exc))

    (
        validated_task_payloads,
        validated_entry_payloads,
        rejected,
        warnings,
    ) = service.validate_candidates(
        task_candidates=task_candidates,
        entry_candidates=entry_candidates,
    )
    if atomic:
        if rejected:
            return _response(
                data={
                    "committed": [],
                    "rejected": rejected,
                    "queued_for_review": [],
                },
                warnings=warnings + ["atomic=true: commit skipped because validation failed"],
            )
        try:
            committed, queued_for_review = await _commit_atomic(
                workspace_id=workspace_id,
                product_id=product_id,
                batch_id=batch_id,
                validated_task_payloads=validated_task_payloads,
                validated_entry_payloads=validated_entry_payloads,
                l2_update_candidates=l2_update_candidates,
            )
            result = {
                "committed": committed,
                "rejected": [],
                "queued_for_review": queued_for_review,
                "warnings": warnings,
            }
        except ValueError as exc:
            result = {
                "committed": [],
                "rejected": [{"type": "atomic", "reason": str(exc)}],
                "queued_for_review": [],
                "warnings": warnings + ["atomic=true: transaction rolled back due to commit failure"],
            }
        except RuntimeError as exc:
            return _backend_unavailable(str(exc))
    else:
        async def _task_adapter_with_product(workspace_id_arg: str, payload: dict) -> dict:
            merged_payload = dict(payload)
            merged_payload.setdefault("product_id", product_id)
            return await _task_adapter(workspace_id_arg, merged_payload)

        result = await service.commit(
            workspace_id=workspace_id,
            product_id=product_id,
            batch_id=batch_id,
            task_candidates=task_candidates,
            entry_candidates=entry_candidates,
            l2_update_candidates=l2_update_candidates,
            task_adapter=_task_adapter_with_product,
            entry_adapter=_entry_adapter,
            atomic=False,
        )
    return _response(
        data={
            "committed": result["committed"],
            "rejected": result["rejected"],
            "queued_for_review": result["queued_for_review"],
        },
        warnings=result.get("warnings") or [],
    )


async def list_review_queue(request: Request) -> JSONResponse:
    unauth = _ensure_authenticated()
    if unauth is not None:
        return unauth
    denied = _require_scope("read")
    if denied is not None:
        return denied

    workspace_id = request.query_params.get("workspace_id")
    ws_err = _require_workspace(workspace_id)
    if ws_err is not None:
        return ws_err
    product_id = request.query_params.get("product_id")
    if not product_id:
        return _invalid("product_id is required")
    status = request.query_params.get("status")
    try:
        limit = int(request.query_params.get("limit", "50"))
        offset = int(request.query_params.get("offset", "0"))
    except ValueError:
        return _invalid("limit and offset must be integers")
    if limit <= 0 or limit > 200:
        return _invalid("limit must be between 1 and 200")
    if offset < 0:
        return _invalid("offset must be >= 0")

    try:
        service = await _ensure_service()
    except RuntimeError as exc:
        return _backend_unavailable(str(exc))
    items, total = await service.review_queue(
        workspace_id=workspace_id,
        product_id=product_id,
        status=status,
        limit=limit,
        offset=offset,
    )
    return _response(data={"items": items, "total": total, "limit": limit, "offset": offset})


def _reset_inmemory_state() -> None:
    """Test helper to reset module-level state."""
    global _repo, _service  # noqa: PLW0603
    if isinstance(_repo, InMemoryIngestionRepository):
        _repo.reset()
    _repo = InMemoryIngestionRepository()
    _service = IngestionService(_repo)


def _set_commit_adapters(task_adapter: TaskAdapter, entry_adapter: EntryAdapter) -> None:
    """Test helper to replace commit adapters."""
    global _task_adapter, _entry_adapter  # noqa: PLW0603
    _task_adapter = task_adapter
    _entry_adapter = entry_adapter


def _reset_commit_adapters() -> None:
    global _task_adapter, _entry_adapter  # noqa: PLW0603
    _task_adapter = _canonical_task_adapter
    _entry_adapter = _canonical_entry_adapter


def _clear_service_cache() -> None:
    """Test helper to clear module-level backend cache."""
    global _repo, _service  # noqa: PLW0603
    _repo = None
    _service = None


# ──────────────────────────────────────────────
# Document file upload — zero LLM token cost
# ──────────────────────────────────────────────

_MAX_UPLOAD_BYTES = 1_048_576  # 1 MB


async def upload_document(request: Request) -> JSONResponse:
    """Create a new document from a multipart file upload (file bytes never touch LLM context).

    POST /api/ext/docs
    Content-Type: multipart/form-data

    Fields:
      file              Markdown file (required)
      title             Document title (required)
      workspace_id      Partner workspace ID (required)
      type              Entity type, e.g. REFERENCE (default: REFERENCE)
      doc_role          index | single (default: index)
      summary           Short document summary
      linked_entity_ids JSON array string of linked entity IDs (default: [])
      tags              JSON object string (default: {})
      allow_l2_direct_document  true only when the upload itself is a new L3 index/root

    Example (curl — file content never enters LLM context):
      curl -F "file=@README.md" -F "title=My Doc" \\
           -F "workspace_id=<id>" -F "linked_entity_ids=[\"<entity-id>\"]" \\
           "https://zenos-mcp-xxx.run.app/api/ext/docs?api_key=KEY"

    Returns: {status, data: {doc_id, revision_id, source_id}}
    """
    import json as _json

    auth_err = _ensure_authenticated()
    if auth_err:
        return auth_err

    try:
        form = await request.form()
    except Exception:
        return _invalid("Expected multipart/form-data request")

    workspace_id = str(form.get("workspace_id") or "").strip()
    ws_err = _require_workspace(workspace_id)
    if ws_err:
        return ws_err

    scope_err = _require_scope("write")
    if scope_err:
        return scope_err

    # --- file field ---
    upload = form.get("file")
    if upload is None:
        return _invalid("file field is required")

    if hasattr(upload, "read"):
        content_bytes: bytes = await upload.read()
    else:
        content_bytes = str(upload).encode("utf-8")

    if len(content_bytes) > _MAX_UPLOAD_BYTES:
        return _response(
            status_code=413,
            status="rejected",
            rejection_reason="INITIAL_CONTENT_TOO_LARGE",
            data={"error": "INITIAL_CONTENT_TOO_LARGE", "max_bytes": _MAX_UPLOAD_BYTES},
        )

    try:
        content = content_bytes.decode("utf-8")
    except UnicodeDecodeError:
        return _invalid("file must be UTF-8 encoded text")

    title = str(form.get("title") or "").strip()
    if not title:
        return _invalid("title is required")

    doc_type = str(form.get("type") or "REFERENCE").strip().upper()
    doc_role = str(form.get("doc_role") or "index").strip()
    summary = str(form.get("summary") or "").strip()
    allow_l2_direct_document = str(
        form.get("allow_l2_direct_document") or ""
    ).strip().lower() in {"1", "true", "yes"}

    try:
        linked_entity_ids = _json.loads(form.get("linked_entity_ids") or "[]")
        if not isinstance(linked_entity_ids, list):
            linked_entity_ids = []
    except Exception:
        linked_entity_ids = []

    try:
        tags = _json.loads(form.get("tags") or "{}")
        if not isinstance(tags, dict):
            tags = {}
    except Exception:
        tags = {}

    from zenos.interface.mcp.write import write as write_tool

    result = await write_tool(
        collection="documents",
        data={
            "title": title,
            "type": doc_type,
            "doc_role": doc_role,
            "summary": summary,
            "linked_entity_ids": linked_entity_ids,
            "tags": tags,
            "initial_content": content,
            "allow_l2_direct_document": allow_l2_direct_document,
        },
        workspace_id=workspace_id,
    )

    rejection = result.get("rejection_reason") or ""
    if "too_large" in rejection.lower():
        http_status = 413
    elif result.get("status") in ("rejected", "error"):
        http_status = 400
    else:
        http_status = 200
    return JSONResponse(result, status_code=http_status)


routes = [
    Route("/signals/ingest", endpoint=ingest_signal, methods=["POST"]),
    Route("/signals/distill", endpoint=distill_signals, methods=["POST"]),
    Route("/candidates/commit", endpoint=commit_candidates, methods=["POST"]),
    Route("/review-queue", endpoint=list_review_queue, methods=["GET"]),
    Route("/docs", endpoint=upload_document, methods=["POST"]),
]

app = Starlette(routes=routes)
