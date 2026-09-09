import asyncio

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.blacklist import is_blacklisted
from app.core.crypto import encrypt
from app.core.database import get_db
from app.models.verify_log import VerifyLog
from app.schemas.verify import VerifyRequest, VerifyResponse, Evidence
from app.services.law_api import check_recent_amendment, LawApiError
from app.services.fire_business import find_business_by_name
from app.services.scam_patterns import detect_scam_phrases
from app.services.ai_verify import request_scam_assessment, finalize_scam_assessment
from app.schemas.verify import AiAssessment

router = APIRouter(prefix="/api/v1", tags=["verify"])


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
    risk_signals: list[tuple[int, str]] = []  # (점수, 이유)
    critical_signal_found = False  # 치명적 위험 신호(존재하지 않는 법령/업체 등) 발견 여부

    # --- AI 판정을 공공데이터 대조와 동시에 시작 (프롬프트는 규칙 점수에 의존하지 않음) ---
    ai_task = asyncio.create_task(
        request_scam_assessment(
            claimed_org=payload.claimed_org,
            claimed_person=payload.claimed_person,
            claim_type=payload.claim_type,
            target_business=payload.target_business,
            law_name=payload.law_name,
            has_account_number=payload.account_number is not None,
        )
    )

    # --- 0. 블랙리스트 대조 ---
    blacklisted_org = await is_blacklisted(db, "org", payload.claimed_org)
    blacklisted_business = await is_blacklisted(db, "business", payload.target_business)

    if blacklisted_org or blacklisted_business:
        blacklist_evidence = Evidence(
            source="관리자 블랙리스트",
            result=(
                f"'{blacklisted_org.name}' 기관명이 사칭 신고 이력에 등록되어 있습니다."
                if blacklisted_org
                else f"'{blacklisted_business.name}' 업체명이 사칭 신고 이력에 등록되어 있습니다."
            ),
            matched=True,
        )
        risk_signals.append((50, "관리자 블랙리스트에 등록된 기관/업체명"))
        critical_signal_found = True
    else:
        blacklist_evidence = Evidence(
            source="관리자 블랙리스트",
            result="블랙리스트에 등록된 이력 없음",
            matched=False,
        )

    # --- 1. 법제처 법령 변경이력 대조 ---
    law_found = False           # 법제처에서 실제로 조회된 법령인지
    law_misrepresented = False  # 실존 법령을 '최근 개정'이라 허위 주장했는지 (적극적 사기 신호)
    law_claimed_but_missing = False  # 법령 개정을 근거로 들면서 그 법령이 조회 안 됨 (적극적 사기 신호)
    if payload.claim_type == "law_amendment" and payload.law_name:
        try:
            result = await check_recent_amendment(payload.law_name)

            if not result["found"]:
                law_claimed_but_missing = True
                law_evidence = Evidence(
                    source="법제처_법령 변경이력 목록 조회",
                    result=f"'{payload.law_name}' 법령을 찾을 수 없음 — 법령명 자체가 허위일 가능성",
                    matched=False,
                )
                risk_signals.append((35, "존재하지 않는 법령명 언급"))
                critical_signal_found = True
            elif result["is_recent"]:
                law_found = True
                law_evidence = Evidence(
                    source="법제처_법령 변경이력 목록 조회",
                    result=f"최근 개정 이력 있음 (시행일: {result['current_law']['enforcement_date']})",
                    matched=True,
                )
                risk_signals.append((-10, "실제 최근 개정 이력과 일치"))
            else:
                law_found = True
                law_misrepresented = True
                law_evidence = Evidence(
                    source="법제처_법령 변경이력 목록 조회",
                    result="최근 개정 이력 없음 — 사칭범이 언급한 '최근 개정'과 불일치",
                    matched=False,
                )
                risk_signals.append((25, "최근 개정 이력 없음에도 개정을 주장"))
        except LawApiError:
            law_evidence = Evidence(
                source="법제처_법령 변경이력 목록 조회",
                result="API 호출 실패 (키 미승인 또는 서버 오류)",
                matched=False,
            )
            risk_signals.append((5, "법령 정보 조회 실패로 확인 불가"))
    else:
        law_evidence = Evidence(
            source="법제처_법령 변경이력 목록 조회",
            result="해당 없음 (법령 개정 관련 사칭 아님)",
            matched=False,
        )

    # --- 2. 소방청 소방시설업 현황 대조 ---
    matched_businesses = await find_business_by_name(db, payload.target_business)

    if matched_businesses:
        names = ", ".join(b.company_name for b in matched_businesses)
        biz_evidence = Evidence(
            source="소방청_소방시설업 현황",
            result=f"등록된 소방시설업체 확인됨: {names}",
            matched=True,
        )
        risk_signals.append((-15, "실제 등록된 소방시설업체와 일치"))
    else:
        biz_evidence = Evidence(
            source="소방청_소방시설업 현황",
            result=f"'{payload.target_business}'와 일치하는 등록업체를 찾을 수 없음",
            matched=False,
        )
        risk_signals.append((30, "소방시설업 등록 현황에 없는 업체명 언급"))
        critical_signal_found = True

    # --- 3. 사기 의심 문구 패턴 탐지 ---
    combined_text = f"{payload.claim_type} {payload.law_name or ''}"
    matched_patterns = detect_scam_phrases(combined_text)

    if matched_patterns:
        all_keywords = [kw for kws in matched_patterns.values() for kw in kws]
        categories = ", ".join(matched_patterns.keys())
        phrase_evidence = Evidence(
            source="사기 의심 문구 패턴 분석",
            result=f"전형적인 사칭 사기 문구가 발견됨 ({categories}): {', '.join(all_keywords)}",
            matched=True,
        )
        # 카테고리 수에 비례해 위험 점수 가중 (카테고리당 15점, 최대 45점)
        risk_signals.append((min(45, len(matched_patterns) * 15), f"사기 의심 문구 탐지: {categories}"))
    else:
        phrase_evidence = Evidence(
            source="사기 의심 문구 패턴 분석",
            result="전형적인 사기 문구가 발견되지 않음",
            matched=False,
        )

    # --- 4. 계좌번호 요구 위험도 (다른 신호와 결합하여 가중치 계산) ---
    if payload.account_number:
        has_scam_phrase = bool(matched_patterns)
        has_unregistered_business = not matched_businesses

        account_score = 10  # 기본값: 계좌번호 요구 자체는 약한 신호
        reasons = ["계좌번호 제공 요구"]

        if has_scam_phrase:
            account_score += 25
            reasons.append("사기 의심 문구와 결합")
        if has_unregistered_business:
            account_score += 15
            reasons.append("미등록 업체의 계좌 요구")

        risk_signals.append((account_score, " · ".join(reasons)))

        account_evidence = Evidence(
            source="계좌번호 요구 위험도 분석",
            result=(
                f"계좌번호 요구가 확인되었습니다"
                + (" (사기 의심 문구와 결합되어 위험도 상승)" if has_scam_phrase else "")
                + (" (미등록 업체의 요구라 위험도 상승)" if has_unregistered_business else "")
            ),
            matched=has_scam_phrase or has_unregistered_business,
        )
    else:
        account_evidence = Evidence(
            source="계좌번호 요구 위험도 분석",
            result="계좌번호 요구 없음",
            matched=False,
        )

    # --- 5. 규칙 기반 점수 계산 ---
    rule_score = sum(points for points, _ in risk_signals)
    rule_score = max(0, min(100, rule_score))

    # 존재하지 않는 법령/업체명처럼 치명적 신호가 있으면, 다른 안전 신호로 상쇄되더라도
    # 최소 caution 단계(30점) 이상은 보장한다.
    if critical_signal_found:
        rule_score = max(rule_score, 30)

    # --- 6. AI(로컬 LLM) 사기 판정 — 위에서 동시에 시작한 결과를 회수해 가드레일 통과 ---
    ai_raw, ai_model_available = await ai_task
    ai_result = finalize_scam_assessment(ai_raw, ai_model_available, rule_score)

    ai_assessment = AiAssessment(
        score=ai_result.score,
        status=ai_result.status.value,
        label=ai_result.label,
        detail=ai_result.detail,
        used_in_verdict=ai_result.used_in_verdict,
    )

    # --- 7. 최종 판정 ---
    # 사기를 '적극적으로' 가리키는 신호. 하나라도 있으면 '확인 불가'가 아니라 위험도를 매긴다.
    money_requested = payload.account_number is not None
    has_fraud_evidence = bool(
        blacklisted_org
        or blacklisted_business
        or matched_patterns                       # 전형적 사기 문구
        or law_misrepresented                     # 실존 법령을 '최근 개정'이라 허위 주장
        or law_claimed_but_missing                # 존재하지 않는 법령을 개정 근거로 제시
        or (money_requested and not matched_businesses)  # 미등록 업체가 금전 이체 요구
    )
    # 공공데이터로 실체가 확인된 항목 (등록된 소방시설업체 / 조회된 법령)
    has_verified_entity = bool(matched_businesses) or law_found

    if not has_fraud_evidence and not has_verified_entity:
        # 사기 신호도 없고 금전 요구도 없는데 입력한 기관·업체·법령이 공공데이터에
        # 전혀 안 잡히는 경우 — 위험도를 매길 근거가 없다(오탈자·미상 업체 조회 등).
        # 이 경우 AI 점수도 신뢰할 수 없으므로 최종 판정에 반영하지 않는다.
        risk_level = "unverified"
        score = rule_score
        recommendation = (
            "입력하신 기관·업체·법령을 공공데이터에서 확인할 수 없어 위험 여부를 판정할 수 없습니다. "
            "받으신 연락처로 회신하지 마시고, 소방청 홈페이지나 정부24에서 관할 소방서 대표번호를 찾아 "
            "직접 전화로 사실 여부를 확인하세요. 확인 전까지 금전·개인정보 요구에는 절대 응하지 마세요."
        )
        if ai_assessment.used_in_verdict:
            ai_assessment = ai_assessment.model_copy(update={"used_in_verdict": False})
    else:
        # 최종 점수: 신뢰 가능한 AI 점수가 더 높을 때만 보수적으로 상향(max).
        # AI가 폐기/보류/미응답이면 규칙 점수를 그대로 쓴다.
        score = rule_score
        if ai_result.used_in_verdict and ai_result.score is not None:
            score = max(rule_score, ai_result.score)

        if score >= 60:
            risk_level = "danger"
            recommendation = "매우 위험합니다. 요구에 응하지 마시고 관할 소방서 또는 112에 즉시 신고하세요."
        elif score >= 30:
            risk_level = "caution"
            recommendation = "의심스러운 정황이 있습니다. 관할 소방서에 직접 전화하여 사실 여부를 확인하세요."
        else:
            risk_level = "safe"
            recommendation = "뚜렷한 위험 신호는 없으나, 금전이나 개인정보를 요구받았다면 기관에 재확인하세요."

    evidence = [blacklist_evidence, law_evidence, biz_evidence, phrase_evidence, account_evidence]

    log = VerifyLog(
        claimed_org=payload.claimed_org,
        claimed_person=payload.claimed_person,
        claim_type=payload.claim_type,
        target_business=payload.target_business,
        account_number=encrypt(payload.account_number),  # 암호화해서 저장
        risk_level=risk_level,
        score=score,
        rule_score=rule_score,
        ai_score=ai_result.score,
        ai_status=ai_result.status.value,
    )
    db.add(log)
    await db.commit()

    return VerifyResponse(
        risk_level=risk_level,
        score=score,
        rule_score=rule_score,
        ai_assessment=ai_assessment,
        evidence=evidence,
        recommendation=recommendation,
    )