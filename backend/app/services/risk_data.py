"""
위험지역 지도용 실데이터 처리 서비스.
- 소방청 전국 화재 현황(2025)
- 전국 다중이용업소 현황(2023)
두 데이터를 시도 단위로 집계하여 위험도를 계산합니다.
"""
from functools import cache
from pathlib import Path
from datetime import timedelta

import pandas as pd

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
FIRE_CSV_PATH = DATA_DIR / "화재_현황_2025_전국.csv"
BUSINESS_CSV_PATH = DATA_DIR / "다중이용업소_현황_2023_전국.csv"

# 시/도청 소재지 기준 좌표 (17개 광역단체)
SIDO_COORDS = {
    "서울특별시": (37.5665, 126.9780),
    "부산광역시": (35.1796, 129.0756),
    "대구광역시": (35.8714, 128.6014),
    "인천광역시": (37.4563, 126.7052),
    "광주광역시": (35.1595, 126.8526),
    "대전광역시": (36.3504, 127.3845),
    "울산광역시": (35.5384, 129.3114),
    "세종특별자치시": (36.4801, 127.2890),
    "경기도": (37.4138, 127.5183),
    "강원특별자치도": (37.8228, 128.1555),
    "충청북도": (36.6357, 127.4917),
    "충청남도": (36.5184, 126.8000),
    "전북특별자치도": (35.7175, 127.1530),
    "전라남도": (34.8161, 126.4630),
    "경상북도": (36.4919, 128.8889),
    "경상남도": (35.4606, 128.2132),
    "제주특별자치도": (33.4996, 126.5312),
}

# 명칭 변경 전(구) 표기 → 현재 표기 정규화
SIDO_NAME_ALIASES = {
    "전라북도": "전북특별자치도",
    "강원도": "강원특별자치도",
}


def _minmax_score(raw_score: pd.Series) -> pd.Series:
    """원점수를 0~100 구간으로 정규화합니다 (편차가 없으면 전부 0점)."""
    score_range = raw_score.max() - raw_score.min()
    if score_range <= 0:
        return pd.Series(0, index=raw_score.index)
    return ((raw_score - raw_score.min()) / score_range * 100).round(1)


@cache
def _load_recent_fire_df() -> pd.DataFrame:
    """화재 현황 CSV를 읽어 최근 3개월(데이터 내 최신일 기준) 건만 남깁니다.

    파일이 24MB대로 커서 요청마다 파싱하면 지도/드릴다운 응답이 1초 이상 걸린다.
    데이터는 배포 시점에 고정된 정적 파일이므로 프로세스 수명 동안 1회만 읽어 캐시한다.
    """
    df = pd.read_csv(
        FIRE_CSV_PATH,
        encoding="utf-8-sig",
        usecols=["wrinv_no", "dth_cnt", "rcpt_dt", "ctpv_nm", "sgg_nm"],
    )
    # rcpt_dt는 YYYYMMDDhhmmss 정수 — 문자열 변환 없이 정수 나눗셈으로 날짜부만 취한다
    rcpt_date = pd.to_datetime(
        df["rcpt_dt"] // 1_000_000, format="%Y%m%d", errors="coerce"
    )
    cutoff = rcpt_date.max() - timedelta(days=90)
    df = df[rcpt_date >= cutoff]
    return df.assign(sido=df["ctpv_nm"].replace(SIDO_NAME_ALIASES))


@cache
def _load_business_df() -> pd.DataFrame:
    """다중이용업소 현황 CSV를 읽어 영업중인 업소만 남깁니다 (정적 데이터, 1회 캐시)."""
    df = pd.read_csv(
        BUSINESS_CSV_PATH,
        encoding="utf-8-sig",
        usecols=["USE_YN", "CONM_ADDR", "TPBIZ_NM"],
    )
    df = df[df["USE_YN"] == "Y"]
    sido = df["CONM_ADDR"].str.extract(r"^(\S+)")[0].replace(SIDO_NAME_ALIASES)
    return df.assign(sido=sido)


