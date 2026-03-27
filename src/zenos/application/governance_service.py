"""GovernanceService — orchestrates ontology-wide governance checks.

Pulls data from all repositories and delegates to pure domain functions
in governance.py. Each method returns a governance result object.
"""

from __future__ import annotations

import re

from zenos.domain.governance import (
    _L2_TECH_TERMS,
    _find_active_l2_without_concrete_impacts,
    _is_concrete_impacts_description,
    analyze_blindspots,
    check_governance_review_overdue,
    check_impacts_target_validity,
    check_reverse_impacts,
    detect_staleness,
    find_stale_l2_downstream_entities,
    run_quality_check,
)
from zenos.domain.models import (
    Blindspot,
    EntityType,
    QualityReport,
    StalenessWarning,
)
from zenos.domain.repositories import (
    BlindspotRepository,
    EntityRepository,
    ProtocolRepository,
    RelationshipRepository,
)


class GovernanceService:
    """Application-layer service for ontology-wide governance analysis."""

    def __init__(
        self,
        entity_repo: EntityRepository,
        document_repo: object | None = None,  # deprecated, kept for backward compat
        relationship_repo: RelationshipRepository | None = None,
        protocol_repo: ProtocolRepository | None = None,
        blindspot_repo: BlindspotRepository | None = None,
    ) -> None:
        self._entities = entity_repo
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

    @staticmethod
    def _semantic_tokens(*values: str) -> set[str]:
        text = " ".join(v for v in values if v).lower()
        tokens = re.findall(r"[A-Za-z0-9\u4e00-\u9fff][A-Za-z0-9\u4e00-\u9fff_\-]{1,}", text)
        stopwords = {
            "the", "and", "for", "with", "from", "that", "this",
            "zenos", "module", "product", "document", "entity",
            "系統", "功能", "文件", "模組", "產品", "相關", "流程",
        }
        return {token for token in tokens if token not in stopwords and len(token) >= 2}

    @staticmethod
    def _entity_tag_list(value: list[str] | str) -> list[str]:
        if isinstance(value, list):
            return [str(v).strip() for v in value if str(v).strip()]
        if isinstance(value, str) and value.strip():
            return [value.strip()]
        return []

    @classmethod
    def _has_technical_summary(cls, summary: str) -> bool:
        return any(
            re.search(r"\b" + re.escape(term) + r"\b", summary or "", re.IGNORECASE)
            for term in _L2_TECH_TERMS
        )

    @classmethod
    def _draft_summary(cls, entity, parent_name: str | None) -> str:
        what = cls._entity_tag_list(entity.tags.what)[:2]
        who = cls._entity_tag_list(entity.tags.who)[:3]
        what_txt = "、".join(what) if what else entity.name
        who_txt = "、".join(who) if who else "公司不同角色"
        scope_prefix = f"在 {parent_name} 中，" if parent_name else ""
        why = (entity.tags.why or "").strip()
        if why:
            return (
                f"{scope_prefix}{entity.name}是與{what_txt}相關的公司共識概念，"
                f"讓{who_txt}對同一件事有一致理解。這個概念存在是為了{why}。"
            )
        return (
            f"{scope_prefix}{entity.name}是與{what_txt}相關的公司共識概念，"
            f"讓{who_txt}對同一件事有一致理解。"
        )

    @classmethod
    def _draft_impacts_description(cls, source, target) -> str:
        source_terms = cls._entity_tag_list(source.tags.what)
        target_terms = cls._entity_tag_list(target.tags.what)
        source_focus = source_terms[0] if source_terms else source.name
        target_focus = target_terms[0] if target_terms else target.name
        return (
            f"{source_focus}的規則或邊界改了→{target_focus}的流程、說法或檢查點要跟著看"
        )

    async def infer_l2_backfill_proposals(self) -> list[dict]:
        """Infer migration/backfill proposals for existing L2 entities."""
        all_entities = await self._entities.list_all()
        entities = [e for e in all_entities if e.type != EntityType.DOCUMENT]
        documents = [e for e in all_entities if e.type == EntityType.DOCUMENT]
        relationships = await self._load_all_relationships(all_entities)

        entity_map = {e.id: e for e in entities if e.id}
        docs_by_parent: dict[str, list] = {}
        for doc in documents:
            if getattr(doc, "parent_id", None):
                docs_by_parent.setdefault(doc.parent_id, []).append(doc)

        modules_without_impacts = {
            e.id: e
            for e in _find_active_l2_without_concrete_impacts(entities, relationships)
            if e.id
        }

        outgoing_concrete_impacts: dict[str, list] = {}
        for rel in relationships:
            if rel.type != "impacts" or not _is_concrete_impacts_description(rel.description):
                continue
            outgoing_concrete_impacts.setdefault(rel.source_entity_id, []).append(rel)

        proposals: list[dict] = []
        modules = [
            e for e in entities
            if e.type == EntityType.MODULE and e.status in ("active", "draft") and e.id
        ]
        for mod in modules:
            reasons: list[str] = []
            repair_actions: list[str] = []
            if mod.status == "draft":
                reasons.append("L2 尚未 confirm，仍為 draft 狀態")
                repair_actions.append("補出至少 1 條具體 impacts 後使用 confirm 升為 active")
                override_reason = (
                    mod.details.get("manual_override_reason")
                    if mod.details and isinstance(mod.details, dict)
                    else None
                )
                if override_reason:
                    reasons.append(f"force 寫入，manual_override_reason: {override_reason}")
                    repair_actions.append("補出具體 impacts 後 confirm，或降級為 L3")
            if mod.id in modules_without_impacts:
                reasons.append("缺少具體 impacts，還不能算完成的 L2")
                repair_actions.append("補出至少 1 條具體 impacts，或降級為 L3")
            if self._has_technical_summary(mod.summary):
                reasons.append("summary 仍偏技術語言，不像跨角色共識概念")
                repair_actions.append("改寫 summary，避免 API / schema / backend 等工程術語")
            if len(self._entity_tag_list(mod.tags.what)) >= 3:
                reasons.append("tags.what 涵蓋範圍過廣，可能混了多個可獨立改變概念")
                repair_actions.append("檢查是否應拆成多個 L2")

            if not reasons:
                continue

            parent_name = entity_map.get(mod.parent_id).name if mod.parent_id and entity_map.get(mod.parent_id) else None
            mod_tokens = self._semantic_tokens(
                mod.name,
                mod.summary,
                " ".join(self._entity_tag_list(mod.tags.what)),
                " ".join(self._entity_tag_list(mod.tags.who)),
                mod.tags.why,
                mod.tags.how,
            )

            candidate_impacts: list[dict] = []
            siblings = [
                e for e in modules
                if e.id != mod.id and e.parent_id == mod.parent_id
            ]
            for sibling in siblings:
                sibling_tokens = self._semantic_tokens(
                    sibling.name,
                    sibling.summary,
                    " ".join(self._entity_tag_list(sibling.tags.what)),
                    sibling.tags.why,
                    sibling.tags.how,
                )
                overlap = sorted(mod_tokens & sibling_tokens)
                if not overlap:
                    continue
                candidate_impacts.append({
                    "target_id": sibling.id,
                    "target_name": sibling.name,
                    "description": self._draft_impacts_description(mod, sibling),
                    "basis": f"shared terms: {', '.join(overlap[:4])}",
                })
            candidate_impacts = candidate_impacts[:3]

            source_documents = [
                {
                    "id": doc.id,
                    "title": doc.name,
                    "summary": doc.summary,
                    "source_uri": (doc.sources[0].get("uri", "") if getattr(doc, "sources", None) else ""),
                }
                for doc in docs_by_parent.get(mod.id, [])[:3]
            ]

            proposals.append({
                "entity_id": mod.id,
                "entity_name": mod.name,
                "product_id": mod.parent_id,
                "product_name": parent_name,
                "issues": reasons,
                "repair_actions": repair_actions,
                "suggested_summary": self._draft_summary(mod, parent_name),
                "candidate_impacts": candidate_impacts,
                "source_documents": source_documents,
                "existing_impacts_count": len(outgoing_concrete_impacts.get(mod.id, [])),
            })

        return proposals

    async def run_quality_check(self) -> QualityReport:
        """Run the full 9-item quality checklist across the ontology.

        Fetches all entities (including type=document), protocols, blindspots,
        and relationships, then delegates to domain.governance.run_quality_check.
        """
        all_entities = await self._entities.list_all()
        # Split: non-document entities vs document entities
        entities = [e for e in all_entities if e.type != EntityType.DOCUMENT]
        documents = [e for e in all_entities if e.type == EntityType.DOCUMENT]
        blindspots = await self._blindspots.list_all()
        relationships = await self._load_all_relationships(all_entities)

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

        Fetches all entities and relationships, then delegates to
        domain.governance.detect_staleness.
        """
        all_entities = await self._entities.list_all()
        entities = [e for e in all_entities if e.type != EntityType.DOCUMENT]
        documents = [e for e in all_entities if e.type == EntityType.DOCUMENT]
        relationships = await self._load_all_relationships(all_entities)

        return detect_staleness(
            entities=entities,
            documents=documents,
            relationships=relationships,
        )

    async def check_impacts_target_validity(self) -> list[dict]:
        """Check that all concrete impacts relationships point to valid entities."""
        all_entities = await self._entities.list_all()
        entities = [e for e in all_entities if e.type != EntityType.DOCUMENT]
        relationships = await self._load_all_relationships(all_entities)
        return check_impacts_target_validity(entities, relationships)

    async def find_stale_l2_downstream_entities(self) -> list[dict]:
        """Find L3 entities under stale L2 modules."""
        all_entities = await self._entities.list_all()
        entities = [e for e in all_entities if e.type != EntityType.DOCUMENT]
        return find_stale_l2_downstream_entities(entities)

    async def check_reverse_impacts(self) -> list[dict]:
        """Check if recently modified entities are targeted by impacts relationships."""
        all_entities = await self._entities.list_all()
        entities = [e for e in all_entities if e.type != EntityType.DOCUMENT]
        relationships = await self._load_all_relationships(all_entities)
        return check_reverse_impacts(entities, relationships)

    async def check_governance_review_overdue(self) -> list[dict]:
        """Find active L2 modules overdue for governance review (90-day period).

        Returns list of dicts with entity_id, entity_name, last_reviewed_at,
        days_overdue, and suggested_action.
        """
        all_entities = await self._entities.list_all()
        entities = [e for e in all_entities if e.type != EntityType.DOCUMENT]
        return check_governance_review_overdue(entities)

    async def run_blindspot_analysis(self) -> list[Blindspot]:
        """Infer blind spots by cross-referencing ontology layers.

        Fetches all entities and relationships, then delegates to
        domain.governance.analyze_blindspots.
        """
        all_entities = await self._entities.list_all()
        entities = [e for e in all_entities if e.type != EntityType.DOCUMENT]
        documents = [e for e in all_entities if e.type == EntityType.DOCUMENT]
        relationships = await self._load_all_relationships(all_entities)

        return analyze_blindspots(
            entities=entities,
            documents=documents,
            relationships=relationships,
        )
