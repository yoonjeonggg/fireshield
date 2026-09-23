from fastapi import APIRouter, Response

from app.schemas.risk_map import (
    RiskMapResponse,
    RiskZone,
    SigunguDetail,
    SigunguDetailResponse,
)
from app.services.risk_data import SIDO_COORDS, load_risk_zones, load_sigungu_zones

router = APIRouter(prefix="/api/v1", tags=["risk-map"])

# 배포 시점에 고정되는 정적 데이터 — 브라우저가 재방문/재클릭 시 네트워크를 타지 않도록 캐시 허용
CACHE_CONTROL = "public, max-age=3600"


# pandas 집계는 CPU 바운드 동기 코드라 async def로 두면 캐시 미스(콜드) 시 이벤트 루프 전체가 멈춘다.
# 일반 def로 선언해 FastAPI가 스레드풀에서 실행하도록 한다.
@router.get(
    "/risk-map",
    response_model=RiskMapResponse,
    summary="지역별 사칭 위험도 지도 데이터",
    description=(
        "소방청 전국 화재 현황(2025) 데이터를 시도 단위로 집계한 위험지역 데이터입니다. "
        "좌표는 시/도청 소재지 기준이며, 실제 화재 발생 지점과는 다를 수 있습니다."
    ),
)
def get_risk_map(response: Response):
    response.headers["Cache-Control"] = CACHE_CONTROL
    zones = [RiskZone(**z) for z in load_risk_zones()]
    return RiskMapResponse(
        total_count=sum(z.report_count for z in zones),
        zones=zones,
    )


@router.get(
    "/risk-map/{sido}",
    response_model=SigunguDetailResponse,
    summary="특정 시도의 시군구별 화재 상세",
)
def get_sigungu_detail(sido: str, response: Response):
    response.headers["Cache-Control"] = CACHE_CONTROL
    lat, lng = SIDO_COORDS.get(sido, (36.5, 127.8))
    return SigunguDetailResponse(
        sido=sido,
        lat=lat,
        lng=lng,
        items=[SigunguDetail(**i) for i in load_sigungu_zones(sido)],
    )
