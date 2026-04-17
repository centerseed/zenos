"""Governance rules — encodes REF-ontology-methodology.md business logic.

All functions are pure: they take domain objects in, return result objects out.
Zero external dependencies.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from .knowledge import (
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
    Tags,
)
from .shared import (
    QualityCheckItem,
    QualityReport,
    SplitRecommendation,
    StalenessWarning,
    TagConfidence,
)


def _safe_str(val) -> str:
    """Safely convert a tag field value to str (handles list/str/None)."""
    if val is None:
        return ""
    if isinstance(val, list):
        return " ".join(str(v) for v in val)
    return str(val)


def _jaccard_similarity(a: str, b: str) -> float:
    """Token-level Jaccard similarity for short text."""
    tokens_a = set(a.lower().split())
    tokens_b = set(b.lower().split())
    if not tokens_a or not tokens_b:
        return 0.0
    intersection = tokens_a & tokens_b
    union = tokens_a | tokens_b
    return len(intersection) / len(union)


# ──────────────────────────────────────────────
# 1. Split-criteria check (拆分粒度檢查)
# ──────────────────────────────────────────────

def check_split_criteria(
    entity: Entity,
    related_docs: list[Entity | Document],
    dependencies: list[Relationship],
) -> SplitRecommendation:
    """Decide whether an entity deserves its own module ontology.

    An entity should be split out when it meets >= 2 of 5 criteria
    defined in REF-ontology-methodology.md:
      1. 3+ documents reference it
      2. Has independent dependency chains (input/output relationships)
      3. Has different audience groups (Who tags differ from other docs)
      4. Has independent goals or open decisions
      5. Complexity exceeds a paragraph (summary > 5 lines / 300 chars)
    """
    reasons: list[str] = []
    score = 0

    # Criterion 1: 3+ related documents
    if len(related_docs) >= 3:
        score += 1
        reasons.append(
            f"Has {len(related_docs)} related documents (threshold: 3)"
        )

    # Criterion 2: independent dependency chain
    # Entity participates in depends_on / blocks / serves relationships
    dep_types = {RelationshipType.DEPENDS_ON, RelationshipType.BLOCKS, RelationshipType.SERVES}
    dep_rels = [r for r in dependencies if r.type in dep_types]
    if dep_rels:
        score += 1
        reasons.append(
            f"Has {len(dep_rels)} dependency-chain relationship(s)"
        )

    # Criterion 3: different audience groups
    # Collect all unique Who values across related docs; if > 1 distinct
    # audience set, the entity serves multiple reader groups.
    all_who: set[str] = set()
    for doc in related_docs:
        who_val = doc.tags.who
        # Handle both list[str] and str formats
        if isinstance(who_val, str):
            who_val = [who_val] if who_val else []
        for w in who_val:
            all_who.add(w.strip().lower())
    if len(all_who) > 1:
        score += 1
        reasons.append(
            f"Has {len(all_who)} distinct audience groups: {', '.join(sorted(all_who))}"
        )

    # Criterion 4: independent goal or open decisions
    # Check if the entity itself is a goal, or if its details dict
    # contains open decisions / roadmap items.
    has_goal_nature = entity.type == EntityType.GOAL
    has_open_decisions = False
    if entity.details and isinstance(entity.details, dict):
        for key in ("decisions", "open_questions", "roadmap", "todos"):
            val = entity.details.get(key)
            if val and (isinstance(val, list) and len(val) > 0 or isinstance(val, str) and val.strip()):
                has_open_decisions = True
                break
    if has_goal_nature or has_open_decisions:
        score += 1
        if has_goal_nature:
            reasons.append("Entity is itself a goal with its own lifecycle")
        if has_open_decisions:
            reasons.append("Has open decisions or roadmap items in details")

    # Criterion 5: complexity exceeds a paragraph
    summary_lines = entity.summary.strip().count("\n") + 1
    summary_chars = len(entity.summary.strip())
    if summary_lines > 5 or summary_chars > 300:
        score += 1
        reasons.append(
            f"Summary complexity high ({summary_lines} lines, {summary_chars} chars)"
        )

    should_split = score >= 2
    return SplitRecommendation(
        should_split=should_split,
        reasons=reasons,
        score=score,
    )


# ──────────────────────────────────────────────
# 2. 4D Tag confidence (標籤信心度)
# ──────────────────────────────────────────────

def apply_tag_confidence(tags: Tags | DocumentTags) -> TagConfidence:
    """Classify tag dimensions by AI confidence level.

    From REF-ontology-methodology.md:
      - What / Who: AI can auto-confirm (factual dimensions)
      - Why / How: Must remain draft until human confirms (intent dimensions)
    """
    confirmed: list[str] = []
    draft: list[str] = []

    def _has_content(val: str | list[str]) -> bool:
        """Check if a tag value has meaningful content (works for str or list)."""
        if isinstance(val, list):
            return bool(val) and any(w.strip() for w in val)
        return bool(val) and bool(val.strip())

    # What: factual — high confidence
    if _has_content(tags.what):
        confirmed.append("what")
    else:
        draft.append("what")

    # Who: factual — high confidence
    if _has_content(tags.who):
        confirmed.append("who")
    else:
        draft.append("who")

    # Why: intent — always draft
    draft.append("why")

    # How: intent — always draft
    draft.append("how")

    return TagConfidence(
        confirmed_fields=confirmed,
        draft_fields=draft,
    )


# ──────────────────────────────────────────────
# 3. Staleness detection (過時推斷)
# ──────────────────────────────────────────────

_STALENESS_THRESHOLD = timedelta(days=30)  # "一個月沒動靜"
_ROLE_DISAPPEAR_THRESHOLD = timedelta(days=90)  # "三個月沒出現"


def detect_staleness(
    entities: list[Entity],
    documents: list[Entity | Document],
    relationships: list[Relationship],
    *,
    now: datetime | None = None,
) -> list[StalenessWarning]:
    """Detect staleness using cross-entity activity anomalies.

    Implements 4 patterns from REF-ontology-methodology.md:
      1. Feature updated but docs lagging
      2. Goal completed but not closed
      3. Dependency updated but dependant silent
      4. Role disappeared
    """
    def _to_aware(dt: datetime) -> datetime:
        return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)

    if now is None:
        now = datetime.now(timezone.utc)
    else:
        now = _to_aware(now)

    warnings: list[StalenessWarning] = []
    entity_map = {e.id: e for e in entities if e.id}
    docs_by_entity: dict[str, list[Entity | Document]] = {}
    for doc in documents:
        # Support both Document (linked_entity_ids) and Entity (parent_id)
        if isinstance(doc, Document):
            for eid in doc.linked_entity_ids:
                docs_by_entity.setdefault(eid, []).append(doc)
        elif hasattr(doc, "parent_id") and doc.parent_id:
            docs_by_entity.setdefault(doc.parent_id, []).append(doc)

    def _doc_title(d: Entity | Document) -> str:
        return d.title if isinstance(d, Document) else d.name

    def _doc_status(d: Entity | Document) -> str:
        return d.status

    def _doc_last_reviewed(d: Entity | Document) -> datetime:
        raw = d.last_reviewed_at or d.updated_at
        return _to_aware(raw)

    def _doc_who(d: Entity | Document) -> list[str]:
        if isinstance(d, Document):
            return d.tags.who
        who = d.tags.who
        if isinstance(who, str):
            return [who] if who else []
        return who

    # --- Pattern 1: Feature updated but docs lagging ---
    # If an entity was updated recently but its linked docs were not,
    # the documentation may be stale.
    for entity in entities:
        if not entity.id or entity.status != EntityStatus.ACTIVE:
            continue
        linked_docs = docs_by_entity.get(entity.id, [])
        for doc in linked_docs:
            if _doc_status(doc) == DocumentStatus.ARCHIVED:
                continue
            # Entity updated after doc was last touched
            doc_last = _doc_last_reviewed(doc)
            if _to_aware(entity.updated_at) > doc_last + _STALENESS_THRESHOLD:
                warnings.append(StalenessWarning(
                    pattern="feature_updated_docs_lagging",
                    description=(
                        f"Entity '{entity.name}' was updated on "
                        f"{entity.updated_at.date()}, but document "
                        f"'{_doc_title(doc)}' hasn't been reviewed since "
                        f"{doc_last.date()}"
                    ),
                    affected_entity_ids=[entity.id],
                    affected_document_ids=[doc.id] if doc.id else [],
                    suggested_action=f"Review document '{_doc_title(doc)}' for accuracy",
                ))

    # --- Pattern 2: Goal completed but not closed ---
    # All related entities of a goal are completed/paused but the goal
    # itself is still active.
    goal_entities = [e for e in entities if e.type == EntityType.GOAL and e.status == EntityStatus.ACTIVE and e.id]
    for goal in goal_entities:
        # Find entities that serve this goal
        serving_rels = [
            r for r in relationships
            if r.target_id == goal.id and r.type in (RelationshipType.SERVES, RelationshipType.PART_OF)
        ]
        if not serving_rels:
            continue
        serving_ids = {r.source_entity_id for r in serving_rels}
        serving_entities = [entity_map[sid] for sid in serving_ids if sid in entity_map]
        if not serving_entities:
            continue
        all_done = all(
            e.status in (EntityStatus.COMPLETED, EntityStatus.PAUSED)
            for e in serving_entities
        )
        if all_done:
            warnings.append(StalenessWarning(
                pattern="goal_completed_not_closed",
                description=(
                    f"Goal '{goal.name}' is still active, but all "
                    f"{len(serving_entities)} serving entities are "
                    f"completed or paused"
                ),
                affected_entity_ids=[goal.id] + [e.id for e in serving_entities if e.id],
                affected_document_ids=[],
                suggested_action=f"Consider closing goal '{goal.name}'",
            ))

    # --- Pattern 3: Dependency updated but dependant silent ---
    # A depends_on B, B was updated but A was not.
    for rel in relationships:
        if rel.type != RelationshipType.DEPENDS_ON:
            continue
        source = entity_map.get(rel.source_entity_id)  # A depends on B
        target = entity_map.get(rel.target_id)          # B is the dependency
        if not source or not target:
            continue
        if _to_aware(target.updated_at) > _to_aware(source.updated_at) + _STALENESS_THRESHOLD:
            warnings.append(StalenessWarning(
                pattern="dependency_updated_dependant_silent",
                description=(
                    f"'{source.name}' depends on '{target.name}', which was "
                    f"updated on {target.updated_at.date()}, but '{source.name}' "
                    f"hasn't been touched since {source.updated_at.date()}"
                ),
                affected_entity_ids=[
                    eid for eid in [source.id, target.id] if eid
                ],
                affected_document_ids=[],
                suggested_action=(
                    f"Check if '{source.name}' needs to sync with "
                    f"changes in '{target.name}'"
                ),
            ))

    # --- Pattern 4: Role disappeared ---
    # A role entity exists but no document mentions it in Who tags
    # within the last 90 days.
    role_entities = [
        e for e in entities
        if e.type == EntityType.ROLE and e.status == EntityStatus.ACTIVE and e.id
    ]
    for role in role_entities:
        role_name_lower = role.name.strip().lower()
        # Check if any current document references this role in Who
        found_recent = False
        for doc in documents:
            if _doc_status(doc) == DocumentStatus.ARCHIVED:
                continue
            doc_who_lower = {w.strip().lower() for w in _doc_who(doc)}
            if role_name_lower in doc_who_lower:
                doc_last = _doc_last_reviewed(doc)
                if now - doc_last < _ROLE_DISAPPEAR_THRESHOLD:
                    found_recent = True
                    break
        if not found_recent:
            warnings.append(StalenessWarning(
                pattern="role_disappeared",
                description=(
                    f"Role '{role.name}' exists in skeleton layer but no "
                    f"current document references it in the last 90 days"
                ),
                affected_entity_ids=[role.id] if role.id else [],
                affected_document_ids=[],
                suggested_action=(
                    f"Confirm whether role '{role.name}' is still active"
                ),
            ))

    return warnings


# ──────────────────────────────────────────────
# 4. Blindspot analysis (盲點分析)
# ──────────────────────────────────────────────

def analyze_blindspots(
    entities: list[Entity],
    documents: list[Entity | Document],
    relationships: list[Relationship],
) -> list[Blindspot]:
    """Infer blind spots by cross-referencing ontology layers.

    Implements 7 patterns from REF-ontology-methodology.md:
      1. Document placed in wrong location (What tag mismatches source path)
      2. Core feature lacks documentation (< 2 docs)
      3. Confirmed problem without schedule
      4. One-off docs ratio too high (archived > 2x core)
      5. Timeline gap (large update-time gaps between docs)
      6. Missing non-technical entry point
      7. Goal priority unclear
    """
    blindspots: list[Blindspot] = []
    entity_map = {e.id: e for e in entities if e.id}
    docs_by_entity: dict[str, list[Entity | Document]] = {}
    for doc in documents:
        if isinstance(doc, Document):
            for eid in doc.linked_entity_ids:
                docs_by_entity.setdefault(eid, []).append(doc)
        elif hasattr(doc, "parent_id") and doc.parent_id:
            docs_by_entity.setdefault(doc.parent_id, []).append(doc)

    def _d_title(d: Entity | Document) -> str:
        return d.title if isinstance(d, Document) else d.name

    def _d_status(d: Entity | Document) -> str:
        return d.status

    def _d_what(d: Entity | Document) -> list[str]:
        if isinstance(d, Document):
            return d.tags.what
        w = d.tags.what
        if isinstance(w, str):
            return [w] if w else []
        return w

    def _d_who(d: Entity | Document) -> list[str]:
        if isinstance(d, Document):
            return d.tags.who
        w = d.tags.who
        if isinstance(w, str):
            return [w] if w else []
        return w

    def _d_uri(d: Entity | Document) -> str:
        if isinstance(d, Document):
            return d.source.uri
        if d.sources:
            return d.sources[0].get("uri", "")
        return ""

    def _d_linked_ids(d: Entity | Document) -> list[str]:
        if isinstance(d, Document):
            return [eid for eid in d.linked_entity_ids if eid]
        return [d.parent_id] if d.parent_id else []

    # --- 1. Document placed in wrong location ---
    # If a doc's source URI path contains a category keyword that
    # conflicts with its What tags, flag it.
    _CATEGORY_KEYWORDS = {
        "marketing": {"marketing", "行銷", "campaign", "branding"},
        "engineering": {"engineering", "eng", "dev", "technical", "技術"},
        "design": {"design", "ui", "ux", "設計"},
        "sales": {"sales", "業務", "銷售"},
        "hr": {"hr", "human", "人資"},
        "finance": {"finance", "財務", "accounting"},
    }
    for doc in documents:
        if _d_status(doc) == DocumentStatus.ARCHIVED:
            continue
        uri_lower = _d_uri(doc).lower()
        if not uri_lower:
            continue
        doc_what_lower = {w.strip().lower() for w in _d_what(doc)}
        for category, keywords in _CATEGORY_KEYWORDS.items():
            # Check if the URI path suggests this category
            path_match = any(f"/{kw}/" in uri_lower or uri_lower.startswith(f"{kw}/") for kw in keywords)
            if not path_match:
                continue
            # Check if any What tag actually matches the category
            content_match = any(kw in wt for wt in doc_what_lower for kw in keywords)
            if content_match:
                continue
            # Mismatch: path says one thing, content says another
            blindspots.append(Blindspot(
                description=(
                    f"Document '{_d_title(doc)}' is in a {category} path "
                    f"({_d_uri(doc)}) but its What tags "
                    f"({', '.join(_d_what(doc))}) suggest different content"
                ),
                severity=Severity.YELLOW,
                related_entity_ids=_d_linked_ids(doc),
                suggested_action=(
                    f"Review whether '{_d_title(doc)}' belongs in its current location "
                    f"or should be moved"
                ),
            ))

    # --- 2. Core feature lacks documentation ---
    # An entity marked as a product/module in active status with < 2 docs.
    core_types = {EntityType.PRODUCT, EntityType.MODULE}
    for entity in entities:
        if entity.type not in core_types or entity.status != EntityStatus.ACTIVE:
            continue
        if not entity.id:
            continue
        linked = docs_by_entity.get(entity.id, [])
        current_docs = [d for d in linked if _d_status(d) != DocumentStatus.ARCHIVED]
        if len(current_docs) < 2:
            blindspots.append(Blindspot(
                description=(
                    f"Core entity '{entity.name}' ({entity.type}) has only "
                    f"{len(current_docs)} current document(s), below the "
                    f"minimum of 2 for adequate coverage"
                ),
                severity=Severity.RED,
                related_entity_ids=[entity.id],
                suggested_action=(
                    f"Create additional documentation for '{entity.name}' "
                    f"to ensure knowledge is captured"
                ),
            ))

    # --- 3. Confirmed problem without schedule ---
    # Documents whose How tag contains problem indicators but no schedule.
    _PROBLEM_INDICATORS = {"待修復", "已確認問題", "bug", "issue", "fix needed", "known issue", "todo"}
    _SCHEDULE_INDICATORS = {"排程", "scheduled", "planned", "sprint", "milestone", "deadline", "時程"}
    for doc in documents:
        if _d_status(doc) == DocumentStatus.ARCHIVED:
            continue
        how_lower = _safe_str(doc.tags.how if hasattr(doc.tags, 'how') else "").lower()
        has_problem = any(ind in how_lower for ind in _PROBLEM_INDICATORS)
        has_schedule = any(ind in how_lower for ind in _SCHEDULE_INDICATORS)
        if has_problem and not has_schedule:
            blindspots.append(Blindspot(
                description=(
                    f"Document '{_d_title(doc)}' mentions confirmed problems "
                    f"but has no scheduled resolution"
                ),
                severity=Severity.RED,
                related_entity_ids=_d_linked_ids(doc),
                suggested_action=(
                    f"Add timeline or priority for resolving issues in "
                    f"'{_d_title(doc)}'"
                ),
            ))

    # --- 4. One-off docs ratio too high ---
    # If archived/draft docs > 2x current docs, knowledge noise is high.
    current_docs = [d for d in documents if _d_status(d) in (DocumentStatus.CURRENT,)]
    archivable_docs = [d for d in documents if _d_status(d) in (DocumentStatus.ARCHIVED, DocumentStatus.STALE)]
    if current_docs and len(archivable_docs) > 2 * len(current_docs):
        blindspots.append(Blindspot(
            description=(
                f"One-off document ratio is high: {len(archivable_docs)} "
                f"archived/stale vs {len(current_docs)} current documents. "
                f"Knowledge noise may be elevated"
            ),
            severity=Severity.YELLOW,
            related_entity_ids=[],
            suggested_action=(
                "Review archived documents and clean up those that no "
                "longer provide value"
            ),
        ))

    # --- 5. Timeline gap ---
    # If there's a gap of > 6 months between consecutive document updates,
    # intermediate evolution may be unrecorded.
    if len(documents) >= 2:
        sorted_docs = sorted(
            [d for d in documents if _d_status(d) != DocumentStatus.ARCHIVED],
            key=lambda d: d.updated_at,
        )
        six_months = timedelta(days=180)
        for i in range(1, len(sorted_docs)):
            gap = sorted_docs[i].updated_at - sorted_docs[i - 1].updated_at
            if gap > six_months:
                blindspots.append(Blindspot(
                    description=(
                        f"Timeline gap of {gap.days} days between "
                        f"'{_d_title(sorted_docs[i-1])}' "
                        f"({sorted_docs[i-1].updated_at.date()}) and "
                        f"'{_d_title(sorted_docs[i])}' "
                        f"({sorted_docs[i].updated_at.date()}). "
                        f"Intermediate changes may be unrecorded"
                    ),
                    severity=Severity.YELLOW,
                    related_entity_ids=[],
                    suggested_action=(
                        "Investigate whether important changes occurred "
                        "during this gap and document them"
                    ),
                ))

    # --- 6. Missing non-technical entry point ---
    # If a non-technical role exists in skeleton layer but no document
    # has that role in its Who tags.
    _NON_TECH_ROLES = {"行銷", "marketing", "業務", "sales", "設計", "design", "hr", "人資", "老闆", "ceo", "founder", "pm", "product manager"}
    role_entities = [e for e in entities if e.type == EntityType.ROLE and e.id]
    for role in role_entities:
        role_lower = role.name.strip().lower()
        if not any(nt in role_lower for nt in _NON_TECH_ROLES):
            continue
        # Check if any non-archived doc targets this role
        has_doc = False
        for doc in documents:
            if _d_status(doc) == DocumentStatus.ARCHIVED:
                continue
            if any(role_lower in w.strip().lower() for w in _d_who(doc)):
                has_doc = True
                break
        if not has_doc:
            blindspots.append(Blindspot(
                description=(
                    f"Non-technical role '{role.name}' exists in skeleton "
                    f"layer but no current document targets this audience"
                ),
                severity=Severity.RED,
                related_entity_ids=[role.id] if role.id else [],
                suggested_action=(
                    f"Create or tag documents accessible to '{role.name}'"
                ),
            ))

    # --- 7. Goal priority unclear ---
    # Multiple active goals without explicit priority ordering.
    active_goals = [
        e for e in entities
        if e.type == EntityType.GOAL
        and e.status == EntityStatus.ACTIVE
        and e.id
    ]
    if len(active_goals) > 1:
        has_priority = False
        for g in active_goals:
            if g.details and isinstance(g.details, dict):
                p = g.details.get("priority")
                if p is not None:
                    has_priority = True
                    break
        if not has_priority:
            blindspots.append(Blindspot(
                description=(
                    f"There are {len(active_goals)} active goals but none "
                    f"have explicit priority ordering"
                ),
                severity=Severity.YELLOW,
                related_entity_ids=[g.id for g in active_goals if g.id],
                suggested_action=(
                    "Define priority ranking for active goals so teams "
                    "know what to focus on"
                ),
            ))

    # --- 8. Active L2 missing concrete impacts ---
    # Hard governance defect: active L2 without impacts should enter repair flow.
    missing_impacts_modules = _find_active_l2_without_concrete_impacts(entities, relationships)
    for mod in missing_impacts_modules:
        blindspots.append(Blindspot(
            description=(
                f"Active L2 '{mod.name}' has no concrete impacts path "
                f"(A 改了什麼→B 的什麼要跟著看)."
            ),
            severity=Severity.RED,
            related_entity_ids=[mod.id] if mod.id else [],
            suggested_action=(
                "補 impacts；若補不出則降級為 L3；或重新切粒度為可獨立改變的 L2"
            ),
        ))

    return blindspots


# ──────────────────────────────────────────────
# 5. Quality check (品質檢查)
# ──────────────────────────────────────────────

# Technical terms that should not appear in L2 (module) summaries.
# L2 summaries represent company-consensus concepts, not technical implementation.
_L2_TECH_TERMS: list[str] = [
    "LLM", "API", "SDK", "Firestore", "Firebase", "schema", "prompt",
    "endpoint", "backend", "frontend", "framework", "middleware",
    "microservice", "REST", "GraphQL", "SQL", "NoSQL", "CRUD", "ORM",
    "JWT", "OAuth", "webhook", "CI/CD", "Docker", "Kubernetes",
]

# Compiled regex for sentence-ending punctuation (Chinese + Latin).
_SENTENCE_END_RE = re.compile(r"[。！？.!?]")

# Governance review period: all confirmed L2 modules must be reviewed at least quarterly.
_GOVERNANCE_REVIEW_PERIOD = timedelta(days=90)


def find_tech_terms_in_summary(summary: str) -> list[str]:
    """Find technical terms that should not appear in L2 summaries.

    L2 summaries represent company-consensus concepts and must be readable
    by any role, not just engineers.
    """
    return [
        term for term in _L2_TECH_TERMS
        if re.search(r"\b" + re.escape(term) + r"\b", summary or "", re.IGNORECASE)
    ]


def _is_concrete_impacts_description(description: str) -> bool:
    """Return True when impacts description encodes a concrete change path."""
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


def _find_active_l2_without_concrete_impacts(
    entities: list[Entity],
    relationships: list[Relationship],
) -> list[Entity]:
    """Find active L2 entities that have no concrete impacts relationship."""
    active_modules = [
        e for e in entities
        if e.type == EntityType.MODULE and e.status == EntityStatus.ACTIVE and e.id
    ]
    impact_entity_ids = set()
    for rel in relationships:
        if rel.type != RelationshipType.IMPACTS:
            continue
        if not _is_concrete_impacts_description(rel.description):
            continue
        impact_entity_ids.add(rel.source_entity_id)
        impact_entity_ids.add(rel.target_id)

    return [m for m in active_modules if m.id not in impact_entity_ids]


# ──────────────────────────────────────────────
# Task 4: impacts 目標有效性檢查
# ──────────────────────────────────────────────

_INVALID_TARGET_STATUSES = frozenset({"stale", "draft", "completed"})

_IMPACTS_SUGGESTED_ACTIONS: dict[str, str] = {
    "target_missing": "目標 entity 已不存在，建議移除此 impacts 關聯",
    "target_stale": "目標 entity 已標記為 stale，建議確認是否有新的替代 entity，或更新 impacts 目標",
    "target_draft": "目標 entity 仍為 draft，建議先 confirm 目標 entity，或暫緩此 impacts",
}


def _broken_impact_reason(target_status: str | None) -> str:
    """Map target status to structured reason enum."""
    if target_status is None:
        return "target_missing"
    if target_status == "stale":
        return "target_stale"
    return "target_draft"


def check_impacts_target_validity(
    entities: list[Entity],
    relationships: list[Relationship],
) -> list[dict]:
    """Check if impacts targets are still valid (exist and active).

    For each active L2 module that has outgoing concrete impacts, verify that
    every target entity still exists and is in an acceptable status.

    Returns a list of dicts describing modules with broken impacts:
    {
        "source_entity_id": str,
        "source_entity_name": str,
        "broken_impacts": [
            {
                "relationship_id": str | None,
                "impacts_description": str,       # concrete impacts description text
                "target_entity_id": str,
                "target_entity_name": str | None,  # None if not found
                "reason": "target_missing" | "target_stale" | "target_draft",
                "suggested_action": str,
            }
        ],
        "suggested_actions": [...],
    }
    """
    entity_map = {e.id: e for e in entities if e.id}
    active_modules = {
        e.id: e
        for e in entities
        if e.type == EntityType.MODULE and e.status == EntityStatus.ACTIVE and e.id
    }

    broken: list[dict] = []
    for rel in relationships:
        if rel.type != RelationshipType.IMPACTS:
            continue
        if not _is_concrete_impacts_description(rel.description):
            continue
        if rel.source_entity_id not in active_modules:
            continue

        target = entity_map.get(rel.target_id)
        if target is None:
            reason = "target_missing"
            target_name = None
        elif target.status in _INVALID_TARGET_STATUSES:
            reason = _broken_impact_reason(target.status)
            target_name = target.name
        else:
            continue  # target is valid

        # Find or create entry for this source module
        entry = next(
            (b for b in broken if b["source_entity_id"] == rel.source_entity_id),
            None,
        )
        if entry is None:
            source = active_modules[rel.source_entity_id]
            entry = {
                "source_entity_id": rel.source_entity_id,
                "source_entity_name": source.name,
                "broken_impacts": [],
                "suggested_actions": ["標記 stale", "更新 impacts", "移除無效關聯"],
            }
            broken.append(entry)
        entry["broken_impacts"].append({
            "relationship_id": rel.id,
            "impacts_description": rel.description or "",
            "target_entity_id": rel.target_id,
            "target_entity_name": target_name,
            "reason": reason,
            "suggested_action": _IMPACTS_SUGGESTED_ACTIONS.get(reason, ""),
        })

    return broken


# ──────────────────────────────────────────────
# Task 5: stale L2 downstream 影響清單（entity 部分）
# ──────────────────────────────────────────────

def find_stale_l2_downstream_entities(
    entities: list[Entity],
) -> list[dict]:
    """Find L3 entities under stale L2 modules (via parent_id).

    Task queries are intentionally excluded here; callers in the interface
    layer can enrich the results with open-task data.

    Returns a list of dicts:
    {
        "stale_module_id": str,
        "stale_module_name": str,
        "affected_l3_entities": [{"id": str, "name": str, "type": str}],
    }
    """
    stale_modules = [
        e for e in entities
        if e.type == EntityType.MODULE and e.status == EntityStatus.STALE and e.id
    ]
    if not stale_modules:
        return []

    results: list[dict] = []
    for mod in stale_modules:
        children = [
            {"id": e.id, "name": e.name, "type": e.type}
            for e in entities
            if e.parent_id == mod.id and e.id
        ]
        results.append({
            "stale_module_id": mod.id,
            "stale_module_name": mod.name,
            "affected_l3_entities": children,
        })
    return results


# ──────────────────────────────────────────────
# Task 6: 反向 impacts 檢查
# ──────────────────────────────────────────────

def check_reverse_impacts(
    entities: list[Entity],
    relationships: list[Relationship],
    *,
    now: datetime | None = None,
    staleness_threshold_days: int | None = None,
) -> list[dict]:
    """Check if entities targeted by impacts have been recently modified.

    When B is modified and A impacts B, A needs to review its impacts path.

    Returns a list of dicts:
    {
        "modified_entity_id": str,
        "modified_entity_name": str,
        "modified_at": str,  # ISO datetime
        "impacted_by": [
            {
                "source_entity_id": str,
                "source_entity_name": str,
                "impacts_description": str,
                "needs_review_reason": str,
            }
        ],
    }
    """
    def _to_aware(dt: datetime) -> datetime:
        return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)

    if now is None:
        now = datetime.now(timezone.utc)
    else:
        now = _to_aware(now)
    threshold = (
        timedelta(days=staleness_threshold_days)
        if staleness_threshold_days is not None
        else _STALENESS_THRESHOLD
    )
    cutoff = now - threshold

    entity_map = {e.id: e for e in entities if e.id}

    # Build reverse index: target_id → list of (relationship, source entity)
    reverse_index: dict[str, list[tuple[Relationship, Entity]]] = {}
    for rel in relationships:
        if rel.type != RelationshipType.IMPACTS:
            continue
        if not _is_concrete_impacts_description(rel.description):
            continue
        source = entity_map.get(rel.source_entity_id)
        if source is None:
            continue
        reverse_index.setdefault(rel.target_id, []).append((rel, source))

    results: list[dict] = []
    for entity in entities:
        if not entity.id:
            continue
        if _to_aware(entity.updated_at) < cutoff:
            continue
        inbound = reverse_index.get(entity.id, [])
        if not inbound:
            continue
        results.append({
            "modified_entity_id": entity.id,
            "modified_entity_name": entity.name,
            "modified_at": entity.updated_at.isoformat(),
            "impacted_by": [
                {
                    "source_entity_id": src.id,
                    "source_entity_name": src.name,
                    "impacts_description": rel.description,
                    "needs_review_reason": (
                        "impacts 目標已被修改，源頭 L2 應 review impacts 路徑是否仍正確"
                    ),
                }
                for rel, src in inbound
            ],
        })
    return results


# ──────────────────────────────────────────────
# Task 7: governance review overdue check
# ──────────────────────────────────────────────

def check_governance_review_overdue(
    entities: list[Entity],
    review_period: timedelta = _GOVERNANCE_REVIEW_PERIOD,
    now: datetime | None = None,
) -> list[dict]:
    """Find active (confirmed) L2 modules overdue for governance review.

    All confirmed L2 modules should be reviewed at least every quarter
    (90 days) to verify that their impacts are still valid.

    Returns a list of dicts:
    {
        "entity_id": str,
        "entity_name": str,
        "last_reviewed_at": str | None,  # ISO datetime or None (never reviewed)
        "days_overdue": int,
        "suggested_action": str,
    }
    """
    if now is None:
        now = datetime.now(timezone.utc)

    def _ensure_utc(dt: datetime) -> datetime:
        return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)

    overdue: list[dict] = []
    active_modules = [
        e for e in entities
        if e.type == EntityType.MODULE and e.status == EntityStatus.ACTIVE and e.id
    ]
    for mod in active_modules:
        if mod.last_reviewed_at is None:
            # Never reviewed: use created_at as baseline (treat None created_at as overdue)
            baseline = _ensure_utc(mod.created_at) if mod.created_at else now - review_period
            elapsed = now - baseline
            if elapsed > review_period:
                overdue.append({
                    "entity_id": mod.id,
                    "entity_name": mod.name,
                    "last_reviewed_at": None,
                    "days_overdue": (elapsed - review_period).days,
                    "suggested_action": "執行 governance review，檢查 impacts 是否仍有效",
                })
        else:
            last = _ensure_utc(mod.last_reviewed_at)
            elapsed = now - last
            if elapsed > review_period:
                overdue.append({
                    "entity_id": mod.id,
                    "entity_name": mod.name,
                    "last_reviewed_at": last.isoformat(),
                    "days_overdue": (elapsed - review_period).days,
                    "suggested_action": "執行 governance review，檢查 impacts 是否仍有效",
                })
    return overdue


def run_quality_check(
    entities: list[Entity],
    documents: list[Entity | Document],
    protocols: list[Protocol],
    blindspots: list[Blindspot],
    relationships: list[Relationship],
    tasks: list | None = None,
    entries_by_entity: dict[str, int] | None = None,
) -> QualityReport:
    """Run the 21-item quality checklist from REF-ontology-methodology.md.

    Returns a QualityReport with weighted score (0-100), passed, failed, and warnings.
    Items 1-9 cover general ontology quality; items 10-16 cover L2 (module) quality;
    items 17-21 cover duplicate detection, entry sparsity, and L2 count balance.

    Args:
        entities: All non-document skeleton-layer entities.
        documents: Neural-layer documents (Document or document-type Entity).
        protocols: Protocol objects for each entity.
        blindspots: Previously inferred blindspot objects.
        relationships: Relationship edges between entities.
        tasks: Optional list of Task objects for duplicate task detection.
        entries_by_entity: Optional mapping of entity_id -> entry count for sparsity check.
    """
    items: list[QualityCheckItem] = []
    entity_map = {e.id: e for e in entities if e.id}
    docs_by_entity: dict[str, list[Entity | Document]] = {}
    for doc in documents:
        if isinstance(doc, Document):
            for eid in doc.linked_entity_ids:
                docs_by_entity.setdefault(eid, []).append(doc)
        elif hasattr(doc, "parent_id") and doc.parent_id:
            docs_by_entity.setdefault(doc.parent_id, []).append(doc)

    def _qc_title(d: Entity | Document) -> str:
        return d.title if isinstance(d, Document) else d.name

    def _qc_status(d: Entity | Document) -> str:
        return d.status

    def _qc_linked(d: Entity | Document) -> list[str]:
        if isinstance(d, Document):
            return d.linked_entity_ids
        return [d.parent_id] if d.parent_id else []

    def _qc_who(d: Entity | Document) -> list[str]:
        if isinstance(d, Document):
            return d.tags.who
        w = d.tags.who
        if isinstance(w, str):
            return [w] if w else []
        return w

    # --- 1. Can the boss read the panorama in 2 minutes? ---
    # Proxy: total summary length of all entities should be manageable.
    # index.md ~= concatenation of entity summaries. 2 minutes ≈ 500 words ≈ 2500 chars.
    total_summary = sum(len(e.summary) for e in entities)
    check1_ok = total_summary <= 2500
    items.append(QualityCheckItem(
        name="panorama_readability",
        passed=check1_ok,
        detail=(
            f"Total entity summary length: {total_summary} chars "
            f"({'within' if check1_ok else 'exceeds'} 2500-char / 2-min target)"
        ),
        weight=1,
    ))

    # --- 2. Are dependency relationships complete? ---
    # Every active product/module should have at least one relationship.
    core_entities = [
        e for e in entities
        if e.type in (EntityType.PRODUCT, EntityType.MODULE)
        and e.status == EntityStatus.ACTIVE
        and e.id
    ]
    rel_entity_ids = set()
    for r in relationships:
        rel_entity_ids.add(r.source_entity_id)
        rel_entity_ids.add(r.target_id)
    orphans = [e for e in core_entities if e.id not in rel_entity_ids]
    check2_ok = len(orphans) == 0
    items.append(QualityCheckItem(
        name="dependency_completeness",
        passed=check2_ok,
        detail=(
            f"{len(orphans)} active product/module(s) without any relationships"
            + (f": {', '.join(e.name for e in orphans)}" if orphans else "")
        ),
        weight=3,
    ))

    # --- 3. Are all unconfirmed fields marked? ---
    # Every entity/doc/protocol with confirmed_by_user=False should exist.
    # This check passes if the system properly tracks confirmation status
    # (i.e., not everything is blindly set to confirmed).
    total_items = len(entities) + len(documents) + len(protocols)
    unconfirmed_count = (
        sum(1 for e in entities if not e.confirmed_by_user)
        + sum(1 for d in documents if not d.confirmed_by_user)
        + sum(1 for p in protocols if not p.confirmed_by_user)
    )
    # It's a warning if everything is confirmed (suspicious) or nothing is.
    check3_ok = True
    check3_warning = False
    if total_items > 0 and unconfirmed_count == 0:
        check3_warning = True
        check3_ok = True  # technically passes but suspicious
    items.append(QualityCheckItem(
        name="unconfirmed_fields_marked",
        passed=check3_ok,
        detail=(
            f"{unconfirmed_count}/{total_items} items pending confirmation"
            + (" (warning: all confirmed — verify this is intentional)" if check3_warning else "")
        ),
        weight=1,
    ))

    # --- 4. Are blindspots inferred from cross-referencing? ---
    # Passes if blindspots exist when there are entities+docs to analyze.
    has_material = len(entities) > 0 and len(documents) > 0
    check4_ok = len(blindspots) > 0 if has_material else True
    items.append(QualityCheckItem(
        name="blindspot_analysis_present",
        passed=check4_ok,
        detail=(
            f"{len(blindspots)} blindspot(s) identified"
            + (" (none found despite having material to analyze)" if not check4_ok else "")
        ),
        weight=1,
    ))

    # --- 5. Every document has a linked module? ---
    unlinked = [d for d in documents if not _qc_linked(d) and _qc_status(d) != DocumentStatus.ARCHIVED]
    check5_ok = len(unlinked) == 0
    items.append(QualityCheckItem(
        name="documents_linked",
        passed=check5_ok,
        detail=(
            f"{len(unlinked)} non-archived document(s) without linked entities"
            + (f": {', '.join(_qc_title(d) for d in unlinked[:5])}" if unlinked else "")
        ),
        weight=2,
    ))

    # --- 6. Archive suggestions have rationale? ---
    # Archived docs should have a summary explaining why.
    archived = [d for d in documents if _qc_status(d) == DocumentStatus.ARCHIVED]
    no_rationale = [d for d in archived if not d.summary.strip()]
    check6_ok = len(no_rationale) == 0
    items.append(QualityCheckItem(
        name="archive_rationale",
        passed=check6_ok,
        detail=(
            f"{len(no_rationale)}/{len(archived)} archived document(s) "
            f"without rationale in summary"
        ),
        weight=1,
    ))

    # --- 7. Goals have explicit priority? ---
    active_goals = [
        e for e in entities
        if e.type == EntityType.GOAL and e.status == EntityStatus.ACTIVE
    ]
    goals_with_priority = [
        g for g in active_goals
        if g.details and isinstance(g.details, dict) and g.details.get("priority") is not None
    ]
    check7_ok = len(goals_with_priority) == len(active_goals) or len(active_goals) <= 1
    items.append(QualityCheckItem(
        name="goal_priority",
        passed=check7_ok,
        detail=(
            f"{len(goals_with_priority)}/{len(active_goals)} active goals "
            f"have explicit priority"
        ),
        weight=1,
    ))

    # --- 8. Role in skeleton but no docs in neural layer? ---
    roles = [e for e in entities if e.type == EntityType.ROLE and e.id]
    roles_without_docs = []
    for role in roles:
        role_lower = role.name.strip().lower()
        has_doc = any(
            role_lower in w.strip().lower()
            for d in documents if _qc_status(d) != DocumentStatus.ARCHIVED
            for w in _qc_who(d)
        )
        if not has_doc:
            roles_without_docs.append(role)
    check8_ok = len(roles_without_docs) == 0
    items.append(QualityCheckItem(
        name="role_document_coverage",
        passed=check8_ok,
        detail=(
            f"{len(roles_without_docs)} role(s) without neural-layer documents"
            + (f": {', '.join(r.name for r in roles_without_docs)}" if roles_without_docs else "")
        ),
        weight=1,
    ))

    # --- 9. Split granularity reasonable (3-10 docs per module)? ---
    modules = [
        e for e in entities
        if e.type == EntityType.MODULE and e.status == EntityStatus.ACTIVE and e.id
    ]
    bad_granularity = []
    for mod in modules:
        linked = docs_by_entity.get(mod.id, [])
        current = [d for d in linked if _qc_status(d) != DocumentStatus.ARCHIVED]
        count = len(current)
        if count < 3 or count > 10:
            bad_granularity.append((mod, count))
    check9_ok = len(bad_granularity) == 0
    items.append(QualityCheckItem(
        name="split_granularity",
        passed=check9_ok,
        detail=(
            f"{len(bad_granularity)} module(s) outside 3-10 doc range"
            + (
                ": " + ", ".join(f"'{m.name}' ({c} docs)" for m, c in bad_granularity)
                if bad_granularity else ""
            )
        ),
        weight=1,
    ))

    # --- 10. L2 Summary readability (no technical jargon)? ---
    # L2 (module) entities represent company-consensus concepts;
    # their summaries must be readable by any role, not just engineers.
    module_entities = [e for e in entities if e.type == EntityType.MODULE]
    check10_ok = True
    check10_detail_parts: list[str] = []
    for mod in module_entities:
        found_terms = [
            term for term in _L2_TECH_TERMS
            if re.search(r"\b" + re.escape(term) + r"\b", mod.summary, re.IGNORECASE)
        ]
        if found_terms:
            check10_ok = False
            check10_detail_parts.append(
                f"L2 entity '{mod.name}' 的 summary 包含技術術語："
                f"{', '.join(found_terms)}。"
                f"L2 summary 應使用任何角色都聽得懂的語言。"
            )
    items.append(QualityCheckItem(
        name="l2_summary_readability",
        passed=check10_ok,
        detail=(
            " | ".join(check10_detail_parts)
            if check10_detail_parts
            else f"所有 {len(module_entities)} 個 L2 entity 的 summary 均無技術術語"
        ),
        weight=2,
    ))

    # --- 11. L2 Summary conciseness (≤ 5 sentences)? ---
    # L2 summaries should be concise; more than 5 sentences is a warning.
    check11_warning_parts: list[str] = []
    for mod in module_entities:
        sentence_count = len(_SENTENCE_END_RE.findall(mod.summary))
        if sentence_count > 5:
            check11_warning_parts.append(
                f"'{mod.name}' ({sentence_count} 句)"
            )
    # This is always "passed" (warnings don't affect score)
    items.append(QualityCheckItem(
        name="l2_summary_conciseness",
        passed=True,
        detail=(
            f"L2 summary 過長（>5句）：{', '.join(check11_warning_parts)}"
            if check11_warning_parts
            else f"所有 {len(module_entities)} 個 L2 entity 的 summary 均在 5 句以內"
        ),
        weight=1,
    ))

    # --- 12. L2 impacts hard rule (every active L2 must have concrete impacts) ---
    # L2 is only valid when it carries at least one concrete change-propagation path.
    # Any active L2 without impacts is a governance defect.
    modules_without_rels = _find_active_l2_without_concrete_impacts(entities, relationships)
    total_active_modules = len(
        [
            e for e in entities
            if e.type == EntityType.MODULE and e.status == EntityStatus.ACTIVE and e.id
        ]
    )
    n_without = len(modules_without_rels)
    check12_ok = n_without == 0
    missing_names = ", ".join(m.name for m in modules_without_rels[:8])
    if n_without > 8:
        missing_names += f" ... (+{n_without - 8})"
    items.append(QualityCheckItem(
        name="l2_impacts_coverage",
        passed=check12_ok,
        detail=(
            f"{n_without}/{total_active_modules} 個 active L2 entity 缺少具體 impacts：{missing_names}。"
            f"治理修補路徑：1) 補 impacts（A 改了什麼→B 的什麼要跟著看）"
            f" 2) 降級為 L3 3) 重新切粒度。"
            if not check12_ok
            else f"所有 {total_active_modules} 個 active L2 entity 皆具備至少 1 條具體 impacts"
        ),
        weight=3,
    ))

    # --- 13. L2 impacts targets still valid? ---
    # Check that all concrete impacts relationships point to existing, active entities.
    broken_impacts_report = check_impacts_target_validity(entities, relationships)
    check13_ok = len(broken_impacts_report) == 0
    broken_module_names = ", ".join(b["source_entity_name"] for b in broken_impacts_report[:5])
    if len(broken_impacts_report) > 5:
        broken_module_names += f" ... (+{len(broken_impacts_report) - 5})"
    items.append(QualityCheckItem(
        name="l2_impacts_target_validity",
        passed=check13_ok,
        detail=(
            f"{len(broken_impacts_report)} 個 L2 entity 的 impacts 目標無效或不存在："
            f"{broken_module_names}。"
            f"治理修補路徑：標記 stale、更新 impacts、或移除無效關聯。"
            if not check13_ok
            else "所有 L2 entity 的 impacts 目標均有效"
        ),
        weight=3,
    ))

    # --- 14. L2 governance review overdue? ---
    # All confirmed L2 modules must be reviewed at least quarterly.
    now = datetime.now(timezone.utc)
    overdue_modules = check_governance_review_overdue(entities, now=now)
    # Treat as warning (always passes) — overdue is informational, not a hard failure.
    # Use len check for detail message
    items.append(QualityCheckItem(
        name="l2_governance_review_overdue",
        passed=True,  # warning-only; does not reduce score
        detail=(
            f"{len(overdue_modules)} 個 active L2 entity 逾期未做 governance review："
            + ", ".join(m["entity_name"] for m in overdue_modules[:5])
            + (f" ... (+{len(overdue_modules) - 5})" if len(overdue_modules) > 5 else "")
            if overdue_modules
            else "所有 active L2 entity 均在 governance review 期限內（90 天）"
        ),
        weight=2,
    ))

    # --- 15. L2 three-question record completeness ---
    # All confirmed L2 (active status) should have layer_decision with all three questions True
    confirmed_modules = [
        e for e in entities
        if e.type == EntityType.MODULE and e.status == EntityStatus.ACTIVE
    ]
    modules_missing_3q: list[tuple[Entity, str]] = []
    for mod in confirmed_modules:
        ld = (
            mod.details.get("layer_decision")
            if mod.details and isinstance(mod.details, dict)
            else None
        )
        if ld is None:
            modules_missing_3q.append((mod, "missing"))
        elif not (ld.get("q1_persistent") and ld.get("q2_cross_role") and ld.get("q3_company_consensus")):
            modules_missing_3q.append((mod, "incomplete"))

    check15_ok = len(modules_missing_3q) == 0
    items.append(QualityCheckItem(
        name="l2_three_question_record",
        passed=check15_ok,
        detail=(
            f"{len(modules_missing_3q)} 個 active L2 entity 缺少完整三問紀錄："
            + ", ".join(f"'{m.name}' ({reason})" for m, reason in modules_missing_3q[:5])
            + (f" ... (+{len(modules_missing_3q) - 5})" if len(modules_missing_3q) > 5 else "")
            if modules_missing_3q
            else f"所有 {len(confirmed_modules)} 個 active L2 entity 均有完整三問紀錄"
        ),
        weight=3,
    ))

    # --- 16. L2 consolidation mode tracking ---
    # L2 entities produced without global consolidation mode should be flagged.
    modules_without_global: list[tuple[Entity, str]] = []
    for mod in module_entities:
        cm = (
            mod.details.get("consolidation_mode")
            if mod.details and isinstance(mod.details, dict)
            else None
        )
        if cm is None:
            modules_without_global.append((mod, "missing"))
        elif cm == "incremental":
            modules_without_global.append((mod, "incremental"))

    items.append(QualityCheckItem(
        name="l2_consolidation_mode",
        passed=True,  # warning-only
        detail=(
            f"{len(modules_without_global)} 個 L2 entity 缺少全局統合模式標記或為 incremental 模式："
            + ", ".join(f"'{m.name}' ({reason})" for m, reason in modules_without_global[:5])
            + (f" ... (+{len(modules_without_global) - 5})" if len(modules_without_global) > 5 else "")
            + "。建議以全局模式重新 capture。"
            if modules_without_global
            else f"所有 {len(module_entities)} 個 L2 entity 均標記為 global 統合模式"
        ),
        weight=1,
    ))

    # --- 17. Duplicate L2 detection ---
    # Find active/draft module pairs with name+summary Jaccard similarity > 0.6.
    candidate_modules = [
        e for e in entities
        if e.type == EntityType.MODULE and e.status in (EntityStatus.ACTIVE, EntityStatus.DRAFT) and e.id
    ]
    similar_l2_pairs: list[tuple[Entity, Entity, float]] = []
    for i in range(len(candidate_modules)):
        for j in range(i + 1, len(candidate_modules)):
            m_a = candidate_modules[i]
            m_b = candidate_modules[j]
            text_a = f"{m_a.name} {m_a.summary}"
            text_b = f"{m_b.name} {m_b.summary}"
            sim = _jaccard_similarity(text_a, text_b)
            if sim > 0.6:
                similar_l2_pairs.append((m_a, m_b, sim))
    check17_ok = len(similar_l2_pairs) == 0
    items.append(QualityCheckItem(
        name="duplicate_l2_detection",
        passed=check17_ok,
        detail=(
            f"{len(similar_l2_pairs)} 組 L2 模組名稱/摘要高度相似（Jaccard > 0.6）："
            + "; ".join(
                f"'{a.name}' ↔ '{b.name}' ({sim:.2f})"
                for a, b, sim in similar_l2_pairs[:5]
            )
            + (f" ... (+{len(similar_l2_pairs) - 5})" if len(similar_l2_pairs) > 5 else "")
            if similar_l2_pairs
            else f"所有 {len(candidate_modules)} 個 active/draft L2 模組均無重複"
        ),
        weight=2,
    ))

    # --- 18. Duplicate document detection ---
    # Find non-archived documents sharing the same source URI.
    uri_to_docs: dict[str, list] = {}
    for doc in documents:
        if _qc_status(doc) == DocumentStatus.ARCHIVED:
            continue
        uri = ""
        if isinstance(doc, Document):
            uri = doc.source.uri
        elif hasattr(doc, "sources") and doc.sources:
            uri = doc.sources[0].get("uri", "")
        if not uri:
            continue
        uri_to_docs.setdefault(uri, []).append(doc)
    dup_uris = {uri: docs for uri, docs in uri_to_docs.items() if len(docs) > 1}
    check18_ok = len(dup_uris) == 0
    items.append(QualityCheckItem(
        name="duplicate_document_detection",
        passed=check18_ok,
        detail=(
            f"{len(dup_uris)} 個 URI 有重複的非歸檔文件："
            + "; ".join(
                f"'{uri}' ({len(docs)} 份)"
                for uri, docs in list(dup_uris.items())[:5]
            )
            + (f" ... (+{len(dup_uris) - 5})" if len(dup_uris) > 5 else "")
            if dup_uris
            else "所有非歸檔文件的 source URI 均唯一"
        ),
        weight=2,
    ))

    # --- 19. Duplicate task detection ---
    # Find open tasks with Jaccard title similarity > 0.7.
    open_tasks = [
        t for t in (tasks or [])
        if getattr(t, "status", None) in ("todo", "in_progress", "review")
    ]
    similar_task_pairs: list[tuple] = []
    for i in range(len(open_tasks)):
        for j in range(i + 1, len(open_tasks)):
            t_a = open_tasks[i]
            t_b = open_tasks[j]
            sim = _jaccard_similarity(t_a.title, t_b.title)
            if sim > 0.7:
                similar_task_pairs.append((t_a, t_b, sim))
    check19_ok = len(similar_task_pairs) == 0
    items.append(QualityCheckItem(
        name="duplicate_task_detection",
        passed=check19_ok,
        detail=(
            f"{len(similar_task_pairs)} 組開放中任務標題高度相似（Jaccard > 0.7）："
            + "; ".join(
                f"'{a.title}' ↔ '{b.title}' ({sim:.2f})"
                for a, b, sim in similar_task_pairs[:5]
            )
            + (f" ... (+{len(similar_task_pairs) - 5})" if len(similar_task_pairs) > 5 else "")
            if similar_task_pairs
            else f"所有 {len(open_tasks)} 個開放中任務均無重複"
        ),
        weight=1,
    ))

    # --- 20. Entry sparsity ---
    # Active L2 modules with zero entries indicate shallow semantic knowledge.
    active_l2_ids = [
        e.id for e in entities
        if e.type == EntityType.MODULE and e.status == EntityStatus.ACTIVE and e.id
    ]
    if active_l2_ids and entries_by_entity:
        zero_entry_l2 = [
            eid for eid in active_l2_ids
            if entries_by_entity.get(eid, 0) == 0
        ]
        sparsity_ratio = len(zero_entry_l2) / len(active_l2_ids)
        check20_ok = sparsity_ratio <= 0.5
        # Map ids back to names for display
        entity_name_map = {e.id: e.name for e in entities if e.id}
        sparse_names = [entity_name_map.get(eid, eid) for eid in zero_entry_l2[:5]]
        items.append(QualityCheckItem(
            name="entry_sparsity",
            passed=check20_ok,
            detail=(
                f"{len(zero_entry_l2)}/{len(active_l2_ids)} 個 active L2 模組無任何 entry"
                f"（{sparsity_ratio:.0%}，超過 50% 閾值）："
                + ", ".join(sparse_names)
                + (f" ... (+{len(zero_entry_l2) - 5})" if len(zero_entry_l2) > 5 else "")
                if not check20_ok
                else f"{len(active_l2_ids)} 個 active L2 模組中，有 entry 的比例正常（{1 - sparsity_ratio:.0%}）"
            ),
            weight=2,
        ))
    else:
        # No entry data provided or no active L2 — skip with pass
        items.append(QualityCheckItem(
            name="entry_sparsity",
            passed=True,
            detail="無 entry 資料或無 active L2，跳過稀疏度檢查",
            weight=2,
        ))

    # --- 21. L2 count balance per product ---
    # Products with < 3 or > 15 modules are imbalanced.
    products = [e for e in entities if e.type == EntityType.PRODUCT and e.id]
    module_count_by_product: dict[str, int] = {}
    for mod in candidate_modules:
        pid = mod.parent_id
        if pid:
            module_count_by_product[pid] = module_count_by_product.get(pid, 0) + 1
    product_name_map = {p.id: p.name for p in products}
    imbalanced_products = [
        (pid, cnt)
        for pid, cnt in module_count_by_product.items()
        if cnt < 3 or cnt > 15
    ]
    check21_ok = len(imbalanced_products) == 0
    items.append(QualityCheckItem(
        name="l2_count_balance",
        passed=check21_ok,
        detail=(
            f"{len(imbalanced_products)} 個 product 的 L2 數量不平衡（<3 或 >15）："
            + "; ".join(
                f"'{product_name_map.get(pid, pid)}' ({cnt} 個)"
                for pid, cnt in imbalanced_products[:5]
            )
            + (f" ... (+{len(imbalanced_products) - 5})" if len(imbalanced_products) > 5 else "")
            if imbalanced_products
            else f"所有 {len(products)} 個 product 的 L2 數量均在合理範圍（3-15）"
        ),
        weight=1,
    ))

    # Compute overall score using weighted calculation (warnings don't affect score)
    passed = [i for i in items if i.passed]
    failed = [i for i in items if not i.passed]
    weighted_total = sum(i.weight for i in items)
    weighted_passed = sum(i.weight for i in passed)
    score = int((weighted_passed / weighted_total) * 100) if weighted_total else 0

    # Warnings: check3 suspicious all-confirmed + check11 verbose L2 summaries + check14 review overdue
    warning_items: list[QualityCheckItem] = []
    if check3_warning:
        warning_items.append(items[2])  # unconfirmed_fields_marked
    if check11_warning_parts:
        warning_items.append(items[10])  # l2_summary_conciseness
    if overdue_modules:
        warning_items.append(items[13])  # l2_governance_review_overdue
    if modules_without_global:
        warning_items.append(items[15])  # l2_consolidation_mode (index 15, 0-based)

    return QualityReport(
        score=score,
        passed=passed,
        failed=failed,
        warnings=warning_items,
    )


# ──────────────────────────────────────────────
# P0-2: 品質校正優先級（Quality Correction Priority）
# ──────────────────────────────────────────────

def _has_technical_summary_domain(summary: str) -> bool:
    """Check if summary contains technical terms (domain-layer copy, no application import)."""
    return any(
        re.search(r"\b" + re.escape(term) + r"\b", summary or "", re.IGNORECASE)
        for term in _L2_TECH_TERMS
    )


def _compute_impacts_vagueness(entity_id: str, relationships: list[Relationship]) -> int:
    """Compute impacts vagueness dimension score (0/1/2)."""
    outgoing_impacts = [
        r for r in relationships
        if r.source_entity_id == entity_id and r.type == RelationshipType.IMPACTS
    ]
    if not outgoing_impacts:
        return 2
    has_concrete = any(_is_concrete_impacts_description(r.description) for r in outgoing_impacts)
    return 0 if has_concrete else 1


def _compute_summary_generality(summary: str) -> int:
    """Compute summary generality dimension score (0/1/2)."""
    if _has_technical_summary_domain(summary):
        return 0
    if len(summary) >= 30:
        return 1
    return 2


def _compute_three_q_confidence(entity: Entity) -> float:
    """Compute three-question confidence dimension score (0/0.5/1.0/1.5/2.0)."""
    tags = entity.tags if entity.tags else Tags(what="", why="", how="", who="")
    has_why = bool(_safe_str(tags.why).strip())
    has_how = bool(_safe_str(tags.how).strip())
    has_layer_decision = bool(
        entity.details
        and isinstance(entity.details, dict)
        and entity.details.get("layer_decision")
    )

    if entity.status == EntityStatus.ACTIVE and has_why and has_how:
        return 0.0
    if entity.status == EntityStatus.DRAFT:
        if has_layer_decision:
            return 0.5
        if has_why and has_how:
            return 1.0
        if has_why or has_how:
            return 1.5
    return 2.0


def _top_repair_action(dimensions: dict) -> str:
    """Return the repair action for the highest-weighted dimension."""
    weighted = {
        "impacts_vagueness": dimensions["impacts_vagueness"] * 0.5,
        "summary_generality": dimensions["summary_generality"] * 0.3,
        "three_q_confidence": dimensions["three_q_confidence"] * 0.2,
    }
    top_dim = max(weighted, key=lambda k: weighted[k])
    actions = {
        "impacts_vagueness": "補充至少 1 條具體 impacts（A 改了什麼→B 的什麼要跟著看）",
        "summary_generality": "改寫 summary，加入核心挑戰、已知限制或關鍵技術名詞",
        "three_q_confidence": "完善 tags.why 和 tags.how，或重新走三問判斷確認分層正確",
    }
    return actions[top_dim]


def compute_quality_correction_priority(
    entities: list[Entity],
    relationships: list[Relationship],
) -> list[dict]:
    """Compute quality correction priority for L2 entities.

    Three dimensions (all without external dependencies):
      1. impacts_vagueness (0/1/2)
      2. summary_generality (0/1/2)
      3. three_q_confidence (0/0.5/1.0/1.5/2.0)

    score = impacts_vagueness*0.5 + summary_generality*0.3 + three_q_confidence*0.2

    Returns list of dicts sorted by score descending (highest = most urgent).
    Only evaluates type==MODULE, status in (draft, active).
    """
    target_modules = [
        e for e in entities
        if e.type == EntityType.MODULE
        and e.status in (EntityStatus.DRAFT, EntityStatus.ACTIVE)
        and e.id
    ]

    ranked: list[dict] = []
    for mod in target_modules:
        iv = _compute_impacts_vagueness(mod.id, relationships)
        sg = _compute_summary_generality(mod.summary or "")
        tq = _compute_three_q_confidence(mod)
        score = round(iv * 0.5 + sg * 0.3 + tq * 0.2, 4)
        dimensions = {
            "impacts_vagueness": iv,
            "summary_generality": sg,
            "three_q_confidence": tq,
        }
        ranked.append({
            "entity_id": mod.id,
            "entity_name": mod.name,
            "score": score,
            "dimensions": dimensions,
            "top_repair_action": _top_repair_action(dimensions),
        })

    ranked.sort(key=lambda x: x["score"], reverse=True)
    return ranked


# ──────────────────────────────────────────────
# P1-1: Task 信號輔助函數（純函數）
# ──────────────────────────────────────────────

PROBLEM_SIGNAL_KEYWORDS: frozenset[str] = frozenset({
    # 中文
    "已知問題", "已知限制", "workaround", "繞過", "失敗", "無法",
    "bug", "問題", "限制", "例外", "不支援", "timeout", "衝突",
    # 英文
    "known issue", "fail", "error", "limit",
    "exception", "not supported", "conflict", "broken", "issue",
})


def _task_problem_tokens(result_text: str, description_text: str) -> set[str]:
    """Extract problem-related keywords from task result + description."""
    text = f"{result_text or ''} {description_text or ''}".lower()
    return {kw for kw in PROBLEM_SIGNAL_KEYWORDS if kw in text}


def _tasks_are_similar(tokens1: set[str], tokens2: set[str], threshold: int = 2) -> bool:
    """Return True if two task problem-token sets overlap >= threshold."""
    return len(tokens1 & tokens2) >= threshold


def _blindspot_threshold(entity_task_count: int) -> int:
    """Dynamic threshold for blindspot suggestion based on project size."""
    if entity_task_count < 20:
        return 2
    if entity_task_count <= 100:
        return 3
    return 5


# ──────────────────────────────────────────────
# P1-3: 文件一致性標記（Document Consistency Detection）
# ──────────────────────────────────────────────

_VERSION_PATTERN = re.compile(r"v(\d+)\.(\d+)", re.IGNORECASE)

CONTRADICTION_PAIRS: list[tuple[str, str]] = [
    ("不支援", "支援"),
    ("廢棄", "推薦"),
    ("已移除", "現有"),
    ("deprecated", "recommended"),
    ("removed", "current"),
]

_DOC_STALE_THRESHOLD_DAYS = 180
_ENTITY_RECENT_UPDATE_DAYS = 90


def _extract_version(text: str) -> tuple[int, int] | None:
    """Extract version tuple (major, minor) from text, or None."""
    m = _VERSION_PATTERN.search(text or "")
    return (int(m.group(1)), int(m.group(2))) if m else None


def _get_doc_linked_entity_ids(doc: Entity) -> list[str]:
    """Get linked entity IDs from a document entity (via parent_id)."""
    return [doc.parent_id] if doc.parent_id else []


def detect_stale_documents_from_consistency(
    entities: list[Entity],
    relationships: list[Relationship],
) -> list[dict]:
    """Detect potentially stale documents via three consistency signals.

    Signal 1: version_lag — document version is >= 2 major versions behind
        the newest version found in same entity group.
    Signal 2: contradictory_signal — two documents under same entity have
        opposing keyword pairs in their name or summary.
    Signal 3: entity_updated_but_doc_stale — L2 entity updated within 90
        days but its linked documents haven't been updated in 180+ days.

    Returns list of dicts:
    {
        "document_id": str,
        "document_title": str,
        "linked_entity_id": str | None,
        "linked_entity_name": str | None,
        "reason": str,
        "detail": str,
        "suggested_action": str,
    }
    """
    now = datetime.now(timezone.utc)

    def _to_aware(dt: datetime) -> datetime:
        return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)

    doc_entities = [e for e in entities if e.type == EntityType.DOCUMENT and e.id]
    entity_map = {e.id: e for e in entities if e.id}

    # Group documents by linked entity (parent_id or via relationships)
    docs_by_linked: dict[str, list[Entity]] = {}
    for doc in doc_entities:
        linked_ids = _get_doc_linked_entity_ids(doc)
        # Also check part_of relationships
        for rel in relationships:
            if rel.source_entity_id == doc.id and rel.type in (
                RelationshipType.PART_OF,
            ):
                if rel.target_id:
                    linked_ids.append(rel.target_id)
        if linked_ids:
            for eid in linked_ids:
                docs_by_linked.setdefault(eid, []).append(doc)
        else:
            docs_by_linked.setdefault("__unlinked__", []).append(doc)

    warnings: list[dict] = []
    seen_doc_ids: set[str] = set()

    def _add_warning(doc: Entity, linked_id: str | None, reason: str, detail: str) -> None:
        if doc.id in seen_doc_ids:
            return
        seen_doc_ids.add(doc.id)
        linked_entity = entity_map.get(linked_id) if linked_id else None
        warnings.append({
            "document_id": doc.id,
            "document_title": doc.name,
            "linked_entity_id": linked_id,
            "linked_entity_name": linked_entity.name if linked_entity else None,
            "reason": reason,
            "detail": detail,
            "suggested_action": "確認是否已被更新版本取代，若是請走 archive/supersede 流程",
        })

    # Signal 1: version_lag
    for linked_id, docs in docs_by_linked.items():
        if linked_id == "__unlinked__":
            continue
        versioned = []
        for doc in docs:
            ver = _extract_version(doc.name) or _extract_version(doc.summary or "")
            if ver:
                versioned.append((doc, ver))
        if len(versioned) < 2:
            continue
        max_major = max(v[0] for _, v in versioned)
        for doc, ver in versioned:
            if max_major - ver[0] >= 2:
                _add_warning(
                    doc, linked_id, "version_lag",
                    f"發現更新版本 v{max_major}.x 存在於同一模組下的其他文件",
                )

    # Signal 2: contradictory_signal
    for linked_id, docs in docs_by_linked.items():
        if linked_id == "__unlinked__" or len(docs) < 2:
            continue
        for i in range(len(docs)):
            for j in range(i + 1, len(docs)):
                doc_a, doc_b = docs[i], docs[j]
                text_a = f"{doc_a.name} {doc_a.summary or ''}".lower()
                text_b = f"{doc_b.name} {doc_b.summary or ''}".lower()
                for neg_word, pos_word in CONTRADICTION_PAIRS:
                    if neg_word in text_a and pos_word in text_b:
                        _add_warning(
                            doc_a, linked_id, "contradictory_signal",
                            f"與文件 '{doc_b.name}' 在同一模組下出現矛盾詞：'{neg_word}' vs '{pos_word}'",
                        )
                    elif pos_word in text_a and neg_word in text_b:
                        _add_warning(
                            doc_b, linked_id, "contradictory_signal",
                            f"與文件 '{doc_a.name}' 在同一模組下出現矛盾詞：'{neg_word}' vs '{pos_word}'",
                        )

    # Signal 3: entity_updated_but_doc_stale
    stale_threshold = timedelta(days=_DOC_STALE_THRESHOLD_DAYS)
    recent_threshold = timedelta(days=_ENTITY_RECENT_UPDATE_DAYS)
    for linked_id, docs in docs_by_linked.items():
        if linked_id == "__unlinked__":
            continue
        linked_entity = entity_map.get(linked_id)
        if not linked_entity or linked_entity.type != EntityType.MODULE:
            continue
        entity_updated_at = _to_aware(linked_entity.updated_at)
        if now - entity_updated_at > recent_threshold:
            continue  # entity not recently updated
        for doc in docs:
            doc_updated_at = _to_aware(doc.updated_at)
            if now - doc_updated_at > stale_threshold:
                _add_warning(
                    doc, linked_id, "entity_updated_but_doc_stale",
                    f"關聯的 L2 entity '{linked_entity.name}' 在近 {_ENTITY_RECENT_UPDATE_DAYS} 天有更新，"
                    f"但此文件超過 {_DOC_STALE_THRESHOLD_DAYS} 天未更新",
                )

    return warnings


# ──────────────────────────────────────────────
# Search-unused signals (搜尋後未使用信號)
# ──────────────────────────────────────────────

def compute_search_unused_signals(
    entity_usage_stats: list[dict],
    entities: list[Entity],
) -> list[dict]:
    """Calculate per-entity unused ratio from tool event stats.

    Args:
        entity_usage_stats: List of dicts from ToolEventRepository.get_entity_usage_stats().
            Each dict contains entity_id, search_count, get_count.
        entities: Entity objects for name lookup.

    Returns:
        List of dicts for entities flagged as low-usage-efficiency (flagged=True).
        Each dict: entity_id, entity_name, search_count, get_count,
        unused_ratio, flagged.
    """
    entity_name_map = {e.id: e.name for e in entities if e.id}

    flagged: list[dict] = []
    for stat in entity_usage_stats:
        entity_id = stat["entity_id"]
        search_count = int(stat.get("search_count") or 0)
        get_count = int(stat.get("get_count") or 0)
        unused_ratio = 1.0 - get_count / max(search_count, 1)
        is_flagged = unused_ratio > 0.8 and search_count >= 3
        if is_flagged:
            flagged.append({
                "entity_id": entity_id,
                "entity_name": entity_name_map.get(entity_id, entity_id),
                "search_count": search_count,
                "get_count": get_count,
                "unused_ratio": round(unused_ratio, 4),
                "flagged": True,
            })
    return flagged


# ──────────────────────────────────────────────
# Summary heuristic quality (摘要品質評估)
# ──────────────────────────────────────────────

TECHNICAL_KEYWORDS: list[str] = [
    "API", "schema", "pipeline", "算法", "架構", "SQL", "migration",
    "endpoint", "cache", "queue", "repository", "service", "domain",
    "LLM", "prompt", "inference", "model", "token",
]

CHALLENGE_KEYWORDS: list[str] = ["挑戰", "限制", "問題", "風險", "瓶頸", "trade-off", "取捨"]

MARKETING_KEYWORDS: list[str] = ["負責", "提供", "支援", "確保", "優化", "全面", "高效", "完善"]


def score_summary_quality(
    summary: str,
    entity_type: str,
) -> dict:
    """Evaluate semantic quality of an L2 entity summary.

    Args:
        summary: The entity summary text to evaluate.
        entity_type: The entity type string (for future type-specific rules).

    Returns:
        Dict with keys: has_technical_keywords, has_challenge_context,
        is_too_generic, marketing_ratio, quality_score.
        quality_score is "good", "needs_improvement", or "poor".
    """
    summary_lower = (summary or "").lower()

    has_technical_keywords = any(kw.lower() in summary_lower for kw in TECHNICAL_KEYWORDS)
    has_challenge_context = any(kw.lower() in summary_lower for kw in CHALLENGE_KEYWORDS)

    # A summary is too generic if shorter than 50 chars or lacks any proper noun.
    # Proper noun heuristic: uppercase-starting ASCII token or CJK sequence of 2+ chars.
    has_proper_noun = bool(
        re.search(r"[A-Z][a-zA-Z0-9_]{1,}", summary or "")
        or re.search(r"[\u4e00-\u9fff]{2,}", summary or "")
    )
    is_too_generic = len((summary or "").strip()) < 50 or not has_proper_noun

    # Marketing ratio: keyword hit count / total word count (CJK chars + ASCII words)
    word_count = max(len(re.findall(r"[\u4e00-\u9fff]|[A-Za-z0-9]+", summary or "")), 1)
    marketing_hits = sum(summary_lower.count(kw.lower()) for kw in MARKETING_KEYWORDS)
    marketing_ratio = marketing_hits / word_count

    if (
        has_technical_keywords
        and has_challenge_context
        and not is_too_generic
        and marketing_ratio < 0.1
    ):
        quality_score = "good"
    elif is_too_generic or (not has_technical_keywords and marketing_ratio > 0.2):
        quality_score = "poor"
    else:
        quality_score = "needs_improvement"

    return {
        "has_technical_keywords": has_technical_keywords,
        "has_challenge_context": has_challenge_context,
        "is_too_generic": is_too_generic,
        "marketing_ratio": round(marketing_ratio, 4),
        "quality_score": quality_score,
    }


# ---------------------------------------------------------------------------
# Invalid document title detection (Task 20/40)
# ---------------------------------------------------------------------------

_BARE_DOMAIN_TITLES: frozenset[str] = frozenset({
    "github", "notion", "drive", "wiki", "confluence"
})


def detect_invalid_document_titles(entities: list[Entity]) -> list[dict]:
    """Return invalid document entities with bare-domain or empty titles.

    An entity is considered invalid when:
    - title (entity.name) is empty/None, OR
    - title matches a bare source-type domain name (case-insensitive).

    Returns a list of dicts with keys:
        entity_id, current_title, source_uri, linked_entity_ids
    """
    invalid: list[dict] = []
    for doc in entities:
        title = (doc.name or "").strip().lower()
        if title and title not in _BARE_DOMAIN_TITLES:
            continue

        source_uri = ""
        if doc.sources:
            source_uri = doc.sources[0].get("uri", "")

        linked_ids: list[str] = []
        if doc.parent_id:
            linked_ids.append(doc.parent_id)

        invalid.append({
            "entity_id": doc.id,
            "current_title": doc.name or "",
            "source_uri": source_uri,
            "linked_entity_ids": linked_ids,
        })

    return invalid


# ──────────────────────────────────────────────
# Health Signal KPIs (ADR-020)
# ──────────────────────────────────────────────

HEALTH_THRESHOLDS: dict[str, dict[str, float]] = {
    "quality_score":               {"green": 70, "yellow": 50},
    "unconfirmed_ratio":           {"green": 0.30, "yellow": 0.60},
    "blindspot_total":             {"green": 20, "yellow": 50},
    "median_confirm_latency_days": {"green": 3, "yellow": 7},
    "active_l2_missing_impacts":   {"green": 0, "yellow": 3},
    "duplicate_blindspot_rate":    {"green": 0.05, "yellow": 0.15},
    "bundle_highlights_coverage":  {"green": 0.80, "yellow": 0.50},
}

BOOTSTRAP_OVERRIDES: dict[str, dict[str, float]] = {
    "unconfirmed_ratio": {"green": 0.50, "yellow": 0.70},
}


def _kpi_level(kpi_name: str, value: float, *, bootstrap: bool = False) -> str:
    """Determine green/yellow/red level for a single KPI."""
    thresholds = HEALTH_THRESHOLDS.get(kpi_name)
    if not thresholds:
        return "green"
    if bootstrap and kpi_name in BOOTSTRAP_OVERRIDES:
        thresholds = BOOTSTRAP_OVERRIDES[kpi_name]

    green_threshold = thresholds["green"]
    yellow_threshold = thresholds["yellow"]

    # quality_score / bundle_highlights_coverage are "higher is better"; others are "lower is better"
    if kpi_name in {"quality_score", "bundle_highlights_coverage"}:
        if value >= green_threshold:
            return "green"
        if value >= yellow_threshold:
            return "yellow"
        return "red"
    else:
        if value <= green_threshold:
            return "green"
        if value <= yellow_threshold:
            return "yellow"
        return "red"


def compute_health_kpis(
    entities: list[Entity],
    protocols: list[Protocol],
    blindspots: list[Blindspot],
    quality_score: int,
    l2_repairs_count: int,
    bundle_highlights_coverage: float | None = None,
    *,
    bootstrap: bool = False,
) -> dict:
    """Compute 6 health KPIs from pre-fetched data. Pure function, zero I/O.

    Returns dict with 'kpis', 'overall_level', 'recommended_action', 'red_reasons'.
    """
    # --- unconfirmed_ratio ---
    all_items = [*entities, *protocols, *blindspots]
    total_items = len(all_items)
    unconfirmed_items = sum(1 for item in all_items if not getattr(item, "confirmed_by_user", False))
    unconfirmed_ratio = (unconfirmed_items / total_items) if total_items else 0.0

    # --- blindspot_total ---
    blindspot_total = len(blindspots)

    # --- duplicate_blindspot_rate ---
    signature_count: dict[tuple, int] = {}
    for bs in blindspots:
        sig = (
            " ".join(bs.description.strip().lower().split()),
            bs.severity,
            tuple(sorted(bs.related_entity_ids)),
            " ".join(bs.suggested_action.strip().lower().split()),
        )
        signature_count[sig] = signature_count.get(sig, 0) + 1
    duplicate_blindspots = sum(max(0, cnt - 1) for cnt in signature_count.values())
    duplicate_blindspot_rate = (duplicate_blindspots / len(blindspots)) if blindspots else 0.0

    # --- median_confirm_latency_days ---
    latencies: list[float] = []
    for item in all_items:
        if not getattr(item, "confirmed_by_user", False):
            continue
        created_at = getattr(item, "created_at", None) or getattr(item, "generated_at", None)
        updated_at = getattr(item, "updated_at", None)
        if created_at and updated_at and updated_at >= created_at:
            latencies.append((updated_at - created_at).total_seconds() / 86400)
    median_confirm_latency_days = 0.0
    if latencies:
        sorted_days = sorted(latencies)
        mid = len(sorted_days) // 2
        if len(sorted_days) % 2 == 1:
            median_confirm_latency_days = sorted_days[mid]
        else:
            median_confirm_latency_days = (sorted_days[mid - 1] + sorted_days[mid]) / 2

    # --- Build KPI dict with levels ---
    raw_kpis = {
        "quality_score": quality_score,
        "unconfirmed_ratio": round(unconfirmed_ratio, 4),
        "blindspot_total": blindspot_total,
        "median_confirm_latency_days": round(median_confirm_latency_days, 2),
        "active_l2_missing_impacts": l2_repairs_count,
        "duplicate_blindspot_rate": round(duplicate_blindspot_rate, 4),
    }
    if bundle_highlights_coverage is not None:
        raw_kpis["bundle_highlights_coverage"] = round(bundle_highlights_coverage, 4)

    kpis = {}
    for name, value in raw_kpis.items():
        level = _kpi_level(name, value, bootstrap=bootstrap)
        kpis[name] = {"value": value, "level": level}

    # --- overall_level: worst of all KPIs ---
    levels = [v["level"] for v in kpis.values()]
    if "red" in levels:
        overall_level = "red"
    elif "yellow" in levels:
        overall_level = "yellow"
    else:
        overall_level = "green"

    # --- red_reasons ---
    red_reasons = []
    for name, kpi_data in kpis.items():
        if kpi_data["level"] == "red":
            thresholds = HEALTH_THRESHOLDS[name]
            if bootstrap and name in BOOTSTRAP_OVERRIDES:
                thresholds = BOOTSTRAP_OVERRIDES[name]
            threshold_val = thresholds["yellow"]
            red_reasons.append({
                "kpi": name,
                "value": kpi_data["value"],
                "threshold": threshold_val,
                "repair": _kpi_repair_hint(name),
            })

    return {
        "kpis": kpis,
        "overall_level": overall_level,
        "recommended_action": determine_recommended_action(overall_level),
        "red_reasons": red_reasons,
    }


def determine_recommended_action(overall_level: str) -> str | None:
    """Map overall health level to recommended action."""
    if overall_level == "red":
        return "run_governance"
    if overall_level == "yellow":
        return "review_health"
    return None


def _kpi_repair_hint(kpi_name: str) -> str:
    """Return human-readable repair hint for a red KPI."""
    hints = {
        "quality_score": "執行 analyze(check_type='quality') 查看具體缺陷並修復",
        "unconfirmed_ratio": "使用 confirm 確認 draft 狀態的 entities/protocols/blindspots",
        "blindspot_total": "逐一審查 blindspots，resolve 已處理的項目",
        "median_confirm_latency_days": "加速 confirm 流程，縮短 draft → confirmed 延遲",
        "active_l2_missing_impacts": "補 impacts 或降級 L2 到 L3",
        "duplicate_blindspot_rate": "合併重複的 blindspots",
    }
    return hints.get(kpi_name, "")
