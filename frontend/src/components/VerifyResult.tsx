"use client";

import { useState } from "react";
import { ShieldCheck, AlertTriangle, ShieldAlert, Check, X, ExternalLink, Copy } from "lucide-react";
import { VerifyResponse, RiskLevel } from "@/types/verify";

const OFFICIAL_ACCOUNT_LOOKUPS: { label: string; desc: string; href: string }[] = [
  {
    label: "경찰청 사이버사기 피해신고 이력조회",
    desc: "최근 3개월간 3회 이상 신고된 계좌·전화번호와 대조",
    href: "https://www.police.go.kr/www/security/cyber/cyber04.jsp",
  },
  {
    label: "더치트(THE CHEAT) 사기 피해 조회",
    desc: "민간 사기 피해 신고 데이터베이스 조회",
    href: "https://thecheat.co.kr/rb/?mod=_search",
  },
];

type LevelStyle = {
  label: string;
  verdict: string;
  headBg: string;
  headColor: string;
  barColor: string;
  chipBg: string;
  chipColor: string;
  Icon: typeof ShieldCheck;
};

const RISK_CONFIG: Record<RiskLevel, LevelStyle> = {
  safe: {
    label: "판정 결과 · 안전",
    verdict: "정상 — 위험 요소 낮음",
    headBg: "linear-gradient(120deg, var(--safe-600), var(--safe-500))",
    headColor: "#fff",
    barColor: "var(--safe-500)",
    chipBg: "var(--safe-100)",
    chipColor: "var(--safe-600)",
    Icon: ShieldCheck,
  },
  caution: {
    label: "판정 결과 · 의심",
    verdict: "의심 — 추가 확인 필요",
    headBg: "linear-gradient(120deg, var(--caution-600), var(--caution-500))",
    headColor: "var(--ink-950)",
    barColor: "var(--caution-500)",
    chipBg: "var(--caution-100)",
    chipColor: "var(--caution-600)",
    Icon: AlertTriangle,
  },
  danger: {
    label: "판정 결과 · 위험",
    verdict: "위험 — 사기 의심",
    headBg: "linear-gradient(120deg, var(--danger-600), var(--danger-500))",
    headColor: "#fff",
    barColor: "var(--danger-500)",
    chipBg: "var(--danger-100)",
    chipColor: "var(--danger-600)",
    Icon: ShieldAlert,
  },
};