@cache
def _sigungu_index() -> dict[str, tuple[tuple[str, int, float], ...]]:
    """전 시도의 시군구별 집계를 한 번의 groupby로 계산해 시도명 → 결과로 캐시합니다.

    결과는 정적 데이터에서 결정적으로 나오므로 요청마다 필터/groupby를 반복할 필요가 없다.
    캐시가 공유되므로 호출자가 변경할 수 없도록 튜플로 보관한다.
    """
    agg = (
        _load_recent_fire_df()
        .groupby(["sido", "sgg_nm"])
        .agg(fire_count=("wrinv_no", "count"), death_count=("dth_cnt", "sum"))
        .reset_index()
    )

    index = {}
    for sido, group in agg.groupby("sido"):
        group = group.sort_values("fire_count", ascending=False)
        scores = _minmax_score(group["fire_count"] + group["death_count"] * 30)
        index[sido] = tuple(
            (name, int(count), float(score))
            for name, count, score in zip(group["sgg_nm"], group["fire_count"], scores)
        )
    return index


def load_sigungu_zones(sido: str) -> list[dict]:
    """특정 시도 내 시군구별 화재 집계를 반환합니다 (좌표 없이 건수만)."""
    return [
        {"sigungu_name": name, "report_count": count, "risk_score": score}
        for name, count, score in _sigungu_index().get(sido, ())
    ]


def _load_fire_agg() -> pd.DataFrame:
    return (
        _load_recent_fire_df()
        .groupby("sido")
        .agg(fire_count=("wrinv_no", "count"), death_count=("dth_cnt", "sum"))
        .reset_index()
    )


def _load_business_agg() -> pd.DataFrame:
    df = _load_business_df()
    biz_count = df.groupby("sido").size().reset_index(name="business_count")

    # 시도별 가장 많은 업종 하나만 대표로 표기
    top_biz = (
        df.groupby(["sido", "TPBIZ_NM"])
        .size()
        .reset_index(name="cnt")
        .sort_values("cnt", ascending=False)
        .drop_duplicates("sido")
        .set_index("sido")["TPBIZ_NM"]
    )

    biz_count = biz_count.set_index("sido")
    biz_count["main_target"] = top_biz
    return biz_count.reset_index()


def load_risk_zones() -> list[dict]:
    """
    화재현황 + 다중이용업소현황을 시도 단위로 결합하여 위험지역 데이터를 반환합니다.
    좌표는 시/도청 소재지 기준이며, 실제 사건 발생 지점과는 다를 수 있습니다.
    """
    return [dict(zone) for zone in _risk_zones()]


@cache
def _risk_zones() -> tuple[dict, ...]:
    """시도 단위 위험지역 집계 (정적 데이터라 1회 계산 후 캐시)."""
    fire_agg = _load_fire_agg()
    biz_agg = _load_business_agg()

    merged = fire_agg.merge(biz_agg, on="sido", how="left")
    merged["business_count"] = merged["business_count"].fillna(0)
    merged["main_target"] = merged["main_target"].fillna("다중이용업소")

    # 화재건수 + 사망자가중치 + 다중이용업소 밀집도를 종합한 위험점수 (0~100 정규화)
    merged["risk_score"] = _minmax_score(
        merged["fire_count"]
        + merged["death_count"] * 30
        + merged["business_count"] * 0.05
    )

    zones = []
    for row in merged.itertuples(index=False):
        if row.sido not in SIDO_COORDS:
            continue
        lat, lng = SIDO_COORDS[row.sido]
        zones.append(
            {
                "region_name": row.sido,
                "lat": lat,
                "lng": lng,
                "risk_score": float(row.risk_score),
                "report_count": int(row.fire_count),
                "main_targets": f"{row.main_target} 등 다중이용업소 {int(row.business_count)}곳",
            }
        )

    zones.sort(key=lambda z: z["report_count"], reverse=True)
    return tuple(zones)


def warm_up() -> None:
    """기동 시 CSV 파싱과 집계를 미리 끝내 첫 요청의 콜드스타트를 없앱니다."""
    _risk_zones()
    _sigungu_index()
