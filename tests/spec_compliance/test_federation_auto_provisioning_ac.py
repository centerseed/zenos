"""
AC tests — SPEC-federation-auto-provisioning.
All 11 acceptance criteria validated with in-memory fakes (no DB access).
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

import pytest

from zenos.domain.identity.federation import TrustedApp, IdentityLink
from zenos.domain.identity.pending_link import PendingIdentityLink
from zenos.application.identity.federation_service import (
    FederationService,
    IDENTITY_NOT_LINKED,
    _hash_secret,
)
from zenos.infrastructure.identity.jwt_service import JwtService


# ---------------------------------------------------------------------------
# In-memory fakes
# ---------------------------------------------------------------------------

APP_SECRET = "test-app-secret"  # pragma: allowlist secret
APP_SECRET_HASH = hashlib.sha256(APP_SECRET.encode()).hexdigest()
JWT_SECRET = "test-jwt-secret"  # pragma: allowlist secret
ISSUER = "https://securetoken.google.com/test-project"
WORKSPACE_ID = "workspace-owner-partner"


class FakeTrustedAppRepo:
    def __init__(self, apps: list[TrustedApp] | None = None) -> None:
        self._apps: dict[str, TrustedApp] = {a.app_id: a for a in (apps or [])}

    async def get_by_id(self, app_id: str) -> TrustedApp | None:
        return self._apps.get(app_id)

    async def get_by_name(self, app_name: str) -> TrustedApp | None:
        return next((a for a in self._apps.values() if a.app_name == app_name), None)

    async def create(
        self,
        app_name: str,
        app_secret_hash: str,
        allowed_issuers: list[str],
        allowed_scopes: list[str],
        default_workspace_id: str | None = None,
        auto_link_email_domains: list[str] | None = None,
    ) -> TrustedApp:
        app = TrustedApp(
            app_id=str(uuid.uuid4()),
            app_name=app_name,
            app_secret_hash=app_secret_hash,
            allowed_issuers=allowed_issuers,
            allowed_scopes=allowed_scopes,
            default_workspace_id=default_workspace_id,
            auto_link_email_domains=auto_link_email_domains or [],
        )
        self._apps[app.app_id] = app
        return app

    async def update_status(self, app_id: str, status: str) -> None:
        if app_id in self._apps:
            self._apps[app_id].status = status


class FakeIdentityLinkRepo:
    def __init__(self, links: list[IdentityLink] | None = None) -> None:
        self._links: list[IdentityLink] = list(links or [])

    async def get(self, app_id: str, issuer: str, external_user_id: str) -> IdentityLink | None:
        for link in self._links:
            if (link.app_id == app_id and link.issuer == issuer
                    and link.external_user_id == external_user_id):
                return link
        return None

    async def create(
        self,
        app_id: str,
        issuer: str,
        external_user_id: str,
        zenos_principal_id: str,
        email: str | None = None,
    ) -> IdentityLink:
        link = IdentityLink(
            id=str(uuid.uuid4()),
            app_id=app_id,
            issuer=issuer,
            external_user_id=external_user_id,
            zenos_principal_id=zenos_principal_id,
            email=email,
        )
        self._links.append(link)
        return link

    async def list_by_principal(self, zenos_principal_id: str) -> list[IdentityLink]:
        return [lnk for lnk in self._links if lnk.zenos_principal_id == zenos_principal_id]


class FakePartnerRepo:
    def __init__(self, partners: dict[str, dict] | None = None) -> None:
        self._partners: dict[str, dict] = dict(partners or {})

    async def get_by_id(self, partner_id: str) -> dict | None:
        return self._partners.get(partner_id)

    async def get_by_email(self, email: str) -> dict | None:
        return next((p for p in self._partners.values() if p.get("email") == email), None)

    async def create(self, data: dict) -> None:
        self._partners[data["id"]] = {
            "id": data["id"],
            "email": data["email"],
            "displayName": data.get("displayName", ""),
            "status": data.get("status", "active"),
            "isAdmin": data.get("isAdmin", False),
            "sharedPartnerId": data.get("sharedPartnerId"),
            "accessMode": data.get("accessMode", "guest"),
            "roles": data.get("roles", []),
            "department": data.get("department", "all"),
        }


class FakePendingLinkRepo:
    def __init__(self) -> None:
        self._links: list[PendingIdentityLink] = []

    def _active_pending(self, app_id: str, issuer: str, external_user_id: str) -> PendingIdentityLink | None:
        now = datetime.now(timezone.utc)
        for pl in self._links:
            if (pl.app_id == app_id and pl.issuer == issuer
                    and pl.external_user_id == external_user_id
                    and pl.status == "pending"):
                exp = pl.expires_at
                if exp and exp.tzinfo is None:
                    exp = exp.replace(tzinfo=timezone.utc)
                if exp and exp > now:
                    return pl
        return None

    async def get_most_recent(
        self, app_id: str, issuer: str, external_user_id: str
    ) -> PendingIdentityLink | None:
        """Return the most recently created link for this user (any status)."""
        matches = [
            pl for pl in self._links
            if pl.app_id == app_id and pl.issuer == issuer and pl.external_user_id == external_user_id
        ]
        if not matches:
            return None
        return sorted(matches, key=lambda pl: pl.created_at or datetime.min.replace(tzinfo=timezone.utc), reverse=True)[0]

    async def get_active(self, app_id: str, issuer: str, external_user_id: str) -> PendingIdentityLink | None:
        return self._active_pending(app_id, issuer, external_user_id)

    async def get_by_id(self, pending_link_id: str) -> PendingIdentityLink | None:
        return next((pl for pl in self._links if pl.id == pending_link_id), None)

    async def create(
        self,
        app_id: str,
        issuer: str,
        external_user_id: str,
        workspace_id: str,
        email: str | None = None,
    ) -> PendingIdentityLink:
        now = datetime.now(timezone.utc)
        pl = PendingIdentityLink(
            id=str(uuid.uuid4()),
            app_id=app_id,
            issuer=issuer,
            external_user_id=external_user_id,
            workspace_id=workspace_id,
            status="pending",
            email=email,
            created_at=now,
            expires_at=now + timedelta(days=7),
        )
        self._links.append(pl)
        return pl

    async def expire_pending(self, app_id: str, issuer: str, external_user_id: str) -> None:
        now = datetime.now(timezone.utc)
        for pl in self._links:
            if (pl.app_id == app_id and pl.issuer == issuer
                    and pl.external_user_id == external_user_id
                    and pl.status == "pending"):
                exp = pl.expires_at
                if exp and exp.tzinfo is None:
                    exp = exp.replace(tzinfo=timezone.utc)
                if exp and exp <= now:
                    pl.status = "expired"

    async def update_status(
        self,
        pending_link_id: str,
        status: str,
        reviewed_by: str | None = None,
    ) -> None:
        for pl in self._links:
            if pl.id == pending_link_id:
                pl.status = status
                pl.reviewed_by = reviewed_by
                pl.reviewed_at = datetime.now(timezone.utc)
                return

    async def list_by_workspace(
        self, workspace_id: str, status: str | None = None
    ) -> list[PendingIdentityLink]:
        result = [pl for pl in self._links if pl.workspace_id == workspace_id]
        if status:
            result = [pl for pl in result if pl.status == status]
        return result


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_app(
    app_id: str = "app-001",
    default_workspace_id: str | None = WORKSPACE_ID,
    auto_link_email_domains: list[str] | None = None,
) -> TrustedApp:
    return TrustedApp(
        app_id=app_id,
        app_name="test-app",
        app_secret_hash=APP_SECRET_HASH,
        allowed_issuers=[ISSUER],
        allowed_scopes=["read", "write"],
        status="active",
        default_workspace_id=default_workspace_id,
        auto_link_email_domains=auto_link_email_domains or [],
    )


def _make_workspace_owner() -> dict:
    """The workspace owner's partner record — id == workspace_id."""
    return {
        "id": WORKSPACE_ID,
        "email": "owner@example.com",
        "displayName": "Workspace Owner",
        "status": "active",
        "isAdmin": True,
        "sharedPartnerId": None,
        "accessMode": "full",
        "roles": [],
        "department": "all",
    }


