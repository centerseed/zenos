"""Admin REST API — Firebase ID token auth for Dashboard operations.

Endpoints:
  GET    /api/partners            — list partners in same tenant (sanitized)
  POST   /api/partners/invite     — invite a new partner (admin only)
  DELETE /api/partners/{id}       — delete an invited partner (admin only)
  PUT    /api/partners/{id}/role  — change partner isAdmin (admin only)
  PUT    /api/partners/{id}/status — change partner status (admin only)
  POST   /api/partners/activate   — first-login activation (self-service)

Auth: all endpoints verify Firebase ID token via firebase_admin.auth.
Admin endpoints additionally check that the caller has isAdmin=True.

CORS: allows requests from the Dashboard origin.
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, timedelta, timezone

import firebase_admin  # type: ignore[import-untyped]
from firebase_admin import auth as firebase_auth  # type: ignore[import-untyped]
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route

from zenos.infrastructure.email_client import EmailService
from zenos.infrastructure.sql_repo import SqlPartnerRepository  # composition root

logger = logging.getLogger(__name__)

# Lazily initialized partner repository (shared across request handlers)
_partner_repo: SqlPartnerRepository | None = None


async def _ensure_partner_repo() -> SqlPartnerRepository:
    global _partner_repo  # noqa: PLW0603
    if _partner_repo is None:
        from zenos.infrastructure.sql_repo import get_pool  # lazy import — interface must not import infra at module level
        pool = await get_pool()
        _partner_repo = SqlPartnerRepository(pool)
    return _partner_repo

# ──────────────────────────────────────────────
# Firebase Admin SDK initialization
# ──────────────────────────────────────────────

_firebase_initialized = False


def _ensure_firebase():
    """Initialize Firebase Admin SDK if not already done."""
    global _firebase_initialized  # noqa: PLW0603
    if not _firebase_initialized:
        try:
            firebase_admin.get_app()
        except ValueError:
            firebase_admin.initialize_app()
        _firebase_initialized = True


# ──────────────────────────────────────────────
# CORS
# ──────────────────────────────────────────────

ALLOWED_ORIGINS = {
    "https://zenos-naruvia.web.app",
    "https://zenos-naruvia.firebaseapp.com",
    "http://localhost:3000",
}


def _cors_headers(request: Request) -> dict[str, str]:
    """Return CORS headers if the request origin is allowed."""
    origin = request.headers.get("origin", "")
    if origin in ALLOWED_ORIGINS:
        return {
            "access-control-allow-origin": origin,
            "access-control-allow-methods": "GET, POST, PUT, PATCH, DELETE, OPTIONS",
            "access-control-allow-headers": "Authorization, Content-Type",
            "access-control-max-age": "86400",
        }
    return {}


def _serialize_for_json(obj: object) -> object:
    """Convert datetime objects to ISO strings for JSON serialization."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, dict):
        return {k: _serialize_for_json(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_serialize_for_json(v) for v in obj]
    return obj


def _json_response(
    data: dict, status_code: int = 200, *, request: Request
) -> JSONResponse:
    """Return a JSONResponse with CORS headers."""
    return JSONResponse(
        _serialize_for_json(data),
        status_code=status_code,
        headers=_cors_headers(request),
    )


def _error_response(
    error: str, message: str, status_code: int, *, request: Request
) -> JSONResponse:
    return _json_response(
        {"error": error, "message": message},
        status_code=status_code,
        request=request,
    )


# ──────────────────────────────────────────────
# Auth helpers
# ──────────────────────────────────────────────


async def _verify_firebase_token(request: Request) -> dict | None:
    """Verify Firebase ID token from Authorization header.

    Returns decoded token dict on success, None on failure.
    """
    _ensure_firebase()
    auth_header = request.headers.get("authorization", "")
    if not auth_header.startswith("Bearer "):
        return None
    id_token = auth_header[7:]
    try:
        decoded = firebase_auth.verify_id_token(id_token)
        return decoded
    except Exception:
        logger.debug("Firebase ID token verification failed", exc_info=True)
        return None


async def _get_partner_by_email(email: str) -> tuple[str | None, dict | None]:
    """Find a partner by email in SQL. Returns (partner_id, data_dict) or (None, None)."""
    repo = await _ensure_partner_repo()
    data = await repo.get_by_email(email)
    if not data:
        return None, None
    partner_id = data.pop("id")
    return partner_id, data


async def _get_caller_partner(decoded_token: dict) -> tuple[str | None, dict | None]:
    """Get the partner doc for the authenticated Firebase user."""
    email = decoded_token.get("email")
    if not email:
        return None, None
    return await _get_partner_by_email(email)


# ──────────────────────────────────────────────
# CORS preflight handler
# ──────────────────────────────────────────────


def _handle_options(request: Request) -> Response:
    """Handle CORS preflight OPTIONS request."""
    return Response(status_code=204, headers=_cors_headers(request))


def _same_tenant_id(partner_id: str | None, partner: dict | None) -> str:
    """Return a stable tenant key for partner-scoped authorization."""
    if partner and partner.get("sharedPartnerId"):
        return str(partner["sharedPartnerId"])
    return partner_id or ""


def _sanitize_partner_for_admin_view(partner_id: str, data: dict) -> dict:
    """Remove sensitive fields before returning partner data to admin UI."""
    sanitized = {
        "id": partner_id,
        "email": data.get("email", ""),
        "displayName": data.get("displayName", ""),
        "isAdmin": bool(data.get("isAdmin", False)),
        "status": data.get("status", "active"),
        "roles": list(data.get("roles", []) or []),
        "department": data.get("department", "all"),
        "invitedBy": data.get("invitedBy"),
        "createdAt": data.get("createdAt"),
        "updatedAt": data.get("updatedAt"),
        "sharedPartnerId": data.get("sharedPartnerId"),
    }
    return sanitized


# ──────────────────────────────────────────────
# Endpoint: GET /api/partners
# ──────────────────────────────────────────────


async def list_partners(request: Request) -> Response:
    """List partners in caller's tenant scope (sensitive fields stripped)."""
    if request.method == "OPTIONS":
        return _handle_options(request)

    decoded = await _verify_firebase_token(request)
    if not decoded:
        return _error_response("UNAUTHORIZED", "Invalid or missing Firebase ID token", 401, request=request)

    caller_id, caller = await _get_caller_partner(decoded)
    if not caller:
        return _error_response("FORBIDDEN", "Partner profile not found", 403, request=request)

    repo = await _ensure_partner_repo()
    caller_tenant = _same_tenant_id(caller_id, caller)
    all_partners = await repo.list_all_in_tenant(caller_tenant)
    partners = [
        _sanitize_partner_for_admin_view(p["id"], p)
        for p in all_partners
    ]

    return _json_response({"partners": partners}, request=request)


async def list_departments(request: Request) -> Response:
    """List department catalog for caller tenant."""
    if request.method == "OPTIONS":
        return _handle_options(request)

    decoded = await _verify_firebase_token(request)
    if not decoded:
        return _error_response("UNAUTHORIZED", "Invalid or missing Firebase ID token", 401, request=request)

    caller_id, caller = await _get_caller_partner(decoded)
    if not caller:
        return _error_response("FORBIDDEN", "Partner profile not found", 403, request=request)

    repo = await _ensure_partner_repo()
    tenant_id = _same_tenant_id(caller_id, caller)
    departments = await repo.list_departments(tenant_id)
    return _json_response({"departments": departments}, request=request)


# ──────────────────────────────────────────────
# Endpoint: POST /api/partners/invite
# ──────────────────────────────────────────────


def _generate_sign_in_link(email: str) -> str:
    """Generate a Firebase email sign-in link. Falls back to DASHBOARD_URL on error."""
    dashboard_url = os.environ.get("DASHBOARD_URL", "https://zenos-naruvia.web.app")
    try:
        action_code_settings = firebase_auth.ActionCodeSettings(
            url=f"{dashboard_url}/login?activate=1",
            handle_code_in_app=False,
        )
        return firebase_auth.generate_sign_in_with_email_link(email, action_code_settings)
    except Exception:
        logger.warning("Failed to generate Firebase sign-in link for %s", email, exc_info=True)
        return dashboard_url


async def _send_invite_email(to_email: str, inviter_name: str, sign_in_link: str) -> bool:
    """Send invite email. Returns bool indicating whether email was sent."""
    email_service = EmailService()
    return await email_service.send_invite_email(
        to_email=to_email,
        inviter_name=inviter_name,
        sign_in_link=sign_in_link,
    )


async def invite_partner(request: Request) -> Response:
    """Create an invited partner doc. Admin only."""
    if request.method == "OPTIONS":
        return _handle_options(request)

    decoded = await _verify_firebase_token(request)
    if not decoded:
        return _error_response("UNAUTHORIZED", "Invalid or missing Firebase ID token", 401, request=request)

    caller_id, caller = await _get_caller_partner(decoded)
    if not caller or not caller.get("isAdmin"):
        return _error_response("FORBIDDEN", "Admin access required", 403, request=request)

    try:
        body = await request.json()
    except (json.JSONDecodeError, Exception):
        return _error_response("INVALID_INPUT", "Invalid JSON body", 400, request=request)

    email = body.get("email", "").strip().lower()
    if not email or "@" not in email:
        return _error_response("INVALID_INPUT", "Valid email is required", 400, request=request)

    authorized_entity_ids = body.get("authorized_entity_ids", [])
    if not isinstance(authorized_entity_ids, list):
        authorized_entity_ids = []

    roles_raw = body.get("roles", [])
    department_raw = str(body.get("department", "all") or "all").strip() or "all"
    if not isinstance(roles_raw, list) or any(not isinstance(role, str) for role in roles_raw):
        return _error_response("INVALID_INPUT", "roles must be string[]", 400, request=request)
    roles = sorted({role.strip() for role in roles_raw if role.strip()})

    now = datetime.now(timezone.utc)
    invite_expires_at = now + timedelta(days=7)
    shared_partner_id = caller.get("sharedPartnerId") or caller_id

    # Check if email already exists in this tenant
    existing_id, existing = await _get_partner_by_email(email)
    if existing:
        existing_status = existing.get("status")
        if existing_status == "active":
            return _error_response("CONFLICT", "此 email 已是活躍成員", 409, request=request)
        if existing_status == "suspended":
            return _error_response("CONFLICT", "此 email 已被停用，請先重新啟用", 409, request=request)
        if existing_status == "invited":
            # Re-invite: reset expiry and optionally update authorized_entity_ids
            reinvite_fields: dict[str, object] = {"inviteExpiresAt": invite_expires_at, "updatedAt": now}
            if authorized_entity_ids:
                reinvite_fields["authorizedEntityIds"] = authorized_entity_ids
            repo = await _ensure_partner_repo()
            await repo.update_fields(existing_id, reinvite_fields)
            logger.info(
                "audit",
                extra={
                    "action": "partner_reinvite",
                    "caller_email": caller.get("email", ""),
                    "target_email": email,
                    "target_partner_id": existing_id,
                    "result": "success",
                    "detail": "invite_expires_at reset",
                },
            )
            existing["inviteExpiresAt"] = invite_expires_at
            existing["updatedAt"] = now
            if authorized_entity_ids:
                existing["authorizedEntityIds"] = authorized_entity_ids
            existing["id"] = existing_id
            sign_in_link = _generate_sign_in_link(email)
            email_sent = await _send_invite_email(
                to_email=email,
                inviter_name=caller.get("displayName") or caller.get("email", ""),
                sign_in_link=sign_in_link,
            )
            existing["emailSent"] = email_sent
            return _json_response(existing, status_code=200, request=request)

    new_id = uuid.uuid4().hex
    repo = await _ensure_partner_repo()
    await repo.create_department(shared_partner_id, department_raw)
    await repo.create({
        "id": new_id,
        "email": email,
        "displayName": email,
        "apiKey": "",
        "authorizedEntityIds": authorized_entity_ids,
        "status": "invited",
        "isAdmin": False,
        "sharedPartnerId": shared_partner_id,
        "invitedBy": caller.get("email", ""),
        "roles": roles,
        "department": department_raw,
        "createdAt": now,
        "updatedAt": now,
        "inviteExpiresAt": invite_expires_at,
    })

    logger.info(
        "audit",
        extra={
            "action": "partner_invite",
            "caller_email": caller.get("email", ""),
            "target_email": email,
            "target_partner_id": new_id,
            "result": "success",
            "detail": "status=invited",
        },
    )

    sign_in_link = _generate_sign_in_link(email)
    email_sent = await _send_invite_email(
        to_email=email,
        inviter_name=caller.get("displayName") or caller.get("email", ""),
        sign_in_link=sign_in_link,
    )

    partner_data = {
        "id": new_id,
        "email": email,
        "displayName": email,
        "apiKey": "",
        "authorizedEntityIds": authorized_entity_ids,
        "sharedPartnerId": shared_partner_id,
        "isAdmin": False,
        "status": "invited",
        "invitedBy": caller.get("email", ""),
        "roles": roles,
        "department": department_raw,
        "createdAt": now,
        "updatedAt": now,
        "inviteExpiresAt": invite_expires_at,
        "emailSent": email_sent,
    }
    return _json_response(partner_data, status_code=201, request=request)


async def create_department(request: Request) -> Response:
    """Create a department in the tenant catalog."""
    if request.method == "OPTIONS":
        return _handle_options(request)

    decoded = await _verify_firebase_token(request)
    if not decoded:
        return _error_response("UNAUTHORIZED", "Invalid or missing Firebase ID token", 401, request=request)

    caller_id, caller = await _get_caller_partner(decoded)
    if not caller or not caller.get("isAdmin"):
        return _error_response("FORBIDDEN", "Admin access required", 403, request=request)

    try:
        body = await request.json()
    except (json.JSONDecodeError, Exception):
        return _error_response("INVALID_INPUT", "Invalid JSON body", 400, request=request)

    name = str(body.get("name", "")).strip()
    if not name:
        return _error_response("INVALID_INPUT", "Department name required", 400, request=request)

    repo = await _ensure_partner_repo()
    tenant_id = _same_tenant_id(caller_id, caller)
    await repo.create_department(tenant_id, name)
    departments = await repo.list_departments(tenant_id)
    return _json_response({"departments": departments}, status_code=201, request=request)


async def rename_department(request: Request) -> Response:
    """Rename a department and cascade partner.department values."""
    if request.method == "OPTIONS":
        return _handle_options(request)

    decoded = await _verify_firebase_token(request)
    if not decoded:
        return _error_response("UNAUTHORIZED", "Invalid or missing Firebase ID token", 401, request=request)

    caller_id, caller = await _get_caller_partner(decoded)
    if not caller or not caller.get("isAdmin"):
        return _error_response("FORBIDDEN", "Admin access required", 403, request=request)

    old_name = request.path_params.get("name", "").strip()
    if not old_name or old_name == "all":
        return _error_response("INVALID_INPUT", "Department name required", 400, request=request)

    try:
        body = await request.json()
    except (json.JSONDecodeError, Exception):
        return _error_response("INVALID_INPUT", "Invalid JSON body", 400, request=request)

    new_name = str(body.get("name", "")).strip()
    if not new_name:
        return _error_response("INVALID_INPUT", "New department name required", 400, request=request)

    repo = await _ensure_partner_repo()
    tenant_id = _same_tenant_id(caller_id, caller)
    await repo.rename_department(tenant_id, old_name, new_name)
    departments = await repo.list_departments(tenant_id)
    return _json_response({"departments": departments}, request=request)


async def delete_department(request: Request) -> Response:
    """Delete a department and move affected partners to fallback."""
    if request.method == "OPTIONS":
        return _handle_options(request)

    decoded = await _verify_firebase_token(request)
    if not decoded:
        return _error_response("UNAUTHORIZED", "Invalid or missing Firebase ID token", 401, request=request)

    caller_id, caller = await _get_caller_partner(decoded)
    if not caller or not caller.get("isAdmin"):
        return _error_response("FORBIDDEN", "Admin access required", 403, request=request)

    name = request.path_params.get("name", "").strip()
    if not name or name == "all":
        return _error_response("INVALID_INPUT", "Department name required", 400, request=request)

    fallback_department = request.query_params.get("fallback", "all").strip() or "all"
    repo = await _ensure_partner_repo()
    tenant_id = _same_tenant_id(caller_id, caller)
    await repo.create_department(tenant_id, fallback_department)
    await repo.delete_department(tenant_id, name, fallback_department=fallback_department)
    departments = await repo.list_departments(tenant_id)
    return _json_response({"departments": departments}, request=request)


# ──────────────────────────────────────────────
# Endpoint: DELETE /api/partners/{id}
# ──────────────────────────────────────────────


async def delete_partner(request: Request) -> Response:
    """Delete an invited partner. Admin only. Only invited status allowed."""
    if request.method == "OPTIONS":
        return _handle_options(request)

    decoded = await _verify_firebase_token(request)
    if not decoded:
        return _error_response("UNAUTHORIZED", "Invalid or missing Firebase ID token", 401, request=request)

    caller_id, caller = await _get_caller_partner(decoded)
    if not caller or not caller.get("isAdmin"):
        return _error_response("FORBIDDEN", "Admin access required", 403, request=request)

    partner_id = request.path_params.get("id")
    if not partner_id:
        return _error_response("INVALID_INPUT", "Partner ID required", 400, request=request)

    # Cannot delete self
    if partner_id == caller_id:
        return _error_response("FORBIDDEN", "Cannot delete yourself", 403, request=request)

    repo = await _ensure_partner_repo()
    target = await repo.get_by_id(partner_id)
    if not target:
        return _error_response("NOT_FOUND", f"Partner {partner_id} not found", 404, request=request)

    if _same_tenant_id(caller_id, caller) != _same_tenant_id(partner_id, target):
        return _error_response("FORBIDDEN", "Cross-tenant delete is not allowed", 403, request=request)

    if target.get("status") != "invited":
        return _error_response(
            "FORBIDDEN",
            f"Only invited partners can be deleted (current status: {target.get('status')})",
            403,
            request=request,
        )

    await repo.delete(partner_id)

    logger.info(
        "audit",
        extra={
            "action": "partner_delete",
            "caller_email": caller.get("email", ""),
            "target_email": target.get("email", ""),
            "target_partner_id": partner_id,
            "result": "success",
            "detail": "status=invited",
        },
    )

    return Response(status_code=204, headers=_cors_headers(request))


# ──────────────────────────────────────────────
# Endpoint: PUT /api/partners/{id}/role
# ──────────────────────────────────────────────


async def update_partner_role(request: Request) -> Response:
    """Update partner isAdmin flag. Admin only."""
    if request.method == "OPTIONS":
        return _handle_options(request)

    decoded = await _verify_firebase_token(request)
    if not decoded:
        return _error_response("UNAUTHORIZED", "Invalid or missing Firebase ID token", 401, request=request)

    caller_id, caller = await _get_caller_partner(decoded)
    if not caller or not caller.get("isAdmin"):
        return _error_response("FORBIDDEN", "Admin access required", 403, request=request)

    partner_id = request.path_params.get("id")
    if not partner_id:
        return _error_response("INVALID_INPUT", "Partner ID required", 400, request=request)

    try:
        body = await request.json()
    except (json.JSONDecodeError, Exception):
        return _error_response("INVALID_INPUT", "Invalid JSON body", 400, request=request)

    is_admin = body.get("isAdmin")
    if not isinstance(is_admin, bool):
        return _error_response("INVALID_INPUT", "isAdmin must be a boolean", 400, request=request)

    repo = await _ensure_partner_repo()
    target = await repo.get_by_id(partner_id)
    if not target:
        return _error_response("NOT_FOUND", f"Partner {partner_id} not found", 404, request=request)

    if _same_tenant_id(caller_id, caller) != _same_tenant_id(partner_id, target):
        return _error_response("FORBIDDEN", "Cross-tenant role change is not allowed", 403, request=request)

    now = datetime.now(timezone.utc)
    await repo.update_fields(partner_id, {"isAdmin": is_admin, "updatedAt": now})

    logger.info(
        "audit",
        extra={
            "action": "partner_role_change",
            "caller_email": caller.get("email", ""),
            "target_email": target.get("email", ""),
            "target_partner_id": partner_id,
            "result": "success",
            "detail": f"is_admin={is_admin}",
        },
    )

    return _json_response({
        "id": partner_id,
        "email": target["email"],
        "displayName": target["displayName"],
        "isAdmin": is_admin,
        "status": target["status"],
        "invitedBy": target.get("invitedBy"),
        "createdAt": target.get("createdAt"),
        "updatedAt": now,
        "sharedPartnerId": target.get("sharedPartnerId"),
    }, request=request)


# ──────────────────────────────────────────────
# Endpoint: PUT /api/partners/{id}/status
# ──────────────────────────────────────────────


async def update_partner_status(request: Request) -> Response:
    """Update partner status (active/suspended). Admin only. Cannot suspend self."""
    if request.method == "OPTIONS":
        return _handle_options(request)

    decoded = await _verify_firebase_token(request)
    if not decoded:
        return _error_response("UNAUTHORIZED", "Invalid or missing Firebase ID token", 401, request=request)

    caller_id, caller = await _get_caller_partner(decoded)
    if not caller or not caller.get("isAdmin"):
        return _error_response("FORBIDDEN", "Admin access required", 403, request=request)

    partner_id = request.path_params.get("id")
    if not partner_id:
        return _error_response("INVALID_INPUT", "Partner ID required", 400, request=request)

    # Cannot suspend self
    if partner_id == caller_id:
        return _error_response("FORBIDDEN", "Cannot change your own status", 403, request=request)

    try:
        body = await request.json()
    except (json.JSONDecodeError, Exception):
        return _error_response("INVALID_INPUT", "Invalid JSON body", 400, request=request)

    new_status = body.get("status", "")
    if new_status not in ("active", "suspended"):
        return _error_response(
            "INVALID_INPUT",
            "status must be 'active' or 'suspended'",
            400,
            request=request,
        )

    repo = await _ensure_partner_repo()
    target = await repo.get_by_id(partner_id)
    if not target:
        return _error_response("NOT_FOUND", f"Partner {partner_id} not found", 404, request=request)

    if _same_tenant_id(caller_id, caller) != _same_tenant_id(partner_id, target):
        return _error_response("FORBIDDEN", "Cross-tenant status change is not allowed", 403, request=request)

    now = datetime.now(timezone.utc)
    await repo.update_fields(partner_id, {"status": new_status, "updatedAt": now})

    logger.info(
        "audit",
        extra={
            "action": "partner_status_change",
            "caller_email": caller.get("email", ""),
            "target_email": target.get("email", ""),
            "target_partner_id": partner_id,
            "result": "success",
            "detail": f"status={new_status}",
        },
    )

    return _json_response({
        "id": partner_id,
        "email": target["email"],
        "displayName": target["displayName"],
        "isAdmin": target["isAdmin"],
        "status": new_status,
        "invitedBy": target.get("invitedBy"),
        "createdAt": target.get("createdAt"),
        "updatedAt": now,
        "sharedPartnerId": target.get("sharedPartnerId"),
    }, request=request)


# ──────────────────────────────────────────────
# Endpoint: PUT /api/partners/{id}/scope
# ──────────────────────────────────────────────


async def update_partner_scope(request: Request) -> Response:
    """Update partner roles/department. Admin only."""
    if request.method == "OPTIONS":
        return _handle_options(request)

    decoded = await _verify_firebase_token(request)
    if not decoded:
        return _error_response("UNAUTHORIZED", "Invalid or missing Firebase ID token", 401, request=request)

    caller_id, caller = await _get_caller_partner(decoded)
    if not caller or not caller.get("isAdmin"):
        return _error_response("FORBIDDEN", "Admin access required", 403, request=request)

    partner_id = request.path_params.get("id")
    if not partner_id:
        return _error_response("INVALID_INPUT", "Partner ID required", 400, request=request)

    try:
        body = await request.json()
    except (json.JSONDecodeError, Exception):
        return _error_response("INVALID_INPUT", "Invalid JSON body", 400, request=request)

    roles_raw = body.get("roles", [])
    department_raw = body.get("department", "all")
    authorized_entity_ids_raw = body.get("authorized_entity_ids", None)

    if not isinstance(roles_raw, list) or any(not isinstance(r, str) for r in roles_raw):
        return _error_response("INVALID_INPUT", "roles must be string[]", 400, request=request)
    if not isinstance(department_raw, str) or not department_raw.strip():
        return _error_response("INVALID_INPUT", "department must be non-empty string", 400, request=request)
    if authorized_entity_ids_raw is not None and (
        not isinstance(authorized_entity_ids_raw, list)
        or any(not isinstance(x, str) for x in authorized_entity_ids_raw)
    ):
        return _error_response("INVALID_INPUT", "authorized_entity_ids must be string[] or null", 400, request=request)

    roles = sorted({r.strip() for r in roles_raw if r.strip()})
    department = department_raw.strip()

    repo = await _ensure_partner_repo()
    target = await repo.get_by_id(partner_id)
    if not target:
        return _error_response("NOT_FOUND", f"Partner {partner_id} not found", 404, request=request)

    caller_tenant = _same_tenant_id(caller_id, caller)
    if caller_tenant != _same_tenant_id(partner_id, target):
        return _error_response("FORBIDDEN", "Cross-tenant scope change is not allowed", 403, request=request)

    now = datetime.now(timezone.utc)
    await repo.create_department(caller_tenant, department)
    update_data: dict = {"roles": roles, "department": department, "updatedAt": now}
    if authorized_entity_ids_raw is not None:
        update_data["authorizedEntityIds"] = authorized_entity_ids_raw
    await repo.update_fields(partner_id, update_data)

    authorized_entity_ids = (
        authorized_entity_ids_raw
        if authorized_entity_ids_raw is not None
        else target.get("authorizedEntityIds", [])
    )
    return _json_response({
        "id": partner_id,
        "email": target["email"],
        "displayName": target["displayName"],
        "isAdmin": target["isAdmin"],
        "status": target["status"],
        "roles": roles,
        "department": department,
        "authorizedEntityIds": authorized_entity_ids,
        "invitedBy": target.get("invitedBy"),
        "createdAt": target.get("createdAt"),
        "updatedAt": now,
        "sharedPartnerId": target.get("sharedPartnerId"),
    }, request=request)


# ──────────────────────────────────────────────
# Endpoint: PUT /api/entities/{id}/visibility
# ──────────────────────────────────────────────


async def update_entity_visibility(request: Request) -> Response:
    """Update entity visibility + visibility scopes. Admin only."""
    if request.method == "OPTIONS":
        return _handle_options(request)

    decoded = await _verify_firebase_token(request)
    if not decoded:
        return _error_response("UNAUTHORIZED", "Invalid or missing Firebase ID token", 401, request=request)

    caller_id, caller = await _get_caller_partner(decoded)
    if not caller or not caller.get("isAdmin"):
        return _error_response("FORBIDDEN", "Admin access required", 403, request=request)

    entity_id = request.path_params.get("id")
    if not entity_id:
        return _error_response("INVALID_INPUT", "Entity ID required", 400, request=request)

    try:
        body = await request.json()
    except (json.JSONDecodeError, Exception):
        return _error_response("INVALID_INPUT", "Invalid JSON body", 400, request=request)

    visibility = str(body.get("visibility", "public"))
    valid = {"public", "restricted", "role-restricted", "confidential"}
    if visibility not in valid:
        return _error_response("INVALID_INPUT", f"visibility must be one of {sorted(valid)}", 400, request=request)

    def _norm_list(v: object) -> list[str]:
        if not isinstance(v, list):
            return []
        return sorted({str(x).strip() for x in v if str(x).strip()})

    visible_to_roles = _norm_list(body.get("visible_to_roles", []))
    visible_to_members = _norm_list(body.get("visible_to_members", []))
    visible_to_departments = _norm_list(body.get("visible_to_departments", []))

    repo = await _ensure_partner_repo()
    caller_tenant = _same_tenant_id(caller_id, caller)
    entity_tenant = await repo.get_entity_tenant(entity_id)
    if not entity_tenant:
        return _error_response("NOT_FOUND", f"Entity {entity_id} not found", 404, request=request)
    target_tenant = entity_tenant["shared_partner_id"] or entity_tenant["partner_id"]
    if caller_tenant != target_tenant:
        return _error_response("FORBIDDEN", "Cross-tenant entity update is not allowed", 403, request=request)

    now = datetime.now(timezone.utc)
    await repo.update_entity_visibility(
        entity_id, visibility, visible_to_roles, visible_to_members, visible_to_departments
    )

    return _json_response(
        {
            "id": entity_id,
            "visibility": visibility,
            "visibleToRoles": visible_to_roles,
            "visibleToMembers": visible_to_members,
            "visibleToDepartments": visible_to_departments,
            "updatedAt": now,
        },
        request=request,
    )


# ──────────────────────────────────────────────
# Endpoint: POST /api/partners/activate
# ──────────────────────────────────────────────


async def activate_partner(request: Request) -> Response:
    """First-login activation: generate API key, set status to active."""
    if request.method == "OPTIONS":
        return _handle_options(request)

    decoded = await _verify_firebase_token(request)
    if not decoded:
        return _error_response("UNAUTHORIZED", "Invalid or missing Firebase ID token", 401, request=request)

    email = decoded.get("email", "")
    if not email:
        return _error_response("INVALID_INPUT", "Email not found in token", 400, request=request)

    partner_id, partner = await _get_partner_by_email(email)
    if not partner:
        return _error_response("NOT_FOUND", f"No partner found for email {email}", 404, request=request)

    if partner.get("status") not in ("invited",):
        # Already active or suspended — return current data (idempotent for active)
        if partner.get("status") == "active":
            partner["id"] = partner_id
            return _json_response(partner, request=request)
        return _error_response(
            "FORBIDDEN",
            f"Partner status is '{partner.get('status')}', cannot activate",
            403,
            request=request,
        )

    invite_expires_at = partner.get("inviteExpiresAt")
    if invite_expires_at and invite_expires_at < datetime.now(timezone.utc):
        return _error_response(
            "INVITATION_EXPIRED",
            "邀請連結已過期，請聯繫管理員重新發送邀請",
            410,
            request=request,
        )

    api_key = str(uuid.uuid4())
    display_name = decoded.get("name") or decoded.get("email", "")
    now = datetime.now(timezone.utc)

    repo = await _ensure_partner_repo()
    await repo.update_fields(partner_id, {
        "status": "active",
        "apiKey": api_key,
        "displayName": display_name,
        "updatedAt": now,
    })

    partner["status"] = "active"
    partner["apiKey"] = api_key
    partner["displayName"] = display_name
    partner["id"] = partner_id

    logger.info(
        "audit",
        extra={
            "action": "partner_activate",
            "caller_email": email,
            "target_email": email,
            "target_partner_id": partner_id,
            "result": "success",
            "detail": "status=active",
        },
    )

    return _json_response(partner, request=request)


# ──────────────────────────────────────────────
# Route table
# ──────────────────────────────────────────────

admin_routes = [
    Route("/api/partners", list_partners, methods=["GET", "OPTIONS"]),
    Route("/api/departments", list_departments, methods=["GET", "OPTIONS"]),
    Route("/api/departments", create_department, methods=["POST", "OPTIONS"]),
    Route("/api/departments/{name:str}", rename_department, methods=["PUT", "OPTIONS"]),
    Route("/api/departments/{name:str}", delete_department, methods=["DELETE", "OPTIONS"]),
    Route("/api/partners/invite", invite_partner, methods=["POST", "OPTIONS"]),
    Route("/api/partners/activate", activate_partner, methods=["POST", "OPTIONS"]),
    Route("/api/partners/{id}", delete_partner, methods=["DELETE", "OPTIONS"]),
    Route("/api/partners/{id}/role", update_partner_role, methods=["PUT", "OPTIONS"]),
    Route("/api/partners/{id}/status", update_partner_status, methods=["PUT", "OPTIONS"]),
    Route("/api/partners/{id}/scope", update_partner_scope, methods=["PUT", "OPTIONS"]),
    Route("/api/entities/{id}/visibility", update_entity_visibility, methods=["PUT", "OPTIONS"]),
]
