"""MCP tool: upload_document_file — create/update ZenOS documents from local files."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from zenos.interface.mcp._common import _error_response, _unified_response

logger = logging.getLogger(__name__)

_MAX_DOCUMENT_BYTES = 1_048_576


def _read_utf8_file(path: str) -> tuple[str | None, dict | None]:
    raw = str(path or "").strip()
    if not raw:
        return None, {
            "error_code": "INVALID_INPUT",
            "message": "path is required",
        }
    if raw.startswith("file://"):
        return None, {
            "error_code": "INVALID_INPUT",
            "message": "path must be a local filesystem path, not file:// URI",
        }

    file_path = Path(raw).expanduser()
    if not file_path.is_file():
        return None, {
            "error_code": "NOT_FOUND",
            "message": f"File not found: {raw}",
        }

    size = file_path.stat().st_size
    if size > _MAX_DOCUMENT_BYTES:
        return None, {
            "error_code": "INITIAL_CONTENT_TOO_LARGE",
            "message": "document file exceeds 1 MB limit",
            "extra_data": {"max_bytes": _MAX_DOCUMENT_BYTES, "actual_bytes": size},
        }

    try:
        return file_path.read_text(encoding="utf-8"), None
    except UnicodeDecodeError:
        return None, {
            "error_code": "INVALID_INPUT",
            "message": "document file must be UTF-8 encoded text",
        }


async def upload_document_file(
    path: str,
    title: str,
    linked_entity_ids: list[str],
    type: str = "REFERENCE",
    doc_role: str = "index",
    summary: str = "",
    tags: dict[str, Any] | None = None,
    id: str | None = None,
    allow_l2_direct_document: bool = False,
    workspace_id: str | None = None,
) -> dict:
    """Create or update a ZenOS document by reading a UTF-8 markdown/text file.

    This is the low-token document delivery path when the MCP server runs on the
    same filesystem as the agent. Hosted MCP servers cannot read the caller's
    local path; in that case use the multipart `/api/ext/docs` upload route.

    Args:
        path: Filesystem path visible to the MCP server. Do not pass file://.
        title: Document title.
        linked_entity_ids: L2/L3 entity IDs this document is linked to.
        type: Document type, e.g. SPEC, DESIGN, TEST, REFERENCE.
        doc_role: "index" by default; use "single" only for independently governed docs.
        summary: Short retrieval summary for the document or bundle.
        tags: Document tags using the standard {what, why, how, who} shape.
        id: Existing document ID to update. Omit to create a new document.
        allow_l2_direct_document: Bypass bundle-first rejection when intentionally creating a root bundle.
        workspace_id: Optional workspace override.
    """
    from zenos.interface.mcp.write import write

    try:
        if not str(title or "").strip():
            return _error_response(
                status="rejected",
                error_code="INVALID_INPUT",
                message="title is required",
            )
        if not linked_entity_ids:
            return _error_response(
                status="rejected",
                error_code="INVALID_INPUT",
                message="linked_entity_ids is required",
            )

        content, err = _read_utf8_file(path)
        if err is not None:
            return _error_response(status="rejected", **err)

        data: dict[str, Any] = {
            "title": title,
            "type": type,
            "doc_role": doc_role,
            "summary": summary,
            "linked_entity_ids": linked_entity_ids,
            "tags": tags or {},
            "allow_l2_direct_document": allow_l2_direct_document,
        }
        if id:
            data["id"] = id
            data["update_content"] = content
        else:
            data["initial_content"] = content

        result = await write(
            collection="documents",
            data=data,
            workspace_id=workspace_id,
        )
        response_data = dict(result.get("data") or {})
        response_data["uploaded_from_path"] = str(Path(path).expanduser())
        response_data["bytes"] = len((content or "").encode("utf-8"))
        result["data"] = response_data
        return result

    except Exception as exc:
        logger.exception("upload_document_file failed")
        return _error_response(
            error_code="INTERNAL_ERROR",
            message=str(exc),
        )
