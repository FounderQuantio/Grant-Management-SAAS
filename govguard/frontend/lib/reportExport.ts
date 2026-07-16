"use client";
/**
 * Findings Report — generates a self-contained HTML report from the same
 * dashboard KPIs endpoint the Governance Dashboard uses. Triggered from
 * the "Download Report" button in the app header.
 */
import { api } from "@/lib/api";
import type { DashboardKPIs } from "@/types";

const fmt = (n: number | undefined | null) =>
  n === undefined || n === null ? "--" : n.toLocaleString();

export async function generateFindingsReport(): Promise<void> {
  const kpis = await api.get<DashboardKPIs>("/api/v1/dashboard/kpis?period=30d");
  const now = new Date().toLocaleString("en-US", { dateStyle: "long", timeStyle: "short" });
  const sc = kpis.complianceScore >= 80 ? "#22C55E" : kpis.complianceScore >= 60 ? "#F59E0B" : "#EF4444";
  const pr = kpis.improperPaymentRate < 5 ? "#22C55E" : kpis.improperPaymentRate < 10 ? "#F59E0B" : "#EF4444";

  const leaderboardRows = (kpis.riskLeaderboard || []).map(g => `
    <tr>
      <td><b>${g.awardNumber}</b></td>
      <td>${g.agency}</td>
      <td>${g.grantId}</td>
      <td>${g.complianceScore.toFixed(0)}/100</td>
    </tr>`).join("");

  const html = `<!DOCTYPE html><html><head><meta charset="UTF-8">
<title>GovGuard Findings Report — ${new Date().toISOString().slice(0,10)}</title>
<style>
  body{font-family:Arial,sans-serif;font-size:12px;color:#212427;margin:40px;line-height:1.6}
  h1{font-size:21px;color:#1F3A5F;border-bottom:3px solid #3D5A99;padding-bottom:8px}
  h2{font-size:14px;color:#3D5A99;border-left:4px solid #3D5A99;padding-left:9px;margin:26px 0 8px}
  table{width:100%;border-collapse:collapse;margin:8px 0 14px}
  td,th{border:1px solid #E4E7EB;padding:6px 10px;font-size:11px;text-align:left}
  th{background:#1F3A5F;color:#fff;font-weight:600}
  tr:nth-child(even){background:#F4F5F7}
  .stat-grid{display:flex;gap:14px;margin:12px 0 20px;flex-wrap:wrap}
  .stat{flex:1;min-width:150px;background:#F4F5F7;border:1px solid #E4E7EB;border-radius:8px;padding:12px 14px}
  .stat .v{font-size:22px;font-weight:800;color:#1F3A5F}
  .stat .l{font-size:9.5px;font-weight:700;letter-spacing:0.5px;text-transform:uppercase;color:#6B7280;margin-top:2px}
  .box{background:#EEF1F4;border:1px solid #C9D2DE;border-radius:6px;padding:12px;margin:10px 0;font-size:11.5px}
  .footer{margin-top:36px;border-top:1px solid #E4E7EB;padding-top:10px;font-size:10px;color:#9AA3AF;text-align:center}
</style></head><body>

<h1>🛡 GovGuard™ Grant Compliance — Findings Report</h1>
<div style="display:flex;justify-content:space-between;font-size:11px;color:#6B7280;margin-bottom:10px">
  <span><b>Generated:</b> ${now}</span>
  <span><b>System:</b> GovGuard™ Grant Compliance Platform</span>
  <span><b>Period:</b> Last ${kpis.periodDays ?? 30} days</span>
</div>

<div class="box"><b>Executive Summary</b><br>
Across ${fmt(kpis.totalTxCount)} transactions in the reporting period, GovGuard flagged ${fmt(kpis.flaggedTxCount)} for review and recorded ${fmt(kpis.openFindings)} open audit findings. The improper payment rate stands at ${kpis.improperPaymentRate?.toFixed(1) ?? "--"}%, with an average grant compliance score of ${kpis.complianceScore?.toFixed(0) ?? "--"}/100.
</div>

<div class="stat-grid">
  <div class="stat"><div class="v" style="color:${pr}">${kpis.improperPaymentRate?.toFixed(1) ?? "--"}%</div><div class="l">Improper Payment Rate</div></div>
  <div class="stat"><div class="v" style="color:${sc}">${kpis.complianceScore?.toFixed(0) ?? "--"}/100</div><div class="l">Avg Compliance Score</div></div>
  <div class="stat"><div class="v">${fmt(kpis.openFindings)}</div><div class="l">Open Findings</div></div>
  <div class="stat"><div class="v">${fmt(kpis.flaggedTxCount)}</div><div class="l">Flagged Transactions</div></div>
  <div class="stat"><div class="v">${fmt(kpis.totalTxCount)}</div><div class="l">Total Transactions</div></div>
</div>

<h2>1. Grant Risk Leaderboard</h2>
<table><tr><th>Award Number</th><th>Agency</th><th>Grant ID</th><th>Compliance Score</th></tr>
${leaderboardRows || '<tr><td colspan="4">No grants in the current risk leaderboard.</td></tr>'}
</table>

<div class="footer">
  GovGuard™ Grant Compliance Platform · Muhammad Bilal FCA FCCA CFA<br>
  OMB 2 CFR 200 · GAO Green Book · COSO<br>
  CONFIDENTIAL – Authorized Personnel Only · ${now}
</div></body></html>`;

  const blob = new Blob([html], { type: "text/html" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `GovGuard_Findings_Report_${new Date().toISOString().slice(0, 10)}.html`;
  a.click();
  URL.revokeObjectURL(url);
}
