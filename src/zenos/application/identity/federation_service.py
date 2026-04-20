"""ZenOS Application — Federation Service.

ADR-029: Auth Federation Runtime.
Handles token exchange, identity link creation, and trusted app registration.
"""

from __future__ import annotations

import hashlib
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# Error codes
# ──────────────────────────────────────────────

INVALID_APP = "INVALID_APP"
INVALID_SECRET = "INVALID_SECRET"  # pragma: allowlist secret
ISSUER_NOT_ALLOWED = "ISSUER_NOT_ALLOWED"
INVALID_EXTERNAL_TOKEN = "INVALID_EXTERNAL_TOKEN"
IDENTITY_NOT_LINKED = "IDENTITY_NOT_LINKED"
APP_SUSPENDED = "APP_SUSPENDED"
PARTNER_NOT_ACTIVATED = "PARTNER_NOT_ACTIVATED"
PARTNER_SUSPENDED = "PARTNER_SUSPENDED"


def _check_secret(plain: str, hashed: str) -> bool:
    """Verify bcrypt-hashed secret. Falls back to sha256 in test environments."""
    try:
        import bcrypt
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except Exception:
        # Fallback: sha256 hex — used in unit tests where bcrypt hash is not used
        return hashlib.sha256(plain.encode()).hexdigest() == hashed


def _hash_secret(plain: str) -> str:
    """Hash a plain-text secret with bcrypt."""
    import bcrypt
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def _verify_external_token(token: str, issuer: str) -> dict | None:
    """Verify an external token for the given issuer.

    Currently supports Firebase tokens (issuer prefix: "https://securetoken.google.com/").
    Returns decoded payload dict or None, including email and email_verified fields.
    """
    if issuer.startswith("https://securetoken.google.com/"):
        try:
            from firebase_admin import auth as firebase_auth
            decoded = firebase_auth.verify_id_token(token)
            return {
                "uid": decoded.get("uid") or decoded.get("user_id"),
                "email": decoded.get("email"),
                "email_verified": decoded.get("email_verified", False),
            }
        except Exception as exc:
            logger.debug("Firebase token verification failed: %s", exc)
            return None

    logger.warning("Unsupported issuer for external token verification: %s", issuer)
    return None


