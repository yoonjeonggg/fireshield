const STEPS = [
  {
    num: "1",
    title: "의심 정보 입력",
    desc: "상대방의 소속, 이름, 요구 내용, 계좌번호를 입력합니다. 계좌번호는 선택사항입니다.",
  },
  {
    num: "2",
    title: "공공데이터 실시간 대조",
    desc: "법제처 법령 변경이력, 소방청 소방시설업 현황 등 공공데이터와 실시간으로 대조하여 진위를 판별합니다.",
  },
  {
    num: "3",
    title: "결과 확인",
    desc: "안전 · 의심 · 위험 3단계 판정 결과와 함께, 판정에 사용된 근거 데이터를 확인할 수 있습니다.",
  },
];

export default function HowItWorks() {
  return (
    <section className="max-w-[1120px] mx-auto px-5 py-16">
      <div className="text-center max-w-[520px] mx-auto mb-10">
        <h2 className="text-2xl font-bold" style={{ fontFamily: "var(--font-head)" }}>
          이용 방법
        </h2>
        <p className="mt-2 text-sm" style={{ color: "var(--ink-600)" }}>
          간단한 3단계로 사기 여부를 확인할 수 있습니다
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
        {STEPS.map((step) => (
          <div key={step.num} className="text-center px-2">
            <div
              className="flex items-center justify-center mx-auto mb-4 font-bold text-base"
              style={{
                width: 40,
                height: 40,
                borderRadius: "50%",
                background: "var(--primary-500)",
                color: "#fff",
                fontFamily: "var(--font-head)",
              }}
            >
              {step.num}
            </div>
            <h3 className="text-[15.5px] font-bold mb-1.5" style={{ color: "var(--ink-950)" }}>
              {step.title}
            </h3>
            <p className="text-[13.5px]" style={{ color: "var(--ink-600)" }}>
              {step.desc}
            </p>
          </div>
        ))}
      </div>
    </section>
  );
}