"""Repository interfaces and in-memory implementation for ingestion flow."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Protocol
import uuid


class IngestionRepository(Protocol):
    """Persistence contract for external ingestion flow."""

    async def ingest_signal(self, payload: dict) -> tuple[str, bool]:
        """Store raw signal. Returns (signal_id, idempotent_replay)."""
        ...

    async def list_signals_in_window(
        self,
        *,
        workspace_id: str,
        product_id: str,
        window_from: datetime,
        window_to: datetime,
        max_items: int,
    ) -> list[dict]:
        ...

    async def create_batch(
        self,
        *,
        workspace_id: str,
        product_id: str,
        window_from: datetime,
        window_to: datetime,
    ) -> str:
        ...

    async def save_candidates(
        self,
        *,
        batch_id: str,
        candidate_type: str,
        candidates: list[dict],
    ) -> list[dict]:
        """Persist candidates and return canonical candidate records."""
        ...

    async def enqueue_review_items(
        self,
        *,
        workspace_id: str,
        product_id: str,
        batch_id: str,
        items: list[dict],
        conn: Any | None = None,
    ) -> list[dict]:
        ...

    async def list_review_queue(
        self,
        *,
        workspace_id: str,
        product_id: str,
        status: str | None,
        limit: int,
        offset: int,
    ) -> tuple[list[dict], int]:
        ...


class InMemoryIngestionRepository:
    """In-memory repository for local runs and tests."""

    def __init__(self) -> None:
        self._signals: dict[str, dict] = {}
        self._signal_idem_index: dict[tuple[str, str], str] = {}
        self._batches: dict[str, dict] = {}
        self._candidates: dict[str, dict] = {}
        self._review_queue: list[dict] = []

    @staticmethod
    def _new_id() -> str:
        return uuid.uuid4().hex

    async def ingest_signal(self, payload: dict) -> tuple[str, bool]:
        workspace_id = str(payload["workspace_id"])
        external_signal_id = str(payload["external_signal_id"])
        idem_key = (workspace_id, external_signal_id)
        existing_signal_id = self._signal_idem_index.get(idem_key)
        if existing_signal_id:
            return existing_signal_id, True

        signal_id = self._new_id()
        self._signal_idem_index[idem_key] = signal_id
        self._signals[signal_id] = {
            "id": signal_id,
            **payload,
        }
        return signal_id, False

    async def list_signals_in_window(
        self,
        *,
        workspace_id: str,
        product_id: str,
        window_from: datetime,
        window_to: datetime,
        max_items: int,
    ) -> list[dict]:
        return [
            s for s in self._signals.values()
            if s["workspace_id"] == workspace_id
            and s["product_id"] == product_id
            and window_from <= s["occurred_at"] <= window_to
        ][:max_items]

    async def create_batch(
        self,
        *,
        workspace_id: str,
        product_id: str,
        window_from: datetime,
        window_to: datetime,
    ) -> str:
        batch_id = self._new_id()
        self._batches[batch_id] = {
            "id": batch_id,
            "workspace_id": workspace_id,
            "product_id": product_id,
            "window_from": window_from,
            "window_to": window_to,
            "created_at": datetime.now(timezone.utc),
        }
        return batch_id

    async def save_candidates(
        self,
        *,
        batch_id: str,
        candidate_type: str,
        candidates: list[dict],
    ) -> list[dict]:
        stored: list[dict] = []
        for c in candidates:
            cid = self._new_id()
            record = {
                "id": cid,
                "batch_id": batch_id,
                "candidate_type": candidate_type,
                "status": "draft",
                "payload": dict(c),
                "reason": str(c.get("reason") or ""),
                "confidence": float(c.get("confidence") or 0.0),
                "created_at": datetime.now(timezone.utc),
            }
            self._candidates[cid] = record
            stored.append(record)
        return stored

    async def enqueue_review_items(
        self,
        *,
        workspace_id: str,
        product_id: str,
        batch_id: str,
        items: list[dict],
        conn: Any | None = None,
    ) -> list[dict]:
        queued: list[dict] = []
        for item in items:
            qid = self._new_id()
            record = {
                "id": qid,
                "workspace_id": workspace_id,
                "product_id": product_id,
                "batch_id": batch_id,
                "candidate_id": item.get("candidate_id"),
                "review_type": item.get("review_type", "l2_update"),
                "status": "pending",
                "note": item.get("note", ""),
                "candidate": item.get("candidate"),
                "created_at": datetime.now(timezone.utc),
            }
            self._review_queue.append(record)
            queued.append(record)
        return queued

    async def list_review_queue(
        self,
        *,
        workspace_id: str,
        product_id: str,
        status: str | None,
        limit: int,
        offset: int,
    ) -> tuple[list[dict], int]:
        items = [
            q for q in self._review_queue
            if q["workspace_id"] == workspace_id and q["product_id"] == product_id
        ]
        if status:
            items = [q for q in items if q.get("status") == status]
        total = len(items)
        return items[offset:offset + limit], total

    def reset(self) -> None:
        self._signals.clear()
        self._signal_idem_index.clear()
        self._batches.clear()
        self._candidates.clear()
        self._review_queue.clear()
