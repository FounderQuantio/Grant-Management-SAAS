"use client";
import Link from "next/link";
import { ArrowRight, AlertCircle } from "lucide-react";

interface LeaderboardItem {
  grantId: string;
  awardNumber: string;
  agency: string;
  complianceScore: number;
}

function ScoreBar({ score }: { score: number }) {
  const color = score >= 80 ? "var(--qg-green)" : score >= 60 ? "var(--qg-yellow)" : "var(--qg-red)";
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 4 }}>
      <div style={{ flex: 1, background: "var(--qg-surface-2)", borderRadius: 100, height: 3 }}>
        <div style={{ background: color, height: 3, borderRadius: 100, width: `${score}%`, transition: "width 0.6s ease" }} />
      </div>
      <span style={{ fontSize: 11, fontWeight: 600, color: "var(--qg-text-3)", width: 26, textAlign: "right" }}>{score}</span>
    </div>
  );
}

export function RiskLeaderboard({ leaderboard, loading }: { leaderboard: LeaderboardItem[]; loading: boolean }) {
  return (
    <div className="qg-card" style={{ padding: 20 }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
        <h3 style={{ fontSize: 13, fontWeight: 700, color: "var(--qg-text-1)" }}>Risk Leaderboard</h3>
        <span className="qg-badge qg-badge-muted">Lowest scoring</span>
      </div>

      {loading ? (
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          {[...Array(5)].map((_, i) => (
            <div key={i} style={{ height: 42, background: "var(--qg-surface-2)", borderRadius: "var(--qg-radius-md)", opacity: 0.6 }} />
          ))}
        </div>
      ) : leaderboard.length === 0 ? (
        <div style={{ textAlign: "center", padding: "32px 0", color: "var(--qg-text-4)" }}>
          <AlertCircle size={28} style={{ margin: "0 auto 10px", display: "block" }} />
          <p style={{ fontSize: 13 }}>No active grants found</p>
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
          {leaderboard.map((item, idx) => (
            <Link
              key={item.grantId}
              href={`/grants/${item.grantId}/compliance`}
              style={{
                display: "flex", alignItems: "center", gap: 12,
                padding: "9px 10px",
                borderRadius: "var(--qg-radius-md)",
                textDecoration: "none",
                transition: "var(--qg-ease)",
              }}
              onMouseEnter={e => (e.currentTarget.style.background = "var(--qg-surface-2)")}
              onMouseLeave={e => (e.currentTarget.style.background = "transparent")}
            >
              <span style={{ fontSize: 10, fontWeight: 800, color: "var(--qg-text-4)", width: 16, textAlign: "center" }}>{idx + 1}</span>
              <div style={{ flex: 1, minWidth: 0 }}>
                <p style={{ fontSize: 12, fontWeight: 600, color: "var(--qg-text-1)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                  {item.awardNumber}
                </p>
                <p style={{ fontSize: 11, color: "var(--qg-text-4)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                  {item.agency}
                </p>
                <ScoreBar score={item.complianceScore} />
              </div>
              <ArrowRight size={13} color="var(--qg-text-4)" />
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
