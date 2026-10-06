import asyncio
from dataclasses import dataclass

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.blacklist import is_blacklisted
from app.core.crypto import encrypt, account_fingerprint
from app.core.database import get_db
from app.models.verify_log import VerifyLog
from app.schemas.verify import VerifyRequest, VerifyResponse, Evidence, AiAssessment
from app.services.law_api import check_recent_amendment, LawApiError
from app.services.fire_business import find_business_by_name
from app.services.fraud_account import FraudAccountResult, get_fraud_account_provider
from app.services.scam_patterns import detect_scam_phrases
from app.services.ai_verify import request_scam_assessment, finalize_scam_assessment

router = APIRouter(prefix="/api/v1", tags=["verify"])

_LAW_SOURCE = "법제처_법령 변경이력 목록 조회"
_ACCOUNT_SOURCE = "계좌번호 요구 위험도 분석"
_FRAUD_SOURCE = "계좌번호 사기 신고 이력"

_UNVERIFIED_RECOMMENDATION = (
    "입력하신 기관·업체·법령을 공공데이터에서 확인할 수 없어 위험 여부를 판정할 수 없습니다. "
    "받으신 연락처로 회신하지 마시고, 소방청 홈페이지나 정부24에서 관할 소방서 대표번호를 찾아 "
    "직접 전화로 사실 여부를 확인하세요. 확인 전까지 금전·개인정보 요구에는 절대 응하지 마세요."
)


@dataclass
class _Finding:
    """검사 한 단계의 결과: 화면에 보여줄 근거 + 규칙 점수 가감."""

    evidence: Evidence
    points: int = 0
    # 존재하지 않는 법령/업체처럼 다른 안전 신호로 상쇄되면 안 되는 치명적 신호
    critical: bool = False


@dataclass
class _LawFinding(_Finding):
    found: bool = False         # 법제처에서 실제로 조회된 법령인지
    contradicted: bool = False  # 개정 주장이 사실과 다름 (실존 법령의 허위 '최근 개정' 또는 없는 법령)


def _check_blacklist(blacklisted_org, blacklisted_business) -> _Finding:
    if blacklisted_org:
        message = f"'{blacklisted_org.name}' 기관명이 사칭 신고 이력에 등록되어 있습니다."
    elif blacklisted_business:
        message = f"'{blacklisted_business.name}' 업체명이 사칭 신고 이력에 등록되어 있습니다."
    else:
        return _Finding(Evidence(source="관리자 블랙리스트", result="블랙리스트에 등록된 이력 없음", matched=False))
    return _Finding(Evidence(source="관리자 블랙리스트", result=message, matched=True), points=50, critical=True)


async def _check_law(law_task: asyncio.Task | None, law_name: str | None) -> _LawFinding:
    if law_task is None:
        return _LawFinding(
            Evidence(source=_LAW_SOURCE, result="해당 없음 (법령 개정 관련 사칭 아님)", matched=False)
        )
    try:
        result = await law_task
    except LawApiError:
        return _LawFinding(
            Evidence(source=_LAW_SOURCE, result="API 호출 실패 (키 미승인 또는 서버 오류)", matched=False),
            points=5,  # 확인 불가
        )

    if not result["found"]:
        return _LawFinding(
            Evidence(
                source=_LAW_SOURCE,
                result=f"'{law_name}' 법령을 찾을 수 없음 — 법령명 자체가 허위일 가능성",
                matched=False,
            ),
            points=35,
            critical=True,
            contradicted=True,
        )
    if result["is_recent"]:
        return _LawFinding(
            Evidence(
                source=_LAW_SOURCE,
                result=f"최근 개정 이력 있음 (시행일: {result['current_law']['enforcement_date']})",
                matched=True,
            ),
            points=-10,  # 실제 최근 개정 이력과 일치
            found=True,
        )
    return _LawFinding(
        Evidence(
            source=_LAW_SOURCE,
            result="최근 개정 이력 없음 — 사칭범이 언급한 '최근 개정'과 불일치",
            matched=False,
        ),
        points=25,
        found=True,
        contradicted=True,
    )


def _check_business(matched_businesses, target_business: str) -> _Finding:
    if matched_businesses:
        names = ", ".join(b.company_name for b in matched_businesses)
        return _Finding(
            Evidence(source="소방청_소방시설업 현황", result=f"등록된 소방시설업체 확인됨: {names}", matched=True),
            points=-15,
        )
    return _Finding(
        Evidence(
            source="소방청_소방시설업 현황",
            result=f"'{target_business}'와 일치하는 등록업체를 찾을 수 없음",
            matched=False,
        ),
        points=30,
        critical=True,
    )


