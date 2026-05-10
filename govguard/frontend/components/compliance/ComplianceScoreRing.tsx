"use client";

export function ComplianceScoreRing({
  score, total, passing, failing,
}: { score: number; total: number; passing: number; failing: number }) {
  const r = 36;
  const circumference = 2 * Math.PI * r;
  const offset = circumference - (score / 100) * circumference;
  const color = score >= 80 ? "#375623" : score >= 60 ? "#C55A11" : "#C00000";

  return (
    <div className="flex items-center gap-4">
      <div className="relative w-24 h-24">
        <svg className="w-24 h-24 -rotate-90" viewBox="0 0 88 88">
          <circle cx="44" cy="44" r={r} fill="none" stroke="#E5E7EB" strokeWidth="8" />
          <circle
            cx="44" cy="44" r={r} fill="none" stroke={color} strokeWidth="8"
            strokeDasharray={circumference} strokeDashoffset={offset}
            strokeLinecap="round" className="transition-all duration-700"
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-xl font-bold text-gray-900">{score.toFixed(0)}</span>
          <span className="text-xs text-gray-500">/ 100</span>
        </div>
      </div>
      <div className="text-sm text-gray-600 space-y-1">
        <p><span className="text-green-600 font-semibold">{passing}</span> passing</p>
        <p><span className="text-red-600 font-semibold">{failing}</span> failing</p>
        <p><span className="text-gray-500 font-semibold">{total - passing - failing}</span> pending</p>
      </div>
    </div>
  );
}
