import { AlertTriangle, MapPin, MessageSquareWarning, ShieldAlert } from "lucide-react";

const REAL_CASES = [
  {
    region: "경북",
    amount: "6억 3,000만 원",
    desc: "소방서를 사칭해 \"법령 개정으로 소화기 교체가 의무화됐다\"며 다중이용업소 사업주들에게 순차적으로 입금을 요구한 사례입니다.",
  },
  {
    region: "제주",
    amount: "8,070만 원",
    desc: "\"정부 보조금이 전액 환급된다\"는 명목으로 사업주를 안심시킨 뒤, 처리 비용 명목의 선입금을 유도한 사례입니다.",
  },
];

const TYPICAL_PHRASES = [
  "법령 개정으로 소화기를 전량 교체해야 합니다",
  "정부 보조금이 전액 환급되니 계좌 정보를 알려주세요",
  "오늘 안에 입금하지 않으면 과태료가 부과됩니다",
  "소방시설 점검비 미납분이 있어 연락드렸습니다",
];

const RED_FLAGS = [
  "계좌번호를 알려주며 즉시 입금을 요구한다",
  "법령명이나 근거를 물으면 얼버무리거나 화를 낸다",
  "발신 번호가 소방서 대표번호가 아닌 개인 휴대폰이다",
  "\"오늘 안에\", \"지금 당장\" 같은 말로 시간을 압박한다",
  "담당자명·소속 확인을 요청하면 전화를 끊거나 회피한다",
];

export default function ScamGuide() {
  return (
    <div className="max-w-[1120px] mx-auto px-5 py-16">
      <div className="mb-12">
        <div
          className="inline-flex items-center gap-1.5 text-xs font-semibold rounded-full mb-4"
          style={{ padding: "6px 12px", background: "var(--danger-100)", color: "var(--danger-600)" }}
        >
          <AlertTriangle size={13} strokeWidth={2.5} />
          소방기관 사칭 사기 주의보
        </div>
        <h1 className="text-2xl font-bold mb-3" style={{ fontFamily: "var(--font-head)", color: "var(--ink-950)" }}>
          이런 연락, 사기일 수 있습니다
        </h1>
        <p className="text-sm max-w-[640px]" style={{ color: "var(--ink-600)" }}>
          소방서·소방공무원을 사칭해 소화기 교체, 보조금 환급 등을 명목으로 금전을 요구하는 사기가
          전국에서 발생하고 있습니다. 실제 피해 사례와 자주 쓰이는 수법을 미리 알아두면 골든타임 안에
          판단하는 데 도움이 됩니다.
        </p>
      </div>

      {/* 실제 피해 사례 */}
      <section className="mb-12">
        <h2 className="text-lg font-bold mb-4 flex items-center gap-2" style={{ color: "var(--ink-950)" }}>
          <MapPin size={18} style={{ color: "var(--danger-500)" }} />
          실제 피해 사례
        </h2>
        <div className="grid md:grid-cols-2 gap-4">
          {REAL_CASES.map((c) => (
            <div
              key={c.region}
              className="p-5 rounded-xl"
              style={{ background: "var(--white)", border: "1px solid var(--paper-200)" }}
            >
              <div className="flex items-center gap-2 mb-2">
                <span
                  className="text-xs font-semibold px-2 py-0.5 rounded-full"
                  style={{ background: "var(--paper-100)", color: "var(--ink-600)" }}
                >
                  {c.region}
                </span>
                <span className="text-lg font-bold" style={{ color: "var(--danger-600)", fontFamily: "var(--font-head)" }}>
                  {c.amount}
                </span>
                <span className="text-xs" style={{ color: "var(--ink-400)" }}>
                  피해
                </span>
              </div>
              <p className="text-sm leading-relaxed" style={{ color: "var(--ink-800)" }}>
                {c.desc}
              </p>
            </div>
          ))}
        </div>
      </section>

      <div className="grid md:grid-cols-2 gap-8 mb-12">
        {/* 전형적인 사기 멘트 */}
        <section>
          <h2 className="text-lg font-bold mb-4 flex items-center gap-2" style={{ color: "var(--ink-950)" }}>
            <MessageSquareWarning size={18} style={{ color: "var(--caution-600)" }} />
            자주 쓰이는 사기 멘트
          </h2>
          <div
            className="rounded-xl overflow-hidden"
            style={{ background: "var(--white)", border: "1px solid var(--paper-200)" }}
          >
            {TYPICAL_PHRASES.map((phrase, i) => (
              <div
                key={phrase}
                className="px-5 py-3.5 text-sm"
                style={{
                  color: "var(--ink-800)",
                  borderTop: i === 0 ? "none" : "1px solid var(--paper-100)",
                }}
              >
                &ldquo;{phrase}&rdquo;
              </div>
            ))}
          </div>
        </section>

        {/* 의심 신호 체크리스트 */}
        <section>
          <h2 className="text-lg font-bold mb-4 flex items-center gap-2" style={{ color: "var(--ink-950)" }}>
            <ShieldAlert size={18} style={{ color: "var(--primary-500)" }} />
            의심 신호 체크리스트
          </h2>
          <div
            className="rounded-xl p-5 flex flex-col gap-3"
            style={{ background: "var(--white)", border: "1px solid var(--paper-200)" }}
          >
            {RED_FLAGS.map((flag) => (
              <div key={flag} className="flex items-start gap-2.5 text-sm" style={{ color: "var(--ink-800)" }}>
                <span
                  className="shrink-0 mt-0.5 flex items-center justify-center rounded-full font-bold"
                  style={{
                    width: 18,
                    height: 18,
                    fontSize: 11,
                    background: "var(--danger-100)",
                    color: "var(--danger-600)",
                  }}
                >
                  !
                </span>
                {flag}
              </div>
            ))}
          </div>
        </section>
      </div>

      {/* CTA */}
      <div
        className="rounded-2xl flex items-center gap-6 flex-wrap justify-between"
        style={{ background: "var(--primary-900)", padding: "32px 30px" }}
      >
        <div>
          <h3 className="text-white text-lg font-bold" style={{ fontFamily: "var(--font-head)" }}>
            지금 받은 연락, 해당되는 게 있나요?
          </h3>
          <p className="mt-1.5 text-sm" style={{ color: "rgba(255,255,255,.6)" }}>
            송금 전에 FireShield로 발신 기관·계좌번호를 바로 대조해보세요.
          </p>
        </div>
        <a
          href="/#verify"
          className="font-bold text-sm rounded-lg shrink-0"
          style={{ padding: "12px 22px", background: "var(--danger-500)", color: "#fff" }}
        >
          지금 진위확인하기
        </a>
      </div>
    </div>
  );
}
