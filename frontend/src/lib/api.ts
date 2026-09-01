import { VerifyRequest, VerifyResponse } from "@/types/verify";
import { RiskMapResponse } from "@/types/riskMap";


const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL;

export async function verifyRequest(payload: VerifyRequest): Promise<VerifyResponse> {
  const res = await fetch(`${API_BASE_URL}/api/v1/verify`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    const errorBody = await res.json().catch(() => null);
    throw new Error(errorBody?.detail ?? "요청 처리 중 오류가 발생했습니다.");
  }

  return res.json();
}

export async function fetchRiskMap(): Promise<RiskMapResponse> {
  const res = await fetch(`${API_BASE_URL}/api/v1/risk-map`);

  if (!res.ok) {
    throw new Error("위험지역 데이터를 불러오지 못했습니다.");
  }

  return res.json();
}import { SigunguDetailResponse } from "@/types/riskMap";

export async function fetchSigunguDetail(sido: string): Promise<SigunguDetailResponse> {
  const res = await fetch(`${API_BASE_URL}/api/v1/risk-map/${encodeURIComponent(sido)}`);

  if (!res.ok) {
    throw new Error("시군구 상세 데이터를 불러오지 못했습니다.");
  }

  return res.json();
}

