import uuid

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.blacklist import BlacklistEntry
from app.schemas.blacklist import BlacklistCreateRequest, BlacklistEntryResponse, BlacklistListResponse
from app.core.database import get_db
from app.core.admin_auth import verify_admin_key
from app.models.verify_log import VerifyLog
from app.schemas.admin import (
    VerifyLogListResponse,
    VerifyLogSummary,
    AdminStatsResponse,
    RiskLevelStats,
)

router = APIRouter(prefix="/api/v1/admin", tags=["admin"], dependencies=[Depends(verify_admin_key)])


def _to_summary(log: VerifyLog) -> VerifyLogSummary:
    return VerifyLogSummary(
        id=str(log.id),
        claimed_org=log.claimed_org,
        claimed_person=log.claimed_person,
        claim_type=log.claim_type,
        target_business=log.target_business,
        has_account_number=log.account_number is not None,
        risk_level=log.risk_level,
        score=log.score,
        created_at=log.created_at,
    )


@router.get(
    "/verify-logs",
    response_model=VerifyLogListResponse,
    summary="[관리자] 진위확인 조회 로그 목록",
    description="계좌번호 등 개인정보는 마스킹되어 노출되지 않습니다. `X-Admin-Key` 헤더 필요.",
)
async def list_verify_logs(
    db: AsyncSession = Depends(get_db),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    total_result = await db.execute(select(func.count()).select_from(VerifyLog))
    total = total_result.scalar_one()

    result = await db.execute(
        select(VerifyLog).order_by(VerifyLog.created_at.desc()).limit(limit).offset(offset)
    )
    logs = result.scalars().all()

    return VerifyLogListResponse(
        total=total,
        items=[_to_summary(log) for log in logs],
    )


@router.get(
    "/stats",
    response_model=AdminStatsResponse,
    summary="[관리자] 진위확인 통계 요약",
    description="위험도별 건수와 최근 로그 10건을 반환합니다. `X-Admin-Key` 헤더 필요.",
)
async def get_stats(db: AsyncSession = Depends(get_db)):
    total_result = await db.execute(select(func.count()).select_from(VerifyLog))
    total = total_result.scalar_one()

    async def count_by_level(level: str) -> int:
        result = await db.execute(
            select(func.count()).select_from(VerifyLog).where(VerifyLog.risk_level == level)
        )
        return result.scalar_one()

    safe_count = await count_by_level("safe")
    caution_count = await count_by_level("caution")
    danger_count = await count_by_level("danger")

    recent_result = await db.execute(
        select(VerifyLog).order_by(VerifyLog.created_at.desc()).limit(10)
    )
    recent_logs = recent_result.scalars().all()

    return AdminStatsResponse(
        total_count=total,
        risk_level_stats=RiskLevelStats(safe=safe_count, caution=caution_count, danger=danger_count),
        recent_logs=[_to_summary(log) for log in recent_logs],
    )

@router.get(
    "/blacklist",
    response_model=BlacklistListResponse,
    summary="[관리자] 블랙리스트 목록 조회",
)
async def list_blacklist(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(BlacklistEntry).order_by(BlacklistEntry.created_at.desc()))
    items = result.scalars().all()
    return BlacklistListResponse(
        items=[
            BlacklistEntryResponse(
                id=str(item.id),
                entry_type=item.entry_type,
                name=item.name,
                reason=item.reason,
                created_at=item.created_at,
            )
            for item in items
        ]
    )


@router.post(
    "/blacklist",
    response_model=BlacklistEntryResponse,
    summary="[관리자] 블랙리스트 항목 추가",
)
async def create_blacklist_entry(payload: BlacklistCreateRequest, db: AsyncSession = Depends(get_db)):
    entry = BlacklistEntry(
        entry_type=payload.entry_type,
        name=payload.name,
        reason=payload.reason,
    )
    db.add(entry)
    await db.commit()
    await db.refresh(entry)
    return BlacklistEntryResponse(
        id=str(entry.id),
        entry_type=entry.entry_type,
        name=entry.name,
        reason=entry.reason,
        created_at=entry.created_at,
    )


@router.delete(
    "/blacklist/{entry_id}",
    summary="[관리자] 블랙리스트 항목 삭제",
)
async def delete_blacklist_entry(entry_id: str, db: AsyncSession = Depends(get_db)):
    try:
        parsed_id = uuid.UUID(entry_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="해당 항목을 찾을 수 없습니다.")

    entry = await db.get(BlacklistEntry, parsed_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="해당 항목을 찾을 수 없습니다.")
    await db.delete(entry)
    await db.commit()
    return {"deleted": True}