"""/api/v1/admin/* 엔드포인트 테스트.

- X-Admin-Key 인증, 위험도별 통계 집계, 로그 목록의 개인정보 마스킹,
  블랙리스트 CRUD를 검증한다.
- DB는 임시 파일 sqlite로 대체 (NullPool — 이벤트 루프 간 커넥션 공유 회피)
"""

import asyncio
import os
import tempfile
import uuid

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

ADMIN_HEADERS = {"X-Admin-Key": "test-admin-key"}


def setup_module(module):
    async def _create():
        async with _engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with _Session() as s:
            s.add_all(
                [
                    VerifyLog(claimed_org="서울소방서", risk_level="danger", score=90,
                              account_number="암호문"),
                    VerifyLog(claimed_org="서울소방서", risk_level="danger", score=80),
                    VerifyLog(claimed_org="부산소방서", risk_level="caution", score=50),
                    VerifyLog(claimed_org="안전기관", risk_level="safe", score=5),
                    VerifyLog(claimed_org="모르는기관", risk_level="unverified", score=0),
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
    previous = fastapi_app.dependency_overrides.get(get_db)
    fastapi_app.dependency_overrides[get_db] = _override_get_db
    yield
    if previous is not None:
        fastapi_app.dependency_overrides[get_db] = previous
    else:
        fastapi_app.dependency_overrides.pop(get_db, None)


client = TestClient(fastapi_app)


# --- 인증 ---------------------------------------------------------------------

@pytest.mark.parametrize("headers", [{}, {"X-Admin-Key": "wrong"}])
def test_rejects_missing_or_wrong_key(headers):
    assert client.get("/api/v1/admin/stats", headers=headers).status_code == 403


# --- 통계 / 로그 ------------------------------------------------------------------

def test_stats_counts_by_risk_level():
    body = client.get("/api/v1/admin/stats", headers=ADMIN_HEADERS).json()
    assert body["total_count"] == 5
    assert body["risk_level_stats"] == {"safe": 1, "caution": 1, "danger": 2, "unverified": 1}
    assert len(body["recent_logs"]) == 5


def test_verify_logs_masks_account_number():
    body = client.get("/api/v1/admin/verify-logs", headers=ADMIN_HEADERS).json()
    assert body["total"] == 5
    assert "암호문" not in str(body)
    assert sorted(item["has_account_number"] for item in body["items"]) == [False] * 4 + [True]


def test_verify_logs_pagination():
    body = client.get(
        "/api/v1/admin/verify-logs", params={"limit": 2, "offset": 4}, headers=ADMIN_HEADERS
    ).json()
    assert body["total"] == 5
    assert len(body["items"]) == 1


# --- 블랙리스트 -----------------------------------------------------------------

def test_blacklist_create_list_delete():
    created = client.post(
        "/api/v1/admin/blacklist",
        json={"entry_type": "org", "name": "  가짜소방본부 ", "reason": "신고 접수"},
        headers=ADMIN_HEADERS,
    )
    assert created.status_code == 200
    entry = created.json()
    assert entry["name"] == "가짜소방본부"  # 앞뒤 공백 제거
    assert entry["entry_type"] == "org"
    assert entry["reason"] == "신고 접수"
    uuid.UUID(entry["id"])

    items = client.get("/api/v1/admin/blacklist", headers=ADMIN_HEADERS).json()["items"]
    assert [i["id"] for i in items] == [entry["id"]]

    deleted = client.delete(f"/api/v1/admin/blacklist/{entry['id']}", headers=ADMIN_HEADERS)
    assert deleted.json() == {"deleted": True}
    assert client.get("/api/v1/admin/blacklist", headers=ADMIN_HEADERS).json()["items"] == []


def test_blacklist_rejects_blank_name():
    res = client.post(
        "/api/v1/admin/blacklist", json={"entry_type": "org", "name": "   "}, headers=ADMIN_HEADERS
    )
    assert res.status_code == 422


@pytest.mark.parametrize("entry_id", ["not-a-uuid", str(uuid.uuid4())])
def test_blacklist_delete_unknown_returns_404(entry_id):
    res = client.delete(f"/api/v1/admin/blacklist/{entry_id}", headers=ADMIN_HEADERS)
    assert res.status_code == 404
