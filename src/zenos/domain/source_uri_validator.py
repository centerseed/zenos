"""Source URI format validators for document entity capture."""

from __future__ import annotations

import re

# Titles that are bare source-type domain names — not valid as document titles.
BARE_DOMAIN_BLACKLIST: frozenset[str] = frozenset({
    "github", "notion", "drive", "wiki", "confluence"
})

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


def validate_source_uri(source_type: str, uri: str) -> tuple[bool, str]:
    """Validate source URI format for document entities.

    Only validates types: github, notion, gdrive, wiki.
    Type 'upload' is not validated.

    Returns (is_valid, error_message). error_message is empty string when valid.
    """
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

    # Unknown or unvalidated types (e.g. 'upload') pass through
    return (True, "")
