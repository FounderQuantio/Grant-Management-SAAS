"use client";

interface RiskScoreBadgeProps {
  score: number | null;
  size?: "sm" | "md" | "lg";
}

function getRiskConfig(score: number) {
  if (score >= 75) return { label: "HIGH RISK", color: "var(--qg-red)",    bg: "var(--qg-red-bg)",    border: "var(--qg-red-border)" };
  if (score >= 40) return { label: "MEDIUM",    color: "var(--qg-yellow)", bg: "var(--qg-yellow-bg)", border: "var(--qg-yellow-border)" };
  return             { label: "LOW",        color: "var(--qg-green)",  bg: "var(--qg-green-bg)",  border: "var(--qg-green-border)" };
}

export function RiskScoreBadge({ score, size = "md" }: RiskScoreBadgeProps) {
  if (score === null || score === undefined) {
    return (
      <span className="qg-badge qg-badge-muted">Scoring…</span>
    );
  }

  const config = getRiskConfig(score);
  const fontSize = size === "sm" ? 9 : size === "lg" ? 12 : 10;

  return (
    <span className="qg-badge" style={{
      background: config.bg, color: config.color, border: `1px solid ${config.border}`,
      fontSize,
    }}>
      <span style={{ fontFamily: "monospace" }}>{score.toFixed(0)}</span>
      <span style={{ opacity: 0.7, fontWeight: 400 }}>{config.label}</span>
    </span>
  );
}
