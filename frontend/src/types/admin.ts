export interface VerifyLogSummary {
  id: string;
  claimed_org: string | null;
  claimed_person: string | null;
  claim_type: string | null;
  target_business: string | null;
  has_account_number: boolean;
  risk_level: string | null;
  score: number | null;
  created_at: string;
}

export interface RiskLevelStats {
  safe: number;
  caution: number;
  danger: number;
  unverified: number;
}

export interface AdminStatsResponse {
  total_count: number;
  risk_level_stats: RiskLevelStats;
  recent_logs: VerifyLogSummary[];
}