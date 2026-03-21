"""ZenOS Domain Models — pure dataclasses, zero external dependencies."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


# ──────────────────────────────────────────────
# Enums
# ──────────────────────────────────────────────

class EntityType(str, Enum):
    PRODUCT = "product"
    MODULE = "module"
    GOAL = "goal"
    ROLE = "role"
    PROJECT = "project"


class EntityStatus(str, Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    PLANNED = "planned"


class RelationshipType(str, Enum):
    DEPENDS_ON = "depends_on"
    SERVES = "serves"
    OWNED_BY = "owned_by"
    PART_OF = "part_of"
    BLOCKS = "blocks"
    RELATED_TO = "related_to"


class SourceType(str, Enum):
    GITHUB = "github"
    GDRIVE = "gdrive"
    NOTION = "notion"
    UPLOAD = "upload"


class DocumentStatus(str, Enum):
    CURRENT = "current"
    STALE = "stale"
    ARCHIVED = "archived"
    DRAFT = "draft"
    CONFLICT = "conflict"


class Severity(str, Enum):
    RED = "red"
    YELLOW = "yellow"
    GREEN = "green"


class BlindspotStatus(str, Enum):
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"


# ──────────────────────────────────────────────
# Skeleton Layer (骨架層)
# ──────────────────────────────────────────────

@dataclass
class Tags:
    """Four-dimensional tag set for skeleton-layer entities."""
    what: str
    why: str
    how: str
    who: str


@dataclass
class Entity:
    """Skeleton-layer entity: product, module, goal, role, or project."""
    name: str
    type: str  # EntityType value
    summary: str
    tags: Tags
    status: str = EntityStatus.ACTIVE  # EntityStatus value
    id: str | None = None
    parent_id: str | None = None
    details: dict | None = None
    confirmed_by_user: bool = False
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class Relationship:
    """Directed edge between two skeleton-layer entities."""
    source_entity_id: str
    target_id: str
    type: str  # RelationshipType value
    description: str
    id: str | None = None
    confirmed_by_user: bool = False


# ──────────────────────────────────────────────
# Neural Layer (神經層)
# ──────────────────────────────────────────────

@dataclass
class Source:
    """Where a document lives."""
    type: str  # SourceType value
    uri: str
    adapter: str


@dataclass
class DocumentTags:
    """Four-dimensional tag set for neural-layer documents.

    what/who are lists (a doc can cover multiple topics/audiences).
    why/how are single strings.
    """
    what: list[str]
    why: str
    how: str
    who: list[str]


@dataclass
class Document:
    """Neural-layer entry: a semantic proxy for an actual file."""
    title: str
    source: Source
    tags: DocumentTags
    summary: str
    linked_entity_ids: list[str] = field(default_factory=list)
    status: str = DocumentStatus.CURRENT  # DocumentStatus value
    id: str | None = None
    confirmed_by_user: bool = False
    last_reviewed_at: datetime | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)


# ──────────────────────────────────────────────
# Protocol (View)
# ──────────────────────────────────────────────

@dataclass
class Gap:
    """A gap identified in a protocol."""
    description: str
    priority: str  # Severity value


@dataclass
class Protocol:
    """A generated context-protocol view for an entity."""
    entity_id: str
    entity_name: str
    content: dict  # { what: {}, why: {}, how: {}, who: {} }
    gaps: list[Gap] = field(default_factory=list)
    version: str = "1.0"
    id: str | None = None
    confirmed_by_user: bool = False
    generated_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)


# ──────────────────────────────────────────────
# Governance Outputs
# ──────────────────────────────────────────────

@dataclass
class Blindspot:
    """An AI-inferred blind spot in the ontology."""
    description: str
    severity: str  # Severity value
    related_entity_ids: list[str]
    suggested_action: str
    status: str = BlindspotStatus.OPEN  # BlindspotStatus value
    id: str | None = None
    confirmed_by_user: bool = False
    created_at: datetime = field(default_factory=datetime.utcnow)


# ──────────────────────────────────────────────
# Governance Result Types
# ──────────────────────────────────────────────

@dataclass
class SplitRecommendation:
    """Result of check_split_criteria."""
    should_split: bool
    reasons: list[str]
    score: int  # number of criteria met (0-5)


@dataclass
class TagConfidence:
    """Result of apply_tag_confidence."""
    confirmed_fields: list[str]  # fields AI can auto-confirm (what, who)
    draft_fields: list[str]      # fields that need human review (why, how)


@dataclass
class StalenessWarning:
    """A staleness signal detected across entities/documents."""
    pattern: str          # which detection pattern triggered
    description: str
    affected_entity_ids: list[str]
    affected_document_ids: list[str]
    suggested_action: str


@dataclass
class QualityCheckItem:
    """A single quality-check result."""
    name: str
    passed: bool
    detail: str


@dataclass
class QualityReport:
    """Aggregated quality report for an ontology instance."""
    score: int  # 0-100
    passed: list[QualityCheckItem]
    failed: list[QualityCheckItem]
    warnings: list[QualityCheckItem]
