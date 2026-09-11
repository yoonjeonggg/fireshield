"""SelfReportProvider(계좌 사기 신고 이력 자체 집계) 단위 테스트.

DB는 임시 파일 sqlite로 격리한다 (NullPool — 이벤트 루프 간 커넥션 공유 회피).
"""

import asyncio
import os
import tempfile
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.core.crypto import account_fingerprint
from app.models.verify_log import Base, VerifyLog
from app.services.fraud_account import SelfReportProvider

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


async def _insert_log(account_hash, risk_level, created_at=None):
    async with _Session() as session:
        log = VerifyLog(
            claimed_org="테스트기관",
            claimed_person="테스트담당자",
            claim_type="테스트",
            target_business="테스트업체",
            account_number=None,
            account_hash=account_hash,
            risk_level=risk_level,
            score=0,
        )
        if created_at is not None:
            log.created_at = created_at
        session.add(log)
        await session.commit()


async def _check(account_hash):
    async with _Session() as session:
        return await SelfReportProvider(session).check(account_hash)


def test_no_account_hash_is_not_checked():
    result = asyncio.run(_check(None))
    assert result.checked is False
    assert result.reported is False
    assert result.report_count == 0


def test_unknown_account_has_no_reports():
    result = asyncio.run(_check(account_fingerprint("999888777")))
    assert result.checked is True
    assert result.reported is False
    assert result.report_count == 0


def test_below_threshold_is_not_reported():
    account_hash = account_fingerprint("110-100-000001")

    async def _run():
        await _insert_log(account_hash, "danger")
        await _insert_log(account_hash, "caution")
        return await _check(account_hash)

    result = asyncio.run(_run())
    assert result.report_count == 2
    assert result.reported is False  # 임계치(기본 3건) 미만


def test_meets_threshold_is_reported():
    account_hash = account_fingerprint("110-100-000002")

    async def _run():
        for _ in range(settings.fraud_check_report_threshold):
            await _insert_log(account_hash, "danger")
        return await _check(account_hash)

    result = asyncio.run(_run())
    assert result.report_count == settings.fraud_check_report_threshold
    assert result.reported is True


def test_safe_verdicts_do_not_count_toward_reports():
    # 안전 판정으로 끝난 조회는 정상 계좌를 확인했을 수 있으므로 집계에서 제외한다.
    account_hash = account_fingerprint("110-100-000003")

    async def _run():
        for _ in range(5):
            await _insert_log(account_hash, "safe")
        return await _check(account_hash)

    result = asyncio.run(_run())
    assert result.report_count == 0
    assert result.reported is False


def test_old_reports_outside_window_are_excluded():
    account_hash = account_fingerprint("110-100-000004")
    stale = datetime.now(timezone.utc) - timedelta(days=settings.fraud_check_window_days + 1)

    async def _run():
        for _ in range(5):
            await _insert_log(account_hash, "danger", created_at=stale)
        return await _check(account_hash)

    result = asyncio.run(_run())
    assert result.report_count == 0
    assert result.reported is False


def test_different_accounts_are_not_conflated():
    hash_a = account_fingerprint("110-100-000005")
    hash_b = account_fingerprint("110-100-000006")

    async def _run():
        for _ in range(settings.fraud_check_report_threshold):
            await _insert_log(hash_a, "danger")
        return await _check(hash_b)

    result = asyncio.run(_run())
    assert result.report_count == 0
    assert result.reported is False
