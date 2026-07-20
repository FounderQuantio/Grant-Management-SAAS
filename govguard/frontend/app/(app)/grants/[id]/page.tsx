"use client";
import useSWR from "swr";
import { useState } from "react";
import Link from "next/link";
import {
  ArrowLeft, FileText, AlertTriangle, CheckCircle2, Clock,
  Shield, TrendingUp, Activity, Search, Zap, ChevronDown, ChevronUp,
} from "lucide-react";
import { GrantTabs } from "@/components/grants/GrantTabs";

const fetcher = (url: string) => fetch(url).then(r => r.json());

const FLAG_CONFIG: Record<string, { label: string; badgeClass: string }> = {
  pending:    { label: "Pending",   badgeClass: "qg-badge-muted" },
  clear:      { label: "Clear",     badgeClass: "qg-badge-low" },
  flagged:    { label: "Flagged",   badgeClass: "qg-badge-critical" },
  approved:   { label: "Approved",  badgeClass: "qg-badge-gold" },
  rejected:   { label: "Rejected",  badgeClass: "qg-badge-high" },
  suppressed: { label: "Duplicate", badgeClass: "qg-badge-medium" },
};

function StatusBadge({ status }: { status: string }) {
  const cfg = FLAG_CONFIG[status] || FLAG_CONFIG.pending;
  return <span className={`qg-badge ${cfg.badgeClass}`}>{cfg.label}</span>;
}

function RiskBar({ score }: { score: number | null }) {
  if (score === null || score === undefined) {
    return <span style={{ fontSize: 11, color: "var(--qg-text-4)" }}>—</span>;
  }
  const n = Number(score);
  const color = n >= 75 ? "var(--qg-red)" : n >= 40 ? "var(--qg-yellow)" : "var(--qg-green)";
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8, minWidth: 80 }}>
      <div style={{ flex: 1, background: "var(--qg-surface-2)", borderRadius: 100, height: 3 }}>
        <div style={{ background: color, height: 3, borderRadius: 100, width: `${n}%` }} />
      </div>
      <span style={{ fontSize: 11, fontWeight: 600, color: "var(--qg-text-3)", width: 22 }}>{Math.round(n)}</span>
    </div>
  );
}

function AISection({
  title, icon: Icon, onRun, result, loading, children,
}: {
  title: string;
  icon: React.ElementType;
  onRun: () => void;
  result: object | null;
  loading: boolean;
  children: (data: object) => React.ReactNode;
}) {
  const [open, setOpen] = useState(false);

  const handleRun = () => { onRun(); setOpen(true); };

  return (
    <div style={{ border: "1px solid var(--qg-border)", borderRadius: "var(--qg-radius-lg)", overflow: "hidden" }}>
      <div style={{
        display: "flex", alignItems: "center", justifyContent: "space-between",
        padding: "10px 14px", background: "var(--qg-surface-2)",
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <Icon size={13} color="var(--qg-gold)" />
          <span style={{ fontSize: 12, fontWeight: 700, color: "var(--qg-text-1)" }}>{title}</span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <button
            onClick={handleRun}
            disabled={loading}
            className="qg-btn qg-btn-primary qg-btn-sm"
            style={{ padding: "4px 12px", fontSize: 11 }}
          >
            {loading ? "Running…" : "Run"}
          </button>
          {result && (
            <button
              onClick={() => setOpen(v => !v)}
              style={{ background: "none", border: "none", cursor: "pointer", color: "var(--qg-text-4)", display: "flex" }}
            >
              {open ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
            </button>
          )}
        </div>
      </div>
      {open && result && (
        <div style={{ padding: 14, background: "var(--qg-surface)", fontSize: 12, color: "var(--qg-text-2)" }}>
          {children(result)}
        </div>
      )}
    </div>
  );
}

function TxFraudButton({ txId }: { txId: string }) {
  const [data, setData] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(false);
  const [open, setOpen] = useState(false);

  const run = async () => {
    setLoading(true);
    try {
      const res = await fetch(`/api/v2/fraud/assess/${txId}`, { method: "POST" });
      setData(await res.json());
      setOpen(true);
    } finally { setLoading(false); }
  };

  const assessment = data?.assessment as Record<string, unknown> | undefined;

  return (
    <>
      <button
        onClick={run}
        disabled={loading}
        style={{ fontSize: 11, color: "var(--qg-gold)", background: "none", border: "none", cursor: "pointer", fontWeight: 600, opacity: loading ? 0.4 : 1 }}
      >
        {loading ? "…" : "Assess"}
      </button>
      {open && assessment && (
        <div
          style={{ position: "fixed", inset: 0, zIndex: 50, display: "flex", alignItems: "center", justifyContent: "center", background: "var(--qg-overlay)", padding: 24 }}
          onClick={() => setOpen(false)}
        >
          <div
            className="qg-card"
            style={{ width: "100%", maxWidth: 480, padding: 24 }}
            onClick={e => e.stopPropagation()}
          >
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 18 }}>
              <h3 style={{ fontSize: 14, fontWeight: 800, color: "var(--qg-text-1)" }}>Fraud Assessment</h3>
              <button onClick={() => setOpen(false)} style={{ background: "none", border: "none", cursor: "pointer", color: "var(--qg-text-4)", fontSize: 18, lineHeight: 1 }}>×</button>
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 10, fontSize: 12 }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <span style={{ color: "var(--qg-text-3)" }}>Composite Score</span>
                <span style={{ fontWeight: 800, fontSize: 16, color: "var(--qg-text-1)" }}>
                  {Number(assessment.composite_score ?? 0).toFixed(1)}/100
                </span>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <span style={{ color: "var(--qg-text-3)" }}>Recommended Action</span>
                <span style={{ fontWeight: 600, color: "var(--qg-text-1)" }}>{String(assessment.recommended_action ?? "—")}</span>
              </div>
              {Array.isArray(assessment.triggered_rules) && assessment.triggered_rules.length > 0 && (
                <div>
                  <p style={{ color: "var(--qg-text-4)", marginBottom: 6 }}>Triggered Rules</p>
                  <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
                    {(assessment.triggered_rules as string[]).map(r => (
                      <span key={r} className="qg-badge qg-badge-critical">{r}</span>
                    ))}
                  </div>
                </div>
              )}
              {!!assessment.explanation && (
                <p style={{ color: "var(--qg-text-3)", background: "var(--qg-surface-2)", padding: 10, borderRadius: "var(--qg-radius-md)" }}>
                  {String(assessment.explanation)}
                </p>
              )}
            </div>
          </div>
        </div>
      )}
    </>
  );
}

