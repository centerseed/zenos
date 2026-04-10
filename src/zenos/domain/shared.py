"""ZenOS Domain — Shared value objects (cross-layer).

These types are used by multiple domain layers and do not belong to any
single sub-package. They are placed here to avoid circular imports.
"""

from __future__ import annotations

from dataclasses import dataclass


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
