"""
소방청 소방시설업 현황 CSV를 fire_businesses 테이블에 적재하는 스크립트.
실행: python scripts/load_fire_businesses.py
"""
import asyncio
import math
import sys
from pathlib import Path

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parent.parent))

from app.core.database import engine, AsyncSessionLocal
from app.models.verify_log import Base
from app.models.fire_business import FireBusiness

CSV_PATH = Path(__file__).resolve().parent.parent / "data" / "소방청_소방시설업_현황_20241231.csv"


def clean(value):
    """NaN/None을 확실하게 None으로, 그 외엔 문자열로 변환"""
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    if pd.isna(value):
        return None
    return str(value).strip()


async def load_csv():
    df = pd.read_csv(CSV_PATH, encoding="cp949")

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as session:
        from sqlalchemy import delete
        await session.execute(delete(FireBusiness))

        records = [
            FireBusiness(
                region=clean(row["지역"]),
                search_region=clean(row["조회지역"]),
                business_type=clean(row["업종"]),
                field=clean(row["분야"]),
                company_name=clean(row["상호"]),
                representative=clean(row["대표자"]),
                zip_code=clean(row["우편번호"]),
                address=clean(row["본사주소"]),
                phone=clean(row["전화번호"]),
            )
            for _, row in df.iterrows()
        ]

        session.add_all(records)
        await session.commit()

    print(f"적재 완료: {len(records)}건")


if __name__ == "__main__":
    asyncio.run(load_csv())