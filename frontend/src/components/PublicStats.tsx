"use client";

import { useEffect, useState } from "react";
import { fetchPublicStats } from "@/lib/api";
import { PublicStatsResponse } from "@/types/publicStats";

function formatDay(dateStr: string) {
  const [, m, d] = dateStr.split("-");
  return `${Number(m)}/${Number(d)}`;
}

export default function PublicStats() {
  const [stats, setStats] = useState<PublicStatsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedDay, setSelectedDay] = useState<number | null>(null);

  useEffect(() => {
    fetchPublicStats()
      .then(setStats)
      .catch((err) => setError(err instanceof Error ? err.message : "오류가 발생했습니다."))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="max-w-[1120px] mx-auto px-5 py-16">
      <div className="mb-10">
        <h1 className="text-2xl font-bold mb-2" style={{ fontFamily: "var(--font-head)", color: "var(--ink-950)" }}>
          실시간 진위확인 통계
        </h1>
        <p className="text-sm" style={{ color: "var(--ink-600)" }}>
          지금까지 FireShield로 접수된 진위확인 요청을 집계한 공개 통계입니다. 계좌번호·담당자명·대상
          업체명 등 개인정보는 표시되지 않습니다.
        </p>
      </div>

      {loading && (
        <p className="text-sm" style={{ color: "var(--ink-600)" }}>
          불러오는 중...
        </p>
      )}

      {error && (
        <div className="p-3 rounded-lg text-sm" style={{ background: "var(--danger-100)", color: "var(--danger-600)" }}>
          {error}
        </div>
      )}

      {stats && (
        <>
          {/* 통계 카드 */}
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-12">
            <StatCard label="전체 조회" value={stats.total_count} color="var(--ink-950)" />
            <StatCard label="안전" value={stats.risk_level_stats.safe} color="var(--safe-600)" />
            <StatCard label="의심" value={stats.risk_level_stats.caution} color="var(--caution-600)" />
            <StatCard label="위험" value={stats.risk_level_stats.danger} color="var(--danger-600)" />
            <StatCard label="확인 불가" value={stats.risk_level_stats.unverified} color="var(--primary-700)" />
          </div>

          {/* 최근 14일 추이 */}
          <section className="mb-12">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-bold" style={{ color: "var(--ink-950)" }}>
                최근 14일 조회 추이
              </h2>
              <Legend
                items={[
                  { label: "전체 조회", color: "var(--primary-300)" },
                  { label: "위험 판정", color: "var(--danger-500)" },
                ]}
              />
            </div>
            <div
              className="p-5 rounded-xl"
              style={{ background: "var(--white)", border: "1px solid var(--paper-200)" }}
            >
              <TrendChart
                data={stats.daily_trend}
                selectedDay={selectedDay}
                onSelect={setSelectedDay}
              />
            </div>
          </section>

          <div className="grid md:grid-cols-2 gap-8">
            {/* 많이 사칭된 기관 */}
            <section>
              <h2 className="text-lg font-bold mb-4" style={{ color: "var(--ink-950)" }}>
                의심·위험 판정에 가장 많이 등장한 발신 기관
              </h2>
              <div
                className="p-5 rounded-xl flex flex-col gap-3"
                style={{ background: "var(--white)", border: "1px solid var(--paper-200)" }}
              >
                {stats.top_claimed_orgs.length === 0 && (
                  <p className="text-sm" style={{ color: "var(--ink-600)" }}>
                    아직 데이터가 없습니다.
                  </p>
                )}
                {stats.top_claimed_orgs.map((org) => (
                  <TopOrgBar
                    key={org.org}
                    org={org.org}
                    count={org.count}
                    max={stats.top_claimed_orgs[0]?.count ?? org.count}
                  />
                ))}
              </div>
            </section>

            {/* 최근 위험 판정 */}
            <section>
              <h2 className="text-lg font-bold mb-4" style={{ color: "var(--ink-950)" }}>
                최근 위험 판정 신고
              </h2>
              <div
                className="rounded-xl overflow-hidden"
                style={{ background: "var(--white)", border: "1px solid var(--paper-200)" }}
              >
                {stats.recent_alerts.length === 0 && (
                  <p className="text-sm p-5" style={{ color: "var(--ink-600)" }}>
                    최근 위험 판정 사례가 없습니다.
                  </p>
                )}
                {stats.recent_alerts.map((alert, i) => (
                  <div
                    key={i}
                    className="px-5 py-3 flex items-center justify-between gap-3"
                    style={{ borderTop: i === 0 ? "none" : "1px solid var(--paper-100)" }}
                  >
                    <div className="min-w-0">
                      <div className="text-sm font-semibold truncate" style={{ color: "var(--ink-950)" }}>
                        {alert.claimed_org ?? "발신 기관 미기재"}
                      </div>
                      <div className="text-xs truncate" style={{ color: "var(--ink-600)" }}>
                        {alert.claim_type ?? "요구 사유 미기재"}
                      </div>
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                      <span
                        className="text-xs font-semibold px-2 py-0.5 rounded-full"
                        style={{ background: "var(--danger-100)", color: "var(--danger-600)" }}
                      >
                        위험
                      </span>
                      <span className="text-xs" style={{ color: "var(--ink-400)" }}>
                        {new Date(alert.created_at).toLocaleDateString("ko-KR", { month: "numeric", day: "numeric" })}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </section>
          </div>
        </>
      )}
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

function Legend({ items }: { items: { label: string; color: string }[] }) {
  return (
    <div className="flex items-center gap-4">
      {items.map((item) => (
        <div key={item.label} className="flex items-center gap-1.5 text-xs" style={{ color: "var(--ink-600)" }}>
          <span
            className="inline-block rounded-sm"
            style={{ width: 10, height: 10, background: item.color }}
          />
          {item.label}
        </div>
      ))}
    </div>
  );
}

function TrendChart({
  data,
  selectedDay,
  onSelect,
}: {
  data: PublicStatsResponse["daily_trend"];
  selectedDay: number | null;
  onSelect: (i: number | null) => void;
}) {
  const max = Math.max(1, ...data.map((d) => d.total));
  const chartHeight = 140;
  const selected = selectedDay !== null ? data[selectedDay] : null;

  return (
    <div>
      {/* 선택한 날짜의 위험도별 breakdown — 항상 자리를 차지해서 클릭할 때 레이아웃이 흔들리지 않게 함 */}
      <div
        className="mb-4 p-3 rounded-lg flex flex-wrap items-center gap-x-5 gap-y-1 text-sm"
        style={{ background: "var(--paper-50)", visibility: selected ? "visible" : "hidden" }}
      >
        {selected ? (
          <>
            <span className="font-semibold" style={{ color: "var(--ink-950)" }}>
              {formatDay(selected.date)}
            </span>
            <BreakdownItem label="전체" value={selected.total} color="var(--ink-950)" />
            <BreakdownItem label="안전" value={selected.safe} color="var(--safe-600)" />
            <BreakdownItem label="의심" value={selected.caution} color="var(--caution-600)" />
            <BreakdownItem label="위험" value={selected.danger} color="var(--danger-600)" />
            <BreakdownItem label="확인 불가" value={selected.unverified} color="var(--primary-700)" />
          </>
        ) : (
          <span>-</span>
        )}
      </div>

      {/* 막대 영역 — 높이를 여기서만 고정해서 라벨 등 다른 요소가 이 높이를 넘어 삐져나오지 않게 함 */}
      <div className="flex items-end gap-1.5" style={{ height: chartHeight }}>
        {data.map((point, i) => {
          const totalH = (point.total / max) * chartHeight;
          const hasBothSegments = point.danger > 0 && point.danger < point.total;
          const gap = hasBothSegments ? 2 : 0;
          const dangerH = point.total > 0 ? (point.danger / point.total) * (totalH - gap) : 0;
          const baseH = Math.max(0, totalH - gap - dangerH);
          const isSelected = selectedDay === i;
          const isDimmed = selectedDay !== null && !isSelected;

          return (
            <button
              key={point.date}
              type="button"
              onClick={() => onSelect(isSelected ? null : i)}
              className="flex-1 h-full flex flex-col items-center justify-end bg-transparent border-0 p-0 cursor-pointer"
              aria-pressed={isSelected}
              aria-label={`${formatDay(point.date)}: 전체 ${point.total}건 중 위험 ${point.danger}건`}
            >
              {totalH > 0 && (
                <div
                  className="w-full flex flex-col justify-end"
                  style={{ maxWidth: 24, height: totalH, opacity: isDimmed ? 0.35 : 1 }}
                >
                  {dangerH > 0 && (
                    <div
                      style={{
                        height: dangerH,
                        background: "var(--danger-500)",
                        borderRadius: "4px 4px 0 0",
                        marginBottom: gap,
                      }}
                    />
                  )}
                  {baseH > 0 && (
                    <div
                      style={{
                        height: baseH,
                        background: "var(--primary-300)",
                        borderRadius: dangerH > 0 ? 0 : "4px 4px 0 0",
                      }}
                    />
                  )}
                </div>
              )}
            </button>
          );
        })}
      </div>

      {/* 날짜 라벨 — 막대 높이 계산과 분리된 별도 행 */}
      <div className="flex gap-1.5 mt-2">
        {data.map((point, i) => (
          <div
            key={point.date}
            className="flex-1 text-center text-[10px]"
            style={{ color: selectedDay === i ? "var(--ink-800)" : "var(--ink-400)" }}
          >
            {i % 2 === 0 ? formatDay(point.date) : ""}
          </div>
        ))}
      </div>
    </div>
  );
}

function BreakdownItem({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <span className="flex items-center gap-1">
      <span style={{ color }}>{label}</span>
      <span className="font-semibold" style={{ color: "var(--ink-950)" }}>
        {value}건
      </span>
    </span>
  );
}

function TopOrgBar({ org, count, max }: { org: string; count: number; max: number }) {
  const widthPct = Math.max(6, (count / max) * 100);
  return (
    <div>
      <div className="flex items-center justify-between mb-1 text-sm">
        <span className="font-medium truncate" style={{ color: "var(--ink-950)" }}>
          {org}
        </span>
        <span className="shrink-0 ml-2" style={{ color: "var(--ink-600)" }}>
          {count}건
        </span>
      </div>
      <div className="h-2 rounded-full" style={{ background: "var(--paper-100)" }}>
        <div
          className="h-2 rounded-full"
          style={{ width: `${widthPct}%`, background: "var(--accent-500)" }}
        />
      </div>
    </div>
  );
}
