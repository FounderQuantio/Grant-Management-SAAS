"use client";

export function ComplianceScoreRing({
  score, total, passing, failing,
}: { score: number; total: number; passing: number; failing: number }) {
  const r = 36;
  const circumference = 2 * Math.PI * r;
  const offset = circumference - (score / 100) * circumference;
  const color = score >= 80 ? "#22C55E" : score >= 60 ? "#EAB308" : "#EF4444";

  return (
    <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
      <div style={{ position: "relative", width: 88, height: 88 }}>
        <svg width="88" height="88" style={{ transform: "rotate(-90deg)" }} viewBox="0 0 88 88">
          <circle cx="44" cy="44" r={r} fill="none" stroke="rgba(255,255,255,0.08)" strokeWidth="8" />
          <circle
            cx="44" cy="44" r={r} fill="none" stroke={color} strokeWidth="8"
            strokeDasharray={circumference} strokeDashoffset={offset}
            strokeLinecap="round" style={{ transition: "stroke-dashoffset 0.7s ease" }}
          />
        </svg>
        <div style={{
          position: "absolute", inset: 0,
          display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center",
        }}>
          <span style={{ fontSize: 18, fontWeight: 900, color: "var(--qg-text-1)" }}>{score.toFixed(0)}</span>
          <span style={{ fontSize: 9, color: "var(--qg-text-4)" }}>/ 100</span>
        </div>
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
        <p style={{ fontSize: 11, color: "var(--qg-text-3)" }}>
          <span style={{ color: "var(--qg-green)", fontWeight: 700 }}>{passing}</span> passing
        </p>
        <p style={{ fontSize: 11, color: "var(--qg-text-3)" }}>
          <span style={{ color: "var(--qg-red)", fontWeight: 700 }}>{failing}</span> failing
        </p>
        <p style={{ fontSize: 11, color: "var(--qg-text-3)" }}>
          <span style={{ color: "var(--qg-text-3)", fontWeight: 700 }}>{total - passing - failing}</span> pending
        </p>
      </div>
    </div>
  );
}
