"""Permission risk analysis service.

Detects misconfigured entity visibility that could lead to
information silos (isolation) or data leaks (overexposure).
"""

from __future__ import annotations

from zenos.domain.knowledge import Entity
from zenos.domain.action import TaskRepository
from zenos.domain.knowledge import EntityRepository

_SENSITIVE_KEYWORDS = [
    "薪資", "salary", "財務", "finance", "人事", "hr",
    "legal", "法務", "合約", "contract", "機密",
]


def _is_sensitive(entity_name: str, entity_summary: str) -> bool:
    """Return True if name or summary contains any sensitive keyword (case-insensitive)."""
    text = (entity_name + " " + entity_summary).lower()
    return any(kw.lower() in text for kw in _SENSITIVE_KEYWORDS)


class PermissionRiskService:
    """Analyse permission configuration risk across entities and tasks.

    Detects two categories of risk:
    - Isolation: knowledge that becomes inaccessible due to overly restrictive settings.
    - Overexposure: sensitive knowledge exposed too broadly.
    """

    def __init__(
        self,
        entity_repo: EntityRepository,
        task_repo: TaskRepository,
    ) -> None:
        self._entity_repo = entity_repo
        self._task_repo = task_repo

    async def analyze_risk(self) -> dict:
        """Run all permission risk checks and return a structured report.

        Returns:
            dict with keys:
                isolation_score (float): 0.0 – 1.0, higher = more isolated.
                overexposure_score (float): 0.0 – 1.0, higher = more dangerous.
                warnings (list[dict]): Detailed warning list.
                summary (str): Human-readable summary.
        """
        entities = await self._entity_repo.list_all()
        tasks = await self._task_repo.list_all()

        warnings: list[dict] = []

        # ── Rule 1: Single-member isolation ──────────────────────────────────
        for ent in entities:
            if (
                ent.visibility in ("restricted", "confidential")
                and len(ent.visible_to_members) == 1
                and ent.visible_to_roles == []
                and ent.visible_to_departments == []
            ):
                warnings.append({
                    "type": "single_member_isolation",
                    "severity": "yellow",
                    "entity_id": ent.id,
                    "entity_name": ent.name,
                })

        # ── Rule 2: High confidential ratio ──────────────────────────────────
        total_entities = len(entities)
        confidential_count = sum(1 for e in entities if e.visibility == "confidential")
        confidential_ratio = confidential_count / total_entities if total_entities else 0.0
        if confidential_ratio > 0.30:
            warnings.append({
                "type": "high_confidential_ratio",
                "severity": "red",
                "ratio": round(confidential_ratio, 4),
            })

        # ── Rule 3: Sensitive entity overexposed ─────────────────────────────
        overexposed_entities: list[Entity] = []
        for ent in entities:
            if ent.visibility == "public" and _is_sensitive(ent.name, ent.summary):
                overexposed_entities.append(ent)
                warnings.append({
                    "type": "sensitive_entity_overexposed",
                    "severity": "red",
                    "entity_id": ent.id,
                    "entity_name": ent.name,
                })

        # ── Rule 4: Tasks hidden by entity visibility ─────────────────────────
        non_public_ids = {
            e.id for e in entities if e.visibility != "public" and e.id is not None
        }
        affected_task_count = sum(
            1
            for t in tasks
            if t.linked_entities
            and all(eid in non_public_ids for eid in t.linked_entities)
        )
        if affected_task_count > 5:
            warnings.append({
                "type": "tasks_hidden_by_entity_visibility",
                "severity": "yellow",
                "affected_task_count": affected_task_count,
            })

        # ── Score calculation ─────────────────────────────────────────────────
        has_single_member = any(w["type"] == "single_member_isolation" for w in warnings)
        has_high_confidential = any(w["type"] == "high_confidential_ratio" for w in warnings)
        tasks_hidden = affected_task_count > 5

        isolation_score = (
            (1 if has_single_member else 0)
            + (1 if has_high_confidential else 0)
            + (min(affected_task_count / 10, 1.0) if tasks_hidden else 0)
        ) / 3

        overexposure_score = min(len(overexposed_entities) / max(total_entities, 1), 1.0)

        # ── Summary ──────────────────────────────────────────────────────────
        red_count = sum(1 for w in warnings if w.get("severity") == "red")
        yellow_count = sum(1 for w in warnings if w.get("severity") == "yellow")

        if not warnings:
            summary = "無已知風險。所有 entity 的能見度設定正常。"
        else:
            parts = []
            if red_count:
                parts.append(f"{red_count} 個高風險項目（紅）")
            if yellow_count:
                parts.append(f"{yellow_count} 個警告項目（黃）")
            summary = f"發現 {len(warnings)} 個能見度風險：{'、'.join(parts)}。"

        return {
            "isolation_score": round(isolation_score, 4),
            "overexposure_score": round(overexposure_score, 4),
            "warnings": warnings,
            "summary": summary,
        }
