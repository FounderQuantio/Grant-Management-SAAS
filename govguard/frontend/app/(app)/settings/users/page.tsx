"use client";
import useSWR from "swr";
import { UserCircle2, ShieldCheck } from "lucide-react";

const fetcher = (url: string) => fetch(url).then(r => r.json());

interface UserRow {
  id: string;
  display_name: string;
  role: string;
  mfa_enabled: boolean;
  is_active: boolean;
  last_login: string | null;
  created_at: string;
}

const ROLE_BADGE: Record<string, string> = {
  system_admin: "qg-badge-critical",
  agency_officer: "qg-badge-high",
  compliance_officer: "qg-badge-gold",
  finance_manager: "qg-badge-medium",
  finance_staff: "qg-badge-muted",
  auditor: "qg-badge-medium",
  equity_analyst: "qg-badge-low",
};

export default function UsersPage() {
  const { data, isLoading } = useSWR<{ users: UserRow[]; total: number }>("/api/v1/users", fetcher);
  const users = data?.users || [];

  return (
    <div className="qg-animate-in" style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      <div>
        <span className="qg-section-label-badge" style={{ marginBottom: 8, display: "inline-block" }}>Settings</span>
        <h1 className="qg-title" style={{ marginTop: 8 }}>Users</h1>
        <p className="qg-subtitle" style={{ marginTop: 4 }}>Team members with access to this tenant's GovGuard™ workspace</p>
      </div>

      {isLoading ? (
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {[...Array(3)].map((_, i) => (
            <div key={i} style={{ height: 64, background: "var(--qg-surface)", borderRadius: "var(--qg-radius-xl)", border: "1px solid var(--qg-border)", opacity: 0.6 }} />
          ))}
        </div>
      ) : users.length === 0 ? (
        <div className="qg-card" style={{ textAlign: "center", padding: "64px 24px" }}>
          <UserCircle2 size={36} color="var(--qg-text-4)" style={{ margin: "0 auto 12px", display: "block" }} />
          <p style={{ fontWeight: 700, color: "var(--qg-text-1)", marginBottom: 6, fontSize: 14 }}>No users found</p>
        </div>
      ) : (
        <div className="qg-card" style={{ padding: 0, overflow: "hidden" }}>
          <div style={{ overflowX: "auto" }}>
            <table className="qg-table">
              <thead>
                <tr>
                  <th>User</th>
                  <th>Role</th>
                  <th style={{ textAlign: "center" }}>MFA</th>
                  <th style={{ textAlign: "center" }}>Status</th>
                  <th>Last Login</th>
                </tr>
              </thead>
              <tbody>
                {users.map((u) => (
                  <tr key={u.id}>
                    <td style={{ fontWeight: 700, color: "var(--qg-text-1)", fontSize: 12 }}>{u.display_name}</td>
                    <td>
                      <span className={`qg-badge ${ROLE_BADGE[u.role] || "qg-badge-muted"}`} style={{ textTransform: "capitalize" }}>
                        {u.role.replace(/_/g, " ")}
                      </span>
                    </td>
                    <td style={{ textAlign: "center" }}>
                      {u.mfa_enabled ? (
                        <ShieldCheck size={14} color="var(--qg-green)" style={{ display: "inline-block" }} />
                      ) : (
                        <span style={{ fontSize: 11, color: "var(--qg-text-4)" }}>—</span>
                      )}
                    </td>
                    <td style={{ textAlign: "center" }}>
                      <span className={`qg-badge ${u.is_active ? "qg-badge-low" : "qg-badge-muted"}`}>
                        {u.is_active ? "Active" : "Inactive"}
                      </span>
                    </td>
                    <td style={{ fontSize: 11, color: "var(--qg-text-4)" }}>
                      {u.last_login ? new Date(u.last_login).toLocaleString() : "Never"}
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
