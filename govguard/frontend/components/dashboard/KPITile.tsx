"use client";
import { LucideIcon, TrendingUp, TrendingDown, Minus } from "lucide-react";

interface KPITileProps {
  label: string;
  value: string;
  icon: LucideIcon;
  trend: "good" | "bad" | "neutral";
  description?: string;
  loading?: boolean;
}

const TREND_CONFIG = {
  good:    { color: "var(--qg-green)",  bg: "var(--qg-green-bg)",    border: "var(--qg-green-border)",  Icon: TrendingUp },
  bad:     { color: "var(--qg-red)",    bg: "var(--qg-red-bg)",      border: "var(--qg-red-border)",    Icon: TrendingDown },
  neutral: { color: "var(--qg-gold)",   bg: "var(--qg-gold-tint-2)", border: "var(--qg-gold-border)",   Icon: Minus },
};

export function KPITile({ label, value, icon: Icon, trend, description, loading }: KPITileProps) {
  const config = TREND_CONFIG[trend];

  if (loading) {
    return (
      <div className="qg-card" style={{ minHeight: 110 }}>
        <div style={{ height: 10, background: "var(--qg-surface-2)", borderRadius: 4, width: "70%", marginBottom: 14 }} />
        <div style={{ height: 24, background: "var(--qg-surface-2)", borderRadius: 4, width: "45%" }} />
      </div>
    );
  }

  return (
    <div className="qg-card" style={{ borderColor: config.border }}>
      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: 14 }}>
        <div style={{ padding: 8, borderRadius: "var(--qg-radius-md)", background: config.bg, border: `1px solid ${config.border}` }}>
          <Icon size={15} color={config.color} />
        </div>
        <config.Icon size={13} color={config.color} style={{ marginTop: 2, opacity: 0.7 }} />
      </div>
      <p style={{ fontSize: 11, fontWeight: 500, color: "var(--qg-text-3)", marginBottom: 5 }}>{label}</p>
      <p style={{ fontSize: 22, fontWeight: 800, color: config.color, letterSpacing: "-0.5px" }}>{value}</p>
      {description && (
        <p style={{ fontSize: 10, color: "var(--qg-text-4)", marginTop: 5, letterSpacing: "0.3px" }}>{description}</p>
      )}
    </div>
  );
}
