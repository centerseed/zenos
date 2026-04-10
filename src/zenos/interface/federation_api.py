"""Federation REST API — token exchange endpoint.

ADR-029: Auth Federation Runtime.

Endpoints:
  POST /api/federation/exchange — exchange external token for ZenOS delegated JWT

Auth: this endpoint is public (validated by app_id + app_secret in request body).
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
        )
    return _federation_service


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

    Response:
        access_token: str
        token_type: "Bearer"
        expires_in: int
        scopes: list[str]
        principal_id: str
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

    if "error" in result:
        error_code = result["error"]
        status_code = _error_status(error_code)
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
]
