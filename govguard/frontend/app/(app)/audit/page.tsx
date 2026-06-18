"use client";
import useSWR from "swr";
import { useState } from "react";
import { ClipboardCheck, Plus, Calendar, AlertTriangle } from "lucide-react";

const fetcher = (url: string) => fetch(url).then(r => r.json());

export default function AuditPage() {
  const { data, mutate } = useSWR("/api/v1/audit/cap", fetcher);
  const [showForm, setShowForm] = useState(false);
  const [formData, setFormData] = useState({ response_text: "", due_date: "", finding_id: "" });
  const [isCreating, setIsCreating] = useState(false);

  const caps = data?.caps || [];
  const today = new Date();

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsCreating(true);
    try {
      await fetch("/api/v1/audit/cap", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(formData),
      });
      await mutate();
      setShowForm(false);
    } finally { setIsCreating(false); }
  };

  const getDaysLeft = (due: string) => {
    const d = new Date(due);
    return Math.ceil((d.getTime() - today.getTime()) / (1000 * 60 * 60 * 24));
  };

  return (
    <div className="qg-animate-in" style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <div>
          <span className="qg-section-label-badge" style={{ marginBottom: 8, display: "inline-block" }}>Audit</span>
          <h1 className="qg-title" style={{ marginTop: 8 }}>Audit & CAP Workspace</h1>
          <p className="qg-subtitle" style={{ marginTop: 4 }}>Corrective Action Plans & evidence management</p>
        </div>
        <button onClick={() => setShowForm(!showForm)} className="qg-btn qg-btn-primary qg-btn-sm">
          <Plus size={13} /> New CAP
        </button>
      </div>

      {showForm && (
        <div className="qg-card qg-animate-in">
          <h3 style={{ fontSize: 13, fontWeight: 700, color: "var(--qg-text-1)", marginBottom: 16 }}>Create Corrective Action Plan</h3>
          <form onSubmit={onSubmit} style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            <div>
              <label className="qg-label-text">Response / Corrective Action</label>
              <textarea
                rows={4}
                value={formData.response_text}
                onChange={e => setFormData(p => ({ ...p, response_text: e.target.value }))}
                className="qg-input"
                style={{ resize: "vertical" }}
                placeholder="Describe the corrective action and responsible party..."
                required
              />
            </div>
            <div>
              <label className="qg-label-text">Target Completion Date</label>
              <input
                type="date"
                value={formData.due_date}
                onChange={e => setFormData(p => ({ ...p, due_date: e.target.value }))}
                className="qg-input"
                style={{ width: "auto" }}
                required
              />
            </div>
            <div style={{ display: "flex", gap: 10 }}>
              <button type="submit" disabled={isCreating} className="qg-btn qg-btn-primary qg-btn-sm">
                {isCreating ? "Saving…" : "Create CAP"}
              </button>
              <button type="button" onClick={() => setShowForm(false)} className="qg-btn qg-btn-secondary qg-btn-sm">
                Cancel
              </button>
            </div>
          </form>
        </div>
      )}

      {caps.length === 0 ? (
        <div className="qg-card" style={{ textAlign: "center", padding: "64px 24px" }}>
          <ClipboardCheck size={36} color="var(--qg-text-4)" style={{ margin: "0 auto 12px", display: "block" }} />
          <p style={{ fontWeight: 700, color: "var(--qg-text-1)", marginBottom: 6, fontSize: 14 }}>No corrective action plans</p>
          <p style={{ fontSize: 12, color: "var(--qg-text-4)" }}>Create CAPs to track remediation of audit findings.</p>
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {caps.map((cap: Record<string, unknown>) => {
            const daysLeft = getDaysLeft(String(cap.due_date));
            const isOverdue = daysLeft < 0;
            const isUrgent = daysLeft >= 0 && daysLeft <= 30;
            const borderColor = isOverdue ? "var(--qg-red-border)" : isUrgent ? "var(--qg-orange-border)" : "var(--qg-border)";
            return (
              <div key={String(cap.id)} className="qg-card" style={{ borderColor, padding: "16px 20px" }}>
                <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between" }}>
                  <div style={{ flex: 1 }}>
                    <p style={{ fontSize: 13, fontWeight: 500, color: "var(--qg-text-1)", display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical", overflow: "hidden" }}>
                      {String(cap.response_text)}
                    </p>
                    <div style={{ display: "flex", alignItems: "center", gap: 16, marginTop: 8 }}>
                      <span style={{ display: "flex", alignItems: "center", gap: 5, fontSize: 11, color: "var(--qg-text-4)" }}>
                        <Calendar size={11} /> Due: {String(cap.due_date)}
                      </span>
                      {isOverdue ? (
                        <span style={{ display: "flex", alignItems: "center", gap: 4, fontSize: 11, color: "var(--qg-red)", fontWeight: 600 }}>
                          <AlertTriangle size={11} /> OVERDUE by {Math.abs(daysLeft)} days
                        </span>
                      ) : (
                        <span style={{ fontSize: 11, color: isUrgent ? "var(--qg-orange)" : "var(--qg-text-4)", fontWeight: isUrgent ? 600 : 400 }}>
                          {daysLeft} days remaining
                        </span>
                      )}
                    </div>
                  </div>
                  <span className={`qg-badge ${
                    cap.status === "closed" ? "qg-badge-low" :
                    cap.status === "open"   ? "qg-badge-medium" :
                    "qg-badge-gold"
                  }`} style={{ textTransform: "capitalize", marginLeft: 12 }}>
                    {String(cap.status)}
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