def _make_service(
    apps: list[TrustedApp] | None = None,
    links: list[IdentityLink] | None = None,
    partners: dict[str, dict] | None = None,
    pending_repo: FakePendingLinkRepo | None = None,
) -> tuple[FederationService, FakePendingLinkRepo, FakeIdentityLinkRepo, FakePartnerRepo]:
    link_repo = FakeIdentityLinkRepo(links)
    partner_repo = FakePartnerRepo(partners)
    p_repo = pending_repo or FakePendingLinkRepo()
    svc = FederationService(
        trusted_app_repo=FakeTrustedAppRepo(apps),
        identity_link_repo=link_repo,
        partner_repo=partner_repo,
        jwt_service=JwtService(secret=JWT_SECRET),
        pending_link_repo=p_repo,
    )
    return svc, p_repo, link_repo, partner_repo


def _patch_verify(monkeypatch, email: str = "user@example.com", email_verified: bool = True) -> None:
    """Patch _verify_external_token to return a controlled payload."""
    import zenos.application.identity.federation_service as svc_mod
    monkeypatch.setattr(
        svc_mod,
        "_verify_external_token",
        lambda token, issuer: {
            "uid": "external-uid-001",
            "email": email,
            "email_verified": email_verified,
        },
    )


# ---------------------------------------------------------------------------
# P0: Pending Link Core Flow
# ---------------------------------------------------------------------------


