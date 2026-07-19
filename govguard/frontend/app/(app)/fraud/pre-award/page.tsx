"use client";
import { useState } from "react";
import { AlertTriangle, CheckCircle2, Shield, Search } from "lucide-react";

interface ScreenResult {
  risk_score: number;
  dnp_match: boolean;
  dedup_matches: { id: string; name: string; risk_score: number }[];
  budget_flags: string[];
  recommendation: string;
}

function getRiskStyle(score: number) {
  if (score >= 70) return { color: "var(--qg-red)",    bg: "var(--qg-red-bg)",    border: "var(--qg-red-border)" };
  if (score >= 40) return { color: "var(--qg-yellow)", bg: "var(--qg-yellow-bg)", border: "var(--qg-yellow-border)" };
  return             { color: "var(--qg-green)",  bg: "var(--qg-green-bg)",  border: "var(--qg-green-border)" };
}

export default function FraudScreenPage() {
  const [result, setResult] = useState<ScreenResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [formData, setFormData] = useState({ applicant_name: "", ein: "", address: "" });

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setError(null);
    try {
      const res = await fetch("/api/v1/fraud/screen", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...formData, budget_json: {} }),
      });
      if (!res.ok) {
        setError(`Screening failed (HTTP ${res.status}). Please try again.`);
        setResult(null);
        return;
      }
      setResult(await res.json());
    } catch {
      setError("Could not reach the screening service. Please try again.");
    } finally { setIsLoading(false); }
  };

  return (
    <div className="qg-animate-in" style={{ maxWidth: 600, display: "flex", flexDirection: "column", gap: 20 }}>
      <div>
        <span className="qg-section-label-badge" style={{ marginBottom: 8, display: "inline-block" }}>Fraud</span>
        <h1 className="qg-title" style={{ marginTop: 8 }}>Pre-Award Fraud Screen</h1>
        <p className="qg-subtitle" style={{ marginTop: 4 }}>Screen applicants before making award decisions</p>
      </div>

      <div className="qg-card">
        <form onSubmit={onSubmit} style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          {[
            { name: "applicant_name", label: "Applicant Organization Name", placeholder: "ABC Nonprofit Inc." },
            { name: "ein",            label: "Employer Identification Number (EIN)", placeholder: "12-3456789" },
            { name: "address",        label: "Primary Address", placeholder: "123 Main St, City, State 00000" },
          ].map(({ name, label, placeholder }) => (
            <div key={name}>
              <label className="qg-label-text">{label}</label>
              <input
                value={(formData as Record<string, string>)[name]}
                onChange={e => setFormData(p => ({ ...p, [name]: e.target.value }))}
                placeholder={placeholder}
                className="qg-input"
                required
              />
            </div>
          ))}
          <button type="submit" disabled={isLoading} className="qg-btn qg-btn-primary" style={{ marginTop: 4 }}>
            {isLoading ? (
              <><Search size={14} className="qg-spin" /> Screening...</>
            ) : (
              <><Shield size={14} /> Run Fraud Screen</>
            )}
          </button>
        </form>
      </div>

      {error && (
        <div className="qg-card" style={{ borderColor: "var(--qg-red-border)", background: "var(--qg-red-bg)" }}>
          <p style={{ fontSize: 12, color: "var(--qg-red)" }}>{error}</p>
        </div>
      )}

      {result && (
        <div className="qg-animate-in" style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          {(() => {
            const rs = getRiskStyle(result.risk_score);
            return (
              <div className="qg-card" style={{ borderColor: rs.border, background: rs.bg }}>
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                  <div>
                    <p style={{ fontSize: 11, color: rs.color, opacity: 0.7, marginBottom: 4 }}>Risk Score</p>
                    <p style={{ fontSize: 36, fontWeight: 900, color: rs.color, letterSpacing: "-1px" }}>
                      {result.risk_score}
                      <span style={{ fontSize: 16, fontWeight: 400, opacity: 0.5 }}>/100</span>
                    </p>
                  </div>
                  <div style={{ textAlign: "right" }}>
                    <p style={{ fontSize: 11, color: rs.color, opacity: 0.7, marginBottom: 4 }}>Recommendation</p>
                    <p style={{ fontWeight: 800, fontSize: 13, color: rs.color }}>
                      {result.recommendation.replace(/_/g, " ")}
                    </p>
                  </div>
                </div>
              </div>
            );
          })()}

          {result.budget_flags.length > 0 && (
            <div className="qg-card" style={{ borderColor: "var(--qg-yellow-border)", background: "var(--qg-yellow-bg)" }}>
              <p style={{ fontSize: 12, fontWeight: 700, color: "var(--qg-yellow)", display: "flex", alignItems: "center", gap: 6, marginBottom: 8 }}>
                <AlertTriangle size={13} /> Budget Flags
              </p>
              {result.budget_flags.map((flag, i) => (
                <p key={i} style={{ fontSize: 12, color: "var(--qg-yellow)", marginBottom: 3 }}>• {flag}</p>
              ))}
            </div>
          )}

          {result.dedup_matches.length > 0 && (
            <div className="qg-card" style={{ borderColor: "var(--qg-red-border)", background: "var(--qg-red-bg)" }}>
              <p style={{ fontSize: 12, fontWeight: 700, color: "var(--qg-red)", marginBottom: 8 }}>
                Duplicate Entity Matches Found
              </p>
              {result.dedup_matches.map(m => (
                <p key={m.id} style={{ fontSize: 12, color: "var(--qg-red)", marginBottom: 3 }}>
                  • {m.name} (Risk: {m.risk_score}/100)
                </p>
              ))}
            </div>
          )}

          {!result.budget_flags.length && !result.dedup_matches.length && (
            <div className="qg-card" style={{ borderColor: "var(--qg-green-border)", display: "flex", alignItems: "center", gap: 10 }}>
              <CheckCircle2 size={18} color="var(--qg-green)" />
              <p style={{ fontSize: 13, color: "var(--qg-green)" }}>
                No flags detected. Standard processing may proceed.
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
