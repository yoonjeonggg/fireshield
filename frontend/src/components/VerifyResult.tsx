import { ShieldCheck, AlertTriangle, ShieldAlert, HelpCircle, Check, X, Sparkles } from "lucide-react";
import { VerifyResponse, RiskLevel, AiAssessment } from "@/types/verify";

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
  unverified: {
    label: "판정 결과 · 확인 불가",
    verdict: "판정 불가 — 직접 확인 필요",
    headBg: "linear-gradient(120deg, var(--primary-700), var(--primary-500))",
    headColor: "#fff",
    barColor: "var(--primary-300)",
    chipBg: "var(--primary-100)",
    chipColor: "var(--primary-700)",
    Icon: HelpCircle,
  },
};

function aiBandColor(ai: AiAssessment): { fg: string; bg: string } {
  if (ai.score === null || ai.score === undefined) {
    return { fg: "var(--ink-400)", bg: "var(--paper-100)" };
  }
  if (ai.score >= 60) return { fg: "var(--danger-600)", bg: "var(--danger-100)" };
  if (ai.score >= 30) return { fg: "var(--caution-600)", bg: "var(--caution-100)" };
  return { fg: "var(--safe-600)", bg: "var(--safe-100)" };
}

function AiPanel({ ai }: { ai: AiAssessment }) {
  const hasScore = ai.score !== null && ai.score !== undefined;
  const band = aiBandColor(ai);

  return (
    <div
      style={{
        padding: "13px 15px",
        borderRadius: 10,
        background: "var(--paper-50)",
        border: "1px solid var(--paper-200)",
      }}
    >
      <div className="flex items-center gap-2" style={{ marginBottom: 8 }}>
        <Sparkles size={14} strokeWidth={2} color="var(--primary-500)" />
        <span className="font-semibold" style={{ fontSize: 13, color: "var(--ink-950)" }}>
          AI 사기 위험 분석
        </span>
        <span
          className="font-semibold"
          style={{
            fontSize: 11,
            padding: "2px 8px",
            borderRadius: 999,
            color: band.fg,
            background: band.bg,
          }}
        >
          {ai.label}
        </span>
        {hasScore && (
          <span
            className="ml-auto font-bold tabular-nums"
            style={{ fontSize: 16, color: "var(--ink-950)" }}
          >
            {ai.score}
            <span style={{ fontSize: 11, color: "var(--ink-400)", fontWeight: 400 }}> / 100</span>
          </span>
        )}
      </div>
      <div style={{ fontSize: 12.5, lineHeight: 1.55, color: "var(--ink-600)" }}>{ai.detail}</div>
      <div style={{ fontSize: 11, color: "var(--ink-400)", marginTop: 6 }}>
        {ai.used_in_verdict
          ? "공공데이터 대조 결과와 함께 최종 판정에 반영되었습니다."
          : "이번 분석은 참고용이며, 최종 판정은 공공데이터 대조 결과를 기준으로 합니다."}
      </div>
    </div>
  );
}

export default function VerifyResult({ result }: { result: VerifyResponse }) {
  const config = RISK_CONFIG[result.risk_level];
  const Icon = config.Icon;
  const unverified = result.risk_level === "unverified";

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
        <span className="ml-auto text-2xl font-bold opacity-90">
          {unverified ? "—" : result.score}
        </span>
      </div>

      {/* 본문 */}
      <div style={{ padding: "22px 26px 26px" }}>
        {/* 점수 바 — 확인 불가일 때는 위험도를 표현하지 않는다 */}
        {unverified ? (
          <div
            style={{
              padding: "10px 14px",
              borderRadius: 10,
              background: "var(--primary-100)",
              color: "var(--primary-700)",
              fontSize: 12.5,
              marginBottom: 18,
            }}
          >
            입력한 정보가 공공데이터와 대조되지 않아 위험도 점수를 산출하지 않았습니다.
          </div>
        ) : (
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
        )}

        {/* 규칙 점수 vs AI 점수 — 따로 표시 */}
        <div className="flex flex-col gap-2.5" style={{ marginBottom: 14 }}>
          <div
            className="flex items-center gap-2"
            style={{
              padding: "12px 14px",
              borderRadius: 10,
              background: "var(--paper-50)",
              border: "1px solid var(--paper-200)",
            }}
          >
            <ShieldCheck size={14} strokeWidth={2} color="var(--ink-600)" />
            <span className="font-medium" style={{ fontSize: 13, color: "var(--ink-950)" }}>
              공공데이터 규칙 점수
            </span>
            <span className="ml-auto font-bold" style={{ fontSize: 16, color: "var(--ink-950)" }}>
              {result.rule_score}
              <span style={{ fontSize: 11, color: "var(--ink-400)" }}> /100</span>
            </span>
          </div>
          {result.ai_assessment && <AiPanel ai={result.ai_assessment} />}
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