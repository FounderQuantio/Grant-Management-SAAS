"use client";
import useSWR from "swr";
import { api } from "@/lib/api";
import { DashboardKPIs } from "@/types";
import { KPITile } from "./KPITile";
import { RiskLeaderboard } from "./RiskLeaderboard";
import { AlertTriage } from "./AlertTriage";
import { TrendingDown, ClipboardCheck, AlertTriangle, DollarSign } from "lucide-react";

export function DashboardContent() {
  const { data: kpis, error, isLoading } = useSWR<DashboardKPIs>(
    "/api/v1/dashboard/kpis?period=30d",
    (url) => api.get<DashboardKPIs>(url),
    { refreshInterval: 300000 }
  );

  if (error) {
    return (
      <div style={{
        background: "var(--qg-red-bg)", border: "1px solid var(--qg-red-border)",
        borderRadius: "var(--qg-radius-xl)", padding: 24, color: "var(--qg-red)",
        fontSize: 13,
      }}>
        Failed to load dashboard data. Please refresh the page.
      </div>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      <div className="qg-grid-4">
        <KPITile
          label="Improper Payment Rate"
          value={`${kpis?.improperPaymentRate?.toFixed(1) ?? "--"}%`}
          icon={TrendingDown}
          trend={kpis ? (kpis.improperPaymentRate < 5 ? "good" : "bad") : "neutral"}
          loading={isLoading}
          description="Last 30 days"
        />
        <KPITile
          label="Avg Compliance Score"
          value={`${kpis?.complianceScore?.toFixed(0) ?? "--"}/100`}
          icon={ClipboardCheck}
          trend={kpis ? (kpis.complianceScore > 80 ? "good" : "bad") : "neutral"}
          loading={isLoading}
          description="Active grants"
        />
        <KPITile
          label="Open Findings"
          value={String(kpis?.openFindings ?? "--")}
          icon={AlertTriangle}
          trend={kpis ? (kpis.openFindings < 5 ? "good" : "bad") : "neutral"}
          loading={isLoading}
          description="Audit findings"
        />
        <KPITile
          label="Flagged Transactions"
          value={String(kpis?.flaggedTxCount ?? "--")}
          icon={DollarSign}
          trend="neutral"
          loading={isLoading}
          description="Pending review"
        />
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20 }}>
        <RiskLeaderboard leaderboard={kpis?.riskLeaderboard ?? []} loading={isLoading} />
        <AlertTriage />
      </div>
    </div>
  );
}
