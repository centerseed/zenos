"""Tests for source_uri_validator domain module."""

import pytest
from zenos.domain.source_uri_validator import validate_source_uri


# ---------------------------------------------------------------------------
# GitHub
# ---------------------------------------------------------------------------


class TestGitHubValidation:
    def test_valid_blob_url(self):
        ok, msg = validate_source_uri(
            "github",
            "https://github.com/owner/repo/blob/main/path/file.md",
        )
        assert ok is True
        assert msg == ""

    def test_valid_blob_url_nested_path(self):
        ok, msg = validate_source_uri(
            "github",
            "https://github.com/acme/backend/blob/develop/src/services/foo.py",
        )
        assert ok is True

    def test_relative_path_rejected(self):
        ok, msg = validate_source_uri("github", "docs/specs/file.md")
        assert ok is False
        assert "blob" in msg

    def test_tree_url_rejected(self):
        """Tree URLs are not blob URLs and must be rejected."""
        ok, msg = validate_source_uri(
            "github",
            "https://github.com/owner/repo/tree/main/docs",
        )
        assert ok is False
        assert "tree" in msg.lower()

    def test_raw_githubusercontent_url_rejected(self):
        """raw.githubusercontent.com URLs must be rejected (ADR-022 D7)."""
        ok, msg = validate_source_uri(
            "github",
            "https://raw.githubusercontent.com/owner/repo/main/path/file.md",
        )
        assert ok is False
        assert "raw" in msg.lower()

    def test_missing_path_segment_rejected(self):
        """URL must have a path after branch."""
        ok, msg = validate_source_uri(
            "github",
            "https://github.com/owner/repo/blob/main",
        )
        assert ok is False

    def test_repo_root_url_rejected(self):
        ok, msg = validate_source_uri(
            "github",
            "https://github.com/owner/repo",
        )
        assert ok is False


# ---------------------------------------------------------------------------
# Notion
# ---------------------------------------------------------------------------


class TestNotionValidation:
    def test_valid_notion_url_with_uuid(self):
        # UUID segment: 32 hex chars (8+4+4+4+12 = 32)
        ok, msg = validate_source_uri(
            "notion",
            "https://www.notion.so/My-Page-abc12345678901234567890123456789",
        )
        assert ok is True

    def test_valid_notion_url_with_hyphenated_uuid(self):
        ok, msg = validate_source_uri(
            "notion",
            "https://www.notion.so/workspace/page-a1b2c3d4-e5f6-7890-abcd-ef1234567890",
        )
        assert ok is True

    def test_title_only_url_rejected(self):
        """URL without UUID segment must be rejected."""
        ok, msg = validate_source_uri(
            "notion",
            "https://www.notion.so/title-only",
        )
        assert ok is False
        assert "UUID" in msg

    def test_wrong_domain_rejected(self):
        ok, msg = validate_source_uri(
            "notion",
            "https://notion.so/page-abc123",
        )
        assert ok is False
        assert "www.notion.so" in msg

    def test_shortened_link_rejected(self):
        ok, msg = validate_source_uri("notion", "https://notion.so/xyz")
        assert ok is False


# ---------------------------------------------------------------------------
# Google Drive
# ---------------------------------------------------------------------------


class TestGDriveValidation:
    def test_valid_file_view_url(self):
        ok, msg = validate_source_uri(
            "gdrive",
            "https://drive.google.com/file/d/abc123XYZ/view",
        )
        assert ok is True

    def test_valid_open_id_url(self):
        ok, msg = validate_source_uri(
            "gdrive",
            "https://drive.google.com/open?id=abc123XYZ",
        )
        assert ok is True

    def test_folder_url_rejected(self):
        ok, msg = validate_source_uri(
            "gdrive",
            "https://drive.google.com/drive/folders/xyz",
        )
        assert ok is False
        assert "folder" in msg.lower()

    def test_folder_url_with_user_path_rejected(self):
        """GDrive /drive/u/ URLs (user-specific folder views) must be rejected."""
        ok, msg = validate_source_uri(
            "gdrive",
            "https://drive.google.com/drive/u/0/folders/abc123",
        )
        assert ok is False
        assert "folder" in msg.lower()

    def test_relative_path_rejected(self):
        ok, msg = validate_source_uri("gdrive", "docs/myfile.pdf")
        assert ok is False


# ---------------------------------------------------------------------------
# Wiki
# ---------------------------------------------------------------------------


class TestWikiValidation:
    def test_valid_wiki_url(self):
        ok, msg = validate_source_uri(
            "wiki",
            "https://wiki.example.com/page/Some+Article",
        )
        assert ok is True

    def test_edit_url_rejected(self):
        ok, msg = validate_source_uri(
            "wiki",
            "https://wiki.example.com/page/Some+Article/edit",
        )
        assert ok is False
        assert "/edit" in msg

    def test_no_scheme_rejected(self):
        ok, msg = validate_source_uri("wiki", "wiki.example.com/page")
        assert ok is False
        assert "https://" in msg

    def test_http_scheme_rejected(self):
        ok, msg = validate_source_uri("wiki", "http://wiki.example.com/page")
        assert ok is False


# ---------------------------------------------------------------------------
# URL
# ---------------------------------------------------------------------------


class TestUrlValidation:
    def test_https_url_passes(self):
        ok, msg = validate_source_uri("url", "https://example.com/docs/file.md")
        assert ok is True
        assert msg == ""

    def test_file_url_rejected(self):
        ok, msg = validate_source_uri("url", "file:///Users/me/docs/file.md")
        assert ok is False
        assert "file://" in msg

    def test_localhost_url_rejected(self):
        ok, msg = validate_source_uri("url", "http://localhost:3000/docs/file.md")
        assert ok is False
        assert "localhost" in msg

    def test_http_url_rejected(self):
        ok, msg = validate_source_uri("url", "http://example.com/docs/file.md")
        assert ok is False
        assert "https://" in msg


# ---------------------------------------------------------------------------
# Upload (global local/dead URI guard only)
# ---------------------------------------------------------------------------


class TestUploadValidation:
    def test_upload_attachment_proxy_rejected(self):
        ok, msg = validate_source_uri("upload", "/attachments/abc123")
        assert ok is False
        assert "task attachment proxy" in msg
        assert "write(initial_content=...)" in msg

    def test_upload_internal_reference_passes(self):
        """Type 'upload' allows internal references after global dead-URI checks."""
        ok, msg = validate_source_uri("upload", "some-internal-reference")
        assert ok is True

    def test_upload_empty_uri_passes(self):
        ok, msg = validate_source_uri("upload", "")
        assert ok is True

    def test_upload_file_uri_rejected(self):
        ok, msg = validate_source_uri("upload", "file:///Users/me/docs/file.md")
        assert ok is False
        assert "file://" in msg

    def test_upload_local_path_rejected(self):
        ok, msg = validate_source_uri("upload", "/Users/me/docs/file.md")
        assert ok is False
        assert "local filesystem path" in msg

    def test_upload_localhost_url_rejected(self):
        ok, msg = validate_source_uri("upload", "http://127.0.0.1:8000/file.md")
        assert ok is False
        assert "localhost" in msg or "loopback" in msg


# ---------------------------------------------------------------------------
# Unknown type (passthrough)
# ---------------------------------------------------------------------------


class TestUnknownTypeValidation:
    def test_unknown_type_passes(self):
        ok, msg = validate_source_uri("custom_source", "https://example.com")
        assert ok is True

    def test_unknown_type_still_rejects_file_uri(self):
        ok, msg = validate_source_uri("custom_source", "file:///tmp/source.md")
        assert ok is False
        assert "file://" in msg
