"""UnitOfWork — cross-repository transaction scope.

Usage:
    async with UnitOfWork(pool) as uow:
        await repo_a.some_write(data, conn=uow.conn)
        await repo_b.some_write(data, conn=uow.conn)
    # auto-commit on success, auto-rollback on exception
"""
from __future__ import annotations

import asyncpg


class UnitOfWork:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool
        self.conn: asyncpg.Connection | None = None
        self._tx = None

    async def __aenter__(self) -> UnitOfWork:
        self.conn = await self._pool.acquire()
        self._tx = self.conn.transaction()
        await self._tx.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        try:
            if exc_type is None:
                await self._tx.commit()
            else:
                await self._tx.rollback()
        finally:
            await self._pool.release(self.conn)
            self.conn = None
