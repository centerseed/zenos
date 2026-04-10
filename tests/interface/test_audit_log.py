"""Tests for _audit_log() graceful degradation.

Verifies that SQL write failure never propagates to the caller of _audit_log().
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestAuditLogGracefulDegradation:
    """_audit_log() must never raise even when SQL write fails."""

    def test_audit_log_does_not_raise_when_write_fails(self):
        """SQL write failure must not propagate to _audit_log() caller.

        _schedule_audit_sql_write wraps exceptions internally, so _audit_log
        is safe even when the underlying loop.create_task call raises.
        """
        import zenos.interface.mcp._audit as audit_mod

        # Simulate the loop raising when create_task is called
        mock_loop = MagicMock()
        mock_loop.is_running.return_value = True
        mock_loop.create_task.side_effect = RuntimeError("loop error")

        with patch("zenos.interface.mcp._audit.asyncio.get_event_loop", return_value=mock_loop):
            # _schedule_audit_sql_write catches all exceptions, so _audit_log must not raise
            audit_mod._audit_log(
                event_type="task.create",
                target={"collection": "tasks", "id": "task-1"},
                changes={"input": {"title": "Test"}},
            )
        # If we reach here, the test passes

    def test_schedule_audit_sql_write_never_raises(self):
        """_schedule_audit_sql_write() swallows all exceptions."""
        from zenos.interface.mcp import _schedule_audit_sql_write

        # No running event loop scenario — should return silently
        payload = {"partner_id": "p1", "event_type": "task.create"}
        # Should not raise
        _schedule_audit_sql_write(payload)

    async def test_write_audit_event_failure_only_logs_warning(self):
        """_write_audit_event() logs warning on failure, does not raise."""
        import zenos.interface.mcp._audit as audit_mod

        # Reset global _audit_repo so it initializes fresh
        original_repo = audit_mod._audit_repo
        audit_mod._audit_repo = None

        try:
            with patch("zenos.infrastructure.sql_common.get_pool", new_callable=AsyncMock,
                       side_effect=RuntimeError("pool failure")), \
                 patch("zenos.interface.mcp._audit.logger") as mock_logger:
                # Should not raise
                await audit_mod._write_audit_event({
                    "partner_id": "p1",
                    "actor": {"id": "p1"},
                    "event_type": "task.create",
                    "target": {"collection": "tasks", "id": "task-1"},
                    "changes": {},
                })
                mock_logger.warning.assert_called_once()
        finally:
            audit_mod._audit_repo = original_repo

    async def test_write_audit_event_logs_warning_on_repo_failure(self):
        """_write_audit_event() catches repo.create() errors and logs warning."""
        import zenos.interface.mcp._audit as audit_mod

        original_repo = audit_mod._audit_repo
        mock_repo = AsyncMock()
        mock_repo.create = AsyncMock(side_effect=Exception("insert failed"))
        audit_mod._audit_repo = mock_repo

        try:
            with patch("zenos.interface.mcp._audit.logger") as mock_logger:
                await audit_mod._write_audit_event({
                    "partner_id": "p1",
                    "actor": {"id": "p1"},
                    "event_type": "task.create",
                    "target": {"collection": "tasks", "id": "task-1"},
                    "changes": {},
                })
                mock_logger.warning.assert_called_once()
        finally:
            audit_mod._audit_repo = original_repo


class TestAuditLogPayloadShape:
    """Verify _audit_log() builds the correct payload for SQL write."""

    async def test_write_audit_event_maps_payload_to_event(self):
        """_write_audit_event() maps payload fields to event dict correctly."""
        import zenos.interface.mcp._audit as audit_mod

        original_repo = audit_mod._audit_repo
        mock_repo = AsyncMock()
        mock_repo.create = AsyncMock(return_value=None)
        audit_mod._audit_repo = mock_repo

        try:
            await audit_mod._write_audit_event({
                "partner_id": "partner-1",
                "actor": {"id": "actor-1", "name": "Alice", "email": "alice@test.com"},
                "event_type": "task.create",
                "target": {"collection": "tasks", "id": "task-xyz"},
                "changes": {"title": "New"},
                "governance": {},
            })

            mock_repo.create.assert_called_once()
            event = mock_repo.create.call_args.args[0]
            assert event["partner_id"] == "partner-1"
            assert event["actor_id"] == "actor-1"
            assert event["actor_type"] == "partner"
            assert event["operation"] == "task.create"
            assert event["resource_type"] == "tasks"
            assert event["resource_id"] == "task-xyz"
            assert event["changes_json"] == {"title": "New"}
        finally:
            audit_mod._audit_repo = original_repo
