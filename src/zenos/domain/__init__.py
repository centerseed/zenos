"""ZenOS Domain — re-exports all sub-package public symbols.

Import from sub-packages directly for new code:
  from zenos.domain.knowledge import Entity, EntityRepository
  from zenos.domain.action import Task, TaskRepository
  from zenos.domain.identity import PartnerRepository
  from zenos.domain.document_platform import DocRole, SourceStatus
  from zenos.domain.shared import SplitRecommendation, QualityReport

This __init__.py is kept for backward compatibility during migration.
"""

from .action import (  # noqa: F401
    Task,
    TaskPriority,
    TaskRepository,
    TaskStatus,
)
from .document_platform import (  # noqa: F401
    DocRole,
    DocStatus,
    SourceStatus,
)
from .identity import (  # noqa: F401
    CLASSIFICATION_ORDER,
    VISIBILITY_ORDER,
    Classification,
    InheritanceMode,
    PartnerRepository,
    Visibility,
)
from .knowledge import (  # noqa: F401
    Blindspot,
    BlindspotRepository,
    BlindspotStatus,
    Document,
    DocumentStatus,
    Entity,
    EntityEntry,
    EntityRepository,
    EntityStatus,
    EntityType,
    EntryStatus,
    EntryType,
    Gap,
    Protocol,
    ProtocolRepository,
    Relationship,
    RelationshipRepository,
    RelationshipType,
    Severity,
    Source,
    SourceAdapter,
    SourceType,
    Tags,
)
from .shared import (  # noqa: F401
    QualityCheckItem,
    QualityReport,
    SplitRecommendation,
    StalenessWarning,
    TagConfidence,
)