@pytest.mark.spec("AC-FAP-01")
async def test_ac_fap_01_exchange_creates_pending_link(monkeypatch):
    """AC-FAP-01: No identity_link + default_workspace_id → 202 IDENTITY_LINK_PENDING + pending row created."""
    _patch_verify(monkeypatch, email="newuser@other.com", email_verified=False)

    app = _make_app(default_workspace_id=WORKSPACE_ID)
    svc, p_repo, _, _ = _make_service(apps=[app])

    result = await svc.exchange_token(
        app_id="app-001",
        app_secret=APP_SECRET,
        external_token="tok",
        issuer=ISSUER,
        requested_scopes=["read"],
    )

    assert result.get("status") == "IDENTITY_LINK_PENDING"
    assert "pending_link_id" in result

    # DB side: exactly one pending row exists
    pending_links = await p_repo.list_by_workspace(WORKSPACE_ID)
    assert len(pending_links) == 1
    assert pending_links[0].status == "pending"


@pytest.mark.spec("AC-FAP-02")
async def test_ac_fap_02_no_duplicate_pending_link(monkeypatch):
    """AC-FAP-02: Second exchange call reuses existing pending_link — DB count stays at 1."""
    _patch_verify(monkeypatch, email="newuser@other.com", email_verified=False)

    app = _make_app(default_workspace_id=WORKSPACE_ID)
    svc, p_repo, _, _ = _make_service(apps=[app])

    result1 = await svc.exchange_token(
        app_id="app-001",
        app_secret=APP_SECRET,
        external_token="tok",
        issuer=ISSUER,
        requested_scopes=["read"],
    )
    result2 = await svc.exchange_token(
        app_id="app-001",
        app_secret=APP_SECRET,
        external_token="tok",
        issuer=ISSUER,
        requested_scopes=["read"],
    )

    assert result1.get("status") == "IDENTITY_LINK_PENDING"
    assert result2.get("status") == "IDENTITY_LINK_PENDING"
    # Same pending_link_id returned both times
    assert result1["pending_link_id"] == result2["pending_link_id"]

    pending_links = await p_repo.list_by_workspace(WORKSPACE_ID)
    assert len(pending_links) == 1


@pytest.mark.spec("AC-FAP-03")
async def test_ac_fap_03_list_pending_links(monkeypatch):
    """AC-FAP-03: Owner calls list_pending_links → returns items with required fields."""
    _patch_verify(monkeypatch, email="newuser@other.com", email_verified=False)

    app = _make_app(default_workspace_id=WORKSPACE_ID)
    partners = {WORKSPACE_ID: _make_workspace_owner()}
    svc, p_repo, _, _ = _make_service(apps=[app], partners=partners)

    # Trigger a pending link via exchange
    await svc.exchange_token(
        app_id="app-001",
        app_secret=APP_SECRET,
        external_token="tok",
        issuer=ISSUER,
        requested_scopes=["read"],
    )

    result = await svc.list_pending_links(
        workspace_id=WORKSPACE_ID,
        reviewer_partner_id=WORKSPACE_ID,
    )

    assert "error" not in result
    assert "pending_links" in result
    items = result["pending_links"]
    assert len(items) >= 1
    item = items[0]
    for field_name in ("id", "app_name", "issuer", "external_user_id", "email", "created_at", "expires_at", "status"):
        assert field_name in item, f"Missing field: {field_name}"
    assert item["app_name"] == "test-app"
    assert item["status"] == "pending"


