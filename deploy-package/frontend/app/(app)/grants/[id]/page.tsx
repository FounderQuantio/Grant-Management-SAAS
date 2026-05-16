"use client";
import useSWR from "swr";
import { useState } from "react";
import Link from "next/link";
import {
  ArrowLeft, FileText, AlertTriangle, CheckCircle2, Clock,
  Shield, TrendingUp, Activity, Search, Zap, ChevronDown, ChevronUp,
} from "lucide-react";

const fetcher = (url: string) => fetch(url).then(r => r.json());

const FLAG_CONFIG: Record<string, { label: string; color: string }> = {
  pending:    { label: "Pending",    color: "bg-gray-100 text-gray-600 border-gray-200" },
  clear:      { label: "Clear",      color: "bg-green-50 text-green-700 border-green-200" },
  flagged:    { label: "Flagged",    color: "bg-red-50 text-red-700 border-red-200" },
  approved:   { label: "Approved",   color: "bg-blue-50 text-blue-700 border-blue-200" },
  rejected:   { label: "Rejected",   color: "bg-orange-50 text-orange-700 border-orange-200" },
  suppressed: { label: "Duplicate",  color: "bg-purple-50 text-purple-700 border-purple-200" },
};

function Badge({ status }: { status: string }) {
  const cfg = FLAG_CONFIG[status] || FLAG_CONFIG.pending;
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border ${cfg.color}`}>
      {cfg.label}
    </span>
  );
}

function RiskBar({ score }: { score: number | null }) {
  if (score === null || score === undefined) return <span className="text-xs text-gray-400">—</span>;
  const n = Number(score);
  const color = n >= 75 ? "bg-red-500" : n >= 40 ? "bg-amber-500" : "bg-green-500";
  return (
    <div className="flex items-center gap-2 min-w-[80px]">
      <div className="flex-1 bg-gray-200 rounded-full h-1.5">
        <div className={`${color} h-1.5 rounded-full`} style={{ width: `${n}%` }} />
      </div>
      <span className="text-xs font-medium text-gray-600 w-6">{Math.round(n)}</span>
    </div>
  );
}

// ─── AI Panel ────────────────────────────────────────────────────────────────

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

  const handleRun = () => {
    onRun();
    setOpen(true);
  };

  return (
    <div className="border border-gray-200 rounded-xl overflow-hidden">
      <div className="flex items-center justify-between px-4 py-3 bg-gray-50">
        <div className="flex items-center gap-2">
          <Icon className="w-4 h-4 text-[#1F3864]" />
          <span className="text-sm font-semibold text-gray-800">{title}</span>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={handleRun}
            disabled={loading}
            className="text-xs font-medium px-3 py-1.5 rounded-lg bg-[#1F3864] text-white hover:bg-[#2E75B6] transition-colors disabled:opacity-50"
          >
            {loading ? "Running…" : "Run"}
          </button>
          {result && (
            <button onClick={() => setOpen(v => !v)} className="text-gray-400 hover:text-gray-600">
              {open ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
            </button>
          )}
        </div>
      </div>
      {open && result && (
        <div className="p-4 bg-white text-sm">{children(result)}</div>
      )}
    </div>
  );
}

// ─── Per-TX fraud modal ───────────────────────────────────────────────────────

function TxFraudButton({ txId }: { txId: string }) {
  const [data, setData] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(false);
  const [open, setOpen] = useState(false);

  const run = async () => {
    setLoading(true);
    try {
      const res = await fetch(`/api/v2/fraud/assess/${txId}`, { method: "POST" });
      const json = await res.json();
      setData(json);
      setOpen(true);
    } finally {
      setLoading(false);
    }
  };

  const assessment = data?.assessment as Record<string, unknown> | undefined;

  return (
    <>
      <button
        onClick={run}
        disabled={loading}
        className="text-xs text-blue-600 hover:text-blue-800 font-medium disabled:opacity-40"
      >
        {loading ? "…" : "Assess"}
      </button>
      {open && assessment && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" onClick={() => setOpen(false)}>
          <div className="bg-white rounded-xl shadow-xl w-full max-w-lg p-6" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-bold text-gray-900">Fraud Assessment</h3>
              <button onClick={() => setOpen(false)} className="text-gray-400 hover:text-gray-600 text-xl leading-none">×</button>
            </div>
            <div className="space-y-3 text-sm">
              <div className="flex items-center justify-between">
                <span className="text-gray-500">Composite Score</span>
                <span className="font-bold text-lg">{Number(assessment.composite_score ?? 0).toFixed(1)}/100</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-gray-500">Risk Tier</span>
                <Badge status={String(assessment.risk_tier ?? "").toLowerCase() === "critical" ? "flagged" : String(assessment.risk_tier ?? "").toLowerCase() === "high" ? "flagged" : "pending"} />
              </div>
              <div className="flex items-center justify-between">
                <span className="text-gray-500">Recommended Action</span>
                <span className="font-medium">{String(assessment.recommended_action ?? "—")}</span>
              </div>
              {Array.isArray(assessment.triggered_rules) && assessment.triggered_rules.length > 0 && (
                <div>
                  <p className="text-gray-500 mb-1">Triggered Rules</p>
                  <div className="flex flex-wrap gap-1">
                    {(assessment.triggered_rules as string[]).map(r => (
                      <span key={r} className="bg-red-50 text-red-700 border border-red-200 px-2 py-0.5 rounded text-xs">{r}</span>
                    ))}
                  </div>
                </div>
              )}
              {!!assessment.explanation && (
                <p className="text-gray-600 bg-gray-50 p-3 rounded-lg">{String(assessment.explanation)}</p>
              )}
            </div>
          </div>
        </div>
      )}
    </>
  );
}

// ─── Main page ────────────────────────────────────────────────────────────────

export default function GrantDetailPage({ params }: { params: { id: string } }) {
  const { id } = params;
  const { data, isLoading } = useSWR(`/api/grants/${id}`, fetcher);

  const [fraudResult, setFraudResult]       = useState<object | null>(null);
  const [fraudLoading, setFraudLoading]     = useState(false);
  const [anomalyResult, setAnomalyResult]   = useState<object | null>(null);
  const [anomalyLoading, setAnomalyLoading] = useState(false);
  const [compResult, setCompResult]         = useState<object | null>(null);
  const [compLoading, setCompLoading]       = useState(false);
  const [riskResult, setRiskResult]         = useState<object | null>(null);
  const [riskLoading, setRiskLoading]       = useState(false);

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
      const res = await fetch(`/api/v2/anomaly/detect/${id}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
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
      <div className="space-y-4 animate-pulse">
        <div className="h-8 w-48 bg-gray-200 rounded" />
        <div className="h-32 bg-gray-100 rounded-xl" />
        <div className="h-64 bg-gray-100 rounded-xl" />
      </div>
    );
  }

  if (!data?.grant) {
    return (
      <div className="text-center py-16">
        <p className="text-gray-500">Grant not found.</p>
        <Link href="/grants" className="text-blue-600 hover:underline text-sm mt-2 block">← Back to grants</Link>
      </div>
    );
  }

  const { grant, transactions = [], stats } = data as {
    grant: Record<string, unknown>;
    transactions: Record<string, unknown>[];
    stats: Record<string, unknown>;
  };

  const compliance = Number(grant.compliance_score ?? 0);
  const compColor = compliance >= 80 ? "text-green-600" : compliance >= 60 ? "text-amber-600" : "text-red-600";

  return (
    <div className="space-y-6">
      {/* Back + header */}
      <div>
        <Link href="/grants" className="flex items-center gap-1 text-sm text-gray-500 hover:text-gray-700 mb-3">
          <ArrowLeft className="w-4 h-4" /> Back to Grants
        </Link>
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">{String(grant.award_number)}</h1>
            <p className="text-sm text-gray-500 mt-0.5">{String(grant.agency)}</p>
          </div>
          <Badge status={String(grant.status)} />
        </div>
      </div>

      {/* Stats row */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {[
          { label: "Total Award",      value: `$${Number(grant.total_amount).toLocaleString()}`,  icon: FileText,       color: "bg-blue-50 border-blue-200" },
          { label: "Compliance Score", value: `${compliance.toFixed(0)}/100`,                     icon: CheckCircle2,   color: "bg-green-50 border-green-200", valueColor: compColor },
          { label: "Flagged Tx",       value: String(stats?.flagged ?? 0),                        icon: AlertTriangle,  color: "bg-red-50 border-red-200" },
          { label: "Total Spend",      value: `$${Number(stats?.total_spend ?? 0).toLocaleString()}`, icon: Clock,      color: "bg-gray-50 border-gray-200" },
        ].map(({ label, value, icon: Icon, color, valueColor }) => (
          <div key={label} className={`rounded-xl border p-4 ${color}`}>
            <div className="flex items-center gap-2 mb-2">
              <Icon className="w-4 h-4 text-gray-500" />
              <span className="text-xs text-gray-500 font-medium">{label}</span>
            </div>
            <p className={`text-xl font-bold ${valueColor || "text-gray-900"}`}>{value}</p>
          </div>
        ))}
      </div>

      {/* Main grid */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        {/* Transactions (2/3 width) */}
        <div className="xl:col-span-2 bg-white rounded-xl border border-gray-200">
          <div className="px-5 py-4 border-b border-gray-100 flex items-center justify-between">
            <h2 className="font-semibold text-gray-900">Transactions</h2>
            <span className="text-xs text-gray-400">{transactions.length} total</span>
          </div>

          {transactions.length === 0 ? (
            <div className="text-center py-12 text-gray-400">
              <FileText className="w-8 h-8 mx-auto mb-2" />
              <p className="text-sm">No transactions yet</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-100 bg-gray-50">
                    <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase">Date</th>
                    <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase">Invoice</th>
                    <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase">Vendor</th>
                    <th className="text-right px-4 py-3 text-xs font-medium text-gray-500 uppercase">Amount</th>
                    <th className="text-center px-4 py-3 text-xs font-medium text-gray-500 uppercase">Risk</th>
                    <th className="text-center px-4 py-3 text-xs font-medium text-gray-500 uppercase">Status</th>
                    <th className="px-4 py-3" />
                  </tr>
                </thead>
                <tbody>
                  {transactions.map((tx) => (
                    <tr key={String(tx.id)} className="border-b border-gray-50 hover:bg-gray-50 transition-colors">
                      <td className="px-4 py-3 text-gray-600">{String(tx.tx_date ?? "").slice(0, 10)}</td>
                      <td className="px-4 py-3 font-mono text-xs text-gray-700">{String(tx.invoice_ref)}</td>
                      <td className="px-4 py-3 text-gray-700 max-w-[140px] truncate">{String(tx.vendor_name ?? "—")}</td>
                      <td className="px-4 py-3 text-right font-medium text-gray-900">
                        ${Number(tx.amount).toLocaleString(undefined, { minimumFractionDigits: 2 })}
                      </td>
                      <td className="px-4 py-3">
                        <RiskBar score={tx.risk_score as number | null} />
                      </td>
                      <td className="px-4 py-3 text-center">
                        <Badge status={String(tx.flag_status)} />
                      </td>
                      <td className="px-4 py-3 text-center">
                        <TxFraudButton txId={String(tx.id)} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* AI Intelligence (1/3 width) */}
        <div className="space-y-3">
          <h2 className="font-semibold text-gray-900 flex items-center gap-2">
            <Zap className="w-4 h-4 text-[#1F3864]" /> AI Intelligence
          </h2>

          <AISection title="Risk Prediction" icon={TrendingUp} onRun={runRisk} result={riskResult} loading={riskLoading}>
            {(d) => {
              const r = d as Record<string, unknown>;
              return (
                <div className="space-y-2">
                  <div className="flex justify-between"><span className="text-gray-500">Predicted Risk</span><span className="font-bold">{Number(r.predicted_risk_score ?? 0).toFixed(1)}/100</span></div>
                  <div className="flex justify-between"><span className="text-gray-500">Trend</span><span className="font-medium capitalize">{String(r.trend ?? "—")}</span></div>
                  <div className="flex justify-between"><span className="text-gray-500">Confidence</span><span className="font-medium">{(Number(r.confidence ?? 0) * 100).toFixed(0)}%</span></div>
                  {Array.isArray(r.risk_drivers) && r.risk_drivers.length > 0 && (
                    <div><p className="text-gray-500 mb-1">Top Drivers</p>
                      {(r.risk_drivers as { factor: string; contribution: number }[]).slice(0, 3).map((drv) => (
                        <p key={drv.factor} className="text-xs bg-amber-50 text-amber-800 p-1.5 rounded mb-1">
                          {drv.factor.replace(/_/g, " ")} <span className="font-semibold">(+{drv.contribution})</span>
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
                <div className="space-y-2">
                  <div className="flex justify-between"><span className="text-gray-500">Queued</span><span className="font-bold">{String(r.transactions_queued ?? 0)}</span></div>
                  <p className="text-xs text-gray-500">{String(r.message ?? "")}</p>
                </div>
              );
            }}
          </AISection>

          <AISection title="Anomaly Detection" icon={Activity} onRun={runAnomaly} result={anomalyResult} loading={anomalyLoading}>
            {(d) => {
              const r = d as Record<string, unknown>;
              const alerts = (r.alerts ?? []) as Record<string, unknown>[];
              return (
                <div className="space-y-2">
                  <div className="flex justify-between"><span className="text-gray-500">Alerts</span><span className="font-bold">{String(r.alert_count ?? 0)}</span></div>
                  {alerts.slice(0, 5).map((a, i) => (
                    <div key={i} className="bg-amber-50 border border-amber-200 rounded-lg p-2 text-xs">
                      <p className="font-medium text-amber-800">{String(a.type ?? "")}</p>
                      <p className="text-amber-700 mt-0.5">{String(a.description ?? "")}</p>
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
                <div className="space-y-2">
                  <div className="flex justify-between"><span className="text-gray-500">Violations</span><span className="font-bold">{String(r.violation_count ?? 0)}</span></div>
                  <div className="flex justify-between"><span className="text-gray-500">Auto-CAPs</span><span className="font-medium">{String(r.auto_caps_created ?? 0)}</span></div>
                  {violations.slice(0, 4).map((v, i) => (
                    <div key={i} className="bg-red-50 border border-red-100 rounded-lg p-2 text-xs">
                      <p className="font-medium text-red-800">{String(v.title ?? v.rule_id ?? "")}</p>
                      <p className="text-gray-500 mt-0.5">{String(v.cfr_citation ?? "")} {String(v.severity ?? "")}</p>
                      <p className="text-red-700 mt-0.5">{String(v.recommended_remediation ?? "")}</p>
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
