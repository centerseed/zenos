"""Tests for FederationService — exchange happy path + all error codes.

These tests use in-memory fakes (not mocks) for repositories to validate
real service logic without DB access.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any

import pytest

from zenos.domain.identity.federation import TrustedApp, IdentityLink
from zenos.application.identity.federation_service import (
    FederationService,
    INVALID_APP,
    INVALID_SECRET,
    ISSUER_NOT_ALLOWED,
    INVALID_EXTERNAL_TOKEN,
    IDENTITY_NOT_LINKED,
    APP_SUSPENDED,
    PARTNER_NOT_ACTIVATED,
    PARTNER_SUSPENDED,
    _hash_secret,
)
from zenos.infrastructure.identity.jwt_service import JwtService


# ──────────────────────────────────────────────
# In-memory fakes (no mocks)
# ──────────────────────────────────────────────

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
            app_id="new-app-id",
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
            if link.app_id == app_id and link.issuer == issuer and link.external_user_id == external_user_id:
                return link
        return None

    async def create(self, app_id: str, issuer: str, external_user_id: str, zenos_principal_id: str, email: str | None = None) -> IdentityLink:
        link = IdentityLink(
            id="new-link-id",
            app_id=app_id,
            issuer=issuer,
            external_user_id=external_user_id,
            zenos_principal_id=zenos_principal_id,
            email=email,
        )
        self._links.append(link)
        return link

    async def list_by_principal(self, zenos_principal_id: str) -> list[IdentityLink]:
        return [l for l in self._links if l.zenos_principal_id == zenos_principal_id]


class FakePartnerRepo:
    def __init__(self, partners: dict[str, dict] | None = None) -> None:
        self._partners: dict[str, dict] = dict(partners or {})

    async def get_by_id(self, partner_id: str) -> dict | None:
        return self._partners.get(partner_id)

    async def get_by_email(self, email: str) -> dict | None:
        return next((p for p in self._partners.values() if p.get("email") == email), None)


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

SECRET = "test-jwt-secret"  # pragma: allowlist secret
APP_SECRET = "super-secret-app-key"  # pragma: allowlist secret
# sha256 fallback hash (used because bcrypt is slow in tests and _check_secret falls back)
APP_SECRET_HASH = hashlib.sha256(APP_SECRET.encode()).hexdigest()


def _make_app(
    app_id: str = "app-001",
    status: str = "active",
    issuers: list[str] | None = None,
    scopes: list[str] | None = None,
) -> TrustedApp:
    return TrustedApp(
        app_id=app_id,
        app_name="test-app",
        app_secret_hash=APP_SECRET_HASH,
        allowed_issuers=issuers or ["https://securetoken.google.com/my-project"],
        allowed_scopes=scopes or ["read", "write"],
        status=status,
    )


def _make_link(
    app_id: str = "app-001",
    issuer: str = "https://securetoken.google.com/my-project",
    external_user_id: str = "firebase-uid-001",
    principal_id: str = "partner-001",
) -> IdentityLink:
    return IdentityLink(
        id="link-001",
        app_id=app_id,
        issuer=issuer,
        external_user_id=external_user_id,
        zenos_principal_id=principal_id,
    )


def _make_partner(partner_id: str = "partner-001", status: str = "active") -> dict:
    return {"id": partner_id, "status": status, "roles": [], "department": "all"}


def _make_service(
    apps: list[TrustedApp] | None = None,
    links: list[IdentityLink] | None = None,
    partners: dict[str, dict] | None = None,
) -> FederationService:
    return FederationService(
        trusted_app_repo=FakeTrustedAppRepo(apps),
        identity_link_repo=FakeIdentityLinkRepo(links),
        partner_repo=FakePartnerRepo(partners),
        jwt_service=JwtService(secret=SECRET),
    )


# ──────────────────────────────────────────────
# exchange_token — happy path
# ──────────────────────────────────────────────

class TestExchangeTokenHappyPath:
    """⚠️ 僅 mock 測試：外部 token 驗證 (_verify_external_token) 用 monkeypatch 替換。
    真實 Firebase token 驗證未在此測試中覆蓋。
    """

    @pytest.fixture(autouse=True)
    def patch_verify(self, monkeypatch) -> None:
        """Replace external token verification with a stub returning valid payload."""
        import zenos.application.identity.federation_service as svc_mod
        monkeypatch.setattr(
            svc_mod,
            "_verify_external_token",
            lambda token, issuer: {"uid": "firebase-uid-001", "email": "user@example.com"},
        )

    async def test_returns_access_token(self) -> None:
        app = _make_app()
        link = _make_link()
        partner = _make_partner()

        svc = _make_service(apps=[app], links=[link], partners={"partner-001": partner})
        result = await svc.exchange_token(
            app_id="app-001",
            app_secret=APP_SECRET,
            external_token="fake-external-token",
            issuer="https://securetoken.google.com/my-project",
            requested_scopes=["read"],
        )

        assert "error" not in result
        assert "access_token" in result
        assert result["token_type"] == "Bearer"
        assert result["expires_in"] == 3600
        assert "read" in result["scopes"]
        assert result["principal_id"] == "partner-001"

    async def test_token_is_verifiable_by_jwt_service(self) -> None:
        app = _make_app()
        link = _make_link()
        partner = _make_partner()
        jwt_svc = JwtService(secret=SECRET)

        svc = FederationService(
            trusted_app_repo=FakeTrustedAppRepo([app]),
            identity_link_repo=FakeIdentityLinkRepo([link]),
            partner_repo=FakePartnerRepo({"partner-001": partner}),
            jwt_service=jwt_svc,
        )
        result = await svc.exchange_token(
            app_id="app-001",
            app_secret=APP_SECRET,
            external_token="fake-external-token",
            issuer="https://securetoken.google.com/my-project",
            requested_scopes=["read"],
        )
        payload = jwt_svc.verify_delegated_credential(result["access_token"])
        assert payload is not None
        assert payload["sub"] == "partner-001"

    async def test_scopes_capped_by_app_allowed(self) -> None:
        """Requested scopes beyond app's allowed_scopes should be silently dropped."""
        app = _make_app(scopes=["read"])  # app only allows read
        link = _make_link()
        partner = _make_partner()

        svc = _make_service(apps=[app], links=[link], partners={"partner-001": partner})
        result = await svc.exchange_token(
            app_id="app-001",
            app_secret=APP_SECRET,
            external_token="fake-external-token",
            issuer="https://securetoken.google.com/my-project",
            requested_scopes=["read", "write", "task"],
        )
        assert "error" not in result
        assert result["scopes"] == ["read"]


