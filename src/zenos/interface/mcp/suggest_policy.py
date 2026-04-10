"""MCP tool: suggest_policy — suggest entity visibility policy."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


async def suggest_policy(
    entity_id: str,
) -> dict:
    """根據 entity 的內容和位置，建議合適的 visibility。

    使用時機：
    - 在 capture 新 entity 時，不確定要設什麼 visibility
    - 審查現有 entity 的權限是否合適

    Args:
        entity_id: 要建議 policy 的 entity ID

    Returns:
        dict — {entity_id, suggested_visibility, reason, risk_score}
    """
    from zenos.interface.mcp import _ensure_services, ontology_service
    from zenos.application.identity.policy_suggestion_service import PolicySuggestionService

    await _ensure_services()
    svc = PolicySuggestionService(entity_repo=ontology_service._entities)
    return await svc.suggest(entity_id)
