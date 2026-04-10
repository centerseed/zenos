"""ZenOS Infrastructure — JWT Service for delegated credentials.

ADR-029: signs and verifies HS256 JWTs for the Auth Federation Runtime.
Secret loaded from ZENOS_JWT_SECRET environment variable.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any

import jwt

logger = logging.getLogger(__name__)

_KID = "v1"
_ALGORITHM = "HS256"
_ISSUER = "zenos"


class JwtService:
    """Signs and verifies ZenOS delegated credentials (HS256 JWTs)."""

    def __init__(self, secret: str | None = None) -> None:
        self._secret = secret or os.environ.get("ZENOS_JWT_SECRET", "")
        if not self._secret:
            logger.warning("ZENOS_JWT_SECRET is not set — JWT signing will fail at runtime")

    def sign_delegated_credential(
        self,
        principal_id: str,
        app_id: str,
        workspace_ids: list[str],
        scopes: list[str],
        ttl: int = 3600,
    ) -> str:
        """Sign a delegated JWT for the given principal.

        Args:
            principal_id: The ZenOS partner/principal ID being delegated.
            app_id: The trusted app that initiated the exchange.
            workspace_ids: Workspaces the credential is valid for.
            scopes: Federation scopes granted (read/write/task).
            ttl: Token lifetime in seconds (default 3600).

        Returns:
            Signed JWT string.
        """
        now = int(time.time())
        payload: dict[str, Any] = {
            "iss": _ISSUER,
            "sub": principal_id,
            "iat": now,
            "exp": now + ttl,
            "app_id": app_id,
            "workspace_ids": workspace_ids,
            "scopes": scopes,
        }
        headers = {"kid": _KID}
        return jwt.encode(payload, self._secret, algorithm=_ALGORITHM, headers=headers)

    def verify_delegated_credential(self, token: str) -> dict | None:
        """Verify and decode a delegated JWT.

        Returns:
            Decoded payload dict on success, None on any failure.
        """
        try:
            payload = jwt.decode(
                token,
                self._secret,
                algorithms=[_ALGORITHM],
                issuer=_ISSUER,
                options={"require": ["exp", "iat", "sub", "app_id"]},
            )
            return payload
        except jwt.ExpiredSignatureError:
            logger.debug("JWT expired")
            return None
        except jwt.InvalidTokenError as exc:
            logger.debug("JWT invalid: %s", exc)
            return None
