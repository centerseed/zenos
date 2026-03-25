"""Admin REST API — Firebase ID token auth for Dashboard operations.

Endpoints:
  GET  /api/partners            — list partners in same tenant (sanitized)
  POST /api/partners/invite     — invite a new partner (admin only)
  PUT  /api/partners/{id}/role  — change partner isAdmin (admin only)
  PUT  /api/partners/{id}/status — change partner status (admin only)
  POST /api/partners/activate   — first-login activation (self-service)

Auth: all endpoints verify Firebase ID token via firebase_admin.auth.
Admin endpoints additionally check that the caller has isAdmin=True.

CORS: allows requests from the Dashboard origin.
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, timezone

import firebase_admin  # type: ignore[import-untyped]
from firebase_admin import auth as firebase_auth  # type: ignore[import-untyped]
from google.cloud import firestore as gcloud_firestore  # type: ignore[import-untyped]
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route

logger = logging.getLogger(__name__)

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
    "http://localhost:3000",
}


def _cors_headers(request: Request) -> dict[str, str]:
    """Return CORS headers if the request origin is allowed."""
    origin = request.headers.get("origin", "")
    if origin in ALLOWED_ORIGINS:
        return {
            "access-control-allow-origin": origin,
            "access-control-allow-methods": "GET, POST, PUT, OPTIONS",
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


def _get_db():
    """Get a Firestore async client directly (not via firestore_repo).

    Admin API manages partners, not ontology entities, so it owns its own
    client instance rather than sharing the infrastructure-layer repo client.
    """
    project = os.environ.get("GOOGLE_CLOUD_PROJECT", "zenos-naruvia")
    return gcloud_firestore.AsyncClient(project=project)


async def _get_partner_by_email(email: str) -> tuple[str | None, dict | None]:
    """Find a partner doc by email. Returns (doc_id, data) or (None, None)."""
    db = _get_db()
    docs = db.collection("partners").where("email", "==", email).limit(1).stream()
    async for doc in docs:
        return doc.id, doc.to_dict()
    return None, None


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

    db = _get_db()
    caller_tenant = _same_tenant_id(caller_id, caller)
    docs = db.collection("partners").stream()
    partners: list[dict] = []
    async for doc in docs:
        data = doc.to_dict()
        if _same_tenant_id(doc.id, data) != caller_tenant:
            continue
        partners.append(_sanitize_partner_for_admin_view(doc.id, data))

    return _json_response({"partners": partners}, request=request)


# ──────────────────────────────────────────────
# Endpoint: POST /api/partners/invite
# ──────────────────────────────────────────────


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

    # Check if email already exists
    existing_id, existing = await _get_partner_by_email(email)
    if existing:
        return _error_response(
            "CONFLICT",
            f"Partner with email {email} already exists (status: {existing.get('status')})",
            409,
            request=request,
        )

    db = _get_db()
    now = datetime.now(timezone.utc)
    shared_partner_id = caller.get("sharedPartnerId") or caller_id
    partner_data = {
        "email": email,
        "displayName": email,  # will be updated on first login
        "apiKey": "",  # generated on activation
        # Keep invited members in the same data visibility/task scope as inviter.
        "authorizedEntityIds": caller.get("authorizedEntityIds", []),
        "sharedPartnerId": shared_partner_id,
        "isAdmin": False,
        "status": "invited",
        "invitedBy": caller.get("email", ""),
        "createdAt": now,
        "updatedAt": now,
    }

    doc_ref = db.collection("partners").document()
    await doc_ref.set(partner_data)

    logger.info(
        "audit",
        extra={
            "action": "partner_invite",
            "caller_email": caller.get("email", ""),
            "target_email": email,
            "target_partner_id": doc_ref.id,
            "result": "success",
            "detail": "status=invited",
        },
    )

    partner_data["id"] = doc_ref.id
    return _json_response(partner_data, status_code=201, request=request)


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

    db = _get_db()
    doc_ref = db.collection("partners").document(partner_id)
    doc = await doc_ref.get()
    if not doc.exists:
        return _error_response("NOT_FOUND", f"Partner {partner_id} not found", 404, request=request)
    target = doc.to_dict()

    if _same_tenant_id(caller_id, caller) != _same_tenant_id(partner_id, target):
        return _error_response("FORBIDDEN", "Cross-tenant role change is not allowed", 403, request=request)

    await doc_ref.update({
        "isAdmin": is_admin,
        "updatedAt": datetime.now(timezone.utc),
    })

    target_email = target.get("email", "")
    logger.info(
        "audit",
        extra={
            "action": "partner_role_change",
            "caller_email": caller.get("email", ""),
            "target_email": target_email,
            "target_partner_id": partner_id,
            "result": "success",
            "detail": f"is_admin={is_admin}",
        },
    )

    updated = target
    updated["isAdmin"] = is_admin
    updated["id"] = partner_id
    return _json_response(updated, request=request)


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

    db = _get_db()
    doc_ref = db.collection("partners").document(partner_id)
    doc = await doc_ref.get()
    if not doc.exists:
        return _error_response("NOT_FOUND", f"Partner {partner_id} not found", 404, request=request)
    target = doc.to_dict()

    if _same_tenant_id(caller_id, caller) != _same_tenant_id(partner_id, target):
        return _error_response("FORBIDDEN", "Cross-tenant status change is not allowed", 403, request=request)

    await doc_ref.update({
        "status": new_status,
        "updatedAt": datetime.now(timezone.utc),
    })

    target_email = target.get("email", "")
    logger.info(
        "audit",
        extra={
            "action": "partner_status_change",
            "caller_email": caller.get("email", ""),
            "target_email": target_email,
            "target_partner_id": partner_id,
            "result": "success",
            "detail": f"status={new_status}",
        },
    )

    updated = target
    updated["status"] = new_status
    updated["id"] = partner_id
    return _json_response(updated, request=request)


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

    db = _get_db()
    api_key = str(uuid.uuid4())
    display_name = decoded.get("name") or decoded.get("email", "")

    doc_ref = db.collection("partners").document(partner_id)
    await doc_ref.update({
        "status": "active",
        "apiKey": api_key,
        "displayName": display_name,
        "updatedAt": datetime.now(timezone.utc),
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
    Route("/api/partners/invite", invite_partner, methods=["POST", "OPTIONS"]),
    Route("/api/partners/{id}/role", update_partner_role, methods=["PUT", "OPTIONS"]),
    Route("/api/partners/{id}/status", update_partner_status, methods=["PUT", "OPTIONS"]),
    Route("/api/partners/activate", activate_partner, methods=["POST", "OPTIONS"]),
]