def _check_phrases(matched_patterns: dict[str, list[str]]) -> _Finding:
    if not matched_patterns:
        return _Finding(
            Evidence(source="사기 의심 문구 패턴 분석", result="전형적인 사기 문구가 발견되지 않음", matched=False)
        )
    all_keywords = [kw for kws in matched_patterns.values() for kw in kws]
    categories = ", ".join(matched_patterns.keys())
    return _Finding(
        Evidence(
            source="사기 의심 문구 패턴 분석",
            result=f"전형적인 사칭 사기 문구가 발견됨 ({categories}): {', '.join(all_keywords)}",
            matched=True,
        ),
        # 카테고리 수에 비례해 위험 점수 가중 (카테고리당 15점, 최대 45점)
        points=min(45, len(matched_patterns) * 15),
    )


def _check_account_request(*, has_scam_phrase: bool, has_unregistered_business: bool) -> _Finding:
    """계좌번호 요구 자체는 약한 신호지만, 다른 신호와 결합되면 가중한다."""
    points = 10
    result = "계좌번호 요구가 확인되었습니다"
    if has_scam_phrase:
        points += 25
        result += " (사기 의심 문구와 결합되어 위험도 상승)"
    if has_unregistered_business:
        points += 15
        result += " (미등록 업체의 요구라 위험도 상승)"
    return _Finding(
        Evidence(source=_ACCOUNT_SOURCE, result=result, matched=has_scam_phrase or has_unregistered_business),
        points=points,
    )


def _check_fraud_history(fraud: FraudAccountResult) -> _Finding:
    if fraud.reported:
        return _Finding(
            Evidence(
                source=_FRAUD_SOURCE,
                result=(
                    f"최근 {fraud.window_days}일간 이 계좌로 "
                    f"{fraud.report_count}건의 의심 신고가 접수되었습니다 "
                    f"({fraud.source}) — 사기 계좌일 가능성이 매우 높습니다."
                ),
                matched=True,
            ),
            points=55,
        )
    if fraud.checked:
        result = (
            f"{fraud.source}에는 반복 접수 기록이 없습니다 "
            f"(최근 {fraud.window_days}일 {fraud.report_count}건). "
            "경찰청·더치트에서 직접 조회해 최종 확인하세요."
        )
    else:
        result = "조회 수단이 없어 확인하지 못했습니다. 경찰청·더치트에서 직접 조회하세요."
    return _Finding(Evidence(source=_FRAUD_SOURCE, result=result, matched=False))


def _grade(score: int) -> tuple[str, str]:
    """최종 점수를 위험도와 사용자 권고 문구로 변환한다."""
    if score >= 60:
        return "danger", "매우 위험합니다. 요구에 응하지 마시고 관할 소방서 또는 112에 즉시 신고하세요."
    if score >= 30:
        return "caution", "의심스러운 정황이 있습니다. 관할 소방서에 직접 전화하여 사실 여부를 확인하세요."
    return "safe", "뚜렷한 위험 신호는 없으나, 금전이나 개인정보를 요구받았다면 기관에 재확인하세요."


