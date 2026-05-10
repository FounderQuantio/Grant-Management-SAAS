"use client";
import { useState } from "react";
import { ComplianceControl } from "@/lib/hooks/useCompliance";
import { CheckCircle2, XCircle, Clock, ChevronDown, ChevronUp, Upload, FileText } from "lucide-react";
import { api } from "@/lib/api";

const STATUS_CONFIG = {
  pass:           { icon: CheckCircle2, color: "text-green-600",  bg: "bg-green-50",  border: "border-green-200" },
  fail:           { icon: XCircle,      color: "text-red-600",    bg: "bg-red-50",    border: "border-red-200" },
  not_tested:     { icon: Clock,        color: "text-gray-500",   bg: "bg-gray-50",   border: "border-gray-200" },
  not_applicable: { icon: Clock,        color: "text-gray-400",   bg: "bg-gray-50",   border: "border-gray-100" },
};

function ControlRow({ control, grantId, onUpdate }: { control: ComplianceControl; grantId: string; onUpdate: () => void }) {
  const [expanded, setExpanded] = useState(false);
  const [isUpdating, setIsUpdating] = useState(false);

  const config = STATUS_CONFIG[control.status as keyof typeof STATUS_CONFIG] || STATUS_CONFIG.not_tested;
  const StatusIcon = config.icon;

  const updateStatus = async (status: string) => {
    setIsUpdating(true);
    try {
      await api.patch(`/api/v1/compliance/controls/${control.id}`, { status });
      onUpdate();
    } catch { /* handle error */ } finally {
      setIsUpdating(false);
    }
  };

  return (
    <div className={`border rounded-lg overflow-hidden ${config.border}`}>
      <button
        className={`w-full flex items-center gap-4 p-4 text-left ${config.bg} hover:opacity-90 transition-opacity`}
        onClick={() => setExpanded(!expanded)}
      >
        <StatusIcon className={`w-5 h-5 flex-shrink-0 ${config.color}`} />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-sm font-semibold text-gray-900">{control.controlCode}</span>
            {control.cfrClause && (
              <span className="text-xs text-gray-500 bg-white/70 px-1.5 py-0.5 rounded border border-gray-200">
                {control.cfrClause}
              </span>
            )}
          </div>
          <p className="text-xs text-gray-500 mt-0.5 capitalize">{control.domain.replace("_", " ")}</p>
        </div>
        <span className={`text-xs font-medium capitalize px-2 py-1 rounded-full ${config.bg} ${config.color} border ${config.border}`}>
          {control.status.replace("_", " ")}
        </span>
        {expanded ? <ChevronUp className="w-4 h-4 text-gray-400" /> : <ChevronDown className="w-4 h-4 text-gray-400" />}
      </button>

      {expanded && (
        <div className="p-4 bg-white border-t border-gray-200 space-y-4">
          {control.gaoPrinciple && (
            <p className="text-xs text-gray-500">
              <span className="font-medium">GAO Principle:</span> {control.gaoPrinciple}
            </p>
          )}
          {control.remediationNote && (
            <p className="text-sm text-gray-700 bg-amber-50 border border-amber-200 rounded p-3">
              <span className="font-medium">Remediation note:</span> {control.remediationNote}
            </p>
          )}
          {control.lastTested && (
            <p className="text-xs text-gray-500">
              Last tested: {new Date(control.lastTested).toLocaleDateString()}
            </p>
          )}

          <div className="flex gap-2 flex-wrap">
            <button
              onClick={() => updateStatus("pass")}
              disabled={isUpdating}
              className="text-xs px-3 py-1.5 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50 transition-colors"
            >
              Mark Pass
            </button>
            <button
              onClick={() => updateStatus("fail")}
              disabled={isUpdating}
              className="text-xs px-3 py-1.5 bg-red-600 text-white rounded-lg hover:bg-red-700 disabled:opacity-50 transition-colors"
            >
              Mark Fail
            </button>
            <button className="text-xs px-3 py-1.5 border border-gray-300 text-gray-600 rounded-lg hover:bg-gray-50 flex items-center gap-1 transition-colors">
              <Upload className="w-3 h-3" /> Upload Evidence
            </button>
            {control.evidenceS3Key && (
              <button className="text-xs px-3 py-1.5 border border-blue-300 text-blue-600 rounded-lg hover:bg-blue-50 flex items-center gap-1 transition-colors">
                <FileText className="w-3 h-3" /> View Evidence
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

// Group controls by domain
export function ControlAccordion({ controls, grantId, onUpdate }: {
  controls: ComplianceControl[];
  grantId: string;
  onUpdate: () => void;
}) {
  const grouped = controls.reduce((acc, ctrl) => {
    const d = ctrl.domain || "general";
    if (!acc[d]) acc[d] = [];
    acc[d].push(ctrl);
    return acc;
  }, {} as Record<string, ComplianceControl[]>);

  return (
    <div className="space-y-6">
      {Object.entries(grouped).map(([domain, ctrls]) => (
        <div key={domain}>
          <h3 className="text-sm font-semibold text-gray-700 uppercase tracking-wider mb-3 capitalize">
            {domain.replace(/_/g, " ")} ({ctrls.length})
          </h3>
          <div className="space-y-2">
            {ctrls.map((ctrl) => (
              <ControlRow key={ctrl.id} control={ctrl} grantId={grantId} onUpdate={onUpdate} />
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
