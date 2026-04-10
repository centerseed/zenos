"""ZenOS Domain — Identity Layer Enums."""

from __future__ import annotations

from enum import Enum


class Visibility(str, Enum):
    """Entity visibility levels in SPEC-identity-and-access."""
    PUBLIC = "public"
    RESTRICTED = "restricted"
    CONFIDENTIAL = "confidential"


# Numeric order for comparison: higher = more restrictive.
VISIBILITY_ORDER: dict[str, int] = {
    "public": 0,
    "restricted": 1,
    "confidential": 2,
    # Legacy alias kept for backward-compatible reads during migration.
    "role-restricted": 1,
}


class Classification(str, Enum):
    OPEN = "open"
    INTERNAL = "internal"
    RESTRICTED = "restricted"
    CONFIDENTIAL = "confidential"


CLASSIFICATION_ORDER: dict[str, int] = {
    "open": 0,
    "internal": 1,
    "restricted": 2,
    "confidential": 3,
}


class InheritanceMode(str, Enum):
    INHERIT = "inherit"
    CUSTOM = "custom"
