"use client";
import { useParams } from "next/navigation";
import { useState } from "react";
import { useCompliance } from "@/lib/hooks/useCompliance";
import { ControlAccordion } from "@/components/compliance/ControlAccordion";
import { ComplianceScoreRing } from "@/components/compliance/ComplianceScoreRing";
import { GrantTabs } from "@/components/grants/GrantTabs";
import { CheckCircle2, XCircle, Clock, Filter } from "lucide-react";

const DOMAINS = ["all", "financial_management", "procurement", "subrecipient", "reporting", "cost_principles", "closeout"];

export default function CompliancePage() {
  const { id: grantId } = useParams<{ id: string }>();
  const [domain, setDomain] = useState<string | undefined>(undefined);
  const [status, setStatus] = useState<string | undefined>(undefined);

  const { data, isLoading, mutate } = useCompliance(grantId, domain, status);

  void status; // used via setStatus for future filter wiring

  return (
    <div className="qg-animate-in">
      <GrantTabs grantId={grantId} />
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 24 }}>
        <div>
          <span className="qg-section-label-badge" style={{ marginBottom: 8, display: "inline-block" }}>Compliance</span>
          <h1 className="qg-title" style={{ marginTop: 8 }}>Compliance Controls</h1>
          <p className="qg-subtitle" style={{ marginTop: 4 }}>2 CFR Part 200 & GAO Green Book alignment</p>
        </div>
        {data && <ComplianceScoreRing score={data.score} total={data.total} passing={data.passing} failing={data.failing} />}
      </div>

      {/* Stats bar */}
      {data && (
        <div className="qg-grid-3" style={{ marginBottom: 24 }}>
          <div className="qg-card" style={{ borderColor: "var(--qg-green-border)", display: "flex", alignItems: "center", gap: 14, padding: 16 }}>
            <CheckCircle2 size={28} color="var(--qg-green)" />
            <div>
              <p style={{ fontSize: 22, fontWeight: 800, color: "var(--qg-green)" }}>{data.passing}</p>
              <p style={{ fontSize: 11, color: "var(--qg-green)", opacity: 0.7 }}>Passing</p>
            </div>
          </div>
          <div className="qg-card" style={{ borderColor: "var(--qg-red-border)", display: "flex", alignItems: "center", gap: 14, padding: 16 }}>
            <XCircle size={28} color="var(--qg-red)" />
            <div>
              <p style={{ fontSize: 22, fontWeight: 800, color: "var(--qg-red)" }}>{data.failing}</p>
              <p style={{ fontSize: 11, color: "var(--qg-red)", opacity: 0.7 }}>Failing</p>
            </div>
          </div>
          <div className="qg-card" style={{ display: "flex", alignItems: "center", gap: 14, padding: 16 }}>
            <Clock size={28} color="var(--qg-text-3)" />
            <div>
              <p style={{ fontSize: 22, fontWeight: 800, color: "var(--qg-text-2)" }}>{data.total - data.passing - data.failing}</p>
              <p style={{ fontSize: 11, color: "var(--qg-text-4)" }}>Not Tested</p>
            </div>
          </div>
        </div>
      )}

      {/* Domain filters */}
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 20, flexWrap: "wrap" }}>
        <Filter size={13} color="var(--qg-text-4)" />
        <span style={{ fontSize: 11, color: "var(--qg-text-4)", marginRight: 4 }}>Domain:</span>
        {DOMAINS.map((d) => (
          <button
            key={d}
            onClick={() => setDomain(d === "all" ? undefined : d)}
            className={`qg-pill${(!domain && d === "all") || domain === d ? " active" : ""}`}
            style={{ textTransform: "capitalize" }}
          >
            {d.replace("_", " ")}
          </button>
        ))}
      </div>

      {/* Control list */}
      {isLoading ? (
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {[...Array(8)].map((_, i) => (
            <div key={i} style={{ height: 56, background: "var(--qg-surface)", borderRadius: "var(--qg-radius-md)", border: "1px solid var(--qg-border)", opacity: 0.6 }} />
          ))}
        </div>
      ) : (
        <ControlAccordion controls={data?.controls ?? []} grantId={grantId} onUpdate={() => mutate()} />
      )}
    </div>
  );
}
