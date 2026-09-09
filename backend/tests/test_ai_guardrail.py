"""
ai_guardrail 단위 테스트 — 로컬 모델이 내놓는 '터무니없는 값'이 전부
안전하게 걸러지는지 검증한다.

실행:  cd backend && python -m pytest tests/test_ai_guardrail.py -v
(fastapi/DB 불필요 — 순수 함수만 테스트)
"""

import pytest

from app.services.ai_guardrail import (
    AiStatus,
    evaluate,
    extract_probability,
)


# --- extract_probability ------------------------------------------------------

@pytest.mark.parametrize(
    "raw, expected_0_100",
    [
        ('{"scam_probability": 0.87, "reason": "x"}', 87.0),
        ('{"scam_probability": 0}', 0.0),
        ('{"scam_probability": 1}', 100.0),
        ('{"score": "80%"}', 80.0),
        ("사기 확률은 0.42 입니다.", 42.0),
        ("위험도: 73/100", 73.0),
        ("0.5", 50.0),
        ('```json\n{"scam_probability": 0.9}\n```', 90.0),
    ],
)
def test_extract_valid(raw, expected_0_100):
    value, is_invalid, _ = extract_probability(raw)
    assert not is_invalid
    assert value == pytest.approx(expected_0_100)


@pytest.mark.parametrize(
    "raw",
    [
        '{"scam_probability": NaN}',
        "확률: nan",
        "결과는 Infinity 입니다",
        '{"scam_probability": "not a number"}',
    ],
)
def test_extract_invalid_tokens(raw):
    value, is_invalid, _ = extract_probability(raw)
    assert is_invalid
    assert value is None


@pytest.mark.parametrize("raw", ["", "   ", None, "판단할 수 없습니다", "죄송합니다만 도와드릴 수 없어요"])
def test_extract_no_number(raw):
    value, is_invalid, _ = extract_probability(raw)
    assert value is None
    assert is_invalid is False  # 망가진 게 아니라 그냥 숫자가 없는 것


def test_extract_out_of_range_passthrough():
    # 정규화 단계에서는 클램프하지 않고 그대로 넘긴다 (evaluate가 처리)
    value, is_invalid, _ = extract_probability('{"scam_probability": 250}')
    assert not is_invalid
    assert value == 250.0

    value, _, _ = extract_probability('{"scam_probability": -0.4}')
    assert value == pytest.approx(-40.0)


# --- evaluate ---------------------------------------------------------------

def test_evaluate_ok_high():
    r = evaluate('{"scam_probability": 0.9}', rule_score=80)
    assert r.status == AiStatus.OK
    assert r.score == 90
    assert r.used_in_verdict
    assert r.label == "사기 위험 높음"
    assert not r.anomaly


def test_evaluate_ok_low():
    r = evaluate('{"scam_probability": 0.05}', rule_score=10)
    assert r.status == AiStatus.OK
    assert r.score == 5
    assert r.used_in_verdict


def test_evaluate_model_unavailable():
    r = evaluate(None, rule_score=50, model_available=False)
    assert r.status == AiStatus.UNAVAILABLE
    assert r.score is None
    assert not r.used_in_verdict
    assert not r.anomaly
    assert r.label == "분석 미실시"


def test_evaluate_nan_is_discarded():
    r = evaluate('{"scam_probability": NaN}', rule_score=70)
    assert r.status == AiStatus.DISCARDED_INVALID
    assert r.score is None
    assert r.anomaly is True
    assert not r.used_in_verdict


def test_evaluate_garbage_prose_is_discarded():
    r = evaluate("모르겠어요. 도와드릴 수 없습니다.", rule_score=70)
    assert r.status == AiStatus.DISCARDED_INVALID
    assert r.score is None
    assert r.anomaly is True


def test_evaluate_out_of_range_high_is_clamped():
    r = evaluate('{"scam_probability": 250}', rule_score=90)
    assert r.status == AiStatus.CLAMPED
    assert r.score == 100
    assert r.anomaly is True
    assert r.used_in_verdict  # 방향은 신뢰 가능 → 반영
    assert r.parsed_value == 250.0


def test_evaluate_out_of_range_negative_is_clamped():
    r = evaluate('{"scam_probability": -0.4}', rule_score=5)
    assert r.status == AiStatus.CLAMPED
    assert r.score == 0
    assert r.anomaly is True


def test_evaluate_extreme_conflict_falls_back_to_rules():
    # 규칙은 위험(85)인데 AI는 안전(2) → AI 폐기
    r = evaluate('{"scam_probability": 0.02}', rule_score=85)
    assert r.status == AiStatus.DISCARDED_CONFLICT
    assert r.score is None
    assert r.anomaly is True
    assert not r.used_in_verdict
    assert "85" in r.detail


def test_evaluate_conflict_both_directions():
    # 규칙은 안전(10)인데 AI는 위험(95) → 마찬가지로 폐기(보수적으로 규칙 신뢰)
    r = evaluate('{"scam_probability": 0.95}', rule_score=10)
    assert r.status == AiStatus.DISCARDED_CONFLICT
    assert not r.used_in_verdict


def test_evaluate_low_confidence_band_not_used_in_verdict():
    r = evaluate('{"scam_probability": 0.5}', rule_score=45)
    assert r.status == AiStatus.LOW_CONFIDENCE
    assert r.score == 50
    assert not r.used_in_verdict
    assert not r.anomaly


def test_evaluate_moderate_gap_still_ok():
    # 40점 차이 (기본 임계 45 미만) → 유지
    r = evaluate('{"scam_probability": 0.75}', rule_score=35)
    assert r.status == AiStatus.OK
    assert r.score == 75


def test_evaluate_conflict_gap_is_configurable():
    r = evaluate('{"scam_probability": 0.75}', rule_score=35, conflict_gap=30)
    assert r.status == AiStatus.DISCARDED_CONFLICT


def test_evaluate_raw_text_is_truncated():
    r = evaluate("사기 확률 0.9 " + "가" * 2000, rule_score=80)
    assert r.raw_text is not None
    assert len(r.raw_text) <= 501


def test_evaluate_bare_huge_number_json():
    # JSON 최상위가 그냥 큰 숫자 → 클램프
    r = evaluate("1e999", rule_score=95)
    assert r.status in (AiStatus.CLAMPED, AiStatus.DISCARDED_INVALID)
    assert r.anomaly is True


def test_evaluate_percent_in_prose():
    r = evaluate("이 신고는 사기일 가능성이 85% 로 보입니다.", rule_score=70)
    assert r.status == AiStatus.OK
    assert r.score == 85


def test_evaluate_rule_score_is_clamped_defensively():
    r = evaluate('{"scam_probability": 0.9}', rule_score=999)
    # rule_score 100으로 클램프되므로 gap = 10 → OK
    assert r.status == AiStatus.OK
