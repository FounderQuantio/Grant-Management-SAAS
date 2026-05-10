"use client";
import useSWR from "swr";
import Link from "next/link";
import { useState } from "react";
import { Plus, FileText, ChevronRight, CheckCircle2, Clock } from "lucide-react";
import { useForm } from "react-hook-form";

const fetcher = (url: string) => fetch(url).then(r => r.json());

export default function GrantsPage() {
  const { data, isLoading, mutate } = useSWR("/api/grants", fetcher);
  const [showForm, setShowForm] = useState(false);
  const [isCreating, setIsCreating] = useState(false);
  const { register, handleSubmit, reset } = useForm();

  const grants = data?.grants || [];

  const onSubmit = async (formData: Record<string, unknown>) => {
    setIsCreating(true);
    try {
      await fetch("/api/grants", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...formData, total_amount: Number(formData.total_amount), budget_json: {} }),
      });
      await mutate();
      setShowForm(false);
      reset();
    } finally { setIsCreating(false); }
  };

  const STATUS_CONFIG: Record<string, { color: string; icon: React.ElementType }> = {
    draft:  { color: "text-gray-600 bg-gray-100 border-gray-200", icon: Clock },
    active: { color: "text-green-700 bg-green-50 border-green-200", icon: CheckCircle2 },
    closed: { color: "text-blue-700 bg-blue-50 border-blue-200", icon: CheckCircle2 },
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Grants</h1>
          <p className="text-sm text-gray-500 mt-1">Manage your federal award portfolio</p>
        </div>
        <button onClick={() => setShowForm(!showForm)}
          className="flex items-center gap-2 bg-[#1F3864] hover:bg-[#2E75B6] text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors">
          <Plus className="w-4 h-4" /> New Grant
        </button>
      </div>

      {showForm && (
        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <h3 className="font-semibold text-gray-900 mb-4">Create New Grant</h3>
          <form onSubmit={handleSubmit(onSubmit)} className="grid grid-cols-2 gap-4">
            {[
              { name: "award_number", label: "Award Number", placeholder: "2024-HUD-001" },
              { name: "agency", label: "Awarding Agency", placeholder: "Dept. of Housing & Urban Development" },
              { name: "program_cfda", label: "CFDA/ALN Number", placeholder: "14.218" },
              { name: "total_amount", label: "Total Amount ($)", placeholder: "500000", type: "number" },
              { name: "period_start", label: "Period Start", type: "date" },
              { name: "period_end", label: "Period End", type: "date" },
            ].map(({ name, label, placeholder, type }) => (
              <div key={name}>
                <label className="block text-sm font-medium text-gray-700 mb-1">{label}</label>
                <input {...register(name, { required: true })} type={type || "text"} placeholder={placeholder}
                  className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
              </div>
            ))}
            <div className="col-span-2 flex gap-3 pt-2">
              <button type="submit" disabled={isCreating}
                className="bg-[#1F3864] text-white px-6 py-2 rounded-lg text-sm font-medium hover:bg-[#2E75B6] transition-colors disabled:opacity-50">
                {isCreating ? "Creating…" : "Create Grant"}
              </button>
              <button type="button" onClick={() => { setShowForm(false); reset(); }}
                className="px-4 py-2 border border-gray-300 rounded-lg text-sm text-gray-600 hover:bg-gray-50">Cancel</button>
            </div>
          </form>
        </div>
      )}

      {isLoading ? (
        <div className="space-y-3 animate-pulse">{[...Array(4)].map((_,i) => <div key={i} className="h-20 bg-gray-100 rounded-xl" />)}</div>
      ) : grants.length === 0 ? (
        <div className="text-center py-16 text-gray-500 bg-white rounded-xl border border-gray-200">
          <FileText className="w-12 h-12 mx-auto mb-3 text-gray-300" />
          <p className="font-medium text-gray-700 mb-1">No grants yet</p>
          <p className="text-sm text-gray-500 mb-4">Create your first grant to start tracking compliance.</p>
          <button onClick={() => setShowForm(true)}
            className="bg-[#1F3864] text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-[#2E75B6] transition-colors">
            Create First Grant
          </button>
        </div>
      ) : (
        <div className="space-y-3">
          {grants.map((g: Record<string, unknown>) => {
            const st = String(g.status || "draft");
            const cfg = STATUS_CONFIG[st] || STATUS_CONFIG.draft;
            const StatusIcon = cfg.icon;
            return (
              <Link key={String(g.id)} href={`/grants/${g.id}`}
                className="bg-white rounded-xl border border-gray-200 p-5 flex items-center gap-4 hover:shadow-md transition-all group">
                <div className="p-3 bg-blue-50 rounded-lg"><FileText className="w-5 h-5 text-blue-600" /></div>
                <div className="flex-1 min-w-0">
                  <p className="font-semibold text-gray-900">{String(g.award_number)}</p>
                  <p className="text-sm text-gray-500 truncate">{String(g.agency)}</p>
                </div>
                <div className="text-right">
                  <p className="text-sm font-medium text-gray-900">${Number(g.total_amount).toLocaleString()}</p>
                  <span className={"inline-flex items-center gap-1 text-xs font-medium px-2 py-0.5 rounded-full border mt-1 " + cfg.color}>
                    <StatusIcon className="w-3 h-3" /> {st}
                  </span>
                </div>
                <ChevronRight className="w-5 h-5 text-gray-400 group-hover:text-blue-600 transition-colors flex-shrink-0" />
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
}
