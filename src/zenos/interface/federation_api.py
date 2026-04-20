"""Federation REST API — token exchange + pending link management.

ADR-029: Auth Federation Runtime.

Endpoints:
  POST /api/federation/exchange                       — exchange external token for ZenOS delegated JWT
  GET  /api/federation/pending-links                  — list pending links for a workspace (owner only)
  POST /api/federation/pending-links/{id}/approve     — approve a pending link (owner only)
  POST /api/federation/pending-links/{id}/reject      — reject a pending link (owner only)

Auth:
  /exchange — public (validated by app_id + app_secret in request body)
  others    — Firebase ID token (Authorization: Bearer <firebase-token>)
"""

from __future__ import annotations

import logging

from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from zenos.infrastructure.sql_common import get_pool
from zenos.infrastructure.identity import (
    SqlTrustedAppRepository,
    SqlIdentityLinkRepository,
    SqlPartnerRepository,
    SqlPendingIdentityLinkRepository,
    JwtService,
)
from zenos.application.identity.federation_service import FederationService

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# Lazy singletons
# ──────────────────────────────────────────────

_federation_service: FederationService | None = None


async def _ensure_federation_service() -> FederationService:
    global _federation_service  # noqa: PLW0603
    if _federation_service is None:
        pool = await get_pool()
        _federation_service = FederationService(
            trusted_app_repo=SqlTrustedAppRepository(pool),
            identity_link_repo=SqlIdentityLinkRepository(pool),
            partner_repo=SqlPartnerRepository(pool),
            jwt_service=JwtService(),
            pending_link_repo=SqlPendingIdentityLinkRepository(pool),
        )
    return _federation_service


async def _verify_firebase_token(request: Request) -> dict | None:
    """Verify Firebase ID token from Authorization header.

    Returns decoded payload with uid/email, or None if verification fails.
    """
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None
    token = auth_header.removeprefix("Bearer ").strip()
    if not token:
        return None
    try:
        from firebase_admin import auth as firebase_auth
        decoded = firebase_auth.verify_id_token(token)
        return {
            "uid": decoded.get("uid") or decoded.get("user_id"),
            "email": decoded.get("email"),
        }
    except Exception as exc:
        logger.debug("Firebase token verification failed in API: %s", exc)
        return None


def _reviewer_id_from_firebase(payload: dict | None) -> tuple[str | None, JSONResponse | None]:
    """Extract reviewer partner_id from a Firebase payload.

    Returns (reviewer_partner_id, None) on success, or (None, error_response) on failure.
    """
    if payload is None:
        return None, JSONResponse(
            {"error": "UNAUTHORIZED", "message": "Valid Firebase ID token required"},
            status_code=401,
        )
    uid = payload.get("uid")
    if not uid:
        return None, JSONResponse(
            {"error": "UNAUTHORIZED", "message": "Cannot resolve reviewer identity"},
            status_code=401,
        )
    return uid, None


# ──────────────────────────────────────────────
# Endpoint handlers
# ──────────────────────────────────────────────


async def exchange_token(request: Request) -> JSONResponse:
    """POST /api/federation/exchange

    Request body:
        app_id: str
        app_secret: str
        external_token: str
        issuer: str
        scopes: list[str] (optional, defaults to ["read"])

    Response (200):
        access_token: str
        token_type: "Bearer"
        expires_in: int
        scopes: list[str]
        principal_id: str

    Response (202):
        status: "IDENTITY_LINK_PENDING"
        message: str
        pending_link_id: str
    """
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "INVALID_REQUEST", "message": "Request body must be valid JSON"}, status_code=400)

    app_id = body.get("app_id")
    app_secret = body.get("app_secret")
    external_token = body.get("external_token")
    issuer = body.get("issuer")
    requested_scopes = body.get("scopes") or ["read"]

    if not all([app_id, app_secret, external_token, issuer]):
        return JSONResponse(
            {"error": "INVALID_REQUEST", "message": "app_id, app_secret, external_token, issuer are required"},
            status_code=400,
        )

    service = await _ensure_federation_service()

    try:
        result = await service.exchange_token(
            app_id=app_id,
            app_secret=app_secret,
            external_token=external_token,
            issuer=issuer,
            requested_scopes=requested_scopes,
        )
    except Exception:
        logger.exception("Unexpected error during federation exchange")
        return JSONResponse({"error": "INTERNAL_ERROR", "message": "Internal server error"}, status_code=500)

    # Pending approval flow → 202
    if result.get("status") == "IDENTITY_LINK_PENDING":
        return JSONResponse(result, status_code=202)

    if "error" in result:
        error_code = result["error"]
        status_code = _error_status(error_code)
        return JSONResponse(result, status_code=status_code)

    return JSONResponse(result, status_code=200)


