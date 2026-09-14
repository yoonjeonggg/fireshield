from datetime import date, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.verify_log import VerifyLog
from app.schemas.admin import RiskLevelStats
from app.schemas.public_stats import (
    DailyTrendPoint,
    PublicStatsResponse,
    RecentAlert,
    TopClaimedOrg,
)

router = APIRouter(prefix="/api/v1/public", tags=["public"])

TREND_DAYS = 14


@router.get(
    "/stats",
    response_model=PublicStatsResponse,
    summary="[공개] 진위확인 통계 요약",
    description="누구나 조회 가능한 집계 통계입니다. 계좌번호·담당자명·대상 업체명 등 개인정보는 노출하지 않습니다.",
)
async def get_public_stats(db: AsyncSession = Depends(get_db)):
    total_result = await db.execute(select(func.count()).select_from(VerifyLog))
    total = total_result.scalar_one()

    async def count_by_level(level: str) -> int:
        result = await db.execute(
            select(func.count()).select_from(VerifyLog).where(VerifyLog.risk_level == level)
        )
        return result.scalar_one()

    risk_level_stats = RiskLevelStats(
        safe=await count_by_level("safe"),
        caution=await count_by_level("caution"),
        danger=await count_by_level("danger"),
        unverified=await count_by_level("unverified"),
    )

    since = date.today() - timedelta(days=TREND_DAYS - 1)
    day_col = func.date(VerifyLog.created_at)
    trend_result = await db.execute(
        select(
            day_col.label("day"),
            func.count().label("total"),
            func.count().filter(VerifyLog.risk_level == "safe").label("safe"),
            func.count().filter(VerifyLog.risk_level == "caution").label("caution"),
            func.count().filter(VerifyLog.risk_level == "danger").label("danger"),
            func.count().filter(VerifyLog.risk_level == "unverified").label("unverified"),
        )
        .where(day_col >= since)
        .group_by(day_col)
        .order_by(day_col)
    )
    # dialect에 따라 func.date()가 date 객체(Postgres) 또는 문자열(SQLite)을 반환하므로
    # 키를 ISO 문자열로 통일해서 비교한다.
    empty_day = {"total": 0, "safe": 0, "caution": 0, "danger": 0, "unverified": 0}
    trend_by_day = {
        (row.day.isoformat() if isinstance(row.day, date) else str(row.day)): {
            "total": row.total,
            "safe": row.safe,
            "caution": row.caution,
            "danger": row.danger,
            "unverified": row.unverified,
        }
        for row in trend_result.all()
    }
    daily_trend = [
        DailyTrendPoint(date=d, **trend_by_day.get(d.isoformat(), empty_day))
        for d in (since + timedelta(days=i) for i in range(TREND_DAYS))
    ]

    top_orgs_result = await db.execute(
        select(VerifyLog.claimed_org, func.count().label("count"))
        .where(VerifyLog.claimed_org.isnot(None))
        .where(VerifyLog.risk_level.in_(["caution", "danger"]))
        .group_by(VerifyLog.claimed_org)
        .order_by(func.count().desc())
        .limit(5)
    )
    top_claimed_orgs = [
        TopClaimedOrg(org=row.claimed_org, count=row.count) for row in top_orgs_result.all()
    ]

    recent_result = await db.execute(
        select(
            VerifyLog.claimed_org,
            VerifyLog.claim_type,
            VerifyLog.risk_level,
            VerifyLog.created_at,
        )
        .where(VerifyLog.risk_level == "danger")
        .order_by(VerifyLog.created_at.desc())
        .limit(10)
    )
    recent_alerts = [
        RecentAlert(
            claimed_org=row.claimed_org,
            claim_type=row.claim_type,
            risk_level=row.risk_level,
            created_at=row.created_at,
        )
        for row in recent_result.all()
    ]

    return PublicStatsResponse(
        total_count=total,
        risk_level_stats=risk_level_stats,
        daily_trend=daily_trend,
        top_claimed_orgs=top_claimed_orgs,
        recent_alerts=recent_alerts,
    )
