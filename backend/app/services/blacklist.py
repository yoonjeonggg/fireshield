from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.blacklist import BlacklistEntry


async def is_blacklisted(db: AsyncSession, entry_type: str, name: str) -> BlacklistEntry | None:
    """이름이 블랙리스트에 부분일치로 등록되어 있는지 확인합니다."""
    if not name:
        return None
    stmt = select(BlacklistEntry).where(
        BlacklistEntry.entry_type == entry_type,
        BlacklistEntry.name.ilike(f"%{name}%"),
    )
    result = await db.execute(stmt)
    return result.scalars().first()