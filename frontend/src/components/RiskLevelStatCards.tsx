import { RISK_LEVEL_META, RISK_LEVELS } from "@/lib/riskLevel";
import { RiskLevelStats } from "@/types/admin";

export default function RiskLevelStatCards({
  total,
  stats,
  className = "",
}: {
  total: number;
  stats: RiskLevelStats;
  className?: string;
}) {
  return (
    <div className={`grid grid-cols-2 md:grid-cols-5 gap-4 ${className}`}>
      <StatCard label="전체 조회" value={total} color="var(--ink-950)" />
      {RISK_LEVELS.map((level) => (
        <StatCard
          key={level}
          label={RISK_LEVEL_META[level].label}
          value={stats[level]}
          color={RISK_LEVEL_META[level].color}
        />
      ))}
    </div>
  );
}

function StatCard({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div className="p-4 rounded-xl" style={{ background: "var(--white)", border: "1px solid var(--paper-200)" }}>
      <div className="text-xs mb-1" style={{ color: "var(--ink-600)" }}>
        {label}
      </div>
      <div className="text-2xl font-bold" style={{ color, fontFamily: "var(--font-head)" }}>
        {value.toLocaleString("ko-KR")}
      </div>
    </div>
  );
}
