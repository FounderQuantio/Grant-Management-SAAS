"use client";
import { useParams } from "next/navigation";
import { useState } from "react";
import { useReporting, ReportingPeriod } from "@/lib/hooks/useReporting";
import { GrantTabs } from "@/components/grants/GrantTabs";
import { api, APIError } from "@/lib/api";
import { CheckCircle2, Clock, AlertTriangle, FileSignature } from "lucide-react";

// 2 CFR 200.415(a) — the exact required certification language. Must match
// modules/performance_reporting/router.py's CERTIFICATION_TEXT verbatim so
// the person checking the box is certifying to the same statement the
// backend records against the submission.
const CERTIFICATION_TEXT =
  "By signing this report, I certify to the best of my knowledge and belief " +
  "that the report is true, complete, and accurate, and the expenditures, " +
  "disbursements and cash receipts are for the purposes and objectives set " +
  "forth in the terms and conditions of the Federal award. I am aware that " +
  "any false, fictitious, or fraudulent information, or the omission of any " +
  "material fact, may subject me to criminal, civil or administrative " +
  "penalties for fraud, false statements, false claims or otherwise " +
  "(18 U.S.C. 1001 and 31 U.S.C. 3729-3730 and 3801-3812).";

const STATUS_CONFIG: Record<string, { icon: typeof CheckCircle2; color: string; bg: string; border: string; label: string }> = {
  submitted: { icon: CheckCircle2, color: "var(--qg-green)",  bg: "var(--qg-green-bg)",  border: "var(--qg-green-border)",  label: "Submitted" },
  overdue:   { icon: AlertTriangle,color: "var(--qg-red)",    bg: "var(--qg-red-bg)",    border: "var(--qg-red-border)",    label: "Overdue" },
  upcoming:  { icon: Clock,        color: "var(--qg-text-3)", bg: "var(--qg-surface-2)", border: "var(--qg-border)",        label: "Upcoming" },
};

