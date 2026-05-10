"use client";

interface RiskScoreBadgeProps {
  score: number | null;
  size?: "sm" | "md" | "lg";
}

function getRiskConfig(score: number) {
  if (score >= 75) return { label: "HIGH RISK", bg: "bg-red-100", text: "text-red-800", border: "border-red-300" };
  if (score >= 40) return { label: "MEDIUM", bg: "bg-amber-100", text: "text-amber-800", border: "border-amber-300" };
  return { label: "LOW", bg: "bg-green-100", text: "text-green-800", border: "border-green-300" };
}

export function RiskScoreBadge({ score, size = "md" }: RiskScoreBadgeProps) {
  if (score === null || score === undefined) {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-1 bg-gray-100 text-gray-500 border border-gray-200 rounded-full text-xs font-medium">
        Scoring...
      </span>
    );
  }

  const config = getRiskConfig(score);
  const textSize = size === "sm" ? "text-xs" : "text-sm";

  return (
    <span className={`inline-flex items-center gap-1 px-2 py-1 ${config.bg} ${config.text} border ${config.border} rounded-full ${textSize} font-bold`}>
      <span className="font-mono">{score.toFixed(0)}</span>
      <span className="font-normal opacity-70">{config.label}</span>
    </span>
  );
}
