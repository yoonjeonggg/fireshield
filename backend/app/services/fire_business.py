from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.fire_business import FireBusiness


async def find_business_by_name(db: AsyncSession, business_name: str) -> list[FireBusiness]:
    """
    업체명으로 fire_businesses 테이블을 부분 일치 검색합니다.

    Args:
        db: DB 세션
        business_name: 검색할 업체명 (예: "강남소방")

    Returns:
        일치하는 FireBusiness 레코드 리스트 (최대 5건)
    """
    stmt = (
        select(FireBusiness)
        .where(FireBusiness.company_name.ilike(f"%{business_name}%"))
        .limit(5)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())