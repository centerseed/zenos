"""Pure-function validation utilities for distributed governance Phase 0.5."""

from __future__ import annotations

from zenos.domain.governance import _jaccard_similarity

_TITLE_STOPWORDS = {"the", "this", "that", "task", "item", "a", "an", "我的", "這個", "那個", "任務"}


def find_similar_items(
    name: str,
    existing_items: list[dict],
    threshold: float = 0.4,
    limit: int = 3,
) -> list[dict]:
    if not name or not existing_items:
        return []
    scored = [
        {"id": item["id"], "name": item["name"], "similarity_score": _jaccard_similarity(name, item["name"])}
        for item in existing_items
    ]
    filtered = [s for s in scored if s["similarity_score"] >= threshold]
    filtered.sort(key=lambda x: x["similarity_score"], reverse=True)
    return filtered[:limit]


def validate_task_title(title: str) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    if len(title) < 4:
        errors.append("任務標題過短（最少 4 字元）")
    else:
        words = title.split()
        first_word = words[0] if words else ""
        matched_stopword = None
        if first_word.lower() in _TITLE_STOPWORDS:
            matched_stopword = first_word
        else:
            for sw in _TITLE_STOPWORDS:
                if title.startswith(sw):
                    matched_stopword = sw
                    break
        if matched_stopword:
            errors.append(f"任務標題不應以停用詞開頭：「{matched_stopword}」")
        if len(title) < 10:
            warnings.append("任務標題偏短，建議補充更多描述（建議 10 字元以上）")
    return errors, warnings


def validate_task_linked_entities(
    entity_ids: list[str],
    valid_ids: set[str],
) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    invalid = [eid for eid in entity_ids if eid not in valid_ids]
    if invalid:
        errors.append(f"以下 entity 不存在：{', '.join(invalid)}")
    if not entity_ids:
        warnings.append("任務未連結任何 entity")
    return errors, warnings


def validate_task_confirm(
    task_status: str,
    has_result: bool,
) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    if task_status == "review" and not has_result:
        errors.append("review 狀態的任務必須有 result 才能 confirm")
    return errors, warnings


def validate_document_frontmatter(data: dict) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    title = data.get("title") or data.get("name", "")
    if not title or len(title.strip()) < 3:
        errors.append("Document title 必須至少 3 個字元")
    linked = data.get("linked_entity_ids") or data.get("parent_id")
    if not linked:
        warnings.append("Document 未關聯任何 entity，建議指定 parent_id 或 linked_entity_ids")
    return errors, warnings
