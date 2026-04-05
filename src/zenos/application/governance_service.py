"""GovernanceService — orchestrates ontology-wide governance checks.

Pulls data from all repositories and delegates to pure domain functions
in governance.py. Each method returns a governance result object.
"""

from __future__ import annotations

import logging
import re
from collections import Counter
from typing import Any

from pydantic import BaseModel as _PydanticBaseModel

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
    compute_quality_correction_priority,
    compute_search_unused_signals,
    detect_staleness,
    detect_stale_documents_from_consistency,
    find_stale_l2_downstream_entities,
    run_quality_check,
)
from zenos.domain.models import (
    Blindspot,
    Entity,
    EntityType,
    QualityCheckItem,
    QualityReport,
    Severity,
    StalenessWarning,
)
from zenos.domain.repositories import (
    BlindspotRepository,
    EntityRepository,
    ProtocolRepository,
    RelationshipRepository,
)

logger = logging.getLogger(__name__)

# Graph topology constants
LEVERAGE_THRESHOLD = 3  # out-degree >= this value flags a high-impact node


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
        governance_ai: Any = None,  # GovernanceAI (duck typing to avoid circular import)
    ) -> None:
        self._entities = entity_repo
        self._relationships = relationship_repo
        self._protocols = protocol_repo
        self._blindspots = blindspot_repo
        self._tasks = task_repo
        self._tool_events = tool_event_repo
        self._governance_ai = governance_ai

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

    async def analyze_graph_topology(self) -> list[dict]:
        """Detect graph-topology blindspots: isolated nodes, leverage nodes, cycles, goal disconnects.

        Returns a list of issue dicts, each with a 'type' field indicating the problem.
        Non-DOCUMENT entities only.
        """
        all_entities = await self._entities.list_all()
        entities = [e for e in all_entities if e.type != EntityType.DOCUMENT]
        relationships = await self._load_all_relationships(all_entities)

        # Build graph structures
        entity_map: dict[str, Entity] = {e.id: e for e in entities if e.id}
        out_degree: dict[str, int] = {e.id: 0 for e in entities if e.id}
        entity_set: set[str] = set()  # entity ids that appear in any relationship
        adj: dict[str, list[str]] = {e.id: [] for e in entities if e.id}
        parent_map: dict[str, str] = {}
        edge_pairs: set[tuple[str, str]] = set()

        for rel in relationships:
            src = rel.source_entity_id
            tgt = rel.target_id
            entity_set.add(src)
            entity_set.add(tgt)
            if src in out_degree:
                out_degree[src] += 1
            if src in adj:
                adj[src].append(tgt)
            edge_pairs.add((src, tgt))

        # Include parent-child hierarchy as structural edges so topology analysis
        # matches the graph users actually see in the dashboard.
        for entity in entities:
            if not entity.id or not entity.parent_id:
                continue
            src = entity.parent_id
            tgt = entity.id
            if src not in entity_map:
                continue
            if (src, tgt) in edge_pairs:
                continue
            entity_set.add(src)
            entity_set.add(tgt)
            if src in out_degree:
                out_degree[src] += 1
            if src in adj:
                adj[src].append(tgt)
            edge_pairs.add((src, tgt))
            parent_map[tgt] = src

        issues: list[dict] = []

        # --- Isolated nodes ---
        for entity in entities:
            if not entity.id:
                continue
            if entity.id not in entity_set:
                issues.append({
                    "type": "isolated_node",
                    "entity_id": entity.id,
                    "entity_name": entity.name,
                    "description": (
                        f"「{entity.name}」沒有任何關聯，可能是孤立的知識節點或待整合的概念。"
                    ),
                })

        # --- Leverage nodes (high out-degree, no docs) ---
        for entity in entities:
            if not entity.id:
                continue
            out_deg = out_degree.get(entity.id, 0)
            if out_deg >= LEVERAGE_THRESHOLD:
                issues.append({
                    "type": "leverage_node_no_docs",
                    "entity_id": entity.id,
                    "entity_name": entity.name,
                    "out_degree": out_deg,
                    "description": (
                        f"「{entity.name}」有 {out_deg} 條出邊，影響面廣，建議確認是否有文件記錄。"
                    ),
                })

        # --- Circular dependencies (iterative DFS) ---
        WHITE, GRAY, BLACK = 0, 1, 2
        color: dict[str, int] = {e.id: WHITE for e in entities if e.id}
        cycles_found: list[list[str]] = []

        for start_id in list(color.keys()):
            if color.get(start_id) != WHITE:
                continue
            if len(cycles_found) >= 3:
                break
            # Iterative DFS with explicit stack: (node_id, iterator_over_neighbors, path)
            stack: list[tuple[str, int, list[str]]] = [(start_id, 0, [start_id])]
            color[start_id] = GRAY
            while stack and len(cycles_found) < 3:
                node, idx, path = stack[-1]
                neighbors = adj.get(node, [])
                if idx < len(neighbors):
                    stack[-1] = (node, idx + 1, path)
                    nxt = neighbors[idx]
                    if nxt not in color:
                        continue
                    if color[nxt] == GRAY:
                        # Found a cycle — extract path from current path
                        cycle_start = path.index(nxt)
                        cycle_path = path[cycle_start:] + [nxt]
                        cycle_names = [
                            entity_map[n].name if n in entity_map else n
                            for n in cycle_path
                        ]
                        cycles_found.append(cycle_names)
                    elif color[nxt] == WHITE:
                        color[nxt] = GRAY
                        stack.append((nxt, 0, path + [nxt]))
                else:
                    color[node] = BLACK
                    stack.pop()

        for path in cycles_found:
            issues.append({
                "type": "circular_dependency",
                "path": path,
                "description": f"發現循環依賴：{' → '.join(path)}，可能造成邏輯矛盾。",
            })

        # --- Goal disconnected (L2 entity types that cannot reach any GOAL) ---
        # Only MODULE is the current L2 type in the domain model.
        _L2_TYPES = {EntityType.MODULE}
        goal_ids = {e.id for e in entities if e.type == EntityType.GOAL and e.id}

        for entity in entities:
            if not entity.id:
                continue
            if entity.type not in _L2_TYPES:
                continue
            # BFS from entity following outgoing edges
            visited: set[str] = set()
            queue = [entity.id]
            reached_goal = False
            while queue:
                current = queue.pop(0)
                if current in visited:
                    continue
                visited.add(current)
                if current in goal_ids:
                    reached_goal = True
                    break
                for nxt in adj.get(current, []):
                    if nxt not in visited:
                        queue.append(nxt)
                parent_id = parent_map.get(current)
                if parent_id and parent_id not in visited:
                    queue.append(parent_id)
            if not reached_goal:
                issues.append({
                    "type": "goal_disconnected",
                    "entity_id": entity.id,
                    "entity_name": entity.name,
                    "description": (
                        f"「{entity.name}」無法追溯到任何目標節點，可能是與公司目標脫節的知識孤島。"
                    ),
                })

        return issues

    async def suggest_relationship_verb(
        self,
        source_entity: Entity,
        target_entity: Entity,
    ) -> list[str]:
        """Suggest Chinese verb phrases describing the relationship from source to target.

        Uses GovernanceAI's LLM client. Returns empty list on any failure.
        """
        if self._governance_ai is None:
            return []
        llm = getattr(self._governance_ai, "_llm", None)
        if llm is None:
            return []

        source_name = source_entity.name
        target_name = target_entity.name
        source_what = ", ".join(
            source_entity.tags.what
            if isinstance(source_entity.tags.what, list)
            else [source_entity.tags.what]
        ) if source_entity.tags.what else source_name
        target_what = ", ".join(
            target_entity.tags.what
            if isinstance(target_entity.tags.what, list)
            else [target_entity.tags.what]
        ) if target_entity.tags.what else target_name

        class _VerbSuggestion(_PydanticBaseModel):
            verbs: list[str]

        messages = [
            {
                "role": "system",
                "content": (
                    "You are an ontology assistant. "
                    'Return a JSON object {"verbs": [...]} with 2-3 short Chinese verb phrases.'
                ),
            },
            {
                "role": "user",
                "content": (
                    f'Two knowledge nodes: "{source_name}" (about: {source_what}) '
                    f'and "{target_name}" (about: {target_what}).\n'
                    "Suggest 2-3 short Chinese verb phrases (2-5 characters each) that best describe "
                    "how the first node relates to the second.\n"
                    "Examples: 校準, 觸發, 驅動, 限制, 依賴, 啟用, 支撐"
                ),
            },
        ]

        try:
            result = llm.chat_structured(
                messages=messages,
                response_schema=_VerbSuggestion,
                temperature=0.3,
            )
            return [str(v) for v in result.verbs if v][:3]
        except Exception:
            logger.warning("suggest_relationship_verb failed", exc_info=True)
            return []

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

        # --- verb_completeness: add warning for entities with relationships but missing verbs ---
        entity_ids_with_rels: dict[str, list] = {}
        for rel in relationships:
            entity_ids_with_rels.setdefault(rel.source_entity_id, []).append(rel)

        total_rels = len(relationships)
        verbed_rels = sum(1 for r in relationships if r.verb)
        verb_rate = verbed_rels / total_rels if total_rels > 0 else 1.0

        # Per-entity: entities with at least one relationship but zero verbs
        entities_missing_verb: list[str] = []
        entity_name_map = {e.id: e.name for e in entities if e.id}
        for eid, rels in entity_ids_with_rels.items():
            if rels and not any(r.verb for r in rels):
                entities_missing_verb.append(entity_name_map.get(eid, eid))

        verb_item = QualityCheckItem(
            name="relationship_verb_completeness",
            passed=len(entities_missing_verb) == 0,
            detail=(
                f"{len(entities_missing_verb)} 個節點的所有關聯均缺少動詞（verb）："
                + ", ".join(f"'{n}'" for n in entities_missing_verb[:5])
                + (f" ... (+{len(entities_missing_verb) - 5})" if len(entities_missing_verb) > 5 else "")
                if entities_missing_verb
                else f"所有關聯均有動詞標記（{verbed_rels}/{total_rels}）"
            ),
            weight=1,
        )
        # Add to warnings list (non-blocking, information only)
        quality_report.warnings.append(verb_item)

        # Partner-level: if overall verb fill rate < 50%, add a warning
        if total_rels > 0 and verb_rate < 0.5:
            partner_verb_item = QualityCheckItem(
                name="partner_verb_fill_rate_low",
                passed=True,  # warning only
                detail=(
                    f"整體關聯動詞填寫率 {verb_rate:.0%}（{verbed_rels}/{total_rels}），"
                    "低於 50% 建議值，語意完整度不足。"
                ),
                weight=1,
            )
            quality_report.warnings.append(partner_verb_item)

        return quality_report

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
        domain.governance.analyze_blindspots. Also runs graph topology analysis
        and persists topology-derived blindspots via blindspot_repo.add().
        """
        all_entities = await self._entities.list_all()
        entities = [e for e in all_entities if e.type != EntityType.DOCUMENT]
        documents = [e for e in all_entities if e.type == EntityType.DOCUMENT]
        relationships = await self._load_all_relationships(all_entities)

        blindspots = analyze_blindspots(
            entities=entities,
            documents=documents,
            relationships=relationships,
        )

        # Run graph topology analysis and persist results
        topology_issues = await self.analyze_graph_topology()
        if topology_issues and self._blindspots is not None:
            existing_blindspots = await self._blindspots.list_all()
            existing_descriptions = {b.description for b in existing_blindspots}
            for issue in topology_issues:
                if issue.get("description", "") in existing_descriptions:
                    continue
                issue_type = issue.get("type", "topology")
                entity_id = issue.get("entity_id")
                related_ids = [entity_id] if entity_id else []
                # For circular_dependency, no single entity_id
                if issue_type == "circular_dependency":
                    severity = Severity.RED.value
                    suggested_action = "檢查循環依賴的節點，重新設計關聯方向，消除邏輯矛盾。"
                elif issue_type == "isolated_node":
                    severity = Severity.YELLOW.value
                    suggested_action = "為此節點建立至少一條關聯，或確認是否需要整合到現有概念。"
                elif issue_type == "leverage_node_no_docs":
                    severity = Severity.YELLOW.value
                    suggested_action = "為此高影響節點補充說明文件，確保知識已記錄。"
                else:  # goal_disconnected
                    severity = Severity.YELLOW.value
                    suggested_action = "為此節點建立通往目標節點的關聯路徑，確保與公司目標一致。"

                topology_blindspot = Blindspot(
                    description=issue.get("description", ""),
                    severity=severity,
                    related_entity_ids=related_ids,
                    suggested_action=suggested_action,
                )
                try:
                    persisted = await self._blindspots.add(topology_blindspot)
                    blindspots.append(persisted)
                except Exception:
                    logger.warning("Failed to persist topology blindspot", exc_info=True)
                    blindspots.append(topology_blindspot)
                finally:
                    existing_descriptions.add(topology_blindspot.description)

        return blindspots

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
