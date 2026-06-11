"use client";
import useSWR from "swr";
import { Bell, CheckCheck, AlertTriangle, Info, CheckCircle2 } from "lucide-react";

const fetcher = (url: string) => fetch(url).then(r => r.json());

const TYPE_CONFIG: Record<string, { icon: React.ElementType; color: string }> = {
  alert:   { icon: AlertTriangle, color: "text-red-600 bg-red-50" },
  info:    { icon: Info,          color: "text-blue-600 bg-blue-50" },
  success: { icon: CheckCircle2,  color: "text-green-600 bg-green-50" },
};

export default function NotificationsPage() {
  const { data, isLoading, mutate } = useSWR("/api/v1/notifications", fetcher);
  const notifications = data?.notifications || [];

  const markAllRead = async () => {
    await fetch("/api/v1/notifications/read-all", { method: "POST" });
    mutate();
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Notifications</h1>
          <p className="text-sm text-gray-500 mt-1">Alerts and system messages</p>
        </div>
        {notifications.length > 0 && (
          <button onClick={markAllRead}
            className="flex items-center gap-2 text-sm text-gray-600 hover:text-gray-900 border border-gray-300 px-3 py-1.5 rounded-lg hover:bg-gray-50 transition-colors">
            <CheckCheck className="w-4 h-4" /> Mark all read
          </button>
        )}
      </div>

      {isLoading ? (
        <div className="space-y-3 animate-pulse">{[...Array(5)].map((_, i) => <div key={i} className="h-16 bg-gray-100 rounded-xl" />)}</div>
      ) : notifications.length === 0 ? (
        <div className="text-center py-16 bg-white rounded-xl border border-gray-200">
          <Bell className="w-12 h-12 mx-auto mb-3 text-gray-300" />
          <p className="font-medium text-gray-700">No notifications</p>
          <p className="text-sm text-gray-500 mt-1">You're all caught up.</p>
        </div>
      ) : (
        <div className="space-y-2">
          {notifications.map((n: Record<string, unknown>) => {
            const type = String(n.type || "info");
            const cfg = TYPE_CONFIG[type] || TYPE_CONFIG.info;
            const Icon = cfg.icon;
            return (
              <div key={String(n.id)}
                className={`flex items-start gap-4 p-4 bg-white rounded-xl border transition-colors ${!n.read ? "border-blue-200 bg-blue-50/30" : "border-gray-200"}`}>
                <div className={`p-2 rounded-lg flex-shrink-0 ${cfg.color}`}>
                  <Icon className="w-4 h-4" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-gray-900">{String(n.title || n.message || "")}</p>
                  {n.body && <p className="text-sm text-gray-500 mt-0.5">{String(n.body)}</p>}
                  <p className="text-xs text-gray-400 mt-1">{String(n.created_at || "").slice(0, 10)}</p>
                </div>
                {!n.read && <span className="w-2 h-2 rounded-full bg-blue-500 flex-shrink-0 mt-1.5" />}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
