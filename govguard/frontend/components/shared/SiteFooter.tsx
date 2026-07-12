"use client";

const HOME_URL = "https://quantioglobal.net";
const FOOTER_LINKS = ["About", "Services", "Contact", "Privacy"];

function FooterLink({ label }: { label: string }) {
  const href = label === "Privacy" ? HOME_URL : `${HOME_URL}/#${label.toLowerCase()}`;
  return (
    <a
      href={href}
      style={{ fontSize: 13, color: "rgba(33,36,39,0.5)", textDecoration: "none" }}
      onMouseEnter={e => e.currentTarget.style.color = "#212427"}
      onMouseLeave={e => e.currentTarget.style.color = "rgba(33,36,39,0.5)"}
    >{label}</a>
  );
}

export default function SiteFooter() {
  return (
    <footer style={{ background: "#F4F5F7", borderTop: "1px solid rgba(33,36,39,0.08)", padding: "20px 40px", flexShrink: 0 }}>
      <div style={{
        maxWidth: 1200, margin: "0 auto",
        display: "flex", justifyContent: "space-between", alignItems: "center",
        flexWrap: "wrap", gap: 24,
      }}>
        <div>
          <a href={HOME_URL} style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 8, textDecoration: "none" }}>
            <img src="/qg-logo-gold.png" alt="Quantio Global" style={{ width: 38, height: "auto" }} />
            <div>
              <div style={{ fontSize: 14, fontWeight: 800, color: "#212427", letterSpacing: 2.5, textTransform: "uppercase", lineHeight: 1 }}>Quantio</div>
              <div style={{ fontSize: 8, fontWeight: 400, color: "rgba(33,36,39,0.62)", letterSpacing: 3.5, textTransform: "uppercase", marginTop: 2 }}>Global</div>
            </div>
          </a>
          <p style={{ fontSize: 12, color: "rgba(33,36,39,0.4)", margin: 0 }}>Finance Governance · Risk Management · Digital Transformation</p>
        </div>
        <div style={{ display: "flex", gap: 32 }}>
          {FOOTER_LINKS.map(l => <FooterLink key={l} label={l} />)}
        </div>
        <div style={{ textAlign: "right" }}>
          <p style={{ fontSize: 13, color: "rgba(33,36,39,0.45)", margin: 0 }}>contact@quantioglobal.net</p>
          <p style={{ fontSize: 11, color: "rgba(33,36,39,0.48)", margin: "6px 0 0" }}>© 2026 Quantio Global. All rights reserved.</p>
        </div>
      </div>
    </footer>
  );
}
