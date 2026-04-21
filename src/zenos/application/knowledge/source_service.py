"""SourceService — reads external document content via adapters and manages
helper-ingest upsert logic.

Bridges entity/document metadata with actual file content
by resolving the source URI through the appropriate adapter.

New in SPEC-docs-native-edit-and-helper-ingest (Helper Ingest Contract):
  - add_source / update_source accept external_id for upsert-by-key semantics.
  - snapshot_summary inline storage (≤10KB language-model summary, not raw mirror).
  - read_source returns staleness_hint when last_synced_at is stale.
  - Duplicate external_id across docs triggers warning (not rejection).
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from zenos.domain.knowledge import SourceType
from zenos.domain.knowledge import EntityRepository, SourceAdapter
from zenos.domain.doc_types import generate_source_id

logger = logging.getLogger(__name__)

# Number of days after which a source is considered stale
STALENESS_DAYS = 14
DEFAULT_SIDECAR_TIMEOUT_SECONDS = 10.0


def _source_status(source: dict) -> str:
    """Return the effective status for a source dict."""
    return str(source.get("source_status") or source.get("status") or "valid")


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _compute_staleness_hint(source: dict) -> dict | None:
    """Return a staleness_hint dict if the source is stale, else None.

    Stale conditions (per SPEC P0-3):
      1. last_synced_at is older than STALENESS_DAYS days.
      2. external_updated_at > last_synced_at (helper pushed an older version or
         remote updated since last sync).

    Returns None if no staleness detected or if timestamps are absent.
    """
    last_synced_raw = source.get("last_synced_at")
    external_updated_raw = source.get("external_updated_at")

    if not last_synced_raw:
        return None

    try:
        last_synced = _parse_iso(last_synced_raw)
    except (ValueError, TypeError):
        return None

    now = _now_utc()
    threshold = now - timedelta(days=STALENESS_DAYS)

    if last_synced < threshold:
        return {
            "reason": "outdated",
            "last_synced_at": last_synced.isoformat(),
            "suggested_helper_prompt": (
                "此 source 超過 14 天未同步。"
                "建議執行 helper 重新同步：用 Notion MCP / GDrive MCP 讀取最新內容，"
                "再用 ZenOS MCP write(update_source, external_id=...) 更新。"
            ),
        }

    if external_updated_raw:
        try:
            external_updated = _parse_iso(external_updated_raw)
        except (ValueError, TypeError):
            return None
        if external_updated > last_synced:
            return {
                "reason": "inverted_timestamps",
                "last_synced_at": last_synced.isoformat(),
                "external_updated_at": external_updated.isoformat(),
                "suggested_helper_prompt": (
                    "外部文件的 external_updated_at 晚於 last_synced_at，"
                    "表示 ZenOS 持有的版本可能已過期。"
                    "建議用 Notion MCP / GDrive MCP 重新同步。"
                ),
            }

    return None


def _parse_iso(ts: Any) -> datetime:
    """Parse an ISO-8601 string or datetime into an aware datetime."""
    if isinstance(ts, datetime):
        if ts.tzinfo is None:
            return ts.replace(tzinfo=timezone.utc)
        return ts
    s = str(ts).strip()
    # Try stdlib fromisoformat (Python 3.11+ handles 'Z'; earlier needs manual fix)
    s_fixed = s.replace("Z", "+00:00")
    return datetime.fromisoformat(s_fixed)


def _partner_preferences(partner: dict | None) -> dict:
    if not partner:
        return {}
    prefs = partner.get("preferences")
    return prefs if isinstance(prefs, dict) else {}


def _google_workspace_settings(
    partner: dict | None,
    override_config: dict | None = None,
) -> dict:
    base = {}
    prefs = _partner_preferences(partner)
    raw = prefs.get("googleWorkspace")
    if isinstance(raw, dict):
        base.update(raw)
    if isinstance(override_config, dict):
        for key in ("sidecar_base_url", "sidecar_token", "principal_mode"):
            if key in override_config:
                base[key] = override_config[key]
    return base


def _normalize_sidecar_base_url(value: Any) -> str:
    return str(value or "").strip().rstrip("/")


def _sidecar_headers(config: dict) -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    token = str(config.get("sidecar_token") or "").strip()
    if token:
        headers["X-Zenos-Connector-Token"] = token
    return headers


class SourceService:
    """Application-layer service for reading external document sources
    and managing helper-ingest upsert operations."""

    def __init__(
        self,
        entity_repo: EntityRepository | None = None,
        source_adapter: SourceAdapter | None = None,
        document_repo: object | None = None,  # deprecated, kept for backward compat
    ) -> None:
        self._entities = entity_repo
        self._adapter = source_adapter

    # ------------------------------------------------------------------
    # Helper Ingest: upsert_source
    # ------------------------------------------------------------------

    def upsert_source_in_sources(
        self,
        sources: list[dict],
        *,
        external_id: str,
        new_source_data: dict,
        now: datetime | None = None,
    ) -> tuple[list[dict], str, bool]:
        """Upsert a source within a sources list by external_id.

        Returns (updated_sources, source_id, was_noop).

        Logic:
          - If a source with matching external_id already exists → update it
            in-place, preserve source_id, update last_synced_at to now.
          - If no match → append a new source with a fresh source_id.
          - was_noop=True when external_updated_at and snapshot_summary are
            unchanged vs. the existing record (no real content change).
        """
        if now is None:
            now = _now_utc()

        now_iso = now.isoformat()

        # Find existing source with this external_id
        existing_idx = next(
            (i for i, s in enumerate(sources) if s.get("external_id") == external_id),
            None,
        )

        if existing_idx is not None:
            existing = sources[existing_idx]
            source_id = existing.get("source_id") or generate_source_id()

            # Detect no-op: neither external_updated_at nor snapshot_summary changed
            new_ext_updated = new_source_data.get("external_updated_at")
            new_snapshot = new_source_data.get("snapshot_summary")
            old_ext_updated = existing.get("external_updated_at")
            old_snapshot = existing.get("snapshot_summary")

            was_noop = (new_ext_updated == old_ext_updated) and (new_snapshot == old_snapshot)

            # Always update last_synced_at to now, regardless of noop
            updated = dict(existing)
            updated["last_synced_at"] = now_iso
            updated["source_id"] = source_id

            # Merge in new fields (skipping None values for optional fields)
            for key in ("uri", "label", "type", "doc_type", "doc_status", "note", "is_primary"):
                if key in new_source_data and new_source_data[key] is not None:
                    updated[key] = new_source_data[key]

            if "external_updated_at" in new_source_data:
                updated["external_updated_at"] = new_source_data["external_updated_at"]

            # snapshot_summary: allow explicit null to clear
            if "snapshot_summary" in new_source_data:
                updated["snapshot_summary"] = new_source_data["snapshot_summary"]

            sources = list(sources)
            sources[existing_idx] = updated
            return sources, source_id, was_noop

        # New source
        source_id = generate_source_id()
        new_src = {
            "source_id": source_id,
            "external_id": external_id,
            "last_synced_at": now_iso,
            "status": "valid",
            "source_status": "valid",
        }
        for key in ("uri", "label", "type", "doc_type", "doc_status", "note", "is_primary",
                    "external_updated_at", "snapshot_summary"):
            if key in new_source_data and new_source_data[key] is not None:
                new_src[key] = new_source_data[key]

        sources = list(sources) + [new_src]
        return sources, source_id, False

    def find_duplicate_external_id_across_entities(
        self,
        entities: list[Any],
        *,
        external_id: str,
        exclude_entity_id: str | None = None,
    ) -> list[str]:
        """Return entity IDs that already contain a source with the given external_id.

        Used for cross-doc duplicate detection (warning, not rejection).
        Excludes the entity with exclude_entity_id (so the caller's own doc
        doesn't trigger a false positive after its own upsert).
        """
        matches: list[str] = []
        for entity in entities:
            if entity.id == exclude_entity_id:
                continue
            for src in (entity.sources or []):
                if src.get("external_id") == external_id:
                    matches.append(entity.id)
                    break
        return matches

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    async def read_source(self, doc_id: str, *, source_uri: str | None = None) -> str:
        """Read the raw content of a document's source file.

        Steps:
          1. Retrieve the entity (type=document) from the repository by UUID.
          2. If UUID lookup fails, fall back to scanning all document entities
             and matching by source URI (for callers that pass a GitHub URI
             instead of an entity ID).
          3. Use *source_uri* if provided; otherwise extract from entity.sources[0].
          4. Delegate to the source adapter to read the content.
          5. Return the text content.

        Args:
            doc_id: Entity ID or URI string.
            source_uri: If provided, read this specific URI instead of sources[0].

        Raises:
            ValueError: if the document entity is not found.
        """
        entity = await self._entities.get_by_id(doc_id)

        if entity is None:
            all_docs = await self._entities.list_all(type_filter="document")
            entity = next(
                (
                    d
                    for d in all_docs
                    if any(
                        str(s.get("uri", "")).strip() == doc_id
                        for s in (d.sources or [])
                    )
                ),
                None,
            )

        if entity is None:
            raise ValueError(f"Document '{doc_id}' not found")

        # Use caller-provided URI or fall back to first source
        if source_uri:
            uri = source_uri
        elif entity.sources:
            uri = entity.sources[0].get("uri", "")
        else:
            raise ValueError(f"Document '{doc_id}' has no source URI")

        return await self._adapter.read_content(uri)

    async def read_source_with_recovery(self, doc_id: str, *, source_uri: str | None = None) -> dict:
        """Read source with dead link detection and source_status update.

        Args:
            doc_id: Entity ID or URI string.
            source_uri: If provided, read this specific URI instead of sources[0].

        Returns:
            {"content": str} on success
            {"error": "DEAD_LINK", "source_type": str, "source_status": str,
             "suggested_action": str, "proposed_uri": str | None} on dead link
            {"error": "NOT_FOUND", "message": str} if entity not found
            {"error": "ALREADY_UNRESOLVABLE"} if source_status already unresolvable
        """
        entity = await self._entities.get_by_id(doc_id)

        if entity is None:
            all_docs = await self._entities.list_all(type_filter="document")
            entity = next(
                (
                    d
                    for d in all_docs
                    if any(
                        str(s.get("uri", "")).strip() == doc_id
                        for s in (d.sources or [])
                    )
                ),
                None,
            )

        if entity is None:
            return {"error": "NOT_FOUND", "message": f"Document '{doc_id}' not found"}

        if not entity.sources:
            return {"error": "NOT_FOUND", "message": f"Document '{doc_id}' has no source URI"}

        # If source_uri provided, find matching source entry; otherwise use first
        if source_uri:
            source = next(
                (s for s in entity.sources if s.get("uri", "") == source_uri),
                entity.sources[0],
            )
        else:
            source = entity.sources[0]
        uri = source.get("uri", "") if not source_uri else source_uri
        source_type = source.get("type", "")
        current_status = _source_status(source)

        # Short-circuit if already unresolvable — don't call external APIs
        if current_status == "unresolvable":
            return {"error": "ALREADY_UNRESOLVABLE"}

        # Extract source_id for targeted status updates (Finding 3)
        source_id = source.get("source_id")

        try:
            content = await self._adapter.read_content(uri)
            return {"content": content}

        except FileNotFoundError:
            return await self._handle_not_found(
                entity, uri, source_type, source_id=source_id,
            )

        except PermissionError:
            await self._entities.update_source_status(
                entity.id, "stale", source_id=source_id,
            )
            return {
                "error": "DEAD_LINK",
                "source_type": source_type,
                "source_status": "stale",
                "suggested_action": "check_permission",
                "proposed_uri": None,
            }

    async def read_source_with_snapshot(
        self,
        doc_id: str,
        *,
        source_id: str | None = None,
        source_uri: str | None = None,
    ) -> dict:
        """Read source content, preferring snapshot_summary for helper-ingest sources.

        For sources with a snapshot_summary, return the summary directly without
        calling the external adapter.  For zenos_native sources, read from GCS
        via the primary_snapshot_revision_id path.

        Returns:
            {"content": str, "source_id": str, "content_type": "snapshot_summary"|"full"}
            {"error": "SNAPSHOT_UNAVAILABLE", "setup_hint": str} when no snapshot
            {"error": "NOT_FOUND", ...}
        """
        entity = await self._entities.get_by_id(doc_id)
        if entity is None:
            return {"error": "NOT_FOUND", "message": f"Document '{doc_id}' not found"}

        sources = entity.sources or []

        # Select target source
        target: dict | None = None
        if source_id:
            target = next((s for s in sources if s.get("source_id") == source_id), None)
        elif source_uri:
            target = next((s for s in sources if s.get("uri", "") == source_uri), None)
        else:
            # Primary fallback: prefer primary+valid, then any valid
            target = next(
                (s for s in sources if s.get("is_primary") and _source_status(s) == "valid"),
                None,
            )
            if target is None:
                target = next((s for s in sources if _source_status(s) == "valid"), None)
            if target is None and sources:
                target = sources[-1]

        if target is None:
            return {"error": "NOT_FOUND", "message": f"Document '{doc_id}' has no sources"}

        sid = target.get("source_id", "")
        stype = target.get("type", "")

        # Helper-ingest sources: return snapshot_summary if available
        if stype not in ("zenos_native", "github"):
            snapshot = target.get("snapshot_summary")
            if snapshot:
                staleness = _compute_staleness_hint(target)
                result: dict = {
                    "content": snapshot,
                    "source_id": sid,
                    "content_type": "snapshot_summary",
                }
                if staleness:
                    result["staleness_hint"] = staleness
                return result
            # No snapshot_summary — return unavailable with setup_hint
            return {
                "error": "SNAPSHOT_UNAVAILABLE",
                "source_id": sid,
                "setup_hint": (
                    "此 source 尚無 snapshot_summary。"
                    "建議用 Notion MCP 同步這份文件，或在 Dashboard 點重新同步。"
                ),
            }

        # zenos_native: read via adapter (GCS) — adapter handles the /docs/{id} URI
        uri = target.get("uri", "")
        if not uri and self._adapter is None:
            return {
                "error": "SNAPSHOT_UNAVAILABLE",
                "source_id": sid,
                "setup_hint": "zenos_native source 尚未有 revision。請先在 Dashboard 儲存文件。",
            }

        try:
            content = await self._adapter.read_content(uri)
            staleness = _compute_staleness_hint(target)
            result = {
                "content": content,
                "source_id": sid,
                "content_type": "full",
            }
            if staleness:
                result["staleness_hint"] = staleness
            return result
        except FileNotFoundError:
            return {
                "error": "SNAPSHOT_UNAVAILABLE",
                "source_id": sid,
                "setup_hint": "zenos_native source 尚未有 revision。請先在 Dashboard 儲存文件。",
            }

    async def check_google_workspace_connector_health(
        self,
        partner: dict | None,
        *,
        override_config: dict | None = None,
    ) -> dict:
        """Probe the internal-first Google Workspace sidecar health endpoint."""
        config = _google_workspace_settings(partner, override_config)
        base_url = _normalize_sidecar_base_url(config.get("sidecar_base_url"))
        if not base_url:
            return {
                "ok": False,
                "status": "missing_config",
                "message": "Google Workspace connector 尚未設定 sidecar URL。",
                "capability": None,
            }

        headers = _sidecar_headers(config)
        try:
            async with httpx.AsyncClient(timeout=DEFAULT_SIDECAR_TIMEOUT_SECONDS) as client:
                response = await client.get(f"{base_url}/health", headers=headers)
        except Exception as exc:  # pragma: no cover - transport-specific
            return {
                "ok": False,
                "status": "offline",
                "message": str(exc),
                "capability": None,
            }

        try:
            payload = response.json()
        except ValueError:
            payload = {}

        ok = bool(response.is_success and str(payload.get("status") or "ok").lower() == "ok")
        return {
            "ok": ok,
            "status": str(payload.get("status") or ("ok" if response.is_success else "error")),
            "message": str(payload.get("message") or ""),
            "capability": payload.get("capability") if isinstance(payload, dict) else None,
        }

    async def read_source_live(
        self,
        doc_id: str,
        *,
        source_uri: str | None = None,
        source: dict | None = None,
        partner: dict | None = None,
    ) -> dict:
        """Read external content through a per-user Google Workspace sidecar."""
        target_source = source if isinstance(source, dict) else {}
        source_type = str(target_source.get("type") or "").strip().lower()
        if source_type != SourceType.GDRIVE:
            return {
                "error": "LIVE_RETRIEVAL_FAILED",
                "message": f"per-user live retrieval is not supported for source type '{source_type or 'unknown'}'",
            }

        config = _google_workspace_settings(partner)
        base_url = _normalize_sidecar_base_url(config.get("sidecar_base_url"))
        if not base_url:
            return {
                "error": "LIVE_RETRIEVAL_REQUIRED",
                "message": "Google Workspace connector 尚未設定 sidecar URL。",
            }

        email = str((partner or {}).get("email") or "").strip()
        if not email:
            return {
                "error": "LIVE_RETRIEVAL_REQUIRED",
                "message": "當前 caller 缺少 email principal，無法走 Google Workspace live retrieval。",
            }

        payload = {
            "connector": "gdrive",
            "doc_id": doc_id,
            "source_id": target_source.get("source_id"),
            "source_uri": source_uri or target_source.get("uri"),
            "requested_access": "full",
            "principal": {
                "partner_id": str((partner or {}).get("id") or "").strip() or None,
                "email": email,
                "display_name": str((partner or {}).get("displayName") or "").strip() or None,
            },
        }

        headers = _sidecar_headers(config)
        try:
            async with httpx.AsyncClient(timeout=DEFAULT_SIDECAR_TIMEOUT_SECONDS) as client:
                response = await client.post(f"{base_url}/read-source", headers=headers, json=payload)
        except Exception as exc:  # pragma: no cover - transport-specific
            return {
                "error": "LIVE_RETRIEVAL_FAILED",
                "message": str(exc),
            }

        try:
            body = response.json()
        except ValueError:
            body = {}

        if not response.is_success:
            return {
                "error": str(body.get("error") or "LIVE_RETRIEVAL_FAILED"),
                "message": str(body.get("message") or f"Google Workspace sidecar responded {response.status_code}"),
            }

        content = body.get("content")
        if not isinstance(content, str) or not content:
            return {
                "error": "LIVE_RETRIEVAL_FAILED",
                "message": "Google Workspace sidecar did not return content.",
            }

        result = {"content": content}
        content_type = body.get("content_type")
        if isinstance(content_type, str) and content_type.strip():
            result["content_type"] = content_type.strip()
        return result

    async def _should_archive_entity(self, entity) -> bool:
        """Return True only if all sources are unresolvable (or entity is single-doc)."""
        doc_role = getattr(entity, "doc_role", None) or "single"
        if doc_role != "index":
            return True
        # For index docs, archive only when ALL sources are unresolvable
        for src in (entity.sources or []):
            if _source_status(src) != "unresolvable":
                return False
        return True

    async def _handle_not_found(
        self,
        entity,
        uri: str,
        source_type: str,
        *,
        source_id: str | None = None,
    ) -> dict:
        """Decide source_status and action based on source type after a 404."""
        if source_type == SourceType.GITHUB:
            return await self._handle_github_not_found(
                entity, uri, source_id=source_id,
            )

        if source_type == SourceType.GDRIVE:
            await self._entities.update_source_status(
                entity.id, "unresolvable", source_id=source_id,
            )
            # Finding 4: only archive if all sources are unresolvable
            if await self._should_archive_entity(entity):
                await self._entities.archive_entity(entity.id)
            return {
                "error": "DEAD_LINK",
                "source_type": source_type,
                "source_status": "unresolvable",
                "suggested_action": "mark_unresolvable",
                "proposed_uri": None,
            }

        # notion and wiki: stale, wait for manual repair
        await self._entities.update_source_status(
            entity.id, "stale", source_id=source_id,
        )
        return {
            "error": "DEAD_LINK",
            "source_type": source_type,
            "source_status": "stale",
            "suggested_action": "check_permission",
            "proposed_uri": None,
        }

    async def _handle_github_not_found(
        self,
        entity,
        uri: str,
        *,
        source_id: str | None = None,
    ) -> dict:
        """Handle GitHub 404: search same repo for same-named file."""
        proposed_uri: str | None = None

        if self._adapter is not None:
            candidates = await self._adapter.search_alternatives_for_uri(uri)
            if candidates:
                proposed_uri = candidates[0]

        if proposed_uri is not None:
            await self._entities.update_source_status(
                entity.id, "stale", source_id=source_id,
            )
            return {
                "error": "DEAD_LINK",
                "source_type": SourceType.GITHUB,
                "source_status": "stale",
                "suggested_action": "search_repo",
                "proposed_uri": proposed_uri,
            }

        # No alternative found — unresolvable
        await self._entities.update_source_status(
            entity.id, "unresolvable", source_id=source_id,
        )
        # Finding 4: only archive if all sources are unresolvable
        if await self._should_archive_entity(entity):
            await self._entities.archive_entity(entity.id)
        return {
            "error": "DEAD_LINK",
            "source_type": SourceType.GITHUB,
            "source_status": "unresolvable",
            "suggested_action": "mark_unresolvable",
            "proposed_uri": None,
        }
