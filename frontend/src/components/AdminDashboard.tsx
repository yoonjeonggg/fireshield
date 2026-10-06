"use client";

import { useState } from "react";
import { fetchAdminStats } from "@/lib/api";
import { AdminStatsResponse } from "@/types/admin";
import { RISK_LEVEL_META } from "@/lib/riskLevel";
import { RiskLevel } from "@/types/verify";
import RiskLevelStatCards from "@/components/RiskLevelStatCards";

export default function AdminDashboard() {
  const [adminKey, setAdminKey] = useState("");
  const [authenticated, setAuthenticated] = useState(false);
  const [stats, setStats] = useState<AdminStatsResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleLogin(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      const data = await fetchAdminStats(adminKey);
      setStats(data);
      setAuthenticated(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "오류가 발생했습니다.");
    } finally {
      setLoading(false);
    }
  }

  async function handleRefresh() {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchAdminStats(adminKey);
      setStats(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "오류가 발생했습니다.");
    } finally {
      setLoading(false);
    }
  }

  if (!authenticated) {
    return (
      <div className="max-w-[400px] mx-auto px-5 py-24">
        <h1 className="text-xl font-bold mb-4 text-center" style={{ fontFamily: "var(--font-head)" }}>
          관리자 로그인
        </h1>
        <form onSubmit={handleLogin} className="flex flex-col gap-3">
          <input
            type="password"
            value={adminKey}
            onChange={(e) => setAdminKey(e.target.value)}
            placeholder="관리자 키 입력"
            className="w-full px-3 py-2 rounded-lg"
            style={{ border: "1.5px solid var(--paper-200)", background: "var(--paper-50)" }}
            required
          />
          <button
            type="submit"
            disabled={loading}
            className="w-full py-2.5 rounded-lg font-semibold text-white"
            style={{ background: "var(--primary-500)", opacity: loading ? 0.6 : 1 }}
          >
            {loading ? "확인 중..." : "로그인"}
          </button>
        </form>
        {error && (
          <p className="mt-3 text-sm text-center" style={{ color: "var(--danger-600)" }}>
            {error}
          </p>
        )}
      </div>
    );
  }

  return (
    <div className="max-w-[1120px] mx-auto px-5 py-12">
      <div className="flex items-center justify-between mb-8">
        <h1 className="text-2xl font-bold" style={{ fontFamily: "var(--font-head)" }}>
          관리자 대시보드
        </h1>
        <button
          onClick={handleRefresh}
          disabled={loading}
          className="text-sm font-semibold px-4 py-2 rounded-lg"
          style={{ background: "var(--paper-100)", color: "var(--ink-800)" }}
        >
          {loading ? "새로고침 중..." : "새로고침"}
        </button>
      </div>

      {error && (
        <div
          className="mb-4 p-3 rounded-lg text-sm"
          style={{ background: "var(--danger-100)", color: "var(--danger-600)" }}
        >
          {error}
        </div>
      )}

      {stats && (
        <>
          {/* 통계 카드 */}
          <RiskLevelStatCards total={stats.total_count} stats={stats.risk_level_stats} className="mb-10" />

          {/* 최근 로그 테이블 */}
          <h2 className="text-lg font-bold mb-3" style={{ color: "var(--ink-950)" }}>
            최근 조회 로그
          </h2>
          <div className="overflow-x-auto rounded-lg" style={{ border: "1px solid var(--paper-200)" }}>
            <table className="w-full text-sm">
              <thead>
                <tr style={{ background: "var(--paper-50)" }}>
                  <Th>시각</Th>
                  <Th>발신 기관</Th>
                  <Th>담당자</Th>
                  <Th>요구 사유</Th>
                  <Th>대상 업체</Th>
                  <Th>계좌요구</Th>
                  <Th>판정</Th>
                  <Th>점수</Th>
                </tr>
              </thead>
              <tbody>
                {stats.recent_logs.map((log) => {
                  const risk = log.risk_level ? RISK_LEVEL_META[log.risk_level as RiskLevel] : undefined;
                  return (
                    <tr key={log.id} style={{ borderTop: "1px solid var(--paper-100)" }}>
                      <Td>{new Date(log.created_at).toLocaleString("ko-KR")}</Td>
                      <Td>{log.claimed_org ?? "-"}</Td>
                      <Td>{log.claimed_person ?? "-"}</Td>
                      <Td className="max-w-[200px] truncate">{log.claim_type ?? "-"}</Td>
                      <Td>{log.target_business ?? "-"}</Td>
                      <Td>{log.has_account_number ? "있음" : "없음"}</Td>
                      <Td>
                        {risk && (
                          <span className="font-semibold" style={{ color: risk.color }}>
                            {risk.label}
                          </span>
                        )}
                      </Td>
                      <Td>{log.score ?? "-"}</Td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}

function Th({ children }: { children: React.ReactNode }) {
  return (
    <th className="text-left px-3 py-2 text-xs font-semibold" style={{ color: "var(--ink-600)" }}>
      {children}
    </th>
  );
}

function Td({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return (
    <td className={`px-3 py-2 ${className}`} style={{ color: "var(--ink-800)" }}>
      {children}
    </td>
  );
}