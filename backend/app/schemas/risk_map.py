from pydantic import BaseModel


class RiskZone(BaseModel):
    region_name: str
    lat: float
    lng: float
    risk_score: float  # 0~100
    report_count: int
    main_targets: str  # 주요 표적 업종 (예: "민박 · 모텔 · 단란주점")


class RiskMapResponse(BaseModel):
    total_count: int
    zones: list[RiskZone]

class SigunguDetail(BaseModel):
    sigungu_name: str
    report_count: int
    risk_score: float


class SigunguDetailResponse(BaseModel):
    sido: str
    lat: float
    lng: float  # 지도 확대 중심점 (시도 좌표 재사용)
    items: list[SigunguDetail]