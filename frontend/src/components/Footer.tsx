const DATA_SOURCES = [
  { name: "법제처 국가법령정보 공동활용 API", url: "https://open.law.go.kr" },
  { name: "소방청 소방시설업 현황", url: "https://www.data.go.kr" },
  { name: "소방청 전국 화재 현황", url: "https://www.bigdata-119.kr" },
  { name: "전국 다중이용업소 현황", url: "https://www.bigdata-119.kr" },
];

export default function Footer() {
  return (
    <footer style={{ background: "var(--primary-900)", padding: "34px 0" }}>
      <div className="max-w-[1120px] mx-auto px-5">
        <div className="flex justify-between items-center flex-wrap gap-3.5">
          <div className="flex items-center gap-2 text-white text-[13px]">
            <b style={{ fontFamily: "var(--font-head)" }}>FireShield</b>
            <span>· 소방기관 사칭 사기 실시간 진위확인 시스템</span>
          </div>
          <div className="flex gap-5 text-xs" style={{ color: "rgba(255,255,255,.55)" }}>
            <span>© 2026 FireShield</span>
          </div>
        </div>

        {/* 데이터 출처 */}
        <div
          className="mt-5 pt-5"
          style={{ borderTop: "1px solid rgba(255,255,255,.1)" }}
        >
          <div
            className="text-[10.5px] font-semibold uppercase mb-2.5"
            style={{ color: "rgba(255,255,255,.4)", letterSpacing: "0.04em" }}
          >
            데이터 출처
          </div>
          <div className="flex flex-wrap gap-x-5 gap-y-1.5">
            {DATA_SOURCES.map((source) => (
              <a
                key={source.name}
                href={source.url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-[11.5px]"
                style={{ color: "rgba(255,255,255,.5)" }}
              >
                {source.name}
              </a>
            ))}
          </div>
        </div>

        <p
          className="mt-4 pt-4 text-[11.5px] leading-relaxed max-w-[640px]"
          style={{ borderTop: "1px solid rgba(255,255,255,.1)", color: "rgba(255,255,255,.4)" }}
        >
          본 서비스는 위 공공데이터를 기반으로 하며, 판정 결과는 참고용입니다.
          최종 확인은 관할 소방서(☎ 119) 또는 경찰(☎ 112)에 직접 문의하시기 바랍니다.
        </p>
      </div>
    </footer>
  );
}