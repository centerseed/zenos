"""Tests for MCP scope enforcement.

Validates that require_scope decorator:
- Blocks calls when the JWT credential lacks the required scope.
- Allows calls when the scope is present.
- Always allows calls when _current_scopes is None (API key path).
"""

from __future__ import annotations

from contextvars import copy_context
from typing import Any

import pytest

from zenos.interface.mcp._scope import require_scope, TOOL_SCOPE_MAP
from zenos.interface.mcp._auth import _current_scopes


# ──────────────────────────────────────────────
# Fake tool functions for testing
# ──────────────────────────────────────────────

async def _fake_read_tool():
    return {"status": "ok", "data": "read result"}


async def _fake_write_tool():
    return {"status": "ok", "data": "write result"}


async def _fake_task_tool():
    return {"status": "ok", "data": "task result"}


read_tool = require_scope("read")(_fake_read_tool)
write_tool = require_scope("write")(_fake_write_tool)
task_tool = require_scope("task")(_fake_task_tool)


# ──────────────────────────────────────────────
# Tests
# ──────────────────────────────────────────────

class TestRequireScopeDecorator:
    async def test_api_key_path_no_scope_restriction(self) -> None:
        """When _current_scopes is None (API key path), all tools are accessible."""
        # Default ContextVar value is None — simulates API key path
        result = await read_tool()
        assert result["status"] == "ok"

    async def test_jwt_with_read_scope_can_call_read_tool(self) -> None:
        token = _current_scopes.set({"read"})
        try:
            result = await read_tool()
            assert result["status"] == "ok"
        finally:
            _current_scopes.reset(token)

    async def test_jwt_without_write_scope_cannot_call_write_tool(self) -> None:
        token = _current_scopes.set({"read"})
        try:
            result = await write_tool()
            assert result["status"] == "error"
            assert result["data"]["error"] == "FORBIDDEN"
            assert "write" in result["data"]["message"]
        finally:
            _current_scopes.reset(token)

    async def test_jwt_without_task_scope_cannot_call_task_tool(self) -> None:
        token = _current_scopes.set({"read", "write"})
        try:
            result = await task_tool()
            assert result["status"] == "error"
            assert result["data"]["error"] == "FORBIDDEN"
        finally:
            _current_scopes.reset(token)

    async def test_jwt_with_all_scopes_can_call_any_tool(self) -> None:
        token = _current_scopes.set({"read", "write", "task"})
        try:
            assert (await read_tool())["status"] == "ok"
            assert (await write_tool())["status"] == "ok"
            assert (await task_tool())["status"] == "ok"
        finally:
            _current_scopes.reset(token)

    async def test_empty_scopes_set_blocks_all(self) -> None:
        token = _current_scopes.set(set())
        try:
            result = await read_tool()
            assert result["status"] == "error"
        finally:
            _current_scopes.reset(token)

    async def test_forbidden_response_contains_granted_scopes(self) -> None:
        """The error message must tell the caller what scopes they actually have."""
        token = _current_scopes.set({"read"})
        try:
            result = await write_tool()
            assert "read" in result["warnings"][0]
        finally:
            _current_scopes.reset(token)


class TestToolScopeMap:
    """Verify TOOL_SCOPE_MAP covers expected tool categories."""

    def test_read_tools_present(self) -> None:
        read_tools = ["search", "get", "read_source", "common_neighbors", "find_gaps",
                      "governance_guide", "journal_read", "analyze", "setup", "suggest_policy"]
        for tool in read_tools:
            assert tool in TOOL_SCOPE_MAP, f"Missing read tool: {tool}"
            assert TOOL_SCOPE_MAP[tool] == "read"

    def test_write_tools_present(self) -> None:
        write_tools = ["write", "confirm", "batch_update_sources", "upload_attachment", "journal_write"]
        for tool in write_tools:
            assert tool in TOOL_SCOPE_MAP, f"Missing write tool: {tool}"
            assert TOOL_SCOPE_MAP[tool] == "write"

    def test_task_tools_present(self) -> None:
        task_tools = ["task", "plan"]
        for tool in task_tools:
            assert tool in TOOL_SCOPE_MAP, f"Missing task tool: {tool}"
            assert TOOL_SCOPE_MAP[tool] == "task"
