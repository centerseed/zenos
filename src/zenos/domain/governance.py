"""Governance rules — encodes REF-ontology-methodology.md business logic.

All functions are pure: they take domain objects in, return result objects out.
Zero external dependencies.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta

from .models import (
    Blindspot,
    Document,
    DocumentStatus,
    DocumentTags,
    Entity,
    EntityStatus,
    EntityType,
    Protocol,
    QualityCheckItem,
    QualityReport,
    Relationship,
    RelationshipType,
    Severity,
    SplitRecommendation,
    StalenessWarning,
    Tags,
    TagConfidence,
)


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
    if now is None:
        now = datetime.utcnow()

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
        if isinstance(d, Document):
            return d.last_reviewed_at or d.updated_at
        return d.last_reviewed_at or d.updated_at

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
            if entity.updated_at > doc_last + _STALENESS_THRESHOLD:
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
        if target.updated_at > source.updated_at + _STALENESS_THRESHOLD:
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
        how_lower = (doc.tags.how if hasattr(doc.tags, 'how') else "").lower()
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

def run_quality_check(
    entities: list[Entity],
    documents: list[Entity | Document],
    protocols: list[Protocol],
    blindspots: list[Blindspot],
    relationships: list[Relationship],
) -> QualityReport:
    """Run the 12-item quality checklist from REF-ontology-methodology.md.

    Returns a QualityReport with score (0-100), passed, failed, and warnings.
    Items 1-9 cover general ontology quality; items 10-12 cover L2 (module) quality.
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
    ))

    # Compute overall score (warnings don't affect score)
    passed = [i for i in items if i.passed]
    failed = [i for i in items if not i.passed]
    # Warnings: check3 suspicious all-confirmed + check11 verbose L2 summaries
    warning_items: list[QualityCheckItem] = []
    if check3_warning:
        warning_items.append(items[2])  # unconfirmed_fields_marked
    if check11_warning_parts:
        warning_items.append(items[10])  # l2_summary_conciseness
    score = int((len(passed) / len(items)) * 100) if items else 0

    return QualityReport(
        score=score,
        passed=passed,
        failed=failed,
        warnings=warning_items,
    )
