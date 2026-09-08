"""/api/v1/verify 엔드포인트 통합 테스트 — 규칙 점수와 AI 판정 결합 배선 검증.

- Ollama 호출은 `_call_ollama`를 몽키패치로 대체 (실제 모델 불필요)
- 외부 공공데이터 서비스도 몽키패치
- DB는 임시 파일 sqlite로 대체 (NullPool — 이벤트 루프 간 커넥션 공유 회피)
"""

import asyncio
import os
import tempfile

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool

from app.main import app as fastapi_app
from app.core.database import get_db
from app.models.verify_log import Base
import app.models.blacklist  # noqa: F401  (테이블 등록)
import app.models.fire_business  # noqa: F401
import app.services.ai_verify as ai_verify
import app.api.v1.verify as verify_api


# --- 임시 파일 sqlite -------------------------------------------------------

_db_fd, _db_path = tempfile.mkstemp(suffix=".db")
os.close(_db_fd)
_engine = create_async_engine(
    f"sqlite+aiosqlite:///{_db_path}", future=True, poolclass=NullPool
)
_Session = async_sessionmaker(_engine, expire_on_commit=False)


def setup_module(module):
    async def _create():
        async with _engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

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


fastapi_app.dependency_overrides[get_db] = _override_get_db


# --- 외부 서비스 스텁 -------------------------------------------------------


@pytest.fixture(autouse=True)
def _stub_external(monkeypatch):
    async def no_blacklist(db, entry_type, name):
        return None

    async def law_not_applicable(law_name):
        return {"found": True, "is_recent": False, "current_law": {}}

    async def no_business(db, business_name):
        return []

    monkeypatch.setattr(verify_api, "is_blacklisted", no_blacklist)
    monkeypatch.setattr(verify_api, "check_recent_amendment", law_not_applicable)
    monkeypatch.setattr(verify_api, "find_business_by_name", no_business)


client = TestClient(fastapi_app)

_PAYLOAD = {
    "claimed_org": "서울강남소방서",
    "claimed_person": "김소방",
    "claim_type": "소방시설 점검비 미납분 계좌 입금 요청",
    "target_business": "없는소방점검주식회사",
    "account_number": "123-456-789012",
}


def _post(monkeypatch, *, ai_enabled, ollama_response):
    monkeypatch.setattr(ai_verify.settings, "ai_enabled", ai_enabled)

    async def fake_call(prompt):
        return ollama_response

    monkeypatch.setattr(ai_verify, "_call_ollama", fake_call)
    resp = client.post("/api/v1/verify", json=_PAYLOAD)
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_ai_disabled_uses_rule_score_only(monkeypatch):
    body = _post(monkeypatch, ai_enabled=False, ollama_response=None)
    assert body["score"] == body["rule_score"]
    assert body["ai_assessment"]["status"] == "unavailable"
    assert body["ai_assessment"]["used_in_verdict"] is False
    assert body["ai_assessment"]["score"] is None


def test_ai_unreachable_falls_back_gracefully(monkeypatch):
    # _call_ollama 가 None (호출 실패) → 폐기, 엔드포인트는 정상 응답
    body = _post(monkeypatch, ai_enabled=True, ollama_response=None)
    assert body["score"] == body["rule_score"]
    assert body["ai_assessment"]["status"] == "unavailable"


def test_ai_garbage_is_discarded(monkeypatch):
    body = _post(
        monkeypatch,
        ai_enabled=True,
        ollama_response="죄송하지만 판단할 수 없습니다. 더 많은 정보가 필요합니다.",
    )
    assert body["ai_assessment"]["status"] == "discarded_invalid"
    assert body["ai_assessment"]["score"] is None
    assert body["score"] == body["rule_score"]


def test_ai_high_score_raises_final_conservatively(monkeypatch):
    body = _post(
        monkeypatch,
        ai_enabled=True,
        ollama_response='{"scam_probability": 0.95, "reason": "전형적인 사칭"}',
    )
    ai = body["ai_assessment"]
    assert ai["score"] == 95
    assert ai["status"] in ("ok", "clamped")
    assert ai["used_in_verdict"] is True
    assert body["score"] == max(body["rule_score"], 95)
    assert body["score"] >= body["rule_score"]


def test_ai_low_score_never_lowers_final(monkeypatch):
    body = _post(
        monkeypatch,
        ai_enabled=True,
        ollama_response='{"scam_probability": 0.05}',
    )
    # gap 이 크면 discarded_conflict, 작으면 low_confidence/ok — 어느 쪽이든 최종은 규칙 점수 밑으로 안 내려감
    assert body["score"] == body["rule_score"]
