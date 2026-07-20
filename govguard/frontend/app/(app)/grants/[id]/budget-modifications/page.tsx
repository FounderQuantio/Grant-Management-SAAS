"use client";
import { useParams } from "next/navigation";
import { useState } from "react";
import { useBudgetModifications } from "@/lib/hooks/useBudgetModifications";
import { GrantTabs } from "@/components/grants/GrantTabs";
import { api, APIError } from "@/lib/api";
import { CheckCircle2, XCircle, Clock, PlusCircle } from "lucide-react";

const STATUS_CONFIG: Record<string, { color: string; bg: string; border: string; label: string }> = {
  pending:      { color: "var(--qg-yellow)", bg: "var(--qg-yellow-bg)", border: "var(--qg-yellow-border)", label: "Pending Approval" },
  auto_applied: { color: "var(--qg-green)",  bg: "var(--qg-green-bg)",  border: "var(--qg-green-border)",  label: "Auto-Applied" },
  approved:     { color: "var(--qg-green)",  bg: "var(--qg-green-bg)",  border: "var(--qg-green-border)",  label: "Approved" },
  rejected:     { color: "var(--qg-red)",    bg: "var(--qg-red-bg)",    border: "var(--qg-red-border)",    label: "Rejected" },
};

function RequestModificationForm({ grantId, onCreated }: { grantId: string; onCreated: () => void }) {
  const [open, setOpen] = useState(false);
  const [category, setCategory] = useState("");
  const [newAmount, setNewAmount] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<{ requires_prior_approval: boolean; cumulative_pct_of_total: number } | null>(null);

  const submit = async () => {
    setSaving(true);
    setError(null);
    setResult(null);
    try {
      const res = await api.post<{ requires_prior_approval: boolean; cumulative_pct_of_total: number }>(
        `/api/v1/budget-modifications/grants/${grantId}`,
        { category, new_amount: parseFloat(newAmount) }
      );
      setResult(res);
      setCategory("");
      setNewAmount("");
      onCreated();
    } catch (e) {
      setError(e instanceof APIError ? e.message : "Request failed");
    } finally {
      setSaving(false);
    }
  };

  if (!open) {
    return (
      <button onClick={() => setOpen(true)} className="qg-btn qg-btn-primary qg-btn-sm" style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
        <PlusCircle size={13} /> Request Modification
      </button>
    );
  }

  return (
    <div className="qg-card" style={{ padding: 16, marginBottom: 20 }}>
      <h3 style={{ fontSize: 12, fontWeight: 700, color: "var(--qg-text-1)", marginBottom: 12 }}>
        Request Budget Modification
      </h3>
      <p style={{ fontSize: 11, color: "var(--qg-text-4)", marginBottom: 14 }}>
        2 CFR §200.308(e)(3) — cumulative transfers ≥10% of the total approved budget require prior written approval before implementation.
      </p>
      <div style={{ display: "flex", gap: 10, marginBottom: 14, flexWrap: "wrap" }}>
        <div style={{ flex: 1, minWidth: 160 }}>
          <label style={{ fontSize: 11, fontWeight: 600, color: "var(--qg-text-3)", display: "block", marginBottom: 6 }}>Cost Category</label>
          <input
            value={category}
            onChange={(e) => setCategory(e.target.value)}
            placeholder="e.g. equipment"
            style={{ width: "100%", fontSize: 12, padding: "8px 10px", border: "1px solid var(--qg-border)", borderRadius: "var(--qg-radius-md)", background: "var(--qg-surface)", color: "var(--qg-text-1)" }}
          />
        </div>
        <div style={{ flex: 1, minWidth: 160 }}>
          <label style={{ fontSize: 11, fontWeight: 600, color: "var(--qg-text-3)", display: "block", marginBottom: 6 }}>New Amount ($)</label>
          <input
            type="number"
            value={newAmount}
            onChange={(e) => setNewAmount(e.target.value)}
            placeholder="0.00"
            style={{ width: "100%", fontSize: 12, padding: "8px 10px", border: "1px solid var(--qg-border)", borderRadius: "var(--qg-radius-md)", background: "var(--qg-surface)", color: "var(--qg-text-1)" }}
          />
        </div>
      </div>

      {error && (
        <p style={{ fontSize: 11, color: "var(--qg-red)", background: "var(--qg-red-bg)", border: "1px solid var(--qg-red-border)", borderRadius: "var(--qg-radius-md)", padding: "8px 12px", marginBottom: 12 }}>
          {error}
        </p>
      )}
      {result && (
        <p style={{
          fontSize: 11, borderRadius: "var(--qg-radius-md)", padding: "8px 12px", marginBottom: 12,
          color: result.requires_prior_approval ? "var(--qg-yellow)" : "var(--qg-green)",
          background: result.requires_prior_approval ? "var(--qg-yellow-bg)" : "var(--qg-green-bg)",
          border: `1px solid ${result.requires_prior_approval ? "var(--qg-yellow-border)" : "var(--qg-green-border)"}`,
        }}>
          Cumulative modification: {result.cumulative_pct_of_total.toFixed(1)}% of total budget —{" "}
          {result.requires_prior_approval ? "held pending prior approval." : "auto-applied (under 10% threshold)."}
        </p>
      )}

      <div style={{ display: "flex", justifyContent: "flex-end", gap: 8 }}>
        <button onClick={() => setOpen(false)} className="qg-btn qg-btn-secondary qg-btn-sm">Close</button>
        <button
          onClick={submit}
          disabled={saving || !category || !newAmount}
          className="qg-btn qg-btn-primary qg-btn-sm"
        >
          {saving ? "Submitting…" : "Submit Request"}
        </button>
      </div>
    </div>
  );
}

