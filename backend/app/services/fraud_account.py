"""
계좌번호 사기 신고 이력 조회 서비스.

경찰청 '사이버사기 피해신고 이력조회'는 최근 3개월간 3회 이상 사이버범죄
신고시스템에 접수된 계좌/전화번호를 알려주는 서비스지만, 공식 오픈 API가
없어 서버 대 서버 연동이 불가능하다. (조회 폼은 자동입력방지문자로 보호됨)

그래서 두 갈래로 접근한다.

  1. SelfReportProvider — FireShield 자체 진위확인 로그(verify_logs)에서 같은
     계좌번호가 기간 내 반복해서 '위험/의심'으로 조회된 횟수를 집계해 신고
     이력처럼 활용한다. 외부 의존/비용/약관 문제가 없다.
  2. 결과 화면에서 경찰청·더치트 공식 조회 페이지로 딥링크를 제공해 사용자가
     직접 최종 확인하도록 안내한다. (프론트엔드에서 처리)

향후 더치트 OpenAPI 등 상용 서비스와 계약하면 Provider 구현체만 교체하면 된다.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Protocol

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.verify_log import VerifyLog

SELF_REPORT_SOURCE = "FireShield 자체 신고 이력"


@dataclass
class FraudAccountResult:
    checked: bool       # 실제로 조회를 수행했는지 (계좌번호 미입력 시 False)
    reported: bool      # 임계치 이상 반복 신고 이력이 있는지
    report_count: int   # 집계된 신고(의심 조회) 횟수
    window_days: int    # 집계 기간(일)
    source: str         # 데이터 출처 설명


class FraudAccountProvider(Protocol):
    async def check(self, account_hash: str | None) -> FraudAccountResult: ...


class NullProvider:
    """조회 수단이 아예 없을 때 쓰는 기본 provider."""

    async def check(self, account_hash: str | None) -> FraudAccountResult:
        return FraudAccountResult(
            checked=False,
            reported=False,
            report_count=0,
            window_days=settings.fraud_check_window_days,
            source="계좌 사기 이력 조회 수단 없음",
        )


class SelfReportProvider:
    """
    FireShield 자체 진위확인 로그를 신고 데이터로 활용한다.

    같은 계좌번호로 '위험/의심' 판정이 기간 내 N건 이상 쌓였다면, 그만큼 여러
    사람이 '이 계좌로 송금하라'는 요구를 받고 의심했다는 뜻이므로 사기 계좌일
    가능성이 높다. (안전 판정으로 끝난 조회는 정상 계좌를 확인한 것일 수 있어
    집계에서 제외한다.)
    """

    RISKY_LEVELS = ("caution", "danger")

    def __init__(self, db: AsyncSession):
        self._db = db

    async def check(self, account_hash: str | None) -> FraudAccountResult:
        window_days = settings.fraud_check_window_days
        threshold = settings.fraud_check_report_threshold

        if not account_hash:
            return FraudAccountResult(
                checked=False,
                reported=False,
                report_count=0,
                window_days=window_days,
                source=SELF_REPORT_SOURCE,
            )

        cutoff = datetime.now(timezone.utc) - timedelta(days=window_days)
        stmt = (
            select(func.count())
            .select_from(VerifyLog)
            .where(
                VerifyLog.account_hash == account_hash,
                VerifyLog.created_at >= cutoff,
                VerifyLog.risk_level.in_(self.RISKY_LEVELS),
            )
        )
        count = int((await self._db.execute(stmt)).scalar_one())

        return FraudAccountResult(
            checked=True,
            reported=count >= threshold,
            report_count=count,
            window_days=window_days,
            source=SELF_REPORT_SOURCE,
        )


def get_fraud_account_provider(db: AsyncSession) -> FraudAccountProvider:
    """현재 사용 가능한 계좌 사기 이력 조회 provider를 반환한다."""
    return SelfReportProvider(db)
