"""
로컬 딥러닝/LLM(Ollama) 모델이 내놓은 사기 위험도 판정을 신뢰하기 전에
검증·정제하는 가드레일.

로컬에서 직접 돌리는 모델은 다음과 같은 '터무니없는 값'을 흔히 내놓는다:
  - 확률 대신 프롬프트를 그대로 반복하거나 한국어 산문만 출력
  - 0~1 범위를 벗어난 숫자 ("3", "-0.4", "250", "80%")
  - NaN / Infinity
  - JSON을 요청했는데 깨진 JSON
  - 규칙 기반 점수와 정반대의 결론 (규칙: 85 위험 / AI: 2 안전)

이 모듈은 외부 I/O가 없는 순수 함수로만 구성되어 단위 테스트로 모든 분기를 검증한다.
verify 응답에는 규칙 점수와 AI 점수를 '따로' 노출하고, AI 값이 의심스러우면
규칙 점수로 폴백하며 이상 징후(anomaly)를 로깅한다.
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from enum import Enum

# AI 점수가 이 중립 구간 안에 있으면 "판단 보류"로 간주하고 최종 판정에 반영하지 않는다.
NEUTRAL_LOW = 40
NEUTRAL_HIGH = 60

# 규칙 점수와 AI 점수가 이 폭 이상 벌어지면(양방향) AI가 헛소리를 했다고 보고 규칙으로 폴백.
DEFAULT_CONFLICT_GAP = 45

# JSON 응답에서 확률로 해석할 키 후보
_PROB_KEYS = (
    "scam_probability",
    "probability",
    "prob",
    "score",
    "risk",
    "risk_score",
    "위험도",
    "위험확률",
    "확률",
    "사기확률",
)

_JSON_OBJ_RE = re.compile(r"\{.*\}", re.DOTALL)
_NUMBER_RE = re.compile(r"-?\d+(?:\.\d+)?")
_NAN_RE = re.compile(r"\b(nan|not[ _]a[ _]number)\b", re.IGNORECASE)
_INF_RE = re.compile(r"[-+]?\b(inf|infinity|무한)\b", re.IGNORECASE)


class AiStatus(str, Enum):
    OK = "ok"                              # 정상 값, 최종 판정에 반영
    CLAMPED = "clamped"                    # 범위를 벗어나 잘라냈지만 방향은 신뢰 가능, 반영
    LOW_CONFIDENCE = "low_confidence"      # 중립 구간, 참고만 하고 판정에는 미반영
    DISCARDED_INVALID = "discarded_invalid"    # 파싱 불가/NaN/타입 오류 → 폐기
    DISCARDED_CONFLICT = "discarded_conflict"  # 규칙 점수와 극단적으로 상충 → 폐기
    UNAVAILABLE = "unavailable"            # 모델 미응답/비활성 → 규칙만 사용


_DISCARDED = {
    AiStatus.DISCARDED_INVALID,
    AiStatus.DISCARDED_CONFLICT,
    AiStatus.UNAVAILABLE,
}
_USED_IN_VERDICT = {AiStatus.OK, AiStatus.CLAMPED}


@dataclass(frozen=True)
class GuardrailResult:
    """가드레일 통과 후의 AI 판정 결과."""

    score: int | None          # 0~100 정규화 점수. 폐기되면 None.
    status: AiStatus
    detail: str                # 사람이 읽는 한국어 설명
    raw_text: str | None       # 모델 원본 응답(로깅/디버깅용, 최대 500자)
    parsed_value: float | None # 파싱된 원시 숫자(정규화 전). NaN/inf면 None로 저장.
    anomaly: bool              # 비정상 상황이 감지되었는지 (경고 로깅 트리거)

    @property
    def used_in_verdict(self) -> bool:
        return self.status in _USED_IN_VERDICT and self.score is not None

    @property
    def label(self) -> str:
        if self.status == AiStatus.UNAVAILABLE:
            return "AI 판정 사용 불가"
        if self.score is None:
            return "AI 판단 보류"
        if self.score >= NEUTRAL_HIGH:
            return "AI: 위험"
        if self.score >= 30:
            return "AI: 의심"
        return "AI: 안전"


def _truncate(text: str | None, limit: int = 500) -> str | None:
    if text is None:
        return None
    text = text.strip()
    return text if len(text) <= limit else text[:limit] + "…"


def _coerce_number(value) -> float | None:
    """JSON 값(숫자/문자열)을 float로. 실패하면 None, NaN/inf면 그대로 반환."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        s = value.strip().rstrip("%").strip()
        m = _NUMBER_RE.search(s)
        if m:
            try:
                return float(m.group())
            except ValueError:
                return None
    return None


