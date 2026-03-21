"""SourceService — reads external document content via adapters.

Bridges the neural-layer document metadata with actual file content
by resolving the source URI through the appropriate adapter.
"""

from __future__ import annotations

from zenos.domain.repositories import DocumentRepository, SourceAdapter


class SourceService:
    """Application-layer service for reading external document sources."""

    def __init__(
        self,
        document_repo: DocumentRepository,
        source_adapter: SourceAdapter,
    ) -> None:
        self._documents = document_repo
        self._adapter = source_adapter

    async def read_source(self, doc_id: str) -> str:
        """Read the raw content of a document's source file.

        Steps:
          1. Retrieve the document metadata from the repository
          2. Extract the source URI
          3. Delegate to the source adapter to read the content
          4. Return the text content

        Raises:
            ValueError: if the document is not found.
        """
        doc = await self._documents.get_by_id(doc_id)
        if doc is None:
            raise ValueError(f"Document '{doc_id}' not found")

        uri = doc.source.uri
        return await self._adapter.read_content(uri)
