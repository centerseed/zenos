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

    async def read_source(self, doc_id: str) -> str:
        """Read the raw content of a document's source file.

        Steps:
          1. Retrieve the entity (type=document) from the repository by UUID.
          2. If UUID lookup fails, fall back to scanning all document entities
             and matching by source URI (for callers that pass a GitHub URI
             instead of an entity ID).
          3. Extract the source URI from entity.sources[0].
          4. Delegate to the source adapter to read the content.
          5. Return the text content.

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

        # Extract URI from sources list or legacy source field
        if entity.sources:
            uri = entity.sources[0].get("uri", "")
        else:
            raise ValueError(f"Document '{doc_id}' has no source URI")

        return await self._adapter.read_content(uri)

    async def read_source_with_recovery(self, doc_id: str) -> dict:
        """Read source with dead link detection and source_status update.

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

        source = entity.sources[0]
        uri = source.get("uri", "")
        source_type = source.get("type", "")
        current_status = source.get("status", "valid")

        # Short-circuit if already unresolvable — don't call external APIs
        if current_status == "unresolvable":
            return {"error": "ALREADY_UNRESOLVABLE"}

        try:
            content = await self._adapter.read_content(uri)
            return {"content": content}

        except FileNotFoundError:
            return await self._handle_not_found(entity.id, uri, source_type)

        except PermissionError:
            await self._entities.update_source_status(entity.id, "stale")
            return {
                "error": "DEAD_LINK",
                "source_type": source_type,
                "source_status": "stale",
                "suggested_action": "check_permission",
                "proposed_uri": None,
            }

    async def _handle_not_found(
        self, entity_id: str, uri: str, source_type: str
    ) -> dict:
        """Decide source_status and action based on source type after a 404."""
        if source_type == SourceType.GITHUB:
            return await self._handle_github_not_found(entity_id, uri)

        if source_type == SourceType.GDRIVE:
            await self._entities.update_source_status(entity_id, "unresolvable")
            await self._entities.archive_entity(entity_id)
            return {
                "error": "DEAD_LINK",
                "source_type": source_type,
                "source_status": "unresolvable",
                "suggested_action": "mark_unresolvable",
                "proposed_uri": None,
            }

        # notion and wiki: stale, wait for manual repair
        await self._entities.update_source_status(entity_id, "stale")
        return {
            "error": "DEAD_LINK",
            "source_type": source_type,
            "source_status": "stale",
            "suggested_action": "check_permission",
            "proposed_uri": None,
        }

    async def _handle_github_not_found(self, entity_id: str, uri: str) -> dict:
        """Handle GitHub 404: search same repo for same-named file."""
        proposed_uri: str | None = None

        if self._adapter is not None:
            candidates = await self._adapter.search_alternatives_for_uri(uri)
            if candidates:
                proposed_uri = candidates[0]

        if proposed_uri is not None:
            await self._entities.update_source_status(entity_id, "stale")
            return {
                "error": "DEAD_LINK",
                "source_type": SourceType.GITHUB,
                "source_status": "stale",
                "suggested_action": "search_repo",
                "proposed_uri": proposed_uri,
            }

        # No alternative found — unresolvable
        await self._entities.update_source_status(entity_id, "unresolvable")
        await self._entities.archive_entity(entity_id)
        return {
            "error": "DEAD_LINK",
            "source_type": SourceType.GITHUB,
            "source_status": "unresolvable",
            "suggested_action": "mark_unresolvable",
            "proposed_uri": None,
        }
