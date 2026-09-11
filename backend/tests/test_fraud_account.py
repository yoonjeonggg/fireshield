from datetime import datetime, timedelta, timezone

import pytest

from app.core.config import settings
from app.core.crypto import account_fingerprint
from app.models.verify_log import VerifyLog
from app.services.fraud_account import SelfReportProvider


async def _insert_log(db_session, account_hash, risk_level, created_at=None):
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
    db_session.add(log)
    await db_session.commit()


async def test_no_account_hash_is_not_checked(db_session):
    provider = SelfReportProvider(db_session)
    result = await provider.check(None)
    assert result.checked is False
    assert result.reported is False
    assert result.report_count == 0


async def test_unknown_account_has_no_reports(db_session):
    provider = SelfReportProvider(db_session)
    result = await provider.check(account_fingerprint("999888777"))
    assert result.checked is True
    assert result.reported is False
    assert result.report_count == 0


async def test_below_threshold_is_not_reported(db_session):
    account_hash = account_fingerprint("111122223333")
    await _insert_log(db_session, account_hash, "danger")
    await _insert_log(db_session, account_hash, "caution")

    provider = SelfReportProvider(db_session)
    result = await provider.check(account_hash)

    assert result.report_count == 2
    assert result.reported is False  # 임계치(기본 3건) 미만


async def test_meets_threshold_is_reported(db_session):
    account_hash = account_fingerprint("111122223333")
    for _ in range(settings.fraud_check_report_threshold):
        await _insert_log(db_session, account_hash, "danger")

    provider = SelfReportProvider(db_session)
    result = await provider.check(account_hash)

    assert result.report_count == settings.fraud_check_report_threshold
    assert result.reported is True


async def test_safe_verdicts_do_not_count_toward_reports(db_session):
    # 안전 판정으로 끝난 조회는 정상 계좌를 확인했을 수 있으므로 집계에서 제외한다.
    account_hash = account_fingerprint("111122223333")
    for _ in range(5):
        await _insert_log(db_session, account_hash, "safe")

    provider = SelfReportProvider(db_session)
    result = await provider.check(account_hash)

    assert result.report_count == 0
    assert result.reported is False


async def test_old_reports_outside_window_are_excluded(db_session):
    account_hash = account_fingerprint("111122223333")
    stale = datetime.now(timezone.utc) - timedelta(days=settings.fraud_check_window_days + 1)
    for _ in range(5):
        await _insert_log(db_session, account_hash, "danger", created_at=stale)

    provider = SelfReportProvider(db_session)
    result = await provider.check(account_hash)

    assert result.report_count == 0
    assert result.reported is False


async def test_different_accounts_are_not_conflated(db_session):
    hash_a = account_fingerprint("111122223333")
    hash_b = account_fingerprint("444455556666")
    for _ in range(settings.fraud_check_report_threshold):
        await _insert_log(db_session, hash_a, "danger")

    provider = SelfReportProvider(db_session)
    result = await provider.check(hash_b)

    assert result.report_count == 0
    assert result.reported is False
