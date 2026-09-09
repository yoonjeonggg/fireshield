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

# 각 항목이 서로 다르고 개별 형식은 유효하지만, 공공데이터로 아무것도 확인되지 않고
# 사기 문구·블랙리스트 같은 적극적 신호도 없는 입력 → "확인 불가"가 나와야 한다.
_UNVERIFIABLE_PAYLOAD = {
    "claimed_org": "강남중부소방서",
    "claimed_person": "박담당",
    "claim_type": "시설 관련 안내 연락 확인 요청",
    "target_business": "강남종합시설관리",
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


# --- 터무니없는 입력은 판정 없이 422 로 거부 -------------------------------

@pytest.mark.parametrize(
    "field, value",
    [
        ("claimed_org", "ㄹ"),          # 자모 한 글자
        ("claimed_org", "ㅋㅋㅋㅋ"),      # 자모 반복
        ("claimed_org", "asdf"),        # 한글 없음
        ("claimed_person", "!"),        # 특수문자 한 글자
        ("target_business", "----"),    # 특수문자 반복
        ("target_business", "ㅁㄴㅇㄹ"),  # 자모만
        ("law_name", "ㄹ"),
        ("law_name", "abcd"),           # 법령명인데 한글 없음
    ],
)
def test_implausible_input_rejected_with_422(field, value):
    payload = {**_PAYLOAD, field: value}
    resp = client.post("/api/v1/verify", json=payload)
    assert resp.status_code == 422, resp.text
    assert resp.json()["error"] == "invalid_request"


def test_all_fields_identical_rejected_with_422():
    payload = {
        "claimed_org": "강남오",
        "claimed_person": "강남오",
        "claim_type": "강남오",
        "target_business": "강남오",
    }
    resp = client.post("/api/v1/verify", json=payload)
    assert resp.status_code == 422, resp.text
    assert resp.json()["error"] == "invalid_request"
    assert "같은 값" in resp.json()["detail"]


def test_identical_ignoring_case_and_spaces_rejected():
    payload = {
        "claimed_org": "강남 소방",
        "claimed_person": "강남소방",
        "claim_type": "점검비 납부 요청",
        "target_business": " 강남소방 ",
    }
    resp = client.post("/api/v1/verify", json=payload)
    assert resp.status_code == 422, resp.text


def test_distinct_fields_pass(monkeypatch):
    monkeypatch.setattr(ai_verify.settings, "ai_enabled", False)
    resp = client.post("/api/v1/verify", json=_PAYLOAD)
    assert resp.status_code == 200, resp.text


def test_fake_but_plausible_law_name_still_scored(monkeypatch):
    # 존재하지 않지만 '그럴듯한' 가짜 법령명은 거부하지 말고 정상 판정해야 한다
    monkeypatch.setattr(ai_verify.settings, "ai_enabled", False)
    payload = {**_PAYLOAD, "law_name": "소방시설안전특별관리법", "claim_type": "law_amendment"}
    resp = client.post("/api/v1/verify", json=payload)
    assert resp.status_code == 200, resp.text


# --- 확인 불가(unverified) 판정 ------------------------------------------

def test_unverifiable_input_returns_unverified(monkeypatch):
    monkeypatch.setattr(ai_verify.settings, "ai_enabled", False)
    resp = client.post("/api/v1/verify", json=_UNVERIFIABLE_PAYLOAD)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["risk_level"] == "unverified"
    assert body["score"] == body["rule_score"]


def test_unverifiable_input_does_not_trust_ai_score(monkeypatch):
    # 공공데이터로 확인 안 되는 입력이면 AI가 높은 점수를 줘도 최종 판정에 반영하지 않는다
    monkeypatch.setattr(ai_verify.settings, "ai_enabled", True)

    async def fake_call(prompt):
        return '{"scam_probability": 0.7}'

    monkeypatch.setattr(ai_verify, "_call_ollama", fake_call)
    body = client.post("/api/v1/verify", json=_UNVERIFIABLE_PAYLOAD).json()
    assert body["risk_level"] == "unverified"
    assert body["ai_assessment"]["used_in_verdict"] is False
    assert body["score"] == body["rule_score"]


def test_scam_phrase_input_is_scored_not_unverified(monkeypatch):
    # 업체는 미등록이지만 전형적 사기 문구가 있으면 '확인 불가'가 아니라 위험도를 매긴다
    monkeypatch.setattr(ai_verify.settings, "ai_enabled", False)
    payload = {
        **_UNVERIFIABLE_PAYLOAD,
        "claim_type": "과태료 부과 전 오늘까지 계좌로 즉시 입금 요청",
    }
    body = client.post("/api/v1/verify", json=payload).json()
    assert body["risk_level"] in ("caution", "danger")


def test_unregistered_business_asking_for_money_is_scored_not_unverified(monkeypatch):
    # 사기 문구가 없어도 '미등록 업체 + 계좌 이체 요구'면 확인 불가가 아니라 위험도를 매긴다
    monkeypatch.setattr(ai_verify.settings, "ai_enabled", False)
    payload = {**_UNVERIFIABLE_PAYLOAD, "account_number": "352-1234-5678-90"}
    body = client.post("/api/v1/verify", json=payload).json()
    assert body["risk_level"] in ("caution", "danger")


def test_fake_law_name_is_scored_not_unverified(monkeypatch):
    # 존재하지 않는 법령을 개정 근거로 들면 확인 불가가 아니라 위험도를 매긴다
    monkeypatch.setattr(ai_verify.settings, "ai_enabled", False)

    async def law_missing(law_name):
        return {"found": False, "is_recent": False, "current_law": {}}

    monkeypatch.setattr(verify_api, "check_recent_amendment", law_missing)
    payload = {
        **_UNVERIFIABLE_PAYLOAD,
        "claim_type": "law_amendment",
        "law_name": "소방시설안전특별관리법",
    }
    body = client.post("/api/v1/verify", json=payload).json()
    assert body["risk_level"] in ("caution", "danger")
