"use client";
import useSWR from "swr";
import { useState } from "react";
import { ClipboardCheck, Plus, Calendar, AlertTriangle } from "lucide-react";

const fetcher = (url: string) => fetch(url).then(r => r.json());

export default function AuditPage() {
  const { data, mutate } = useSWR("/api/audit/cap", fetcher);
  const [showForm, setShowForm] = useState(false);
  const [formData, setFormData] = useState({ response_text: "", due_date: "", finding_id: "" });
  const [isCreating, setIsCreating] = useState(false);

  const caps = data?.caps || [];
  const today = new Date();

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsCreating(true);
    try {
      await fetch("/api/audit/cap", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(formData),
      });
      await mutate();
      setShowForm(false);
    } finally { setIsCreating(false); }
  };

  const getDaysLeft = (due: string) => {
    const d = new Date(due);
    return Math.ceil((d.getTime() - today.getTime()) / (1000 * 60 * 60 * 24));
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Audit & CAP Workspace</h1>
          <p className="text-sm text-gray-500 mt-1">Corrective Action Plans & evidence management</p>
        </div>
        <button onClick={() => setShowForm(!showForm)}
          className="flex items-center gap-2 bg-[#1F3864] hover:bg-[#2E75B6] text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors">
          <Plus className="w-4 h-4" /> New CAP
        </button>
      </div>

      {showForm && (
        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <h3 className="font-semibold text-gray-900 mb-4">Create Corrective Action Plan</h3>
          <form onSubmit={onSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Response / Corrective Action</label>
              <textarea rows={4} value={formData.response_text}
                onChange={e => setFormData(p => ({ ...p, response_text: e.target.value }))}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="Describe the corrective action and responsible party..." required />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Target Completion Date</label>
              <input type="date" value={formData.due_date}
                onChange={e => setFormData(p => ({ ...p, due_date: e.target.value }))}
                className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" required />
            </div>
            <div className="flex gap-3">
              <button type="submit" disabled={isCreating}
                className="bg-[#1F3864] text-white px-6 py-2 rounded-lg text-sm font-medium hover:bg-[#2E75B6] disabled:opacity-50 transition-colors">
                {isCreating ? "Saving…" : "Create CAP"}
              </button>
              <button type="button" onClick={() => setShowForm(false)}
                className="px-4 py-2 border border-gray-300 rounded-lg text-sm text-gray-600 hover:bg-gray-50">Cancel</button>
            </div>
          </form>
        </div>
      )}

      {caps.length === 0 ? (
        <div className="text-center py-16 bg-white rounded-xl border border-gray-200">
          <ClipboardCheck className="w-12 h-12 mx-auto mb-3 text-gray-300" />
          <p className="font-medium text-gray-700 mb-1">No corrective action plans</p>
          <p className="text-sm text-gray-500">Create CAPs to track remediation of audit findings.</p>
        </div>
      ) : (
        <div className="space-y-3">
          {caps.map((cap: Record<string, unknown>) => {
            const daysLeft = getDaysLeft(String(cap.due_date));
            const isOverdue = daysLeft < 0;
            const isUrgent = daysLeft >= 0 && daysLeft <= 30;
            return (
              <div key={String(cap.id)} className={"bg-white rounded-xl border p-5 " + (isOverdue ? "border-red-300" : isUrgent ? "border-amber-300" : "border-gray-200")}>
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <p className="text-sm font-medium text-gray-900 line-clamp-2">{String(cap.response_text)}</p>
                    <div className="flex items-center gap-4 mt-2 text-xs text-gray-500">
                      <span className="flex items-center gap-1"><Calendar className="w-3 h-3" />Due: {String(cap.due_date)}</span>
                      {isOverdue ? (
                        <span className="text-red-600 font-medium flex items-center gap-1"><AlertTriangle className="w-3 h-3" />OVERDUE by {Math.abs(daysLeft)} days</span>
                      ) : (
                        <span className={isUrgent ? "text-amber-600 font-medium" : ""}>{daysLeft} days remaining</span>
                      )}
                    </div>
                  </div>
                  <span className={"text-xs font-medium px-2 py-1 rounded-full capitalize " +
                    (cap.status === "closed" ? "bg-green-100 text-green-700" :
                     cap.status === "open" ? "bg-amber-100 text-amber-700" : "bg-blue-100 text-blue-700")}>
                    {String(cap.status)}
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
