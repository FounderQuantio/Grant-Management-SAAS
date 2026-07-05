"use client";
import { useState } from "react";
import { ComplianceControl } from "@/lib/hooks/useCompliance";
import { CheckCircle2, XCircle, Clock, ChevronDown, ChevronUp, Upload, FileText } from "lucide-react";
import { api } from "@/lib/api";

const STATUS_CONFIG = {
  pass:           { icon: CheckCircle2, color: "var(--qg-green)",  bg: "var(--qg-green-bg)",  border: "var(--qg-green-border)" },
  fail:           { icon: XCircle,      color: "var(--qg-red)",    bg: "var(--qg-red-bg)",    border: "var(--qg-red-border)" },
  not_tested:     { icon: Clock,        color: "var(--qg-text-3)", bg: "var(--qg-surface-2)", border: "var(--qg-border)" },
  not_applicable: { icon: Clock,        color: "var(--qg-text-4)", bg: "var(--qg-surface-2)", border: "var(--qg-border)" },
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
    <div style={{ border: `1px solid ${config.border}`, borderRadius: "var(--qg-radius-md)", overflow: "hidden" }}>
      <button
        style={{
          width: "100%", display: "flex", alignItems: "center", gap: 12, padding: "12px 14px",
          textAlign: "left", background: config.bg, border: "none", cursor: "pointer",
          transition: "var(--qg-ease)",
        }}
        onClick={() => setExpanded(!expanded)}
      >
        <StatusIcon size={15} color={config.color} style={{ flexShrink: 0 }} />
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <span style={{ fontSize: 12, fontWeight: 700, color: "var(--qg-text-1)" }}>{control.controlCode}</span>
            {control.cfrClause && (
              <span style={{
                fontSize: 9, color: "var(--qg-text-4)",
                background: "rgba(15,23,42,0.06)", padding: "1px 6px",
                borderRadius: "var(--qg-radius-sm)", border: "1px solid var(--qg-border)",
              }}>
                {control.cfrClause}
              </span>
            )}
          </div>
          <p style={{ fontSize: 11, color: "var(--qg-text-4)", marginTop: 2, textTransform: "capitalize" }}>
            {control.domain.replace("_", " ")}
          </p>
        </div>
        <span className="qg-badge" style={{
          background: config.bg, color: config.color, border: `1px solid ${config.border}`,
          textTransform: "capitalize",
        }}>
          {control.status.replace("_", " ")}
        </span>
        {expanded
          ? <ChevronUp size={13} color="var(--qg-text-4)" />
          : <ChevronDown size={13} color="var(--qg-text-4)" />
        }
      </button>

      {expanded && (
        <div style={{
          padding: 16, background: "var(--qg-surface-2)",
          borderTop: `1px solid var(--qg-border)`,
          display: "flex", flexDirection: "column", gap: 12,
        }}>
          {control.gaoPrinciple && (
            <p style={{ fontSize: 11, color: "var(--qg-text-4)" }}>
              <span style={{ fontWeight: 600, color: "var(--qg-text-3)" }}>GAO Principle:</span>{" "}
              {control.gaoPrinciple}
            </p>
          )}
          {control.remediationNote && (
            <p style={{
              fontSize: 12, color: "var(--qg-yellow)",
              background: "var(--qg-yellow-bg)", border: "1px solid var(--qg-yellow-border)",
              borderRadius: "var(--qg-radius-md)", padding: "8px 12px",
            }}>
              <span style={{ fontWeight: 700 }}>Remediation note:</span>{" "}
              {control.remediationNote}
            </p>
          )}
          {control.lastTested && (
            <p style={{ fontSize: 11, color: "var(--qg-text-4)" }}>
              Last tested: {new Date(control.lastTested).toLocaleDateString()}
            </p>
          )}

          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            <button
              onClick={() => updateStatus("pass")}
              disabled={isUpdating}
              className="qg-btn qg-btn-sm"
              style={{ background: "var(--qg-green-bg)", color: "var(--qg-green)", border: "1px solid var(--qg-green-border)" }}
            >
              Mark Pass
            </button>
            <button
              onClick={() => updateStatus("fail")}
              disabled={isUpdating}
              className="qg-btn qg-btn-sm"
              style={{ background: "var(--qg-red-bg)", color: "var(--qg-red)", border: "1px solid var(--qg-red-border)" }}
            >
              Mark Fail
            </button>
            <button className="qg-btn qg-btn-secondary qg-btn-sm" style={{ display: "flex", alignItems: "center", gap: 5 }}>
              <Upload size={11} /> Upload Evidence
            </button>
            {control.evidenceS3Key && (
              <button className="qg-btn qg-btn-sm" style={{ background: "var(--qg-gold-tint-2)", color: "var(--qg-gold)", border: "1px solid var(--qg-gold-border)", display: "flex", alignItems: "center", gap: 5 }}>
                <FileText size={11} /> View Evidence
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

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
    <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
      {Object.entries(grouped).map(([domain, ctrls]) => (
        <div key={domain}>
          <h3 style={{
            fontSize: 10, fontWeight: 800, color: "var(--qg-text-4)",
            textTransform: "uppercase", letterSpacing: "1.2px", marginBottom: 10,
          }}>
            {domain.replace(/_/g, " ")} ({ctrls.length})
          </h3>
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            {ctrls.map((ctrl) => (
              <ControlRow key={ctrl.id} control={ctrl} grantId={grantId} onUpdate={onUpdate} />
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
