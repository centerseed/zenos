"""GovernanceService — orchestrates ontology-wide governance checks.

Pulls data from all repositories and delegates to pure domain functions
in governance.py. Each method returns a governance result object.
"""

from __future__ import annotations

import logging
import os
import re
from collections import Counter
from pathlib import Path
from typing import Any


from zenos.application.knowledge.governance_ssot_audit import run_governance_ssot_audit
from zenos.domain.governance import (
    _L2_TECH_TERMS,
    _blindspot_threshold,
    _find_active_l2_without_concrete_impacts,
    _is_concrete_impacts_description,
    _task_problem_tokens,
    _tasks_are_similar,
    analyze_blindspots,
    check_governance_review_overdue,
    check_impacts_target_validity,
    check_reverse_impacts,
    compute_health_kpis,
    compute_quality_correction_priority,
    compute_search_unused_signals,
    detect_staleness,
    detect_stale_documents_from_consistency,
    determine_recommended_action,
    find_stale_l2_downstream_entities,
    run_quality_check,
)
from zenos.domain.knowledge import Blindspot, Entity, EntityType
from zenos.domain.shared import QualityCheckItem, QualityReport, StalenessWarning
from zenos.domain.knowledge import BlindspotRepository, EntityRepository, ProtocolRepository, RelationshipRepository

logger = logging.getLogger(__name__)

