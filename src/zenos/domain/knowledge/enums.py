"""ZenOS Domain — Knowledge Layer Enums."""

from __future__ import annotations

from enum import Enum


class EntityType(str, Enum):
    PRODUCT = "product"
    MODULE = "module"
    GOAL = "goal"
    ROLE = "role"
    PROJECT = "project"
    DOCUMENT = "document"
    COMPANY = "company"
    PERSON = "person"
    DEAL = "deal"


class EntityStatus(str, Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    PLANNED = "planned"
    ARCHIVED = "archived"
    # Document-specific statuses (only valid when type="document")
    CURRENT = "current"
    STALE = "stale"
    DRAFT = "draft"
    CONFLICT = "conflict"


class RelationshipType(str, Enum):
    DEPENDS_ON = "depends_on"
    SERVES = "serves"
    OWNED_BY = "owned_by"
    PART_OF = "part_of"
    BLOCKS = "blocks"
    RELATED_TO = "related_to"
    IMPACTS = "impacts"   # A 改了，B 必須跟著檢查
    ENABLES = "enables"   # A 存在讓 B 成為可能


class SourceType(str, Enum):
    GITHUB = "github"
    GDRIVE = "gdrive"
    NOTION = "notion"
    UPLOAD = "upload"
    WIKI = "wiki"
    URL = "url"
    ZENOS_NATIVE = "zenos_native"
    LOCAL = "local"


class DocumentStatus(str, Enum):
    CURRENT = "current"
    STALE = "stale"
    ARCHIVED = "archived"
    DRAFT = "draft"
    CONFLICT = "conflict"


class EntryType(str, Enum):
    DECISION = "decision"
    INSIGHT = "insight"
    LIMITATION = "limitation"
    CHANGE = "change"
    CONTEXT = "context"


class EntryStatus(str, Enum):
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    ARCHIVED = "archived"


class Severity(str, Enum):
    RED = "red"
    YELLOW = "yellow"
    GREEN = "green"


class BlindspotStatus(str, Enum):
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
