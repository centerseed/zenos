"""Policy suggestion service.

Suggests appropriate entity visibility based on content and hierarchy position.
Used during capture to help agents set correct access controls.
"""

from __future__ import annotations

from zenos.domain.repositories import EntityRepository

_SENSITIVE_KEYWORDS = [
    "薪資", "salary", "財務", "finance", "人事", "hr",
    "法務", "legal", "合約", "contract", "機密", "confidential",
]

_SENSITIVE_REASON = "Entity 包含財務/人事/法務敏感關鍵字，建議限制可見性"
_INHERIT_REASON = "L3/document entity 建議繼承父節點 visibility"
_PUBLIC_REASON = "一般 entity，建議 public"


def _contains_sensitive_keyword(name: str, summary: str) -> bool:
    """Return True if name or summary contains any sensitive keyword (case-insensitive)."""
    text = (name + " " + summary).lower()
    return any(kw.lower() in text for kw in _SENSITIVE_KEYWORDS)


class PolicySuggestionService:
    """Suggest visibility policy for an entity based on content and position.

    Rules (applied in priority order):
    1. Finance/HR/Legal keywords → restricted (risk_score=0.7)
    2. L3 entity or type=document with parent → inherit parent visibility (risk_score=0.2)
    3. General entity → public (risk_score=0.0)
    """

    def __init__(self, entity_repo: EntityRepository) -> None:
        self._entity_repo = entity_repo

    async def suggest(self, entity_id: str) -> dict:
        """Suggest an appropriate visibility policy for the given entity.

        Args:
            entity_id: ID of the entity to evaluate.

        Returns:
            dict with keys: entity_id, suggested_visibility, reason, risk_score.
            If entity not found, returns public with risk_score=0.0.
        """
        entity = await self._entity_repo.get_by_id(entity_id)
        if entity is None:
            return {
                "entity_id": entity_id,
                "suggested_visibility": "public",
                "reason": _PUBLIC_REASON,
                "risk_score": 0.0,
            }

        # Rule 1: Sensitive keyword check (highest priority)
        if _contains_sensitive_keyword(entity.name, entity.summary):
            return {
                "entity_id": entity_id,
                "suggested_visibility": "restricted",
                "reason": _SENSITIVE_REASON,
                "risk_score": 0.7,
            }

        # Rule 2: L3 or document type → inherit from parent
        is_l3 = entity.level == 3
        is_document = entity.type == "document"
        if (is_l3 or is_document) and entity.parent_id:
            parent = await self._entity_repo.get_by_id(entity.parent_id)
            inherited_visibility = parent.visibility if parent else "public"
            return {
                "entity_id": entity_id,
                "suggested_visibility": inherited_visibility,
                "reason": _INHERIT_REASON,
                "risk_score": 0.2,
            }

        # Rule 3: Default public
        return {
            "entity_id": entity_id,
            "suggested_visibility": "public",
            "reason": _PUBLIC_REASON,
            "risk_score": 0.0,
        }
