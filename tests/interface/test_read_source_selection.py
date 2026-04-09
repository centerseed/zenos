"""Tests for read_source source-selection logic in the MCP tool handler.

Covers:
- Finding 1: selected source URI is passed to the service read call
- Finding 2: stale primaries are skipped in auto-selection
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from zenos.domain.models import Entity, Tags


def _make_doc_entity(sources: list[dict], **overrides) -> Entity:
    """Create a minimal Entity with the given sources list."""
    defaults = dict(
        id="doc-1",
        name="Test Doc",
        type="document",
        summary="A doc",
        tags=Tags(what=["test"], why="testing", how="unit", who=["dev"]),
        status="active",
        sources=sources,
    )
    defaults.update(overrides)
    return Entity(**defaults)


@pytest.fixture(autouse=True)
def _mock_tool_bootstrap():
    """Avoid bootstrapping real SQL repos in interface unit tests."""
    with (
        patch("zenos.interface.tools._ensure_services", new=AsyncMock(return_value=None)),
        patch("zenos.interface.tools.ontology_service", new=AsyncMock()),
        patch("zenos.interface.tools.task_service", new=AsyncMock()),
        patch("zenos.interface.tools.entity_repo", new=AsyncMock()),
        patch("zenos.interface.tools.entry_repo", new=AsyncMock()),
    ):
        yield


# ---------------------------------------------------------------------------
# Finding 2: stale primary is skipped, valid source is selected
# ---------------------------------------------------------------------------


class TestAutoSelectSkipsStalePrimary:
    """When primary source is stale, auto-select should pick the first valid source."""

    @pytest.mark.asyncio
    async def test_stale_primary_skipped_valid_source_used(self):
        """Primary is stale, second source is valid -> reads second source."""
        from zenos.interface.tools import read_source

        doc = _make_doc_entity(sources=[
            {
                "source_id": "s1",
                "uri": "stale-primary.md",
                "label": "Primary",
                "type": "github",
                "status": "stale",
                "is_primary": True,
            },
            {
                "source_id": "s2",
                "uri": "valid-secondary.md",
                "label": "Secondary",
                "type": "github",
                "status": "valid",
                "is_primary": False,
            },
        ])

        with (
            patch("zenos.interface.tools.ontology_service") as mock_os,
            patch("zenos.interface.tools.source_service") as mock_ss,
            patch("zenos.interface.tools._current_partner") as mock_partner,
        ):
            mock_partner.get.return_value = None
            mock_os.get_document = AsyncMock(return_value=doc)
            mock_ss.read_source_with_recovery = None  # disable recovery
            mock_ss.read_source = AsyncMock(return_value="secondary content")

            result = await read_source(doc_id="doc-1")

            assert result["content"] == "secondary content"
            assert result["source_id"] == "s2"
            # Verify the valid URI was passed, not the stale one
            mock_ss.read_source.assert_called_once_with("doc-1", source_uri="valid-secondary.md")

    @pytest.mark.asyncio
    async def test_valid_primary_still_preferred(self):
        """Primary is valid -> it is still selected (no regression)."""
        from zenos.interface.tools import read_source

        doc = _make_doc_entity(sources=[
            {
                "source_id": "s1",
                "uri": "valid-primary.md",
                "label": "Primary",
                "type": "github",
                "status": "valid",
                "is_primary": True,
            },
            {
                "source_id": "s2",
                "uri": "valid-secondary.md",
                "label": "Secondary",
                "type": "github",
                "status": "valid",
                "is_primary": False,
            },
        ])

        with (
            patch("zenos.interface.tools.ontology_service") as mock_os,
            patch("zenos.interface.tools.source_service") as mock_ss,
            patch("zenos.interface.tools._current_partner") as mock_partner,
        ):
            mock_partner.get.return_value = None
            mock_os.get_document = AsyncMock(return_value=doc)
            mock_ss.read_source_with_recovery = None
            mock_ss.read_source = AsyncMock(return_value="primary content")

            result = await read_source(doc_id="doc-1")

            assert result["content"] == "primary content"
            assert result["source_id"] == "s1"
            mock_ss.read_source.assert_called_once_with("doc-1", source_uri="valid-primary.md")

    @pytest.mark.asyncio
    async def test_all_stale_returns_source_unavailable(self):
        """All sources are stale -> returns SOURCE_UNAVAILABLE with alternatives empty."""
        from zenos.interface.tools import read_source

        doc = _make_doc_entity(sources=[
            {
                "source_id": "s1",
                "uri": "stale1.md",
                "label": "Primary",
                "type": "github",
                "status": "stale",
                "is_primary": True,
            },
            {
                "source_id": "s2",
                "uri": "stale2.md",
                "label": "Secondary",
                "type": "github",
                "status": "stale",
                "is_primary": False,
            },
        ])

        with (
            patch("zenos.interface.tools.ontology_service") as mock_os,
            patch("zenos.interface.tools.source_service") as mock_ss,
            patch("zenos.interface.tools._current_partner") as mock_partner,
        ):
            mock_partner.get.return_value = None
            mock_os.get_document = AsyncMock(return_value=doc)

            result = await read_source(doc_id="doc-1")

            assert result["error"] == "SOURCE_UNAVAILABLE"
            assert result["source_status"] == "stale"


# ---------------------------------------------------------------------------
# Finding 1: source_id selects the correct source URI for the read call
# ---------------------------------------------------------------------------


class TestSourceIdPassedToService:
    """When source_id is specified, the selected URI must be passed to the service."""

    @pytest.mark.asyncio
    async def test_source_id_routes_to_correct_uri(self):
        """Explicit source_id -> service is called with that source's URI."""
        from zenos.interface.tools import read_source

        doc = _make_doc_entity(sources=[
            {
                "source_id": "s1",
                "uri": "first.md",
                "label": "First",
                "type": "github",
                "status": "valid",
                "is_primary": True,
            },
            {
                "source_id": "s2",
                "uri": "second.md",
                "label": "Second",
                "type": "github",
                "status": "valid",
                "is_primary": False,
            },
        ])

        with (
            patch("zenos.interface.tools.ontology_service") as mock_os,
            patch("zenos.interface.tools.source_service") as mock_ss,
            patch("zenos.interface.tools._current_partner") as mock_partner,
        ):
            mock_partner.get.return_value = None
            mock_os.get_document = AsyncMock(return_value=doc)
            mock_ss.read_source_with_recovery = None
            mock_ss.read_source = AsyncMock(return_value="second content")

            result = await read_source(doc_id="doc-1", source_id="s2")

            assert result["content"] == "second content"
            assert result["source_id"] == "s2"
            # The critical assertion: the correct URI was passed to the service
            mock_ss.read_source.assert_called_once_with("doc-1", source_uri="second.md")

    @pytest.mark.asyncio
    async def test_source_id_with_recovery_routes_to_correct_uri(self):
        """Explicit source_id with recovery enabled -> correct URI passed."""
        from zenos.interface.tools import read_source

        doc = _make_doc_entity(sources=[
            {
                "source_id": "s1",
                "uri": "first.md",
                "label": "First",
                "type": "github",
                "status": "valid",
                "is_primary": True,
            },
            {
                "source_id": "s2",
                "uri": "second.md",
                "label": "Second",
                "type": "github",
                "status": "valid",
                "is_primary": False,
            },
        ])

        with (
            patch("zenos.interface.tools.ontology_service") as mock_os,
            patch("zenos.interface.tools.source_service") as mock_ss,
            patch("zenos.interface.tools._current_partner") as mock_partner,
        ):
            mock_partner.get.return_value = None
            mock_os.get_document = AsyncMock(return_value=doc)
            mock_ss.read_source_with_recovery = AsyncMock(
                return_value={"content": "recovered second"}
            )

            result = await read_source(doc_id="doc-1", source_id="s2")

            assert result["content"] == "recovered second"
            assert result["source_id"] == "s2"
            mock_ss.read_source_with_recovery.assert_called_once_with(
                "doc-1", source_uri="second.md"
            )
