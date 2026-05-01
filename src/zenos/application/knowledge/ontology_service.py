"""OntologyService — orchestrates all CRUD and query use cases.

Consumes domain models, repositories, and governance/search functions.
Each public method corresponds to one MCP tool's business logic.
"""

from __future__ import annotations

import logging
import re
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from collections import Counter

logger = logging.getLogger(__name__)

from zenos.domain.governance import apply_tag_confidence, check_split_criteria, find_tech_terms_in_summary
from zenos.domain.validation import find_similar_items
from zenos.domain.source_uri_validator import (
    validate_source_uri,
    validate_external_id_format,
    BARE_DOMAIN_BLACKLIST,
)
from zenos.domain.doc_types import (
    canonical_type as compute_canonical_type,
    ensure_source_ids,
    expand_for_search,
    generate_source_id,
    is_known_doc_type,
)
from zenos.infrastructure.github_adapter import parse_github_url, GitHubAdapter
from zenos.domain.knowledge import Blindspot, Document, DocumentStatus, Entity, EntityStatus, EntityType, Protocol, Relationship, RelationshipType, Severity, Source, SourceType, Tags
from zenos.domain.shared import SplitRecommendation, TagConfidence
from zenos.domain.knowledge import BlindspotRepository, EntityRepository, ProtocolRepository, RelationshipRepository
from zenos.domain.knowledge.entity_levels import DEFAULT_TYPE_LEVELS, default_level_for_type
from zenos.domain.knowledge.collaboration_roots import is_collaboration_root_entity
from zenos.domain.search import SearchResult, search_ontology
from zenos.domain.partner_access import describe_partner_access, is_guest, is_unassigned_partner
from zenos.application.identity.source_access_policy import entity_has_visible_source


# ──────────────────────────────────────────────
# Helper Ingest Contract constants
# ──────────────────────────────────────────────

SNAPSHOT_SUMMARY_MAX_BYTES = 10_240  # 10 KB — semantic discipline, not just tech limit
_VALID_CONTENT_ACCESS = {"summary", "full", "none"}


class SnapshotTooLargeError(ValueError):
    """Raised when snapshot_summary exceeds the 10 KB hard limit.

    snapshot_summary is a helper-distilled semantic summary, NOT a raw mirror.
    The 10 KB limit enforces meaningful compression by the helper.
    """
    pass


def _assert_snapshot_size(snapshot: str | bytes) -> None:
    """Raise SnapshotTooLargeError if snapshot_summary exceeds the size limit."""
    size = len(snapshot.encode("utf-8")) if isinstance(snapshot, str) else len(snapshot)
    if size > SNAPSHOT_SUMMARY_MAX_BYTES:
        raise SnapshotTooLargeError(
            f"snapshot_summary 是摘要不是 mirror，請先在 helper 端 distill。"
            f"（大小 {size} bytes 超過上限 {SNAPSHOT_SUMMARY_MAX_BYTES} bytes）"
        )


def _validate_source_access_fields(source_data: dict) -> None:
    retrieval_mode = source_data.get("retrieval_mode")
    if retrieval_mode is not None:
        normalized = str(retrieval_mode).strip().lower()
        if normalized not in {"direct", "snapshot", "per_user_live"}:
            raise ValueError("retrieval_mode must be one of: direct, snapshot, per_user_live")

    content_access = source_data.get("content_access")
    if content_access is not None:
        normalized = str(content_access).strip().lower()
        if normalized not in _VALID_CONTENT_ACCESS:
            raise ValueError("content_access must be one of: summary, full, none")


def _validate_document_source_uri(source: dict, *, context: str = "source") -> None:
    source_type = str(source.get("type", "") or "").strip()
    source_uri = str(source.get("uri", "") or "").strip()
    if source_type and source_uri:
        is_valid, error_msg = validate_source_uri(source_type, source_uri)
        if not is_valid:
            raise ValueError(f"Invalid source URI for {context}: {error_msg}")


# ──────────────────────────────────────────────
# Helper types
# ──────────────────────────────────────────────

@dataclass
class EntityWithRelationships:
    """An entity bundled with its outgoing/incoming relationships."""
    entity: Entity
    relationships: list[Relationship]


def _bundle_source_status(source: dict) -> str:
    """Return the effective status for a bundle source.

    ADR-022 introduced `source_status` but some paths still write `status`.
    Treat them as aliases here so reads stay stable during migration.
    """
    return str(source.get("source_status") or source.get("status") or "valid")


def _sync_bundle_source_status(source: dict, status: str) -> None:
    """Write both legacy and canonical status keys for a bundle source."""
    source["status"] = status
    source["source_status"] = status


def _bundle_highlight_priority(source: dict) -> str:
    """Return deterministic priority for a bundle source."""
    if bool(source.get("is_primary")):
        return "primary"

    doc_type = str(source.get("doc_type", "")).strip().upper()
    if doc_type in {"SPEC", "DECISION", "CONTRACT"}:
        return "primary"
    if doc_type in {"DESIGN", "TEST", "PLAN"}:
        return "important"
    return "supporting"


def _bundle_highlight_headline(source: dict) -> str:
    """Use label as deterministic headline when it is meaningfully descriptive."""
    label = str(source.get("label", "")).strip()
    source_type = str(source.get("type", "")).strip()
    if not label:
        return ""
    if source_type and label.lower() == source_type.lower():
        return ""
    return label


def _build_bundle_highlights_suggestion(
    sources: list[dict],
    existing_highlights: list[dict] | None,
    candidate_source_ids: list[str] | None,
) -> dict | None:
    """Build deterministic highlight suggestions for missing source-linked entries."""
    if not candidate_source_ids:
        return None

    candidate_set = {
        str(source_id).strip()
        for source_id in candidate_source_ids
        if str(source_id).strip()
    }
    if not candidate_set:
        return None

    existing_source_ids = {
        str(item.get("source_id", "")).strip()
        for item in (existing_highlights or [])
        if isinstance(item, dict)
    }
    items: list[dict] = []
    for source in sources:
        if not isinstance(source, dict):
            continue
        source_id = str(source.get("source_id", "")).strip()
        if not source_id or source_id not in candidate_set or source_id in existing_source_ids:
            continue
        items.append({
            "source_id": source_id,
            "headline": _bundle_highlight_headline(source),
            "reason_to_read": "",
            "priority": _bundle_highlight_priority(source),
        })

    if not items:
        return None

    return {
        "type": "bundle_highlights_suggestion",
        "items": items,
    }


@dataclass
class UpsertEntityResult:
    """Result of upsert_entity, including optional governance advice."""
    entity: Entity
    tag_confidence: TagConfidence
    split_recommendation: SplitRecommendation | None
    warnings: list[str] | None = None
    similar_items: list[dict] | None = None


@dataclass
class DocumentSyncResult:
    """Result of a document-governance sync operation."""
    operation: str
    dry_run: bool
    document_id: str
    before: dict
    after: dict
    relationship_changes: dict
    warnings: list[str] | None = None
    document: Entity | None = None


