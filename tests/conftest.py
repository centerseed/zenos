"""Shared test helpers and fixtures."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock


class AsyncContextManager:
    """Mock async context manager that is also awaitable (like asyncpg PoolAcquireContext)."""

    def __init__(self, value):
        self._value = value

    async def __aenter__(self):
        return self._value

    async def __aexit__(self, *args):
        pass

    def __await__(self):
        return self._await_impl().__await__()

    async def _await_impl(self):
        return self._value
