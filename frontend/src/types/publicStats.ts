import { RiskLevelStats } from "@/types/admin";

export interface DailyTrendPoint {
  date: string;
  total: number;
  safe: number;
  caution: number;
  danger: number;
  unverified: number;
}

export interface TopClaimedOrg {
  org: string;
  count: number;
}

export interface RecentAlert {
  claimed_org: string | null;
  claim_type: string | null;
  risk_level: string | null;
  created_at: string;
}

export interface PublicStatsResponse {
  total_count: number;
  risk_level_stats: RiskLevelStats;
  daily_trend: DailyTrendPoint[];
  top_claimed_orgs: TopClaimedOrg[];
  recent_alerts: RecentAlert[];
}
