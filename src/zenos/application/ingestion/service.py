"""Application service for external ingestion facade."""

from __future__ import annotations

from datetime import datetime
from typing import Awaitable, Callable

from .repository import IngestionRepository

TaskAdapter = Callable[[str, dict], Awaitable[dict]]
EntryAdapter = Callable[[str, dict], Awaitable[dict]]

INGEST_EVENT_TYPES = {"task_input", "idea_input", "reflection_input"}
INGEST_INTENTS = {"todo", "explore", "decide", "reflect"}
ENTRY_TYPES = {"decision", "insight", "limitation", "change", "context"}
FORBIDDEN_MUTATION_KEYS = {"entities", "relationships", "documents", "protocols", "blindspots"}

TASK_FIELD_WHITELIST = {
    "title",
    "description",
    "acceptance_criteria",
    "linked_entities",
    "priority",
    "assignee",
    "assignee_role_id",
    "plan_id",
    "plan_order",
    "due_date",
    "source_metadata",
}
ENTRY_FIELD_WHITELIST = {"entity_id", "type", "content", "context"}


class IngestionService:
    """Coordinates signal ingest, distill, commit, and review queue."""

    def __init__(self, repo: IngestionRepository) -> None:
        self._repo = repo

    @staticmethod
    def parse_iso8601(value: str) -> datetime | None:
        if not isinstance(value, str) or not value:
            return None
        try:
            if value.endswith("Z"):
                return datetime.fromisoformat(value[:-1] + "+00:00")
            return datetime.fromisoformat(value)
        except Exception:
            return None

    async def ingest(self, payload: dict) -> tuple[str, bool]:
        return await self._repo.ingest_signal(payload)

    async def distill(
        self,
        *,
        workspace_id: str,
        product_id: str,
        window_from: datetime,
        window_to: datetime,
        max_items: int,
    ) -> dict:
        signals = await self._repo.list_signals_in_window(
            workspace_id=workspace_id,
            product_id=product_id,
            window_from=window_from,
            window_to=window_to,
            max_items=max_items,
        )
        task_candidates: list[dict] = []
        entry_candidates: list[dict] = []
        dropped_signals: list[dict] = []

        for signal in signals:
            if signal["event_type"] == "task_input" or signal["intent"] == "todo":
                task_candidates.append(
                    {
                        "external_signal_id": signal["external_signal_id"],
                        "title": signal["summary"][:120] or "Untitled task candidate",
                        "description": signal["summary"],
                        "reason": "task-like signal",
                        "confidence": signal["confidence"],
                    }
                )
            elif signal["event_type"] in {"idea_input", "reflection_input"}:
                entry_type = "insight" if signal["event_type"] == "idea_input" else "context"
                entry_candidates.append(
                    {
                        "external_signal_id": signal["external_signal_id"],
                        "entity_id": None,
                        "type": entry_type,
                        "content": signal["summary"],
                        "reason": "knowledge-like signal",
                        "confidence": signal["confidence"],
                    }
                )
            else:
                dropped_signals.append(
                    {
                        "external_signal_id": signal["external_signal_id"],
                        "reason": "unsupported signal type",
                    }
                )

        batch_id = await self._repo.create_batch(
            workspace_id=workspace_id,
            product_id=product_id,
            window_from=window_from,
            window_to=window_to,
        )
        stored_tasks = await self._repo.save_candidates(
            batch_id=batch_id,
            candidate_type="task",
            candidates=task_candidates,
        )
        stored_entries = await self._repo.save_candidates(
            batch_id=batch_id,
            candidate_type="entry",
            candidates=entry_candidates,
        )
        return {
            "batch_id": batch_id,
            "task_candidates": stored_tasks,
            "entry_candidates": stored_entries,
            "l2_update_candidates": [],
            "dropped_signals": dropped_signals,
        }

    async def commit(
        self,
        *,
        workspace_id: str,
        product_id: str,
        batch_id: str,
        task_candidates: list[dict],
        entry_candidates: list[dict],
        l2_update_candidates: list[dict],
        task_adapter: TaskAdapter,
        entry_adapter: EntryAdapter,
        atomic: bool = False,
    ) -> dict:
        committed: list[dict] = []
        queued_for_review: list[dict] = []
        (
            validated_task_payloads,
            validated_entry_payloads,
            rejected,
            warnings,
        ) = self.validate_candidates(
            task_candidates=task_candidates,
            entry_candidates=entry_candidates,
        )

        if atomic and rejected:
            return {
                "committed": [],
                "rejected": rejected,
                "queued_for_review": [],
                "warnings": warnings + ["atomic=true: commit skipped because validation failed"],
            }

        for idx, payload in validated_task_payloads:
            result = await task_adapter(workspace_id, payload)
            if result.get("status") not in {"ok", "partial"}:
                rejected.append(
                    {
                        "index": idx,
                        "type": "task",
                        "reason": result.get("rejection_reason") or "task adapter rejected candidate",
                        "adapter_result": result,
                    }
                )
                if atomic:
                    break
                continue
            committed.append(
                {
                    "candidate_type": "task",
                    "candidate_index": idx,
                    "status": "committed",
                    "target": result.get("data", {}),
                }
            )

        if not (atomic and any(r["type"] == "task" for r in rejected)):
            for idx, payload in validated_entry_payloads:
                result = await entry_adapter(workspace_id, payload)
                if result.get("status") not in {"ok", "partial"}:
                    rejected.append(
                        {
                            "index": idx,
                            "type": "entry",
                            "reason": result.get("rejection_reason") or "entry adapter rejected candidate",
                            "adapter_result": result,
                        }
                    )
                    if atomic:
                        break
                    continue
                committed.append(
                    {
                        "candidate_type": "entry",
                        "candidate_index": idx,
                        "status": "committed",
                        "target": result.get("data", {}),
                    }
                )

        review_items = [
            {
                "review_type": "l2_update",
                "candidate": c,
                "candidate_id": c.get("id") if isinstance(c, dict) else None,
                "note": "l2_update_candidate must go through review queue",
            }
            for c in l2_update_candidates
        ]
        if review_items:
            queued_for_review = await self._repo.enqueue_review_items(
                workspace_id=workspace_id,
                product_id=product_id,
                batch_id=batch_id,
                items=review_items,
            )

        return {
            "committed": committed,
            "rejected": rejected,
            "queued_for_review": queued_for_review,
            "warnings": warnings,
        }

    def validate_candidates(
        self,
        *,
        task_candidates: list[dict],
        entry_candidates: list[dict],
    ) -> tuple[list[tuple[int, dict]], list[tuple[int, dict]], list[dict], list[str]]:
        """Validate/sanitize candidates before commit.

        Returns:
            validated_task_payloads, validated_entry_payloads, rejected, warnings
        """
        validated_task_payloads: list[tuple[int, dict]] = []
        validated_entry_payloads: list[tuple[int, dict]] = []
        rejected: list[dict] = []
        warnings: list[str] = []

        for idx, candidate in enumerate(task_candidates):
            if not isinstance(candidate, dict):
                rejected.append({"index": idx, "type": "task", "reason": "candidate must be object"})
                continue
            if candidate.get("collection") and str(candidate.get("collection")) not in {"task", "tasks"}:
                rejected.append({"index": idx, "type": "task", "reason": "forbidden mutation target"})
                continue
            if any(key in candidate for key in FORBIDDEN_MUTATION_KEYS):
                rejected.append({"index": idx, "type": "task", "reason": "forbidden mutation payload"})
                continue
            unknown_fields = sorted(set(candidate.keys()) - TASK_FIELD_WHITELIST - {"reason", "confidence", "id", "payload", "candidate_type"})
            if unknown_fields:
                warnings.append(f"task_candidate[{idx}] ignored unknown fields: {unknown_fields}")
            source = candidate.get("payload") if isinstance(candidate.get("payload"), dict) else candidate
            sanitized = {k: v for k, v in source.items() if k in TASK_FIELD_WHITELIST}
            if not sanitized.get("title"):
                rejected.append({"index": idx, "type": "task", "reason": "title is required"})
                continue
            validated_task_payloads.append((idx, sanitized))

        for idx, candidate in enumerate(entry_candidates):
            if not isinstance(candidate, dict):
                rejected.append({"index": idx, "type": "entry", "reason": "candidate must be object"})
                continue
            if candidate.get("collection") and str(candidate.get("collection")) not in {"entry", "entries"}:
                rejected.append({"index": idx, "type": "entry", "reason": "forbidden mutation target"})
                continue
            if any(key in candidate for key in FORBIDDEN_MUTATION_KEYS):
                rejected.append({"index": idx, "type": "entry", "reason": "forbidden mutation payload"})
                continue
            unknown_fields = sorted(set(candidate.keys()) - ENTRY_FIELD_WHITELIST - {"reason", "confidence", "id", "payload", "candidate_type"})
            if unknown_fields:
                warnings.append(f"entry_candidate[{idx}] ignored unknown fields: {unknown_fields}")
            source = candidate.get("payload") if isinstance(candidate.get("payload"), dict) else candidate
            sanitized = {k: v for k, v in source.items() if k in ENTRY_FIELD_WHITELIST}
            if not sanitized.get("entity_id") or not sanitized.get("content"):
                rejected.append({"index": idx, "type": "entry", "reason": "entity_id and content are required"})
                continue
            if sanitized.get("type") not in ENTRY_TYPES:
                rejected.append({"index": idx, "type": "entry", "reason": "invalid entry type"})
                continue
            # Align atomic and non-atomic behavior with write(collection="entries")
            # governance guards: content length (1-200) and context length (<=200).
            content = sanitized.get("content")
            if not isinstance(content, str):
                rejected.append({"index": idx, "type": "entry", "reason": "content must be a string"})
                continue
            if not (1 <= len(content) <= 200):
                rejected.append({"index": idx, "type": "entry", "reason": "content must be 1-200 chars"})
                continue

            context = sanitized.get("context")
            if context is not None:
                if not isinstance(context, str):
                    rejected.append({"index": idx, "type": "entry", "reason": "context must be a string"})
                    continue
                if len(context) > 200:
                    rejected.append({"index": idx, "type": "entry", "reason": "context must be <= 200 chars"})
                    continue
            validated_entry_payloads.append((idx, sanitized))

        return validated_task_payloads, validated_entry_payloads, rejected, warnings

    async def review_queue(
        self,
        *,
        workspace_id: str,
        product_id: str,
        status: str | None,
        limit: int,
        offset: int,
    ) -> tuple[list[dict], int]:
        return await self._repo.list_review_queue(
            workspace_id=workspace_id,
            product_id=product_id,
            status=status,
            limit=limit,
            offset=offset,
        )