class DocumentLinkageValidationError(ValueError):
    """Structured validation error for document linked_entity_ids contract."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        missing_entity_ids: list[str] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.missing_entity_ids = missing_entity_ids or []


def _build_ancestors(entity_id: str, entity_map: dict[str, Entity], max_depth: int = 5) -> list[dict]:
    """Build ancestor chain for an entity, from direct parent up to max_depth levels.

    Returns a list of ancestor dicts ordered from direct parent (index 0) to furthest ancestor.
    Each dict: {"id": str, "name": str, "type": str, "level": int | None}
    Stops early if parent_id is missing, not found in entity_map, or a cycle is detected.
    """
    ancestors: list[dict] = []
    current_id = entity_id
    seen: set[str] = {current_id}

    for _ in range(max_depth):
        entity = entity_map.get(current_id)
        if entity is None or not entity.parent_id:
            break
        parent_id = entity.parent_id
        if parent_id in seen:
            break  # cycle guard
        parent = entity_map.get(parent_id)
        if parent is None:
            break
        ancestors.append({
            "id": parent.id,
            "name": parent.name,
            "type": parent.type,
            "level": parent.level,
        })
        seen.add(parent_id)
        current_id = parent_id

    return ancestors


def _find_product_root(entity_id: str, entity_map: dict[str, Entity]) -> str | None:
    """Walk parent_id chain up to the L1 product root.

    Returns the root entity's ID (which may equal entity_id if it IS an L1 product).
    Returns None only if entity is orphaned (no parent chain reaches an L1).
    Used by governance auto-link scoping to prevent cross-product contamination.
    """
    visited: set[str] = set()
    current_id: str | None = entity_id
    while current_id and current_id not in visited:
        visited.add(current_id)
        ent = entity_map.get(current_id)
        if ent is None:
            return None
        if (ent.level or 0) == 1:
            return current_id
        if not ent.parent_id:
            return None
        current_id = ent.parent_id
    return None


def _collect_subtree_ids(root_id: str, entity_map: dict[str, Entity]) -> set[str]:
    """Return the set of entity IDs that belong to a product subtree.

    Includes the root itself and any entity whose parent_id chain leads to it.
    Uses iterative BFS to avoid stack overflow on deep trees.
    """
    ids: set[str] = {root_id}
    # Build parent -> children index
    children: dict[str, list[str]] = {}
    for eid, e in entity_map.items():
        if e.parent_id:
            children.setdefault(e.parent_id, []).append(eid)
    # BFS
    queue = [root_id]
    while queue:
        current = queue.pop(0)
        for child_id in children.get(current, []):
            if child_id not in ids:
                ids.add(child_id)
                queue.append(child_id)
    return ids


# ──────────────────────────────────────────────
# Service
# ──────────────────────────────────────────────

class OntologyService:
    """Application-layer service that orchestrates Domain + Infrastructure."""

    def __init__(
        self,
        entity_repo: EntityRepository,
        relationship_repo: RelationshipRepository,
        document_repo: object | None = None,  # deprecated, ignored; docs are entity-backed
        protocol_repo: ProtocolRepository | None = None,
        blindspot_repo: BlindspotRepository | None = None,
        governance_ai: object | None = None,
        source_adapter: GitHubAdapter | None = None,
        embedding_service: object | None = None,
    ) -> None:
        self._entities = entity_repo
        self._relationships = relationship_repo
        self._protocols = protocol_repo
        self._blindspots = blindspot_repo
        self._governance_ai = governance_ai
        self._source_adapter = source_adapter
        self._embedding_service = embedding_service

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

    @staticmethod
    def _coerce_bool_like(value: object, field_name: str) -> bool:
        """Coerce common bool-like payloads into bool, else raise clear error."""
        if isinstance(value, bool):
            return value
        if isinstance(value, int) and value in (0, 1):
            return bool(value)
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"true", "1"}:
                return True
            if normalized in {"false", "0"}:
                return False
        raise ValueError(
            f"layer_decision.{field_name} must be boolean "
            "(accepted: true/false, 1/0, 'true'/'false', '1'/'0')."
        )

    @staticmethod
    def _canonical_visibility(value: object) -> str:
        raw = str(value or "public").strip().lower()
        if raw == "role-restricted":
            return "restricted"
        if raw not in {"public", "restricted", "confidential"}:
            raise ValueError("visibility must be one of: public, restricted, confidential")
        return raw

    @staticmethod
    def is_entity_visible_for_partner(
        entity: Entity,
        partner: dict,
        entity_map: "dict[str, Entity] | None" = None,
    ) -> bool:
        """Determine if a partner can see a given entity based on visibility rules.

        Args:
            entity: The entity to check visibility for.
            partner: Partner dict with keys: isAdmin, id, roles, authorizedEntityIds.
            entity_map: Optional full entity map for L1 scope checking (scoped partners).

        Returns:
            True if the partner has access, False otherwise.
        """
        access = describe_partner_access(partner)

        if not entity_has_visible_source(entity, partner):
            return False

        if access["is_owner"]:
            return True

        if is_unassigned_partner(partner):
            return False

        authorized_ids = list(partner.get("authorizedEntityIds") or [])

        if access["is_guest"]:
            # Guest: check authorized L1 subtree, then public-only visibility.
            if entity_map is not None:
                allowed: set[str] = set()
                for l1_id in authorized_ids:
                    allowed |= _collect_subtree_ids(l1_id, entity_map)
                if entity.id not in allowed:
                    return False
            elif not authorized_ids:
                return False
            return OntologyService._canonical_visibility(entity.visibility) == "public"

        # Member: can see public + restricted, but not confidential.
        visibility = OntologyService._canonical_visibility(entity.visibility)
        return visibility in ("public", "restricted")

    @classmethod
    def _normalize_layer_decision(cls, layer_decision: object) -> dict:
        """Normalize layer_decision payload into canonical dict with bool flags."""
        if isinstance(layer_decision, str):
            try:
                layer_decision = json.loads(layer_decision)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    "layer_decision must be an object; JSON string provided but parse failed."
                ) from exc

        if not isinstance(layer_decision, dict):
            raise ValueError(
                f"layer_decision must be an object, got {type(layer_decision).__name__}."
            )

        required_keys = (
            "q1_persistent",
            "q2_cross_role",
            "q3_company_consensus",
        )
        missing = [k for k in required_keys if k not in layer_decision]
        if missing:
            raise ValueError(
                f"layer_decision missing required fields: {', '.join(missing)}."
            )

        normalized = dict(layer_decision)
        normalized["q1_persistent"] = cls._coerce_bool_like(
            layer_decision.get("q1_persistent"), "q1_persistent"
        )
        normalized["q2_cross_role"] = cls._coerce_bool_like(
            layer_decision.get("q2_cross_role"), "q2_cross_role"
        )
        normalized["q3_company_consensus"] = cls._coerce_bool_like(
            layer_decision.get("q3_company_consensus"), "q3_company_consensus"
        )

        impacts_draft = layer_decision.get("impacts_draft")
        if impacts_draft is None:
            normalized["impacts_draft"] = ""
        elif isinstance(impacts_draft, str):
            normalized["impacts_draft"] = impacts_draft
        elif isinstance(impacts_draft, list):
            normalized["impacts_draft"] = "\n".join(
                str(item).strip() for item in impacts_draft if str(item).strip()
            )
        else:
            normalized["impacts_draft"] = str(impacts_draft)
        return normalized

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
        """Walk the parentId chain upward to find the L1 collaboration root ancestor."""
        visited: set[str] = set()
        current = entity
        while current:
            if is_collaboration_root_entity(current):
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
        scope_entity_id: str | None = None,
    ) -> dict:
        """Build deterministic panorama hints so inference starts global-first.

        DF-20260419-3 F6 fix: when scope_entity_id is given and maps to an L1
        product root, `active_products / active_modules / impact_target_hints`
        are filtered to that subtree, so the LLM prompt cannot propose links
        pointing at unrelated products.
        """
        allowed_ids: set[str] | None = None
        if scope_entity_id:
            emap = {e.id: e for e in all_entities if e.id}
            product_root = _find_product_root(scope_entity_id, emap)
            if product_root:
                allowed_ids = _collect_subtree_ids(product_root, emap)

        def _in_scope(e: Entity) -> bool:
            if allowed_ids is None:
                return True
            return e.id in allowed_ids if e.id else False

        scoped_entities = [e for e in all_entities if e.id != exclude_entity_id and _in_scope(e)]
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
            # Defensive normalization: legacy/dirty tag payloads may include non-str items
            # (e.g. nested list values), which would break " ".join(...).
            normalized_parts: list[str] = []
            for part in text_parts:
                if not part:
                    continue
                if isinstance(part, list):
                    normalized_parts.extend(str(item) for item in part if item)
                else:
                    normalized_parts.append(str(part))
            terms = set(cls._tokenize_semantic_text(" ".join(normalized_parts)))
            recurring_terms_counter.update(terms)

        recurring_terms = [
            term for term, count in recurring_terms_counter.most_common()
            if count >= 2
        ][:8]

        def _line(ent: Entity) -> str:
            return f"{ent.id}|{ent.name}|{ent.summary}"

        # UI label judgment: filtering by EntityType for display context sent to GovernanceAI.
        # Not a business gate — these labels guide the AI's context, not access control.
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
            "visibility": entity.visibility,
            "visible_to_roles": list(entity.visible_to_roles),
            "visible_to_members": list(entity.visible_to_members),
            "visible_to_departments": list(entity.visible_to_departments),
        }

    @staticmethod
    def _normalize_linked_entity_ids(raw: object) -> list[str]:
        """Normalize linked_entity_ids into canonical list[str]."""
        if raw is None:
            return []

        if isinstance(raw, list):
            normalized: list[str] = []
            for item in raw:
                if item is None:
                    continue
                if not isinstance(item, (str, int)):
                    raise ValueError("linked_entity_ids must be list[str] or JSON array string")
                value = str(item).strip()
                if value:
                    normalized.append(value)
            return list(dict.fromkeys(normalized))

        if isinstance(raw, str):
            text = raw.strip()
            if not text:
                return []
            if text.startswith("["):
                try:
                    parsed = json.loads(text)
                except json.JSONDecodeError as exc:
                    raise ValueError("linked_entity_ids JSON string is invalid") from exc
                if not isinstance(parsed, list):
                    raise ValueError("linked_entity_ids JSON string must decode to list[str]")
                return OntologyService._normalize_linked_entity_ids(parsed)
            return [text]

        raise ValueError("linked_entity_ids must be list[str] or JSON array string")

    async def _validate_document_linked_entity_ids(self, raw: object) -> list[str]:
        """Enforce the required document linkage contract."""
        linked_entity_ids = self._normalize_linked_entity_ids(raw)
        if not linked_entity_ids:
            raise DocumentLinkageValidationError(
                "LINKED_ENTITY_IDS_REQUIRED",
                "linked_entity_ids 為必填；請先 search(collection='entities') 找到合法 entity IDs 後再寫入 document。",
            )

        missing_entity_ids: list[str] = []
        for eid in linked_entity_ids:
            entity = await self._entities.get_by_id(eid)
            if entity is None:
                missing_entity_ids.append(eid)

        if missing_entity_ids:
            raise DocumentLinkageValidationError(
                "LINKED_ENTITY_NOT_FOUND",
                "linked_entity_ids 包含不存在的 entity ID；請確認後重試。",
                missing_entity_ids=missing_entity_ids,
            )

        return linked_entity_ids

    async def _load_document_linkage_state(self, doc_id: str) -> tuple[str | None, list[str]]:
        """Return (primary_parent_id, related_entity_ids) from relationships."""
        rels = await self._relationships.list_by_entity(doc_id)
        outgoing = [r for r in rels if r.source_entity_id == doc_id]
        parent_rel = next(
            (
                r for r in outgoing
                if r.type == RelationshipType.PART_OF
                and r.description == "document primary linkage"
            ),
            None,
        )
        related_ids = [
            r.target_id
            for r in outgoing
            if r.type == RelationshipType.RELATED_TO
            and r.description == "document linked to entity"
        ]
        return (parent_rel.target_id if parent_rel else None, list(dict.fromkeys(related_ids)))

    async def _remove_relationship(self, source_id: str, target_id: str, rel_type: str) -> bool:
        """Best-effort relationship removal for repos that implement deletion."""
        remover = getattr(self._relationships, "remove", None)
        if remover is None:
            return False
        removed = await remover(source_id, target_id, rel_type)
        return bool(removed)

    async def remove_orphaned_relationships(self) -> dict:
        """Find and delete relationships pointing to non-existent entities.

        Returns:
            dict with keys "removed" (list of orphaned rel dicts) and "count" (int).
        """
        list_all_rels = getattr(self._relationships, "list_all", None)
        if list_all_rels is None:
            return {"removed": [], "count": 0}

        all_relationships = await list_all_rels()
        all_entities = await self._entities.list_all()
        entity_ids: set[str] = {e.id for e in all_entities if e.id}

        removed = []
        for rel in all_relationships:
            source_missing = rel.source_entity_id not in entity_ids
            target_missing = rel.target_id not in entity_ids
            if source_missing or target_missing:
                success = await self._remove_relationship(
                    rel.source_entity_id, rel.target_id, rel.type
                )
                if success:
                    removed.append({
                        "source_entity_id": rel.source_entity_id,
                        "target_id": rel.target_id,
                        "type": rel.type,
                        "reason": (
                            "source_missing" if source_missing else "target_missing"
                        ),
                    })
        return {"removed": removed, "count": len(removed)}

    async def _sync_document_linkage_relationships(
        self,
        *,
        doc_id: str,
        parent_id: str | None,
        related_ids: list[str],
        remove_stale: bool = True,
    ) -> dict:
        """Keep materialized linkage relationships consistent with parent_id."""
        before_parent, before_related = await self._load_document_linkage_state(doc_id)
        desired_related = list(dict.fromkeys([eid for eid in related_ids if eid and eid != parent_id]))
        changes = {
            "added": [],
            "removed": [],
        }

        if parent_id:
            existing = await self._relationships.find_duplicate(doc_id, parent_id, RelationshipType.PART_OF)
            if existing is None:
                await self.add_relationship(
                    source_id=doc_id,
                    target_id=parent_id,
                    rel_type=RelationshipType.PART_OF,
                    description="document primary linkage",
                )
                changes["added"].append({"target_id": parent_id, "type": RelationshipType.PART_OF})

        for rid in desired_related:
            existing = await self._relationships.find_duplicate(doc_id, rid, RelationshipType.RELATED_TO)
            if existing is None:
                await self.add_relationship(
                    source_id=doc_id,
                    target_id=rid,
                    rel_type=RelationshipType.RELATED_TO,
                    description="document linked to entity",
                )
                changes["added"].append({"target_id": rid, "type": RelationshipType.RELATED_TO})

        if remove_stale:
            if before_parent and before_parent != parent_id:
                removed = await self._remove_relationship(doc_id, before_parent, RelationshipType.PART_OF)
                if removed:
                    changes["removed"].append({"target_id": before_parent, "type": RelationshipType.PART_OF})
            stale_related = [rid for rid in before_related if rid not in desired_related]
            for rid in stale_related:
                removed = await self._remove_relationship(doc_id, rid, RelationshipType.RELATED_TO)
                if removed:
                    changes["removed"].append({"target_id": rid, "type": RelationshipType.RELATED_TO})

        return changes

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
        scope_entity_id: str | None = None,
    ) -> tuple[list[dict], list[dict]]:
        """Build richer, token-aware infer_all inputs.

        Includes summary/tags plus compact doc and impacts hints so LLM can infer
        concrete propagation paths without sending full documents.

        If scope_entity_id is provided, candidates are filtered to the same
        L1 product subtree (DF-20260419-2 F6 fix: prevent cross-subtree
        auto-link contamination). Entities without a product root are excluded
        from scoped inference entirely; cross-product relationships must be
        authored explicitly.
        """
        entity_map = {e.id: e for e in all_entities if e.id}

        # Determine subtree scope if requested
        allowed_ids: set[str] | None = None
        if scope_entity_id:
            product_root = _find_product_root(scope_entity_id, entity_map)
            if product_root:
                allowed_ids = _collect_subtree_ids(product_root, entity_map)

        def _in_scope(e: Entity) -> bool:
            if allowed_ids is None:
                return True
            return e.id in allowed_ids if e.id else False

        doc_entities = [
            e for e in all_entities
            if e.type == EntityType.DOCUMENT and e.id and _in_scope(e)
        ]
        # UI label judgment: filtering skeleton (L1/L2) entities by type label for
        # context payload sent to GovernanceAI. Not a business gate.
        skeleton_entities = [
            e for e in all_entities
            if e.type in (EntityType.PRODUCT, EntityType.MODULE)
            and e.id and e.id != exclude_entity_id and _in_scope(e)
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
        for ent in skeleton_entities:
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
        return None

    async def search(
        self,
        query: str,
        *,
        max_level: int | None = None,
        product_id: str | None = None,
    ) -> list[SearchResult]:
        """Keyword search across entities, documents, and protocols.

        Archived document entities (dead links confirmed unresolvable) are excluded
        from the default search space per the source governance spec.

        Args:
            max_level: If set, only include entities with level <= max_level.
            product_id: If set, only include entities that belong to the given
                        product subtree (the product itself or any entity whose
                        parent_id chain leads to it).
        """
        all_entities = await self._entities.list_all()
        # Exclude archived document entities — they have been removed due to unresolvable dead links
        entities = [
            e for e in all_entities
            if not (e.type == "document" and e.status == "archived")
        ]

        # Build full entity map for ancestor traversal (from all_entities, not filtered)
        full_entity_map = {e.id: e for e in all_entities if e.id}

        # Filter by product subtree if requested
        if product_id is not None:
            product_ids = _collect_subtree_ids(product_id, full_entity_map)
            entities = [e for e in entities if e.id in product_ids]

        # Document entities are already included in entities list (type="document")
        documents: list[Document] = []
        protocols: list[Protocol] = []
        # Collect protocols for all entities that have one
        for entity in entities:
            if entity.id:
                protocol = await self._protocols.get_by_entity(entity.id)
                if protocol is not None:
                    protocols.append(protocol)
        # ADR-022 D2: Transparent doc_type search expansion.
        # If the query matches a known doc_type (legacy or new), expand the query
        # to also match its aliases. E.g., "ADR" → search for "ADR" and "DECISION".
        expanded_query = query
        query_upper = query.strip().upper()
        from zenos.domain.doc_types import expand_for_search, DOC_TYPE_ALIASES, VALID_DOC_TYPES
        all_known_types = set(VALID_DOC_TYPES) | set(DOC_TYPE_ALIASES.keys()) | {"SC"}
        if query_upper in all_known_types:
            expanded_types = expand_for_search(query_upper)
            if len(expanded_types) > 1:
                # Search with multiple type keywords joined by space (OR semantics in tokenizer)
                expanded_query = " ".join(expanded_types)

        results = search_ontology(expanded_query, entities, documents, protocols, max_level=max_level)

        # Fill ancestors for entity results
        for result in results:
            if result.type == "entity" and result.id:
                result.ancestors = _build_ancestors(result.id, full_entity_map)

        return results

    # ──────────────────────────────────────────
    # Governance-facing use cases (治理端)
    # ──────────────────────────────────────────

    # ── L2/L3 type constants for write guard ──
    # NOTE: type whitelist for L1 was removed (ADR-047 S03). L1 is now determined by level,
    # not by a type whitelist. See _enforce_guest_write_guard.
    _L2_TYPES: frozenset[str] = frozenset({"module"})
    _L3_TYPES: frozenset[str] = frozenset({"document", "goal", "role", "project"})
    _MODULE_SCOPED_L3_TYPES: frozenset[str] = frozenset({"document", "role", "project"})

    async def _enforce_guest_write_guard(self, data: dict, partner: dict) -> None:
        """Enforce write restrictions for guest partners.

        Rules:
        - L1 entity creation → always rejected for guests. L1 is determined by
          level==1 (explicit) or by DEFAULT_TYPE_LEVELS fallback (ADR-047 D2).
        - L2 entity creation → always rejected for guests.
        - L3 entity creation → allowed only when parent_id is within the guest's
          authorized L1 subtree. If no parent_id is provided the guard also rejects,
          because we cannot verify scope membership.
        - After passing the guard, data["visibility"] is forced to "public".

        Raises:
            PermissionError: When the guest violates any of the above rules.
        """
        entity_type = str(data.get("type", "")).strip()
        explicit_level = data.get("level")

        # L1: always rejected — level-based, not type-whitelist (ADR-047 S03)
        is_l1 = (
            explicit_level == 1
            or (explicit_level is None and default_level_for_type(entity_type) == 1)
        )
        if is_l1:
            raise PermissionError(
                f"Guest partners cannot create L1 entities (type='{entity_type}'). "
                "Only member or owner roles may create top-level entities."
            )

        # L2: always rejected
        if entity_type in self._L2_TYPES:
            raise PermissionError(
                f"Guest partners cannot create L2 entities (type='{entity_type}'). "
                "Only member or owner roles may create module-level entities."
            )

        # L3: must have parent_id within authorized subtree
        if entity_type in self._L3_TYPES:
            parent_id = data.get("parent_id")
            access = describe_partner_access(partner)
            authorized_l1_ids = access["authorized_l1_ids"]

            if not parent_id:
                raise PermissionError(
                    "Guest partners must provide parent_id when creating L3 entities. "
                    "The parent must be within your authorized scope."
                )

            # Build the guest's allowed subtree from their authorized L1 ids
            all_entities_list = await self._entities.list_all()
            entity_map: dict[str, Entity] = {
                e.id: e for e in (all_entities_list or []) if e.id
            }
            allowed: set[str] = set()
            for l1_id in authorized_l1_ids:
                allowed |= _collect_subtree_ids(l1_id, entity_map)

            if parent_id not in allowed:
                raise PermissionError(
                    f"Guest partners cannot create entities under parent '{parent_id}'. "
                    "The parent entity is outside your authorized scope."
                )

            # Force visibility=public for guest-created L3 entities
            data["visibility"] = "public"

    async def upsert_entity(self, data: dict, partner: dict | None = None) -> UpsertEntityResult:
        """Create or update an entity with integrated governance logic.

        Steps:
          1. Guest write guard (if partner provided)
          2. Validate input data
          3. Build and persist the entity
          4. Apply tag-confidence classification
          5. Check split criteria (if entity has an ID for relationship lookup)
          6. Return entity + governance advice

        Args:
            data: Entity field dict (name, type, summary, tags, etc.)
            partner: Optional partner dict for write guard enforcement.
                     When provided and partner is a guest, L1/L2 creation
                     is rejected and L3 creation requires an authorized parent.
        """
        # ── Guest write guard (application-layer, server-side enforcement) ──
        if partner is not None and is_guest(partner):
            await self._enforce_guest_write_guard(data, partner)

        allow_create_with_id = bool(data.get("allow_create_with_id"))
        existing: Entity | None = None
        if data.get("id"):
            existing = await self._entities.get_by_id(data["id"])
            if existing is None and not allow_create_with_id:
                raise ValueError(
                    f"Entity '{data['id']}' not found. Use create without id to add a new entity."
                )

        # --- Fast path: append_sources on existing entity (skip full validation) ---
        # Only use fast path when append_sources is the ONLY mutation requested.
        # If caller also provides name/summary/tags/type changes, fall through
        # to the full update path so those fields are not silently ignored.
        _FIELD_MUTATIONS = {"name", "summary", "tags", "type", "status", "parent_id", "level", "owner", "force"}
        _has_field_mutations = existing and any(
            k in data and data[k] != getattr(existing, k, None)
            for k in _FIELD_MUTATIONS
            if k in data
        )
        if existing and data.get("append_sources") and not _has_field_mutations:
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
            merged_data.setdefault("visible_to_roles", list(existing.visible_to_roles))
            merged_data.setdefault("visible_to_members", list(existing.visible_to_members))
            merged_data.setdefault("visible_to_departments", list(existing.visible_to_departments))
            merged_data.setdefault("confirmed_by_user", existing.confirmed_by_user)
            merged_data.setdefault("last_reviewed_at", existing.last_reviewed_at)

        if "visibility" in merged_data:
            merged_data["visibility"] = self._canonical_visibility(merged_data["visibility"])

        # 2. type enum
        entity_type = merged_data.get("type", "")
        valid_types = [e.value for e in EntityType]
        if entity_type not in valid_types:
            raise ValueError(
                f"Invalid entity type '{entity_type}'. "
                f"Must be one of: {', '.join(valid_types)}"
            )

        # 3. status enum — document type allows document-specific statuses;
        # module (L2) type also allows draft and stale for lifecycle state machine.
        status = merged_data.get("status", "active")
        _DOCUMENT_STATUSES = {"current", "stale", "draft", "conflict", "archived"}
        _BASE_STATUSES = {"active", "paused", "completed", "planned"}
        # DF-20260419-L2d: add "archived" as explicit L2 end-of-life state so
        # consumers can deprecate a module without deleting it. Cascade is
        # not automatic — caller is expected to consolidate/manual-archive
        # entries first (warning is emitted when archiving an L2 with active
        # entries, see upsert_entity post-save checks).
        _L2_EXTRA_STATUSES = {"draft", "stale", "archived"}
        if entity_type == EntityType.DOCUMENT:
            valid_statuses = sorted(_BASE_STATUSES | _DOCUMENT_STATUSES)
            # Default status for document entities
            if status == "active":
                status = "current"
                merged_data["status"] = status
        elif entity_type == EntityType.MODULE:
            valid_statuses = sorted(_BASE_STATUSES | _L2_EXTRA_STATUSES)
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

        # 6b. Auto-infer module parent for module-scoped L3 entities.
        # Milestones are represented as type=goal and stay directly under product.
        if entity_type in self._MODULE_SCOPED_L3_TYPES:
            inferred_parent = await self._infer_module_parent(merged_data)
            if inferred_parent and inferred_parent != merged_data.get("parent_id"):
                warnings.append(
                    f"自動推斷 parent：{merged_data.get('parent_id')} → {inferred_parent}（L3 entity 應掛在 Module 下）"
                )
                merged_data["parent_id"] = inferred_parent

        # 6c. L2 summary quality gate: tech-term scan (warn, may force draft)
        # Runs on both create and update; detected terms trigger a warning.
        # For unconfirmed modules, we also force status back to draft so the user
        # must fix the summary before confirm.
        if entity_type == EntityType.MODULE:
            summary = merged_data.get("summary", "")
            found_terms = find_tech_terms_in_summary(summary)
            if found_terms:
                is_confirmed_existing = (
                    existing is not None and existing.confirmed_by_user
                )
                if not is_confirmed_existing and not merged_data.get("force"):
                    merged_data["status"] = "draft"
                warnings.append(
                    f"L2 summary 包含技術術語：{', '.join(found_terms)}。"
                    f"L2 summary 應使用任何角色都聽得懂的語言。"
                    + (
                        "已自動降為 draft。"
                        if not is_confirmed_existing and not merged_data.get("force")
                        else ""
                    )
                    + "修正 summary 後再 confirm。"
                )

        # 6d. L2 hard rule on write path: check concrete impacts and warn;
        # new modules always start as draft regardless of inferred impacts.
        if entity_type == EntityType.MODULE and not merged_data.get("id"):
            # P0-1: layer_decision gate — enforce three-question routing on new L2 write
            force = merged_data.get("force")
            layer_decision = merged_data.get("layer_decision")
            if not force and layer_decision is None:
                raise ValueError(
                    "LAYER_DECISION_REQUIRED: 寫入 L2 entity 前必須完成分層判斷。\n"
                    "請在 data 中提供 layer_decision: {\n"
                    "  'q1_persistent': bool,  # 跨時間存活？不是一次性研究？\n"
                    "  'q2_cross_role': bool,  # 跨越 ≥2 個不同角色？\n"
                    "  'q3_company_consensus': bool,  # 公司共識概念，非個人判斷？\n"
                    "  'impacts_draft': str  # 候選 impacts（可草稿，格式 A→B）\n"
                    "}\n"
                    "或提供 force=True 加 manual_override_reason 來 bypass（需有理由）。\n"
                    "若三問未全通過，建議降級：q1=False→document+sources, q2=False→L3, q3=False→document"
                )
            if not force and layer_decision is not None:
                layer_decision = self._normalize_layer_decision(layer_decision)
                merged_data["layer_decision"] = layer_decision
                q1 = layer_decision.get("q1_persistent")
                q2 = layer_decision.get("q2_cross_role")
                q3 = layer_decision.get("q3_company_consensus")
                if not (q1 and q2 and q3):
                    downgrade_hints = []
                    if not q1:
                        downgrade_hints.append("q1=False→改為 document 掛在相關 L2 的 sources")
                    if not q2:
                        downgrade_hints.append("q2=False→改為 L3 entity (type=goal/role/project)")
                    if not q3:
                        downgrade_hints.append("q3=False→改為 document type")
                    raise ValueError(
                        f"LAYER_DOWNGRADE_REQUIRED: 三問未全通過（q1={q1}, q2={q2}, q3={q3}）。\n"
                        f"此內容不符合 L2 標準，必須降級。建議路徑：{'；'.join(downgrade_hints)}\n"
                        "確認降級後，請使用對應的 collection（documents/entities with non-module type）寫入。\n"
                        "若確認這是 L2，請修正 layer_decision 中回答 False 的三問，並提供具體的 impacts_draft。"
                    )
                # All three questions passed — validate impacts_draft
                impacts_draft_raw = layer_decision.get("impacts_draft")
                if isinstance(impacts_draft_raw, list):
                    impacts_items = [
                        str(item).strip()
                        for item in impacts_draft_raw
                        if str(item).strip()
                    ]
                    impacts_draft = "\n".join(impacts_items)
                    layer_decision["impacts_draft"] = impacts_draft
                else:
                    impacts_draft = str(impacts_draft_raw or "").strip()
                    layer_decision["impacts_draft"] = impacts_draft
                if not impacts_draft:
                    raise ValueError(
                        "IMPACTS_DRAFT_REQUIRED: 三問通過，但未提供 impacts_draft。\n"
                        "請在 layer_decision 中提供：\n"
                        "  'impacts_draft': 'A 改了什麼→B 的什麼要跟著看'\n"
                        "  或 ['A 改了什麼→B 的什麼要跟著看', ...]\n"
                        "（至少 1 條具體 impacts 描述，格式：A 改了{什麼}→B 的{什麼}要跟著看）\n"
                        "語意判斷可在 agent 端執行，impacts_draft 是草稿，confirm 時再補 relationship。"
                    )
                # Store layer_decision in details
                existing_details = merged_data.get("details") or {}
                if isinstance(existing_details, dict):
                    existing_details["layer_decision"] = layer_decision
                    merged_data["details"] = existing_details

            # force=true guard: always require manual_override_reason (independent of governance_ai)
            if merged_data.get("force"):
                override_reason = (merged_data.get("manual_override_reason") or "").strip()
                if not override_reason:
                    raise ValueError(
                        "force=true 用於 L2 時必須提供 manual_override_reason，"
                        "說明為什麼這個 module 可以暫時沒有 impacts。"
                    )
                details = merged_data.get("details") or {}
                if isinstance(details, dict):
                    details["manual_override_reason"] = override_reason
                    details["manual_override_at"] = datetime.now(timezone.utc).isoformat()
                    merged_data["details"] = details
                warnings.append(
                    f"bypass layer_decision check: {override_reason}"
                )
                warnings.append(
                    f"L2 以 force 模式寫入（draft）。manual_override_reason: {override_reason}"
                )

            # LLM impacts inference (only when governance_ai available)
            if self._governance_ai:
                all_entities = await self._entities.list_all()
                entity_dicts, unlinked_dicts = await self._build_infer_all_inputs(
                    all_entities=all_entities,
                    exclude_entity_id=merged_data.get("id"),
                    scope_entity_id=merged_data.get("parent_id") or merged_data.get("id"),
                )
                infer_entity_data = dict(merged_data)
                infer_entity_data["_global_context"] = self._build_global_infer_context(
                    all_entities,
                    exclude_entity_id=merged_data.get("id"),
                    scope_entity_id=merged_data.get("parent_id") or merged_data.get("id"),
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
                    warnings.append(
                        "L2 hard rule: 候選 module 尚無具體 impacts（A 改了什麼→B 的什麼要跟著看）。"
                        "請補充 impacts 後再 confirm。若確認不需要 impacts，可降級為 L3。"
                    )
                elif inferred_concrete_impacts:
                    warnings.append(
                        "已推斷出具體 impacts 關聯。confirm 後將升級為 active L2。"
                    )

        # L2 lifecycle: new modules always start as draft.
        # Users must confirm (via confirm tool) to transition to active.
        if entity_type == EntityType.MODULE and not merged_data.get("id"):
            merged_data["status"] = "draft"
            warnings.append(
                "L2 entity 初始為 draft 狀態。經 confirm 且至少有 1 條具體 impacts 後才會升為 active。"
            )

        # L2 consolidation_mode: store the mode that was used to produce this L2.
        # Applies to both new and existing module entities.
        if entity_type == EntityType.MODULE:
            consolidation_mode = merged_data.get("consolidation_mode")
            if consolidation_mode is not None:
                valid_modes = {"global", "incremental"}
                if consolidation_mode not in valid_modes:
                    raise ValueError(
                        f"consolidation_mode 必須是 {valid_modes} 之一，收到：'{consolidation_mode}'"
                    )
                details = merged_data.get("details") or {}
                if isinstance(details, dict):
                    details["consolidation_mode"] = consolidation_mode
                    merged_data["details"] = details

        # 7. duplicate name+type check (new entity only)
        if not merged_data.get("id"):
            existing = await self._entities.get_by_name(name)
            if existing and existing.type == entity_type:
                raise ValueError(
                    f"Entity '{name}' (type={entity_type}) already exists "
                    f"(id={existing.id}). To update it, provide id='{existing.id}'."
                )

            # 8. fuzzy similarity check — prevent semantically duplicate entities.
            # L2 modules are owned by a product, so compare only siblings under
            # the same parent; product/root duplicate protection remains global.
            all_same_type = await self._entities.list_all(type_filter=entity_type)
            if entity_type == EntityType.MODULE and merged_data.get("parent_id"):
                all_same_type = [
                    ent for ent in all_same_type
                    if ent.parent_id == merged_data.get("parent_id")
                ]
            similar = self._find_similar_entities(name, all_same_type)
            if similar:
                lines = [
                    f"Found {len(similar)} similar {entity_type} entity(ies). "
                    f"Are you sure '{name}' is not a duplicate?\n"
                ]
                for ent in similar:
                    # UI label judgment: show child modules only for product-type
                    # entities in the duplicate-check display. Not a business gate.
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
                skipped_fields: list[str] = []
                # Check name: explicitly requested rename is blocked without force
                if data.get("name") and data["name"] != existing.name:
                    skipped_fields.append(
                        f"name: '{existing.name}' → '{data['name']}'"
                    )
                for field_name in ("summary", "status", "parent_id", "level"):
                    existing_val = getattr(existing, field_name, None)
                    new_val = data.get(field_name)
                    if new_val and new_val != existing_val:
                        if not existing_val:
                            # Fill empty field — allowed
                            setattr(existing, field_name, new_val)
                        else:
                            # Overwrite non-empty field — blocked
                            skipped_fields.append(
                                f"{field_name}: '{existing_val}' → '{new_val}'"
                            )
                # Merge tags: only fill empty tag fields, report skipped overwrites
                if isinstance(data.get("tags"), dict) and isinstance(existing.tags, Tags):
                    for dim in ("what", "why", "how", "who"):
                        new_tag_val = data["tags"].get(dim)
                        existing_tag_val = getattr(existing.tags, dim, "")
                        if new_tag_val and new_tag_val != existing_tag_val:
                            if not existing_tag_val:
                                setattr(existing.tags, dim, new_tag_val)
                            else:
                                skipped_fields.append(
                                    f"tags.{dim}: '{existing_tag_val}' → '{new_tag_val}'"
                                )
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
                if skipped_fields:
                    warnings.append(
                        f"REJECTED_FIELDS: Entity '{existing.name}' 已確認，"
                        f"以下欄位變更被拒絕（需 force=true 覆寫）：{'; '.join(skipped_fields)}"
                    )
                else:
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
        # Uses DEFAULT_TYPE_LEVELS SSOT (ADR-047 S03) — replaced the previous local type-to-level dict.
        level = (
            merged_data.get("level")
            if merged_data.get("level") is not None
            else default_level_for_type(merged_data["type"])
        )

        # L2 status transition validation (update path):
        # draft → active must go through confirm, not write.
        if existing and existing.type == EntityType.MODULE:
            new_status = merged_data.get("status", existing.status)
            if existing.status == "draft" and new_status == "active":
                raise ValueError(
                    "L2 entity 不能透過 write 從 draft 直接升為 active。"
                    "請使用 confirm(collection='entities') 來升級，系統會檢查 impacts gate。"
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
            entity.visible_to_roles = list(merged_data.get("visible_to_roles", existing.visible_to_roles))
            entity.visible_to_members = list(merged_data.get("visible_to_members", existing.visible_to_members))
            entity.visible_to_departments = list(
                merged_data.get("visible_to_departments", existing.visible_to_departments)
            )
            entity.last_reviewed_at = merged_data.get(
                "last_reviewed_at", existing.last_reviewed_at
            )
            # ADR-022 Document Bundle fields
            if "doc_role" in merged_data:
                entity.doc_role = merged_data["doc_role"]
            if "bundle_highlights" in merged_data:
                entity.bundle_highlights = merged_data["bundle_highlights"]
            if "highlights_updated_at" in merged_data:
                entity.highlights_updated_at = merged_data["highlights_updated_at"]
            if "change_summary" in merged_data:
                entity.change_summary = merged_data["change_summary"]
            if "summary_updated_at" in merged_data:
                entity.summary_updated_at = merged_data["summary_updated_at"]
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
                visible_to_roles=list(merged_data.get("visible_to_roles", [])),
                visible_to_members=list(merged_data.get("visible_to_members", [])),
                visible_to_departments=list(merged_data.get("visible_to_departments", [])),
                # ADR-022 Document Bundle fields
                doc_role=merged_data.get("doc_role"),
                bundle_highlights=list(merged_data.get("bundle_highlights", [])),
                highlights_updated_at=merged_data.get("highlights_updated_at"),
                change_summary=merged_data.get("change_summary"),
                summary_updated_at=merged_data.get("summary_updated_at"),
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
        if self._governance_ai and saved.id and saved.type != EntityType.DOCUMENT:
            all_entities = await self._entities.list_all()
            entity_dicts, unlinked_dicts = await self._build_infer_all_inputs(
                all_entities=all_entities,
                exclude_entity_id=saved.id,
                scope_entity_id=saved.id,
            )
            doc_entities = [e for e in all_entities if e.type == EntityType.DOCUMENT and e.id]
            infer_entity_data = self._entity_to_dict(saved)
            infer_entity_data["_global_context"] = self._build_global_infer_context(
                all_entities,
                exclude_entity_id=saved.id,
                scope_entity_id=saved.id,
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

        # Compute similar_items for duplicate detection hints
        all_entities_for_sim = await self._entities.list_all()
        items_for_sim = [{"id": e.id, "name": e.name} for e in all_entities_for_sim if e.id != saved.id]
        similar = find_similar_items(saved.name, items_for_sim) or None

        return UpsertEntityResult(
            entity=saved,
            tag_confidence=tag_confidence,
            split_recommendation=split_rec,
            warnings=warnings or None,
            similar_items=similar,
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
        if rel_type == RelationshipType.IMPACTS and not self._is_concrete_impacts_description(description):
            raise ValueError(
                "impacts relationship description must be concrete. "
                "Use format: A 改了什麼 → B 的什麼要跟著看"
            )

        # --- Cross-product guard for ANY auto-inferred / auto-linked edge ---
        # DF-20260419-L2a (F6 symmetric): previously only related_to with
        # description="auto-inferred..." was blocked cross-product, leaving
        # the other five rel_types (impacts / depends_on / part_of / serves
        # / enables) and "auto-linked document" paths able to silently span
        # L1 subtrees. F6 already scopes the candidate pool at inference
        # time, but a hostile / buggy caller can still call add_relationship
        # directly with a cross-subtree target. Generalize the guard:
        # any description that starts with "auto-" and targets a peer in a
        # different L1 product → don't persist, return synthetic edge.
        # Manual callers (description without auto- prefix) are unaffected,
        # so intentional cross-product edges still work.
        is_auto = description.startswith("auto-")
        if is_auto:
            source_product = await self._find_product_ancestor(source)
            target_product = await self._find_product_ancestor(target)
            if (
                source_product is not None
                and target_product is not None
                and source_product.id != target_product.id
            ):
                logger.info(
                    "Skipping cross-product auto edge: %s (%s) -%s-> %s (%s)",
                    source.name, source_product.name,
                    rel_type,
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
            if existing.description != description:
                existing.description = description
                return await self._relationships.add(existing)
            return existing

        rel = Relationship(
            source_entity_id=source_id,
            target_id=target_id,
            type=rel_type,
            description=description,
        )
        return await self._relationships.add(rel)

    @staticmethod
    def _cosine_similarity(a: list[float], b: list[float]) -> float:
        """Compute cosine similarity between two equal-length vectors."""
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(x * x for x in b) ** 0.5
        if norm_a == 0.0 or norm_b == 0.0:
            return 0.0
        return dot / (norm_a * norm_b)

    async def compute_impact_chain(
        self,
        entity_id: str,
        max_depth: int = 5,
        direction: str = "forward",
        intent: str | None = None,
        top_k_per_hop: int | None = None,
    ) -> list[dict]:
        """BFS traverse relationship edges from entity_id.

        Args:
            direction: "forward" (outgoing, default), "reverse" (incoming),
                       or "both" (union of forward + reverse).
            intent: Optional query string to embed and use as ranking signal.
                    If provided, neighbors are ranked by cosine similarity to
                    the intent embedding.  If None, uses root entity's
                    summary_embedding as query vector (root-self mode).
            top_k_per_hop: If set, retain only the top-K neighbors per BFS hop.
                    Neighbors with embeddings are ranked first; those without
                    appear last (alphabetical).  If None, all neighbors kept.

        Returns an ordered list of hops, each as a dict:
            {from_id, from_name, type, to_id, to_name, relevance_score}

        Cycle-safe via a visited set of entity IDs.
        Gracefully handles deleted entities by substituting the entity ID as name.
        """
        if direction == "both":
            fwd = await self.compute_impact_chain(
                entity_id, max_depth, "forward", intent=intent, top_k_per_hop=top_k_per_hop,
            )
            rev = await self.compute_impact_chain(
                entity_id, max_depth, "reverse", intent=intent, top_k_per_hop=top_k_per_hop,
            )
            return fwd + rev

        # ------------------------------------------------------------------
        # Determine query vector
        # ------------------------------------------------------------------
        query_vec: list[float] | None = None
        use_semantic = False

        if self._embedding_service is not None:
            if intent:
                # Intent mode: embed the intent string
                query_vec = await self._embedding_service.embed_query(intent)
                # If API returned None, fall back to root-self mode below
                if query_vec is not None:
                    use_semantic = True

            if not use_semantic:
                # Root-self mode: use root entity embedding from DB
                if hasattr(self._entities, "get_embeddings_by_ids"):
                    embeddings = await self._entities.get_embeddings_by_ids([entity_id])
                    root_vec = embeddings.get(entity_id)
                    if root_vec is not None:
                        query_vec = root_vec
                        use_semantic = True
                    # else: root has no embedding → full alphabetical fallback

        # use_semantic=False means full alphabetical fallback (AC-17)
        # In fallback mode we do NOT call any embedding API for neighbors.

        # ------------------------------------------------------------------
        # BFS
        # ------------------------------------------------------------------
        result: list[dict] = []
        visited: set[str] = {entity_id}
        # Queue entries: (entity_id, depth, from_id, from_name, rel_type, hop_direction)
        # We batch-collect all candidates at each depth level before ranking.
        # Use a two-phase approach: collect candidates per depth level, rank, prune.

        # Level-aware BFS: process one depth level at a time.
        current_level: list[tuple[str, int]] = [(entity_id, 0)]

        while current_level:
            next_level_candidates: list[tuple[str, str, str, str, str]] = []
            # (next_id, current_id, current_name, rel_type, next_name)

            for current_id, depth in current_level:
                if depth >= max_depth:
                    continue

                current_entity = await self._entities.get_by_id(current_id)
                current_name = current_entity.name if current_entity else current_id

                rels = await self._relationships.list_by_entity(current_id)
                for rel in rels:
                    if direction == "forward":
                        if rel.source_entity_id != current_id:
                            continue
                        next_id = rel.target_id
                    else:  # reverse
                        if rel.target_id != current_id:
                            continue
                        next_id = rel.source_entity_id

                    if next_id in visited:
                        continue

                    next_entity = await self._entities.get_by_id(next_id)
                    next_name = next_entity.name if next_entity else next_id

                    visited.add(next_id)
                    next_level_candidates.append((next_id, current_id, current_name, rel.type, next_name))

            if not next_level_candidates:
                break

            # ------------------------------------------------------------------
            # Rank candidates for this level
            # ------------------------------------------------------------------
            ranked = await self._rank_hop_candidates(
                candidates=next_level_candidates,
                query_vec=query_vec if use_semantic else None,
                top_k=top_k_per_hop,
                direction=direction,
            )

            for hop in ranked:
                result.append(hop)

            # Advance to next level: only enqueue entities that survived pruning
            surviving_ids = {hop["to_id"] if direction == "forward" else hop["from_id"] for hop in ranked}
            current_depth = current_level[0][1]
            current_level = [
                (nid, current_depth + 1)
                for nid in surviving_ids
            ]

        return result

    async def _rank_hop_candidates(
        self,
        candidates: list[tuple[str, str, str, str, str]],
        query_vec: list[float] | None,
        top_k: int | None,
        direction: str,
    ) -> list[dict]:
        """Rank one BFS hop's candidate neighbors and return hop dicts.

        Args:
            candidates: list of (next_id, from_id, from_name, rel_type, next_name)
            query_vec: query embedding (None = full alphabetical fallback)
            top_k: prune to top K after ranking; None means no pruning
            direction: "forward" or "reverse" (controls dict key layout)

        Returns:
            list of hop dicts with relevance_score field
        """
        if query_vec is None:
            # Full alphabetical fallback — no embedding API call
            sorted_candidates = sorted(candidates, key=lambda c: c[4])  # sort by next_name
            pruned = sorted_candidates[:top_k] if top_k is not None else sorted_candidates
            return [
                self._make_hop_dict(c, direction, relevance_score=None)
                for c in pruned
            ]

        # Batch-fetch embeddings for all candidates
        candidate_ids = [c[0] for c in candidates]
        if hasattr(self._entities, "get_embeddings_by_ids"):
            id_to_vec = await self._entities.get_embeddings_by_ids(candidate_ids)
        else:
            id_to_vec = {}

        # Split into scored and unscored
        scored: list[tuple[float, tuple]] = []
        unscored: list[tuple] = []

        for c in candidates:
            next_id = c[0]
            vec = id_to_vec.get(next_id)
            if vec is not None:
                score = self._cosine_similarity(vec, query_vec)
                scored.append((score, c))
            else:
                unscored.append(c)

        # Sort scored descending by score
        scored.sort(key=lambda x: x[0], reverse=True)
        # Sort unscored alphabetically by next_name (c[4])
        unscored.sort(key=lambda c: c[4])

        # Apply top_k: prefer scored, then fill from unscored
        if top_k is not None:
            scored_take = scored[:top_k]
            remaining = top_k - len(scored_take)
            unscored_take = unscored[:remaining] if remaining > 0 else []
        else:
            scored_take = scored
            unscored_take = unscored

        result: list[dict] = []
        for score, c in scored_take:
            result.append(self._make_hop_dict(c, direction, relevance_score=score))
        for c in unscored_take:
            result.append(self._make_hop_dict(c, direction, relevance_score=None))

        return result

    @staticmethod
    def _make_hop_dict(
        candidate: tuple[str, str, str, str, str],
        direction: str,
        relevance_score: float | None,
    ) -> dict:
        """Build a hop result dict from a candidate tuple.

        candidate = (next_id, from_id, from_name, rel_type, next_name)
        """
        next_id, current_id, current_name, rel_type, next_name = candidate
        if direction == "forward":
            return {
                "from_id": current_id,
                "from_name": current_name,
                "type": rel_type,
                "to_id": next_id,
                "to_name": next_name,
                "relevance_score": relevance_score,
            }
        else:
            return {
                "from_id": next_id,
                "from_name": next_name,
                "type": rel_type,
                "to_id": current_id,
                "to_name": current_name,
                "relevance_score": relevance_score,
            }

    async def find_gaps(
        self, gap_type: str = "all", scope_product: str | None = None,
    ) -> dict:
        """Find structural gaps in the ontology graph.

        gap_type: orphan_entities | underconnected | all
        scope_product: limit to entities under a specific product name
        """
        results: list[dict] = []
        all_entities = await self._entities.list_all()
        entity_map = {entity.id: entity for entity in all_entities if entity.id}

        def _is_in_scope(entity) -> bool:
            if not scope_product:
                return True
            current = entity
            visited: set[str] = set()
            while current is not None and current.id not in visited:
                visited.add(current.id)
                if is_collaboration_root_entity(current):
                    return current.name == scope_product
                parent_id = getattr(current, "parent_id", None)
                current = entity_map.get(parent_id) if parent_id else None
            return False

        if gap_type in ("all", "orphan_entities"):
            orphans = await self._relationships.find_orphan_entities()
            for o in orphans:
                entity = entity_map.get(o["id"])
                if entity is not None and not _is_in_scope(entity):
                    continue
                results.append({
                    "type": "orphan",
                    "entity_id": o["id"],
                    "entity_name": o["name"],
                    "entity_type": o["type"],
                    "severity": "high" if o.get("level", 0) <= 2 else "medium",
                    "suggestion": f"'{o['name']}' 沒有任何關聯，考慮補上 impacts/depends_on/part_of 關係，或確認是否需要保留",
                })

        if gap_type in ("all", "weak_semantics"):
            weak_types = {"related_to"}
            for ent in all_entities:
                if ent.status == "archived" or ent.type in ("product", "project"):
                    continue
                if not _is_in_scope(ent):
                    continue
                if not ent.id:
                    continue
                rels = await self._relationships.list_by_entity(ent.id)
                if not rels:
                    continue  # already caught by orphan check
                rel_types = {r.type for r in rels}
                if rel_types.issubset(weak_types):
                    results.append({
                        "type": "weak_semantics",
                        "entity_id": ent.id,
                        "entity_name": ent.name,
                        "entity_type": ent.type,
                        "relation_types": sorted(rel_types),
                        "relation_count": len(rels),
                        "severity": "high",
                        "suggestion": f"'{ent.name}' 的所有關聯都是 related_to，缺少語意明確的 impacts/depends_on/part_of，考慮補上",
                    })

        if gap_type in ("all", "underconnected"):
            for ent in all_entities:
                if ent.status == "archived" or ent.type in ("product", "project"):
                    continue
                if not _is_in_scope(ent):
                    continue
                if not ent.id:
                    continue
                rels = await self._relationships.list_by_entity(ent.id)
                outgoing = [r for r in rels if r.source_entity_id == ent.id]
                if len(outgoing) == 0 and len(rels) > 0:
                    results.append({
                        "type": "no_outgoing",
                        "entity_id": ent.id,
                        "entity_name": ent.name,
                        "entity_type": ent.type,
                        "incoming_count": len(rels),
                        "severity": "low",
                        "suggestion": f"'{ent.name}' 只有被引用但沒有主動關聯，考慮補上 outgoing 關係",
                    })

        summary = {}
        for r in results:
            summary[r["type"]] = summary.get(r["type"], 0) + 1

        return {
            "gaps": results,
            "total": len(results),
            "by_type": summary,
        }

    async def find_common_neighbors(
        self, entity_a: str, entity_b: str,
    ) -> dict:
        """Find entities connected to both A and B.

        entity_a/entity_b: entity ID or name.
        """
        # Resolve names to IDs
        a_id = await self._resolve_entity_id(entity_a)
        b_id = await self._resolve_entity_id(entity_b)
        if not a_id:
            raise ValueError(f"Entity '{entity_a}' not found")
        if not b_id:
            raise ValueError(f"Entity '{entity_b}' not found")

        neighbors = await self._relationships.find_common_neighbors(a_id, b_id)
        return {
            "entity_a": {"id": a_id, "name": entity_a},
            "entity_b": {"id": b_id, "name": entity_b},
            "common_neighbors": neighbors,
            "count": len(neighbors),
        }

    async def _resolve_entity_id(self, name_or_id: str) -> str | None:
        """Resolve an entity name or ID to an ID."""
        ent = await self._entities.get_by_id(name_or_id)
        if ent:
            return ent.id
        ent = await self._entities.get_by_name(name_or_id)
        if ent:
            return ent.id
        return None

    async def upsert_document(self, data: dict, partner: dict | None = None) -> Entity:
        """Create or update a document as an entity(type="document").

        Accepts the legacy document format (title, source, linked_entity_ids)
        and maps it to the unified Entity model:
          - title → name
          - source → sources[0]
          - linked_entity_ids[0] → parent_id (primary), rest → relationships
          - tags (legacy document tag format) → Tags (unified list format)
        """
        # --- Guest write guard ---
        # document is an L3 type; guests may create it under an authorized parent.
        # We inject type="document" so the shared guard can evaluate L1/L2/L3 rules.
        if partner is not None and is_guest(partner):
            await self._enforce_guest_write_guard({**data, "type": "document"}, partner)

        # --- Required field validation (clear error messages) ---
        allow_create_with_id = bool(data.get("allow_create_with_id"))
        is_create = not data.get("id") or allow_create_with_id
        if is_create:
            missing = []
            # title can be empty when source is GitHub (H1 derivation)
            has_github_source = (
                isinstance(data.get("source"), dict)
                and data["source"].get("type") == "github"
            )
            if not data.get("title") and not has_github_source:
                missing.append("title")
            if not data.get("summary"):
                missing.append("summary")
            if not data.get("tags"):
                missing.append("tags（格式：{what, why, how, who}）")
            if missing:
                raise ValueError(
                    f"建立 document 必須提供以下欄位：{', '.join(missing)}。"
                )

        # --- Existing document lookup ---
        existing: Entity | None = None
        if data.get("id"):
            existing = await self._entities.get_by_id(data["id"])
            if existing is None:
                all_doc_entities = await self._entities.list_all(type_filter=EntityType.DOCUMENT)
                existing = next((e for e in all_doc_entities if e.id == data["id"]), None)
            if existing is None and not allow_create_with_id:
                raise ValueError(
                    f"Document entity '{data['id']}' not found. Use create without id."
                )
            if existing is not None and existing.type != EntityType.DOCUMENT:
                raise ValueError(
                    f"Entity '{data['id']}' is type='{existing.type}', not document."
                )
            if existing is not None:
                is_create = False

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
            # Validate source_uri format when creating or updating with a new URI.
            # Skip validation if no URI is provided (allows pure summary/status updates).
            if source_type and source_uri:
                is_new_doc = not data.get("id") and existing is None
                is_updating_uri = bool(existing) and source_data.get("uri")
                if is_new_doc or is_updating_uri:
                    is_valid, error_msg = validate_source_uri(source_type, source_uri)
                    if not is_valid:
                        raise ValueError(
                            f"Invalid source URI for type '{source_type}': {error_msg}"
                        )

        # Server-side idempotency: dedup by source URI for document entities.
        if source_uri and not data.get("id"):
            all_doc_entities = await self._entities.list_all(type_filter=EntityType.DOCUMENT)
            for d in all_doc_entities:
                if any(str(s.get("uri", "")).strip() == source_uri for s in (d.sources or [])):
                    data["id"] = d.id
                    existing = d
                    break

        if "linked_entity_ids" in data:
            linked_entity_ids = await self._validate_document_linked_entity_ids(
                data.get("linked_entity_ids")
            )
        elif existing:
            primary_linked_id, related_linked_ids = await self._load_document_linkage_state(
                existing.id or data["id"]
            )
            fallback_linked_ids = [
                eid
                for eid in [primary_linked_id or existing.parent_id, *related_linked_ids]
                if eid
            ]
            linked_entity_ids = await self._validate_document_linked_entity_ids(
                fallback_linked_ids
            )
        else:
            linked_entity_ids = await self._validate_document_linked_entity_ids(None)

        # Map fields to entity format (merge semantics for sparse updates)
        parent_id = (
            linked_entity_ids[0]
            if linked_entity_ids
            else data.get("parent_id", existing.parent_id if existing else None)
        )
        related_ids = linked_entity_ids[1:] if len(linked_entity_ids) > 1 else []

        # Formal-entry contract: persist as details.formal_entry so delivery logic
        # can use an explicit marker instead of relying only on heuristics.
        details = dict(existing.details or {}) if existing and isinstance(existing.details, dict) else {}
        incoming_details = data.get("details")
        if isinstance(incoming_details, dict):
            details.update(incoming_details)
        formal_entry = data.get("formal_entry")
        if formal_entry is not None:
            details["formal_entry"] = bool(formal_entry)
        if not details:
            details = None

        # --- ADR-022 Bundle Operations ---
        # Detect add_source / update_source / remove_source in data
        add_source_data = data.get("add_source")
        update_source_data = data.get("update_source")
        remove_source_data = data.get("remove_source")
        has_bundle_op = any([add_source_data, update_source_data, remove_source_data])

        # Resolve doc_role
        doc_role = data.get("doc_role")
        if doc_role is None and existing:
            doc_role = existing.doc_role or "single"
        elif doc_role is None:
            doc_role = "index"

        # Handle bundle_highlights
        bundle_highlights = data.get("bundle_highlights")
        highlights_updated_at = None
        if bundle_highlights is not None:
            highlights_updated_at = datetime.now(timezone.utc)
        elif existing:
            bundle_highlights = list(existing.bundle_highlights or [])
            highlights_updated_at = existing.highlights_updated_at
        else:
            bundle_highlights = []

        if bundle_highlights is not None and not isinstance(bundle_highlights, list):
            raise ValueError("bundle_highlights must be a list")
        if isinstance(bundle_highlights, list):
            normalized_highlights: list[dict] = []
            for item in bundle_highlights:
                if not isinstance(item, dict):
                    raise ValueError("bundle_highlights items must be objects")
                normalized_highlights.append({
                    "source_id": str(item.get("source_id", "")).strip(),
                    "headline": str(item.get("headline", "")).strip(),
                    "reason_to_read": str(item.get("reason_to_read", "")).strip(),
                    "priority": str(item.get("priority", "important")).strip() or "important",
                })
            bundle_highlights = normalized_highlights

        # Handle change_summary
        change_summary = data.get("change_summary")
        summary_updated_at = None
        if change_summary is not None:
            summary_updated_at = datetime.now(timezone.utc)
        elif existing:
            change_summary = existing.change_summary
            summary_updated_at = existing.summary_updated_at

        # Build sources list — bundle operations take priority over legacy source field
        sources_payload = data.get("sources")
        suggestions = []
        suggestion_source_ids: list[str] = []
        if has_bundle_op and existing:
            sources: list[dict] = list(existing.sources) if existing.sources else []
            for src in sources:
                if isinstance(src, dict):
                    _sync_bundle_source_status(src, _bundle_source_status(src))

            if add_source_data:
                _validate_source_access_fields(add_source_data)
                # --- Helper Ingest Contract: external_id validation & size check ---
                new_external_id = add_source_data.get("external_id")
                if new_external_id is not None:
                    is_valid_eid, eid_error = validate_external_id_format(str(new_external_id))
                    if not is_valid_eid:
                        raise ValueError(f"Invalid external_id: {eid_error}")

                new_snapshot = add_source_data.get("snapshot_summary")
                if new_snapshot is not None:
                    _assert_snapshot_size(new_snapshot)

                # Helper upsert by external_id: if same external_id already exists in
                # this doc → update in-place (preserve source_id), not add a new source.
                if new_external_id is not None:
                    existing_idx = next(
                        (i for i, s in enumerate(sources) if s.get("external_id") == new_external_id),
                        None,
                    )
                    now_iso = datetime.now(timezone.utc).isoformat()
                    if existing_idx is not None:
                        # Update path: overwrite mutable fields, preserve source_id
                        existing_src = sources[existing_idx]
                        preserved_sid = existing_src.get("source_id") or generate_source_id()
                        updated_src = dict(existing_src)
                        updated_src["last_synced_at"] = now_iso
                        updated_src["source_id"] = preserved_sid
                        for key in (
                            "uri", "label", "type", "doc_type", "doc_status", "note", "is_primary",
                            "container_id", "container_ids", "retrieval_mode", "content_access",
                        ):
                            if key in add_source_data and add_source_data[key] is not None:
                                updated_src[key] = add_source_data[key]
                        if "external_updated_at" in add_source_data:
                            updated_src["external_updated_at"] = add_source_data["external_updated_at"]
                        if "snapshot_summary" in add_source_data:
                            updated_src["snapshot_summary"] = add_source_data["snapshot_summary"]
                        if (
                            "uri" in add_source_data
                            and str(add_source_data.get("uri", "")).strip()
                            != str(existing_src.get("uri", "")).strip()
                        ):
                            _validate_document_source_uri(updated_src, context="add_source")
                        sources[existing_idx] = updated_src
                        suggestion_source_ids = [preserved_sid]
                        # Detect no-op
                        new_ext_upd = add_source_data.get("external_updated_at")
                        old_ext_upd = existing_src.get("external_updated_at")
                        noop = (new_ext_upd == old_ext_upd) and (new_snapshot == existing_src.get("snapshot_summary"))
                        if "_helper_upsert_meta" not in data:
                            data["_helper_upsert_meta"] = {}
                        data["_helper_upsert_meta"]["noop"] = noop
                        data["_helper_upsert_meta"]["source_id"] = preserved_sid
                    else:
                        # Create path: new source with external_id
                        # Guard: single cannot add 2nd source
                        if doc_role == "single" and len(sources) >= 1:
                            raise ValueError(
                                "single doc entity 只能有一個 source。"
                                "若需聚合多份文件請先將 doc_role 改為 index。"
                            )
                        new_src_uri = str(add_source_data.get("uri", "")).strip()
                        new_src_type = add_source_data.get("type", "")
                        _validate_document_source_uri(
                            {"type": new_src_type, "uri": new_src_uri},
                            context="add_source",
                        )
                        new_sid = generate_source_id()
                        new_source = {
                            "source_id": new_sid,
                            "external_id": new_external_id,
                            "last_synced_at": now_iso,
                            "uri": new_src_uri,
                            "type": new_src_type,
                            "label": add_source_data.get("label", ""),
                            "doc_type": add_source_data.get("doc_type", ""),
                            "doc_status": add_source_data.get("doc_status", ""),
                            "status": "valid",
                            "source_status": "valid",
                            "note": add_source_data.get("note", ""),
                            "is_primary": add_source_data.get("is_primary", False),
                            "container_id": add_source_data.get("container_id"),
                            "container_ids": add_source_data.get("container_ids"),
                            "retrieval_mode": add_source_data.get("retrieval_mode"),
                            "content_access": add_source_data.get("content_access"),
                        }
                        if "external_updated_at" in add_source_data:
                            new_source["external_updated_at"] = add_source_data["external_updated_at"]
                        if new_snapshot is not None:
                            new_source["snapshot_summary"] = new_snapshot
                        # Warn on unknown doc_type
                        if new_source["doc_type"] and not is_known_doc_type(new_source["doc_type"]):
                            suggestions.append(
                                f"doc_type '{new_source['doc_type']}' is not a known type. "
                                f"Consider using 'OTHER' or one of: SPEC, DECISION, DESIGN, PLAN, "
                                f"REPORT, CONTRACT, GUIDE, MEETING, REFERENCE, TEST."
                            )
                        sources.append(new_source)
                        suggestion_source_ids = [new_sid]
                        data["_helper_upsert_meta"] = {"noop": False, "source_id": new_sid}
                    suggestions.append("change_summary 可能需要更新")
                else:
                    # No external_id: standard add path (backward compat)
                    # Guard: single cannot add 2nd source
                    if doc_role == "single" and len(sources) >= 1:
                        raise ValueError(
                            "single doc entity 只能有一個 source。"
                            "若需聚合多份文件請先將 doc_role 改為 index。"
                        )
                    # Validate URI if provided
                    new_src_uri = str(add_source_data.get("uri", "")).strip()
                    new_src_type = add_source_data.get("type", "")
                    _validate_document_source_uri(
                        {"type": new_src_type, "uri": new_src_uri},
                        context="add_source",
                    )
                    new_source = {
                        "source_id": generate_source_id(),
                        "uri": new_src_uri,
                        "type": new_src_type,
                        "label": add_source_data.get("label", ""),
                        "doc_type": add_source_data.get("doc_type", ""),
                        "doc_status": add_source_data.get("doc_status", ""),
                        "status": "valid",
                        "source_status": "valid",
                        "note": add_source_data.get("note", ""),
                        "is_primary": add_source_data.get("is_primary", False),
                        "container_id": add_source_data.get("container_id"),
                        "container_ids": add_source_data.get("container_ids"),
                        "retrieval_mode": add_source_data.get("retrieval_mode"),
                        "content_access": add_source_data.get("content_access"),
                    }
                    # Warn on unknown doc_type
                    if new_source["doc_type"] and not is_known_doc_type(new_source["doc_type"]):
                        suggestions.append(
                            f"doc_type '{new_source['doc_type']}' is not a known type. "
                            f"Consider using 'OTHER' or one of: SPEC, DECISION, DESIGN, PLAN, "
                            f"REPORT, CONTRACT, GUIDE, MEETING, REFERENCE, TEST."
                        )
                    sources.append(new_source)
                    suggestion_source_ids = [new_source["source_id"]]
                    suggestions.append("change_summary 可能需要更新")

            elif update_source_data:
                _validate_source_access_fields(update_source_data)
                # --- Helper Ingest Contract: external_id in update_source ---
                upd_external_id = update_source_data.get("external_id")
                if upd_external_id is not None:
                    is_valid_eid, eid_error = validate_external_id_format(str(upd_external_id))
                    if not is_valid_eid:
                        raise ValueError(f"Invalid external_id: {eid_error}")

                upd_snapshot = update_source_data.get("snapshot_summary")
                if upd_snapshot is not None:
                    _assert_snapshot_size(upd_snapshot)

                target_sid = update_source_data.get("source_id")
                if not target_sid and upd_external_id is None:
                    raise ValueError("update_source requires source_id or external_id")

                # If external_id provided without source_id: look up by external_id
                if target_sid is None and upd_external_id is not None:
                    matched = next(
                        (s for s in sources if s.get("external_id") == upd_external_id),
                        None,
                    )
                    if matched is None:
                        raise ValueError(
                            f"update_source: external_id '{upd_external_id}' not found in this document. "
                            f"Use add_source to create a new source with this external_id."
                        )
                    target_sid = matched.get("source_id")

                found = False
                now_iso = datetime.now(timezone.utc).isoformat()
                for src in sources:
                    if src.get("source_id") == target_sid:
                        for key in (
                            "uri", "label", "doc_type", "doc_status", "note", "is_primary",
                            "status", "source_status", "container_id", "container_ids",
                            "retrieval_mode", "content_access",
                        ):
                            if key in update_source_data and key != "source_id":
                                src[key] = update_source_data[key]
                        if "status" in update_source_data or "source_status" in update_source_data:
                            _sync_bundle_source_status(src, _bundle_source_status(update_source_data))
                        # Re-validate URI if changed
                        if "uri" in update_source_data:
                            _validate_document_source_uri(src, context="update_source")
                        # Helper ingest fields
                        if upd_external_id is not None:
                            src["external_id"] = upd_external_id
                        if "external_updated_at" in update_source_data:
                            src["external_updated_at"] = update_source_data["external_updated_at"]
                        if "snapshot_summary" in update_source_data:
                            src["snapshot_summary"] = update_source_data["snapshot_summary"]
                        # Always update last_synced_at when helper calls update_source
                        if upd_external_id is not None or "external_updated_at" in update_source_data:
                            src["last_synced_at"] = now_iso
                        found = True
                        break
                if not found:
                    raise ValueError(
                        f"source_id '{target_sid}' not found in this document"
                    )
                suggestion_source_ids = [str(target_sid).strip()]
                suggestions.append("change_summary 可能需要更新")

            elif remove_source_data:
                target_sid = remove_source_data.get("source_id")
                if not target_sid:
                    raise ValueError("remove_source requires source_id")
                # Guard: cannot remove last source
                if len(sources) <= 1:
                    raise ValueError(
                        "不可移除最後一個 source。"
                        "Document entity 至少需要一個 source。"
                    )
                # Guard: index only
                if doc_role == "single":
                    raise ValueError(
                        "single doc entity 不支援 remove_source。"
                    )
                original_len = len(sources)
                sources = [s for s in sources if s.get("source_id") != target_sid]
                if len(sources) == original_len:
                    raise ValueError(
                        f"source_id '{target_sid}' not found in this document"
                    )
                suggestions.append("change_summary 可能需要更新")
                suggestions.append("bundle_highlights 可能需要更新")

        else:
            # Check for plural "sources" payload first (ADR-022 bundle creation)
            if sources_payload and isinstance(sources_payload, list):
                # Honor explicit sources array from caller
                sources: list[dict] = []
                for src in sources_payload:
                    if isinstance(src, dict):
                        snapshot = src.get("snapshot_summary")
                        if snapshot is not None:
                            _assert_snapshot_size(snapshot)
                        status = _bundle_source_status(src)
                        normalized_source = {
                            "source_id": src.get("source_id"),
                            "external_id": src.get("external_id"),
                            "uri": src.get("uri", ""),
                            "type": src.get("type", ""),
                            "label": src.get("label", ""),
                            "doc_type": src.get("doc_type", ""),
                            "doc_status": src.get("doc_status", ""),
                            "status": status,
                            "source_status": status,
                            "note": src.get("note", ""),
                            "is_primary": src.get("is_primary", False),
                            "container_id": src.get("container_id"),
                            "container_ids": src.get("container_ids"),
                            "retrieval_mode": src.get("retrieval_mode"),
                            "content_access": src.get("content_access"),
                        }
                        for optional_key in (
                            "external_updated_at",
                            "last_synced_at",
                            "snapshot_summary",
                        ):
                            if optional_key in src:
                                normalized_source[optional_key] = src[optional_key]
                        _validate_document_source_uri(
                            normalized_source,
                            context="sources[]",
                        )
                        sources.append(normalized_source)
            else:
                # Legacy path: build sources from singular source field
                existing_source = (existing.sources[0] if existing and existing.sources else {})
                if data.get("clear_sources"):
                    sources: list[dict] = []
                else:
                    sources: list[dict] = list(existing.sources) if existing else []
                if source_data and isinstance(source_data, dict):
                    source_status = _bundle_source_status(source_data)
                    merged_source = {
                        "uri": source_data.get("uri", existing_source.get("uri", "")),
                        "label": source_data.get("label") or data.get("title") or existing_source.get("label", ""),
                        "type": source_data.get("type", existing_source.get("type", "")),
                        "status": source_status,
                        "source_status": source_status,
                    }
                    _validate_document_source_uri(merged_source)
                    sources = [merged_source]

        # Ensure all sources have source_ids (backfill for legacy sources)
        for src in sources:
            if isinstance(src, dict):
                _sync_bundle_source_status(src, _bundle_source_status(src))
        ensure_source_ids(sources)
        if not has_bundle_op and sources_payload and isinstance(sources_payload, list):
            suggestion_source_ids = [
                str(src.get("source_id", "")).strip()
                for src in sources
                if isinstance(src, dict)
            ]

        if has_bundle_op:
            suggestions.append("bundle_highlights 可能需要更新")

        if doc_role == "index":
            suggestion = _build_bundle_highlights_suggestion(
                sources=sources,
                existing_highlights=bundle_highlights if isinstance(bundle_highlights, list) else [],
                candidate_source_ids=suggestion_source_ids,
            )
            if suggestion is not None:
                suggestions.append(suggestion)

        if doc_role == "index":
            if bundle_highlights:
                valid_source_ids = {str(src.get("source_id", "")).strip() for src in sources if isinstance(src, dict)}
                primary_count = 0
                for item in bundle_highlights:
                    sid = item.get("source_id", "")
                    if sid and sid not in valid_source_ids:
                        raise ValueError(f"bundle_highlights source_id '{sid}' not found in this document")
                    if not item.get("headline"):
                        raise ValueError("bundle_highlights requires headline")
                    if not item.get("reason_to_read"):
                        raise ValueError("bundle_highlights requires reason_to_read")
                    if item.get("priority") == "primary":
                        primary_count += 1
                if primary_count == 0:
                    suggestions.append("index document 建議至少標記一筆 primary bundle_highlight")
            else:
                suggestions.append("index document 建議補上 bundle_highlights")

        # Build unified Tags from legacy document tag format
        tags_data = data.get("tags")
        existing_tags = existing.tags if existing else Tags(what=[], why="", how="", who=[])
        if isinstance(tags_data, dict):
            tags = Tags(
                what=tags_data.get("what", existing_tags.what),
                why=tags_data.get("why", existing_tags.why),
                how=tags_data.get("how", existing_tags.how),
                who=tags_data.get("who", existing_tags.who),
            )
        elif tags_data is None and existing:
            tags = existing.tags
        else:
            tags = tags_data

        doc_title = str(data.get("title", existing.name if existing else "")).strip()

        # --- Title validation and auto-derivation ---
        doc_title = await self._resolve_document_title(
            doc_title=doc_title,
            source_type=source_data.get("type", "") if isinstance(source_data, dict) else "",
            source_uri=source_uri,
            sources=sources,
        )

        # Document titles sometimes carry file hints like "(CLAUDE.md)".
        # Keep title semantics but normalize the entity name to satisfy global naming rules.
        doc_entity_name = re.sub(r"\s*\([^)]+\)$", "", doc_title).strip() or doc_title

        entity_payload = {
            "id": data.get("id"),
            "name": doc_entity_name,
            "type": EntityType.DOCUMENT,
            "summary": data.get("summary", existing.summary if existing else ""),
            "tags": tags,
            "status": data.get("status", existing.status if existing else "current"),
            "parent_id": parent_id,
            "details": details,
            "sources": sources,
            # ADR-022 Document Bundle fields
            "doc_role": doc_role,
            "bundle_highlights": bundle_highlights,
            "highlights_updated_at": highlights_updated_at,
            "change_summary": change_summary,
            "summary_updated_at": summary_updated_at,
        }
        # Document lifecycle updates are governance operations that should remain
        # merge-safe but not be blocked by confirmed-entity protection.
        entity_payload["force"] = data.get("force", True)
        if allow_create_with_id:
            entity_payload["allow_create_with_id"] = True
        for optional_key in ("owner", "visibility", "last_reviewed_at"):
            if optional_key in data:
                entity_payload[optional_key] = data[optional_key]
        if "confirmed_by_user" in data:
            entity_payload["confirmed_by_user"] = data["confirmed_by_user"]

        # --- Helper Ingest: cross-doc duplicate external_id detection (warning only) ---
        # Collect all external_ids being written in this operation
        _helper_warnings: list[str] = []
        _all_new_external_ids: list[str] = []
        if add_source_data and add_source_data.get("external_id"):
            _all_new_external_ids.append(str(add_source_data["external_id"]))
        if update_source_data and update_source_data.get("external_id"):
            _all_new_external_ids.append(str(update_source_data["external_id"]))

        if _all_new_external_ids:
            current_entity_id = data.get("id") or (existing.id if existing else None)
            try:
                all_docs = await self._entities.list_all(type_filter=EntityType.DOCUMENT)
                for ext_id in _all_new_external_ids:
                    for doc in all_docs:
                        if doc.id == current_entity_id:
                            continue
                        for src in (doc.sources or []):
                            if src.get("external_id") == ext_id:
                                _helper_warnings.append(
                                    f"DUPLICATE_EXTERNAL_ID_ACROSS_BUNDLES: "
                                    f"external_id '{ext_id}' 已存在於 doc_id='{doc.id}'。"
                                    f"同一外部文件疑似掛在多個 bundle，請確認是否正確。"
                                )
                                break
            except Exception:
                logger.warning("Cross-doc external_id duplicate check failed", exc_info=True)

        result = await self.upsert_entity(entity_payload)
        saved = result.entity

        # Keep materialized linkage relationships consistent with parent_id as canonical.
        if saved.id:
            if not linked_entity_ids and existing:
                _, existing_related_ids = await self._load_document_linkage_state(saved.id)
                related_ids = existing_related_ids
            await self._sync_document_linkage_relationships(
                doc_id=saved.id,
                parent_id=saved.parent_id,
                related_ids=related_ids,
                remove_stale=True,
            )

        # Attach bundle operation suggestions for tools.py to pick up
        # Also attach helper ingest metadata (noop flag, duplicate warnings)
        saved._bundle_suggestions = suggestions  # type: ignore[attr-defined]
        saved._helper_upsert_meta = data.get("_helper_upsert_meta", {})  # type: ignore[attr-defined]
        saved._helper_warnings = _helper_warnings  # type: ignore[attr-defined]
        return saved

    async def _resolve_document_title(
        self,
        doc_title: str,
        source_type: str,
        source_uri: str,
        sources: list[dict],
    ) -> str:
        """Validate and auto-derive a document title.

        Rules (applied in order):
        1. Bare-domain blacklist: raise ValueError if title is a bare source-type name.
        2. Empty title + GitHub source with valid URL: try H1 from .md file, fallback to filename.
        3. Empty title + non-GitHub source: raise ValueError.

        Returns the resolved title string.
        """
        # doc_title is already stripped by caller
        normalized = doc_title.lower()

        # Rule 1: Bare domain blacklist
        if normalized in BARE_DOMAIN_BLACKLIST:
            raise ValueError(
                f"Document title {doc_title!r} is not descriptive — "
                "title 不得為 source type 名稱或裸域名。"
                f"請提供具體的文件名稱，例如：「{doc_title.title()} 文件規範」"
            )

        # Rule 2/3: Empty title
        if not doc_title:
            if source_type == "github" and source_uri:
                return await self._derive_github_title(source_uri, sources)
            raise ValueError(
                "Document title is required. "
                "title 不得為空，請提供文件名稱。"
            )

        return doc_title

    async def _derive_github_title(self, source_uri: str, sources: list[dict]) -> str:
        """Derive a document title from a GitHub source URI.

        For .md files: attempts to read the file and extract the first H1 heading.
        Falls back to filename. On 404, sets sources[0]['status'] = 'stale'.
        """
        # Extract filename from path as baseline fallback
        try:
            _, _, path, _ = parse_github_url(source_uri)
            filename = path.rsplit("/", 1)[-1]
        except ValueError:
            filename = source_uri.rsplit("/", 1)[-1] or "untitled"

        # Only attempt H1 extraction for .md files
        if not filename.endswith(".md") or self._source_adapter is None:
            return filename

        try:
            content = await self._source_adapter.read_content(source_uri)
            for line in content.splitlines():
                m = re.match(r"^#\s+(.+)", line)
                if m:
                    return m.group(1).strip()
            # No H1 found — fallback to filename
            return filename
        except FileNotFoundError:
            logger.warning("GitHub source 404 for %r — marking stale, using filename", source_uri)
            if sources:
                sources[0]["status"] = "stale"
            return filename
        except Exception:
            logger.warning("Failed to read GitHub source %r for H1 extraction", source_uri, exc_info=True)
            return filename

    async def sync_document_governance(self, data: dict) -> DocumentSyncResult:
        """Perform governance-safe batch sync for document lifecycle operations."""
        operation = str(data.get("sync_mode", "")).strip().lower()
        if operation not in {"rename", "reclassify", "archive", "supersede", "sync_repair"}:
            raise ValueError(
                "sync_mode must be one of: rename, reclassify, archive, supersede, sync_repair"
            )
        doc_id = str(data.get("id", "")).strip()
        if not doc_id:
            raise ValueError("sync document requires id")
        dry_run = bool(data.get("dry_run", False))

        existing = await self._entities.get_by_id(doc_id)
        if existing is None or existing.type != EntityType.DOCUMENT:
            raise ValueError(f"Document entity '{doc_id}' not found")

        current_parent_rel, current_related_rel = await self._load_document_linkage_state(doc_id)
        existing_source_uri = existing.sources[0].get("uri", "") if existing.sources else ""
        before = {
            "name": existing.name,
            "status": existing.status,
            "parent_id": existing.parent_id,
            "source_uri": existing_source_uri,
            "relationship_parent_id": current_parent_rel,
            "relationship_related_ids": current_related_rel,
        }

        update_payload: dict = {"id": doc_id}
        if "title" in data:
            update_payload["title"] = data["title"]
        if "summary" in data:
            update_payload["summary"] = data["summary"]
        if "source" in data:
            update_payload["source"] = data["source"]
        if "linked_entity_ids" in data:
            update_payload["linked_entity_ids"] = data["linked_entity_ids"]
        if "parent_id" in data:
            update_payload["parent_id"] = data["parent_id"]
        if "status" in data:
            update_payload["status"] = data["status"]

        if operation == "archive":
            update_payload.setdefault("status", "archived")
            update_payload["clear_sources"] = True  # 標記需要清空 sources
        if operation == "supersede":
            successor_id = str(data.get("superseded_by_id", "")).strip()
            if not successor_id:
                raise ValueError("supersede requires superseded_by_id")
            successor = await self._entities.get_by_id(successor_id)
            if successor is None or successor.type != EntityType.DOCUMENT:
                raise ValueError("superseded_by_id must point to an existing document entity")
            update_payload.setdefault("status", "stale")
            existing_details = dict(existing.details or {})
            existing_details["superseded_by"] = successor_id
            update_payload["details"] = existing_details

        linked_ids = self._normalize_linked_entity_ids(update_payload.get("linked_entity_ids"))
        if linked_ids:
            target_parent = linked_ids[0]
            target_related = linked_ids[1:]
        else:
            target_parent = update_payload.get("parent_id", existing.parent_id)
            target_related = current_related_rel

        target_status = update_payload.get("status", existing.status)
        target_name = update_payload.get("title", existing.name)
        target_source_uri = existing_source_uri
        if isinstance(update_payload.get("source"), dict):
            target_source_uri = str(
                update_payload["source"].get("uri", existing_source_uri)
            ).strip()

        after = {
            "name": target_name,
            "status": target_status,
            "parent_id": target_parent,
            "source_uri": target_source_uri,
            "relationship_parent_id": target_parent,
            "relationship_related_ids": target_related,
        }
        rel_changes = {
            "add": [],
            "remove": [],
        }
        if current_parent_rel != target_parent:
            if target_parent:
                rel_changes["add"].append({"target_id": target_parent, "type": RelationshipType.PART_OF})
            if current_parent_rel:
                rel_changes["remove"].append({"target_id": current_parent_rel, "type": RelationshipType.PART_OF})
        rel_changes["add"].extend(
            {"target_id": rid, "type": RelationshipType.RELATED_TO}
            for rid in target_related
            if rid not in current_related_rel
        )
        rel_changes["remove"].extend(
            {"target_id": rid, "type": RelationshipType.RELATED_TO}
            for rid in current_related_rel
            if rid not in target_related
        )

        if dry_run:
            return DocumentSyncResult(
                operation=operation,
                dry_run=True,
                document_id=doc_id,
                before=before,
                after=after,
                relationship_changes=rel_changes,
                warnings=None,
                document=None,
            )

        saved = existing if operation == "sync_repair" else await self.upsert_document(update_payload)
        linkage_changes = await self._sync_document_linkage_relationships(
            doc_id=doc_id,
            parent_id=target_parent,
            related_ids=target_related,
            remove_stale=True,
        )
        return DocumentSyncResult(
            operation=operation,
            dry_run=False,
            document_id=doc_id,
            before=before,
            after=after,
            relationship_changes=linkage_changes,
            warnings=None,
            document=saved,
        )

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

        from zenos.domain.knowledge import Gap

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
            # ADR-045 S02: version is a caller-visible revision label for the
            # generated protocol artifact. We store/echo it, but do not branch
            # application behavior on specific version values.
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

            # L2 (module) confirmation gate: require three-question record and concrete impacts
            if entity.type == EntityType.MODULE:
                # Gate 1: three-question record must exist and all answers must be True
                layer_decision = (
                    entity.details.get("layer_decision")
                    if entity.details and isinstance(entity.details, dict)
                    else None
                )
                if layer_decision is None:
                    raise ValueError(
                        f"L2 confirm 失敗：'{entity.name}' 缺少三問判斷紀錄（layer_decision）。"
                        f"請先用 write 更新 entity，在 data 中提供 layer_decision。"
                    )
                q1 = layer_decision.get("q1_persistent")
                q2 = layer_decision.get("q2_cross_role")
                q3 = layer_decision.get("q3_company_consensus")
                if not (q1 and q2 and q3):
                    raise ValueError(
                        f"L2 confirm 失敗：'{entity.name}' 的三問判斷未全通過"
                        f"（q1={q1}, q2={q2}, q3={q3}）。三問必須全部為 True 才能 confirm L2。"
                    )

                # Gate 2: require at least one outgoing concrete impacts relationship
                rels = await self._relationships.list_by_entity(entity.id)
                all_entities = await self._entities.list_all()
                entity_map = {e.id: e for e in all_entities if e.id}
                has_concrete_impacts = any(
                    r.type == RelationshipType.IMPACTS
                    and r.source_entity_id == entity.id
                    and self._is_concrete_impacts_description(r.description)
                    and ((target := entity_map.get(r.target_id)) is not None)
                    and target.status == "active"
                    for r in rels
                )
                if not has_concrete_impacts:
                    raise ValueError(
                        f"L2 confirm 失敗：'{entity.name}' 尚無指向 active entity 的具體 impacts 關聯。"
                        f"請先用 write(collection='relationships') 補充至少 1 條具體 impacts "
                        f"（格式：A 改了什麼→B 的什麼要跟著看），且 target 必須存在並為 active，再 confirm。"
                    )
                # Transition draft/stale → active on confirm
                if entity.status in ("draft", "stale"):
                    entity.status = "active"

            entity.confirmed_by_user = True
            entity.last_reviewed_at = now
            entity.updated_at = now
            await self._entities.upsert(entity)

        elif collection == "documents":
            entity = await self._entities.get_by_id(item_id)
            if entity is None or entity.type != EntityType.DOCUMENT:
                raise ValueError(f"Document '{item_id}' not found")
            entity.confirmed_by_user = True
            entity.updated_at = now
            await self._entities.upsert(entity)

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
                result["documents"] = [
                    e for e in await self._entities.list_unconfirmed()
                    if e.type == EntityType.DOCUMENT
                ]
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

    async def batch_update_document_sources(
        self,
        updates: list[dict],
        *,
        atomic: bool = False,
    ) -> dict:
        """Batch update source URIs for multiple document entities.

        Args:
            updates: List of {"document_id": str, "new_uri": str}
            atomic: If True, all-or-nothing via DB transaction.

        Returns:
            {"updated": [...], "not_found": [...], "errors": [...]}
        """
        if len(updates) > 100:
            raise ValueError(
                f"Batch size {len(updates)} exceeds limit of 100. "
                f"Split into smaller batches."
            )
        if not updates:
            return {"updated": [], "not_found": [], "errors": []}

        for i, item in enumerate(updates):
            if "document_id" not in item or "new_uri" not in item:
                raise ValueError(
                    f"updates[{i}] must have 'document_id' and 'new_uri' keys. "
                    f"Got: {list(item.keys())}"
                )
            doc_id = str(item["document_id"]).strip()
            existing = await self._entities.get_by_id(doc_id)
            if existing is None:
                continue
            sources = list(existing.sources or [])
            target_source = None
            target_source_id = item.get("source_id")
            if target_source_id:
                target_source = next(
                    (src for src in sources if src.get("source_id") == target_source_id),
                    None,
                )
            elif sources:
                target_source = next((src for src in sources if src.get("is_primary")), sources[0])
            source_type = str((target_source or {}).get("type") or "github").strip()
            _validate_document_source_uri(
                {"type": source_type, "uri": item["new_uri"]},
                context=f"batch_update_sources[{i}]",
            )

        return await self._entities.batch_update_source_uris(
            updates, atomic=atomic
        )
