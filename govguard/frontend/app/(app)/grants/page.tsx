"use client";
import useSWR from "swr";
import Link from "next/link";
import { useState } from "react";
import { Plus, FileText, ChevronRight, CheckCircle2, Clock } from "lucide-react";
import { useForm } from "react-hook-form";

const fetcher = (url: string) => fetch(url).then(r => r.json());

const STATUS_CONFIG: Record<string, { badgeClass: string; icon: React.ElementType }> = {
  draft:  { badgeClass: "qg-badge-muted",   icon: Clock },
  active: { badgeClass: "qg-badge-low",     icon: CheckCircle2 },
  closed: { badgeClass: "qg-badge-gold",    icon: CheckCircle2 },
};

export default function GrantsPage() {
  const { data, isLoading, mutate } = useSWR("/api/v1/grants", fetcher);
  const [showForm, setShowForm] = useState(false);
  const [isCreating, setIsCreating] = useState(false);
  const { register, handleSubmit, reset } = useForm();

  const grants = data?.grants || [];

  const onSubmit = async (formData: Record<string, unknown>) => {
    setIsCreating(true);
    try {
      await fetch("/api/v1/grants", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...formData, total_amount: Number(formData.total_amount), budget_json: {} }),
      });
      await mutate();
      setShowForm(false);
      reset();
    } finally { setIsCreating(false); }
  };

  return (
    <div className="qg-animate-in" style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <div>
          <span className="qg-section-label-badge" style={{ marginBottom: 8, display: "inline-block" }}>Portfolio</span>
          <h1 className="qg-title" style={{ marginTop: 8 }}>Grants</h1>
          <p className="qg-subtitle" style={{ marginTop: 4 }}>Manage your federal award portfolio</p>
        </div>
        <button
          onClick={() => setShowForm(!showForm)}
          className="qg-btn qg-btn-primary qg-btn-sm"
        >
          <Plus size={13} /> New Grant
        </button>
      </div>

      {showForm && (
        <div className="qg-card qg-animate-in">
          <h3 style={{ fontSize: 13, fontWeight: 700, color: "var(--qg-text-1)", marginBottom: 16 }}>Create New Grant</h3>
          <form onSubmit={handleSubmit(onSubmit)} style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
            {[
              { name: "award_number",  label: "Award Number",      placeholder: "2024-HUD-001" },
              { name: "agency",        label: "Awarding Agency",   placeholder: "Dept. of Housing & Urban Development" },
              { name: "program_cfda",  label: "CFDA/ALN Number",   placeholder: "14.218" },
              { name: "total_amount",  label: "Total Amount ($)",  placeholder: "500000", type: "number" },
              { name: "period_start",  label: "Period Start",      type: "date" },
              { name: "period_end",    label: "Period End",        type: "date" },
            ].map(({ name, label, placeholder, type }) => (
              <div key={name}>
                <label className="qg-label-text">{label}</label>
                <input
                  {...register(name, { required: true })}
                  type={type || "text"}
                  placeholder={placeholder}
                  className="qg-input"
                />
              </div>
            ))}
            <div style={{ gridColumn: "span 2", display: "flex", gap: 10, paddingTop: 4 }}>
              <button type="submit" disabled={isCreating} className="qg-btn qg-btn-primary qg-btn-sm">
                {isCreating ? "Creating…" : "Create Grant"}
              </button>
              <button
                type="button"
                onClick={() => { setShowForm(false); reset(); }}
                className="qg-btn qg-btn-secondary qg-btn-sm"
              >
                Cancel
              </button>
            </div>
          </form>
        </div>
      )}

      {isLoading ? (
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {[...Array(4)].map((_, i) => (
            <div key={i} style={{ height: 72, background: "var(--qg-surface)", borderRadius: "var(--qg-radius-xl)", border: "1px solid var(--qg-border)", opacity: 0.6 }} />
          ))}
        </div>
      ) : grants.length === 0 ? (
        <div className="qg-card" style={{ textAlign: "center", padding: "64px 24px" }}>
          <FileText size={36} color="var(--qg-text-4)" style={{ margin: "0 auto 12px", display: "block" }} />
          <p style={{ fontWeight: 700, color: "var(--qg-text-1)", marginBottom: 6, fontSize: 14 }}>No grants yet</p>
          <p style={{ fontSize: 12, color: "var(--qg-text-4)", marginBottom: 16 }}>Create your first grant to start tracking compliance.</p>
          <button onClick={() => setShowForm(true)} className="qg-btn qg-btn-primary qg-btn-sm">
            Create First Grant
          </button>
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {grants.map((g: Record<string, unknown>) => {
            const st = String(g.status || "draft");
            const cfg = STATUS_CONFIG[st] || STATUS_CONFIG.draft;
            const StatusIcon = cfg.icon;
            return (
              <Link
                key={String(g.id)}
                href={`/grants/${g.id}`}
                className="qg-card qg-card-clickable"
                style={{ display: "flex", alignItems: "center", gap: 16, padding: "16px 20px", textDecoration: "none" }}
              >
                <div className="qg-card-icon" style={{ width: 40, height: 40 }}>
                  <FileText size={15} />
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <p style={{ fontWeight: 700, color: "var(--qg-text-1)", fontSize: 13 }}>{String(g.award_number)}</p>
                  <p style={{ fontSize: 11, color: "var(--qg-text-4)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", marginTop: 2 }}>
                    {String(g.agency)}
                  </p>
                </div>
                <div style={{ textAlign: "right" }}>
                  <p style={{ fontSize: 13, fontWeight: 700, color: "var(--qg-text-1)" }}>
                    ${Number(g.total_amount).toLocaleString()}
                  </p>
                  <span className={`qg-badge ${cfg.badgeClass}`} style={{ marginTop: 4, display: "inline-flex", alignItems: "center", gap: 4 }}>
                    <StatusIcon size={9} /> {st}
                  </span>
                </div>
                <ChevronRight size={15} color="var(--qg-text-4)" />
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
}
