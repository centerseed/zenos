"""Unit tests for the setup.py CLI script.

Tests the setup_cloud, update_cloud, _build_cloud_url, _parse_existing_url
functions directly using tmp_path for file I/O isolation.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Add the script directory to path so we can import setup
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "release" / "zenos-setup" / "scripts"))
import setup as setup_script  # noqa: E402


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

@pytest.fixture()
def mcp_dir(tmp_path: Path) -> Path:
    """Create a .claude dir and return the mcp.json path."""
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir()
    return claude_dir / "mcp.json"


@pytest.fixture(autouse=True)
def patch_mcp_path(mcp_dir: Path):
    """Patch MCP_CONFIG_PATH to use tmp dir."""
    with patch.object(setup_script, "MCP_CONFIG_PATH", str(mcp_dir)):
        yield


# ──────────────────────────────────────────────
# _build_cloud_url tests
# ──────────────────────────────────────────────

class TestBuildCloudUrl:
    def test_token_only(self):
        url = setup_script._build_cloud_url("https://example.com/mcp", "my-token")
        assert url == "https://example.com/mcp?api_key=my-token"

    def test_token_and_project(self):
        url = setup_script._build_cloud_url("https://example.com/mcp", "tok", "myproj")
        assert "api_key=tok" in url
        assert "project=myproj" in url

    def test_empty_project_not_included(self):
        url = setup_script._build_cloud_url("https://example.com/mcp", "tok", "")
        assert "project" not in url

    def test_special_chars_in_project_are_encoded(self):
        url = setup_script._build_cloud_url("https://example.com/mcp", "tok", "my project")
        assert "project=my+project" in url or "project=my%20project" in url


# ──────────────────────────────────────────────
# _parse_existing_url tests
# ──────────────────────────────────────────────

class TestParseExistingUrl:
    def test_parse_token_only(self):
        base, token, project = setup_script._parse_existing_url(
            "https://example.com/mcp?api_key=tok123"
        )
        assert base == "https://example.com/mcp"
        assert token == "tok123"
        assert project == ""

    def test_parse_token_and_project(self):
        base, token, project = setup_script._parse_existing_url(
            "https://example.com/mcp?api_key=tok&project=myproj"
        )
        assert base == "https://example.com/mcp"
        assert token == "tok"
        assert project == "myproj"

    def test_parse_missing_params(self):
        base, token, project = setup_script._parse_existing_url(
            "https://example.com/mcp"
        )
        assert base == "https://example.com/mcp"
        assert token == ""
        assert project == ""


# ──────────────────────────────────────────────
# setup_cloud tests
# ──────────────────────────────────────────────

class TestSetupCloud:
    def test_creates_config_with_token(self, mcp_dir: Path):
        setup_script.setup_cloud("mytoken", "https://example.com/mcp")
        config = json.loads(mcp_dir.read_text())
        url = config["mcpServers"]["zenos"]["url"]
        assert "api_key=mytoken" in url
        assert "project" not in url

    def test_creates_config_with_token_and_project(self, mcp_dir: Path):
        setup_script.setup_cloud("mytoken", "https://example.com/mcp", "myproj")
        config = json.loads(mcp_dir.read_text())
        url = config["mcpServers"]["zenos"]["url"]
        assert "api_key=mytoken" in url
        assert "project=myproj" in url

    def test_preserves_other_servers(self, mcp_dir: Path):
        existing = {"mcpServers": {"other": {"type": "stdio"}}}
        mcp_dir.write_text(json.dumps(existing))
        setup_script.setup_cloud("tok", "https://example.com/mcp")
        config = json.loads(mcp_dir.read_text())
        assert "other" in config["mcpServers"]
        assert "zenos" in config["mcpServers"]


# ──────────────────────────────────────────────
# update_cloud tests
# ──────────────────────────────────────────────

class TestUpdateCloud:
    def _write_existing(self, mcp_dir: Path, token: str = "old-tok", project: str = ""):
        url = setup_script._build_cloud_url("https://example.com/mcp", token, project)
        config = {"mcpServers": {"zenos": {"type": "http", "url": url}}}
        mcp_dir.write_text(json.dumps(config))

    def test_update_project_preserves_token(self, mcp_dir: Path):
        self._write_existing(mcp_dir, token="keep-me")
        setup_script.update_cloud(token=None, project="new-proj")
        config = json.loads(mcp_dir.read_text())
        url = config["mcpServers"]["zenos"]["url"]
        assert "api_key=keep-me" in url
        assert "project=new-proj" in url

    def test_update_token_preserves_project(self, mcp_dir: Path):
        self._write_existing(mcp_dir, token="old-tok", project="keep-proj")
        setup_script.update_cloud(token="new-tok", project=None)
        config = json.loads(mcp_dir.read_text())
        url = config["mcpServers"]["zenos"]["url"]
        assert "api_key=new-tok" in url
        assert "project=keep-proj" in url

    def test_update_both(self, mcp_dir: Path):
        self._write_existing(mcp_dir, token="old", project="old-proj")
        setup_script.update_cloud(token="new-tok", project="new-proj")
        config = json.loads(mcp_dir.read_text())
        url = config["mcpServers"]["zenos"]["url"]
        assert "api_key=new-tok" in url
        assert "project=new-proj" in url

    def test_update_fails_without_existing_zenos(self, mcp_dir: Path):
        config = {"mcpServers": {"other": {"type": "stdio"}}}
        mcp_dir.write_text(json.dumps(config))
        with pytest.raises(SystemExit):
            setup_script.update_cloud(token="tok", project=None)

    def test_update_fails_without_mcp_json(self):
        with pytest.raises(SystemExit):
            setup_script.update_cloud(token="tok", project=None)


# ──────────────────────────────────────────────
# CLI argument parsing tests (via main)
# ──────────────────────────────────────────────

class TestMainCli:
    def test_update_without_token_or_project_exits(self):
        with patch("sys.argv", ["setup.py", "--update"]):
            with pytest.raises(SystemExit) as exc_info:
                setup_script.main()
            assert exc_info.value.code == 1

    def test_no_args_exits(self):
        with patch("sys.argv", ["setup.py"]):
            with pytest.raises(SystemExit) as exc_info:
                setup_script.main()
            assert exc_info.value.code == 1

    def test_token_creates_cloud_config(self, mcp_dir: Path):
        with patch("sys.argv", ["setup.py", "--token", "test-tok"]):
            setup_script.main()
        config = json.loads(mcp_dir.read_text())
        assert "zenos" in config["mcpServers"]

    def test_token_with_project(self, mcp_dir: Path):
        with patch("sys.argv", ["setup.py", "--token", "tok", "--project", "proj"]):
            setup_script.main()
        config = json.loads(mcp_dir.read_text())
        url = config["mcpServers"]["zenos"]["url"]
        assert "project=proj" in url

    def test_update_with_project(self, mcp_dir: Path):
        # First create existing config
        setup_script.setup_cloud("tok", "https://example.com/mcp")
        with patch("sys.argv", ["setup.py", "--update", "--project", "myproj"]):
            setup_script.main()
        config = json.loads(mcp_dir.read_text())
        url = config["mcpServers"]["zenos"]["url"]
        assert "project=myproj" in url
        assert "api_key=tok" in url
