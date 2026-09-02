export default function ReportCta() {
  return (
    <section className="max-w-[1120px] mx-auto px-5 pb-20">
      <div
        className="rounded-2xl flex items-center gap-6 flex-wrap justify-between"
        style={{ background: "var(--primary-900)", padding: "36px 30px" }}
      >
        <div>
          <h3
            className="text-white text-lg font-bold"
            style={{ fontFamily: "var(--font-head)" }}
          >
            사칭 피해를 경험하셨나요?
          </h3>
          <p className="mt-1.5 text-sm" style={{ color: "rgba(255,255,255,.6)" }}>
            피해 사실을 신고하시면 동일 수법의 추가 피해를 막을 수 있습니다.
          </p>
        </div>

        <div className="flex gap-2.5 flex-wrap">
          <a
            href="tel:112"
            className="flex items-center gap-2 font-bold text-sm rounded-lg"
            style={{ padding: "12px 20px", background: "var(--danger-500)", color: "#fff" }}
          >
            경찰 신고 (112)
          </a>
          <a
            href="tel:119"
            className="flex items-center gap-2 font-bold text-sm rounded-lg"
            style={{ padding: "12px 20px", background: "#fff", color: "var(--primary-700)" }}
          >
            소방서 문의 (119)
          </a>
        </div>
      </div>
    </section>
  );
}