def extract_probability(raw: str | None) -> tuple[float | None, bool, str]:
    """
    모델 원본 응답에서 사기 확률을 뽑아 0~100 스케일로 정규화한다.

    Returns:
        (score_0_100 | None, is_invalid, note)
        - score_0_100: 정규화된 값. 파싱 실패/NaN/inf면 None.
        - is_invalid: NaN·inf·타입오류처럼 '명백히 망가진' 값이면 True.
                      (단순히 값을 못 찾은 경우와 구분)
        - note: 한국어 설명.
    """
    if raw is None or not raw.strip():
        return None, False, "모델이 빈 응답을 반환함"

    text = raw.strip()

    # 1) NaN / Infinity 토큰이 먼저 보이면 즉시 무효 처리
    if _NAN_RE.search(text):
        return None, True, "확률 자리에 NaN이 들어옴"
    if _INF_RE.search(text):
        return None, True, "확률 자리에 무한대(inf)가 들어옴"

    had_percent = "%" in text

    # 2) JSON 우선 파싱 (전체 → 부분 객체)
    parsed_obj = None
    for candidate in (text, _JSON_OBJ_RE.search(text)):
        if candidate is None:
            continue
        chunk = candidate if isinstance(candidate, str) else candidate.group()
        try:
            obj = json.loads(chunk)
        except (json.JSONDecodeError, ValueError):
            continue
        if isinstance(obj, dict):
            parsed_obj = obj
            break
        if isinstance(obj, (int, float)) and not isinstance(obj, bool):
            fval = float(obj)
            if math.isnan(fval) or math.isinf(fval):
                return None, True, "파싱된 확률이 NaN 또는 inf"
            return _normalize_scale(fval, had_percent=had_percent)

    raw_value: float | None = None

    if parsed_obj is not None:
        for key in _PROB_KEYS:
            if key in parsed_obj:
                raw_value = _coerce_number(parsed_obj[key])
                if isinstance(parsed_obj[key], str) and "%" in parsed_obj[key]:
                    had_percent = True
                break
        if raw_value is None and parsed_obj:
            # 키 이름이 예상과 다르면 첫 번째 숫자형 값이라도 시도
            for v in parsed_obj.values():
                cand = _coerce_number(v)
                if cand is not None:
                    raw_value = cand
                    break

    # 3) JSON 실패 시 본문에서 첫 숫자
    if raw_value is None:
        m = _NUMBER_RE.search(text.replace("%", " % "))
        if m:
            try:
                raw_value = float(m.group())
            except ValueError:
                raw_value = None

    if raw_value is None:
        return None, False, "응답에서 확률로 해석할 숫자를 찾지 못함"

    if math.isnan(raw_value) or math.isinf(raw_value):
        return None, True, "파싱된 확률이 NaN 또는 inf"

    return _normalize_scale(raw_value, had_percent=had_percent)


