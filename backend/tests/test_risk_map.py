"""/api/v1/risk-map, /api/v1/risk-map/{sido} 엔드포인트 테스트.

risk_data 서비스는 24MB대 화재 CSV를 요청마다 파싱하면 응답이 1초 이상
걸리던 문제가 있어 캐싱으로 고쳤다. 응답 형태뿐 아니라 CSV 파싱이
프로세스당 1회만 일어나는지(캐시가 실제로 동작하는지)도 함께 검증한다.
"""

from fastapi.testclient import TestClient

from app.main import app
import app.services.risk_data as rd

client = TestClient(app)


def test_get_risk_map_returns_all_sido_sorted_by_report_count():
    body = client.get("/api/v1/risk-map").json()

    assert body["zones"]
    assert body["total_count"] == sum(z["report_count"] for z in body["zones"])

    report_counts = [z["report_count"] for z in body["zones"]]
    assert report_counts == sorted(report_counts, reverse=True)

    for zone in body["zones"]:
        assert zone["region_name"] in rd.SIDO_COORDS
        assert 0 <= zone["risk_score"] <= 100


def test_get_sigungu_detail_for_known_sido():
    sido = "서울특별시"
    body = client.get(f"/api/v1/risk-map/{sido}").json()

    assert body["sido"] == sido
    assert (body["lat"], body["lng"]) == rd.SIDO_COORDS[sido]
    assert body["items"]
    for item in body["items"]:
        assert 0 <= item["risk_score"] <= 100


def test_get_sigungu_detail_for_unknown_sido_falls_back_to_default_coords():
    body = client.get("/api/v1/risk-map/존재하지않는시도").json()

    assert body["items"] == []
    assert (body["lat"], body["lng"]) == (36.5, 127.8)


def test_fire_csv_is_parsed_only_once_across_repeated_requests():
    """캐시가 걷히면 지도 클릭 한 번마다 CSV 재파싱이 부활하는 회귀를 잡는다."""
    rd._load_recent_fire_df.cache_clear()
    before = rd._load_recent_fire_df.cache_info()

    rd.load_risk_zones()
    rd.load_sigungu_zones("서울특별시")
    rd.load_sigungu_zones("부산광역시")

    after = rd._load_recent_fire_df.cache_info()
    assert after.misses == before.misses + 1
    assert after.hits >= 2


def test_business_csv_is_parsed_only_once_across_repeated_requests():
    rd._load_business_df.cache_clear()
    before = rd._load_business_df.cache_info()

    rd.load_risk_zones()
    rd.load_risk_zones()

    after = rd._load_business_df.cache_info()
    assert after.misses == before.misses + 1
    assert after.hits >= 1
