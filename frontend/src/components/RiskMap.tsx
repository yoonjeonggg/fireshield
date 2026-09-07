"use client";

import { useEffect, useRef, useState } from "react";
import { fetchRiskMap, fetchSigunguDetail } from "@/lib/api";
import { RiskZone, SigunguDetail } from "@/types/riskMap";

const GOOGLE_MAPS_API_KEY = process.env.NEXT_PUBLIC_GOOGLE_MAPS_API_KEY ?? "";

function riskColor(score: number): string {
  if (score >= 60) return "#d6362c";
  if (score >= 30) return "#d9a520";
  return "#2ea866";
}

declare global {
  interface Window {
    google: any;
    initFireShieldMap: () => void;
  }
}

export default function RiskMap({ compact = false }: { compact?: boolean }) {
  const mapRef = useRef<HTMLDivElement>(null);
  const mapInstanceRef = useRef<any>(null);
  const infoWindowRef = useRef<any>(null);
  const markersRef = useRef<Record<string, any>>({});
  const boundsRef = useRef<any>(null);

  const [zones, setZones] = useState<RiskZone[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedRegion, setSelectedRegion] = useState<string | null>(null);

  const [drilldownSido, setDrilldownSido] = useState<string | null>(null);
  const [sigunguItems, setSigunguItems] = useState<SigunguDetail[]>([]);
  const [drilldownLoading, setDrilldownLoading] = useState(false);

  useEffect(() => {
    fetchRiskMap()
      .then((data) => {
        setZones(data.zones);
        setTotalCount(data.total_count);
      })
      .catch((err) => setError(err instanceof Error ? err.message : "오류가 발생했습니다."))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (zones.length === 0) return;
    if (!GOOGLE_MAPS_API_KEY) return;

    function initMap() {
      if (!mapRef.current) return;

      const darkStyle = [
        { elementType: "geometry", stylers: [{ color: "#1d3a5f" }] },
        { elementType: "labels.text.fill", stylers: [{ color: "#d6e2f0" }] },
        { elementType: "labels.text.stroke", stylers: [{ color: "#0e2a47" }] },
        { featureType: "water", elementType: "geometry", stylers: [{ color: "#0a1f38" }] },
        { featureType: "road", elementType: "geometry", stylers: [{ color: "#3a5b85" }] },
        { featureType: "road", elementType: "geometry.stroke", stylers: [{ color: "#2a4a70" }] },
        { featureType: "administrative.province", elementType: "geometry.stroke", stylers: [{ color: "#7ea3cc", weight: 1.2 }] },
        { featureType: "administrative.country", elementType: "geometry.stroke", stylers: [{ color: "#9fbde0", weight: 1.5 }] },
        { featureType: "landscape", elementType: "geometry", stylers: [{ color: "#24466e" }] },
        { featureType: "poi", stylers: [{ visibility: "off" }] },
      ];

      const map = new window.google.maps.Map(mapRef.current, {
        center: { lat: 36.2, lng: 127.9 },
        zoom: 7,
        styles: darkStyle,
        disableDefaultUI: true,
        zoomControl: true,
      });
      mapInstanceRef.current = map;
      infoWindowRef.current = new window.google.maps.InfoWindow();

      const bounds = new window.google.maps.LatLngBounds();
      const maxCount = Math.max(...zones.map((z) => z.report_count), 1);

      zones.forEach((zone) => {
        const marker = new window.google.maps.Marker({
          position: { lat: zone.lat, lng: zone.lng },
          map,
          title: zone.region_name,
          icon: {
            path: window.google.maps.SymbolPath.CIRCLE,
            scale: 8 + (zone.report_count / maxCount) * 18,
            fillColor: riskColor(zone.risk_score),
            fillOpacity: 0.9,
            strokeColor: "#fff",
            strokeWeight: 1.5,
          },
          label: {
            text: String(zone.report_count),
            color: zone.risk_score >= 30 && zone.risk_score < 60 ? "#3a2c04" : "#fff",
            fontSize: "11px",
            fontWeight: "700",
          },
        });

        marker.addListener("click", () => {
          handleSelectSido(zone);
        });

        markersRef.current[zone.region_name] = marker;
        bounds.extend(marker.getPosition());
      });

      boundsRef.current = bounds;
      map.fitBounds(bounds);
      window.google.maps.event.addListenerOnce(map, "bounds_changed", () => {
        if (map.getZoom() > 9) map.setZoom(9);
      });
    }

    if (window.google?.maps) {
      initMap();
      return;
    }

    const existingScript = document.querySelector<HTMLScriptElement>(
      'script[data-fireshield-gmaps="true"]'
    );
    if (existingScript) {
      window.initFireShieldMap = initMap;
      return;
    }

    window.initFireShieldMap = initMap;
    const script = document.createElement("script");
    script.src = `https://maps.googleapis.com/maps/api/js?key=${GOOGLE_MAPS_API_KEY}&loading=async&callback=initFireShieldMap`;
    script.async = true;
    script.setAttribute("data-fireshield-gmaps", "true");
    script.onerror = () => setError("구글 지도를 불러오지 못했습니다.");
    document.head.appendChild(script);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [zones]);

  async function handleSelectSido(zone: RiskZone) {
    setSelectedRegion(zone.region_name);

    const map = mapInstanceRef.current;
    const marker = markersRef.current[zone.region_name];
    if (map && marker) {
      map.panTo({ lat: zone.lat, lng: zone.lng });
      map.setZoom(10);
      infoWindowRef.current.setContent(
        `<div style="font-family:sans-serif;font-size:13px;line-height:1.6;color:#141a24;">
           <b>${zone.region_name}</b><br>최근 3개월 신고 <b>${zone.report_count}건</b><br>${zone.main_targets}
         </div>`
      );
      infoWindowRef.current.open(map, marker);
    }

    setDrilldownSido(zone.region_name);
    setDrilldownLoading(true);
    try {
      const detail = await fetchSigunguDetail(zone.region_name);
      setSigunguItems(detail.items);
    } catch (err) {
      setError(err instanceof Error ? err.message : "시군구 데이터를 불러오지 못했습니다.");
    } finally {
      setDrilldownLoading(false);
    }
  }

  function handleResetView() {
    setSelectedRegion(null);
    setDrilldownSido(null);
    setSigunguItems([]);

    const map = mapInstanceRef.current;
    if (!map || !boundsRef.current) return;

    infoWindowRef.current?.close();
    map.fitBounds(boundsRef.current);
    window.google.maps.event.addListenerOnce(map, "bounds_changed", () => {
      if (map.getZoom() > 9) map.setZoom(9);
    });
  }

  if (loading) {
    return (
      <div className="max-w-[1120px] mx-auto px-5 py-16 text-center" style={{ color: "var(--ink-600)" }}>
        위험지역 데이터를 불러오는 중...
      </div>
    );
  }

  if (error) {
    return (
      <div className="max-w-[1120px] mx-auto px-5 py-16 text-center" style={{ color: "var(--danger-600)" }}>
        {error}
      </div>
    );
  }

  return (
    <section className="max-w-[1120px] mx-auto px-5 py-16">
      <div className="text-center max-w-[520px] mx-auto mb-8">
        <h2 className="text-2xl font-bold" style={{ fontFamily: "var(--font-head)" }}>
          화재 위험 지역
        </h2>
        <p className="mt-2 text-sm" style={{ color: "var(--ink-600)" }}>
          최근 3개월간 전국 화재 발생 현황입니다. 현재까지 총{" "}
          <b style={{ color: "var(--ink-950)" }}>{totalCount}</b>건이 확인되었습니다.
        </p>
        <p className="mt-1 text-xs" style={{ color: "var(--ink-400)" }}>
          출처: 소방청 전국 화재 현황(2025) · 시도 단위 집계, 좌표는 시/도청 소재지 기준
        </p>
        {compact && (
          <a 
            href="/risk-map"
            className="inline-block mt-3 text-sm font-semibold"
            style={{ color: "var(--primary-500)" }}
          >
            전체 지도 자세히 보기 →
          </a>
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[1fr_300px] gap-6 items-start">
        {/* 지도 */}
        <div
          className="relative overflow-hidden flex flex-col"
          style={{
            background: "linear-gradient(160deg, var(--primary-900), var(--primary-700))",
            borderRadius: 16,
            padding: 20,
            color: "#fff",
            minHeight: 700,
          }}
        >
          <div
            className="absolute top-[18px] left-[18px] z-10"
            style={{
              background: "rgba(255,255,255,.1)",
              backdropFilter: "blur(4px)",
              border: "1px solid rgba(255,255,255,.16)",
              borderRadius: 12,
              padding: "10px 14px",
            }}
          >
            <div className="text-[10.5px] font-semibold opacity-70 uppercase" style={{ letterSpacing: "0.03em" }}>
              누적 신고 건수
            </div>
            <div className="font-bold text-2xl" style={{ fontFamily: "var(--font-head)" }}>
              {totalCount}
              <span className="text-xs font-normal opacity-70 ml-1">건 / 최근 3개월</span>
            </div>
          </div>

          {selectedRegion && (
            <button
              onClick={handleResetView}
              className="absolute z-10 text-xs font-semibold"
              style={{
                top: 18,
                right: 18,
                background: "rgba(255,255,255,.15)",
                backdropFilter: "blur(4px)",
                border: "1px solid rgba(255,255,255,.25)",
                borderRadius: 8,
                padding: "8px 12px",
                color: "#fff",
                cursor: "pointer",
              }}
            >
              ↺ 전체보기
            </button>
          )}

          {GOOGLE_MAPS_API_KEY ? (
            <div
              ref={mapRef}
              className="flex-1 w-full rounded-xl overflow-hidden"
              style={{ minHeight: 460, background: "rgba(255,255,255,.05)" }}
            />
          ) : (
            <div
              className="flex-1 flex flex-col items-center justify-center text-center gap-1.5"
              style={{ minHeight: 460, color: "rgba(255,255,255,.6)", fontSize: 13 }}
            >
              구글 지도 API 키가 설정되지 않았습니다.
            </div>
          )}

          <div className="flex gap-4 mt-2.5 text-[11.5px] opacity-80 relative z-10">
            <span className="flex items-center gap-1.5">
              <i className="inline-block w-2 h-2 rounded-full" style={{ background: "#d6362c" }} />
              고위험 (60점↑)
            </span>
            <span className="flex items-center gap-1.5">
              <i className="inline-block w-2 h-2 rounded-full" style={{ background: "#d9a520" }} />
              주의 (30~59점)
            </span>
            <span className="flex items-center gap-1.5">
              <i className="inline-block w-2 h-2 rounded-full" style={{ background: "#2ea866" }} />
              관찰 (30점 미만)
            </span>
          </div>
        </div>

        {/* 오른쪽 패널: 시도 리스트 또는 시군구 드릴다운 */}
        <div className="flex flex-col gap-2.5">
          {drilldownSido ? (
            <>
              <div className="flex items-center justify-between mb-1">
                <span className="text-sm font-bold" style={{ color: "var(--ink-950)" }}>
                  {drilldownSido} 시군구별 현황
                </span>
                <button
                  onClick={handleResetView}
                  className="text-xs font-medium"
                  style={{ color: "var(--primary-500)" }}
                >
                  ← 전체보기
                </button>
              </div>

              {drilldownLoading ? (
                <div className="text-sm py-6 text-center" style={{ color: "var(--ink-400)" }}>
                  불러오는 중...
                </div>
              ) : (
                sigunguItems.map((item) => (
                  <div
                    key={item.sigungu_name}
                    className="flex items-center gap-3"
                    style={{
                      padding: "12px 14px",
                      background: "var(--white)",
                      border: "1px solid var(--paper-200)",
                      borderRadius: 10,
                    }}
                  >
                    <span
                      className="flex items-center justify-center shrink-0 text-white text-xs font-bold"
                      style={{ width: 26, height: 26, borderRadius: 8, background: riskColor(item.risk_score) }}
                    >
                      {item.report_count}
                    </span>
                    <span className="text-sm font-medium" style={{ color: "var(--ink-950)" }}>
                      {item.sigungu_name}
                    </span>
                  </div>
                ))
              )}
            </>
         ) : (
  <div
    className="flex flex-col"
    style={{
      maxHeight: 700,
      overflowY: "auto",
      background: "var(--white)",
      border: "1px solid var(--paper-200)",
      borderRadius: 12,
    }}
  >
    {zones.map((zone, index) => {
      const isSelected = selectedRegion === zone.region_name;
      const maxCount = zones[0]?.report_count || 1;
      const barPct = Math.max(6, (zone.report_count / maxCount) * 100);
      const rank = index + 1;

      return (
        <button
          key={zone.region_name}
          onClick={() => handleSelectSido(zone)}
          className="flex items-center gap-3 text-left w-full transition-colors"
          style={{
            padding: "10px 14px",
            background: isSelected ? "var(--primary-100)" : "transparent",
            borderBottom: index < zones.length - 1 ? "1px solid var(--paper-100)" : "none",
            cursor: "pointer",
          }}
        >
          <span
            className="shrink-0 text-xs font-bold text-center"
            style={{
              width: 20,
              color: rank <= 3 ? "var(--primary-700)" : "var(--ink-400)",
            }}
          >
            {rank}
          </span>

          <div className="flex-1 min-w-0">
            <div className="flex items-baseline justify-between gap-2 mb-1">
              <span
                className="text-[13px] font-semibold truncate"
                style={{ color: "var(--ink-950)" }}
              >
                {zone.region_name}
              </span>
              <span
                className="text-xs font-bold shrink-0"
                style={{ color: riskColor(zone.risk_score) }}
              >
                {zone.report_count}건
              </span>
            </div>
            <div
              style={{
                height: 5,
                borderRadius: 999,
                background: "var(--paper-100)",
                overflow: "hidden",
              }}
            >
              <div
                style={{
                  height: "100%",
                  width: `${barPct}%`,
                  background: riskColor(zone.risk_score),
                  borderRadius: 999,
                }}
              />
            </div>
          </div>
        </button>
      );
    })}
  </div>
)}
        </div>
      </div>
    </section>
  );
}