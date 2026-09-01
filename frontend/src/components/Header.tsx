import { Siren } from "lucide-react";

export default function Header() {
  return (
    <header
      style={{
        position: "sticky",
        top: 0,
        zIndex: 50,
        background: "rgba(246,247,249,.92)",
        backdropFilter: "blur(8px)",
        borderBottom: "1px solid var(--paper-200)",
      }}
    >
      <div className="max-w-[1120px] mx-auto px-5 h-16 flex items-center justify-between">
        <a href="/" className="flex items-center gap-2.5">
          <span
            className="flex items-center justify-center shrink-0"
            style={{
              width: 38,
              height: 38,
              borderRadius: 10,
              background: "var(--primary-500)",
              boxShadow: "0 2px 6px rgba(29,78,137,.35)",
            }}
          >
            <Siren size={20} strokeWidth={2} color="#fff" />
          </span>
          <span className="flex flex-col leading-tight">
            <span
              className="font-bold text-[17px]"
              style={{ fontFamily: "var(--font-head)", color: "var(--primary-700)" }}
            >
              FireShield
            </span>
            <span className="text-[11px]" style={{ color: "var(--ink-600)" }}>
              소방사칭 진위확인
            </span>
          </span>
        </a>

        <nav className="flex items-center gap-7">
          <a href="/" className="text-sm font-medium" style={{ color: "var(--primary-500)" }}>
            진위확인
          </a>
          <a href="/risk-map" className="text-sm font-medium" style={{ color: "var(--primary-500)" }}>
  위험지역 지도
</a>
        </nav>
      </div>
    </header>
  );
}