# ──────────────────────────────────────────────
# exchange_token — error codes
# ──────────────────────────────────────────────

class TestExchangeTokenErrorCodes:
    @pytest.fixture(autouse=True)
    def patch_verify(self, monkeypatch) -> None:
        import zenos.application.identity.federation_service as svc_mod
        monkeypatch.setattr(
            svc_mod,
            "_verify_external_token",
            lambda token, issuer: {"uid": "firebase-uid-001"},
        )

    async def test_invalid_app_id(self) -> None:
        svc = _make_service()
        result = await svc.exchange_token(
            app_id="non-existent-app",
            app_secret=APP_SECRET,
            external_token="tok",
            issuer="https://securetoken.google.com/my-project",
            requested_scopes=["read"],
        )
        assert result["error"] == INVALID_APP

    async def test_app_suspended(self) -> None:
        app = _make_app(status="suspended")
        svc = _make_service(apps=[app])
        result = await svc.exchange_token(
            app_id="app-001",
            app_secret=APP_SECRET,
            external_token="tok",
            issuer="https://securetoken.google.com/my-project",
            requested_scopes=["read"],
        )
        assert result["error"] == APP_SUSPENDED

    async def test_invalid_secret(self) -> None:
        app = _make_app()
        svc = _make_service(apps=[app])
        result = await svc.exchange_token(
            app_id="app-001",
            app_secret="wrong-secret",  # pragma: allowlist secret
            external_token="tok",
            issuer="https://securetoken.google.com/my-project",
            requested_scopes=["read"],
        )
        assert result["error"] == INVALID_SECRET

    async def test_issuer_not_allowed(self) -> None:
        app = _make_app()
        svc = _make_service(apps=[app])
        result = await svc.exchange_token(
            app_id="app-001",
            app_secret=APP_SECRET,
            external_token="tok",
            issuer="https://evil.example.com/",
            requested_scopes=["read"],
        )
        assert result["error"] == ISSUER_NOT_ALLOWED

    async def test_invalid_external_token(self, monkeypatch) -> None:
        import zenos.application.identity.federation_service as svc_mod
        monkeypatch.setattr(svc_mod, "_verify_external_token", lambda token, issuer: None)
        app = _make_app()
        svc = _make_service(apps=[app])
        result = await svc.exchange_token(
            app_id="app-001",
            app_secret=APP_SECRET,
            external_token="bad-token",
            issuer="https://securetoken.google.com/my-project",
            requested_scopes=["read"],
        )
        assert result["error"] == INVALID_EXTERNAL_TOKEN

    async def test_identity_not_linked(self) -> None:
        app = _make_app()
        svc = _make_service(apps=[app], links=[])  # no links
        result = await svc.exchange_token(
            app_id="app-001",
            app_secret=APP_SECRET,
            external_token="tok",
            issuer="https://securetoken.google.com/my-project",
            requested_scopes=["read"],
        )
        assert result["error"] == IDENTITY_NOT_LINKED

    async def test_partner_not_activated(self) -> None:
        app = _make_app()
        link = _make_link()
        partner = _make_partner(status="invited")
        svc = _make_service(apps=[app], links=[link], partners={"partner-001": partner})
        result = await svc.exchange_token(
            app_id="app-001",
            app_secret=APP_SECRET,
            external_token="tok",
            issuer="https://securetoken.google.com/my-project",
            requested_scopes=["read"],
        )
        assert result["error"] == PARTNER_NOT_ACTIVATED

    async def test_partner_suspended(self) -> None:
        app = _make_app()
        link = _make_link()
        partner = _make_partner(status="suspended")
        svc = _make_service(apps=[app], links=[link], partners={"partner-001": partner})
        result = await svc.exchange_token(
            app_id="app-001",
            app_secret=APP_SECRET,
            external_token="tok",
            issuer="https://securetoken.google.com/my-project",
            requested_scopes=["read"],
        )
        assert result["error"] == PARTNER_SUSPENDED

    async def test_partner_not_found_returns_not_activated(self) -> None:
        app = _make_app()
        link = _make_link()
        svc = _make_service(apps=[app], links=[link], partners={})  # partner missing
        result = await svc.exchange_token(
            app_id="app-001",
            app_secret=APP_SECRET,
            external_token="tok",
            issuer="https://securetoken.google.com/my-project",
            requested_scopes=["read"],
        )
        assert result["error"] == PARTNER_NOT_ACTIVATED


