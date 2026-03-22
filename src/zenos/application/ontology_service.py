"""OntologyService — orchestrates all CRUD and query use cases.

Consumes domain models, repositories, and governance/search functions.
Each public method corresponds to one MCP tool's business logic.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime

from zenos.domain.governance import apply_tag_confidence, check_split_criteria
from zenos.domain.models import (
    Blindspot,
    Document,
    DocumentTags,
    Entity,
    Protocol,
    Relationship,
    Source,
    SplitRecommendation,
    TagConfidence,
    Tags,
)
from zenos.domain.repositories import (
    BlindspotRepository,
    DocumentRepository,
    EntityRepository,
    ProtocolRepository,
    RelationshipRepository,
)
from zenos.domain.search import SearchResult, search_ontology


# ──────────────────────────────────────────────
# Helper types
# ──────────────────────────────────────────────

@dataclass
class EntityWithRelationships:
    """An entity bundled with its outgoing/incoming relationships."""
    entity: Entity
    relationships: list[Relationship]


@dataclass
class UpsertEntityResult:
    """Result of upsert_entity, including optional governance advice."""
    entity: Entity
    tag_confidence: TagConfidence
    split_recommendation: SplitRecommendation | None
    warnings: list[str] | None = None


# ──────────────────────────────────────────────
# Service
# ──────────────────────────────────────────────

class OntologyService:
    """Application-layer service that orchestrates Domain + Infrastructure."""

    def __init__(
        self,
        entity_repo: EntityRepository,
        relationship_repo: RelationshipRepository,
        document_repo: DocumentRepository,
        protocol_repo: ProtocolRepository,
        blindspot_repo: BlindspotRepository,
    ) -> None:
        self._entities = entity_repo
        self._relationships = relationship_repo
        self._documents = document_repo
        self._protocols = protocol_repo
        self._blindspots = blindspot_repo

    # ──────────────────────────────────────────
    # Consumer-facing use cases (消費端)
    # ──────────────────────────────────────────

    async def get_protocol(self, entity_name: str) -> Protocol | None:
        """Retrieve the context protocol for a named entity."""
        return await self._protocols.get_by_entity_name(entity_name)

    async def list_entities(self, type_filter: str | None = None) -> list[Entity]:
        """List all entities, optionally filtered by type."""
        return await self._entities.list_all(type_filter=type_filter)

    async def get_entity(self, entity_name: str) -> EntityWithRelationships | None:
        """Get a single entity by name, together with its relationships."""
        entity = await self._entities.get_by_name(entity_name)
        if entity is None:
            return None
        relationships: list[Relationship] = []
        if entity.id:
            relationships = await self._relationships.list_by_entity(entity.id)
        return EntityWithRelationships(entity=entity, relationships=relationships)

    async def list_blindspots(
        self,
        entity_name: str | None = None,
        severity: str | None = None,
    ) -> list[Blindspot]:
        """List blindspots, optionally filtered by entity name or severity."""
        entity_id: str | None = None
        if entity_name is not None:
            entity = await self._entities.get_by_name(entity_name)
            if entity is not None and entity.id is not None:
                entity_id = entity.id
            else:
                # Entity not found — return empty rather than unfiltered
                return []
        return await self._blindspots.list_all(entity_id=entity_id, severity=severity)

    async def get_document(self, doc_id: str) -> Document | None:
        """Get a single document by ID."""
        return await self._documents.get_by_id(doc_id)

    async def search(self, query: str) -> list[SearchResult]:
        """Keyword search across entities, documents, and protocols."""
        entities = await self._entities.list_all()
        documents = await self._documents.list_all()
        protocols: list[Protocol] = []
        # Collect protocols for all entities that have one
        for entity in entities:
            if entity.id:
                protocol = await self._protocols.get_by_entity(entity.id)
                if protocol is not None:
                    protocols.append(protocol)
        return search_ontology(query, entities, documents, protocols)

    # ──────────────────────────────────────────
    # Governance-facing use cases (治理端)
    # ──────────────────────────────────────────

    async def upsert_entity(self, data: dict) -> UpsertEntityResult:
        """Create or update an entity with integrated governance logic.

        Steps:
          1. Build and persist the entity
          2. Apply tag-confidence classification
          3. Check split criteria (if entity has an ID for relationship lookup)
          4. Return entity + governance advice
        """
        tags = Tags(**data["tags"]) if isinstance(data.get("tags"), dict) else data["tags"]
        entity = Entity(
            name=data["name"],
            type=data["type"],
            summary=data["summary"],
            tags=tags,
            status=data.get("status", "active"),
            id=data.get("id"),
            parent_id=data.get("parent_id"),
            details=data.get("details"),
            confirmed_by_user=data.get("confirmed_by_user", False),
        )
        entity.updated_at = datetime.utcnow()

        saved = await self._entities.upsert(entity)

        # Governance: warn if module has no parent_id
        warnings: list[str] = []
        if saved.type == "module" and not saved.parent_id:
            warnings.append(
                "Module entity has no parent_id. "
                "It will not appear under any product in the Dashboard. "
                "Set parent_id to the owning product's entity ID."
            )

        # Governance: tag confidence
        tag_confidence = apply_tag_confidence(saved.tags)

        # Governance: split check (needs related docs + relationships)
        split_rec: SplitRecommendation | None = None
        if saved.id:
            related_docs = await self._documents.list_by_entity(saved.id)
            dependencies = await self._relationships.list_by_entity(saved.id)
            split_rec = check_split_criteria(saved, related_docs, dependencies)

        return UpsertEntityResult(
            entity=saved,
            tag_confidence=tag_confidence,
            split_recommendation=split_rec,
            warnings=warnings or None,
        )

    async def add_relationship(
        self,
        source_id: str,
        target_id: str,
        rel_type: str,
        description: str,
    ) -> Relationship:
        """Add a directed relationship between two entities."""
        rel = Relationship(
            source_entity_id=source_id,
            target_id=target_id,
            type=rel_type,
            description=description,
        )
        return await self._relationships.add(rel)

    async def upsert_document(self, data: dict) -> Document:
        """Create or update a neural-layer document entry."""
        source_data = data["source"]
        source = Source(**source_data) if isinstance(source_data, dict) else source_data
        tags_data = data["tags"]
        tags = DocumentTags(**tags_data) if isinstance(tags_data, dict) else tags_data

        doc = Document(
            title=data["title"],
            source=source,
            tags=tags,
            summary=data["summary"],
            linked_entity_ids=data.get("linked_entity_ids", []),
            status=data.get("status", "current"),
            id=data.get("id"),
            confirmed_by_user=data.get("confirmed_by_user", False),
        )
        doc.updated_at = datetime.utcnow()
        return await self._documents.upsert(doc)

    async def upsert_protocol(self, data: dict) -> Protocol:
        """Create or update a context protocol."""
        from zenos.domain.models import Gap

        gaps_data = data.get("gaps", [])
        gaps = [
            Gap(**g) if isinstance(g, dict) else g
            for g in gaps_data
        ]

        protocol = Protocol(
            entity_id=data["entity_id"],
            entity_name=data["entity_name"],
            content=data["content"],
            gaps=gaps,
            version=data.get("version", "1.0"),
            id=data.get("id"),
            confirmed_by_user=data.get("confirmed_by_user", False),
        )
        protocol.updated_at = datetime.utcnow()
        return await self._protocols.upsert(protocol)

    async def add_blindspot(self, data: dict) -> Blindspot:
        """Record a new blindspot finding."""
        blindspot = Blindspot(
            description=data["description"],
            severity=data["severity"],
            related_entity_ids=data.get("related_entity_ids", []),
            suggested_action=data["suggested_action"],
            status=data.get("status", "open"),
            id=data.get("id"),
            confirmed_by_user=data.get("confirmed_by_user", False),
        )
        return await self._blindspots.add(blindspot)

    async def confirm(self, collection: str, item_id: str) -> dict:
        """Mark an item as confirmed by user.

        Args:
            collection: one of "entities", "documents", "protocols", "blindspots"
            item_id: the document/entity ID within that collection

        Returns:
            dict with collection, id, and confirmed status.
        """
        now = datetime.utcnow()

        if collection == "entities":
            entity = await self._entities.get_by_id(item_id)
            if entity is None:
                raise ValueError(f"Entity '{item_id}' not found")
            entity.confirmed_by_user = True
            entity.updated_at = now
            await self._entities.upsert(entity)

        elif collection == "documents":
            doc = await self._documents.get_by_id(item_id)
            if doc is None:
                raise ValueError(f"Document '{item_id}' not found")
            doc.confirmed_by_user = True
            doc.updated_at = now
            await self._documents.upsert(doc)

        elif collection == "protocols":
            # Protocols are keyed by entity_id; item_id here is protocol id
            # We need to look up by entity to find the protocol.
            # Since ProtocolRepository has get_by_entity, we use item_id as entity_id.
            protocol = await self._protocols.get_by_entity(item_id)
            if protocol is None:
                raise ValueError(f"Protocol for entity '{item_id}' not found")
            protocol.confirmed_by_user = True
            protocol.updated_at = now
            await self._protocols.upsert(protocol)

        elif collection == "blindspots":
            target = await self._blindspots.get_by_id(item_id)
            if target is None:
                raise ValueError(f"Blindspot '{item_id}' not found")
            target.confirmed_by_user = True
            await self._blindspots.add(target)

        else:
            raise ValueError(
                f"Unknown collection '{collection}'. "
                f"Expected: entities, documents, protocols, blindspots"
            )

        return {
            "collection": collection,
            "id": item_id,
            "confirmed_by_user": True,
            "updated_at": now.isoformat(),
        }

    async def list_unconfirmed(self, collection: str | None = None) -> dict:
        """List all unconfirmed items, optionally filtered by collection.

        Returns:
            dict keyed by collection name, each value is a list of
            unconfirmed items in that collection.
        """
        result: dict[str, list] = {}

        collections_to_check = (
            [collection] if collection else
            ["entities", "documents", "protocols", "blindspots"]
        )

        for col in collections_to_check:
            if col == "entities":
                result["entities"] = await self._entities.list_unconfirmed()
            elif col == "documents":
                result["documents"] = await self._documents.list_unconfirmed()
            elif col == "protocols":
                result["protocols"] = await self._protocols.list_unconfirmed()
            elif col == "blindspots":
                result["blindspots"] = await self._blindspots.list_unconfirmed()
            else:
                raise ValueError(
                    f"Unknown collection '{col}'. "
                    f"Expected: entities, documents, protocols, blindspots"
                )

        return result
