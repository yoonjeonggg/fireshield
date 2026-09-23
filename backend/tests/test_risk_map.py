"""/api/v1/risk-map, /api/v1/risk-map/{sido} 엔드포인트 테스트.

risk_data 서비스는 24MB대 화재 CSV 파싱과 시도/시군구 집계를 프로세스당
1회만 수행하고 결과를 캐시한다. 응답 형태뿐 아니라 캐시가 실제로 동작하는지,
공유 캐시가 호출자에 의해 오염되지 않는지도 함께 검증한다.
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


def _clear_risk_caches():
    for fn in (rd._load_recent_fire_df, rd._load_business_df, rd._risk_zones, rd._sigungu_index):
        fn.cache_clear()


def test_csv_parsing_and_aggregation_run_once_across_repeated_requests():
    """캐시가 걷히면 지도 클릭 한 번마다 CSV 재파싱/재집계가 부활하는 회귀를 잡는다."""
    _clear_risk_caches()

    for _ in range(3):
        client.get("/api/v1/risk-map")
        client.get("/api/v1/risk-map/서울특별시")
        client.get("/api/v1/risk-map/부산광역시")

    for fn in (rd._load_recent_fire_df, rd._load_business_df, rd._risk_zones, rd._sigungu_index):
        assert fn.cache_info().misses == 1, fn.__name__


def test_unknown_sido_does_not_grow_cache():
    """임의 경로값마다 캐시 엔트리가 쌓이면 메모리가 무한히 늘 수 있다."""
    rd.load_sigungu_zones("서울특별시")
    before = rd._sigungu_index.cache_info().currsize

    for i in range(20):
        client.get(f"/api/v1/risk-map/없는시도{i}")

    assert rd._sigungu_index.cache_info().currsize == before


def test_returned_data_is_a_copy_not_the_shared_cache():
    zones = rd.load_risk_zones()
    zones[0]["risk_score"] = -1
    zones.clear()

    fresh = rd.load_risk_zones()
    assert fresh and fresh[0]["risk_score"] != -1


def test_sigungu_scores_are_normalized_within_each_sido():
    for sido in ("서울특별시", "경기도"):
        items = rd.load_sigungu_zones(sido)
        scores = [i["risk_score"] for i in items]
        assert max(scores) == 100.0 and min(scores) == 0.0
        counts = [i["report_count"] for i in items]
        assert counts == sorted(counts, reverse=True)


def test_risk_map_responses_are_browser_cacheable():
    for path in ("/api/v1/risk-map", "/api/v1/risk-map/서울특별시"):
        assert "max-age" in client.get(path).headers["cache-control"]
