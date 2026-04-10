"""ZenOS Domain — Document Platform Enums."""

from __future__ import annotations

from enum import Enum


class DocRole(str, Enum):
    """Document entity role: single file proxy vs multi-source index."""
    SINGLE = "single"
    INDEX = "index"


class SourceStatus(str, Enum):
    """Per-source URI reachability status."""
    VALID = "valid"
    STALE = "stale"
    UNRESOLVABLE = "unresolvable"


class DocStatus(str, Enum):
    """Per-source document lifecycle status (used in index bundles)."""
    DRAFT = "draft"
    APPROVED = "approved"
    SUPERSEDED = "superseded"
    ARCHIVED = "archived"
