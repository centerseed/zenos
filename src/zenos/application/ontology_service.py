"""OntologyService — orchestrates all CRUD and query use cases.

Consumes domain models, repositories, and governance/search functions.
Each public method corresponds to one MCP tool's business logic.
"""

from __future__ import annotations

import logging
import re
from dataclasses import asdict, dataclass
from datetime import datetime

logger = logging.getLogger(__name__)

from zenos.domain.governance import apply_tag_confidence, check_split_criteria
from zenos.domain.models import (
    Blindspot,
    Document,
    DocumentStatus,
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
        governance_ai: object | None = None,
    ) -> None:
        self._entities = entity_repo
        self._relationships = relationship_repo
        self._documents = document_repo
        self._protocols = protocol_repo
        self._blindspots = blindspot_repo
        self._governance_ai = governance_ai

    # ──────────────────────────────────────────
    # Internal helpers
    # ──────────────────────────────────────────

    async def _infer_module_parent(self, entity_data: dict) -> str | None:
        """For L3 entities, if parent_id points to a Product or is null,
        try to find the best matching Module by comparing tags.what overlap.

        Returns the inferred module ID, or the original parent_id if no
        better match is found.
        """
        parent_id = entity_data.get("parent_id")

        # Check if parent is already a module — no change needed
        if parent_id:
            parent = await self._entities.get_by_id(parent_id)
            if parent and parent.type == "module":
                return parent_id

        # parent_id is either null or points to a product (L1)
        product_id = parent_id  # may be None or a product ID

        # Get all modules
        modules = await self._entities.list_all(type_filter="module")
        if not modules:
            return parent_id  # no modules exist, can't infer

        # If we know the product, filter modules to that product only
        if product_id:
            modules = [m for m in modules if m.parent_id == product_id]
            if not modules:
                return parent_id  # no modules under this product

        # Extract keywords from entity's tags.what
        tags_data = entity_data.get("tags", {})
        if isinstance(tags_data, Tags):
            entity_what = tags_data.what
        elif isinstance(tags_data, dict):
            entity_what = tags_data.get("what", "")
        else:
            entity_what = ""

        if isinstance(entity_what, list):
            entity_keywords = set(w.lower() for w in entity_what if w)
        elif isinstance(entity_what, str) and entity_what:
            entity_keywords = set(entity_what.lower().split())
        else:
            entity_keywords = set()

        # Also include words from entity name
        entity_name = entity_data.get("name", "")
        if entity_name:
            entity_keywords |= set(
                t.lower() for t in re.split(r'[\s\-_]+', entity_name) if len(t) > 1
            )

        best_module = None
        best_score = 0

        for module in modules:
            module_what = module.tags.what if module.tags else ""
            if isinstance(module_what, list):
                module_keywords = set(w.lower() for w in module_what if w)
            elif isinstance(module_what, str) and module_what:
                module_keywords = set(module_what.lower().split())
            else:
                module_keywords = set()

            # Also match against module name tokens
            if module.name:
                module_keywords |= set(
                    t.lower() for t in re.split(r'[\s\-_]+', module.name) if len(t) > 1
                )

            overlap = len(entity_keywords & module_keywords)
            if overlap > best_score:
                best_score = overlap
                best_module = module

        if best_module and best_score > 0:
            return best_module.id

        # Fallback: if product_id known, pick first module under that product
        if product_id and modules:
            return modules[0].id

        return parent_id  # give up, return original

    async def _find_product_ancestor(self, entity: Entity) -> Entity | None:
        """Walk the parentId chain upward to find the product ancestor."""
        visited: set[str] = set()
        current = entity
        while current:
            if current.type == EntityType.PRODUCT:
                return current
            if current.id in visited or not current.parent_id:
                return None
            visited.add(current.id or "")
            current = await self._entities.get_by_id(current.parent_id)
        return None

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

    @staticmethod
    def _entity_to_dict(entity: Entity) -> dict:
        """Convert an Entity to a plain dict for GovernanceAI consumption."""
        tags = entity.tags
        tags_dict = (
            {"what": tags.what, "why": tags.why, "how": tags.how, "who": tags.who}
            if isinstance(tags, Tags)
            else tags
        )
        return {
            "id": entity.id,
            "name": entity.name,
            "type": entity.type,
            "parent_id": entity.parent_id,
            "summary": entity.summary,
            "tags": tags_dict,
        }

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

    async def get_document(self, doc_id: str) -> Entity | None:
        """Get a single document entity by ID."""
        entity = await self._entities.get_by_id(doc_id)
        if entity is not None and entity.type == EntityType.DOCUMENT:
            return entity
        # Fallback: try legacy documents collection
        return await self._documents.get_by_id(doc_id)

    async def search(self, query: str) -> list[SearchResult]:
        """Keyword search across entities, documents, and protocols."""
        entities = await self._entities.list_all()
        # Document entities are included in entities list (type="document")
        # Also fetch legacy documents for backward compat
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
        # --- Fast path: append_sources on existing entity (skip full validation) ---
        if data.get("id") and data.get("append_sources"):
            existing = await self._entities.get_by_id(data["id"])
            if existing:
                append_sources = data["append_sources"]
                existing_uris = {s.get("uri") for s in existing.sources}
                added = 0
                for s in append_sources:
                    if s.get("uri") not in existing_uris:
                        existing.sources.append(s)
                        added += 1
                if data.get("owner") and not existing.owner:
                    existing.owner = data["owner"]
                if added > 0:
                    existing.updated_at = datetime.utcnow()
                    saved = await self._entities.upsert(existing)
                    tag_confidence = apply_tag_confidence(saved.tags)
                    return UpsertEntityResult(
                        entity=saved,
                        tag_confidence=tag_confidence,
                        split_recommendation=None,
                        warnings=[f"追加 {added} 個 sources 到 '{existing.name}'"],
                    )
                return UpsertEntityResult(
                    entity=existing,
                    tag_confidence=apply_tag_confidence(existing.tags),
                    split_recommendation=None,
                    warnings=["所有 sources 已存在，跳過"],
                )

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

        # --- GovernanceAI: auto-classify if caller omitted type ---
        warnings: list[str] = []

        if self._governance_ai and not data.get("type"):
            all_entities = await self._entities.list_all()
            entity_dicts = [
                self._entity_to_dict(e)
                for e in all_entities
                if e.type != EntityType.DOCUMENT
            ]

            # Step 1: Rule-based classification (no LLM)
            rule_type, rule_parent = self._governance_ai._rule_classify(
                data["name"], entity_dicts
            )
            if rule_type:
                data["type"] = rule_type
                if rule_parent:
                    data["parent_id"] = rule_parent
                warnings.append(f"規則分類：type={rule_type}, parent={rule_parent}")
            else:
                # Step 2: LLM classification via infer_all (classify-only, pre-save)
                inference = self._governance_ai.infer_all(data, entity_dicts, [])
                if inference:
                    if inference.duplicate_of:
                        warnings.append(
                            f"GovernanceAI 判斷此 entity 與 '{inference.duplicate_of}' 語意重複"
                        )
                        existing_dup = await self._entities.get_by_id(inference.duplicate_of)
                        if existing_dup:
                            tag_confidence = apply_tag_confidence(existing_dup.tags)
                            return UpsertEntityResult(
                                entity=existing_dup,
                                tag_confidence=tag_confidence,
                                split_recommendation=None,
                                warnings=warnings,
                            )
                    if inference.type:
                        data["type"] = inference.type
                        warnings.append(f"GovernanceAI 推薦 type='{inference.type}'")
                    if inference.parent_id and not data.get("parent_id"):
                        data["parent_id"] = inference.parent_id
                        warnings.append(f"GovernanceAI 推薦 parent_id='{inference.parent_id}'")
                else:
                    warnings.append("GovernanceAI 推斷失敗，已退回規則/手動路徑")

        # 2. type enum
        entity_type = data.get("type", "")
        valid_types = [e.value for e in EntityType]
        if entity_type not in valid_types:
            raise ValueError(
                f"Invalid entity type '{entity_type}'. "
                f"Must be one of: {', '.join(valid_types)}"
            )

        # 3. status enum — document type allows document-specific statuses
        status = data.get("status", "active")
        _DOCUMENT_STATUSES = {"current", "stale", "draft", "conflict"}
        _BASE_STATUSES = {"active", "paused", "completed", "planned"}
        if entity_type == EntityType.DOCUMENT:
            valid_statuses = sorted(_BASE_STATUSES | _DOCUMENT_STATUSES)
            # Default status for document entities
            if status == "active":
                status = "current"
                data["status"] = status
        else:
            valid_statuses = sorted(_BASE_STATUSES)
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

        # 6b. Auto-infer module parent for L3 entities
        l3_types = {"document", "goal", "role", "project"}
        if entity_type in l3_types:
            inferred_parent = await self._infer_module_parent(data)
            if inferred_parent and inferred_parent != data.get("parent_id"):
                warnings.append(
                    f"自動推斷 parent：{data.get('parent_id')} → {inferred_parent}（L3 entity 應掛在 Module 下）"
                )
                data["parent_id"] = inferred_parent

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

        # --- Confirmed entity protection: merge-only update ---
        if data.get("id"):
            existing = await self._entities.get_by_id(data["id"])
            if existing and existing.confirmed_by_user:
                for field_name in ("summary", "status", "parent_id", "level"):
                    existing_val = getattr(existing, field_name, None)
                    new_val = data.get(field_name)
                    if new_val and not existing_val:
                        setattr(existing, field_name, new_val)
                # Merge tags: only fill empty tag fields
                if isinstance(data.get("tags"), dict) and isinstance(existing.tags, Tags):
                    for dim in ("what", "why", "how", "who"):
                        if data["tags"].get(dim) and not getattr(existing.tags, dim, ""):
                            setattr(existing.tags, dim, data["tags"][dim])
                if data.get("details") and not existing.details:
                    existing.details = data["details"]
                if data.get("owner") and not existing.owner:
                    existing.owner = data["owner"]
                # append_sources always works on confirmed entities (additive, not overwrite)
                append_sources = data.get("append_sources")
                if append_sources:
                    existing_uris = {s.get("uri") for s in existing.sources}
                    for s in append_sources:
                        if s.get("uri") not in existing_uris:
                            existing.sources.append(s)
                warnings.append(
                    f"Entity '{existing.name}' 已確認，僅更新空欄位"
                )
                existing.updated_at = datetime.utcnow()
                saved = await self._entities.upsert(existing)
                tag_confidence = apply_tag_confidence(saved.tags)
                split_rec: SplitRecommendation | None = None
                if saved.id:
                    related_docs = await self._entities.list_by_parent(saved.id)
                    dependencies = await self._relationships.list_by_entity(saved.id)
                    split_rec = check_split_criteria(saved, related_docs, dependencies)
                return UpsertEntityResult(
                    entity=saved,
                    tag_confidence=tag_confidence,
                    split_recommendation=split_rec,
                    warnings=warnings or None,
                )

        # --- Build entity ---

        tags = Tags(**data["tags"]) if isinstance(data.get("tags"), dict) else data["tags"]
        # Handle append_sources: merge with existing sources if updating
        sources = data.get("sources", [])
        # Dedup sources by URI
        if sources:
            seen_uris: set[str] = set()
            deduped: list[dict] = []
            for s in sources:
                uri = s.get("uri", "")
                if uri and uri not in seen_uris:
                    seen_uris.add(uri)
                    deduped.append(s)
                elif not uri:
                    deduped.append(s)
            sources = deduped
        append_sources = data.get("append_sources")
        if append_sources and data.get("id"):
            existing = await self._entities.get_by_id(data["id"])
            if existing:
                existing_uris = {s.get("uri") for s in existing.sources}
                sources = list(existing.sources)
                for s in append_sources:
                    if s.get("uri") not in existing_uris:
                        sources.append(s)

        # Auto-set level based on type; caller-provided level takes precedence.
        _TYPE_TO_LEVEL: dict[str, int] = {
            EntityType.PRODUCT: 1,
            EntityType.MODULE: 2,
            EntityType.DOCUMENT: 3,
            EntityType.GOAL: 3,
            EntityType.ROLE: 3,
            EntityType.PROJECT: 3,
        }
        level = data.get("level") if data.get("level") is not None else _TYPE_TO_LEVEL.get(data["type"])

        entity = Entity(
            name=data["name"],
            type=data["type"],
            summary=data["summary"],
            tags=tags,
            level=level,
            status=data.get("status", "active"),
            id=data.get("id"),
            parent_id=data.get("parent_id"),
            details=data.get("details"),
            confirmed_by_user=data.get("confirmed_by_user", False),
            owner=data.get("owner"),
            sources=sources,
            visibility=data.get("visibility", "public"),
        )
        entity.updated_at = datetime.utcnow()

        saved = await self._entities.upsert(entity)

        # Governance: tag confidence
        tag_confidence = apply_tag_confidence(saved.tags)

        # Governance: split check (needs related docs + relationships)
        split_rec = None
        if saved.id:
            related_docs = await self._entities.list_by_parent(saved.id)
            dependencies = await self._relationships.list_by_entity(saved.id)
            split_rec = check_split_criteria(saved, related_docs, dependencies)

        # --- GovernanceAI: unified inference (rels + doc links) ---
        if self._governance_ai and saved.id:
            all_entities = await self._entities.list_all()
            # Keep infer_all context focused on non-document entities.
            entity_dicts = [
                self._entity_to_dict(e)
                for e in all_entities
                if e.id != saved.id and e.type != EntityType.DOCUMENT
            ]

            # Find unlinked document entities (no parent_id pointing to saved entity)
            doc_entities = [
                e for e in all_entities
                if e.type == EntityType.DOCUMENT and e.id and e.parent_id != saved.id
            ]
            unlinked_dicts = [{"id": e.id, "title": e.name} for e in doc_entities]

            inference = self._governance_ai.infer_all(
                self._entity_to_dict(saved), entity_dicts, unlinked_dicts
            )
            if inference:
                # Handle duplicate (post-save detection)
                if inference.duplicate_of:
                    warnings.append(
                        f"GovernanceAI 判斷此 entity 與 '{inference.duplicate_of}' 語意重複"
                    )

                # Auto relationships
                for rel in inference.rels:
                    try:
                        rel_desc = (rel.description or "").strip()
                        await self.add_relationship(
                            source_id=saved.id,
                            target_id=rel.target,
                            rel_type=rel.type,
                            description=rel_desc or "auto-inferred",
                        )
                        warnings.append(
                            f"GovernanceAI 自動建立關係：{saved.name} → {rel.target} ({rel.type})"
                        )
                    except Exception as exc:
                        logger.warning("GovernanceAI auto-relationship failed: %s", exc)

                # Auto document links: create relationships instead of updating linked_entity_ids
                for doc_id in inference.doc_links:
                    doc_ent = next((e for e in doc_entities if e.id == doc_id), None)
                    if doc_ent and doc_ent.id:
                        try:
                            await self.add_relationship(
                                source_id=doc_ent.id,
                                target_id=saved.id,
                                rel_type=RelationshipType.RELATED_TO,
                                description="auto-linked document",
                            )
                            warnings.append(
                                f"GovernanceAI 自動連結文件 '{doc_ent.name}' → entity '{saved.name}'"
                            )
                        except Exception as exc:
                            logger.warning("GovernanceAI auto-doc-link failed: %s", exc)
            else:
                warnings.append("GovernanceAI 關聯推斷失敗，未自動建立關係")

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
        """Add a directed relationship between two entities.

        Dedup: if a relationship with the same source, target, and type
        already exists, return the existing one instead of creating a new one.
        """
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

        # --- Cross-product guard for auto-inferred related_to ---
        if (
            rel_type == RelationshipType.RELATED_TO
            and description.startswith("auto-inferred")
        ):
            source_product = await self._find_product_ancestor(source)
            target_product = await self._find_product_ancestor(target)
            if (
                source_product is not None
                and target_product is not None
                and source_product.id != target_product.id
            ):
                logger.info(
                    "Skipping cross-product auto-inferred related_to: "
                    "%s (%s) -> %s (%s)",
                    source.name, source_product.name,
                    target.name, target_product.name,
                )
                # Return a synthetic relationship without persisting
                return Relationship(
                    source_entity_id=source_id,
                    target_id=target_id,
                    type=rel_type,
                    description=description,
                )

        # --- Dedup check ---
        existing = await self._relationships.find_duplicate(source_id, target_id, rel_type)
        if existing is not None:
            return existing

        rel = Relationship(
            source_entity_id=source_id,
            target_id=target_id,
            type=rel_type,
            description=description,
        )
        return await self._relationships.add(rel)

    async def upsert_document(self, data: dict) -> Entity:
        """Create or update a document as an entity(type="document").

        Accepts the legacy document format (title, source, linked_entity_ids)
        and maps it to the unified Entity model:
          - title → name
          - source → sources[0]
          - linked_entity_ids[0] → parent_id (primary), rest → relationships
          - tags (DocumentTags format) → Tags (unified list format)
        """
        # --- Validation ---
        source_data = data.get("source", {})
        source_uri = ""
        if isinstance(source_data, dict):
            source_type = source_data.get("type", "")
            source_uri = str(source_data.get("uri", "")).strip()
            valid_source_types = [s.value for s in SourceType]
            if source_type and source_type not in valid_source_types:
                raise ValueError(
                    f"Invalid source type '{source_type}'. "
                    f"Must be one of: {', '.join(valid_source_types)}"
                )

        # Server-side idempotency: dedup by source URI for document entities.
        if source_uri and not data.get("id"):
            all_doc_entities = await self._entities.list_all(type_filter=EntityType.DOCUMENT)
            for d in all_doc_entities:
                if any(str(s.get("uri", "")).strip() == source_uri for s in (d.sources or [])):
                    data["id"] = d.id
                    break

        linked_entity_ids = data.get("linked_entity_ids", [])
        for eid in linked_entity_ids:
            entity = await self._entities.get_by_id(eid)
            if entity is None:
                raise ValueError(
                    f"Entity '{eid}' in linked_entity_ids not found. "
                    f"Verify the entity ID."
                )

        # --- GovernanceAI: auto-link to entities if caller didn't specify ---
        if not linked_entity_ids and self._governance_ai:
            all_entities = await self._entities.list_all()
            if all_entities:
                entity_dicts = [
                    {"id": e.id, "name": e.name, "type": e.type}
                    for e in all_entities if e.id
                ]
                inferred = self._governance_ai.infer_doc_entities(
                    data["title"], data["summary"], entity_dicts
                )
                valid_ids = {e.id for e in all_entities}
                linked_entity_ids = [eid for eid in inferred if eid in valid_ids]

        # Map fields to entity format
        parent_id = linked_entity_ids[0] if linked_entity_ids else data.get("parent_id")
        related_ids = linked_entity_ids[1:] if len(linked_entity_ids) > 1 else []

        # Build sources list from legacy source field
        sources: list[dict] = []
        if source_data and isinstance(source_data, dict):
            sources = [{
                "uri": source_data.get("uri", ""),
                "label": source_data.get("adapter", ""),
                "type": source_data.get("type", ""),
            }]

        # Build unified Tags from legacy DocumentTags format
        tags_data = data.get("tags", {})
        if isinstance(tags_data, dict):
            tags = Tags(
                what=tags_data.get("what", []),
                why=tags_data.get("why", ""),
                how=tags_data.get("how", ""),
                who=tags_data.get("who", []),
            )
        else:
            tags = tags_data

        entity = Entity(
            name=data["title"],
            type=EntityType.DOCUMENT,
            summary=data["summary"],
            tags=tags,
            status=data.get("status", "current"),
            id=data.get("id"),
            parent_id=parent_id,
            sources=sources,
            confirmed_by_user=data.get("confirmed_by_user", False),
        )
        entity.updated_at = datetime.utcnow()
        saved = await self._entities.upsert(entity)

        # Create relationships for additional linked entities
        if saved.id and related_ids:
            for rel_eid in related_ids:
                try:
                    await self.add_relationship(
                        source_id=saved.id,
                        target_id=rel_eid,
                        rel_type=RelationshipType.RELATED_TO,
                        description="document linked to entity",
                    )
                except Exception as exc:
                    logger.warning("Auto-relationship for document entity failed: %s", exc)

        return saved

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
            # Try entity(type=document) first, fallback to legacy documents
            entity = await self._entities.get_by_id(item_id)
            if entity is not None and entity.type == EntityType.DOCUMENT:
                entity.confirmed_by_user = True
                entity.updated_at = now
                await self._entities.upsert(entity)
            else:
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
                # Include both document entities and legacy documents
                doc_entities = [
                    e for e in await self._entities.list_unconfirmed()
                    if e.type == EntityType.DOCUMENT
                ]
                legacy_docs = await self._documents.list_unconfirmed()
                result["documents"] = doc_entities + legacy_docs
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
