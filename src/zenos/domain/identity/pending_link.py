"""ZenOS Domain — Pending Identity Link.

Represents a pending request for an external user to be linked to a
ZenOS workspace, awaiting owner approval (P0 Owner-Approve Flow).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass
class PendingIdentityLink:
    """A pending request to link an external identity to a ZenOS workspace.

    Lifecycle: pending → approved | rejected | expired.
    """

    id: str
    app_id: str
    issuer: str
    external_user_id: str
    workspace_id: str
    status: str = "pending"
    email: str | None = None
    reviewed_by: str | None = None
    reviewed_at: datetime | None = None
    created_at: datetime | None = None
    expires_at: datetime | None = None

    def is_pending(self) -> bool:
        return self.status == "pending"

    def is_expired(self) -> bool:
        if self.status != "pending" or self.expires_at is None:
            return False
        exp = self.expires_at if self.expires_at.tzinfo else self.expires_at.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) > exp
