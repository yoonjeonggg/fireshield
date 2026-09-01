from fastapi import APIRouter
from app.schemas.risk_map import RiskMapResponse, RiskZone
from app.services.risk_data import load_risk_zones
from app.schemas.risk_map import SigunguDetailResponse, SigunguDetail
from app.services.risk_data import load_sigungu_zones, SIDO_COORDS

router = APIRouter(prefix="/api/v1", tags=["risk-map"])


@router.get(
    "/risk-map",
    response_model=RiskMapResponse,
    summary="지역별 사칭 위험도 지도 데이터",
    description=(
        "소방청 전국 화재 현황(2025) 데이터를 시도 단위로 집계한 위험지역 데이터입니다. "
        "좌표는 시/도청 소재지 기준이며, 실제 화재 발생 지점과는 다를 수 있습니다."
    ),
)
async def get_risk_map():
    zones_data = load_risk_zones()
    zones = [RiskZone(**z) for z in zones_data]

    return RiskMapResponse(
        total_count=sum(z.report_count for z in zones),
        zones=zones,
    )

@router.get(
    "/risk-map/{sido}",
    response_model=SigunguDetailResponse,
    summary="특정 시도의 시군구별 화재 상세",
)
async def get_sigungu_detail(sido: str):
    items = load_sigungu_zones(sido)
    lat, lng = SIDO_COORDS.get(sido, (36.5, 127.8))
    return SigunguDetailResponse(
        sido=sido,
        lat=lat,
        lng=lng,
        items=[SigunguDetail(**i) for i in items],
    )