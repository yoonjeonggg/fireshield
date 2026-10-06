"""
로컬 LLM(Ollama)으로 소방기관 사칭 사기 위험도를 판정하는 서비스.

Ollama( https://ollama.com )를 로컬에서 띄워 두고 한국어가 가능한 모델
(예: `ollama pull gemma2:2b`, `exaone3.5`, `qwen2.5` 등)을 사용한다.
모델이 없거나 응답이 이상하면 ai_guardrail이 걸러내고 verify는 규칙 점수로 폴백한다.
"""

from __future__ import annotations

import json
import logging

import httpx

from app.core.config import settings
from app.services.ai_guardrail import GuardrailResult, evaluate

logger = logging.getLogger("fireshield")

# CPU 추론에서는 프롬프트 읽기(prompt eval)가 응답 시간의 대부분이라 지시문을 짧게 유지한다.
# (190 → 120토큰으로 줄였을 때 판정값 변화 없이 약 40% 단축)
_SYSTEM_PROMPT = (
    "소방기관 사칭 사기 분류기. 아래 신고가 사기일 확률(0.0~1.0)을 "
    'JSON {"scam_probability": 실수} 한 줄로만 답하라.'
)

# 응답 앞부분을 미리 채워(prefill) 모델이 숫자만 생성하게 한다. (12토큰 → 3~4토큰)
_RESPONSE_PREFIX = '{"scam_probability": '


def build_prompt(
    *,
    claimed_org: str,
    claimed_person: str,
    claim_type: str,
    target_business: str,
    law_name: str | None,
    has_account_number: bool,
) -> str:
    return (
        f"{_SYSTEM_PROMPT}\n"
        f"기관:{claimed_org} / 담당자:{claimed_person} / 사유:{claim_type} / "
        f"업체:{target_business} / 법령:{law_name or '없음'} / "
        f"계좌요구:{'있음' if has_account_number else '없음'}"
    )


def _ollama_options(**overrides) -> dict:
    options = {"temperature": 0.0, **overrides}
    # 예열과 실제 요청의 num_thread가 다르면 Ollama가 모델을 다시 올리므로 반드시 같은 값을 쓴다.
    if settings.ollama_num_thread:
        options["num_thread"] = settings.ollama_num_thread
    return options


async def _call_ollama(prompt: str) -> str | None:
    """Ollama /api/chat 호출. 실패하면 None(가드레일이 UNAVAILABLE 처리)."""
    url = f"{settings.ollama_base_url.rstrip('/')}/api/chat"
    body = {
        "model": settings.ollama_model,
        "messages": [
            {"role": "user", "content": prompt},
            # 마지막 assistant 메시지는 Ollama가 이어서 생성한다 (모델별 템플릿과 무관).
            {"role": "assistant", "content": _RESPONSE_PREFIX},
        ],
        "stream": False,
        "keep_alive": settings.ollama_keep_alive,
        "options": _ollama_options(num_predict=8, stop=["}"]),
    }
    # 연결은 빠르게 실패시키되(3초), 추론(read)에는 콜드스타트 여유를 준다.
    timeout = httpx.Timeout(settings.ai_timeout_seconds, connect=3.0)
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(url, json=body)
            resp.raise_for_status()
        content = resp.json()["message"]["content"]
    except (httpx.HTTPError, json.JSONDecodeError, ValueError, KeyError, TypeError) as e:
        logger.warning("Ollama 호출 실패 — 규칙 점수로 폴백: %s", e)
        return None
    # stop 토큰("}")은 응답에 포함되지 않으므로 JSON을 닫아 가드레일이 그대로 파싱하게 한다.
    return f"{_RESPONSE_PREFIX}{content}}}"


async def warm_up() -> None:
    """서버 기동 시 모델을 미리 메모리에 올려 첫 요청의 콜드스타트를 없앤다."""
    if not settings.ai_enabled:
        return
    url = f"{settings.ollama_base_url.rstrip('/')}/api/chat"
    body = {
        "model": settings.ollama_model,
        "messages": [{"role": "user", "content": "ping"}],
        "stream": False,
        "keep_alive": settings.ollama_keep_alive,
        "options": _ollama_options(num_predict=1),
    }
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=3.0)) as client:
            resp = await client.post(url, json=body)
            resp.raise_for_status()
        logger.info("Ollama 모델 예열 완료: %s", settings.ollama_model)
    except (httpx.HTTPError, ValueError) as e:
        logger.warning("Ollama 예열 실패(무시하고 계속): %s", e)


async def request_scam_assessment(
    *,
    claimed_org: str,
    claimed_person: str,
    claim_type: str,
    target_business: str,
    law_name: str | None,
    has_account_number: bool,
) -> tuple[str | None, bool]:
    """
    Ollama 원본 응답만 받아온다(가드레일 판정은 하지 않음).
    프롬프트가 규칙 점수에 의존하지 않으므로, 공공데이터 대조와 '동시에' 실행하기 위해 분리했다.
    이 함수는 어떤 경우에도 예외를 밖으로 던지지 않는다.

    Returns:
        (raw_response | None, model_available)
    """
    if not settings.ai_enabled:
        return None, False

    try:
        prompt = build_prompt(
            claimed_org=claimed_org,
            claimed_person=claimed_person,
            claim_type=claim_type,
            target_business=target_business,
            law_name=law_name,
            has_account_number=has_account_number,
        )
        raw = await _call_ollama(prompt)
    except Exception as e:  # 방어적: 예상 못 한 오류도 규칙 점수로 폴백
        logger.exception("AI 판정 중 예기치 못한 오류 — 규칙 점수로 폴백: %s", e)
        return None, False

    return raw, raw is not None


def finalize_scam_assessment(
    raw: str | None,
    model_available: bool,
    rule_score: int,
) -> GuardrailResult:
    """원본 응답 + 규칙 점수를 가드레일에 통과시켜 최종 AI 판정을 만든다."""
    result = evaluate(
        raw,
        rule_score,
        model_available=model_available,
        conflict_gap=settings.ai_conflict_gap,
    )

    if result.anomaly:
        logger.warning(
            "AI 이상 응답 감지 [status=%s] rule=%s parsed=%s raw=%r",
            result.status.value,
            rule_score,
            result.parsed_value,
            result.raw_text,
        )

    return result
