"""MCP tools: governance_guide, find_gaps, common_neighbors."""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
from pathlib import Path

from zenos.interface.governance_rules import GOVERNANCE_RULES
from zenos.interface.mcp._common import _unified_response, _error_response

logger = logging.getLogger(__name__)

_VALID_TOPICS = frozenset(GOVERNANCE_RULES.keys())
_VALID_LEVELS = frozenset({1, 2, 3})
_RULES_FILE = Path(__file__).resolve().parents[1] / "governance_rules.py"


def _content_version() -> str:
    return datetime.fromtimestamp(_RULES_FILE.stat().st_mtime, tz=timezone.utc).isoformat()


def _content_hash(content: str) -> str:
    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


async def governance_guide(
    topic: str,
    level: int = 2,
    since_hash: str | None = None,
) -> dict:
    """取得 ZenOS 治理規則指南。

    讓任何 MCP client 按需載入 ZenOS 治理規則，取代 local skill 文件。
    規則分七個主題，三個深度層級。不需要 DB 連線，不需要 partner key。

    使用時機：
    - 開始 capture/write 操作前想確認規則 → governance_guide(topic="entity", level=1)
    - 需要完整建票規則 → governance_guide(topic="task", level=2)
    - 需要含範例的 capture 指南 → governance_guide(topic="capture", level=3)

    Args:
        topic: 規則主題。entity=L2知識節點治理, document=L3文件治理,
               bundle=L3 文件 bundle-first 規則, task=任務建票與驗收,
               capture=知識捕獲分層路由, sync=知識同步流程,
               remediation=治理缺口修復流程
        level: 深度層級。1=核心摘要(~1k tokens), 2=完整規則(~2-3k),
               3=含範例(~3-5k)。預設 2。

    Returns:
        dict with keys: topic, level, version, content
        On invalid input: {"error": "INVALID_INPUT", "message": "..."}
    """
    normalized_topic = (topic or "").strip()
    if normalized_topic not in _VALID_TOPICS:
        return _error_response(
            status="rejected",
            error_code="UNKNOWN_TOPIC",
            message=f"topic 必須是 {sorted(_VALID_TOPICS)} 之一，收到：'{topic}'",
            extra_data={"available_topics": sorted(_VALID_TOPICS)},
        )
    if level not in _VALID_LEVELS:
        return _error_response(
            status="rejected",
            error_code="INVALID_LEVEL",
            message=f"level 必須是 1/2/3，收到：{level}",
        )

    _topic_versions = {
        "entity": "1.1",
        "document": "2.2",
        "bundle": "1.1",
        "task": "2.0",
        "capture": "1.1",
        "sync": "1.0",
        "remediation": "1.0",
    }
    content = GOVERNANCE_RULES[normalized_topic][level]
    content_hash = _content_hash(content)
    content_version = _content_version()
    if since_hash and since_hash == content_hash:
        return _unified_response(
            data={
                "topic": normalized_topic,
                "level": level,
                "version": _topic_versions.get(normalized_topic, "1.0"),
                "content_version": content_version,
                "content_hash": content_hash,
                "unchanged": True,
            }
        )
    return _unified_response(
        data={
            "topic": normalized_topic,
            "level": level,
            "version": _topic_versions.get(normalized_topic, "1.0"),
            "content": content,
            "content_version": content_version,
            "content_hash": content_hash,
        }
    )


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
    from zenos.interface.mcp import _ensure_services
    import zenos.interface.mcp as _mcp

    await _ensure_services()
    result = await _mcp.ontology_service.find_gaps(gap_type, scope_product)
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
    from zenos.interface.mcp import _ensure_services
    import zenos.interface.mcp as _mcp

    await _ensure_services()
    try:
        result = await _mcp.ontology_service.find_common_neighbors(entity_a, entity_b)
    except ValueError as e:
        return _unified_response(
            status="rejected", data={}, rejection_reason=str(e)
        )
    return _unified_response(data=result)
