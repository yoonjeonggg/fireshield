import { RiskLevelStats } from "@/types/admin";

export type RiskLevel = keyof RiskLevelStats;

export const RISK_LEVEL_META: Record<RiskLevel, { label: string; color: string }> = {
  safe: { label: "안전", color: "var(--safe-600)" },
  caution: { label: "의심", color: "var(--caution-600)" },
  danger: { label: "위험", color: "var(--danger-600)" },
  unverified: { label: "확인 불가", color: "var(--primary-700)" },
};

export const RISK_LEVELS = Object.keys(RISK_LEVEL_META) as RiskLevel[];
