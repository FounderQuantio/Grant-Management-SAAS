"use client";
import useSWR from "swr";
import { Building, Link2, ShieldAlert } from "lucide-react";

const fetcher = (url: string) => fetch(url).then(r => r.json());

interface VendorRow {
  id: string;
  name: string;
  sam_status: string;
  risk_tier: string;
  risk_score: number | null;
  sam_checked_at: string | null;
  created_at: string;
}

interface DupLink {
  id: string;
  source_name: string;
  target_name: string;
  link_type: string;
  confidence: number;
}

const SAM_BADGE: Record<string, string> = {
  clear: "qg-badge-low",
  excluded: "qg-badge-critical",
  unknown: "qg-badge-muted",
};

const RISK_BADGE: Record<string, string> = {
  low: "qg-badge-low",
  medium: "qg-badge-medium",
  high: "qg-badge-high",
  critical: "qg-badge-critical",
};

export default function VendorsPage() {
  const { data, isLoading } = useSWR<{ vendors: VendorRow[]; total: number; duplicate_links: DupLink[] }>(
    "/api/v1/fraud/vendors",
    fetcher
  );
  const vendors = data?.vendors || [];
  const links = data?.duplicate_links || [];

  return (
    <div className="qg-animate-in" style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      <div>
        <span className="qg-section-label-badge" style={{ marginBottom: 8, display: "inline-block" }}>Fraud</span>
        <h1 className="qg-title" style={{ marginTop: 8 }}>Vendor Directory</h1>
        <p className="qg-subtitle" style={{ marginTop: 4 }}>SAM.gov exclusion status, risk tiering, and duplicate-entity matches</p>
      </div>

      {isLoading ? (
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {[...Array(3)].map((_, i) => (
            <div key={i} style={{ height: 64, background: "var(--qg-surface)", borderRadius: "var(--qg-radius-xl)", border: "1px solid var(--qg-border)", opacity: 0.6 }} />
          ))}
        </div>
      ) : vendors.length === 0 ? (
        <div className="qg-card" style={{ textAlign: "center", padding: "64px 24px" }}>
          <Building size={36} color="var(--qg-text-4)" style={{ margin: "0 auto 12px", display: "block" }} />
          <p style={{ fontWeight: 700, color: "var(--qg-text-1)", marginBottom: 6, fontSize: 14 }}>No vendors on file</p>
        </div>
      ) : (
        <div className="qg-card" style={{ padding: 0, overflow: "hidden" }}>
          <div style={{ overflowX: "auto" }}>
            <table className="qg-table">
              <thead>
                <tr>
                  <th>Vendor</th>
                  <th style={{ textAlign: "center" }}>SAM Status</th>
                  <th style={{ textAlign: "center" }}>Risk Tier</th>
                  <th style={{ textAlign: "center" }}>Risk Score</th>
                  <th>SAM Last Checked</th>
                </tr>
              </thead>
              <tbody>
                {vendors.map((v) => (
                  <tr key={v.id}>
                    <td style={{ fontWeight: 700, color: "var(--qg-text-1)", fontSize: 12 }}>{v.name}</td>
                    <td style={{ textAlign: "center" }}>
                      <span className={`qg-badge ${SAM_BADGE[v.sam_status] || "qg-badge-muted"}`} style={{ textTransform: "capitalize" }}>
                        {v.sam_status}
                      </span>
                    </td>
                    <td style={{ textAlign: "center" }}>
                      <span className={`qg-badge ${RISK_BADGE[v.risk_tier] || "qg-badge-muted"}`} style={{ textTransform: "capitalize" }}>
                        {v.risk_tier}
                      </span>
                    </td>
                    <td style={{ textAlign: "center", fontSize: 12, fontWeight: 600 }}>
                      {v.risk_score !== null ? v.risk_score.toFixed(0) : "—"}
                    </td>
                    <td style={{ fontSize: 11, color: "var(--qg-text-4)" }}>
                      {v.sam_checked_at ? new Date(v.sam_checked_at).toLocaleDateString() : "Not checked"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <div>
        <h2 style={{ fontSize: 13, fontWeight: 700, color: "var(--qg-text-1)", display: "flex", alignItems: "center", gap: 7, marginBottom: 10 }}>
          <Link2 size={13} color="var(--qg-gold)" /> Duplicate Entity Matches
        </h2>
        {links.length === 0 ? (
          <div className="qg-card" style={{ display: "flex", alignItems: "center", gap: 10, padding: 16 }}>
            <ShieldAlert size={16} color="var(--qg-text-4)" />
            <p style={{ fontSize: 12, color: "var(--qg-text-4)" }}>No duplicate or linked vendor entities detected.</p>
          </div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {links.map((l) => (
              <div key={l.id} className="qg-card" style={{ borderColor: "var(--qg-red-border)", display: "flex", alignItems: "center", justifyContent: "space-between", padding: "12px 16px" }}>
                <div style={{ fontSize: 12, color: "var(--qg-text-1)" }}>
                  <strong>{l.source_name}</strong> ↔ <strong>{l.target_name}</strong>
                  <span style={{ color: "var(--qg-text-4)", marginLeft: 8, textTransform: "capitalize" }}>({l.link_type.replace(/_/g, " ")})</span>
                </div>
                <span className="qg-badge qg-badge-critical">{(l.confidence * 100).toFixed(0)}% match</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
