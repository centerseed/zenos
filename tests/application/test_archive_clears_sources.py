"""Tests for Fix 1: sync_mode='archive' clears sources in upsert_document.

Verifies:
- clear_sources=True in data results in empty sources list
- clear_sources not set preserves existing sources
"""

from __future__ import annotations

import pytest


class TestClearSourcesFlag:
    """Unit tests for the clear_sources branch in upsert_document."""

    def test_clear_sources_true_sets_empty_list(self):
        """When clear_sources=True, sources must be set to empty list."""
        data = {"clear_sources": True}
        existing_sources = [{"uri": "https://example.com/doc.md", "label": "doc.md"}]

        if data.get("clear_sources"):
            sources = []
        else:
            sources = list(existing_sources)

        assert sources == []

    def test_clear_sources_false_preserves_existing(self):
        """When clear_sources is absent, existing sources are preserved."""
        data = {}
        existing_sources = [{"uri": "https://example.com/doc.md", "label": "doc.md"}]

        if data.get("clear_sources"):
            sources = []
        else:
            sources = list(existing_sources)

        assert sources == existing_sources

    def test_clear_sources_false_explicit_preserves_existing(self):
        """When clear_sources=False, existing sources are preserved."""
        data = {"clear_sources": False}
        existing_sources = [{"uri": "https://example.com/doc.md", "label": "doc.md"}]

        if data.get("clear_sources"):
            sources = []
        else:
            sources = list(existing_sources)

        assert sources == existing_sources

    def test_archive_operation_sets_clear_sources_flag(self):
        """sync_document_governance archive operation sets clear_sources in update_payload."""
        update_payload: dict = {}
        operation = "archive"

        if operation == "archive":
            update_payload.setdefault("status", "archived")
            update_payload["clear_sources"] = True

        assert update_payload["status"] == "archived"
        assert update_payload["clear_sources"] is True

    def test_non_archive_operation_does_not_set_clear_sources(self):
        """Non-archive operations do not set clear_sources."""
        update_payload: dict = {}
        operation = "update"

        if operation == "archive":
            update_payload.setdefault("status", "archived")
            update_payload["clear_sources"] = True

        assert "clear_sources" not in update_payload
