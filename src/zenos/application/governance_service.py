"""GovernanceService — orchestrates ontology-wide governance checks.

Pulls data from all repositories and delegates to pure domain functions
in governance.py. Each method returns a governance result object.
"""

from __future__ import annotations

from zenos.domain.governance import (
    analyze_blindspots,
    detect_staleness,
    run_quality_check,
)
from zenos.domain.models import (
    Blindspot,
    QualityReport,
    StalenessWarning,
)
from zenos.domain.repositories import (
    BlindspotRepository,
    DocumentRepository,
    EntityRepository,
    ProtocolRepository,
    RelationshipRepository,
)


class GovernanceService:
    """Application-layer service for ontology-wide governance analysis."""

    def __init__(
        self,
        entity_repo: EntityRepository,
        document_repo: DocumentRepository,
        relationship_repo: RelationshipRepository,
        protocol_repo: ProtocolRepository,
        blindspot_repo: BlindspotRepository,
    ) -> None:
        self._entities = entity_repo
        self._documents = document_repo
        self._relationships = relationship_repo
        self._protocols = protocol_repo
        self._blindspots = blindspot_repo

    async def _load_all_relationships(self, entities: list) -> list:
        """Collect all relationships by querying each entity's relationships."""
        all_rels = []
        seen_ids: set[str | None] = set()
        for entity in entities:
            if not entity.id:
                continue
            rels = await self._relationships.list_by_entity(entity.id)
            for r in rels:
                if r.id not in seen_ids:
                    all_rels.append(r)
                    seen_ids.add(r.id)
        return all_rels

    async def run_quality_check(self) -> QualityReport:
        """Run the full 9-item quality checklist across the ontology.

        Fetches all entities, documents, protocols, blindspots, and
        relationships, then delegates to domain.governance.run_quality_check.
        """
        entities = await self._entities.list_all()
        documents = await self._documents.list_all()
        blindspots = await self._blindspots.list_all()
        relationships = await self._load_all_relationships(entities)

        # Collect all protocols
        protocols = []
        for entity in entities:
            if entity.id:
                protocol = await self._protocols.get_by_entity(entity.id)
                if protocol is not None:
                    protocols.append(protocol)

        return run_quality_check(
            entities=entities,
            documents=documents,
            protocols=protocols,
            blindspots=blindspots,
            relationships=relationships,
        )

    async def run_staleness_check(self) -> list[StalenessWarning]:
        """Detect staleness patterns across entities and documents.

        Fetches all entities, documents, and relationships, then
        delegates to domain.governance.detect_staleness.
        """
        entities = await self._entities.list_all()
        documents = await self._documents.list_all()
        relationships = await self._load_all_relationships(entities)

        return detect_staleness(
            entities=entities,
            documents=documents,
            relationships=relationships,
        )

    async def run_blindspot_analysis(self) -> list[Blindspot]:
        """Infer blind spots by cross-referencing ontology layers.

        Fetches all entities, documents, and relationships, then
        delegates to domain.governance.analyze_blindspots.
        """
        entities = await self._entities.list_all()
        documents = await self._documents.list_all()
        relationships = await self._load_all_relationships(entities)

        return analyze_blindspots(
            entities=entities,
            documents=documents,
            relationships=relationships,
        )
