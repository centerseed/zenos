"""ZenOS Application — Knowledge Layer.

Services responsible for ontology management, document sources,
governance rules, and AI-assisted governance inference.
"""

from .ontology_service import (
    OntologyService,
    EntityWithRelationships,
    UpsertEntityResult,
    DocumentSyncResult,
)
from .source_service import SourceService
from .governance_service import GovernanceService
from .governance_ai import (
    GovernanceAI,
    GovernanceInference,
    InferredRel,
    TaskLinkInference,
    ConsolidationMergeGroup,
    ConsolidationProposal,
)

__all__ = [
    "OntologyService",
    "EntityWithRelationships",
    "UpsertEntityResult",
    "DocumentSyncResult",
    "SourceService",
    "GovernanceService",
    "GovernanceAI",
    "GovernanceInference",
    "InferredRel",
    "TaskLinkInference",
    "ConsolidationMergeGroup",
    "ConsolidationProposal",
]
