"use client";
import useSWR from "swr";
import { Building2, Users, FileText, ShieldCheck } from "lucide-react";

const fetcher = (url: string) => fetch(url).then(r => r.json());

interface TenantRow {
  id: string;
  name: string;
  tier: number;
  plan: string;
  fedramp_scope: boolean;
  modules_enabled: string[];
  user_count: number;
  grant_count: number;
  created_at: string;
}

const TIER_LABEL: Record<number, string> = { 1: "Starter", 2: "Standard", 3: "Enterprise" };

export default function AdminTenantsPage() {
  const { data, isLoading } = useSWR<{ tenants: TenantRow[]; total: number }>("/api/v1/tenants", fetcher);
  const tenants = data?.tenants || [];

  return (
    <div className="qg-animate-in" style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      <div>
        <span className="qg-section-label-badge" style={{ marginBottom: 8, display: "inline-block" }}>Admin</span>
        <h1 className="qg-title" style={{ marginTop: 8 }}>Tenant Management</h1>
        <p className="qg-subtitle" style={{ marginTop: 4 }}>Platform-wide view of all agencies and organizations on GovGuard™</p>
      </div>

      {isLoading ? (
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {[...Array(3)].map((_, i) => (
            <div key={i} style={{ height: 64, background: "var(--qg-surface)", borderRadius: "var(--qg-radius-xl)", border: "1px solid var(--qg-border)", opacity: 0.6 }} />
          ))}
        </div>
      ) : tenants.length === 0 ? (
        <div className="qg-card" style={{ textAlign: "center", padding: "64px 24px" }}>
          <Building2 size={36} color="var(--qg-text-4)" style={{ margin: "0 auto 12px", display: "block" }} />
          <p style={{ fontWeight: 700, color: "var(--qg-text-1)", marginBottom: 6, fontSize: 14 }}>No tenants provisioned</p>
        </div>
      ) : (
        <div className="qg-card" style={{ padding: 0, overflow: "hidden" }}>
          <div style={{ overflowX: "auto" }}>
            <table className="qg-table">
              <thead>
                <tr>
                  <th>Tenant</th>
                  <th>Tier</th>
                  <th>Plan</th>
                  <th style={{ textAlign: "center" }}>FedRAMP Scope</th>
                  <th>Modules Enabled</th>
                  <th style={{ textAlign: "center" }}>Users</th>
                  <th style={{ textAlign: "center" }}>Grants</th>
                </tr>
              </thead>
              <tbody>
                {tenants.map((t) => (
                  <tr key={t.id}>
                    <td style={{ fontWeight: 700, color: "var(--qg-text-1)", fontSize: 12 }}>{t.name}</td>
                    <td style={{ fontSize: 12 }}>{TIER_LABEL[t.tier] || t.tier}</td>
                    <td style={{ fontSize: 12, textTransform: "capitalize" }}>{t.plan}</td>
                    <td style={{ textAlign: "center" }}>
                      {t.fedramp_scope ? (
                        <span className="qg-badge qg-badge-low" style={{ display: "inline-flex", alignItems: "center", gap: 4 }}>
                          <ShieldCheck size={10} /> In scope
                        </span>
                      ) : (
                        <span className="qg-badge qg-badge-muted">Not scoped</span>
                      )}
                    </td>
                    <td style={{ fontSize: 11, color: "var(--qg-text-4)" }}>
                      {(t.modules_enabled || []).join(", ")}
                    </td>
                    <td style={{ textAlign: "center", fontSize: 12 }}>
                      <span style={{ display: "inline-flex", alignItems: "center", gap: 4 }}>
                        <Users size={11} color="var(--qg-text-4)" /> {t.user_count}
                      </span>
                    </td>
                    <td style={{ textAlign: "center", fontSize: 12 }}>
                      <span style={{ display: "inline-flex", alignItems: "center", gap: 4 }}>
                        <FileText size={11} color="var(--qg-text-4)" /> {t.grant_count}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
