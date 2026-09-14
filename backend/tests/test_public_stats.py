"""/api/v1/public/stats 엔드포인트 테스트.

- 인증 없이 노출되는 집계 API이므로, 개인정보(계좌번호·담당자명·대상 업체명)가
  응답에 전혀 섞여나오지 않는지, 그리고 dialect(SQLite/Postgres)에 따라
  func.date()가 date 객체/문자열 중 무엇을 돌려주든 최근 14일 추이 집계가
  올바르게 매칭되는지를 검증한다.
- DB는 임시 파일 sqlite로 대체 (NullPool — 이벤트 루프 간 커넥션 공유 회피)
"""

import asyncio
import os
import tempfile
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool

from app.main import app as fastapi_app
from app.core.database import get_db
from app.models.verify_log import Base, VerifyLog
import app.models.blacklist  # noqa: F401  (테이블 등록)
import app.models.fire_business  # noqa: F401


# --- 임시 파일 sqlite -------------------------------------------------------

_db_fd, _db_path = tempfile.mkstemp(suffix=".db")
os.close(_db_fd)
_engine = create_async_engine(
    f"sqlite+aiosqlite:///{_db_path}", future=True, poolclass=NullPool
)
_Session = async_sessionmaker(_engine, expire_on_commit=False)

_OLD_ORG = "오래된기관"  # 14일 추이 집계 대상 기간 밖에 있어야 한다
_TODAY_DANGER_ORGS = ("서울소방서", "서울소방서")
_TODAY_CAUTION_ORG = "부산소방서"
_SAFE_ORG = "안전기관"  # risk_level=safe → 사칭 랭킹에서 제외되어야 한다


def setup_module(module):
    async def _create():
        async with _engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with _Session() as s:
            s.add_all(
                [
                    VerifyLog(
                        claimed_org=_TODAY_DANGER_ORGS[0],
                        claim_type="소화기 교체 비용",
                        target_business="어떤업체",
                        claimed_person="김담당",
                        risk_level="danger",
                        score=90,
                    ),
                    VerifyLog(
                        claimed_org=_TODAY_DANGER_ORGS[1],
                        claim_type="보조금 환급",
                        risk_level="danger",
                        score=85,
                    ),
                    VerifyLog(
                        claimed_org=_TODAY_CAUTION_ORG,
                        claim_type="점검 수수료",
                        risk_level="caution",
                        score=55,
                    ),
                    VerifyLog(claimed_org=_SAFE_ORG, risk_level="safe", score=10),
                    # 14일 추이 집계 윈도우 밖 (전체 합계/사칭 랭킹에는 포함되어야 함)
                    VerifyLog(
                        claimed_org=_OLD_ORG,
                        claim_type="오래된 사유",
                        risk_level="danger",
                        score=95,
                        created_at=datetime.now(timezone.utc) - timedelta(days=16),
                    ),
                ]
            )
            await s.commit()

    asyncio.run(_create())


def teardown_module(module):
    async def _dispose():
        await _engine.dispose()

    asyncio.run(_dispose())
    try:
        os.unlink(_db_path)
    except OSError:
        pass


async def _override_get_db():
    async with _Session() as session:
        yield session


@pytest.fixture(autouse=True)
def _use_this_module_db():
    """다른 테스트 모듈(test_verify_endpoint 등)도 같은 FastAPI 앱 싱글턴의
    dependency_overrides를 전역으로 건드리므로, 이 모듈의 테스트가 실행되는
    동안만 오버라이드하고 끝나면 이전 값으로 복원한다."""
    previous = fastapi_app.dependency_overrides.get(get_db)
    fastapi_app.dependency_overrides[get_db] = _override_get_db
    yield
    if previous is not None:
        fastapi_app.dependency_overrides[get_db] = previous
    else:
        fastapi_app.dependency_overrides.pop(get_db, None)


client = TestClient(fastapi_app)


def test_total_and_risk_level_stats():
    body = client.get("/api/v1/public/stats").json()

    assert body["total_count"] == 5
    assert body["risk_level_stats"] == {"safe": 1, "caution": 1, "danger": 3, "unverified": 0}


def test_daily_trend_matches_today_and_excludes_old_window():
    body = client.get("/api/v1/public/stats").json()
    daily_trend = body["daily_trend"]

    assert len(daily_trend) == 14
    today_key = datetime.now(timezone.utc).date().isoformat()
    today_point = next(p for p in daily_trend if p["date"] == today_key)
    assert today_point["total"] == 4
    assert today_point["danger"] == 2
    assert today_point["caution"] == 1
    assert today_point["safe"] == 1
    assert today_point["unverified"] == 0

    # 16일 전 항목은 14일 윈도우 밖이므로 추이 합계에 잡히면 안 된다
    assert sum(p["total"] for p in daily_trend) == 4


def test_top_claimed_orgs_excludes_safe_and_ranks_by_count():
    body = client.get("/api/v1/public/stats").json()
    orgs = {item["org"]: item["count"] for item in body["top_claimed_orgs"]}

    assert orgs["서울소방서"] == 2
    assert _SAFE_ORG not in orgs  # safe 판정은 사칭 랭킹에서 제외
    assert orgs[_OLD_ORG] == 1  # 랭킹은 기간 제한 없이 전체 집계


def test_recent_alerts_only_danger_and_no_pii_leak():
    body = client.get("/api/v1/public/stats").json()
    alerts = body["recent_alerts"]

    assert len(alerts) == 3  # danger 3건 (오늘 2건 + 16일 전 1건), 기간 제한 없음
    assert all(a["risk_level"] == "danger" for a in alerts)
    for alert in alerts:
        assert set(alert.keys()) == {"claimed_org", "claim_type", "risk_level", "created_at"}
