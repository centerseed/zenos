"""ZenOS Domain Models — pure dataclasses, zero external dependencies."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
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
    DOCUMENT = "document"
    COMPANY = "company"
    PERSON = "person"


class EntityStatus(str, Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    PLANNED = "planned"
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


class TaskStatus(str, Enum):
    TODO = "todo"
    BLOCKED = "blocked"
    IN_PROGRESS = "in_progress"
    REVIEW = "review"
    DONE = "done"
    CANCELLED = "cancelled"


class TaskPriority(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


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


@dataclass
class UserPrincipal:
    user_id: str
    partner_id: str
    role_ids: list[str] = field(default_factory=list)
    department_ids: list[str] = field(default_factory=list)
    is_admin: bool = False


@dataclass
class AgentScope:
    read_classification_max: str = Classification.OPEN.value
    write_classification_max: str = Classification.INTERNAL.value
    allowed_role_ids: list[str] = field(default_factory=list)
    allowed_department_ids: list[str] = field(default_factory=list)
    allowed_entity_ids: list[str] = field(default_factory=list)


@dataclass
class AgentPrincipal:
    agent_id: str
    owner_user_id: str
    partner_id: str
    scope: AgentScope = field(default_factory=AgentScope)


@dataclass
class AccessPolicy:
    classification: str = Classification.OPEN.value
    inheritance_mode: str = InheritanceMode.INHERIT.value
    allowed_role_ids: list[str] = field(default_factory=list)
    allowed_department_ids: list[str] = field(default_factory=list)
    allowed_member_ids: list[str] = field(default_factory=list)

    def validate_transition_from_parent(self, parent_classification: str | None) -> bool:
        if not parent_classification:
            return True
        return CLASSIFICATION_ORDER[self.classification] >= CLASSIFICATION_ORDER[parent_classification]

    def validate_custom_scope(self) -> bool:
        if self.inheritance_mode == InheritanceMode.INHERIT.value:
            return not (self.allowed_role_ids or self.allowed_department_ids or self.allowed_member_ids)
        return True


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
    status: str = EntityStatus.ACTIVE  # EntityStatus value
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
    change_summary: str | None = None  # Human-authored summary of recent doc changes
    summary_updated_at: datetime | None = None  # When change_summary was last updated


@dataclass
class Relationship:
    """Directed edge between two skeleton-layer entities."""
    source_entity_id: str
    target_id: str
    type: str  # RelationshipType value
    description: str
    id: str | None = None
    confirmed_by_user: bool = False
    verb: str | None = None


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
    weight: int = 1


@dataclass
class QualityReport:
    """Aggregated quality report for an ontology instance."""
    score: int  # 0-100
    passed: list[QualityCheckItem]
    failed: list[QualityCheckItem]
    warnings: list[QualityCheckItem]


# ──────────────────────────────────────────────
# Action Layer (任務管理)
# ──────────────────────────────────────────────

@dataclass
class Task:
    """Action Layer task: a knowledge-driven action item.

    Tasks live above the ontology layer. They reference ontology entries
    via linked_entities / linked_protocol / linked_blindspot, but have
    their own lifecycle (status, priority, assignee, due date).
    """
    title: str
    status: str  # TaskStatus value
    priority: str  # TaskPriority value
    created_by: str
    updated_by: str | None = None
    id: str | None = None
    description: str = ""
    priority_reason: str = ""
    assignee: str | None = None
    linked_entities: list[str] = field(default_factory=list)
    linked_protocol: str | None = None
    linked_blindspot: str | None = None
    source_type: str = ""
    source_metadata: dict[str, object] = field(default_factory=dict)
    context_summary: str = ""
    due_date: datetime | None = None
    assignee_role_id: str | None = None
    plan_id: str | None = None
    plan_order: int | None = None
    depends_on_task_ids: list[str] = field(default_factory=list)
    blocked_by: list[str] = field(default_factory=list)
    blocked_reason: str | None = None
    acceptance_criteria: list[str] = field(default_factory=list)
    completed_by: str | None = None
    creator_name: str | None = None
    assignee_name: str | None = None
    confirmed_by_creator: bool = False
    rejection_reason: str | None = None
    result: str | None = None
    project: str = ""  # Partner-level project grouping (e.g. "zenos", "paceriz")
    project_id: str | None = None  # Link to product/project entity ID
    attachments: list[dict] = field(default_factory=list)  # [{id, filename, content_type, gcs_path, ...}]
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: datetime | None = None


# ──────────────────────────────────────────────
# Entity Entries (知識容器)
# ──────────────────────────────────────────────

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
