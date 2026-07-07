import { Shield, ChevronRight, Lock } from "lucide-react";
import Link from "next/link";

export default function LoginPage() {
  return (
    <div style={{
      minHeight: "100vh",
      background: "var(--qg-bg)",
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      padding: 24,
    }}>
      {/* Background grid accent */}
      <div style={{
        position: "fixed", inset: 0, zIndex: 0,
        backgroundImage: "radial-gradient(rgba(91,127,166,0.06) 1px, transparent 1px)",
        backgroundSize: "32px 32px",
        pointerEvents: "none",
      }} />

      <div style={{ width: "100%", maxWidth: 420, position: "relative", zIndex: 1 }}>
        {/* Logo */}
        <div style={{ textAlign: "center", marginBottom: 40 }}>
          <div style={{
            width: 64, height: 64, margin: "0 auto 20px",
            borderRadius: "var(--qg-radius-xl)",
            background: "var(--qg-gold-tint-1)",
            border: "1px solid var(--qg-gold-border)",
            display: "flex", alignItems: "center", justifyContent: "center",
            boxShadow: "var(--qg-shadow-gold)",
          }}>
            <Shield size={28} color="var(--qg-gold)" />
          </div>
          <h1 style={{ fontFamily: "var(--qg-font-display)", fontSize: 32, fontWeight: 900, color: "var(--qg-text-1)", letterSpacing: "-0.8px" }}>
            GovGuard™
          </h1>
          <p style={{ fontSize: 13, color: "var(--qg-text-3)", marginTop: 6 }}>
            Grant Compliance &amp; Fraud Prevention Platform
          </p>
        </div>

        {/* Card */}
        <div className="qg-card" style={{ padding: 32 }}>
          <h2 style={{ fontSize: 18, fontWeight: 800, color: "var(--qg-text-1)", marginBottom: 4 }}>Welcome</h2>
          <p style={{ fontSize: 13, color: "var(--qg-text-3)", marginBottom: 28 }}>
            Explore the GovGuard™ demo platform.
          </p>

          <Link
            href="/dashboard"
            className="qg-btn qg-btn-primary"
            style={{ width: "100%", justifyContent: "center", padding: "12px 24px", fontSize: 14 }}
          >
            <Shield size={16} />
            <span style={{ flex: 1, textAlign: "center" }}>Enter GovGuard™</span>
            <ChevronRight size={15} />
          </Link>

          <div style={{ marginTop: 24, paddingTop: 24, borderTop: "1px solid var(--qg-border)" }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 8 }}>
              <Lock size={11} color="var(--qg-text-4)" />
              <span style={{ fontSize: 11, color: "var(--qg-text-4)" }}>
                SOC 2 Type II · FedRAMP-aligned · Demo Mode
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
