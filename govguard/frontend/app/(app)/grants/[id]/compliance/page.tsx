"use client";
import { useParams } from "next/navigation";
import { useState } from "react";
import { useCompliance } from "@/lib/hooks/useCompliance";
import { ControlAccordion } from "@/components/compliance/ControlAccordion";
import { ComplianceScoreRing } from "@/components/compliance/ComplianceScoreRing";
import { CheckCircle2, XCircle, Clock, Filter } from "lucide-react";

const DOMAINS = ["all", "financial_management", "procurement", "subrecipient", "reporting", "cost_principles", "closeout"];
const STATUS_FILTERS = ["all", "fail", "pass", "not_tested"];

export default function CompliancePage() {
  const { id: grantId } = useParams<{ id: string }>();
  const [domain, setDomain] = useState<string | undefined>(undefined);
  const [status, setStatus] = useState<string | undefined>(undefined);

  const { data, isLoading, mutate } = useCompliance(grantId, domain, status);

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Compliance Controls</h1>
          <p className="text-sm text-gray-500 mt-1">2 CFR Part 200 & GAO Green Book alignment</p>
        </div>
        {data && <ComplianceScoreRing score={data.score} total={data.total} passing={data.passing} failing={data.failing} />}
      </div>

      {/* Stats bar */}
      {data && (
        <div className="grid grid-cols-3 gap-4 mb-6">
          <div className="bg-green-50 border border-green-200 rounded-lg p-4 flex items-center gap-3">
            <CheckCircle2 className="w-8 h-8 text-green-600" />
            <div>
              <p className="text-2xl font-bold text-green-700">{data.passing}</p>
              <p className="text-sm text-green-600">Passing</p>
            </div>
          </div>
          <div className="bg-red-50 border border-red-200 rounded-lg p-4 flex items-center gap-3">
            <XCircle className="w-8 h-8 text-red-600" />
            <div>
              <p className="text-2xl font-bold text-red-700">{data.failing}</p>
              <p className="text-sm text-red-600">Failing</p>
            </div>
          </div>
          <div className="bg-gray-50 border border-gray-200 rounded-lg p-4 flex items-center gap-3">
            <Clock className="w-8 h-8 text-gray-500" />
            <div>
              <p className="text-2xl font-bold text-gray-700">{data.total - data.passing - data.failing}</p>
              <p className="text-sm text-gray-600">Not Tested</p>
            </div>
          </div>
        </div>
      )}

      {/* Filters */}
      <div className="flex gap-3 mb-6 flex-wrap">
        <div className="flex items-center gap-2">
          <Filter className="w-4 h-4 text-gray-500" />
          <span className="text-sm text-gray-600">Domain:</span>
          {DOMAINS.map((d) => (
            <button
              key={d}
              onClick={() => setDomain(d === "all" ? undefined : d)}
              className={`text-xs px-3 py-1 rounded-full border transition-colors capitalize
                ${(!domain && d === "all") || domain === d
                  ? "bg-[#1F3864] text-white border-[#1F3864]"
                  : "text-gray-600 border-gray-300 hover:border-blue-400"
                }`}
            >
              {d.replace("_", " ")}
            </button>
          ))}
        </div>
      </div>

      {/* Control list */}
      {isLoading ? (
        <div className="space-y-3 animate-pulse">
          {[...Array(8)].map((_, i) => <div key={i} className="h-16 bg-gray-100 rounded-lg" />)}
        </div>
      ) : (
        <ControlAccordion controls={data?.controls ?? []} grantId={grantId} onUpdate={() => mutate()} />
      )}
    </div>
  );
}