@pytest.mark.spec("AC-FAP-04")
async def test_ac_fap_04_approve_creates_link(monkeypatch):
    """AC-FAP-04: Owner approves → identity_link created + pending=approved + subsequent exchange returns 200."""
    _patch_verify(monkeypatch, email="newuser@other.com", email_verified=False)

    app = _make_app(default_workspace_id=WORKSPACE_ID)
    partners = {WORKSPACE_ID: _make_workspace_owner()}
    svc, p_repo, link_repo, partner_repo = _make_service(apps=[app], partners=partners)

    # Create pending via exchange
    result = await svc.exchange_token(
        app_id="app-001",
        app_secret=APP_SECRET,
        external_token="tok",
        issuer=ISSUER,
        requested_scopes=["read"],
    )
    pending_link_id = result["pending_link_id"]

    # Owner approves
    approve_result = await svc.approve_pending_link(
        pending_link_id=pending_link_id,
        reviewer_partner_id=WORKSPACE_ID,
    )
    assert "error" not in approve_result
    assert approve_result["status"] == "approved"

    # Pending link is now approved
    pending = await p_repo.get_by_id(pending_link_id)
    assert pending.status == "approved"

    # Identity link exists
    link = await link_repo.get("app-001", ISSUER, "external-uid-001")
    assert link is not None

    # Subsequent exchange returns 200 with access_token
    partner_id = approve_result["partner_id"]
    # Partner should already be in the repo from provisioning
    exchange_result = await svc.exchange_token(
        app_id="app-001",
        app_secret=APP_SECRET,
        external_token="tok",
        issuer=ISSUER,
        requested_scopes=["read"],
    )
    assert "error" not in exchange_result
    assert "access_token" in exchange_result


@pytest.mark.spec("AC-FAP-05")
async def test_ac_fap_05_reject_blocks_exchange(monkeypatch):
    """AC-FAP-05: Owner rejects → pending=rejected + subsequent exchange returns IDENTITY_NOT_LINKED."""
    _patch_verify(monkeypatch, email="newuser@other.com", email_verified=False)

    app = _make_app(default_workspace_id=WORKSPACE_ID)
    partners = {WORKSPACE_ID: _make_workspace_owner()}
    svc, p_repo, _, _ = _make_service(apps=[app], partners=partners)

    # Create pending
    result = await svc.exchange_token(
        app_id="app-001",
        app_secret=APP_SECRET,
        external_token="tok",
        issuer=ISSUER,
        requested_scopes=["read"],
    )
    pending_link_id = result["pending_link_id"]

    # Owner rejects
    reject_result = await svc.reject_pending_link(
        pending_link_id=pending_link_id,
        reviewer_partner_id=WORKSPACE_ID,
    )
    assert "error" not in reject_result
    assert reject_result["status"] == "rejected"

    # Pending link is now rejected
    pending = await p_repo.get_by_id(pending_link_id)
    assert pending.status == "rejected"

    # Subsequent exchange: no identity link, pending is rejected (not pending), no new auto-link
    # → falls through to IDENTITY_NOT_LINKED (rejected != pending, and domain not in auto-link list)
    exchange_result = await svc.exchange_token(
        app_id="app-001",
        app_secret=APP_SECRET,
        external_token="tok",
        issuer=ISSUER,
        requested_scopes=["read"],
    )
    # Should NOT return IDENTITY_LINK_PENDING (old rejected link is not reused)
    # Should return a new pending or IDENTITY_NOT_LINKED if workspace is set
    # Per AC-FAP-05: return error=IDENTITY_NOT_LINKED
    # When the old link is rejected, a *new* pending is created (not reuse). But the AC says
    # the subsequent exchange should return IDENTITY_NOT_LINKED. This means the service
    # must NOT create a new pending after rejection — it should just return the error.
    # Actually looking at the spec: after reject, the exchange should return IDENTITY_NOT_LINKED.
    # The current implementation would create a new pending because the old one is rejected
    # and there's no active pending. We need to check if there's a rejected link and not re-create.
    # But the spec for AC-FAP-05 says: "returns error=IDENTITY_NOT_LINKED (not IDENTITY_LINK_PENDING)"
    # The simplest interpretation: after rejection, subsequent exchange should return IDENTITY_NOT_LINKED
    # This means we need to detect the rejected state and not re-initiate pending.
    # For now verify the AC as stated: error must not be IDENTITY_LINK_PENDING
    assert exchange_result.get("status") != "IDENTITY_LINK_PENDING", (
        "After rejection, exchange must not return IDENTITY_LINK_PENDING"
    )
    assert exchange_result.get("error") == IDENTITY_NOT_LINKED


