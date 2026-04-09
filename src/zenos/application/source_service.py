"""SourceService — reads external document content via adapters.

Bridges entity/document metadata with actual file content
by resolving the source URI through the appropriate adapter.
"""

from __future__ import annotations

from zenos.domain.models import SourceType
from zenos.domain.repositories import EntityRepository, SourceAdapter


class SourceService:
    """Application-layer service for reading external document sources."""

    def __init__(
        self,
        entity_repo: EntityRepository | None = None,
        source_adapter: SourceAdapter | None = None,
        document_repo: object | None = None,  # deprecated, kept for backward compat
    ) -> None:
        self._entities = entity_repo
        self._adapter = source_adapter

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
        current_status = source.get("status", "valid")

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

    async def _should_archive_entity(self, entity) -> bool:
        """Return True only if all sources are unresolvable (or entity is single-doc)."""
        doc_role = getattr(entity, "doc_role", None) or "single"
        if doc_role != "index":
            return True
        # For index docs, archive only when ALL sources are unresolvable
        for src in (entity.sources or []):
            if src.get("status", "valid") != "unresolvable":
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
