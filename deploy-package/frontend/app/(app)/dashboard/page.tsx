"use client";
import useSWR from "swr";
import Link from "next/link";
import { TrendingDown, ClipboardCheck, AlertTriangle, DollarSign,
         ArrowRight, CheckCircle2, XCircle, BarChart3 } from "lucide-react";

const fetcher = (url: string) => fetch(url).then(r => r.json());

interface KPI {
  improperPaymentRate: number; complianceScore: number;
  openFindings: number; flaggedTxCount: number; totalTxCount: number;
  riskLeaderboard: { grantId: string; awardNumber: string; agency: string; complianceScore: number }[];
}

function KPICard({ label, value, sub, color, Icon }: { label: string; value: string; sub: string; color: string; Icon: React.ElementType }) {
  return (
    <div className={"rounded-xl border p-5 " + color}>
      <div className="flex items-center justify-between mb-3">
        <div className="p-2 bg-white/60 rounded-lg"><Icon className="w-5 h-5" /></div>
      </div>
      <p className="text-sm font-medium text-gray-600 mb-1">{label}</p>
      <p className="text-3xl font-bold text-gray-900">{value}</p>
      <p className="text-xs text-gray-500 mt-1">{sub}</p>
    </div>
  );
}

function ScoreBar({ score }: { score: number }) {
  const c = score >= 80 ? "bg-green-500" : score >= 60 ? "bg-amber-500" : "bg-red-500";
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 bg-gray-200 rounded-full h-2">
        <div className={c + " h-2 rounded-full"} style={{ width: `${score}%` }} />
      </div>
      <span className="text-sm font-bold text-gray-700 w-8">{Math.round(score)}</span>
    </div>
  );
}

export default function DashboardPage() {
  const { data: kpi, isLoading } = useSWR<KPI>("/api/dashboard/kpis?period=30d", fetcher, { refreshInterval: 300000 });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Governance Dashboard</h1>
        <p className="text-sm text-gray-500 mt-1">Real-time grant compliance and fraud risk — last 30 days</p>
      </div>

      {/* KPI Grid */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <KPICard label="Improper Payment Rate" value={isLoading ? "—" : `${kpi?.improperPaymentRate?.toFixed(1)}%`}
          sub="vs 5% target" color="bg-blue-50 border-blue-200" Icon={TrendingDown} />
        <KPICard label="Avg Compliance Score" value={isLoading ? "—" : `${kpi?.complianceScore?.toFixed(0)}/100`}
          sub="Active grants" color="bg-green-50 border-green-200" Icon={ClipboardCheck} />
        <KPICard label="Open Findings" value={isLoading ? "—" : String(kpi?.openFindings ?? 0)}
          sub="Audit findings" color="bg-amber-50 border-amber-200" Icon={AlertTriangle} />
        <KPICard label="Flagged Transactions" value={isLoading ? "—" : String(kpi?.flaggedTxCount ?? 0)}
          sub="Pending review" color="bg-red-50 border-red-200" Icon={DollarSign} />
      </div>

      {/* Bottom grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Risk Leaderboard */}
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-semibold text-gray-900">Risk Leaderboard</h3>
            <span className="text-xs text-gray-500">Lowest scoring grants</span>
          </div>
          {isLoading ? (
            <div className="space-y-3 animate-pulse">{[...Array(5)].map((_,i) => <div key={i} className="h-12 bg-gray-100 rounded" />)}</div>
          ) : !kpi?.riskLeaderboard?.length ? (
            <div className="text-center py-8 text-gray-400 text-sm">
              <BarChart3 className="w-8 h-8 mx-auto mb-2" /><p>No active grants yet</p>
              <Link href="/grants" className="text-blue-600 hover:underline text-xs mt-1 block">Create your first grant →</Link>
            </div>
          ) : (
            <div className="space-y-3">
              {kpi.riskLeaderboard.map((item, idx) => (
                <Link key={item.grantId} href={`/grants/${item.grantId}`}
                  className="flex items-center gap-3 p-3 rounded-lg hover:bg-gray-50 transition-colors group">
                  <span className="text-sm font-bold text-gray-400 w-5">{idx+1}</span>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-gray-900 truncate">{item.awardNumber}</p>
                    <p className="text-xs text-gray-500 truncate">{item.agency}</p>
                    <ScoreBar score={item.complianceScore} />
                  </div>
                  <ArrowRight className="w-4 h-4 text-gray-400 group-hover:text-blue-600 transition-colors" />
                </Link>
              ))}
            </div>
          )}
        </div>

        {/* Quick Actions */}
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <h3 className="font-semibold text-gray-900 mb-4">Quick Actions</h3>
          <div className="space-y-3">
            {[
              { href: "/grants", icon: FileText, label: "View all grants", desc: "Manage grant portfolio", color: "text-blue-600" },
              { href: "/fraud/pre-award", icon: AlertTriangle, label: "Screen applicant", desc: "Pre-award fraud detection", color: "text-amber-600" },
              { href: "/audit", icon: ClipboardCheck, label: "Audit workspace", desc: "CAP tracking & evidence", color: "text-green-600" },
            ].map(({ href, icon: Icon, label, desc, color }) => (
              <Link key={href} href={href} className="flex items-center gap-4 p-3 rounded-lg hover:bg-gray-50 transition-colors group border border-gray-100">
                <div className={"p-2 rounded-lg bg-gray-50 " + color}><Icon className="w-5 h-5" /></div>
                <div>
                  <p className="text-sm font-medium text-gray-900">{label}</p>
                  <p className="text-xs text-gray-500">{desc}</p>
                </div>
                <ArrowRight className="w-4 h-4 text-gray-400 group-hover:text-blue-600 ml-auto transition-colors" />
              </Link>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
