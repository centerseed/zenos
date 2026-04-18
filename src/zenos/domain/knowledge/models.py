"""ZenOS Domain — Knowledge Layer Models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from .enums import DocumentStatus, EntryStatus


# ──────────────────────────────────────────────
# Skeleton Layer (骨架層)
# ──────────────────────────────────────────────

@dataclass
class Tags:
    """Four-dimensional tag set for entities.

    what/who are list[str] to support multiple topics/audiences (unified
    with the old DocumentTags format). Reading from Firestore, legacy
    string values are automatically wrapped in a list.
    """
    what: list[str] | str
    why: str
    how: str
    who: list[str] | str


@dataclass
class Entity:
    """Skeleton-layer entity: product, module, goal, role, project, or document."""
    name: str
    type: str  # EntityType value
    summary: str
    tags: Tags
    level: int | None = None  # 1=product, 2=consensus concept (module), 3=document/detail
    status: str = "active"  # EntityStatus value
    id: str | None = None
    parent_id: str | None = None
    details: dict | None = None
    confirmed_by_user: bool = False
    owner: str | None = None  # Phase 0: simple name string (e.g. "Barry")
    sources: list[dict] = field(default_factory=list)  # [{uri, label, type, source_id, ...}]
    visibility: str = "public"  # "public" | "restricted" | "confidential"
    visible_to_roles: list[str] = field(default_factory=list)
    visible_to_members: list[str] = field(default_factory=list)
    visible_to_departments: list[str] = field(default_factory=list)
    last_reviewed_at: datetime | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    # ADR-022 Document Bundle fields (only meaningful for type="document")
    doc_role: str | None = None  # DocRole value: "single" | "index"
    bundle_highlights: list[dict] = field(default_factory=list)  # [{source_id, headline, reason_to_read, priority}]
    highlights_updated_at: datetime | None = None  # When bundle_highlights was last updated
    change_summary: str | None = None  # Human-authored summary of recent doc changes
    summary_updated_at: datetime | None = None  # When change_summary was last updated
    # ADR-041 Pillar A — embedding metadata (summary_embedding itself is NOT here;
    # it is a 768-float vector fetched only via get_embeddings_by_ids / search_by_vector)
    embedded_summary_hash: str | None = None  # sha256(summary) hex, or 'EMPTY'/'FAILED' sentinel
    embedding_model: str | None = None        # e.g. "gemini/gemini-embedding-001"
    embedded_at: datetime | None = None       # UTC timestamp of last successful embed


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
    status: str = "open"  # BlindspotStatus value
    id: str | None = None
    confirmed_by_user: bool = False
    created_at: datetime = field(default_factory=datetime.utcnow)


# ──────────────────────────────────────────────
# Entity Entries (知識容器)
# ──────────────────────────────────────────────

@dataclass
class EntityEntry:
    """A structured knowledge entry attached to an L2 entity.

    Entries make an entity a knowledge container, not just an index pointer.
    Each entry captures a specific type of knowledge (decision, insight, etc.)
    with an optional context and lineage (superseded_by).
    """
    id: str
    partner_id: str
    entity_id: str
    type: str  # EntryType value
    content: str  # 1-200 chars
    status: str = "active"  # EntryStatus value
    context: str | None = None  # optional extra context, max 200 chars
    author: str | None = None
    department: str | None = None
    source_task_id: str | None = None
    superseded_by: str | None = None  # ID of the entry that supersedes this one
    archive_reason: str | None = None  # required when status='archived'; values: 'merged' | 'manual'
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
