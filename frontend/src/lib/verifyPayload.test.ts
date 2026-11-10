import { describe, expect, it } from "vitest";
import { buildVerifyPayload, VerifyFormValues } from "@/lib/verifyPayload";

const base: VerifyFormValues = {
  claimedOrg: "서울소방서",
  claimedPerson: "김소방",
  claimType: "law_amendment",
  claimTypeCustom: "",
  targetBusiness: "한국소방설비",
  accountNumber: "",
  lawName: "",
};

function build(overrides: Partial<VerifyFormValues>) {
  return buildVerifyPayload({ ...base, ...overrides });
}

describe("buildVerifyPayload", () => {
  it("앞뒤 공백을 제거하고 비어 있는 선택 항목은 생략한다", () => {
    const result = build({ claimedOrg: "  서울소방서 ", targetBusiness: " 한국소방설비\t" });
    expect(result).toEqual({
      ok: true,
      payload: {
        claimed_org: "서울소방서",
        claimed_person: "김소방",
        claim_type: "law_amendment",
        target_business: "한국소방설비",
        account_number: undefined,
        law_name: undefined,
      },
    });
  });

  it.each(["claimedOrg", "claimedPerson", "targetBusiness"] as const)(
    "필수 항목 %s가 공백뿐이면 거부한다",
    (field) => {
      const result = build({ [field]: "   " });
      expect(result).toEqual({ ok: false, error: expect.stringContaining("공백만으로는") });
    },
  );

  it("직접 입력한 요구 사유가 5자 미만이면 거부한다", () => {
    const result = build({ claimType: "custom", claimTypeCustom: "  소화기 " });
    expect(result).toEqual({ ok: false, error: "요구 사유를 5자 이상 입력해주세요." });
  });

  it("직접 입력한 요구 사유를 claim_type으로 보낸다", () => {
    const result = build({ claimType: "custom", claimTypeCustom: " 소화기 교체 의무화 " });
    expect(result.ok && result.payload.claim_type).toBe("소화기 교체 의무화");
  });

  it.each(["110-123-456789", "110123456789"])("올바른 계좌번호 %s는 통과한다", (accountNumber) => {
    const result = build({ accountNumber: ` ${accountNumber} ` });
    expect(result.ok && result.payload.account_number).toBe(accountNumber);
  });

  it.each(["110 123 456", "12345", "abc-123-456", "1".repeat(26)])(
    "잘못된 계좌번호 %s는 거부한다",
    (accountNumber) => {
      const result = build({ accountNumber });
      expect(result).toEqual({ ok: false, error: expect.stringContaining("계좌번호는") });
    },
  );

  it("법령명 칸이 보이는 요구 사유에서만 법령명을 보낸다", () => {
    expect(build({ claimType: "law_amendment", lawName: " 소방시설법 " })).toMatchObject({
      ok: true,
      payload: { law_name: "소방시설법" },
    });
    expect(
      build({ claimType: "custom", claimTypeCustom: "법령 개정 안내", lawName: "소방시설법" }),
    ).toMatchObject({ ok: true, payload: { law_name: "소방시설법" } });

    // 법령명 칸이 숨겨진 사유로 바꾼 뒤 남아 있는 값은 전송하지 않는다
    const hidden = build({ claimType: "subsidy", lawName: "소방시설법" });
    expect(hidden.ok && hidden.payload.law_name).toBeUndefined();
  });
});