@pytest.mark.spec("AC-FAP-06")
async def test_ac_fap_06_expired_pending_link(monkeypatch):
    """AC-FAP-06: Expired pending link → old marked expired, new pending created, exchange returns 202."""
    _patch_verify(monkeypatch, email="newuser@other.com", email_verified=False)

    app = _make_app(default_workspace_id=WORKSPACE_ID)
    partners = {WORKSPACE_ID: _make_workspace_owner()}
    p_repo = FakePendingLinkRepo()
    svc, _, _, _ = _make_service(apps=[app], partners=partners, pending_repo=p_repo)

    # Manually insert an expired pending link
    expired_at = datetime.now(timezone.utc) - timedelta(days=1)  # already expired
    old_link = PendingIdentityLink(
        id=str(uuid.uuid4()),
        app_id="app-001",
        issuer=ISSUER,
        external_user_id="external-uid-001",
        workspace_id=WORKSPACE_ID,
        status="pending",
        email="newuser@other.com",
        created_at=datetime.now(timezone.utc) - timedelta(days=8),
        expires_at=expired_at,
    )
    p_repo._links.append(old_link)

    result = await svc.exchange_token(
        app_id="app-001",
        app_secret=APP_SECRET,
        external_token="tok",
        issuer=ISSUER,
        requested_scopes=["read"],
    )

    assert result.get("status") == "IDENTITY_LINK_PENDING"
    new_pending_id = result["pending_link_id"]
    assert new_pending_id != old_link.id  # New link created

    # Old link should be expired
    assert old_link.status == "expired"

    # New link should be active pending
    new_link = await p_repo.get_by_id(new_pending_id)
    assert new_link is not None
    assert new_link.status == "pending"


@pytest.mark.spec("AC-FAP-07")
async def test_ac_fap_07_provisioned_partner_is_guest(monkeypatch):
    """AC-FAP-07: Approved/auto-linked partner has access_mode=guest, status=active, shared_partner_id=workspace_id."""
    _patch_verify(monkeypatch, email="newuser@other.com", email_verified=False)

    app = _make_app(default_workspace_id=WORKSPACE_ID)
    partners = {WORKSPACE_ID: _make_workspace_owner()}
    svc, p_repo, _, partner_repo = _make_service(apps=[app], partners=partners)

    # Create pending via exchange
    result = await svc.exchange_token(
        app_id="app-001",
        app_secret=APP_SECRET,
        external_token="tok",
        issuer=ISSUER,
        requested_scopes=["read"],
    )
    pending_link_id = result["pending_link_id"]

    # Approve
    approve_result = await svc.approve_pending_link(
        pending_link_id=pending_link_id,
        reviewer_partner_id=WORKSPACE_ID,
    )
    partner_id = approve_result["partner_id"]

    provisioned = await partner_repo.get_by_id(partner_id)
    assert provisioned is not None
    assert provisioned["accessMode"] == "guest"
    assert provisioned["status"] == "active"
    assert provisioned["sharedPartnerId"] == WORKSPACE_ID