def _normalize_scale(value: float, *, had_percent: bool) -> tuple[float, bool, str]:
    """원시 숫자를 0~100 스케일 추정치로. (아직 클램프하지 않음 — 범위 밖 여부를 상위에서 판단)"""
    if had_percent:
        return value, False, f"백분율로 해석: {value}%"
    if -1.0 <= value <= 1.0:
        # 0~1 확률로 간주
        return value * 100.0, False, f"0~1 확률로 해석: {value}"
    # 그 외는 이미 0~100(혹은 그 이상)의 점수 스케일로 간주
    return value, False, f"0~100 점수로 해석: {value}"


def evaluate(
    raw_text: str | None,
    rule_score: int,
    *,
    model_available: bool = True,
    conflict_gap: int = DEFAULT_CONFLICT_GAP,
) -> GuardrailResult:
    """
    모델 원본 응답 + 규칙 점수를 받아 신뢰 가능한 AI 판정으로 정제한다.

    Args:
        raw_text: Ollama가 돌려준 텍스트(보통 JSON 문자열). 호출 실패 시 None.
        rule_score: 규칙 기반 위험 점수 (0~100).
        model_available: 모델 호출 자체가 가능했는지. False면 UNAVAILABLE.
        conflict_gap: 규칙 점수와 이 폭 이상 벌어지면 폐기.
    """
    rule_score = max(0, min(100, int(rule_score)))
    trimmed = _truncate(raw_text)

    if not model_available:
        return GuardrailResult(
            score=None,
            status=AiStatus.UNAVAILABLE,
            detail="AI 모델에 연결하지 못해 규칙 기반 점수만 사용합니다.",
            raw_text=trimmed,
            parsed_value=None,
            anomaly=False,
        )

    value_0_100, is_invalid, note = extract_probability(raw_text)

    if is_invalid or value_0_100 is None:
        return GuardrailResult(
            score=None,
            status=AiStatus.DISCARDED_INVALID,
            detail=f"AI 응답을 신뢰할 수 없어 폐기하고 규칙 점수로 대체합니다 ({note}).",
            raw_text=trimmed,
            parsed_value=None,
            anomaly=True,
        )

    parsed_value = value_0_100

    # 범위 밖 → 클램프. 방향(위험/안전)은 살리되 이상 징후로 표시.
    clamped = False
    if value_0_100 < 0:
        value_0_100, clamped = 0.0, True
    elif value_0_100 > 100:
        value_0_100, clamped = 100.0, True

    score = int(round(value_0_100))

    # 규칙 점수와 극단적으로 상충 → AI 폐기(양방향)
    gap = abs(score - rule_score)
    if gap >= conflict_gap:
        return GuardrailResult(
            score=None,
            status=AiStatus.DISCARDED_CONFLICT,
            detail=(
                f"AI 점수({score})가 규칙 점수({rule_score})와 {gap}점이나 차이 나 "
                f"신뢰할 수 없다고 보고 규칙 점수를 사용합니다."
            ),
            raw_text=trimmed,
            parsed_value=parsed_value,
            anomaly=True,
        )

    if clamped:
        return GuardrailResult(
            score=score,
            status=AiStatus.CLAMPED,
            detail=f"AI가 범위를 벗어난 값({parsed_value})을 반환해 0~100으로 보정했습니다.",
            raw_text=trimmed,
            parsed_value=parsed_value,
            anomaly=True,
        )

    if NEUTRAL_LOW <= score <= NEUTRAL_HIGH:
        return GuardrailResult(
            score=score,
            status=AiStatus.LOW_CONFIDENCE,
            detail=(
                f"AI 점수({score})가 애매한 중간 구간이라 참고용으로만 표시하고 "
                f"최종 판정에는 반영하지 않습니다."
            ),
            raw_text=trimmed,
            parsed_value=parsed_value,
            anomaly=False,
        )

    return GuardrailResult(
        score=score,
        status=AiStatus.OK,
        detail=f"AI 사기 위험 점수: {score}/100",
        raw_text=trimmed,
        parsed_value=parsed_value,
        anomaly=False,
    )
