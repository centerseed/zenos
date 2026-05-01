"""Source URI format validators for document entity capture."""

from __future__ import annotations

import re
from urllib.parse import urlparse

# Titles that are bare source-type domain names — not valid as document titles.
BARE_DOMAIN_BLACKLIST: frozenset[str] = frozenset({
    "github", "notion", "drive", "wiki", "confluence"
})

# --- Helper Ingest Contract validators ---

ZENOS_NATIVE_URI_PATTERN = re.compile(
    r"^/docs/[a-zA-Z0-9_\-]+$"
)

LOCAL_URI_PATTERN = re.compile(
    r"^local:[a-f0-9]{64}$"
)

# external_id format: {source_type_prefix}:{identifier}
# prefix: lowercase letters and underscores only; identifier: alphanumeric + _-./
EXTERNAL_ID_PATTERN = re.compile(
    r"^[a-z_]+:[A-Za-z0-9_\-./]+$"
)

GITHUB_BLOB_PATTERN = re.compile(
    r"^https://github\.com/[^/]+/[^/]+/blob/[^/]+/.+"
)

GITHUB_TREE_PATTERN = re.compile(
    r"^https://github\.com/[^/]+/[^/]+/tree/"
)

GITHUB_RAW_PATTERN = re.compile(
    r"^https://raw\.githubusercontent\.com/"
)

NOTION_UUID_PATTERN = re.compile(
    r"[0-9a-f]{8}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{12}",
    re.IGNORECASE,
)

GDRIVE_FILE_PATTERN = re.compile(
    r"^https://drive\.google\.com/(file/d/[^/]+/|open\?id=)"
)

LOCALHOST_HOSTS = {"localhost", "127.0.0.1", "::1", "0.0.0.0"}


def _reject_unreachable_uri(source_type: str, uri: str) -> tuple[bool, str]:
    """Reject local-only URIs before source-type-specific validation.

    Document sources must be resolvable by ZenOS server-side governance paths.
    A caller's local filesystem or loopback web server is not reachable from
    Cloud Run and becomes silent dead metadata if accepted.
    """
    if not uri:
        return (True, "")

    if source_type == "upload" and uri.startswith("/attachments/"):
        return (
            False,
            (
                "upload source_uri must not point at task attachment proxy URLs "
                "(/attachments/{attachment_id}). Task attachments are not document "
                "delivery snapshots and cannot be read as document source content. "
                "Use write(initial_content=...) to create a zenos_native source for "
                "markdown content, or attach a snapshot_summary for helper-ingest sources."
            ),
        )

    lowered = uri.lower()
    if lowered.startswith("file://"):
        return (
            False,
            (
                "source_uri must be reachable by ZenOS backend; file:// URIs "
                "point to the caller's local filesystem and are not accepted. "
                "Use initial_content for markdown content, zenos_native /docs/{doc_id}, "
                "or attach a helper snapshot_summary for helper-ingest sources."
            ),
        )

    if source_type != "zenos_native" and (
        uri.startswith("/")
        or uri.startswith("~/")
        or re.match(r"^[A-Za-z]:[\\/]", uri)
    ):
        return (
            False,
            (
                "source_uri must not be a local filesystem path. "
                "Use initial_content, zenos_native /docs/{doc_id}, or a backend-reachable https:// URL."
            ),
        )

    parsed = urlparse(uri)
    if parsed.scheme in {"http", "https"} and (parsed.hostname or "").lower() in LOCALHOST_HOSTS:
        return (
            False,
            (
                "source_uri must not point to localhost or loopback addresses; "
                "ZenOS backend cannot resolve caller-local services."
            ),
        )

    return (True, "")


