"use client";
import useSWR from "swr";
import { api } from "@/lib/api";
import { Flame } from "lucide-react";

interface HeatmapCell {
  category: string;
  spend: number;
  budget: number;
  variance: number;
  tx_count: number;
}

const fmtMoney = (n: number) =>
  n >= 1_000_000 ? `$${(n / 1_000_000).toFixed(1)}M` : `$${Math.round(n).toLocaleString()}`;

// Some imported transactions carry a raw NAICS code instead of a normalized
// cost_category (data-quality artifact from CSV ingestion, not a UI bug).
const NAICS_LABELS: Record<string, string> = {
  "722511": "Full-Service Restaurants",
};

function categoryLabel(category: string): string {
  if (NAICS_LABELS[category]) return `${NAICS_LABELS[category]} (NAICS ${category})`;
  if (/^\d+$/.test(category)) return `NAICS ${category}`;
  return category.replace(/_/g, " ");
}

function intensityColor(ratio: number) {
  // Interpolates from a light gold tint to the full brand gold as spend share increases.
  const alpha = 0.08 + ratio * 0.42;
  return `rgba(61,90,153,${alpha.toFixed(2)})`;
}

export function SpendHeatmap() {
  const { data, isLoading } = useSWR<{ cells: HeatmapCell[] }>(
    "/api/v1/dashboard/heatmap?period=30d",
    (url) => api.get<{ cells: HeatmapCell[] }>(url)
  );

  const cells = data?.cells ?? [];
  const maxSpend = Math.max(1, ...cells.map((c) => c.spend));
  const totalSpend = cells.reduce((sum, c) => sum + c.spend, 0);

  return (
    <div className="qg-card" style={{ padding: 20 }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
        <h3 style={{ fontSize: 13, fontWeight: 700, color: "var(--qg-text-1)", display: "flex", alignItems: "center", gap: 7 }}>
          <Flame size={13} color="var(--qg-gold)" /> Spend Heatmap by Cost Category
        </h3>
        <span className="qg-badge qg-badge-muted">{fmtMoney(totalSpend)} total</span>
      </div>

      {isLoading ? (
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          {[...Array(6)].map((_, i) => (
            <div key={i} style={{ width: 140, height: 84, background: "var(--qg-surface-2)", borderRadius: "var(--qg-radius-md)", opacity: 0.6 }} />
          ))}
        </div>
      ) : cells.length === 0 ? (
        <p style={{ fontSize: 12, color: "var(--qg-text-4)" }}>No categorized transactions yet.</p>
      ) : (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(150px, 1fr))", gap: 10 }}>
          {cells.map((c) => {
            const ratio = c.spend / maxSpend;
            return (
              <div
                key={c.category}
                style={{
                  background: intensityColor(ratio),
                  border: "1px solid var(--qg-border)",
                  borderRadius: "var(--qg-radius-md)",
                  padding: "12px 14px",
                }}
              >
                <p style={{ fontSize: 10, fontWeight: 700, color: "var(--qg-text-3)", textTransform: "capitalize", marginBottom: 8 }}>
                  {categoryLabel(c.category)}
                </p>
                <p style={{ fontSize: 17, fontWeight: 800, color: "var(--qg-text-1)", letterSpacing: "-0.3px" }}>
                  {fmtMoney(c.spend)}
                </p>
                <p style={{ fontSize: 10, color: "var(--qg-text-4)", marginTop: 4 }}>
                  {c.tx_count} transaction{c.tx_count === 1 ? "" : "s"} · {(ratio * 100).toFixed(0)}% of top category
                </p>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
