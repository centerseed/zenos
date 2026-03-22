"""OntologyService — orchestrates all CRUD and query use cases.

Consumes domain models, repositories, and governance/search functions.
Each public method corresponds to one MCP tool's business logic.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from datetime import datetime

from zenos.domain.governance import apply_tag_confidence, check_split_criteria
from zenos.domain.models import (
    Blindspot,
    Document,
    DocumentTags,
    Entity,
    EntityStatus,
    EntityType,
    Protocol,
    Relationship,
    RelationshipType,
    Severity,
    Source,
    SourceType,
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
    # Internal helpers
    # ──────────────────────────────────────────

    @staticmethod
    def _find_similar_entities(name: str, candidates: list[Entity]) -> list[Entity]:
        """Find entities with names similar to `name`.

        Similarity rules:
        - name is a substring of candidate (or vice versa), case-insensitive
        - significant token overlap (ignoring short tokens like "AI", "v2")
        """
        name_lower = name.lower()
        name_tokens = {t for t in re.split(r'[\s\-_]+', name_lower) if len(t) > 2}

        similar: list[Entity] = []
        for ent in candidates:
            ent_lower = ent.name.lower()
            if ent_lower == name_lower:
                continue  # exact match handled by check #7

            # substring match
            if name_lower in ent_lower or ent_lower in name_lower:
                similar.append(ent)
                continue

            # token overlap (at least one significant shared token)
            ent_tokens = {t for t in re.split(r'[\s\-_]+', ent_lower) if len(t) > 2}
            if name_tokens & ent_tokens:
                similar.append(ent)

        return similar

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
          1. Validate input data
          2. Build and persist the entity
          3. Apply tag-confidence classification
          4. Check split criteria (if entity has an ID for relationship lookup)
          5. Return entity + governance advice
        """
        # --- Validation ---

        # 1. name: strip, length 2-80, no trailing parenthetical
        name = data.get("name", "")
        if isinstance(name, str):
            name = name.strip()
            data["name"] = name
        if not name or len(name) < 2 or len(name) > 80:
            raise ValueError("Entity name must be 2-80 characters.")
        if re.search(r'\([^)]+\)$', name):
            raise ValueError(
                f"Entity name '{name}' must not end with parenthetical annotation "
                f"like '(English)' or '(iOS)'. Use a clean name without parentheses."
            )

        # 2. type enum
        entity_type = data.get("type", "")
        valid_types = [e.value for e in EntityType]
        if entity_type not in valid_types:
            raise ValueError(
                f"Invalid entity type '{entity_type}'. "
                f"Must be one of: {', '.join(valid_types)}"
            )

        # 3. status enum
        status = data.get("status", "active")
        valid_statuses = [s.value for s in EntityStatus]
        if status not in valid_statuses:
            raise ValueError(
                f"Invalid entity status '{status}'. "
                f"Must be one of: {', '.join(valid_statuses)}"
            )

        # 4. tags must have four dimensions
        tags_data = data.get("tags")
        if not isinstance(tags_data, (dict, Tags)):
            raise ValueError("Tags must be a dict with keys: what, why, how, who")
        if isinstance(tags_data, dict):
            missing = [k for k in ("what", "why", "how", "who") if k not in tags_data]
            if missing:
                raise ValueError(
                    f"Tags missing required dimensions: {', '.join(missing)}. "
                    f"All four (what, why, how, who) are required."
                )

        # 5. module must have parent_id
        if entity_type == "module" and not data.get("parent_id"):
            raise ValueError(
                "Module entity must have parent_id set to the owning product's entity ID. "
                "Without parent_id, the module will not appear in the Dashboard."
            )

        # 6. parent_id existence
        parent_id = data.get("parent_id")
        if parent_id:
            parent = await self._entities.get_by_id(parent_id)
            if parent is None:
                raise ValueError(
                    f"parent_id '{parent_id}' does not exist. "
                    f"Create the parent entity first."
                )

        # 7. duplicate name+type check (new entity only)
        if not data.get("id"):
            existing = await self._entities.get_by_name(name)
            if existing and existing.type == entity_type:
                raise ValueError(
                    f"Entity '{name}' (type={entity_type}) already exists "
                    f"(id={existing.id}). To update it, provide id='{existing.id}'."
                )

            # 8. fuzzy similarity check — prevent semantically duplicate products
            all_same_type = await self._entities.list_all(type_filter=entity_type)
            similar = self._find_similar_entities(name, all_same_type)
            if similar:
                lines = [
                    f"Found {len(similar)} similar {entity_type} entity(ies). "
                    f"Are you sure '{name}' is not a duplicate?\n"
                ]
                for ent in similar:
                    modules = [
                        e for e in await self._entities.list_all(type_filter="module")
                        if e.parent_id == ent.id
                    ] if ent.type == "product" else []
                    lines.append(
                        f"  - \"{ent.name}\" (id={ent.id})\n"
                        f"    summary: {ent.summary}\n"
                        f"    tags.what: {ent.tags.what}\n"
                        f"    status: {ent.status}, confirmed: {ent.confirmed_by_user}"
                    )
                    if modules:
                        mod_names = ", ".join(m.name for m in modules[:5])
                        lines.append(f"    modules ({len(modules)}): {mod_names}")
                lines.append(
                    f"\nIf '{name}' is genuinely different, add "
                    f"force=true to data to skip this check. "
                    f"If it's the same, use id='<existing_id>' to update."
                )
                if not data.get("force"):
                    raise ValueError("\n".join(lines))

        # --- Build entity ---

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

        warnings: list[str] = []

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
        # --- Validation ---
        source = await self._entities.get_by_id(source_id)
        if source is None:
            raise ValueError(f"Source entity '{source_id}' not found. Verify the entity ID.")
        target = await self._entities.get_by_id(target_id)
        if target is None:
            raise ValueError(f"Target entity '{target_id}' not found. Verify the entity ID.")
        valid_rel_types = [r.value for r in RelationshipType]
        if rel_type not in valid_rel_types:
            raise ValueError(
                f"Invalid relationship type '{rel_type}'. "
                f"Must be one of: {', '.join(valid_rel_types)}"
            )

        rel = Relationship(
            source_entity_id=source_id,
            target_id=target_id,
            type=rel_type,
            description=description,
        )
        return await self._relationships.add(rel)

    async def upsert_document(self, data: dict) -> Document:
        """Create or update a neural-layer document entry."""
        # --- Validation ---
        source_data = data.get("source", {})
        if isinstance(source_data, dict):
            source_type = source_data.get("type", "")
            valid_source_types = [s.value for s in SourceType]
            if source_type and source_type not in valid_source_types:
                raise ValueError(
                    f"Invalid source type '{source_type}'. "
                    f"Must be one of: {', '.join(valid_source_types)}"
                )
        for eid in data.get("linked_entity_ids", []):
            entity = await self._entities.get_by_id(eid)
            if entity is None:
                raise ValueError(
                    f"Entity '{eid}' in linked_entity_ids not found. "
                    f"Verify the entity ID."
                )

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
        # --- Validation ---
        entity_id = data.get("entity_id", "")
        if entity_id:
            entity = await self._entities.get_by_id(entity_id)
            if entity is None:
                raise ValueError(
                    f"Entity '{entity_id}' not found. "
                    f"Protocol must link to an existing entity."
                )
        content = data.get("content", {})
        if isinstance(content, dict):
            missing = [k for k in ("what", "why", "how", "who") if k not in content]
            if missing:
                raise ValueError(
                    f"Protocol content missing: {', '.join(missing)}. "
                    f"Must include: what, why, how, who"
                )

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
        # --- Validation ---
        severity = data.get("severity", "")
        valid_severities = [s.value for s in Severity]
        if severity not in valid_severities:
            raise ValueError(
                f"Invalid severity '{severity}'. "
                f"Must be one of: {', '.join(valid_severities)}"
            )
        if not data.get("description", "").strip():
            raise ValueError("Blindspot description is required and cannot be empty.")
        if not data.get("suggested_action", "").strip():
            raise ValueError("Blindspot suggested_action is required and cannot be empty.")
        for eid in data.get("related_entity_ids", []):
            entity = await self._entities.get_by_id(eid)
            if entity is None:
                raise ValueError(
                    f"Entity '{eid}' in related_entity_ids not found. "
                    f"Verify the entity ID."
                )

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