function SubmitReportModal({
  grantId, period, onClose, onSubmitted,
}: {
  grantId: string;
  period: ReportingPeriod;
  onClose: () => void;
  onSubmitted: () => void;
}) {
  const [narrative, setNarrative] = useState("");
  const [certified, setCertified] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async () => {
    setSaving(true);
    setError(null);
    try {
      await api.post(`/api/v1/reporting/grants/${grantId}`, {
        period_label: period.period_label,
        narrative,
        certification_accepted: certified,
      });
      onSubmitted();
      onClose();
    } catch (e) {
      setError(e instanceof APIError ? e.message : "Submission failed");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div
      style={{ position: "fixed", inset: 0, zIndex: 50, display: "flex", alignItems: "center", justifyContent: "center", background: "var(--qg-overlay)", padding: 24 }}
      onClick={onClose}
    >
      <div className="qg-card" style={{ width: "100%", maxWidth: 560, padding: 24 }} onClick={(e) => e.stopPropagation()}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
          <h3 style={{ fontSize: 14, fontWeight: 800, color: "var(--qg-text-1)" }}>
            Submit Performance Report — {period.period_label}
          </h3>
          <button onClick={onClose} style={{ background: "none", border: "none", cursor: "pointer", color: "var(--qg-text-4)", fontSize: 18, lineHeight: 1 }}>×</button>
        </div>

        <p style={{ fontSize: 11, color: "var(--qg-text-4)", marginBottom: 14 }}>
          Reporting period ending {period.period_end} · due {period.due_date} · 2 CFR §200.329
        </p>

        <label style={{ fontSize: 11, fontWeight: 600, color: "var(--qg-text-3)", display: "block", marginBottom: 6 }}>
          Narrative
        </label>
        <textarea
          value={narrative}
          onChange={(e) => setNarrative(e.target.value)}
          rows={4}
          placeholder="Summarize progress, expenditures, and objectives for this reporting period…"
          style={{
            width: "100%", resize: "vertical", fontSize: 12, padding: "10px 12px",
            border: "1px solid var(--qg-border)", borderRadius: "var(--qg-radius-md)",
            background: "var(--qg-surface)", color: "var(--qg-text-1)", marginBottom: 16,
            fontFamily: "inherit",
          }}
        />

        <div style={{
          display: "flex", alignItems: "center", gap: 6, marginBottom: 8,
        }}>
          <FileSignature size={13} color="var(--qg-gold)" />
          <span style={{ fontSize: 11, fontWeight: 700, color: "var(--qg-text-1)" }}>
            Required Certification — 2 CFR §200.415
          </span>
        </div>
        <p style={{
          fontSize: 11, lineHeight: 1.5, color: "var(--qg-text-3)",
          background: "var(--qg-surface-2)", border: "1px solid var(--qg-border)",
          borderRadius: "var(--qg-radius-md)", padding: "10px 12px", marginBottom: 12,
        }}>
          {CERTIFICATION_TEXT}
        </p>

        <label style={{ display: "flex", alignItems: "flex-start", gap: 8, fontSize: 12, color: "var(--qg-text-2)", marginBottom: 16, cursor: "pointer" }}>
          <input
            type="checkbox"
            checked={certified}
            onChange={(e) => setCertified(e.target.checked)}
            style={{ marginTop: 2 }}
          />
          I have read and certify to the statement above.
        </label>

        {error && (
          <p style={{ fontSize: 11, color: "var(--qg-red)", background: "var(--qg-red-bg)", border: "1px solid var(--qg-red-border)", borderRadius: "var(--qg-radius-md)", padding: "8px 12px", marginBottom: 12 }}>
            {error}
          </p>
        )}

        <div style={{ display: "flex", justifyContent: "flex-end", gap: 8 }}>
          <button onClick={onClose} className="qg-btn qg-btn-secondary qg-btn-sm">Cancel</button>
          <button
            onClick={submit}
            disabled={!certified || saving}
            className="qg-btn qg-btn-primary qg-btn-sm"
          >
            {saving ? "Submitting…" : "Submit Report"}
          </button>
        </div>
      </div>
    </div>
  );
}

export default function ReportingPage() {
  const { id: grantId } = useParams<{ id: string }>();
  const { data, isLoading, mutate } = useReporting(grantId);
  const [activePeriod, setActivePeriod] = useState<ReportingPeriod | null>(null);

  const periods = data?.periods ?? [];
  const submittedCount = periods.filter((p) => p.status === "submitted").length;
  const overdueCount = periods.filter((p) => p.status === "overdue").length;

  return (
    <div className="qg-animate-in">
      <GrantTabs grantId={grantId} />

      <div style={{ marginBottom: 24 }}>
        <span className="qg-section-label-badge" style={{ marginBottom: 8, display: "inline-block" }}>Reporting</span>
        <h1 className="qg-title" style={{ marginTop: 8 }}>Performance Reports</h1>
        <p className="qg-subtitle" style={{ marginTop: 4 }}>2 CFR §200.329 quarterly reporting · §200.415 required certification</p>
      </div>

      {data && (
        <div className="qg-grid-3" style={{ marginBottom: 24 }}>
          <div className="qg-card" style={{ borderColor: "var(--qg-green-border)", display: "flex", alignItems: "center", gap: 14, padding: 16 }}>
            <CheckCircle2 size={28} color="var(--qg-green)" />
            <div>
              <p style={{ fontSize: 22, fontWeight: 800, color: "var(--qg-green)" }}>{submittedCount}</p>
              <p style={{ fontSize: 11, color: "var(--qg-green)", opacity: 0.7 }}>Submitted</p>
            </div>
          </div>
          <div className="qg-card" style={{ borderColor: "var(--qg-red-border)", display: "flex", alignItems: "center", gap: 14, padding: 16 }}>
            <AlertTriangle size={28} color="var(--qg-red)" />
            <div>
              <p style={{ fontSize: 22, fontWeight: 800, color: "var(--qg-red)" }}>{overdueCount}</p>
              <p style={{ fontSize: 11, color: "var(--qg-red)", opacity: 0.7 }}>Overdue</p>
            </div>
          </div>
          <div className="qg-card" style={{ display: "flex", alignItems: "center", gap: 14, padding: 16 }}>
            <Clock size={28} color="var(--qg-text-3)" />
            <div>
              <p style={{ fontSize: 22, fontWeight: 800, color: "var(--qg-text-2)" }}>{periods.length - submittedCount - overdueCount}</p>
              <p style={{ fontSize: 11, color: "var(--qg-text-4)" }}>Upcoming</p>
            </div>
          </div>
        </div>
      )}

      {isLoading ? (
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {[...Array(4)].map((_, i) => (
            <div key={i} style={{ height: 56, background: "var(--qg-surface)", borderRadius: "var(--qg-radius-md)", border: "1px solid var(--qg-border)", opacity: 0.6 }} />
          ))}
        </div>
      ) : (
        <div className="qg-card" style={{ padding: 0, overflow: "hidden" }}>
          <div style={{ overflowX: "auto" }}>
            <table className="qg-table">
              <thead>
                <tr>
                  <th>Period</th>
                  <th>Period End</th>
                  <th>Due</th>
                  <th style={{ textAlign: "center" }}>Status</th>
                  <th style={{ textAlign: "center" }}>Certified</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {periods.map((p) => {
                  const cfg = STATUS_CONFIG[p.status] || STATUS_CONFIG.upcoming;
                  const Icon = cfg.icon;
                  return (
                    <tr key={p.period_label}>
                      <td style={{ fontWeight: 700, fontSize: 12 }}>{p.period_label}</td>
                      <td style={{ fontSize: 12 }}>{p.period_end}</td>
                      <td style={{ fontSize: 12 }}>{p.due_date}</td>
                      <td style={{ textAlign: "center" }}>
                        <span className="qg-badge" style={{ background: cfg.bg, color: cfg.color, border: `1px solid ${cfg.border}`, display: "inline-flex", alignItems: "center", gap: 4 }}>
                          <Icon size={11} /> {cfg.label}
                        </span>
                      </td>
                      <td style={{ textAlign: "center" }}>
                        {p.status === "submitted" ? (
                          p.certification_accepted ? (
                            <span className="qg-badge qg-badge-low">Certified</span>
                          ) : (
                            <span className="qg-badge qg-badge-critical">Uncertified</span>
                          )
                        ) : (
                          <span style={{ fontSize: 11, color: "var(--qg-text-4)" }}>—</span>
                        )}
                      </td>
                      <td style={{ textAlign: "right" }}>
                        {p.status !== "submitted" && (
                          <button onClick={() => setActivePeriod(p)} className="qg-btn qg-btn-primary qg-btn-sm">
                            Submit Report
                          </button>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {activePeriod && (
        <SubmitReportModal
          grantId={grantId}
          period={activePeriod}
          onClose={() => setActivePeriod(null)}
          onSubmitted={() => mutate()}
        />
      )}
    </div>
  );
}
