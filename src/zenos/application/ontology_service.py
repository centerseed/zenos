"""OntologyService — orchestrates all CRUD and query use cases.

Consumes domain models, repositories, and governance/search functions.
Each public method corresponds to one MCP tool's business logic.
"""

from __future__ import annotations

import logging
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from collections import Counter

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

    @staticmethod
    def _is_concrete_impacts_description(description: str) -> bool:
        """Validate impacts text follows concrete propagation format."""
        desc = (description or "").strip()
        if not desc:
            return False
        if "→" in desc:
            left, right = desc.split("→", 1)
            return bool(left.strip()) and bool(right.strip())
        if "->" in desc:
            left, right = desc.split("->", 1)
            return bool(left.strip()) and bool(right.strip())
        return False

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
    def _tokenize_semantic_text(value: str) -> list[str]:
        """Extract coarse semantic terms for deterministic panorama hints."""
        stopwords = {
            "the", "and", "for", "with", "from", "that", "this", "into", "your",
            "zenos", "entity", "module", "product", "document", "docs", "spec",
            "系統", "功能", "文件", "模組", "產品", "設計", "流程", "相關", "說明",
            "以及", "用於", "如何", "公司", "概念", "機制", "資料", "處理", "管理",
        }
        tokens = re.findall(r"[A-Za-z0-9\u4e00-\u9fff][A-Za-z0-9\u4e00-\u9fff_\-]{1,}", value.lower())
        return [token for token in tokens if token not in stopwords and len(token) >= 2]

    @classmethod
    def _build_global_infer_context(
        cls,
        all_entities: list[Entity],
        *,
        exclude_entity_id: str | None = None,
    ) -> dict:
        """Build deterministic panorama hints so inference starts global-first."""
        scoped_entities = [e for e in all_entities if e.id != exclude_entity_id]
        non_doc_entities = [e for e in scoped_entities if e.type != EntityType.DOCUMENT]
        doc_entities = [e for e in scoped_entities if e.type == EntityType.DOCUMENT]

        entity_counts = Counter(str(ent.type) for ent in non_doc_entities)
        recurring_terms_counter: Counter[str] = Counter()
        for ent in scoped_entities:
            tags = ent.tags if isinstance(ent.tags, Tags) else None
            text_parts = [ent.name or "", ent.summary or ""]
            if tags:
                what = tags.what if isinstance(tags.what, list) else [tags.what]
                who = tags.who if isinstance(tags.who, list) else [tags.who]
                text_parts.extend([*(w for w in what if w), *(w for w in who if w), tags.why or "", tags.how or ""])
            terms = set(cls._tokenize_semantic_text(" ".join(text_parts)))
            recurring_terms_counter.update(terms)

        recurring_terms = [
            term for term, count in recurring_terms_counter.most_common()
            if count >= 2
        ][:8]

        def _line(ent: Entity) -> str:
            return f"{ent.id}|{ent.name}|{ent.summary}"

        active_products = [
            _line(ent)
            for ent in non_doc_entities
            if ent.type == EntityType.PRODUCT
        ][:4]
        active_modules = [
            _line(ent)
            for ent in non_doc_entities
            if ent.type == EntityType.MODULE
        ][:6]
        impact_target_hints = [
            _line(ent)
            for ent in non_doc_entities
            if ent.type in {EntityType.MODULE, EntityType.PRODUCT}
        ][:6]

        return {
            "entity_counts": dict(entity_counts),
            "document_count": len(doc_entities),
            "recurring_terms": recurring_terms,
            "active_products": active_products,
            "active_modules": active_modules,
            "impact_target_hints": impact_target_hints,
        }

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
            "status": entity.status,
            "level": entity.level,
            "tags": tags_dict,
        }

    async def _load_relationship_snapshot(self, entities: list[Entity]) -> list[Relationship]:
        """Load and deduplicate relationships for a context snapshot."""
        rels: list[Relationship] = []
        seen: set[str | None] = set()
        for ent in entities:
            if not ent.id:
                continue
            for rel in await self._relationships.list_by_entity(ent.id):
                key = rel.id or f"{rel.source_entity_id}:{rel.type}:{rel.target_id}:{rel.description}"
                if key in seen:
                    continue
                seen.add(key)
                rels.append(rel)
        return rels

    async def _build_infer_all_inputs(
        self,
        *,
        all_entities: list[Entity],
        exclude_entity_id: str | None = None,
    ) -> tuple[list[dict], list[dict]]:
        """Build richer, token-aware infer_all inputs.

        Includes summary/tags plus compact doc and impacts hints so LLM can infer
        concrete propagation paths without sending full documents.
        """
        entity_map = {e.id: e for e in all_entities if e.id}
        doc_entities = [e for e in all_entities if e.type == EntityType.DOCUMENT and e.id]
        non_doc_entities = [
            e for e in all_entities
            if e.type != EntityType.DOCUMENT and e.id and e.id != exclude_entity_id
        ]
        relationships = await self._load_relationship_snapshot(all_entities)

        docs_by_parent: dict[str, list[Entity]] = {}
        for doc in doc_entities:
            if not doc.parent_id:
                continue
            docs_by_parent.setdefault(doc.parent_id, []).append(doc)

        impacts_out: dict[str, list[str]] = {}
        impacts_in: dict[str, list[str]] = {}
        for rel in relationships:
            if rel.type != RelationshipType.IMPACTS:
                continue
            if not self._is_concrete_impacts_description(rel.description):
                continue
            src_name = entity_map.get(rel.source_entity_id).name if entity_map.get(rel.source_entity_id) else rel.source_entity_id
            tgt_name = entity_map.get(rel.target_id).name if entity_map.get(rel.target_id) else rel.target_id
            impacts_out.setdefault(rel.source_entity_id, []).append(
                f"{src_name} -> {tgt_name}: {rel.description}"
            )
            impacts_in.setdefault(rel.target_id, []).append(
                f"{src_name} -> {tgt_name}: {rel.description}"
            )

        entity_dicts: list[dict] = []
        for ent in non_doc_entities:
            base = self._entity_to_dict(ent)
            doc_hints = [
                f"{d.name}: {d.summary}"
                for d in docs_by_parent.get(ent.id or "", [])[:2]
            ]
            base["doc_hints"] = doc_hints
            base["impacts_to"] = impacts_out.get(ent.id or "", [])[:2]
            base["impacted_by"] = impacts_in.get(ent.id or "", [])[:2]
            entity_dicts.append(base)

        unlinked_docs = [
            d for d in doc_entities
            if exclude_entity_id is None or d.parent_id != exclude_entity_id
        ]
        unlinked_dicts = [
            {
                "id": d.id,
                "title": d.name,
                "summary": d.summary,
                "source_uri": (d.sources[0].get("uri", "") if d.sources else ""),
            }
            for d in unlinked_docs
        ]
        return entity_dicts, unlinked_dicts

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
        existing: Entity | None = None
        if data.get("id"):
            existing = await self._entities.get_by_id(data["id"])
            if existing is None:
                raise ValueError(
                    f"Entity '{data['id']}' not found. Use create without id to add a new entity."
                )

        # --- Fast path: append_sources on existing entity (skip full validation) ---
        if existing and data.get("append_sources"):
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
                existing.updated_at = datetime.now(timezone.utc)
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
        name = data.get("name", existing.name if existing else "")
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

        pre_save_inference = None

        if self._governance_ai and not data.get("type") and not existing:
            all_entities = await self._entities.list_all()
            entity_dicts, unlinked_dicts = await self._build_infer_all_inputs(
                all_entities=all_entities,
                exclude_entity_id=data.get("id"),
            )
            infer_entity_data = dict(data)
            infer_entity_data["_global_context"] = self._build_global_infer_context(
                all_entities,
                exclude_entity_id=data.get("id"),
            )

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
                inference = self._governance_ai.infer_all(
                    infer_entity_data, entity_dicts, unlinked_dicts
                )
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

        # For updates, patch on top of the existing entity instead of rebuilding
        # from sparse input. This preserves omitted fields like sources and
        # confirmed_by_user unless the caller explicitly changes them.
        merged_data = dict(data)
        if existing:
            existing_tags = existing.tags if isinstance(existing.tags, Tags) else Tags(
                what="", why="", how="", who=""
            )
            merged_tags = {
                "what": existing_tags.what,
                "why": existing_tags.why,
                "how": existing_tags.how,
                "who": existing_tags.who,
            }
            incoming_tags = merged_data.get("tags")
            if isinstance(incoming_tags, dict):
                merged_tags.update({k: v for k, v in incoming_tags.items() if v is not None})
            elif isinstance(incoming_tags, Tags):
                merged_tags = {
                    "what": incoming_tags.what,
                    "why": incoming_tags.why,
                    "how": incoming_tags.how,
                    "who": incoming_tags.who,
                }
            merged_data.setdefault("name", existing.name)
            merged_data.setdefault("type", existing.type)
            merged_data.setdefault("summary", existing.summary)
            merged_data["tags"] = merged_tags
            merged_data.setdefault("status", existing.status)
            merged_data.setdefault("parent_id", existing.parent_id)
            merged_data.setdefault("details", existing.details)
            merged_data.setdefault("level", existing.level)
            merged_data.setdefault("owner", existing.owner)
            merged_data.setdefault("sources", list(existing.sources))
            merged_data.setdefault("visibility", existing.visibility)
            merged_data.setdefault("confirmed_by_user", existing.confirmed_by_user)
            merged_data.setdefault("last_reviewed_at", existing.last_reviewed_at)

        # 2. type enum
        entity_type = merged_data.get("type", "")
        valid_types = [e.value for e in EntityType]
        if entity_type not in valid_types:
            raise ValueError(
                f"Invalid entity type '{entity_type}'. "
                f"Must be one of: {', '.join(valid_types)}"
            )

        # 3. status enum — document type allows document-specific statuses
        status = merged_data.get("status", "active")
        _DOCUMENT_STATUSES = {"current", "stale", "draft", "conflict"}
        _BASE_STATUSES = {"active", "paused", "completed", "planned"}
        if entity_type == EntityType.DOCUMENT:
            valid_statuses = sorted(_BASE_STATUSES | _DOCUMENT_STATUSES)
            # Default status for document entities
            if status == "active":
                status = "current"
                merged_data["status"] = status
        else:
            valid_statuses = sorted(_BASE_STATUSES)
        if status not in valid_statuses:
            raise ValueError(
                f"Invalid entity status '{status}'. "
                f"Must be one of: {', '.join(valid_statuses)}"
            )

        # 4. tags must have four dimensions
        tags_data = merged_data.get("tags")
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
        if entity_type == "module" and not merged_data.get("parent_id"):
            raise ValueError(
                "Module entity must have parent_id set to the owning product's entity ID. "
                "Without parent_id, the module will not appear in the Dashboard."
            )

        # 6. parent_id existence
        parent_id = merged_data.get("parent_id")
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
            inferred_parent = await self._infer_module_parent(merged_data)
            if inferred_parent and inferred_parent != merged_data.get("parent_id"):
                warnings.append(
                    f"自動推斷 parent：{merged_data.get('parent_id')} → {inferred_parent}（L3 entity 應掛在 Module 下）"
                )
                merged_data["parent_id"] = inferred_parent

        # 6c. L2 hard rule on write path: new module requires concrete impacts.
        if self._governance_ai and entity_type == EntityType.MODULE and not merged_data.get("id"):
            all_entities = await self._entities.list_all()
            entity_dicts, unlinked_dicts = await self._build_infer_all_inputs(
                all_entities=all_entities,
                exclude_entity_id=merged_data.get("id"),
            )
            infer_entity_data = dict(merged_data)
            infer_entity_data["_global_context"] = self._build_global_infer_context(
                all_entities,
                exclude_entity_id=merged_data.get("id"),
            )
            pre_save_inference = self._governance_ai.infer_all(
                infer_entity_data, entity_dicts, unlinked_dicts
            )
            inferred_concrete_impacts = bool(
                pre_save_inference
                and any(
                    rel.type == RelationshipType.IMPACTS
                    and self._is_concrete_impacts_description(rel.description)
                    for rel in pre_save_inference.rels
                )
            )
            if not inferred_concrete_impacts and not merged_data.get("force"):
                insufficient_reasons = ""
                if pre_save_inference and pre_save_inference.impacts_context_status == "insufficient":
                    reasons = [r for r in pre_save_inference.impacts_context_gaps if r]
                    if reasons:
                        insufficient_reasons = f" Context gaps: {'; '.join(reasons[:3])}."
                raise ValueError(
                    "L2 hard rule failed: candidate module has no concrete impacts "
                    "(A 改了什麼→B 的什麼要跟著看). "
                    "Please 1) add concrete impacts, 2) downgrade to L3, or 3) re-scope granularity. "
                    f"If this is an intentional manual override, set force=true.{insufficient_reasons}"
                )

        # 7. duplicate name+type check (new entity only)
        if not merged_data.get("id"):
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

        # --- Confirmed entity protection: merge-only update (unless force=true) ---
        if existing and existing.confirmed_by_user and not merged_data.get("force"):
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
                    f"Entity '{existing.name}' 已確認，僅更新空欄位（加 force=true 可覆寫）"
                )
                existing.updated_at = datetime.now(timezone.utc)
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

        tags = Tags(**merged_data["tags"]) if isinstance(merged_data.get("tags"), dict) else merged_data["tags"]
        # Handle append_sources: merge with existing sources if updating
        sources = merged_data.get("sources", [])
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
        append_sources = merged_data.get("append_sources")
        if append_sources and existing:
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
        level = (
            merged_data.get("level")
            if merged_data.get("level") is not None
            else _TYPE_TO_LEVEL.get(merged_data["type"])
        )

        if existing:
            entity = existing
            entity.name = merged_data["name"]
            entity.type = merged_data["type"]
            entity.summary = merged_data["summary"]
            entity.tags = tags
            entity.level = level
            entity.status = merged_data.get("status", existing.status)
            entity.parent_id = merged_data.get("parent_id")
            entity.details = merged_data.get("details")
            entity.confirmed_by_user = merged_data.get(
                "confirmed_by_user", existing.confirmed_by_user
            )
            entity.owner = merged_data.get("owner")
            entity.sources = sources
            entity.visibility = merged_data.get("visibility", existing.visibility)
            entity.last_reviewed_at = merged_data.get(
                "last_reviewed_at", existing.last_reviewed_at
            )
        else:
            entity = Entity(
                name=merged_data["name"],
                type=merged_data["type"],
                summary=merged_data["summary"],
                tags=tags,
                level=level,
                status=merged_data.get("status", "active"),
                id=merged_data.get("id"),
                parent_id=merged_data.get("parent_id"),
                details=merged_data.get("details"),
                confirmed_by_user=merged_data.get("confirmed_by_user", False),
                owner=merged_data.get("owner"),
                sources=sources,
                visibility=merged_data.get("visibility", "public"),
            )
        entity.updated_at = datetime.now(timezone.utc)

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
            entity_dicts, unlinked_dicts = await self._build_infer_all_inputs(
                all_entities=all_entities,
                exclude_entity_id=saved.id,
            )
            doc_entities = [e for e in all_entities if e.type == EntityType.DOCUMENT and e.id]
            infer_entity_data = self._entity_to_dict(saved)
            infer_entity_data["_global_context"] = self._build_global_infer_context(
                all_entities,
                exclude_entity_id=saved.id,
            )

            inference = pre_save_inference if pre_save_inference and not unlinked_dicts else None
            if inference is None:
                inference = self._governance_ai.infer_all(
                    infer_entity_data, entity_dicts, unlinked_dicts
                )
            if inference:
                if inference.impacts_context_status == "insufficient":
                    gaps = "; ".join((inference.impacts_context_gaps or [])[:3])
                    warnings.append(
                        "GovernanceAI impacts 推斷資訊不足"
                        + (f"：{gaps}" if gaps else "")
                    )
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
        entity.updated_at = datetime.now(timezone.utc)
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
        protocol.updated_at = datetime.now(timezone.utc)
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

        # Idempotency / dedup guard: same semantic blindspot should not be
        # re-created repeatedly (which also fan-outs duplicate tasks).
        if not data.get("id"):
            normalized_desc = " ".join(data["description"].strip().lower().split())
            normalized_action = " ".join(data["suggested_action"].strip().lower().split())
            normalized_related = sorted(
                [str(eid).strip() for eid in data.get("related_entity_ids", []) if str(eid).strip()]
            )
            same_severity = await self._blindspots.list_all(severity=data["severity"])
            for existing in same_severity:
                if existing.status == "resolved":
                    continue
                if " ".join(existing.description.strip().lower().split()) != normalized_desc:
                    continue
                if " ".join(existing.suggested_action.strip().lower().split()) != normalized_action:
                    continue
                if sorted(existing.related_entity_ids) != normalized_related:
                    continue
                return existing

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
        now = datetime.now(timezone.utc)

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
            # Backward compatibility:
            # - New behavior: item_id is protocol document ID
            # - Legacy behavior: item_id is entity_id
            protocol = await self._protocols.get_by_id(item_id)
            if protocol is None:
                protocol = await self._protocols.get_by_entity(item_id)
            if protocol is None:
                raise ValueError(f"Protocol '{item_id}' not found")
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
