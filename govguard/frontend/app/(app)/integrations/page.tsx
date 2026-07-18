"use client";
import useSWR from "swr";
import { Plug, CheckCircle2, XCircle, Loader2 } from "lucide-react";

const fetcher = (url: string) => fetch(url).then(r => r.json());

interface JobRow {
  id: string;
  job_type: string;
  status: string;
  rows_total: number | null;
  rows_processed: number | null;
  rows_failed: number | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
}

const STATUS_CONFIG: Record<string, { badgeClass: string; icon: React.ElementType }> = {
  queued:    { badgeClass: "qg-badge-muted",    icon: Loader2 },
  running:   { badgeClass: "qg-badge-gold",     icon: Loader2 },
  completed: { badgeClass: "qg-badge-low",      icon: CheckCircle2 },
  failed:    { badgeClass: "qg-badge-critical", icon: XCircle },
};

export default function IntegrationsPage() {
  const { data, isLoading } = useSWR<{ jobs: JobRow[]; total: number }>("/api/v1/integrations/jobs", fetcher);
  const jobs = data?.jobs || [];

  return (
    <div className="qg-animate-in" style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      <div>
        <span className="qg-section-label-badge" style={{ marginBottom: 8, display: "inline-block" }}>Integrations</span>
        <h1 className="qg-title" style={{ marginTop: 8 }}>ERP Sync Jobs</h1>
        <p className="qg-subtitle" style={{ marginTop: 4 }}>Batch import history from connected financial and ERP systems</p>
      </div>

      {isLoading ? (
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {[...Array(3)].map((_, i) => (
            <div key={i} style={{ height: 64, background: "var(--qg-surface)", borderRadius: "var(--qg-radius-xl)", border: "1px solid var(--qg-border)", opacity: 0.6 }} />
          ))}
        </div>
      ) : jobs.length === 0 ? (
        <div className="qg-card" style={{ textAlign: "center", padding: "64px 24px" }}>
          <Plug size={36} color="var(--qg-text-4)" style={{ margin: "0 auto 12px", display: "block" }} />
          <p style={{ fontWeight: 700, color: "var(--qg-text-1)", marginBottom: 6, fontSize: 14 }}>No sync jobs yet</p>
          <p style={{ fontSize: 12, color: "var(--qg-text-4)" }}>Connect an ERP or financial system to begin importing transactions.</p>
        </div>
      ) : (
        <div className="qg-card" style={{ padding: 0, overflow: "hidden" }}>
          <div style={{ overflowX: "auto" }}>
            <table className="qg-table">
              <thead>
                <tr>
                  <th>Job Type</th>
                  <th style={{ textAlign: "center" }}>Status</th>
                  <th style={{ textAlign: "right" }}>Processed / Total</th>
                  <th style={{ textAlign: "right" }}>Failed</th>
                  <th>Started</th>
                  <th>Completed</th>
                </tr>
              </thead>
              <tbody>
                {jobs.map((j) => {
                  const cfg = STATUS_CONFIG[j.status] || STATUS_CONFIG.queued;
                  const Icon = cfg.icon;
                  return (
                    <tr key={j.id}>
                      <td style={{ fontWeight: 700, color: "var(--qg-text-1)", fontSize: 12, textTransform: "capitalize" }}>
                        {j.job_type.replace(/_/g, " ")}
                      </td>
                      <td style={{ textAlign: "center" }}>
                        <span className={`qg-badge ${cfg.badgeClass}`} style={{ display: "inline-flex", alignItems: "center", gap: 4, textTransform: "capitalize" }}>
                          <Icon size={10} /> {j.status}
                        </span>
                      </td>
                      <td style={{ textAlign: "right", fontSize: 12 }}>
                        {j.rows_processed ?? "—"} / {j.rows_total ?? "—"}
                      </td>
                      <td style={{ textAlign: "right", fontSize: 12, color: j.rows_failed ? "var(--qg-red)" : "var(--qg-text-4)" }}>
                        {j.rows_failed ?? 0}
                      </td>
                      <td style={{ fontSize: 11, color: "var(--qg-text-4)" }}>
                        {j.started_at ? new Date(j.started_at).toLocaleString() : "—"}
                      </td>
                      <td style={{ fontSize: 11, color: "var(--qg-text-4)" }}>
                        {j.completed_at ? new Date(j.completed_at).toLocaleString() : "—"}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
