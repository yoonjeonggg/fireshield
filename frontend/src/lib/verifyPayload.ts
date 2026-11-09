import { ClaimType, VerifyRequest } from "@/types/verify";

// 법령명 칸이 보이는 요구 사유 — 숨겨진 칸에 남아 있는 값은 전송하지 않는다
export const CLAIM_TYPES_WITH_LAW: ClaimType[] = ["law_amendment", "custom"];

export const ACCOUNT_NUMBER_PATTERN = /^[0-9-]{6,25}$/;

export interface VerifyFormValues {
  claimedOrg: string;
  claimedPerson: string;
  claimType: ClaimType;
  claimTypeCustom: string;
  targetBusiness: string;
  accountNumber: string;
  lawName: string;
}

export type BuildVerifyPayloadResult =
  | { ok: true; payload: VerifyRequest }
  | { ok: false; error: string };

/** 입력폼 값을 검증하고 /verify 요청 본문으로 정리한다 (앞뒤 공백 제거, 빈 선택 항목 생략). */
export function buildVerifyPayload(values: VerifyFormValues): BuildVerifyPayloadResult {
  const claimedOrg = values.claimedOrg.trim();
  const claimedPerson = values.claimedPerson.trim();
  const targetBusiness = values.targetBusiness.trim();
  const claimType = values.claimType === "custom" ? values.claimTypeCustom.trim() : values.claimType;
  const accountNumber = values.accountNumber.trim();

  if (!claimedOrg || !claimedPerson || !targetBusiness) {
    return { ok: false, error: "공백만으로는 입력할 수 없습니다. 내용을 정확히 입력해주세요." };
  }

  if (values.claimType === "custom" && claimType.length < 5) {
    return { ok: false, error: "요구 사유를 5자 이상 입력해주세요." };
  }

  if (accountNumber && !ACCOUNT_NUMBER_PATTERN.test(accountNumber)) {
    return { ok: false, error: "계좌번호는 숫자와 하이픈(-)만 입력 가능합니다. (예: 110-123-456789)" };
  }

  const showLawName = CLAIM_TYPES_WITH_LAW.includes(values.claimType);

  return {
    ok: true,
    payload: {
      claimed_org: claimedOrg,
      claimed_person: claimedPerson,
      claim_type: claimType,
      target_business: targetBusiness,
      account_number: accountNumber || undefined,
      law_name: (showLawName && values.lawName.trim()) || undefined,
    },
  };
}
