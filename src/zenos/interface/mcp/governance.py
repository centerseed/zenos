"""MCP tools: governance_guide, find_gaps, common_neighbors."""

from __future__ import annotations

import logging

from zenos.interface.governance_rules import GOVERNANCE_RULES
from zenos.interface.mcp._common import _unified_response

logger = logging.getLogger(__name__)

_VALID_TOPICS = frozenset(GOVERNANCE_RULES.keys())
_VALID_LEVELS = frozenset({1, 2, 3})


async def governance_guide(
    topic: str,
    level: int = 1,
) -> dict:
    """取得 ZenOS 治理規則指南。

    讓任何 MCP client 按需載入 ZenOS 治理規則，取代 local skill 文件。
    規則分四個主題，三個深度層級。不需要 DB 連線，不需要 partner key。

    使用時機：
    - 開始 capture/write 操作前想確認規則 → governance_guide(topic="entity", level=1)
    - 需要完整建票規則 → governance_guide(topic="task", level=2)
    - 需要含範例的 capture 指南 → governance_guide(topic="capture", level=3)

    Args:
        topic: 規則主題。entity=L2知識節點治理, document=L3文件治理,
               task=任務建票與驗收, capture=知識捕獲分層路由
        level: 深度層級。1=核心摘要(~1k tokens), 2=完整規則(~2-3k),
               3=含範例(~3-5k)。預設 1。

    Returns:
        dict with keys: topic, level, version, content
        On invalid input: {"error": "INVALID_INPUT", "message": "..."}
    """
    if topic not in _VALID_TOPICS:
        return {
            "error": "INVALID_INPUT",
            "message": f"topic 必須是 {sorted(_VALID_TOPICS)} 之一，收到：'{topic}'",
        }
    if level not in _VALID_LEVELS:
        return {
            "error": "INVALID_INPUT",
            "message": f"level 必須是 1/2/3，收到：{level}",
        }

    _topic_versions = {
        "entity": "1.1",
        "document": "1.1",
        "task": "2.0",
        "capture": "1.0",
    }
    return {
        "topic": topic,
        "level": level,
        "version": _topic_versions.get(topic, "1.0"),
        "content": GOVERNANCE_RULES[topic][level],
    }


async def find_gaps(
    gap_type: str = "all",
    scope_product: str | None = None,
) -> dict:
    """找出 ontology 中的結構性缺口——孤立節點、缺少關聯的節點。

    這是 search/get 做不到的「負面查詢」：找出圖譜中「不存在的東西」。
    用於定期健檢、發現 ontology 品質問題。

    使用時機：
    - 找孤立節點（沒有任何 relationship）→ find_gaps(gap_type="orphan_entities")
    - 找只被引用但無主動關聯的節點 → find_gaps(gap_type="underconnected")
    - 找語意品質差的節點（全是 related_to） → find_gaps(gap_type="weak_semantics")
    - 全面掃描 → find_gaps()
    - 限定在某產品下 → find_gaps(scope_product="ZenOS")

    不要用這個工具的情境：
    - 搜尋特定節點 → 用 search
    - 查看特定節點的關係 → 用 get（會顯示 outgoing/incoming 分類）
    - 品質分數和治理問題 → 用 analyze
    - 查詢某個節點缺什麼 → 用 get 看它的 relationships，不是 find_gaps

    Args:
        gap_type: "all" / "orphan_entities" / "weak_semantics" / "underconnected"
            - orphan_entities: 沒有任何 relationship 的非根節點
            - weak_semantics: 所有關聯都是 related_to，缺少 impacts/depends_on 等語意明確的關係
            - underconnected: 只有 incoming 沒有 outgoing 的節點
        scope_product: 限定在某產品名稱下（例如 "ZenOS"）

    Returns:
        {gaps: [{type, entity_id, entity_name, severity, suggestion}], total, by_type}
    """
    from zenos.interface.mcp import _ensure_services, ontology_service

    await _ensure_services()
    result = await ontology_service.find_gaps(gap_type, scope_product)
    return _unified_response(data=result)


async def common_neighbors(
    entity_a: str,
    entity_b: str,
) -> dict:
    """找出兩個節點的共同鄰居——同時與 A 和 B 有直接關聯的節點。

    用於發現隱藏的關聯、找出交集、理解兩個概念之間的間接連結。
    這是 search 做不到的「集合交集查詢」。

    使用時機：
    - 「A 和 B 有什麼共同關聯？」→ common_neighbors(entity_a="A", entity_b="B")
    - 找兩個模組共同影響的下游 → common_neighbors(entity_a="模組A", entity_b="模組B")

    不要用這個工具的情境：
    - 只看單一節點的關係 → 用 get
    - 看 A 到 B 的影響鏈 → 用 get 看 impact_chain

    Args:
        entity_a: 第一個節點的名稱或 ID
        entity_b: 第二個節點的名稱或 ID

    Returns:
        {entity_a, entity_b, common_neighbors: [{neighbor_id, neighbor_name, edge_type_a, edge_type_b}], count}
    """
    from zenos.interface.mcp import _ensure_services, ontology_service

    await _ensure_services()
    try:
        result = await ontology_service.find_common_neighbors(entity_a, entity_b)
    except ValueError as e:
        return _unified_response(
            status="rejected", data={}, rejection_reason=str(e)
        )
    return _unified_response(data=result)
