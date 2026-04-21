"""Tests for search-service logging redaction on semantic fallback."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from zenos.application.knowledge.search_service import SearchService


@pytest.mark.asyncio
async def test_semantic_fallback_warning_redacts_query_text():
    repo = AsyncMock()
    repo.list_all = AsyncMock(return_value=[])
    embed = AsyncMock()
    embed.embed_query = AsyncMock(return_value=None)
    svc = SearchService(entity_repo=repo, embedding_service=embed)

    with patch("zenos.application.knowledge.search_service.logger") as mock_logger:
        await svc.search_entities("salary sheet for customer x", mode="semantic")

    msg = mock_logger.warning.call_args.args[0]
    marker = mock_logger.warning.call_args.args[1]
    assert "query=%r" not in msg
    assert "sha256_12=" in marker
    assert "salary sheet for customer x" not in marker
