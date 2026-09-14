from datetime import date, datetime

from pydantic import BaseModel

from app.schemas.admin import RiskLevelStats


class DailyTrendPoint(BaseModel):
    date: date
    total: int
    safe: int
    caution: int
    danger: int
    unverified: int


class TopClaimedOrg(BaseModel):
    org: str
    count: int


class RecentAlert(BaseModel):
    claimed_org: str | None
    claim_type: str | None
    risk_level: str | None
    created_at: datetime


class PublicStatsResponse(BaseModel):
    total_count: int
    risk_level_stats: RiskLevelStats
    daily_trend: list[DailyTrendPoint]
    top_claimed_orgs: list[TopClaimedOrg]
    recent_alerts: list[RecentAlert]