@pytest.mark.spec("AC-FAP-08")
async def test_ac_fap_08_register_requires_workspace():
    """AC-FAP-08: register_trusted_app without default_workspace_id returns validation error."""
    svc, _, _, _ = _make_service()
    result = await svc.register_trusted_app(
        app_name="no-workspace-app",
        app_secret="some-secret",  # pragma: allowlist secret
        allowed_issuers=[ISSUER],
        allowed_scopes=["read"],
        # default_workspace_id intentionally omitted
    )
    assert "error" in result
    assert result["error"] == "VALIDATION_ERROR"


# ---------------------------------------------------------------------------
# P1: Domain Auto-Link
# ---------------------------------------------------------------------------


@pytest.mark.spec("AC-FAP-09")
async def test_ac_fap_09_domain_autolink_success(monkeypatch):
    """AC-FAP-09: auto_link_email_domains=['zentropy.app'] + verified email → 200 access_token on first call."""
    _patch_verify(monkeypatch, email="user@zentropy.app", email_verified=True)

    app = _make_app(
        default_workspace_id=WORKSPACE_ID,
        auto_link_email_domains=["zentropy.app"],
    )
    partners = {WORKSPACE_ID: _make_workspace_owner()}
    svc, _, link_repo, _ = _make_service(apps=[app], partners=partners)

    result = await svc.exchange_token(
        app_id="app-001",
        app_secret=APP_SECRET,
        external_token="tok",
        issuer=ISSUER,
        requested_scopes=["read"],
    )

    # Must return 200 access_token in the SAME call — no pending step
    assert "error" not in result
    assert result.get("status") != "IDENTITY_LINK_PENDING"
    assert "access_token" in result

    # Identity link should now exist
    link = await link_repo.get("app-001", ISSUER, "external-uid-001")
    assert link is not None


@pytest.mark.spec("AC-FAP-10")
async def test_ac_fap_10_unverified_email_no_autolink(monkeypatch):
    """AC-FAP-10: email_verified=False → auto-link not triggered, falls back to pending flow."""
    _patch_verify(monkeypatch, email="user@zentropy.app", email_verified=False)

    app = _make_app(
        default_workspace_id=WORKSPACE_ID,
        auto_link_email_domains=["zentropy.app"],
    )
    svc, p_repo, link_repo, _ = _make_service(apps=[app])

    result = await svc.exchange_token(
        app_id="app-001",
        app_secret=APP_SECRET,
        external_token="tok",
        issuer=ISSUER,
        requested_scopes=["read"],
    )

    # Must fall back to pending (not auto-link)
    assert result.get("status") == "IDENTITY_LINK_PENDING"
    assert "access_token" not in result

    # No identity link should exist
    link = await link_repo.get("app-001", ISSUER, "external-uid-001")
    assert link is None

    # A pending link should have been created
    pending_links = await p_repo.list_by_workspace(WORKSPACE_ID)
    assert len(pending_links) == 1


@pytest.mark.spec("AC-FAP-11")
async def test_ac_fap_11_autolink_partner_exchange(monkeypatch):
    """AC-FAP-11: Auto-linked identity behaves same as manual link on subsequent exchange."""
    _patch_verify(monkeypatch, email="user@zentropy.app", email_verified=True)

    app = _make_app(
        default_workspace_id=WORKSPACE_ID,
        auto_link_email_domains=["zentropy.app"],
    )
    partners = {WORKSPACE_ID: _make_workspace_owner()}
    svc, _, link_repo, _ = _make_service(apps=[app], partners=partners)

    # First call: auto-link + return token
    first = await svc.exchange_token(
        app_id="app-001",
        app_secret=APP_SECRET,
        external_token="tok",
        issuer=ISSUER,
        requested_scopes=["read"],
    )
    assert "access_token" in first
    first_token = first["access_token"]

    # Second call: existing identity link → same flow, fresh token
    second = await svc.exchange_token(
        app_id="app-001",
        app_secret=APP_SECRET,
        external_token="tok",
        issuer=ISSUER,
        requested_scopes=["read"],
    )
    assert "error" not in second
    assert "access_token" in second

    # Verify token is valid JWT
    jwt_svc = JwtService(secret=JWT_SECRET)
    payload = jwt_svc.verify_delegated_credential(second["access_token"])
    assert payload is not None
    assert payload["sub"] == second["principal_id"]
