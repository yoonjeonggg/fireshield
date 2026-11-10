"""진위확인 로그 보관 기간 정리(purge_expired_logs) 테스트.

DB는 임시 파일 sqlite로 격리한다 (NullPool — 이벤트 루프 간 커넥션 공유 회피).
"""

import asyncio
import os
import tempfile
from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool

from app.core.config import Settings
from app.models.verify_log import Base, VerifyLog
from app.services.log_retention import purge_expired_logs

_db_fd, _db_path = tempfile.mkstemp(suffix=".db")
os.close(_db_fd)
_engine = create_async_engine(
    f"sqlite+aiosqlite:///{_db_path}", future=True, poolclass=NullPool
)
_Session = async_sessionmaker(_engine, expire_on_commit=False)


def setup_module(module):
    async def _create():
        async with _engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    asyncio.run(_create())


def teardown_module(module):
    async def _dispose():
        await _engine.dispose()

    asyncio.run(_dispose())
    try:
        os.unlink(_db_path)
    except OSError:
        pass


async def _insert(created_at):
    async with _Session() as session:
        session.add(VerifyLog(claimed_org="기관", risk_level="danger", score=80, created_at=created_at))
        await session.commit()


async def _count():
    async with _Session() as session:
        return (await session.execute(select(func.count()).select_from(VerifyLog))).scalar_one()


def test_purge_deletes_only_logs_past_retention():
    now = datetime(2026, 11, 9, tzinfo=timezone.utc)

    async def _run():
        await _insert(now - timedelta(days=181))  # 만료
        await _insert(now - timedelta(days=400))  # 만료
        await _insert(now - timedelta(days=179))  # 보관
        await _insert(now - timedelta(days=1))    # 보관
        async with _Session() as session:
            deleted = await purge_expired_logs(session, retention_days=180, now=now)
        return deleted, await _count()

    deleted, remaining = asyncio.run(_run())
    assert deleted == 2
    assert remaining == 2


def test_purge_with_nothing_expired_is_noop():
    now = datetime(2026, 11, 9, tzinfo=timezone.utc)

    async def _run():
        before = await _count()
        async with _Session() as session:
            deleted = await purge_expired_logs(session, retention_days=10_000, now=now)
        return deleted, before, await _count()

    deleted, before, after = asyncio.run(_run())
    assert deleted == 0
    assert before == after


def test_retention_shorter_than_fraud_window_is_rejected():
    # 보관 기간이 집계 기간보다 짧으면 사기 이력 집계가 조용히 깨지므로 기동 단계에서 막는다
    with pytest.raises(ValidationError, match="VERIFY_LOG_RETENTION_DAYS"):
        Settings(verify_log_retention_days=30, fraud_check_window_days=90)
