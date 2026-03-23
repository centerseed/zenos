"""GovernanceAI — LLM-based automatic inference for the write path.

Provides three core functions:
  - _rule_classify: pure-rule entity classification (no LLM)
  - infer_all: unified LLM call for type/parent/duplicate/rels/docs
  - infer_task_links: infer entity links for new tasks

All LLM calls are wrapped in try/except so failures never block writes.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from pydantic import BaseModel

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# Response schemas (Pydantic)
# ──────────────────────────────────────────────


class InferredRel(BaseModel):
    target: str  # entity ID
    type: str  # depends_on | related_to | part_of | serves


class GovernanceInference(BaseModel):
    type: str | None = None
    parent_id: str | None = None
    duplicate_of: str | None = None
    rels: list[InferredRel] = []
    doc_links: list[str] = []  # document entity IDs to link via relationships


class TaskLinkInference(BaseModel):
    entity_ids: list[str] = []


# ──────────────────────────────────────────────
# Service
# ──────────────────────────────────────────────


class GovernanceAI:
    """LLM-based governance inference for the ZenOS write path."""

    def __init__(self, llm_client: Any) -> None:
        self._llm = llm_client

    # ──────────────────────────────────────────
    # A. _rule_classify (pure rules, no LLM)
    # ──────────────────────────────────────────

    def _rule_classify(
        self,
        name: str,
        existing_entities: list[dict],
    ) -> tuple[str | None, str | None]:
        """Determine entity type and parent using simple rules.

        Rules:
        - Name starts with "Android ", "iOS ", "Web " → type="module"
        - Parent: if exactly one product exists → that's the parent

        Returns (type, parent_id). Either or both may be None.
        """
        inferred_type: str | None = None
        inferred_parent: str | None = None

        # Platform prefix → module
        prefixes = ("Android ", "iOS ", "Web ")
        if any(name.startswith(p) for p in prefixes):
            inferred_type = "module"

        # Find parent: single product → auto-assign
        if inferred_type == "module":
            products = [
                e for e in existing_entities
                if e.get("type") == "product"
            ]
            if len(products) == 1:
                inferred_parent = products[0].get("id")

        return (inferred_type, inferred_parent)

    # ──────────────────────────────────────────
    # B. infer_all (one LLM call)
    # ──────────────────────────────────────────

    def infer_all(
        self,
        entity_data: dict,
        existing_entities: list[dict],
        unlinked_docs: list[dict],
    ) -> GovernanceInference | None:
        """Unified LLM inference: type, parent, duplicate, rels, doc links.

        Returns None on LLM failure (non-blocking).
        """
        if not existing_entities and not unlinked_docs:
            return None

        # Build compact entity table (pipe-separated)
        entity_lines = "\n".join(
            f"{e.get('id')}|{e.get('name')}|{e.get('type')}"
            for e in existing_entities
        )

        # Build compact doc table
        doc_lines = "\n".join(
            f"{d.get('id')}|{d.get('title')}"
            for d in unlinked_docs
        )

        entity_name = entity_data.get("name", "")
        entity_summary = entity_data.get("summary", "")

        user_parts = [f"新實體：{entity_name} - {entity_summary}"]
        if entity_lines:
            user_parts.append(f"現有實體：\n{entity_lines}")
        if doc_lines:
            user_parts.append(f"待連結文件：\n{doc_lines}")

        messages = [
            {
                "role": "system",
                "content": (
                    "你是 ontology 治理 AI。判斷新實體的關聯和文件連結。回傳 JSON：\n"
                    "- type: null（caller 已指定時）或 \"product\"/\"module\"\n"
                    "- parent_id: module 的 parent product ID\n"
                    "- duplicate_of: 完全相同概念的 entity ID。嚴格標準：只有名稱不同但描述同一件事才算重複。"
                    "不同平台的實作（如 Android X 和 iOS X）絕對不是重複，它們是 related_to 關係。\n"
                    "- rels: [{\"target\":\"id\",\"type\":\"depends_on|related_to|part_of\"}]\n"
                    "- doc_links: [\"doc-id\"]\n"
                    "不確定就不填。duplicate_of 寧可漏判也不要誤判。"
                ),
            },
            {
                "role": "user",
                "content": "\n".join(user_parts),
            },
        ]

        try:
            return self._llm.chat_structured(
                messages=messages,
                response_schema=GovernanceInference,
                temperature=0.1,
            )
        except Exception:
            logger.warning("GovernanceAI.infer_all failed", exc_info=True)
            return None

    # ──────────────────────────────────────────
    # C. infer_doc_entities (one LLM call)
    # ──────────────────────────────────────────

    def infer_doc_entities(
        self,
        doc_title: str,
        doc_summary: str,
        existing_entities: list[dict],
    ) -> list[str]:
        """Infer which entities a document belongs to.

        Returns list of entity IDs. Returns empty list on LLM failure.
        """
        if not existing_entities:
            return []

        entity_lines = "\n".join(
            f"{e.get('id')}|{e.get('name')}|{e.get('type')}"
            for e in existing_entities
        )

        messages = [
            {
                "role": "system",
                "content": (
                    "判斷文件與哪些實體相關。回傳 JSON：{\"entity_ids\": [\"id1\", \"id2\"]}"
                ),
            },
            {
                "role": "user",
                "content": (
                    f"文件：{doc_title} - {doc_summary}\n"
                    f"實體：\n{entity_lines}"
                ),
            },
        ]

        try:
            result = self._llm.chat_structured(
                messages=messages,
                response_schema=TaskLinkInference,
                temperature=0.1,
            )
            return result.entity_ids
        except Exception:
            logger.warning("GovernanceAI.infer_doc_entities failed", exc_info=True)
            return []

    # ──────────────────────────────────────────
    # D. infer_task_links (one LLM call)
    # ──────────────────────────────────────────

    def infer_task_links(
        self,
        title: str,
        description: str,
        existing_entities: list[dict],
    ) -> list[str]:
        """Infer which entities a new task relates to.

        Returns list of entity IDs. Returns empty list on LLM failure.
        """
        if not existing_entities:
            return []

        entity_lines = "\n".join(
            f"{e.get('id')}|{e.get('name')}|{e.get('type')}"
            for e in existing_entities
        )

        messages = [
            {
                "role": "system",
                "content": (
                    "判斷任務與哪些實體相關。回傳 JSON：{\"entity_ids\": [\"id1\", \"id2\"]}"
                ),
            },
            {
                "role": "user",
                "content": (
                    f"任務：{title} - {description}\n"
                    f"實體：\n{entity_lines}"
                ),
            },
        ]

        try:
            result = self._llm.chat_structured(
                messages=messages,
                response_schema=TaskLinkInference,
                temperature=0.1,
            )
            return result.entity_ids
        except Exception:
            logger.warning("GovernanceAI.infer_task_links failed", exc_info=True)
            return []
