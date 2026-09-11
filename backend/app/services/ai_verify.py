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

_SYSTEM_PROMPT = (
    "너는 대한민국 소방기관(소방서·소방공무원) 사칭 사기를 탐지하는 분류기다. "
    "아래 신고 내용이 사칭 사기일 확률을 0.0~1.0 사이 실수로 판단한다. "
    "설명·이유 없이 아래 JSON 한 줄만 출력하라.\n"
    '{"scam_probability": <0.0~1.0 실수>}'
)


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
        f"{_SYSTEM_PROMPT}\n\n"
        "[신고 내용]\n"
        f"- 발신 기관명: {claimed_org}\n"
        f"- 담당자명: {claimed_person}\n"
        f"- 요구 사유: {claim_type}\n"
        f"- 대상 업체: {target_business}\n"
        f"- 언급된 법령: {law_name or '없음'}\n"
        f"- 계좌번호 요구: {'있음' if has_account_number else '없음'}\n\n"
        "JSON:"
    )


async def _call_ollama(prompt: str) -> str | None:
    """Ollama /api/generate 호출. 실패하면 None(가드레일이 UNAVAILABLE 처리)."""
    url = f"{settings.ollama_base_url.rstrip('/')}/api/generate"
    body = {
        "model": settings.ollama_model,
        "prompt": prompt,
        "stream": False,
        "format": "json",
        "keep_alive": settings.ollama_keep_alive,
        # 숫자 하나짜리 JSON만 받으므로 토큰을 짧게 제한해 추론 시간을 줄인다.
        "options": {"temperature": 0.0, "num_predict": 32},
    }
    # 연결은 빠르게 실패시키되(3초), 추론(read)에는 콜드스타트 여유를 준다.
    timeout = httpx.Timeout(settings.ai_timeout_seconds, connect=3.0)
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(url, json=body)
            resp.raise_for_status()
        data = resp.json()
    except (httpx.HTTPError, json.JSONDecodeError, ValueError) as e:
        logger.warning("Ollama 호출 실패 — 규칙 점수로 폴백: %s", e)
        return None
    return data.get("response")


async def warm_up() -> None:
    """서버 기동 시 모델을 미리 메모리에 올려 첫 요청의 콜드스타트를 없앤다."""
    if not settings.ai_enabled:
        return
    url = f"{settings.ollama_base_url.rstrip('/')}/api/generate"
    body = {
        "model": settings.ollama_model,
        "prompt": "ping",
        "stream": False,
        "keep_alive": settings.ollama_keep_alive,
        "options": {"num_predict": 1},
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


async def assess_scam_risk(
    rule_score: int,
    *,
    claimed_org: str,
    claimed_person: str,
    claim_type: str,
    target_business: str,
    law_name: str | None,
    has_account_number: bool,
) -> GuardrailResult:
    """AI 판정을 순차 실행하는 편의 래퍼(동시 실행이 필요 없는 호출부용)."""
    raw, model_available = await request_scam_assessment(
        claimed_org=claimed_org,
        claimed_person=claimed_person,
        claim_type=claim_type,
        target_business=target_business,
        law_name=law_name,
        has_account_number=has_account_number,
    )
    return finalize_scam_assessment(raw, model_available, rule_score)
