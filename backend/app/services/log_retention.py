"""진위확인 로그 보관 기간 관리.

verify_logs에는 암호화된 계좌번호와 요청자 지문이 남으므로, 계좌 사기 이력
집계에 필요한 기간(fraud_check_window_days)을 넘겨 무기한 보관하지 않는다.
보관 기간이 지난 로그는 서버 기동 시와 이후 하루 간격으로 삭제한다.
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import settings
from app.models.verify_log import VerifyLog

logger = logging.getLogger("fireshield.retention")

PURGE_INTERVAL_SECONDS = 24 * 60 * 60


async def purge_expired_logs(
    db: AsyncSession, retention_days: int | None = None, now: datetime | None = None
) -> int:
    """보관 기간이 지난 진위확인 로그를 삭제하고 삭제 건수를 반환한다."""
    days = settings.verify_log_retention_days if retention_days is None else retention_days
    cutoff = (now or datetime.now(timezone.utc)) - timedelta(days=days)
    result = await db.execute(delete(VerifyLog).where(VerifyLog.created_at < cutoff))
    await db.commit()
    return result.rowcount or 0


async def run_retention_loop(session_factory: async_sessionmaker[AsyncSession]) -> None:
    """서버가 떠 있는 동안 하루 간격으로 만료 로그를 정리한다 (실패해도 다음 주기에 재시도)."""
    while True:
        try:
            async with session_factory() as db:
                deleted = await purge_expired_logs(db)
            if deleted:
                logger.info("보관 기간(%d일)이 지난 진위확인 로그 %d건 삭제", settings.verify_log_retention_days, deleted)
        except Exception:
            logger.exception("진위확인 로그 정리 실패 — 다음 주기에 재시도")
        await asyncio.sleep(PURGE_INTERVAL_SECONDS)
