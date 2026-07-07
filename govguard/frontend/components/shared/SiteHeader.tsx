"use client";

const GOLD = "#6495ED";
const HOME_URL = "https://quantioglobal.net";
const NAV_LINKS = ["About", "Services", "Platforms", "Vision", "Contact"];

function NavLink({ label }: { label: string }) {
  return (
    <a
      href={`${HOME_URL}/#${label.toLowerCase()}`}
      style={{
        color: "rgba(33,36,39,0.65)", fontSize: 13, fontWeight: 500,
        textDecoration: "none", padding: "7px 16px", borderRadius: 100,
        background: "rgba(33,36,39,0.04)",
        border: "1px solid rgba(33,36,39,0.08)",
        transition: "all 0.18s",
      }}
      onMouseEnter={e => {
        e.currentTarget.style.color = GOLD;
        e.currentTarget.style.background = "rgba(100,149,237,0.10)";
        e.currentTarget.style.borderColor = "rgba(100,149,237,0.30)";
      }}
      onMouseLeave={e => {
        e.currentTarget.style.color = "rgba(33,36,39,0.65)";
        e.currentTarget.style.background = "rgba(33,36,39,0.04)";
        e.currentTarget.style.borderColor = "rgba(33,36,39,0.08)";
      }}
    >{label}</a>
  );
}

export default function SiteHeader() {
  return (
    <nav style={{
      background: "#FFFFFF", padding: "18px 40px",
      display: "flex", alignItems: "center", gap: 6,
      borderBottom: "1px solid rgba(33,36,39,0.08)", flexShrink: 0,
    }}>
      <a href={HOME_URL} style={{ display: "flex", alignItems: "center", gap: 10, marginRight: 24, textDecoration: "none" }}>
        <img src="/qg-logo-gold.png" alt="Quantio Global" style={{ width: 40, height: "auto" }} />
        <div>
          <div style={{ fontSize: 14, fontWeight: 800, color: "#212427", letterSpacing: 2.5, textTransform: "uppercase", lineHeight: 1 }}>Quantio</div>
          <div style={{ fontSize: 8, fontWeight: 400, color: "rgba(33,36,39,0.45)", letterSpacing: 3.5, textTransform: "uppercase", marginTop: 2 }}>Global</div>
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