@router.post(
    "/verify",
    response_model=VerifyResponse,
    summary="소방기관 사칭 진위확인",
    description=(
        "사용자가 입력한 소방기관 사칭 의심 정보(발신 기관명, 담당자명, "
        "요구 사유, 대상 업체, 계좌번호 등)를 법제처 법령 변경이력, "
        "소방청 소방시설업 현황 등 공공데이터와 대조하여 "
        "위험도(safe/caution/danger)를 판정합니다."
    ),
)
async def verify(payload: VerifyRequest, db: AsyncSession = Depends(get_db)):
    money_requested = payload.account_number is not None

    # --- AI 판정을 공공데이터 대조와 동시에 시작 (프롬프트는 규칙 점수에 의존하지 않음) ---
    ai_task = asyncio.create_task(
        request_scam_assessment(
            claimed_org=payload.claimed_org,
            claimed_person=payload.claimed_person,
            claim_type=payload.claim_type,
            target_business=payload.target_business,
            law_name=payload.law_name,
            has_account_number=money_requested,
        )
    )

    # 법제처 조회(외부 API, 캐시 미스 시 ~1초)도 DB 대조를 기다리지 않고 미리 시작한다
    law_task = (
        asyncio.create_task(check_recent_amendment(payload.law_name))
        if payload.claim_type == "law_amendment" and payload.law_name
        else None
    )

    # --- 공공데이터·자체 데이터 대조 ---
    blacklisted_org = await is_blacklisted(db, "org", payload.claimed_org)
    blacklisted_business = await is_blacklisted(db, "business", payload.target_business)
    blacklist = _check_blacklist(blacklisted_org, blacklisted_business)

    law = await _check_law(law_task, payload.law_name)

    matched_businesses = await find_business_by_name(db, payload.target_business)
    business = _check_business(matched_businesses, payload.target_business)

    matched_patterns = detect_scam_phrases(f"{payload.claim_type} {payload.law_name or ''}")
    phrases = _check_phrases(matched_patterns)

    findings = [blacklist, law, business, phrases]

    account_hash = account_fingerprint(payload.account_number)
    if money_requested:
        findings.append(
            _check_account_request(
                has_scam_phrase=bool(matched_patterns),
                has_unregistered_business=not matched_businesses,
            )
        )
        fraud = await get_fraud_account_provider(db).check(account_hash)
        findings.append(_check_fraud_history(fraud))
    else:
        findings.append(
            _Finding(Evidence(source=_ACCOUNT_SOURCE, result="계좌번호 요구 없음", matched=False))
        )

    # --- 규칙 기반 점수 ---
    rule_score = max(0, min(100, sum(f.points for f in findings)))
    # 치명적 신호가 있으면 다른 안전 신호로 상쇄되더라도 최소 caution 단계(30점) 이상은 보장한다.
    if any(f.critical for f in findings):
        rule_score = max(rule_score, 30)

    # --- AI(로컬 LLM) 사기 판정 — 위에서 동시에 시작한 결과를 회수해 가드레일 통과 ---
    ai_raw, ai_model_available = await ai_task
    ai_result = finalize_scam_assessment(ai_raw, ai_model_available, rule_score)
    ai_assessment = AiAssessment(
        score=ai_result.score,
        status=ai_result.status.value,
        label=ai_result.label,
        detail=ai_result.detail,
        used_in_verdict=ai_result.used_in_verdict,
    )

    # --- 최종 판정 ---
    # 사기를 '적극적으로' 가리키는 신호. 하나라도 있으면 '확인 불가'가 아니라 위험도를 매긴다.
    has_fraud_evidence = bool(
        blacklisted_org
        or blacklisted_business
        or matched_patterns                              # 전형적 사기 문구
        or law.contradicted                              # 법령 개정 주장이 사실과 다름
        or (money_requested and not matched_businesses)  # 미등록 업체가 금전 이체 요구
    )
    # 공공데이터로 실체가 확인된 항목 (등록된 소방시설업체 / 조회된 법령)
    has_verified_entity = bool(matched_businesses) or law.found

    score = rule_score
    if not has_fraud_evidence and not has_verified_entity:
        # 사기 신호도 없고 금전 요구도 없는데 입력한 기관·업체·법령이 공공데이터에
        # 전혀 안 잡히는 경우 — 위험도를 매길 근거가 없다(오탈자·미상 업체 조회 등).
        # 이 경우 AI 점수도 신뢰할 수 없으므로 최종 판정에 반영하지 않는다.
        risk_level, recommendation = "unverified", _UNVERIFIED_RECOMMENDATION
        ai_assessment.used_in_verdict = False
    else:
        # 신뢰 가능한 AI 점수가 더 높을 때만 보수적으로 상향(max).
        # AI가 폐기/보류/미응답이면 규칙 점수를 그대로 쓴다.
        if ai_result.used_in_verdict and ai_result.score is not None:
            score = max(rule_score, ai_result.score)
        risk_level, recommendation = _grade(score)

    db.add(
        VerifyLog(
            claimed_org=payload.claimed_org,
            claimed_person=payload.claimed_person,
            claim_type=payload.claim_type,
            target_business=payload.target_business,
            account_number=encrypt(payload.account_number),  # 암호화해서 저장
            account_hash=account_hash,  # 같은 계좌 반복 신고 집계용 (단방향 해시)
            risk_level=risk_level,
            score=score,
            rule_score=rule_score,
            ai_score=ai_result.score,
            ai_status=ai_result.status.value,
        )
    )
    await db.commit()

    return VerifyResponse(
        risk_level=risk_level,
        score=score,
        rule_score=rule_score,
        ai_assessment=ai_assessment,
        evidence=[f.evidence for f in findings],
        recommendation=recommendation,
    )