export default function VerifyResult({
  result,
  accountNumber,
}: {
  result: VerifyResponse;
  accountNumber?: string;
}) {
  const config = RISK_CONFIG[result.risk_level];
  const Icon = config.Icon;
  const [copied, setCopied] = useState(false);

  async function copyAccount() {
    if (!accountNumber) return;
    try {
      await navigator.clipboard.writeText(accountNumber);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* 클립보드 접근 불가 시 무시 */
    }
  }

  return (
    <div
      className="mt-6 text-left overflow-hidden"
      style={{
        background: "var(--white)",
        borderRadius: 18,
        border: "1px solid var(--paper-200)",
        boxShadow: "0 20px 50px -25px rgba(9,20,40,.4)",
        animation: "fireshield-rise 220ms ease",
      }}
    >
      {/* 헤드 */}
      <div
        className="flex items-center gap-4"
        style={{ background: config.headBg, color: config.headColor, padding: "22px 26px" }}
      >
        <div
          className="flex items-center justify-center shrink-0"
          style={{
            width: 48,
            height: 48,
            borderRadius: "50%",
            background: "rgba(255,255,255,.22)",
          }}
        >
          <Icon size={26} strokeWidth={2} color={config.headColor} />
        </div>
        <div>
          <div className="text-[11.5px] font-semibold opacity-85" style={{ letterSpacing: "0.03em" }}>
            {config.label}
          </div>
          <div className="font-bold text-[21px]" style={{ fontFamily: "var(--font-head)" }}>
            {config.verdict}
          </div>
        </div>
        <span className="ml-auto text-2xl font-bold opacity-90">{result.score}</span>
      </div>

      {/* 본문 */}
      <div style={{ padding: "22px 26px 26px" }}>
        {/* 점수 바 */}
        <div
          style={{
            height: 7,
            borderRadius: 999,
            background: "var(--paper-100)",
            overflow: "hidden",
            marginBottom: 18,
          }}
        >
          <div
            style={{
              height: "100%",
              width: `${result.score}%`,
              background: config.barColor,
              borderRadius: 999,
              transition: "width .6s ease",
            }}
          />
        </div>

        {/* 근거 목록 */}
        <div className="flex flex-col gap-2.5">
          {result.evidence.map((ev, i) => (
            <div
              key={i}
              className="flex gap-3 items-start"
              style={{
                padding: "12px 14px",
                borderRadius: 10,
                background: "var(--paper-50)",
                border: "1px solid var(--paper-200)",
              }}
            >
              <span
                className="flex items-center justify-center shrink-0"
                style={{
                  width: 22,
                  height: 22,
                  borderRadius: "50%",
                  marginTop: 1,
                  background: ev.matched ? "var(--safe-100)" : config.chipBg,
                  color: ev.matched ? "var(--safe-600)" : config.chipColor,
                }}
              >
                {ev.matched ? <Check size={13} strokeWidth={3} /> : <X size={13} strokeWidth={3} />}
              </span>
              <div style={{ fontSize: 13.5 }}>
                <div className="font-medium" style={{ color: "var(--ink-950)" }}>
                  {ev.source}
                </div>
                <div style={{ color: "var(--ink-600)" }}>{ev.result}</div>
              </div>
            </div>
          ))}
        </div>

        {/* 계좌번호 사기 이력 공식 조회 안내 */}
        {accountNumber && (
          <div className="mt-4 pt-4" style={{ borderTop: "1px dashed var(--paper-200)" }}>
            <div className="flex items-center justify-between gap-2 flex-wrap">
              <p className="font-semibold" style={{ fontSize: 13, color: "var(--ink-800)" }}>
                계좌번호 사기 이력 공식 조회
              </p>
              <button
                type="button"
                onClick={copyAccount}
                className="inline-flex items-center gap-1"
                style={{
                  border: "1px solid var(--paper-200)",
                  borderRadius: 7,
                  background: "var(--paper-50)",
                  padding: "4px 9px",
                  fontSize: 12,
                  color: "var(--ink-600)",
                  cursor: "pointer",
                }}
              >
                {copied ? <Check size={12} strokeWidth={3} /> : <Copy size={12} strokeWidth={2} />}
                {copied ? "복사됨" : `${accountNumber} 복사`}
              </button>
            </div>
            <p className="mt-1" style={{ fontSize: 12, color: "var(--ink-500)" }}>
              FireShield 판정은 참고용입니다. 아래 공식 서비스에서 계좌번호를 직접 조회해 최종 확인하세요.
            </p>
            <div className="flex flex-col gap-2 mt-2.5">
              {OFFICIAL_ACCOUNT_LOOKUPS.map((lk) => (
                <a
                  key={lk.href}
                  href={lk.href}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-3"
                  style={{
                    padding: "10px 13px",
                    borderRadius: 10,
                    background: "var(--paper-50)",
                    border: "1px solid var(--paper-200)",
                    textDecoration: "none",
                  }}
                >
                  <ExternalLink size={15} strokeWidth={2} style={{ color: "var(--ink-400)", flexShrink: 0 }} />
                  <span style={{ fontSize: 13 }}>
                    <span className="font-medium block" style={{ color: "var(--ink-950)" }}>
                      {lk.label}
                    </span>
                    <span style={{ color: "var(--ink-500)", fontSize: 12 }}>{lk.desc}</span>
                  </span>
                </a>
              ))}
            </div>
          </div>
        )}

        {/* 권고사항 */}
        <div className="mt-4 pt-4" style={{ borderTop: "1px dashed var(--paper-200)" }}>
          <p className="font-semibold" style={{ color: config.chipColor, fontSize: 14 }}>
            {result.recommendation}
          </p>
          <p className="mt-2 text-center" style={{ fontSize: 11.5, color: "var(--ink-400)" }}>
            본 판정은 공공데이터 기반 참고용 결과입니다. 최종 확인은 관할 소방서(☎119) 또는 경찰(☎112)에 문의하세요.
          </p>
        </div>
      </div>
    </div>
  );
}