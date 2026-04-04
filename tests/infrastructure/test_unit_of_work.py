import pytest
from unittest.mock import AsyncMock, MagicMock
from zenos.infrastructure.unit_of_work import UnitOfWork


def _make_pool_and_conn():
    pool = MagicMock()
    conn = MagicMock()
    tx = AsyncMock()
    conn.transaction.return_value = tx
    pool.acquire = AsyncMock(return_value=conn)
    pool.release = AsyncMock()
    return pool, conn, tx


@pytest.mark.asyncio
async def test_commit_on_success():
    pool, conn, tx = _make_pool_and_conn()

    async with UnitOfWork(pool) as uow:
        assert uow.conn is conn

    tx.start.assert_awaited_once()
    tx.commit.assert_awaited_once()
    tx.rollback.assert_not_awaited()
    pool.release.assert_awaited_once_with(conn)


@pytest.mark.asyncio
async def test_rollback_on_exception():
    pool, conn, tx = _make_pool_and_conn()

    with pytest.raises(ValueError):
        async with UnitOfWork(pool) as uow:
            raise ValueError("test error")

    tx.start.assert_awaited_once()
    tx.rollback.assert_awaited_once()
    tx.commit.assert_not_awaited()
    pool.release.assert_awaited_once_with(conn)


@pytest.mark.asyncio
async def test_conn_released_after_exit():
    pool, conn, tx = _make_pool_and_conn()

    async with UnitOfWork(pool) as uow:
        pass

    assert uow.conn is None
