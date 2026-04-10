"""Tests for JwtService — sign/verify round-trip, expiry, tamper detection."""

from __future__ import annotations

import time

import pytest

from zenos.infrastructure.identity.jwt_service import JwtService

SECRET = "test-secret-key-for-unit-tests"  # pragma: allowlist secret


@pytest.fixture
def svc() -> JwtService:
    return JwtService(secret=SECRET)


class TestSignAndVerify:
    def test_round_trip_returns_payload(self, svc: JwtService) -> None:
        token = svc.sign_delegated_credential(
            principal_id="partner-001",
            app_id="app-abc",
            workspace_ids=["ws-1", "ws-2"],
            scopes=["read"],
        )
        payload = svc.verify_delegated_credential(token)
        assert payload is not None
        assert payload["sub"] == "partner-001"
        assert payload["app_id"] == "app-abc"
        assert payload["workspace_ids"] == ["ws-1", "ws-2"]
        assert payload["scopes"] == ["read"]

    def test_token_starts_with_eyJ(self, svc: JwtService) -> None:
        """JWT format check — our middleware uses this prefix to detect JWTs."""
        token = svc.sign_delegated_credential(
            principal_id="partner-001",
            app_id="app-abc",
            workspace_ids=[],
            scopes=["read"],
        )
        assert token.startswith("eyJ")

    def test_multiple_scopes_preserved(self, svc: JwtService) -> None:
        token = svc.sign_delegated_credential(
            principal_id="p1",
            app_id="a1",
            workspace_ids=["ws-x"],
            scopes=["read", "write", "task"],
        )
        payload = svc.verify_delegated_credential(token)
        assert payload is not None
        assert set(payload["scopes"]) == {"read", "write", "task"}

    def test_custom_ttl_respected(self, svc: JwtService) -> None:
        before = int(time.time())
        token = svc.sign_delegated_credential(
            principal_id="p1",
            app_id="a1",
            workspace_ids=[],
            scopes=["read"],
            ttl=7200,
        )
        payload = svc.verify_delegated_credential(token)
        assert payload is not None
        assert payload["exp"] >= before + 7200


class TestExpiredToken:
    def test_expired_token_returns_none(self, svc: JwtService) -> None:
        """A token with ttl=0 (or already past expiry) must be rejected."""
        import jwt as pyjwt

        # Manually craft a token that expired 1 second ago
        now = int(time.time())
        payload = {
            "iss": "zenos",
            "sub": "partner-001",
            "iat": now - 10,
            "exp": now - 1,
            "app_id": "app-abc",
            "workspace_ids": [],
            "scopes": ["read"],
        }
        token = pyjwt.encode(payload, SECRET, algorithm="HS256", headers={"kid": "v1"})
        result = svc.verify_delegated_credential(token)
        assert result is None


class TestTamperedToken:
    def test_wrong_secret_returns_none(self, svc: JwtService) -> None:
        other = JwtService(secret="completely-different-secret")
        token = other.sign_delegated_credential(
            principal_id="partner-001",
            app_id="app-abc",
            workspace_ids=[],
            scopes=["read"],
        )
        result = svc.verify_delegated_credential(token)
        assert result is None

    def test_truncated_token_returns_none(self, svc: JwtService) -> None:
        token = svc.sign_delegated_credential(
            principal_id="partner-001",
            app_id="app-abc",
            workspace_ids=[],
            scopes=["read"],
        )
        result = svc.verify_delegated_credential(token[:-10])
        assert result is None

    def test_garbage_string_returns_none(self, svc: JwtService) -> None:
        result = svc.verify_delegated_credential("not-a-jwt-at-all")
        assert result is None

    def test_wrong_issuer_token_returns_none(self) -> None:
        """Token signed by our secret but with wrong issuer should be rejected."""
        import jwt as pyjwt

        now = int(time.time())
        payload = {
            "iss": "evil-issuer",
            "sub": "partner-001",
            "iat": now,
            "exp": now + 3600,
            "app_id": "app-abc",
            "workspace_ids": [],
            "scopes": ["read"],
        }
        token = pyjwt.encode(payload, SECRET, algorithm="HS256")
        svc = JwtService(secret=SECRET)
        result = svc.verify_delegated_credential(token)
        assert result is None