function LabelButton({ txId, onLabeled }: { txId: string; onLabeled: () => void }) {
  const [saving, setSaving] = useState<"fraud" | "clean" | null>(null);
  const [done, setDone] = useState<boolean | null>(null);

  const submit = async (confirmed_fraud: boolean) => {
    setSaving(confirmed_fraud ? "fraud" : "clean");
    try {
      await fetch(`/api/v2/fraud/label/${txId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ confirmed_fraud }),
      });
      setDone(confirmed_fraud);
      onLabeled();
    } finally { setSaving(null); }
  };

  if (done !== null) {
    return (
      <span style={{ fontSize: 11, fontWeight: 600, color: done ? "var(--qg-red)" : "var(--qg-green)" }}>
        {done ? "Confirmed fraud" : "Confirmed clean"}
      </span>
    );
  }

  return (
    <div style={{ display: "flex", gap: 4 }}>
      <button
        onClick={() => submit(true)}
        disabled={!!saving}
        className="qg-badge qg-badge-critical"
        style={{ cursor: "pointer", border: "1px solid var(--qg-red-border)" }}
      >
        {saving === "fraud" ? "…" : "Fraud"}
      </button>
      <button
        onClick={() => submit(false)}
        disabled={!!saving}
        className="qg-badge qg-badge-low"
        style={{ cursor: "pointer", border: "1px solid var(--qg-green-border)" }}
      >
        {saving === "clean" ? "…" : "Clean"}
      </button>
    </div>
  );
}

export default function GrantDetailPage({ params }: { params: { id: string } }) {
  const { id } = params;
  const { data, isLoading, mutate } = useSWR(`/api/v1/grants/${id}`, fetcher);

  const [fraudResult, setFraudResult]     = useState<object | null>(null);
  const [fraudLoading, setFraudLoading]   = useState(false);
  const [anomalyResult, setAnomalyResult] = useState<object | null>(null);
  const [anomalyLoading, setAnomalyLoading] = useState(false);
  const [compResult, setCompResult]       = useState<object | null>(null);
  const [compLoading, setCompLoading]     = useState(false);
  const [riskResult, setRiskResult]       = useState<object | null>(null);
  const [riskLoading, setRiskLoading]     = useState(false);

  const runFraudScan = async () => {
    setFraudLoading(true);
    try {
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 15000);
      const res = await fetch(`/api/v2/fraud/bulk-scan/${id}`, { method: "POST", signal: controller.signal });
      clearTimeout(timeout);
      setFraudResult(await res.json());
    } catch {
      setFraudResult({ transactions_queued: 0, message: "Scan timed out — Celery worker not configured on this deployment." });
    } finally { setFraudLoading(false); }
  };

  const runAnomaly = async () => {
    setAnomalyLoading(true);
    try {
      const txns = (data as { transactions?: Record<string, unknown>[] })?.transactions ?? [];
      const latestTx = txns.reduce<Record<string, unknown> | null>((best, t) =>
        !best || parseFloat(String(t.amount)) > parseFloat(String(best.amount)) ? t : best, null);
      const txBody = latestTx ? {
        amount: parseFloat(String(latestTx.amount)),
        vendor_id: latestTx.vendor_id,
        cost_category: latestTx.cost_category,
        tx_date: latestTx.tx_date,
      } : {};
      const res = await fetch(`/api/v2/anomaly/detect/${id}`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(txBody),
      });
      setAnomalyResult(await res.json());
    } finally { setAnomalyLoading(false); }
  };

  const runCompliance = async () => {
    setCompLoading(true);
    try {
      const res = await fetch(`/api/v2/compliance/monitor/${id}`);
      setCompResult(await res.json());
    } finally { setCompLoading(false); }
  };

  const runRisk = async () => {
    setRiskLoading(true);
    try {
      const res = await fetch(`/api/v2/risk/predict/${id}`);
      setRiskResult(await res.json());
    } finally { setRiskLoading(false); }
  };

  if (isLoading) {
    return (
      <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
        {[...Array(3)].map((_, i) => (
          <div key={i} style={{ height: i === 0 ? 40 : i === 1 ? 120 : 240, background: "var(--qg-surface)", borderRadius: "var(--qg-radius-xl)", border: "1px solid var(--qg-border)", opacity: 0.6 }} />
        ))}
      </div>
    );
  }

  if (!data?.grant) {
    return (
      <div style={{ textAlign: "center", padding: "64px 0" }}>
        <p style={{ color: "var(--qg-text-3)", fontSize: 13 }}>Grant not found.</p>
        <Link href="/grants" style={{ color: "var(--qg-gold)", fontSize: 12, marginTop: 8, display: "block", textDecoration: "none" }}>
          ← Back to grants
        </Link>
      </div>
    );
  }

  const { grant, transactions = [], stats } = data as {
    grant: Record<string, unknown>;
    transactions: Record<string, unknown>[];
    stats: Record<string, unknown>;
  };

  const compliance = Number(grant.compliance_score ?? 0);
  const compColor = compliance >= 80 ? "var(--qg-green)" : compliance >= 60 ? "var(--qg-yellow)" : "var(--qg-red)";

  return (
    <div className="qg-animate-in" style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      {/* Header */}
      <div>
        <Link
          href="/grants"
          style={{ display: "inline-flex", alignItems: "center", gap: 5, fontSize: 12, color: "var(--qg-text-4)", textDecoration: "none", marginBottom: 12, transition: "var(--qg-ease)" }}
        >
          <ArrowLeft size={12} /> Back to Grants
        </Link>
        <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between" }}>
          <div>
            <h1 className="qg-title">{String(grant.award_number)}</h1>
            <p style={{ fontSize: 12, color: "var(--qg-text-4)", marginTop: 3 }}>{String(grant.agency)}</p>
          </div>
          <StatusBadge status={String(grant.status)} />
        </div>
      </div>

      <GrantTabs grantId={id} />

      {/* Stat tiles */}
      <div className="qg-grid-4">
        {[
          { label: "Total Award",      value: `$${Number(grant.total_amount).toLocaleString()}`, icon: FileText,     color: "var(--qg-gold)" },
          { label: "Compliance Score", value: `${compliance.toFixed(0)}/100`,                    icon: CheckCircle2, color: compColor },
          { label: "Flagged Tx",       value: String(stats?.flagged ?? 0),                       icon: AlertTriangle,color: "var(--qg-red)" },
          { label: "Total Spend",      value: `$${Number(stats?.total_spend ?? 0).toLocaleString()}`, icon: Clock,   color: "var(--qg-text-2)" },
        ].map(({ label, value, icon: Icon, color }) => (
          <div key={label} className="qg-card" style={{ padding: 16 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10 }}>
              <Icon size={13} color={color} />
              <span style={{ fontSize: 10, color: "var(--qg-text-4)", fontWeight: 600 }}>{label}</span>
            </div>
            <p style={{ fontSize: 18, fontWeight: 800, color, letterSpacing: "-0.3px" }}>{value}</p>
          </div>
        ))}
      </div>

      {/* Transactions + AI */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 320px", gap: 20 }}>
        {/* Transactions table */}
        <div className="qg-card" style={{ padding: 0, overflow: "hidden" }}>
          <div style={{
            padding: "14px 20px", borderBottom: "1px solid var(--qg-border)",
            display: "flex", alignItems: "center", justifyContent: "space-between",
          }}>
            <h2 style={{ fontSize: 13, fontWeight: 700, color: "var(--qg-text-1)" }}>Transactions</h2>
            <span style={{ fontSize: 11, color: "var(--qg-text-4)" }}>{transactions.length} total</span>
          </div>

          {transactions.length === 0 ? (
            <div style={{ textAlign: "center", padding: "48px 0", color: "var(--qg-text-4)" }}>
              <FileText size={24} style={{ margin: "0 auto 8px", display: "block" }} />
              <p style={{ fontSize: 12 }}>No transactions yet</p>
            </div>
          ) : (
            <div style={{ overflowX: "auto" }}>
              <table className="qg-table">
                <thead>
                  <tr>
                    <th>Date</th>
                    <th>Invoice</th>
                    <th>Vendor</th>
                    <th style={{ textAlign: "right" }}>Amount</th>
                    <th style={{ textAlign: "center" }}>Risk</th>
                    <th style={{ textAlign: "center" }}>Status</th>
                    <th style={{ textAlign: "center" }}>Label</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {transactions.map((tx) => (
                    <tr key={String(tx.id)}>
                      <td style={{ fontSize: 12 }}>{String(tx.tx_date ?? "").slice(0, 10)}</td>
                      <td style={{ fontFamily: "monospace", fontSize: 11 }}>{String(tx.invoice_ref)}</td>
                      <td style={{ maxWidth: 130, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", fontSize: 12 }}>
                        {String(tx.vendor_name ?? "—")}
                      </td>
                      <td style={{ textAlign: "right", fontWeight: 600, color: "var(--qg-text-1)", fontSize: 12 }}>
                        ${Number(tx.amount).toLocaleString(undefined, { minimumFractionDigits: 2 })}
                      </td>
                      <td style={{ textAlign: "center" }}>
                        <RiskBar score={tx.risk_score as number | null} />
                      </td>
                      <td style={{ textAlign: "center" }}>
                        <StatusBadge status={String(tx.flag_status)} />
                      </td>
                      <td style={{ textAlign: "center" }}>
                        {String(tx.flag_status) === "flagged" && (
                          <LabelButton txId={String(tx.id)} onLabeled={() => mutate()} />
                        )}
                      </td>
                      <td style={{ textAlign: "center" }}>
                        <TxFraudButton txId={String(tx.id)} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* AI Intelligence panel */}
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          <h2 style={{ fontSize: 13, fontWeight: 700, color: "var(--qg-text-1)", display: "flex", alignItems: "center", gap: 7 }}>
            <Zap size={13} color="var(--qg-gold)" /> AI Intelligence
          </h2>

          <AISection title="Risk Prediction" icon={TrendingUp} onRun={runRisk} result={riskResult} loading={riskLoading}>
            {(d) => {
              const r = d as Record<string, unknown>;
              return (
                <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                  <div style={{ display: "flex", justifyContent: "space-between" }}>
                    <span style={{ color: "var(--qg-text-4)" }}>Predicted Risk</span>
                    <span style={{ fontWeight: 800, color: "var(--qg-text-1)" }}>{Number(r.predicted_risk_score ?? 0).toFixed(1)}/100</span>
                  </div>
                  <div style={{ display: "flex", justifyContent: "space-between" }}>
                    <span style={{ color: "var(--qg-text-4)" }}>Trend</span>
                    <span style={{ fontWeight: 600, textTransform: "capitalize", color: "var(--qg-text-2)" }}>{String(r.trend ?? "—")}</span>
                  </div>
                  <div style={{ display: "flex", justifyContent: "space-between" }}>
                    <span style={{ color: "var(--qg-text-4)" }}>Confidence</span>
                    <span style={{ fontWeight: 600, color: "var(--qg-text-2)" }}>{(Number(r.confidence ?? 0) * 100).toFixed(0)}%</span>
                  </div>
                  {Array.isArray(r.risk_drivers) && r.risk_drivers.length > 0 && (
                    <div style={{ marginTop: 4 }}>
                      <p style={{ color: "var(--qg-text-4)", marginBottom: 5, fontSize: 10 }}>Top Drivers</p>
                      {(r.risk_drivers as { factor: string; contribution: number }[]).slice(0, 3).map((drv) => (
                        <p key={drv.factor} style={{ fontSize: 11, background: "var(--qg-yellow-bg)", color: "var(--qg-yellow)", padding: "4px 8px", borderRadius: "var(--qg-radius-sm)", marginBottom: 3 }}>
                          {drv.factor.replace(/_/g, " ")} <strong>(+{drv.contribution})</strong>
                        </p>
                      ))}
                    </div>
                  )}
                </div>
              );
            }}
          </AISection>

          <AISection title="Fraud Bulk Scan" icon={Shield} onRun={runFraudScan} result={fraudResult} loading={fraudLoading}>
            {(d) => {
              const r = d as Record<string, unknown>;
              return (
                <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                  <div style={{ display: "flex", justifyContent: "space-between" }}>
                    <span style={{ color: "var(--qg-text-4)" }}>Queued</span>
                    <span style={{ fontWeight: 800, color: "var(--qg-text-1)" }}>{String(r.transactions_queued ?? 0)}</span>
                  </div>
                  <p style={{ fontSize: 11, color: "var(--qg-text-4)" }}>{String(r.message ?? "")}</p>
                </div>
              );
            }}
          </AISection>

          <AISection title="Anomaly Detection" icon={Activity} onRun={runAnomaly} result={anomalyResult} loading={anomalyLoading}>
            {(d) => {
              const r = d as Record<string, unknown>;
              const alerts = (r.alerts ?? []) as Record<string, unknown>[];
              return (
                <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                  <div style={{ display: "flex", justifyContent: "space-between" }}>
                    <span style={{ color: "var(--qg-text-4)" }}>Alerts</span>
                    <span style={{ fontWeight: 800, color: "var(--qg-text-1)" }}>{String(r.alert_count ?? 0)}</span>
                  </div>
                  {alerts.slice(0, 4).map((a, i) => (
                    <div key={i} style={{ background: "var(--qg-yellow-bg)", border: "1px solid var(--qg-yellow-border)", borderRadius: "var(--qg-radius-sm)", padding: "6px 8px", fontSize: 11 }}>
                      <p style={{ fontWeight: 700, color: "var(--qg-yellow)" }}>{String(a.type ?? "")}</p>
                      <p style={{ color: "var(--qg-text-3)", marginTop: 2 }}>{String(a.description ?? "")}</p>
                    </div>
                  ))}
                </div>
              );
            }}
          </AISection>

          <AISection title="Compliance Monitor" icon={Search} onRun={runCompliance} result={compResult} loading={compLoading}>
            {(d) => {
              const r = d as Record<string, unknown>;
              const violations = (r.violations ?? []) as Record<string, unknown>[];
              return (
                <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                  <div style={{ display: "flex", justifyContent: "space-between" }}>
                    <span style={{ color: "var(--qg-text-4)" }}>Violations</span>
                    <span style={{ fontWeight: 800, color: "var(--qg-text-1)" }}>{String(r.violation_count ?? 0)}</span>
                  </div>
                  <div style={{ display: "flex", justifyContent: "space-between" }}>
                    <span style={{ color: "var(--qg-text-4)" }}>Auto-CAPs</span>
                    <span style={{ fontWeight: 600, color: "var(--qg-text-2)" }}>{String(r.auto_caps_created ?? 0)}</span>
                  </div>
                  {violations.slice(0, 4).map((v, i) => (
                    <div key={i} style={{ background: "var(--qg-red-bg)", border: "1px solid var(--qg-red-border)", borderRadius: "var(--qg-radius-sm)", padding: "6px 8px", fontSize: 11 }}>
                      <p style={{ fontWeight: 700, color: "var(--qg-red)" }}>{String(v.title ?? v.rule_id ?? "")}</p>
                      <p style={{ color: "var(--qg-text-4)", marginTop: 2 }}>{String(v.cfr_citation ?? "")} {String(v.severity ?? "")}</p>
                      <p style={{ color: "var(--qg-red)", marginTop: 2, opacity: 0.8 }}>{String(v.recommended_remediation ?? "")}</p>
                    </div>
                  ))}
                </div>
              );
            }}
          </AISection>
        </div>
      </div>
    </div>
  );
}
