"use client";
import useSWR from "swr";
import { Bell, CheckCheck, AlertTriangle, Info, CheckCircle2 } from "lucide-react";

const fetcher = (url: string) => fetch(url).then(r => r.json());

const TYPE_CONFIG: Record<string, { icon: React.ElementType; color: string; bg: string }> = {
  alert:   { icon: AlertTriangle, color: "var(--qg-red)",    bg: "var(--qg-red-bg)" },
  info:    { icon: Info,          color: "var(--qg-gold)",   bg: "var(--qg-gold-tint-2)" },
  success: { icon: CheckCircle2,  color: "var(--qg-green)",  bg: "var(--qg-green-bg)" },
};

export default function NotificationsPage() {
  const { data, isLoading, mutate } = useSWR("/api/v1/notifications", fetcher);
  const notifications = data?.notifications || [];

  const markAllRead = async () => {
    await fetch("/api/v1/notifications/read-all", { method: "POST" });
    mutate();
  };

  return (
    <div className="qg-animate-in" style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <div>
          <span className="qg-section-label-badge" style={{ marginBottom: 8, display: "inline-block" }}>Inbox</span>
          <h1 className="qg-title" style={{ marginTop: 8 }}>Notifications</h1>
          <p className="qg-subtitle" style={{ marginTop: 4 }}>Alerts and system messages</p>
        </div>
        {notifications.length > 0 && (
          <button onClick={markAllRead} className="qg-btn qg-btn-secondary qg-btn-sm">
            <CheckCheck size={13} /> Mark all read
          </button>
        )}
      </div>

      {isLoading ? (
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {[...Array(5)].map((_, i) => (
            <div key={i} style={{ height: 64, background: "var(--qg-surface)", borderRadius: "var(--qg-radius-xl)", border: "1px solid var(--qg-border)", opacity: 0.6 }} />
          ))}
        </div>
      ) : notifications.length === 0 ? (
        <div className="qg-card" style={{ textAlign: "center", padding: "64px 24px" }}>
          <Bell size={36} color="var(--qg-text-4)" style={{ margin: "0 auto 12px", display: "block" }} />
          <p style={{ fontWeight: 700, color: "var(--qg-text-1)", fontSize: 14 }}>No notifications</p>
          <p style={{ fontSize: 12, color: "var(--qg-text-4)", marginTop: 4 }}>You&apos;re all caught up.</p>
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {notifications.map((n: Record<string, unknown>) => {
            const type = String(n.type || "info");
            const cfg = TYPE_CONFIG[type] || TYPE_CONFIG.info;
            const Icon = cfg.icon;
            return (
              <div
                key={String(n.id)}
                className="qg-card"
                style={{
                  display: "flex", alignItems: "flex-start", gap: 14, padding: "14px 18px",
                  borderColor: !n.read ? "var(--qg-gold-border)" : "var(--qg-border)",
                  background: !n.read ? "rgba(91,127,166,0.04)" : "var(--qg-surface)",
                }}
              >
                <div style={{ padding: 7, borderRadius: "var(--qg-radius-md)", background: cfg.bg, flexShrink: 0 }}>
                  <Icon size={13} color={cfg.color} />
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <p style={{ fontSize: 13, fontWeight: 600, color: "var(--qg-text-1)" }}>
                    {String(n.title || n.message || "")}
                  </p>
                  {n.body && (
                    <p style={{ fontSize: 12, color: "var(--qg-text-3)", marginTop: 3 }}>{String(n.body)}</p>
                  )}
                  <p style={{ fontSize: 10, color: "var(--qg-text-4)", marginTop: 4 }}>
                    {String(n.created_at || "").slice(0, 10)}
                  </p>
                </div>
                {!n.read && (
                  <span style={{ width: 6, height: 6, borderRadius: "50%", background: "var(--qg-gold)", flexShrink: 0, marginTop: 4 }} />
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