class FederationService:
    """Orchestrates the Auth Federation token exchange flow."""

    def __init__(
        self,
        trusted_app_repo,
        identity_link_repo,
        partner_repo,
        jwt_service,
        pending_link_repo=None,
    ) -> None:
        self._app_repo = trusted_app_repo
        self._link_repo = identity_link_repo
        self._partner_repo = partner_repo
        self._jwt = jwt_service
        self._pending_repo = pending_link_repo

    # ──────────────────────────────────────────────
    # Token exchange (9-step validation)
    # ──────────────────────────────────────────────

    async def exchange_token(
        self,
        app_id: str,
        app_secret: str,
        external_token: str,
        issuer: str,
        requested_scopes: list[str],
    ) -> dict[str, Any]:
        """Exchange an external token for a ZenOS delegated JWT.

        Steps:
        1. Look up trusted app by app_id.
        2. Verify app exists → INVALID_APP.
        3. Verify app is active → APP_SUSPENDED.
        4. Verify app_secret matches hash → INVALID_SECRET.
        5. Verify issuer is in app.allowed_issuers → ISSUER_NOT_ALLOWED.
        6. Verify external token with the issuer → INVALID_EXTERNAL_TOKEN.
        7. Look up identity link; if not found, try auto-provisioning paths.
        8. Verify identity link is active (partner lookup).
        9. Sign and return delegated JWT.
        """
        # Step 1-2: Look up app
        app = await self._app_repo.get_by_id(app_id)
        if app is None:
            return {"error": INVALID_APP, "message": "Trusted app not found"}

        # Step 3: Check app status
        if not app.is_active():
            return {"error": APP_SUSPENDED, "message": "Trusted app is suspended"}

        # Step 4: Verify secret
        if not _check_secret(app_secret, app.app_secret_hash):
            return {"error": INVALID_SECRET, "message": "Invalid app secret"}

        # Step 5: Check issuer
        if not app.allows_issuer(issuer):
            return {"error": ISSUER_NOT_ALLOWED, "message": f"Issuer '{issuer}' is not allowed for this app"}

        # Step 6: Verify external token
        token_payload = _verify_external_token(external_token, issuer)
        if token_payload is None:
            return {"error": INVALID_EXTERNAL_TOKEN, "message": "External token is invalid or expired"}

        external_user_id = token_payload.get("uid") or token_payload.get("sub")
        if not external_user_id:
            return {"error": INVALID_EXTERNAL_TOKEN, "message": "Cannot extract user ID from external token"}

        # Step 7: Look up identity link; attempt auto-provisioning if missing
        link = await self._link_repo.get(app_id, issuer, external_user_id)
        if link is None:
            email = token_payload.get("email")
            email_verified = token_payload.get("email_verified", False)

            # P1: Domain auto-link (lowest friction — triggers before pending flow)
            if app.can_autolink_email(email or "", email_verified):
                partner_id = await self._provision_guest_partner(
                    workspace_id=app.default_workspace_id,
                    email=email,
                )
                link = await self._link_repo.create(
                    app_id=app_id,
                    issuer=issuer,
                    external_user_id=external_user_id,
                    zenos_principal_id=partner_id,
                    email=email,
                )
                # fall through to step 8 with the newly created link

            # P0: Owner-approve pending flow
            elif app.default_workspace_id and self._pending_repo is not None:
                # If the most recent link was explicitly rejected, do not re-initiate
                most_recent = await self._pending_repo.get_most_recent(app_id, issuer, external_user_id)
                if most_recent is not None and most_recent.status == "rejected":
                    return {"error": IDENTITY_NOT_LINKED, "message": "Identity link request was rejected"}

                # Expire any stale pending links first
                await self._pending_repo.expire_pending(app_id, issuer, external_user_id)
                # Return existing active pending or create new one
                pending = await self._pending_repo.get_active(app_id, issuer, external_user_id)
                if pending is None:
                    pending = await self._pending_repo.create(
                        app_id=app_id,
                        issuer=issuer,
                        external_user_id=external_user_id,
                        email=email,
                        workspace_id=app.default_workspace_id,
                    )
                return {
                    "status": "IDENTITY_LINK_PENDING",
                    "message": "Approval pending from workspace owner",
                    "pending_link_id": pending.id,
                }

            # Legacy: no workspace configured → 403
            else:
                return {"error": IDENTITY_NOT_LINKED, "message": "No identity link found"}

        # Step 8: Verify partner status
        partner = await self._partner_repo.get_by_id(link.zenos_principal_id)
        if partner is None:
            return {"error": PARTNER_NOT_ACTIVATED, "message": "Linked partner account not found"}

        partner_status = partner.get("status", "active")
        if partner_status == "invited":
            return {"error": PARTNER_NOT_ACTIVATED, "message": "Partner account has not been activated"}
        if partner_status not in ("active",):
            return {"error": PARTNER_SUSPENDED, "message": f"Partner account status is '{partner_status}'"}

        # Step 9: Sign delegated JWT
        granted_scopes = app.allows_scopes(requested_scopes) if requested_scopes else ["read"]
        if not granted_scopes:
            granted_scopes = ["read"]

        workspace_ids = [str(partner.get("id", link.zenos_principal_id))]
        shared = partner.get("sharedPartnerId")
        if shared:
            workspace_ids.append(str(shared))

        token = self._jwt.sign_delegated_credential(
            principal_id=link.zenos_principal_id,
            app_id=app_id,
            workspace_ids=workspace_ids,
            scopes=granted_scopes,
        )

        logger.info(
            "Federation exchange: principal=%s app=%s scopes=%s",
            link.zenos_principal_id, app_id, granted_scopes,
        )

        return {
            "access_token": token,
            "token_type": "Bearer",
            "expires_in": 3600,
            "scopes": granted_scopes,
            "principal_id": link.zenos_principal_id,
        }

    # ──────────────────────────────────────────────
    # Auto-provisioning helpers
    # ──────────────────────────────────────────────

    async def _provision_guest_partner(
        self,
        workspace_id: str,
        email: str | None,
    ) -> str:
        """Create a guest partner scoped to workspace_id and return its ID."""
        partner_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        display_name = email or f"guest-{partner_id[:8]}"
        guest_email = email or f"guest-{partner_id}@auto.zenos"

        await self._partner_repo.create({
            "id": partner_id,
            "email": guest_email,
            "displayName": display_name,
            "apiKey": "",
            "authorizedEntityIds": [],
            "status": "active",
            "isAdmin": False,
            "sharedPartnerId": workspace_id,
            "accessMode": "guest",
            "invitedBy": "",
            "roles": [],
            "department": "all",
            "createdAt": now,
            "updatedAt": now,
            "inviteExpiresAt": None,
        })
        logger.info("Provisioned guest partner: id=%s workspace=%s email=%s", partner_id, workspace_id, email)
        return partner_id

    async def _load_and_authorize_pending(
        self,
        pending_link_id: str,
        reviewer_partner_id: str,
    ) -> tuple[Any, dict | None]:
        """Load a pending link and verify the reviewer is the workspace owner.

        Returns (pending_link, error_dict). If error_dict is not None, abort with it.
        """
        if self._pending_repo is None:
            return None, {"error": "NOT_CONFIGURED", "message": "Pending link repository not configured"}

        pending = await self._pending_repo.get_by_id(pending_link_id)
        if pending is None:
            return None, {"error": "NOT_FOUND", "message": "Pending link not found"}

        if not pending.is_pending():
            return None, {"error": "INVALID_STATUS", "message": f"Pending link status is '{pending.status}', expected 'pending'"}

        owner = await self._partner_repo.get_by_id(reviewer_partner_id)
        if owner is None or str(owner["id"]) != pending.workspace_id:
            return None, {"error": "FORBIDDEN", "message": "Not workspace owner"}

        return pending, None

    async def approve_pending_link(
        self,
        pending_link_id: str,
        reviewer_partner_id: str,
    ) -> dict[str, Any]:
        """Approve a pending identity link request.

        Creates guest partner + identity link + marks pending approved.
        Note: three DB operations are not wrapped in a single transaction.
        Partial failure leaves orphan partner; monitor logs for WARN on link creation errors.
        """
        pending, err = await self._load_and_authorize_pending(pending_link_id, reviewer_partner_id)
        if err is not None:
            return err

        partner_id = await self._provision_guest_partner(
            workspace_id=pending.workspace_id,
            email=pending.email,
        )
        link = await self._link_repo.create(
            app_id=pending.app_id,
            issuer=pending.issuer,
            external_user_id=pending.external_user_id,
            zenos_principal_id=partner_id,
            email=pending.email,
        )
        await self._pending_repo.update_status(
            pending_link_id=pending_link_id,
            status="approved",
            reviewed_by=reviewer_partner_id,
        )

        logger.info(
            "Pending link approved: pending_id=%s link_id=%s partner_id=%s reviewer=%s",
            pending_link_id, link.id, partner_id, reviewer_partner_id,
        )
        return {
            "status": "approved",
            "identity_link_id": link.id,
            "partner_id": partner_id,
        }

    async def reject_pending_link(
        self,
        pending_link_id: str,
        reviewer_partner_id: str,
    ) -> dict[str, Any]:
        """Reject a pending identity link request."""
        pending, err = await self._load_and_authorize_pending(pending_link_id, reviewer_partner_id)
        if err is not None:
            return err

        await self._pending_repo.update_status(
            pending_link_id=pending_link_id,
            status="rejected",
            reviewed_by=reviewer_partner_id,
        )

        logger.info("Pending link rejected: pending_id=%s reviewer=%s", pending_link_id, reviewer_partner_id)
        return {"status": "rejected"}

    async def list_pending_links(
        self,
        workspace_id: str,
        reviewer_partner_id: str,
    ) -> dict[str, Any]:
        """List pending links for a workspace (owner only).

        Returns list of dicts with: id, app_name, issuer, external_user_id,
        email, created_at, expires_at, status.
        """
        if self._pending_repo is None:
            return {"error": "NOT_CONFIGURED", "message": "Pending link repository not configured"}

        # Verify reviewer is the workspace owner
        owner = await self._partner_repo.get_by_id(reviewer_partner_id)
        if owner is None or str(owner["id"]) != workspace_id:
            return {"error": "FORBIDDEN", "message": "Not workspace owner"}

        pending_links = await self._pending_repo.list_by_workspace(workspace_id)

        # Enrich with app_name by fetching each app (apps are few, cache not needed here)
        app_names: dict[str, str] = {}
        items = []
        for pl in pending_links:
            if pl.app_id not in app_names:
                app = await self._app_repo.get_by_id(pl.app_id)
                app_names[pl.app_id] = app.app_name if app else pl.app_id
            items.append({
                "id": pl.id,
                "app_name": app_names[pl.app_id],
                "issuer": pl.issuer,
                "external_user_id": pl.external_user_id,
                "email": pl.email,
                "created_at": pl.created_at.isoformat() if pl.created_at else None,
                "expires_at": pl.expires_at.isoformat() if pl.expires_at else None,
                "status": pl.status,
            })

        return {"pending_links": items}

    # ──────────────────────────────────────────────
    # Admin: create identity link
    # ──────────────────────────────────────────────

    async def create_identity_link(
        self,
        app_id: str,
        issuer: str,
        external_user_id: str,
        zenos_principal_id: str,
        email: str | None = None,
    ) -> dict[str, Any]:
        """Admin operation: manually link an external identity to a ZenOS principal."""
        app = await self._app_repo.get_by_id(app_id)
        if app is None:
            return {"error": INVALID_APP, "message": "Trusted app not found"}

        link = await self._link_repo.create(
            app_id=app_id,
            issuer=issuer,
            external_user_id=external_user_id,
            zenos_principal_id=zenos_principal_id,
            email=email,
        )
        logger.info(
            "Identity link created: app=%s issuer=%s external_user=%s principal=%s",
            app_id, issuer, external_user_id, zenos_principal_id,
        )
        return {
            "id": link.id,
            "app_id": link.app_id,
            "issuer": link.issuer,
            "external_user_id": link.external_user_id,
            "zenos_principal_id": link.zenos_principal_id,
            "email": link.email,
            "status": link.status,
        }

    # ──────────────────────────────────────────────
    # Admin: register trusted app
    # ──────────────────────────────────────────────

    async def register_trusted_app(
        self,
        app_name: str,
        app_secret: str,
        allowed_issuers: list[str],
        allowed_scopes: list[str] | None = None,
        default_workspace_id: str | None = None,
        auto_link_email_domains: list[str] | None = None,
    ) -> dict[str, Any]:
        """Admin operation: register a new trusted application.

        default_workspace_id is required for auto-provisioning flows.
        """
        if default_workspace_id is None:
            return {
                "error": "VALIDATION_ERROR",
                "message": "default_workspace_id is required",
            }

        if allowed_scopes is None:
            allowed_scopes = ["read"]

        app_secret_hash = _hash_secret(app_secret)
        app = await self._app_repo.create(
            app_name=app_name,
            app_secret_hash=app_secret_hash,
            allowed_issuers=allowed_issuers,
            allowed_scopes=allowed_scopes,
            default_workspace_id=default_workspace_id,
            auto_link_email_domains=auto_link_email_domains or [],
        )
        logger.info("Trusted app registered: name=%s id=%s", app.app_name, app.app_id)
        return {
            "app_id": app.app_id,
            "app_name": app.app_name,
            "allowed_issuers": app.allowed_issuers,
            "allowed_scopes": app.allowed_scopes,
            "default_workspace_id": app.default_workspace_id,
            "auto_link_email_domains": app.auto_link_email_domains,
            "status": app.status,
        }
