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
  good:    { bg: "bg-green-50",  border: "border-green-200",  text: "text-green-700",  Icon: TrendingUp },
  bad:     { bg: "bg-red-50",    border: "border-red-200",    text: "text-red-700",    Icon: TrendingDown },
  neutral: { bg: "bg-blue-50",   border: "border-blue-200",   text: "text-blue-700",   Icon: Minus },
};

export function KPITile({ label, value, icon: Icon, trend, description, loading }: KPITileProps) {
  const config = TREND_CONFIG[trend];

  if (loading) {
    return (
      <div className="bg-white rounded-xl border border-gray-200 p-5 animate-pulse">
        <div className="h-4 bg-gray-200 rounded w-3/4 mb-3" />
        <div className="h-8 bg-gray-200 rounded w-1/2" />
      </div>
    );
  }

  return (
    <div className={`rounded-xl border p-5 ${config.bg} ${config.border}`}>
      <div className="flex items-start justify-between mb-3">
        <div className={`p-2 rounded-lg bg-white/60`}>
          <Icon className={`w-5 h-5 ${config.text}`} />
        </div>
        <config.Icon className={`w-4 h-4 ${config.text} mt-1`} />
      </div>
      <p className="text-sm font-medium text-gray-600 mb-1">{label}</p>
      <p className={`text-2xl font-bold ${config.text}`}>{value}</p>
      {description && <p className="text-xs text-gray-500 mt-1">{description}</p>}
    </div>
  );
}
