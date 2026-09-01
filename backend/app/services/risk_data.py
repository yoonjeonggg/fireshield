"""
위험지역 지도용 실데이터 처리 서비스.
- 소방청 전국 화재 현황(2025)
- 전국 다중이용업소 현황(2023)
두 데이터를 시도 단위로 집계하여 위험도를 계산합니다.
"""
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta
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


def _normalize_sido(name: str) -> str:
    return SIDO_NAME_ALIASES.get(name, name)

def load_sigungu_zones(sido: str) -> list[dict]:
    """특정 시도 내 시군구별 화재 집계를 반환합니다 (좌표 없이 건수만)."""
    df = pd.read_csv(FIRE_CSV_PATH, encoding="utf-8-sig")
    df["rcpt_dt"] = df["rcpt_dt"].astype(str)
    df["rcpt_date"] = pd.to_datetime(df["rcpt_dt"].str[:8], format="%Y%m%d", errors="coerce")

    latest_date = df["rcpt_date"].max()
    cutoff = latest_date - timedelta(days=90)
    df = df[df["rcpt_date"] >= cutoff]

    df["sido"] = df["ctpv_nm"].apply(_normalize_sido)
    df = df[df["sido"] == sido]

    agg = (
        df.groupby("sgg_nm")
        .agg(fire_count=("wrinv_no", "count"), death_count=("dth_cnt", "sum"))
        .reset_index()
        .sort_values("fire_count", ascending=False)
    )

    raw_score = agg["fire_count"] + agg["death_count"] * 30
    score_range = raw_score.max() - raw_score.min()
    agg["risk_score"] = (
        ((raw_score - raw_score.min()) / score_range * 100).round(1) if score_range > 0 else 0
    )

    return [
        {
            "sigungu_name": row["sgg_nm"],
            "report_count": int(row["fire_count"]),
            "risk_score": float(row["risk_score"]),
        }
        for _, row in agg.iterrows()
    ]


def _load_fire_agg() -> pd.DataFrame:
    df = pd.read_csv(FIRE_CSV_PATH, encoding="utf-8-sig")
    df["rcpt_dt"] = df["rcpt_dt"].astype(str)
    df["rcpt_date"] = pd.to_datetime(df["rcpt_dt"].str[:8], format="%Y%m%d", errors="coerce")

    # 데이터 내 가장 최근 날짜를 기준으로 "최근 3개월" 산정
    latest_date = df["rcpt_date"].max()
    cutoff = latest_date - timedelta(days=90)
    df = df[df["rcpt_date"] >= cutoff]

    df["sido"] = df["ctpv_nm"].apply(_normalize_sido)

    agg = (
        df.groupby("sido")
        .agg(fire_count=("wrinv_no", "count"), death_count=("dth_cnt", "sum"))
        .reset_index()
    )
    return agg


def _load_business_agg() -> pd.DataFrame:
    df = pd.read_csv(BUSINESS_CSV_PATH, encoding="utf-8-sig")
    df = df[df["USE_YN"] == "Y"].copy()  # 실제 영업중인 곳만
    df["sido"] = df["CONM_ADDR"].str.extract(r"^(\S+)")[0].apply(_normalize_sido)

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
    fire_agg = _load_fire_agg()
    biz_agg = _load_business_agg()

    merged = fire_agg.merge(biz_agg, on="sido", how="left")
    merged["business_count"] = merged["business_count"].fillna(0)
    merged["main_target"] = merged["main_target"].fillna("다중이용업소")

    # 화재건수 + 사망자가중치 + 다중이용업소 밀집도를 종합한 위험점수 (0~100 정규화)
    raw_score = (
        merged["fire_count"]
        + merged["death_count"] * 30
        + merged["business_count"] * 0.05
    )
    score_range = raw_score.max() - raw_score.min()
    merged["risk_score"] = (
        ((raw_score - raw_score.min()) / score_range * 100).round(1) if score_range > 0 else 0
    )

    zones = []
    for _, row in merged.iterrows():
        sido = row["sido"]
        if sido not in SIDO_COORDS:
            continue
        lat, lng = SIDO_COORDS[sido]
        zones.append(
            {
                "region_name": sido,
                "lat": lat,
                "lng": lng,
                "risk_score": float(row["risk_score"]),
                "report_count": int(row["fire_count"]),
                "main_targets": f"{row['main_target']} 등 다중이용업소 {int(row['business_count'])}곳",
            }
        )

    zones.sort(key=lambda z: z["report_count"], reverse=True)
    return zones