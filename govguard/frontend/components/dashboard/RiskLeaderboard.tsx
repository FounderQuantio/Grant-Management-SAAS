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
  const color = score >= 80 ? "bg-green-500" : score >= 60 ? "bg-amber-500" : "bg-red-500";
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 bg-gray-200 rounded-full h-2">
        <div className={`${color} h-2 rounded-full transition-all`} style={{ width: `${score}%` }} />
      </div>
      <span className="text-sm font-medium text-gray-700 w-10 text-right">{score}</span>
    </div>
  );
}

export function RiskLeaderboard({
  leaderboard,
  loading,
}: {
  leaderboard: LeaderboardItem[];
  loading: boolean;
}) {
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-semibold text-gray-900">Risk Leaderboard</h3>
        <span className="text-xs text-gray-500">Lowest scoring grants</span>
      </div>

      {loading ? (
        <div className="space-y-3 animate-pulse">
          {[...Array(5)].map((_, i) => <div key={i} className="h-10 bg-gray-100 rounded" />)}
        </div>
      ) : leaderboard.length === 0 ? (
        <div className="text-center py-8 text-gray-500 text-sm">
          <AlertCircle className="w-8 h-8 mx-auto mb-2 text-gray-400" />
          No active grants found
        </div>
      ) : (
        <div className="space-y-3">
          {leaderboard.map((item, idx) => (
            <Link
              key={item.grantId}
              href={`/grants/${item.grantId}/compliance`}
              className="flex items-center gap-3 p-3 rounded-lg hover:bg-gray-50 transition-colors group"
            >
              <span className="text-sm font-bold text-gray-400 w-5">{idx + 1}</span>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-gray-900 truncate">{item.awardNumber}</p>
                <p className="text-xs text-gray-500 truncate">{item.agency}</p>
                <ScoreBar score={item.complianceScore} />
              </div>
              <ArrowRight className="w-4 h-4 text-gray-400 group-hover:text-blue-600 transition-colors flex-shrink-0" />
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
