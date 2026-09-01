export type ClaimType = "law_amendment" | "inspection" | "subsidy" | "custom";
export type RiskLevel = "safe" | "caution" | "danger";

export interface VerifyRequest {
  claimed_org: string;
  claimed_person: string;
  claim_type: string;
  target_business: string;
  account_number?: string;
  law_name?: string;
}

export interface Evidence {
  source: string;
  result: string;
  matched: boolean;
}

export interface VerifyResponse {
  risk_level: RiskLevel;
  score: number;
  evidence: Evidence[];
  recommendation: string;
}