function ReviewButtons({ modId, onReviewed }: { modId: string; onReviewed: () => void }) {
  const [saving, setSaving] = useState<"approve" | "reject" | null>(null);
  const [error, setError] = useState<string | null>(null);

  const review = async (approve: boolean) => {
    setSaving(approve ? "approve" : "reject");
    setError(null);
    try {
      await api.patch(`/api/v1/budget-modifications/${modId}/review`, { approve });
      onReviewed();
    } catch (e) {
      setError(e instanceof APIError ? e.message : "Review failed");
    } finally {
      setSaving(null);
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 4 }}>
      <div style={{ display: "flex", gap: 6 }}>
        <button onClick={() => review(true)} disabled={!!saving} className="qg-badge qg-badge-low" style={{ cursor: "pointer", border: "1px solid var(--qg-green-border)" }}>
          {saving === "approve" ? "…" : "Approve"}
        </button>
        <button onClick={() => review(false)} disabled={!!saving} className="qg-badge qg-badge-critical" style={{ cursor: "pointer", border: "1px solid var(--qg-red-border)" }}>
          {saving === "reject" ? "…" : "Reject"}
        </button>
      </div>
      {error && <span style={{ fontSize: 10, color: "var(--qg-red)" }}>{error}</span>}
    </div>
  );
}

