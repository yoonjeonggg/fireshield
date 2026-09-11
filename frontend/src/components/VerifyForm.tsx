"use client";

import { useEffect, useRef, useState } from "react";
import { Building2, User, FileText, Landmark, LoaderCircle, Check } from "lucide-react";
import { verifyRequest } from "@/lib/api";
import { ClaimType, VerifyResponse } from "@/types/verify";
import VerifyResult from "@/components/VerifyResult";

const inputStyle: React.CSSProperties = {
  width: "100%",
  border: "1.5px solid var(--paper-200)",
  borderRadius: 10,
  background: "var(--paper-50)",
  padding: "12px 14px 12px 40px",
  fontSize: 14,
  color: "var(--ink-950)",
  outline: "none",
  fontFamily: "var(--font-body)",
};

const iconStyle: React.CSSProperties = {
  position: "absolute",
  left: 12,
  top: "50%",
  transform: "translateY(-50%)",
  color: "var(--ink-400)",
  pointerEvents: "none",
};

const LOADING_STEPS = [
  "법제처 법령 변경이력 대조 중",
  "소방청 소방시설업 현황 대조 중",
  "위험도 종합 판정 중",
];

export default function VerifyForm() {
  const [claimedOrg, setClaimedOrg] = useState("");
  const [claimedPerson, setClaimedPerson] = useState("");
  const [claimType, setClaimType] = useState<ClaimType>("law_amendment");
  const [claimTypeCustom, setClaimTypeCustom] = useState("");
  const [targetBusiness, setTargetBusiness] = useState("");
  const [accountNumber, setAccountNumber] = useState("");
  const [lawName, setLawName] = useState("");

  const [result, setResult] = useState<VerifyResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [stepIndex, setStepIndex] = useState(-1);

  const stepTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    return () => {
      if (stepTimerRef.current) clearInterval(stepTimerRef.current);
    };
  }, []);

  function startStepAnimation() {
    setStepIndex(0);
    let i = 0;
    stepTimerRef.current = setInterval(() => {
      i += 1;
      if (i >= LOADING_STEPS.length) {
        if (stepTimerRef.current) clearInterval(stepTimerRef.current);
        return;
      }
      setStepIndex(i);
    }, 500);
  }

  function stopStepAnimation() {
    if (stepTimerRef.current) clearInterval(stepTimerRef.current);
    setStepIndex(-1);
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setResult(null);

    const trimmedOrg = claimedOrg.trim();
    const trimmedPerson = claimedPerson.trim();
    const trimmedBusiness = targetBusiness.trim();
    const effectiveClaimType = claimType === "custom" ? claimTypeCustom.trim() : claimType;

    if (!trimmedOrg || !trimmedPerson || !trimmedBusiness) {
      setError("공백만으로는 입력할 수 없습니다. 내용을 정확히 입력해주세요.");
      return;
    }

    if (claimType === "custom" && effectiveClaimType.length < 5) {
      setError("요구 사유를 5자 이상 입력해주세요.");
      return;
    }

    if (accountNumber.trim()) {
      const accountPattern = /^[0-9-]{6,25}$/;
      if (!accountPattern.test(accountNumber.trim())) {
        setError("계좌번호는 숫자와 하이픈(-)만 입력 가능합니다. (예: 110-123-456789)");
        return;
      }
    }

    setLoading(true);
    startStepAnimation();

    // 체크리스트 애니메이션이 최소한 끝까지 재생되도록, API 응답과 최소 대기시간 중 늦게 끝나는 쪽을 기다림
    const minDelay = new Promise((resolve) => setTimeout(resolve, LOADING_STEPS.length * 500));

    try {
      const [data] = await Promise.all([
        verifyRequest({
          claimed_org: trimmedOrg,
          claimed_person: trimmedPerson,
          claim_type: effectiveClaimType,
          target_business: trimmedBusiness,
          account_number: accountNumber.trim() || undefined,
          law_name: lawName.trim() || undefined,
        }),
        minDelay,
      ]);
      setResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "알 수 없는 오류가 발생했습니다.");
    } finally {
      setLoading(false);
      stopStepAnimation();
    }
  }

  return (
    <section
      style={{
        background: "linear-gradient(160deg, var(--primary-900) 0%, var(--primary-700) 55%, var(--primary-500) 100%)",
        padding: "56px 0 72px",
      }}
    >
      <div className="max-w-[680px] mx-auto px-5 text-center">
        <span
          className="inline-flex items-center gap-2 text-white"
          style={{
            background: "rgba(255,255,255,.1)",
            border: "1px solid rgba(255,255,255,.15)",
            borderRadius: 999,
            padding: "7px 14px",
            fontSize: 12.5,
            fontWeight: 500,
          }}
        >
          <span
            style={{
              width: 6,
              height: 6,
              borderRadius: 999,
              background: "var(--accent-500)",
              display: "inline-block",
            }}
          />
          소방기관 사칭 사기 전국 확산 중 — 송금 전에 꼭 확인하세요
        </span>

        <h1
          className="text-white font-bold mt-4"
          style={{ fontFamily: "var(--font-head)", fontSize: "clamp(28px, 4.2vw, 40px)" }}
        >
          의심스러운 연락을
          <br />
          받으셨나요?
        </h1>
        <p className="mt-3" style={{ color: "rgba(255,255,255,.68)", fontSize: 15 }}>
          소방점검·법령개정을 사칭한 연락을 받으셨다면,
          <br />
          아래 정보를 입력하고 <strong style={{ color: "#fff" }}>실시간으로 진위를 확인</strong>하세요.
        </p>

        {/* 입력 카드 */}
        <div
          className="text-left mt-8"
          style={{
            background: "var(--white)",
            borderRadius: 18,
            padding: 28,
            boxShadow: "0 20px 50px -20px rgba(9,20,40,.5)",
          }}
        >
          <form onSubmit={handleSubmit}>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-4">
              <div>
                <label className="block text-[13px] font-semibold mb-1.5" style={{ color: "var(--ink-800)" }}>
                  발신 기관명
                </label>
                <div className="relative">
                  <Building2 size={17} strokeWidth={2} style={iconStyle} />
                  <input
                    style={inputStyle}
                    value={claimedOrg}
                    onChange={(e) => setClaimedOrg(e.target.value)}
                    placeholder="예: OO소방서"
                    required
                  />
                </div>
              </div>
              <div>
                <label className="block text-[13px] font-semibold mb-1.5" style={{ color: "var(--ink-800)" }}>
                  담당자명
                </label>
                <div className="relative">
                  <User size={17} strokeWidth={2} style={iconStyle} />
                  <input
                    style={inputStyle}
                    value={claimedPerson}
                    onChange={(e) => setClaimedPerson(e.target.value)}
                    placeholder="예: 홍길동"
                    required
                  />
                </div>
              </div>
            </div>

            <div className="mb-4">
              <label className="block text-[13px] font-semibold mb-1.5" style={{ color: "var(--ink-800)" }}>
                요구 사유
              </label>
              <select
                style={{ ...inputStyle, paddingLeft: 14 }}
                value={claimType}
                onChange={(e) => setClaimType(e.target.value as ClaimType)}
              >
                <option value="law_amendment">법령 개정</option>
                <option value="inspection">점검</option>
                <option value="subsidy">보조금</option>
                <option value="custom">직접 입력</option>
              </select>

              {claimType === "custom" && (
                <input
                  style={{ ...inputStyle, paddingLeft: 14, marginTop: 10 }}
                  value={claimTypeCustom}
                  onChange={(e) => setClaimTypeCustom(e.target.value)}
                  placeholder="예: 화재보험 가입 강요, 소화기 교체 안내 등 직접 입력"
                  required
                />
              )}
            </div>

            {(claimType === "law_amendment" || claimType === "custom") && (
              <div className="mb-4">
                <label className="block text-[13px] font-semibold mb-1.5" style={{ color: "var(--ink-800)" }}>
                  언급된 법령명{" "}
                  <span className="font-normal" style={{ color: "var(--ink-400)" }}>
                    (해당 시)
                  </span>
                </label>
                <div className="relative">
                  <FileText size={17} strokeWidth={2} style={iconStyle} />
                  <input
                    style={inputStyle}
                    value={lawName}
                    onChange={(e) => setLawName(e.target.value)}
                    placeholder="예: 소방시설 설치 및 관리에 관한 법률"
                  />
                </div>
              </div>
            )}

            <div className="mb-4">
              <label className="block text-[13px] font-semibold mb-1.5" style={{ color: "var(--ink-800)" }}>
                대상 업체명
              </label>
              <div className="relative">
                <Building2 size={17} strokeWidth={2} style={iconStyle} />
                <input
                  style={inputStyle}
                  value={targetBusiness}
                  onChange={(e) => setTargetBusiness(e.target.value)}
                  placeholder="예: 강남소방"
                  required
                />
              </div>
            </div>

            <div className="mb-5">
              <label className="block text-[13px] font-semibold mb-1.5" style={{ color: "var(--ink-800)" }}>
                요구받은 계좌번호{" "}
                <span className="font-normal" style={{ color: "var(--ink-400)" }}>
                  (선택사항)
                </span>
              </label>
              <div className="relative">
                <Landmark size={17} strokeWidth={2} style={iconStyle} />
                <input
                  style={inputStyle}
                  value={accountNumber}
                  onChange={(e) => setAccountNumber(e.target.value)}
                  placeholder="예: 110-xxx-xxxxxx"
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full flex items-center justify-center gap-2"
              style={{
                padding: 15,
                border: "none",
                borderRadius: 12,
                background: "var(--accent-500)",
                color: "#fff",
                fontWeight: 700,
                fontSize: 15.5,
                cursor: loading ? "progress" : "pointer",
                opacity: loading ? 0.85 : 1,
              }}
            >
              {loading && <LoaderCircle size={18} strokeWidth={2} className="animate-spin" />}
              {loading ? "대조 중..." : "진위 확인하기"}
            </button>

            {/* 로딩 체크리스트 */}
            {loading && (
              <div
                className="mt-4 p-4"
                style={{ background: "var(--paper-50)", borderRadius: 10, border: "1px solid var(--paper-200)" }}
              >
                {LOADING_STEPS.map((step, i) => {
                  const done = i < stepIndex;
                  const active = i === stepIndex;
                  return (
                    <div
                      key={step}
                      className="flex items-center gap-2 py-1"
                      style={{
                        opacity: i <= stepIndex ? 1 : 0.35,
                        animation: i === stepIndex ? "fireshield-check-in 200ms ease" : undefined,
                      }}
                    >
                      <span
                        className="flex items-center justify-center shrink-0"
                        style={{
                          width: 18,
                          height: 18,
                          borderRadius: "50%",
                          background: done ? "var(--safe-100)" : "var(--paper-200)",
                          color: done ? "var(--safe-600)" : "var(--ink-400)",
                        }}
                      >
                        {done ? (
                          <Check size={12} strokeWidth={3} />
                        ) : active ? (
                          <LoaderCircle size={11} strokeWidth={3} className="animate-spin" />
                        ) : null}
                      </span>
                      <span className="text-xs" style={{ color: "var(--ink-600)" }}>
                        {step}
                      </span>
                    </div>
                  );
                })}
              </div>
            )}
          </form>
        </div>

        {error && (
          <div
            className="mt-4 p-4 text-left"
            style={{ background: "var(--danger-100)", color: "var(--danger-600)", borderRadius: 10, fontSize: 13.5 }}
          >
            {error}
          </div>
        )}

        {result && <VerifyResult result={result} accountNumber={accountNumber.trim() || undefined} />}
      </div>
    </section>
  );
}