# ──────────────────────────────────────────────
# Admin operations
# ──────────────────────────────────────────────

class TestAdminOperations:
    async def test_create_identity_link(self) -> None:
        app = _make_app()
        svc = _make_service(apps=[app])
        result = await svc.create_identity_link(
            app_id="app-001",
            issuer="https://securetoken.google.com/my-project",
            external_user_id="firebase-uid-999",
            zenos_principal_id="partner-999",
            email="test@example.com",
        )
        assert "error" not in result
        assert result["external_user_id"] == "firebase-uid-999"
        assert result["zenos_principal_id"] == "partner-999"
        assert result["email"] == "test@example.com"

    async def test_create_identity_link_invalid_app(self) -> None:
        svc = _make_service()
        result = await svc.create_identity_link(
            app_id="non-existent",
            issuer="https://securetoken.google.com/my-project",
            external_user_id="uid",
            zenos_principal_id="partner-001",
        )
        assert result["error"] == INVALID_APP

    async def test_register_trusted_app(self) -> None:
        svc = _make_service()
        result = await svc.register_trusted_app(
            app_name="new-app",
            app_secret="some-secret",  # pragma: allowlist secret
            allowed_issuers=["https://securetoken.google.com/proj"],
            allowed_scopes=["read"],
            default_workspace_id="workspace-001",
        )
        assert "error" not in result
        assert result["app_name"] == "new-app"
        assert "app_id" in result
        assert result["allowed_scopes"] == ["read"]
        assert result["default_workspace_id"] == "workspace-001"

    async def test_register_trusted_app_requires_workspace_id(self) -> None:
        """AC-FAP-08: register_trusted_app without default_workspace_id returns validation error."""
        svc = _make_service()
        result = await svc.register_trusted_app(
            app_name="no-workspace-app",
            app_secret="some-secret",  # pragma: allowlist secret
            allowed_issuers=["https://securetoken.google.com/proj"],
            allowed_scopes=["read"],
        )
        assert result["error"] == "VALIDATION_ERROR"