export default function BudgetModificationsPage() {
  const { id: grantId } = useParams<{ id: string }>();
  const { data, isLoading, mutate } = useBudgetModifications(grantId);

  const mods = data?.modifications ?? [];
  const pendingCount = mods.filter((m) => m.status === "pending").length;

  return (
    <div className="qg-animate-in">
      <GrantTabs grantId={grantId} />

      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: 20 }}>
        <div>
          <span className="qg-section-label-badge" style={{ marginBottom: 8, display: "inline-block" }}>Budget</span>
          <h1 className="qg-title" style={{ marginTop: 8 }}>Budget Modifications</h1>
          <p className="qg-subtitle" style={{ marginTop: 4 }}>2 CFR §200.308(e)(3) prior-approval workflow</p>
        </div>
        <RequestModificationForm grantId={grantId} onCreated={() => mutate()} />
      </div>

      {data && (
        <div className="qg-grid-3" style={{ marginBottom: 24 }}>
          <div className="qg-card" style={{ borderColor: "var(--qg-yellow-border)", display: "flex", alignItems: "center", gap: 14, padding: 16 }}>
            <Clock size={28} color="var(--qg-yellow)" />
            <div>
              <p style={{ fontSize: 22, fontWeight: 800, color: "var(--qg-yellow)" }}>{pendingCount}</p>
              <p style={{ fontSize: 11, color: "var(--qg-yellow)", opacity: 0.7 }}>Pending Approval</p>
            </div>
          </div>
          <div className="qg-card" style={{ borderColor: "var(--qg-green-border)", display: "flex", alignItems: "center", gap: 14, padding: 16 }}>
            <CheckCircle2 size={28} color="var(--qg-green)" />
            <div>
              <p style={{ fontSize: 22, fontWeight: 800, color: "var(--qg-green)" }}>{mods.filter((m) => m.status === "approved" || m.status === "auto_applied").length}</p>
              <p style={{ fontSize: 11, color: "var(--qg-green)", opacity: 0.7 }}>Applied</p>
            </div>
          </div>
          <div className="qg-card" style={{ borderColor: "var(--qg-red-border)", display: "flex", alignItems: "center", gap: 14, padding: 16 }}>
            <XCircle size={28} color="var(--qg-red)" />
            <div>
              <p style={{ fontSize: 22, fontWeight: 800, color: "var(--qg-red)" }}>{mods.filter((m) => m.status === "rejected").length}</p>
              <p style={{ fontSize: 11, color: "var(--qg-red)", opacity: 0.7 }}>Rejected</p>
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
      ) : mods.length === 0 ? (
        <div className="qg-card" style={{ textAlign: "center", padding: "48px 0", color: "var(--qg-text-4)" }}>
          <p style={{ fontSize: 12 }}>No budget modifications requested yet.</p>
        </div>
      ) : (
        <div className="qg-card" style={{ padding: 0, overflow: "hidden" }}>
          <div style={{ overflowX: "auto" }}>
            <table className="qg-table">
              <thead>
                <tr>
                  <th>Category</th>
                  <th style={{ textAlign: "right" }}>Old Amount</th>
                  <th style={{ textAlign: "right" }}>New Amount</th>
                  <th style={{ textAlign: "right" }}>Cumulative %</th>
                  <th style={{ textAlign: "center" }}>Status</th>
                  <th>Requested</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {mods.map((m) => {
                  const cfg = STATUS_CONFIG[m.status] || STATUS_CONFIG.pending;
                  return (
                    <tr key={m.id}>
                      <td style={{ fontWeight: 700, fontSize: 12, textTransform: "capitalize" }}>{m.category}</td>
                      <td style={{ textAlign: "right", fontSize: 12 }}>${m.old_amount.toLocaleString()}</td>
                      <td style={{ textAlign: "right", fontSize: 12, fontWeight: 600, color: "var(--qg-text-1)" }}>${m.new_amount.toLocaleString()}</td>
                      <td style={{ textAlign: "right", fontSize: 12 }}>{m.cumulative_pct_of_total.toFixed(1)}%</td>
                      <td style={{ textAlign: "center" }}>
                        <span className="qg-badge" style={{ background: cfg.bg, color: cfg.color, border: `1px solid ${cfg.border}` }}>
                          {cfg.label}
                        </span>
                      </td>
                      <td style={{ fontSize: 12 }}>{new Date(m.created_at).toLocaleDateString()}</td>
                      <td style={{ textAlign: "right" }}>
                        {m.status === "pending" && <ReviewButtons modId={m.id} onReviewed={() => mutate()} />}
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
