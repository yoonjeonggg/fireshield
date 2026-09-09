export type ClaimType = "law_amendment" | "inspection" | "subsidy" | "custom";
export type RiskLevel = "safe" | "caution" | "danger" | "unverified";

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

export type AiStatus =
  | "ok"
  | "clamped"
  | "low_confidence"
  | "discarded_invalid"
  | "discarded_conflict"
  | "unavailable";

export interface AiAssessment {
  score: number | null;
  status: AiStatus;
  label: string;
  detail: string;
  used_in_verdict: boolean;
}

export interface VerifyResponse {
  risk_level: RiskLevel;
  score: number; // 최종(보수적) 점수
  rule_score: number; // 공공데이터 규칙 기반 점수
  ai_assessment?: AiAssessment | null;
  evidence: Evidence[];
  recommendation: string;
}