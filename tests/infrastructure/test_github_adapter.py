"""Tests for GitHubAdapter error message format changes."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from zenos.infrastructure.github_adapter import GitHubAdapter, parse_github_url


# ---------------------------------------------------------------------------
# Unit tests: parse_github_url (unchanged behaviour)
# ---------------------------------------------------------------------------


def test_parse_github_url_short_form():
    owner, repo, path, ref = parse_github_url("centerseed/havital/cloud/api_service/docs/spec.md")
    assert owner == "centerseed"
    assert repo == "havital"
    assert path == "cloud/api_service/docs/spec.md"
    assert ref == "main"


def test_parse_github_url_full_blob():
    owner, repo, path, ref = parse_github_url(
        "https://github.com/centerseed/havital/blob/develop/cloud/api_service/docs/spec.md"
    )
    assert owner == "centerseed"
    assert repo == "havital"
    assert path == "cloud/api_service/docs/spec.md"
    assert ref == "develop"


# ---------------------------------------------------------------------------
# Unit tests: _fetch_contents NOT_FOUND error message format
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_contents_404_error_message_format():
    """404 from Contents API uses new message format with path/repo clearly separated."""
    adapter = GitHubAdapter(token="fake-token")

    mock_resp = MagicMock()
    mock_resp.status_code = 404

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client_cls.return_value.__aenter__.return_value = mock_client
        mock_client.get.return_value = mock_resp

        with pytest.raises(FileNotFoundError) as exc_info:
            await adapter._fetch_contents("centerseed", "havital", "cloud/api_service/docs/spec.md", "main")

    msg = str(exc_info.value)
    assert "GitHub 404" in msg
    assert "path=" in msg
    assert "repo=" in msg
    assert "centerseed/havital" in msg
    assert "cloud/api_service/docs/spec.md" in msg
    assert "(ref=main)" in msg


# ---------------------------------------------------------------------------
# Unit tests: _fetch_via_blob NOT_FOUND error message format
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_via_blob_path_segment_error_message_format():
    """Path-segment-not-found in blob API uses new message format."""
    adapter = GitHubAdapter(token="fake-token")

    # Stub responses: commit lookup succeeds, first tree lookup returns item not matching
    commit_resp = MagicMock()
    commit_resp.status_code = 200
    commit_resp.json.return_value = {"commit": {"tree": {"sha": "tree-sha-001"}}}

    tree_resp = MagicMock()
    tree_resp.status_code = 200
    tree_resp.json.return_value = {"tree": [{"path": "other_dir", "sha": "sha-other"}]}

    mock_client = AsyncMock()
    mock_client.get.side_effect = [commit_resp, tree_resp]

    with pytest.raises(FileNotFoundError) as exc_info:
        await adapter._fetch_via_blob(mock_client, "centerseed", "havital", "cloud/api_service/docs/spec.md", "main")

    msg = str(exc_info.value)
    assert "GitHub 404" in msg
    assert "path segment" in msg
    assert "repo=" in msg
    assert "centerseed/havital" in msg
    assert "traversed=" in msg
