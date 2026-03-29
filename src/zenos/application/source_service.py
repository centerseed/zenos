"""SourceService — reads external document content via adapters.

Bridges entity/document metadata with actual file content
by resolving the source URI through the appropriate adapter.
"""

from __future__ import annotations

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
