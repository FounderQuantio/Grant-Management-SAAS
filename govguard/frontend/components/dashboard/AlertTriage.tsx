"use client";
import useSWR from "swr";
import { AlertTriangle, CheckCircle2, Bell } from "lucide-react";
import { api } from "@/lib/api";
import { useAlertStore } from "@/lib/stores/alerts";

const SEVERITY_CONFIG = {
  critical: { bg: "bg-red-50",    text: "text-red-700",    border: "border-red-200",    Icon: AlertTriangle },
  warning:  { bg: "bg-amber-50",  text: "text-amber-700",  border: "border-amber-200",  Icon: AlertTriangle },
  info:     { bg: "bg-blue-50",   text: "text-blue-700",   border: "border-blue-200",   Icon: Bell },
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
    <div className="bg-white rounded-xl border border-gray-200 p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-semibold text-gray-900">Alert Triage Queue</h3>
        <span className="text-xs text-blue-600 font-medium">{allAlerts.length} active</span>
      </div>

      {allAlerts.length === 0 ? (
        <div className="text-center py-8 text-gray-500 text-sm">
          <CheckCircle2 className="w-8 h-8 mx-auto mb-2 text-green-400" />
          No active alerts
        </div>
      ) : (
        <div className="space-y-2 max-h-64 overflow-y-auto">
          {allAlerts.map((alert, idx) => {
            const severity = (alert.severity as keyof typeof SEVERITY_CONFIG) || "info";
            const config = SEVERITY_CONFIG[severity];
            return (
              <div
                key={alert.id || idx}
                className={`flex items-start gap-3 p-3 rounded-lg border ${config.bg} ${config.border}`}
              >
                <config.Icon className={`w-4 h-4 mt-0.5 ${config.text} flex-shrink-0`} />
                <div className="min-w-0 flex-1">
                  <p className={`text-sm font-medium ${config.text}`}>
                    {alert.type?.replace(/_/g, " ")}
                  </p>
                  <p className="text-xs text-gray-500 mt-0.5">
                    {new Date(alert.created_at || (alert as Record<string,unknown>).ts as string).toLocaleTimeString()}
                  </p>
                </div>
                <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${config.bg} ${config.text} border ${config.border} uppercase`}>
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
