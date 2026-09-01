from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.crypto import encrypt

from app.core.database import get_db
from app.models.verify_log import VerifyLog
from app.schemas.verify import VerifyRequest, VerifyResponse, Evidence
from app.services.law_api import check_recent_amendment, LawApiError
from app.services.fire_business import find_business_by_name

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

    # --- 1. 법제처 법령 변경이력 대조 ---
    if payload.claim_type == "law_amendment" and payload.law_name:
        try:
            result = await check_recent_amendment(payload.law_name)

            if not result["found"]:
                law_evidence = Evidence(
                    source="법제처_법령 변경이력 목록 조회",
                    result=f"'{payload.law_name}' 법령을 찾을 수 없음 — 법령명 자체가 허위일 가능성",
                    matched=False,
                )
                risk_signals.append((35, "존재하지 않는 법령명 언급"))
            elif result["is_recent"]:
                law_evidence = Evidence(
                    source="법제처_법령 변경이력 목록 조회",
                    result=f"최근 개정 이력 있음 (시행일: {result['current_law']['enforcement_date']})",
                    matched=True,
                )
                risk_signals.append((-10, "실제 최근 개정 이력과 일치"))
            else:
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

    # --- 3. 계좌번호 요구 여부 ---
    if payload.account_number:
        risk_signals.append((20, "계좌번호 제공 요구 — 공공기관은 통상 계좌번호를 요구하지 않음"))

    # --- 4. 최종 점수 계산 ---
    score = sum(points for points, _ in risk_signals)
    score = max(0, min(100, score))

    if score >= 60:
        risk_level = "danger"
        recommendation = "매우 위험합니다. 요구에 응하지 마시고 관할 소방서 또는 112에 즉시 신고하세요."
    elif score >= 30:
        risk_level = "caution"
        recommendation = "의심스러운 정황이 있습니다. 관할 소방서에 직접 전화하여 사실 여부를 확인하세요."
    else:
        risk_level = "safe"
        recommendation = "뚜렷한 위험 신호는 없으나, 금전이나 개인정보를 요구받았다면 기관에 재확인하세요."

    evidence = [law_evidence, biz_evidence]

    log = VerifyLog(
        claimed_org=payload.claimed_org,
        claimed_person=payload.claimed_person,
        claim_type=payload.claim_type,
        target_business=payload.target_business,
        account_number=encrypt(payload.account_number),  # 암호화해서 저장
        risk_level=risk_level,
        score=score,
    )
    db.add(log)
    await db.commit()

    return VerifyResponse(
        risk_level=risk_level,
        score=score,
        evidence=evidence,
        recommendation=recommendation,
    )