def validate_source_uri(source_type: str, uri: str) -> tuple[bool, str]:
    """Validate source URI format for document entities.

    All source types first pass a global reachability guard that rejects local-only
    schemes/paths. Type-specific validators then enforce each platform contract.

    Returns (is_valid, error_message). error_message is empty string when valid.
    """
    source_type = str(source_type or "").strip()
    uri = str(uri or "").strip()

    ok, error = _reject_unreachable_uri(source_type, uri)
    if not ok:
        return (False, error)

    if source_type == "github":
        if GITHUB_TREE_PATTERN.match(uri):
            return (
                False,
                (
                    "GitHub tree URLs (directory listings) are not accepted. "
                    "Use a blob URL pointing to a specific file: "
                    "https://github.com/{owner}/{repo}/blob/{branch}/{path}. "
                    f"Got: {uri!r}"
                ),
            )
        if GITHUB_RAW_PATTERN.match(uri):
            return (
                False,
                (
                    "GitHub raw.githubusercontent.com URLs are not accepted. "
                    "Use the standard blob URL: "
                    "https://github.com/{owner}/{repo}/blob/{branch}/{path}. "
                    f"Got: {uri!r}"
                ),
            )
        if not GITHUB_BLOB_PATTERN.match(uri):
            return (
                False,
                (
                    "GitHub source_uri must be a blob URL in the form "
                    "https://github.com/{owner}/{repo}/blob/{branch}/{path}. "
                    f"Got: {uri!r}"
                ),
            )
        return (True, "")

    if source_type == "notion":
        if not uri.startswith("https://www.notion.so/"):
            return (
                False,
                (
                    "Notion source_uri must start with https://www.notion.so/. "
                    f"Got: {uri!r}"
                ),
            )
        if not NOTION_UUID_PATTERN.search(uri):
            return (
                False,
                (
                    "Notion source_uri must contain a page UUID "
                    "(32 hex chars, e.g. https://www.notion.so/page-title-abc123...def456). "
                    f"Got: {uri!r}"
                ),
            )
        return (True, "")

    if source_type == "gdrive":
        if "/drive/folders/" in uri or "/drive/u/" in uri:
            return (
                False,
                (
                    "Google Drive folder URLs are not accepted. "
                    "Use a file URL: https://drive.google.com/file/d/{file-id}/view. "
                    f"Got: {uri!r}"
                ),
            )
        if not GDRIVE_FILE_PATTERN.match(uri):
            return (
                False,
                (
                    "Google Drive source_uri must be a file URL in the form "
                    "https://drive.google.com/file/d/{file-id}/view "
                    "or https://drive.google.com/open?id={file-id}. "
                    "Folder URLs are not accepted. "
                    f"Got: {uri!r}"
                ),
            )
        return (True, "")

    if source_type == "wiki":
        if not uri.startswith("https://"):
            return (
                False,
                (
                    "Wiki source_uri must be a full URL starting with https://. "
                    f"Got: {uri!r}"
                ),
            )
        if "/edit" in uri:
            return (
                False,
                (
                    "Wiki source_uri must not contain '/edit'. "
                    "Use the view URL instead. "
                    f"Got: {uri!r}"
                ),
            )
        return (True, "")

    if source_type == "url":
        if not uri.startswith("https://"):
            return (
                False,
                (
                    "url source_uri must be a backend-reachable https:// URL. "
                    f"Got: {uri!r}"
                ),
            )
        return (True, "")

    if source_type == "zenos_native":
        if not ZENOS_NATIVE_URI_PATTERN.match(uri):
            return (
                False,
                (
                    "zenos_native source_uri must match /docs/{doc_id} "
                    "(alphanumeric, hyphens, underscores only). "
                    f"Got: {uri!r}"
                ),
            )
        return (True, "")

    if source_type == "local":
        if not LOCAL_URI_PATTERN.match(uri):
            return (
                False,
                (
                    "local source_uri must be in the form local:{sha256_hex} "
                    "(exactly 64 lowercase hex characters). "
                    f"Got: {uri!r}"
                ),
            )
        return (True, "")

    # Unknown or unvalidated types (e.g. 'upload') pass through after the
    # global local/dead URI guard above.
    return (True, "")


def validate_external_id_format(external_id: str) -> tuple[bool, str]:
    """Validate the format of an external_id value.

    Valid format: ``{prefix}:{identifier}``
    - prefix: one or more lowercase letters or underscores
    - identifier: one or more alphanumeric chars, hyphens, underscores, dots, slashes

    Examples of valid values: ``notion:abc123``, ``gdrive:1abcXYZ``,
    ``local:a1b2c3...`` (64 hex chars).

    Returns (is_valid, error_message). error_message is empty when valid.
    """
    if not external_id:
        return (
            False,
            "external_id must not be empty.",
        )
    if not EXTERNAL_ID_PATTERN.match(external_id):
        return (
            False,
            (
                "external_id must follow the format '{source_type}:{identifier}', "
                "e.g. 'notion:abc123' or 'gdrive:1abcXYZ'. "
                "Prefix must be lowercase letters/underscores; "
                "identifier must be alphanumeric plus _-./. "
                f"Got: {external_id!r}"
            ),
        )
    return (True, "")
