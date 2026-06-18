"use client";
import useSWR from "swr";
import { AlertTriangle, CheckCircle2, Bell } from "lucide-react";
import { api } from "@/lib/api";
import { useAlertStore } from "@/lib/stores/alerts";

const SEVERITY_CONFIG = {
  critical: { bg: "var(--qg-red-bg)",    text: "var(--qg-red)",    border: "var(--qg-red-border)",    badgeClass: "qg-badge-critical", Icon: AlertTriangle },
  warning:  { bg: "var(--qg-orange-bg)", text: "var(--qg-orange)", border: "var(--qg-orange-border)", badgeClass: "qg-badge-high",     Icon: AlertTriangle },
  info:     { bg: "var(--qg-gold-tint-2)", text: "var(--qg-gold)", border: "var(--qg-gold-border)",   badgeClass: "qg-badge-gold",     Icon: Bell },
};

export function AlertTriage() {
  const { alerts: liveAlerts } = useAlertStore();
  const { data } = useSWR(
    "/api/v1/dashboard/alerts?limit=10",
    (url) => api.get<{ alerts: Array<{ id: string; type: string; severity: string; created_at: string; resource: { type: string; id: string } }> }>(url),
    { refreshInterval: 30000 }
  );

  const apiAlerts = data?.alerts ?? [];
  const allAlerts = [...liveAlerts.slice(0, 5), ...apiAlerts.slice(0, 5)].slice(0, 8);

  return (
    <div className="qg-card" style={{ padding: 20 }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
        <h3 style={{ fontSize: 13, fontWeight: 700, color: "var(--qg-text-1)" }}>Alert Triage Queue</h3>
        <span className="qg-badge qg-badge-gold">{allAlerts.length} active</span>
      </div>

      {allAlerts.length === 0 ? (
        <div style={{ textAlign: "center", padding: "32px 0", color: "var(--qg-text-4)" }}>
          <CheckCircle2 size={28} color="var(--qg-green)" style={{ margin: "0 auto 10px", display: "block" }} />
          <p style={{ fontSize: 13 }}>No active alerts</p>
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 8, maxHeight: 260, overflowY: "auto" }}>
          {allAlerts.map((alert, idx) => {
            const severity = (alert.severity as keyof typeof SEVERITY_CONFIG) || "info";
            const config = SEVERITY_CONFIG[severity] || SEVERITY_CONFIG.info;
            return (
              <div
                key={alert.id || idx}
                style={{
                  display: "flex", alignItems: "flex-start", gap: 10, padding: 10,
                  borderRadius: "var(--qg-radius-md)",
                  background: config.bg,
                  border: `1px solid ${config.border}`,
                }}
              >
                <config.Icon size={13} color={config.text} style={{ marginTop: 1, flexShrink: 0 }} />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <p style={{ fontSize: 12, fontWeight: 600, color: config.text }}>
                    {alert.type?.replace(/_/g, " ")}
                  </p>
                  <p style={{ fontSize: 10, color: "var(--qg-text-4)", marginTop: 2 }}>
                    {new Date(
                      (alert as Record<string, unknown>).created_at as string ||
                      (alert as Record<string, unknown>).ts as string
                    ).toLocaleTimeString()}
                  </p>
                </div>
                <span className={`qg-badge ${config.badgeClass}`} style={{ textTransform: "uppercase" }}>
                  {severity}
                </span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
