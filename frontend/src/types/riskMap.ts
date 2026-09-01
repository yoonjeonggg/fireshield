export interface RiskZone {
  region_name: string;
  lat: number;
  lng: number;
  risk_score: number;
  report_count: number;
  main_targets: string;
}

export interface RiskMapResponse {
  total_count: number;
  zones: RiskZone[];
}

export interface SigunguDetail {
  sigungu_name: string;
  report_count: number;
  risk_score: number;
}

export interface SigunguDetailResponse {
  sido: string;
  lat: number;
  lng: number;
  items: SigunguDetail[];
}