_LEVEL_PRIORITY = {"green": 0, "yellow": 1, "red": 2}
_LLM_DEPENDENCY_REGISTRY: tuple[dict[str, Any], ...] = (
    {
        "location": "src/zenos/application/knowledge/ontology_service.py::infer_all_classify",
        "path_category": "critical",
        "purpose": "entity_auto_classification",
        "compliant": False,
        "notes": "write(collection='entities') 省略 type 時會呼叫 GovernanceAI infer_all。",
    },
    {
        "location": "src/zenos/application/knowledge/ontology_service.py::l2_semantic_gate",
        "path_category": "optional_enrichment",
        "purpose": "l2_semantic_gate",
        "compliant": True,
        "notes": "L2 三問輔助判斷；失敗時只回 warning，不阻擋 write。",
    },
    {
        "location": "src/zenos/application/knowledge/ontology_service.py::post_save_enrichment",
        "path_category": "optional_enrichment",
        "purpose": "entity_relationship_enrichment",
        "compliant": True,
        "notes": "entity upsert 後補 relationships / doc links；失敗不影響主路徑。",
    },
    {
        "location": "src/zenos/application/action/task_service.py::infer_task_links",
        "path_category": "critical",
        "purpose": "task_auto_linking",
        "compliant": False,
        "notes": "task(action=create) 未帶 linked_entities 時會呼叫 infer_task_links。",
    },
    {
        "location": "src/zenos/interface/mcp/analyze.py::entry_consolidation",
        "path_category": "optional_enrichment",
        "purpose": "entry_consolidation",
        "compliant": True,
        "notes": "analyze(quality) 的 consolidate_entries proposal；失敗不影響主要分析。",
    },
    {
        "location": "src/zenos/interface/mcp/__init__.py::_compress_journal",
        "path_category": "non_critical",
        "purpose": "journal_compression",
        "compliant": True,
        "notes": "工作日誌壓縮為背景整理任務，失敗可跳過。",
    },
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
        task_repo=None,  # TaskRepository (duck typing to avoid circular import)
        tool_event_repo=None,  # ToolEventRepository (duck typing to avoid circular import)
        usage_log_repo=None,  # UsageLogRepository (duck typing to avoid circular import)
        governance_ai: Any = None,  # GovernanceAI (duck typing to avoid circular import)
    ) -> None:
        self._entities = entity_repo
        self._relationships = relationship_repo
        self._protocols = protocol_repo
        self._blindspots = blindspot_repo
        self._tasks = task_repo
        self._tool_events = tool_event_repo
        self._usage_logs = usage_log_repo
        self._governance_ai = governance_ai

    @staticmethod
    def _provider_name_from_model(model: str) -> str:
        model_lower = (model or "").lower()
        if model_lower.startswith("gemini/") or model_lower.startswith("gemini"):
            return "gemini"
        if model_lower.startswith("openai/") or model_lower.startswith("gpt-"):
            return "openai"
        if "/" in model_lower:
            return model_lower.split("/", 1)[0]
        return model_lower or "unknown"

    @staticmethod
    def _rate(numerator: int, denominator: int) -> float:
        if denominator <= 0:
            return 0.0
        return round(numerator / denominator, 4)

    @classmethod
    def _compute_bundle_highlights_coverage(cls, documents: list[Entity]) -> float:
        index_docs = [doc for doc in documents if getattr(doc, "doc_role", None) == "index"]
        if not index_docs:
            return 1.0
        covered = sum(1 for doc in index_docs if list(getattr(doc, "bundle_highlights", []) or []))
        return cls._rate(covered, len(index_docs))

    @classmethod
    def _merge_governance_ssot_signal(cls, signal: dict, governance_ssot: dict) -> dict:
        merged = dict(signal)
        findings = governance_ssot.get("findings", [])
        ssot_level = governance_ssot.get("overall_level", "green")
        red_count = sum(1 for item in findings if item.get("severity") == "red")
        merged.setdefault("kpis", {})
        merged["kpis"]["governance_ssot"] = {"value": red_count, "level": ssot_level}
        merged["governance_ssot"] = governance_ssot
        merged["overall_level"] = cls._worse_level(merged.get("overall_level", "green"), ssot_level)
        merged["recommended_action"] = determine_recommended_action(merged["overall_level"])
        merged.setdefault("red_reasons", [])
        if ssot_level == "red":
            merged["red_reasons"].append({
                "kpi": "governance_ssot",
                "value": red_count,
                "reason": "governance SSOT drift is red",
            })
        return merged

    @classmethod
    def _worse_level(cls, left: str, right: str) -> str:
        return left if _LEVEL_PRIORITY[left] >= _LEVEL_PRIORITY[right] else right

    def _configured_provider_rows(self) -> list[dict[str, Any]]:
        llm = getattr(self._governance_ai, "_llm", None)
        if llm is not None:
            model = str(getattr(llm, "model", "") or "")
            raw_api_key = getattr(llm, "api_key", None)
            api_key_present = bool(
                isinstance(raw_api_key, str)
                and raw_api_key.strip()
                and raw_api_key.strip().lower() not in {"none", "null"}
            )
            return [{
                "name": self._provider_name_from_model(model),
                "model": model,
                "api_key_present": api_key_present,
            }]
        model = os.getenv("ZENOS_LLM_MODEL", "gemini/gemini-2.5-flash-lite")
        raw_api_key = os.getenv("GEMINI_API_KEY")
        return [{
            "name": self._provider_name_from_model(model),
            "model": model,
            "api_key_present": bool(
                raw_api_key
                and raw_api_key.strip()
                and raw_api_key.strip().lower() not in {"none", "null"}
            ),
        }]

    async def _collect_provider_status(self, partner_id: str | None) -> list[dict]:
        telemetry_rows: dict[str, dict[str, Any]] = {}
        if partner_id and self._usage_logs is not None:
            rows = await self._usage_logs.summarize_provider_health(partner_id, days=7, hours=1)
            telemetry_rows = {str(row.get("provider")): row for row in rows}

        providers: dict[str, dict[str, Any]] = {
            row["name"]: dict(row) for row in self._configured_provider_rows() if row.get("name")
        }
        for provider, row in telemetry_rows.items():
            providers.setdefault(provider, {
                "name": provider,
                "model": str(row.get("model", provider)),
                "api_key_present": True,
            })

        statuses: list[dict] = []
        for provider, config in sorted(providers.items()):
            row = telemetry_rows.get(provider, {})
            success_7d = int(row.get("success_count_7d") or 0)
            fallback_7d = int(row.get("fallback_count_7d") or 0)
            exception_7d = int(row.get("exception_count_7d") or 0)
            success_1h = int(row.get("success_count_1h") or 0)
            fallback_1h = int(row.get("fallback_count_1h") or 0)
            exception_1h = int(row.get("exception_count_1h") or 0)
            attempts_7d = success_7d + fallback_7d
            attempts_1h = success_1h + fallback_1h
            fallback_rate_7d = self._rate(fallback_7d, attempts_7d)
            exception_rate_7d = self._rate(exception_7d, attempts_7d)
            error_rate_1h = self._rate(exception_1h, attempts_1h)
            api_key_present = bool(config.get("api_key_present"))

            if not api_key_present:
                status = "down"
            elif exception_rate_7d > 0.05 or fallback_rate_7d > 0.2:
                status = "degraded"
            elif success_7d > 0 or row.get("last_success_at") is not None:
                status = "healthy"
            else:
                status = "degraded"

            notes: list[str] = []
            if not api_key_present:
                notes.append("API key missing")
            if attempts_7d == 0 and success_7d == 0:
                notes.append("近 7 天無 telemetry rows")

            statuses.append({
                "name": provider,
                "status": status,
                "last_success_at": (
                    row["last_success_at"].isoformat()
                    if row.get("last_success_at") is not None
                    else None
                ),
                "error_rate_1h": error_rate_1h,
                "success_count_7d": success_7d,
                "fallback_count_7d": fallback_7d,
                "exception_count_7d": exception_7d,
                "fallback_rate_7d": fallback_rate_7d,
                "exception_rate_7d": exception_rate_7d,
                "model": str(config.get("model") or row.get("model") or ""),
                "notes": "; ".join(notes) if notes else "",
            })
        return statuses

    def _collect_dependency_points(self) -> list[dict]:
        repo_root = Path(__file__).resolve().parents[4]
        points: list[dict] = []
        for entry in _LLM_DEPENDENCY_REGISTRY:
            rel_path = str(entry["location"]).split("::", 1)[0]
            if not (repo_root / rel_path).exists():
                continue
            points.append(dict(entry))
        return points

    @classmethod
    def _merge_llm_health_signal(cls, signal: dict, llm_health: dict) -> dict:
        merged = dict(signal)
        findings = llm_health.get("findings", [])
        llm_level = llm_health.get("overall_level", "green")
        red_count = sum(1 for item in findings if item.get("severity") == "red")
        merged.setdefault("kpis", {})
        merged["kpis"]["llm_health"] = {"value": red_count, "level": llm_level}
        merged["llm_health"] = llm_health
        merged["overall_level"] = cls._worse_level(merged.get("overall_level", "green"), llm_level)
        merged["recommended_action"] = determine_recommended_action(merged["overall_level"])
        merged.setdefault("red_reasons", [])
        if llm_level == "red":
            merged["red_reasons"].append({
                "kpi": "llm_health",
                "value": red_count,
                "reason": "server LLM dependency or provider health is red",
            })
        return merged

    async def analyze_llm_health(self, partner_id: str | None = None) -> dict:
        """Analyze provider health and server-side LLM dependency points."""
        provider_status = await self._collect_provider_status(partner_id)
        dependency_points = self._collect_dependency_points()

        findings: list[dict] = []
        for point in dependency_points:
            if point.get("compliant", False):
                continue
            severity = "red" if point["path_category"] == "critical" else "yellow"
            findings.append({
                "severity": severity,
                "type": (
                    "critical_path_llm_dependency"
                    if point["path_category"] == "critical"
                    else "deprecated_dependency"
                ),
                "location": point["location"],
                "description": point["notes"],
            })

        for provider in provider_status:
            provider_name = provider["name"]
            if provider["status"] == "down":
                findings.append({
                    "severity": "red",
                    "type": "provider_down",
                    "location": provider_name,
                    "description": provider.get("notes") or f"{provider_name} provider is down",
                })
            if provider["fallback_rate_7d"] > 0.2:
                findings.append({
                    "severity": "yellow",
                    "type": "provider_fallback_rate_high",
                    "location": provider_name,
                    "description": f"{provider_name} fallback rate over 7d = {provider['fallback_rate_7d']:.0%}",
                })
            if provider["exception_rate_7d"] > 0.05:
                findings.append({
                    "severity": "red",
                    "type": "provider_exception_rate_high",
                    "location": provider_name,
                    "description": f"{provider_name} exception rate over 7d = {provider['exception_rate_7d']:.0%}",
                })

        overall_level = "green"
        for finding in findings:
            overall_level = self._worse_level(overall_level, str(finding["severity"]))

        return {
            "check_type": "llm_health",
            "provider_status": provider_status,
            "dependency_points": dependency_points,
            "findings": findings,
            "overall_level": overall_level,
        }

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

    async def run_quality_check(
        self,
        tasks: list | None = None,
        entries_by_entity: dict[str, int] | None = None,
    ) -> QualityReport:
        """Run the full quality checklist across the ontology.

        Fetches all entities (including type=document), protocols, blindspots,
        and relationships, then delegates to domain.governance.run_quality_check.

        Args:
            tasks: Optional list of Task objects for duplicate task detection.
                   If None, attempts to fetch from task_repo if available.
            entries_by_entity: Optional mapping of entity_id -> entry count.
                               Used for entry sparsity check.
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

        # Fetch tasks if not provided but task_repo is available
        if tasks is None and self._tasks is not None:
            try:
                tasks = await self._tasks.list_all(limit=500)
            except Exception:
                tasks = None

        quality_report = run_quality_check(
            entities=entities,
            documents=documents,
            protocols=protocols,
            blindspots=blindspots,
            relationships=relationships,
            tasks=tasks,
            entries_by_entity=entries_by_entity,
        )

        return quality_report

    async def compute_health_signal(self) -> dict:
        """Compute lightweight health signal (ADR-020).

        Queries repos, runs quality check for score + l2 repairs,
        then delegates to domain pure function compute_health_kpis.

        Returns dict with kpis, overall_level, recommended_action, red_reasons.
        """
        all_entities = await self._entities.list_all()
        entities = [e for e in all_entities if e.type != EntityType.DOCUMENT]
        documents = [e for e in all_entities if e.type == EntityType.DOCUMENT]
        blindspots = await self._blindspots.list_all()

        # Collect protocols
        protocols = []
        for entity in entities:
            if entity.id:
                protocol = await self._protocols.get_by_entity(entity.id)
                if protocol is not None:
                    protocols.append(protocol)

        # Get quality_score and l2_repairs via existing run_quality_check
        relationships = await self._load_all_relationships(all_entities)
        quality_report = run_quality_check(
            entities=entities,
            documents=documents,
            protocols=protocols,
            blindspots=blindspots,
            relationships=relationships,
        )
        quality_score = quality_report.score

        # Count active L2 missing impacts
        l2_missing = _find_active_l2_without_concrete_impacts(entities, relationships)
        l2_repairs_count = len(l2_missing)

        # Determine bootstrap mode: < 50 entities
        bootstrap = len(entities) < 50

        signal = compute_health_kpis(
            entities=entities,
            protocols=protocols,
            blindspots=blindspots,
            quality_score=quality_score,
            l2_repairs_count=l2_repairs_count,
            bundle_highlights_coverage=self._compute_bundle_highlights_coverage(documents),
            bootstrap=bootstrap,
        )
        try:
            from zenos.infrastructure.context import current_partner_id as _current_partner_id

            llm_health = await self.analyze_llm_health(_current_partner_id.get())
            signal = self._merge_llm_health_signal(signal, llm_health)
        except Exception:
            logger.warning("compute_health_signal: llm health enrichment failed", exc_info=True)
        try:
            signal = self._merge_governance_ssot_signal(signal, run_governance_ssot_audit())
        except Exception:
            logger.warning("compute_health_signal: governance ssot enrichment failed", exc_info=True)
        return signal

    async def run_staleness_check(self) -> dict:
        """Detect staleness patterns across entities and documents.

        Fetches all entities and relationships, then delegates to
        domain.governance.detect_staleness and detect_stale_documents_from_consistency.

        Returns a dict with:
          - warnings: list[StalenessWarning]
          - document_consistency_warnings: list[dict]
        """
        all_entities = await self._entities.list_all()
        entities = [e for e in all_entities if e.type != EntityType.DOCUMENT]
        documents = [e for e in all_entities if e.type == EntityType.DOCUMENT]
        relationships = await self._load_all_relationships(all_entities)

        staleness_warnings = detect_staleness(
            entities=entities,
            documents=documents,
            relationships=relationships,
        )
        doc_consistency_warnings = detect_stale_documents_from_consistency(
            entities=all_entities,
            relationships=relationships,
        )
        return {
            "warnings": staleness_warnings,
            "document_consistency_warnings": doc_consistency_warnings,
        }

    async def run_quality_correction_priority(self) -> dict:
        """Compute quality correction priority for L2 entities.

        Returns a dict with:
          - total_l2_entities: int
          - ranked: list[dict]
          - needs_immediate_review: int (score > 1.5)
        """
        all_entities = await self._entities.list_all()
        entities = [e for e in all_entities if e.type != EntityType.DOCUMENT]
        relationships = await self._load_all_relationships(all_entities)

        ranked = compute_quality_correction_priority(entities, relationships)
        needs_immediate_review = sum(1 for r in ranked if r["score"] > 1.5)
        return {
            "total_l2_entities": len(ranked),
            "ranked": ranked,
            "needs_immediate_review": needs_immediate_review,
        }

    async def infer_blindspots_from_tasks(self) -> list[dict]:
        """Infer blindspot suggestions from task execution history.

        For each active L2 entity, find done/cancelled tasks that share
        problem-signal keywords. If a cluster of similar-problem tasks
        meets the dynamic threshold, suggest a blindspot.

        Returns list of dicts (empty if task_repo is None).
        """
        if self._tasks is None:
            return []

        all_entities = await self._entities.list_all()
        active_modules = [
            e for e in all_entities
            if e.type == EntityType.MODULE and e.status == "active" and e.id
        ]

        suggestions: list[dict] = []
        for mod in active_modules:
            tasks = await self._tasks.list_all(
                linked_entity=mod.id,
                status=["done", "cancelled"],
                limit=200,
            )
            if not tasks:
                continue

            task_tokens = [
                (t, _task_problem_tokens(
                    getattr(t, "result", None) or "",
                    getattr(t, "description", None) or "",
                ))
                for t in tasks
            ]
            # Only keep tasks with at least one problem token
            problem_tasks = [(t, toks) for t, toks in task_tokens if toks]
            if not problem_tasks:
                continue

            threshold = _blindspot_threshold(len(tasks))

            # Find clusters: group tasks by shared problem tokens
            # Build adjacency: task i similar to task j
            n = len(problem_tasks)
            cluster_map: dict[int, int] = {}  # task index -> cluster root
            for i in range(n):
                for j in range(i + 1, n):
                    if _tasks_are_similar(problem_tasks[i][1], problem_tasks[j][1]):
                        root_i = cluster_map.get(i, i)
                        root_j = cluster_map.get(j, j)
                        if root_i != root_j:
                            for k, v in list(cluster_map.items()):
                                if v == root_j:
                                    cluster_map[k] = root_i
                            cluster_map[j] = root_i
                        elif i not in cluster_map:
                            cluster_map[i] = i
                        if j not in cluster_map:
                            cluster_map[j] = root_i

            # Determine cluster sizes
            roots = [cluster_map.get(i, i) for i in range(n)]
            cluster_counts = Counter(roots)
            max_cluster_root = max(cluster_counts, key=lambda k: cluster_counts[k])
            max_size = cluster_counts[max_cluster_root]

            if max_size < threshold:
                continue

            # Collect matched tasks and dominant keywords for the largest cluster
            matched_tasks = [
                problem_tasks[i][0]
                for i in range(n)
                if cluster_map.get(i, i) == max_cluster_root
            ]
            all_tokens: set[str] = set()
            for _, toks in [problem_tasks[i] for i in range(n) if cluster_map.get(i, i) == max_cluster_root]:
                all_tokens |= toks
            keyword_sample = "、".join(sorted(all_tokens)[:3])

            suggestions.append({
                "entity_id": mod.id,
                "entity_name": mod.name,
                "pattern_summary": f"{max_size} 張 task 提到 '{keyword_sample}' 問題",
                "matched_tasks": [getattr(t, "id", str(t)) for t in matched_tasks],
                "suggested_blindspot": {
                    "description": f"{mod.name} 有反覆出現的問題：{keyword_sample}，agent 需要額外處理",
                    "severity": "yellow",
                    "suggested_action": "在 sources 中記錄 workaround 步驟，或更新 L2 summary 加入已知限制",
                },
            })

        return suggestions

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

    async def compute_search_unused_for_partner(
        self,
        partner_id: str,
        days: int = 30,
    ) -> list[dict]:
        """Compute search-unused signals for all entities of a partner.

        Fetches entity usage stats from ToolEventRepository and delegates to
        domain function compute_search_unused_signals.

        Returns list of dicts for entities with unused_ratio > 0.8 and
        search_count >= 3 (flagged=True only).
        """
        if self._tool_events is None:
            return []
        usage_stats = await self._tool_events.get_entity_usage_stats(partner_id, days=days)
        all_entities = await self._entities.list_all()
        entities = [e for e in all_entities if e.type != EntityType.DOCUMENT]
        return compute_search_unused_signals(usage_stats, entities)
