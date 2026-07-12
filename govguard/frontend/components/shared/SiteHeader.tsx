"use client";

const GOLD = "#3D5A99";
const HOME_URL = "https://quantioglobal.net";
const NAV_LINKS = ["About", "Services", "Platforms", "Vision", "Contact"];

function NavLink({ label }: { label: string }) {
  return (
    <a
      href={`${HOME_URL}/#${label.toLowerCase()}`}
      style={{
        color: "rgba(255,255,255,0.75)", fontSize: 13, fontWeight: 500,
        textDecoration: "none", padding: "7px 16px", borderRadius: 100,
        background: "rgba(255,255,255,0.08)",
        border: "1px solid rgba(255,255,255,0.14)",
        transition: "all 0.18s",
      }}
      onMouseEnter={e => {
        e.currentTarget.style.color = "#FFFFFF";
        e.currentTarget.style.background = "rgba(61,90,153,0.35)";
        e.currentTarget.style.borderColor = "rgba(61,90,153,0.55)";
      }}
      onMouseLeave={e => {
        e.currentTarget.style.color = "rgba(255,255,255,0.75)";
        e.currentTarget.style.background = "rgba(255,255,255,0.08)";
        e.currentTarget.style.borderColor = "rgba(255,255,255,0.14)";
      }}
    >{label}</a>
  );
}

export default function SiteHeader() {
  return (
    <nav style={{
      background: "#1F3A5F", padding: "18px 40px",
      display: "flex", alignItems: "center", gap: 6,
      borderBottom: "1px solid rgba(255,255,255,0.10)", flexShrink: 0,
    }}>
      <a href={HOME_URL} style={{ display: "flex", alignItems: "center", gap: 10, marginRight: 24, textDecoration: "none" }}>
        <img src="/qg-logo-gold.png" alt="Quantio Global" style={{ width: 40, height: "auto" }} />
        <div>
          <div style={{ fontSize: 14, fontWeight: 800, color: "#FFFFFF", letterSpacing: 2.5, textTransform: "uppercase", lineHeight: 1 }}>Quantio</div>
          <div style={{ fontSize: 8, fontWeight: 600, color: "rgba(255,255,255,0.75)", letterSpacing: 3.5, textTransform: "uppercase", marginTop: 2 }}>Global</div>
        </div>
      </a>
      <div style={{ display: "flex", gap: 6 }}>
        {NAV_LINKS.map(l => <NavLink key={l} label={l} />)}
      </div>
      <div style={{ marginLeft: "auto" }}>
        <a href={HOME_URL} style={{
          background: GOLD, color: "#FFFFFF", fontSize: 13, fontWeight: 700,
          padding: "9px 22px", borderRadius: 100, textDecoration: "none", display: "inline-block",
        }}>Home page</a>
      </div>
    </nav>
  );
}
