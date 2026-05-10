"use client";
import { useState } from "react";
import { AlertTriangle, CheckCircle2, Shield, Search } from "lucide-react";

interface ScreenResult {
  risk_score: number;
  dnp_match: boolean;
  dedup_matches: { id: string; name: string; risk_score: number }[];
  budget_flags: string[];
  recommendation: string;
}

export default function FraudScreenPage() {
  const [result, setResult] = useState<ScreenResult | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [formData, setFormData] = useState({ applicant_name: "", ein: "", address: "" });

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    try {
      const res = await fetch("/api/fraud/screen", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...formData, budget_json: {} }),
      });
      setResult(await res.json());
    } finally { setIsLoading(false); }
  };

  const getRiskColor = (score: number) => score >= 70 ? "text-red-700 bg-red-50 border-red-300" : score >= 40 ? "text-amber-700 bg-amber-50 border-amber-300" : "text-green-700 bg-green-50 border-green-300";

  return (
    <div className="max-w-2xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Pre-Award Fraud Screen</h1>
        <p className="text-sm text-gray-500 mt-1">Screen applicants before making award decisions</p>
      </div>

      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <form onSubmit={onSubmit} className="space-y-4">
          {[
            { name: "applicant_name", label: "Applicant Organization Name", placeholder: "ABC Nonprofit Inc." },
            { name: "ein", label: "Employer Identification Number (EIN)", placeholder: "12-3456789" },
            { name: "address", label: "Primary Address", placeholder: "123 Main St, City, State 00000" },
          ].map(({ name, label, placeholder }) => (
            <div key={name}>
              <label className="block text-sm font-medium text-gray-700 mb-1">{label}</label>
              <input value={(formData as Record<string, string>)[name]}
                onChange={e => setFormData(p => ({ ...p, [name]: e.target.value }))}
                placeholder={placeholder}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" required />
            </div>
          ))}
          <button type="submit" disabled={isLoading}
            className="w-full flex items-center justify-center gap-2 bg-[#1F3864] hover:bg-[#2E75B6] text-white py-2.5 rounded-lg text-sm font-medium transition-colors disabled:opacity-50">
            {isLoading ? (<><Search className="w-4 h-4 animate-spin" />Screening...</>) : (<><Shield className="w-4 h-4" />Run Fraud Screen</>)}
          </button>
        </form>
      </div>

      {result && (
        <div className="space-y-4">
          <div className={"rounded-xl border p-6 " + getRiskColor(result.risk_score)}>
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium opacity-70">Risk Score</p>
                <p className="text-4xl font-bold mt-1">{result.risk_score}<span className="text-lg font-normal opacity-60">/100</span></p>
              </div>
              <div className="text-right">
                <p className="text-sm font-medium opacity-70">Recommendation</p>
                <p className="font-bold mt-1 text-sm">{result.recommendation.replace(/_/g, " ")}</p>
              </div>
            </div>
          </div>

          {result.budget_flags.length > 0 && (
            <div className="bg-amber-50 border border-amber-200 rounded-xl p-4">
              <p className="text-sm font-semibold text-amber-800 flex items-center gap-2 mb-2">
                <AlertTriangle className="w-4 h-4" /> Budget Flags
              </p>
              {result.budget_flags.map((flag, i) => <p key={i} className="text-sm text-amber-700">• {flag}</p>)}
            </div>
          )}

          {result.dedup_matches.length > 0 && (
            <div className="bg-red-50 border border-red-200 rounded-xl p-4">
              <p className="text-sm font-semibold text-red-800 mb-2">Duplicate Entity Matches Found</p>
              {result.dedup_matches.map(m => <p key={m.id} className="text-sm text-red-700">• {m.name} (Risk: {m.risk_score}/100)</p>)}
            </div>
          )}

          {!result.budget_flags.length && !result.dedup_matches.length && (
            <div className="bg-green-50 border border-green-200 rounded-xl p-4 flex items-center gap-3">
              <CheckCircle2 className="w-5 h-5 text-green-600" />
              <p className="text-sm text-green-800">No flags detected. Standard processing may proceed.</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