async def list_pending_links(request: Request) -> JSONResponse:
    """GET /api/federation/pending-links?workspace_id=<uuid>

    Returns pending link requests for the workspace (owner only).
    Auth: Firebase ID token.
    """
    reviewer_partner_id, err = _reviewer_id_from_firebase(await _verify_firebase_token(request))
    if err is not None:
        return err

    workspace_id = request.query_params.get("workspace_id")
    if not workspace_id:
        return JSONResponse({"error": "INVALID_REQUEST", "message": "workspace_id query parameter is required"}, status_code=400)

    service = await _ensure_federation_service()

    try:
        result = await service.list_pending_links(
            workspace_id=workspace_id,
            reviewer_partner_id=reviewer_partner_id,
        )
    except Exception:
        logger.exception("Unexpected error listing pending links")
        return JSONResponse({"error": "INTERNAL_ERROR", "message": "Internal server error"}, status_code=500)

    if "error" in result:
        return JSONResponse(result, status_code=403)

    return JSONResponse(result, status_code=200)


async def approve_pending_link(request: Request) -> JSONResponse:
    """POST /api/federation/pending-links/{id}/approve

    Approves a pending identity link request (workspace owner only).
    Auth: Firebase ID token.
    """
    reviewer_partner_id, err = _reviewer_id_from_firebase(await _verify_firebase_token(request))
    if err is not None:
        return err

    pending_link_id = request.path_params.get("id")
    if not pending_link_id:
        return JSONResponse({"error": "INVALID_REQUEST", "message": "Pending link ID is required"}, status_code=400)

    service = await _ensure_federation_service()

    try:
        result = await service.approve_pending_link(
            pending_link_id=pending_link_id,
            reviewer_partner_id=reviewer_partner_id,
        )
    except Exception:
        logger.exception("Unexpected error approving pending link")
        return JSONResponse({"error": "INTERNAL_ERROR", "message": "Internal server error"}, status_code=500)

    if "error" in result:
        status_code = 403 if result["error"] == "FORBIDDEN" else 400
        return JSONResponse(result, status_code=status_code)

    return JSONResponse(result, status_code=200)


async def reject_pending_link(request: Request) -> JSONResponse:
    """POST /api/federation/pending-links/{id}/reject

    Rejects a pending identity link request (workspace owner only).
    Auth: Firebase ID token.
    """
    reviewer_partner_id, err = _reviewer_id_from_firebase(await _verify_firebase_token(request))
    if err is not None:
        return err

    pending_link_id = request.path_params.get("id")
    if not pending_link_id:
        return JSONResponse({"error": "INVALID_REQUEST", "message": "Pending link ID is required"}, status_code=400)

    service = await _ensure_federation_service()

    try:
        result = await service.reject_pending_link(
            pending_link_id=pending_link_id,
            reviewer_partner_id=reviewer_partner_id,
        )
    except Exception:
        logger.exception("Unexpected error rejecting pending link")
        return JSONResponse({"error": "INTERNAL_ERROR", "message": "Internal server error"}, status_code=500)

    if "error" in result:
        status_code = 403 if result["error"] == "FORBIDDEN" else 400
        return JSONResponse(result, status_code=status_code)

    return JSONResponse(result, status_code=200)


def _error_status(error_code: str) -> int:
    """Map error codes to HTTP status codes."""
    mapping = {
        "INVALID_APP": 401,
        "INVALID_SECRET": 401,
        "ISSUER_NOT_ALLOWED": 403,
        "INVALID_EXTERNAL_TOKEN": 401,
        "IDENTITY_NOT_LINKED": 403,
        "APP_SUSPENDED": 403,
        "PARTNER_NOT_ACTIVATED": 403,
        "PARTNER_SUSPENDED": 403,
    }
    return mapping.get(error_code, 400)


# ──────────────────────────────────────────────
# Route definitions
# ──────────────────────────────────────────────

routes = [
    Route("/api/federation/exchange", endpoint=exchange_token, methods=["POST"]),
    Route("/api/federation/pending-links", endpoint=list_pending_links, methods=["GET"]),
    Route("/api/federation/pending-links/{id}/approve", endpoint=approve_pending_link, methods=["POST"]),
    Route("/api/federation/pending-links/{id}/reject", endpoint=reject_pending_link, methods=["POST"]),
]
