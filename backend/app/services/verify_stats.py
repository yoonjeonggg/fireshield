from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.verify_log import VerifyLog
from app.schemas.admin import RiskLevelStats


async def get_verify_log_totals(db: AsyncSession) -> tuple[int, RiskLevelStats]:
    """진위확인 로그 전체 건수와 위험도별 건수를 한 번의 쿼리로 집계한다."""
    row = (
        await db.execute(
            select(
                func.count().label("total"),
                *(
                    func.count().filter(VerifyLog.risk_level == level).label(level)
                    for level in RiskLevelStats.model_fields
                ),
            ).select_from(VerifyLog)
        )
    ).one()
    stats = RiskLevelStats(**{level: getattr(row, level) for level in RiskLevelStats.model_fields})
    return row.total, stats
