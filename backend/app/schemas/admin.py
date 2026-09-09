from pydantic import BaseModel
from datetime import datetime


class VerifyLogSummary(BaseModel):
    id: str
    claimed_org: str | None
    claimed_person: str | None
    claim_type: str | None
    target_business: str | None
    has_account_number: bool  # 실제 값은 노출하지 않고 여부만
    risk_level: str | None
    score: int | None
    created_at: datetime

    class Config:
        from_attributes = True


class VerifyLogListResponse(BaseModel):
    total: int
    items: list[VerifyLogSummary]


class RiskLevelStats(BaseModel):
    safe: int
    caution: int
    danger: int
    unverified: int = 0


class AdminStatsResponse(BaseModel):
    total_count: int
    risk_level_stats: RiskLevelStats
    recent_logs: list[VerifyLogSummary]