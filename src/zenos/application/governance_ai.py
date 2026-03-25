"""GovernanceAI — LLM-based automatic inference for the write path.

Provides three core functions:
  - _rule_classify: pure-rule entity classification (no LLM)
  - infer_all: unified LLM call for type/parent/duplicate/rels/docs
  - infer_task_links: infer entity links for new tasks

All LLM calls are wrapped in try/except so failures never block writes.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import datetime
from typing import Any

from pydantic import BaseModel
from zenos.infrastructure.context import current_partner_id
from zenos.infrastructure.firestore_repo import get_db

logger = logging.getLogger(__name__)


def _audit_governance(event_type: str, payload: dict[str, Any]) -> None:
    """Emit structured governance inference audit logs."""
    body = {
        "event_type": event_type,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "partner_id": "",
        "actor": {"id": "", "name": "governance_ai", "email": ""},
        "target": {"component": "GovernanceAI"},
        "changes": {},
        "governance": payload,
    }
    logger.info("AUDIT_LOG %s", json.dumps(body, ensure_ascii=False, default=str))


# ──────────────────────────────────────────────
# Response schemas (Pydantic)
# ──────────────────────────────────────────────


class InferredRel(BaseModel):
    target: str  # entity ID
    type: str  # depends_on | related_to | part_of | serves | impacts | enables
    description: str = ""  # for impacts, must describe change propagation path


class GovernanceInference(BaseModel):
    type: str | None = None
    parent_id: str | None = None
    duplicate_of: str | None = None
    rels: list[InferredRel] = []
    doc_links: list[str] = []  # document entity IDs to link via relationships
    impacts_context_status: str | None = None  # ok | insufficient
    impacts_context_gaps: list[str] = []


class TaskLinkInference(BaseModel):
    entity_ids: list[str] = []


# ──────────────────────────────────────────────
# Service
# ──────────────────────────────────────────────


class GovernanceAI:
    """LLM-based governance inference for the ZenOS write path."""

    def __init__(self, llm_client: Any) -> None:
        self._llm = llm_client

    @staticmethod
    def _compact_text(value: Any, limit: int = 180) -> str:
        text = str(value or "").strip().replace("\n", " ")
        if len(text) <= limit:
            return text
        return text[: limit - 1].rstrip() + "…"

    def _format_entity_context(self, entities: list[dict], limit: int = 30) -> str:
        """Build compact yet semantically rich context for infer_all."""
        lines: list[str] = []
        for e in entities[:limit]:
            tags = e.get("tags") if isinstance(e.get("tags"), dict) else {}
            what = tags.get("what", [])
            who = tags.get("who", [])
            if isinstance(what, str):
                what = [what]
            if isinstance(who, str):
                who = [who]
            what_txt = ", ".join(self._compact_text(w, 24) for w in what[:3] if w)
            who_txt = ", ".join(self._compact_text(w, 24) for w in who[:3] if w)
            docs = e.get("doc_hints", []) if isinstance(e.get("doc_hints"), list) else []
            impacts_to = e.get("impacts_to", []) if isinstance(e.get("impacts_to"), list) else []
            impacted_by = e.get("impacted_by", []) if isinstance(e.get("impacted_by"), list) else []
            doc_txt = "; ".join(self._compact_text(d, 80) for d in docs[:2])
            impacts_to_txt = "; ".join(self._compact_text(d, 80) for d in impacts_to[:2])
            impacted_by_txt = "; ".join(self._compact_text(d, 80) for d in impacted_by[:2])

            lines.append(
                "|".join(
                    [
                        self._compact_text(e.get("id"), 32),
                        self._compact_text(e.get("name"), 48),
                        self._compact_text(e.get("type"), 16),
                        self._compact_text(e.get("summary"), 140),
                        self._compact_text(what_txt, 80),
                        self._compact_text(who_txt, 60),
                        self._compact_text(doc_txt, 170),
                        self._compact_text(impacts_to_txt, 170),
                        self._compact_text(impacted_by_txt, 170),
                    ]
                )
            )
        return "\n".join(lines)

    def _format_doc_context(self, docs: list[dict], limit: int = 20) -> str:
        lines: list[str] = []
        for d in docs[:limit]:
            lines.append(
                "|".join(
                    [
                        self._compact_text(d.get("id"), 32),
                        self._compact_text(d.get("title"), 60),
                        self._compact_text(d.get("summary"), 180),
                        self._compact_text(d.get("source_uri"), 120),
                    ]
                )
            )
        return "\n".join(lines)

    def _format_global_context(self, global_context: dict[str, Any] | None) -> str:
        """Render deterministic panorama hints for global-first inference."""
        if not isinstance(global_context, dict):
            return ""

        lines: list[str] = []
        entity_counts = global_context.get("entity_counts")
        if isinstance(entity_counts, dict) and entity_counts:
            counts_txt = ", ".join(
                f"{k}={v}" for k, v in sorted(entity_counts.items()) if isinstance(v, int)
            )
            if counts_txt:
                lines.append(f"- entity_counts: {counts_txt}")

        document_count = global_context.get("document_count")
        if isinstance(document_count, int):
            lines.append(f"- document_count: {document_count}")

        recurring_terms = global_context.get("recurring_terms")
        if isinstance(recurring_terms, list) and recurring_terms:
            terms_txt = ", ".join(str(t) for t in recurring_terms[:8] if t)
            if terms_txt:
                lines.append(f"- recurring_terms: {terms_txt}")

        product_lines = global_context.get("active_products")
        if isinstance(product_lines, list) and product_lines:
            compact_products = [
                self._compact_text(str(item), 120)
                for item in product_lines[:4]
                if item
            ]
            if compact_products:
                lines.append("- active_products:")
                lines.extend(f"  {item}" for item in compact_products)

        module_lines = global_context.get("active_modules")
        if isinstance(module_lines, list) and module_lines:
            compact_modules = [
                self._compact_text(str(item), 120)
                for item in module_lines[:6]
                if item
            ]
            if compact_modules:
                lines.append("- active_modules:")
                lines.extend(f"  {item}" for item in compact_modules)

        impact_targets = global_context.get("impact_target_hints")
        if isinstance(impact_targets, list) and impact_targets:
            compact_targets = [
                self._compact_text(str(item), 120)
                for item in impact_targets[:6]
                if item
            ]
            if compact_targets:
                lines.append("- impact_target_hints:")
                lines.extend(f"  {item}" for item in compact_targets)

        return "\n".join(lines)

    async def _write_usage_log(self, payload: dict[str, Any]) -> None:
        """Persist LLM usage metadata to partner-scoped Firestore."""
        partner_id = current_partner_id.get()
        if not partner_id:
            return
        try:
            db = get_db()
            await db.collection("partners").document(partner_id).collection("usage_logs").add(payload)
        except Exception:
            logger.warning("GovernanceAI usage logging failed", exc_info=True)

    def _schedule_usage_log(self, feature: str) -> None:
        """Schedule usage logging without blocking the caller path."""
        if hasattr(self._llm, "consume_last_usage"):
            usage = self._llm.consume_last_usage()
        else:
            usage = getattr(self._llm, "last_usage", None)
        if not usage:
            return
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return

        payload = {
            "timestamp": datetime.utcnow(),
            "feature": feature,
            "model": str(usage.get("model", getattr(self._llm, "model", ""))),
            "tokens_in": int(usage.get("tokens_in", 0)),
            "tokens_out": int(usage.get("tokens_out", 0)),
            "partner_id": current_partner_id.get(),
        }
        loop.create_task(self._write_usage_log(payload))

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

        # Build compact context tables (token-aware, semantically rich).
        entity_lines = self._format_entity_context(existing_entities)

        doc_lines = self._format_doc_context(unlinked_docs)

        entity_name = entity_data.get("name", "")
        entity_summary = entity_data.get("summary", "")
        entity_tags = entity_data.get("tags", {})
        entity_tags_txt = json.dumps(entity_tags, ensure_ascii=False) if entity_tags else "{}"
        global_context = entity_data.get("_global_context")

        user_parts = [
            f"新實體：{entity_name}",
            f"新實體摘要：{self._compact_text(entity_summary, 240)}",
            f"新實體 tags：{self._compact_text(entity_tags_txt, 240)}",
        ]
        global_lines = self._format_global_context(global_context)
        if global_lines:
            user_parts.append(
                "全局統合 context（先用這些資訊建立全景，再判斷新實體，不可逐檔直接下結論）：\n"
                f"{global_lines}"
            )
        if entity_lines:
            user_parts.append(
                "現有實體（欄位：id|name|type|summary|tags.what|tags.who|doc_hints|impacts_to|impacted_by）：\n"
                f"{entity_lines}"
            )
        if doc_lines:
            user_parts.append(
                "待連結文件（欄位：id|title|summary|source_uri）：\n"
                f"{doc_lines}"
            )

        messages = [
            {
                "role": "system",
                "content": (
                    "你是 ontology 治理 AI。你的任務不是逐檔摘要，而是先做全局統合，再判斷新實體是否屬於公司共識概念，並推斷它的關聯與文件連結。"
                    "當候選是 L2/module 時，必須用以下內部流程思考："
                    "Step 1 建立全景理解（整體產品、跨文件重複主題、現有概念邊界）；"
                    "Step 2 套用三問篩選閘（公司共識、改了有下游 impacts、跨時間存活）；"
                    "Step 3 若通過，再用可獨立改變原則切粒度；"
                    "Step 4 推斷具體 impacts 傳播路徑。"
                    "如果說不出具體 impacts，代表它不夠格當 L2，寧可不輸出 impacts 也不要硬湊。"
                    "優先輸出 impacts 關聯，且 impacts 的 description 必須具體。回傳 JSON：\n"
                    "- type: null（caller 已指定時）或 \"product\"/\"module\"\n"
                    "- parent_id: module 的 parent product ID\n"
                    "- duplicate_of: 完全相同概念的 entity ID。嚴格標準：只有名稱不同但描述同一件事才算重複。"
                    "不同平台的實作（如 Android X 和 iOS X）絕對不是重複，它們是 related_to 關係。\n"
                    "- rels: [{\"target\":\"id\",\"type\":\"impacts|depends_on|related_to|part_of|serves|enables\","
                    "\"description\":\"A 改了什麼→B 的什麼要跟著看\"}]\n"
                    "- doc_links: [\"doc-id\"]\n"
                    "- impacts_context_status: \"ok\" | \"insufficient\"\n"
                    "- impacts_context_gaps: [\"缺哪種資訊，無法推斷具體 impacts\"]\n"
                    "規則：\n"
                    "1) 不確定就不填。duplicate_of 寧可漏判也不要誤判。\n"
                    "2) 若 type=impacts，description 必須包含「→」或「->」，且左右都要有具體內容。\n"
                    "3) 若不是 impacts，也要提供簡短 description。\n"
                    "4) 若上下文不足以推斷具體 impacts，必須回傳 impacts_context_status='insufficient'，"
                    "並在 impacts_context_gaps 指出缺失（例如缺少候選下游、缺少實體摘要、缺少文件脈絡）。\n"
                    "5) summary/description 的語言必須跨角色可讀，避免只用工程術語。\n"
                    "6) 回覆要控制 token：只輸出高價值 rels，不要湊數。"
                ),
            },
            {
                "role": "user",
                "content": "\n".join(user_parts),
            },
        ]

        try:
            result = self._llm.chat_structured(
                messages=messages,
                response_schema=GovernanceInference,
                temperature=0.1,
            )
            self._schedule_usage_log("governance.infer_all")
            _audit_governance(
                "governance.infer_all",
                {
                    "model": getattr(self._llm, "model", ""),
                    "entity_name": entity_name,
                    "candidate_entities_count": len(existing_entities),
                    "unlinked_docs_count": len(unlinked_docs),
                    "result": result.model_dump() if hasattr(result, "model_dump") else {},
                },
            )
            return result
        except Exception:
            _audit_governance(
                "governance.infer_all.error",
                {
                    "model": getattr(self._llm, "model", ""),
                    "entity_name": entity_name,
                },
            )
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
            self._schedule_usage_log("governance.infer_doc_entities")
            _audit_governance(
                "governance.infer_doc_entities",
                {
                    "model": getattr(self._llm, "model", ""),
                    "doc_title": doc_title,
                    "candidate_entities_count": len(existing_entities),
                    "result_entity_ids": result.entity_ids,
                },
            )
            return result.entity_ids
        except Exception:
            _audit_governance(
                "governance.infer_doc_entities.error",
                {
                    "model": getattr(self._llm, "model", ""),
                    "doc_title": doc_title,
                },
            )
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
            self._schedule_usage_log("governance.infer_task_links")
            _audit_governance(
                "governance.infer_task_links",
                {
                    "model": getattr(self._llm, "model", ""),
                    "task_title": title,
                    "candidate_entities_count": len(existing_entities),
                    "result_entity_ids": result.entity_ids,
                },
            )
            return result.entity_ids
        except Exception:
            _audit_governance(
                "governance.infer_task_links.error",
                {
                    "model": getattr(self._llm, "model", ""),
                    "task_title": title,
                },
            )
            logger.warning("GovernanceAI.infer_task_links failed", exc_info=True)
            return []
