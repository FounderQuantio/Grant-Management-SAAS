import { Suspense } from "react";
import { DashboardContent } from "@/components/dashboard/DashboardContent";

export default function DashboardPage() {
  return (
    <div className="qg-animate-in">
      <div style={{ marginBottom: 24 }}>
        <span className="qg-section-label-badge" style={{ marginBottom: 8, display: "inline-block" }}>Dashboard</span>
        <h1 className="qg-title" style={{ marginTop: 8 }}>Governance Dashboard</h1>
        <p className="qg-subtitle" style={{ marginTop: 4 }}>Real-time grant compliance and fraud risk overview</p>
      </div>
      <Suspense fallback={<DashboardSkeleton />}>
        <DashboardContent />
      </Suspense>
    </div>
  );
}

function DashboardSkeleton() {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
      <div className="qg-grid-4">
        {[...Array(4)].map((_, i) => (
          <div key={i} style={{ height: 112, background: "var(--qg-surface)", borderRadius: "var(--qg-radius-xl)", border: "1px solid var(--qg-border)", opacity: 0.6 }} />
        ))}
      </div>
      <div style={{ height: 256, background: "var(--qg-surface)", borderRadius: "var(--qg-radius-xl)", border: "1px solid var(--qg-border)", opacity: 0.6 }} />
    </div>
  );
}
