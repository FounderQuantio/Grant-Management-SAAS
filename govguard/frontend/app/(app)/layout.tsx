"use client";
import { useRouter, usePathname } from "next/navigation";
import Link from "next/link";
import {
  LayoutDashboard, FileText, AlertTriangle, ClipboardCheck,
  Settings, Users, BarChart3, Bell, LogOut,
} from "lucide-react";
import { useUser } from "@auth0/nextjs-auth0/client";
import { useAlertStore } from "@/lib/stores/alerts";
import { useAlertFeed } from "@/lib/hooks/useAlertFeed";

const NAV_ITEMS = [
  { href: "/dashboard",          icon: LayoutDashboard, label: "Dashboard",    roles: [] },
  { href: "/grants",             icon: FileText,         label: "Grants",       roles: [] },
  { href: "/fraud/pre-award",    icon: AlertTriangle,    label: "Fraud Screen", roles: ["agency_officer", "system_admin"] },
  { href: "/fraud/vendor",       icon: AlertTriangle,    label: "Vendors",      roles: ["compliance_officer", "system_admin"] },
  { href: "/audit",              icon: ClipboardCheck,   label: "Audit",        roles: ["compliance_officer", "auditor", "system_admin"] },
  { href: "/integrations",       icon: Settings,         label: "Integrations", roles: ["compliance_officer", "system_admin"] },
  { href: "/equity",             icon: BarChart3,        label: "Equity",       roles: ["equity_analyst", "system_admin"] },
  { href: "/settings/users",     icon: Users,            label: "Users",        roles: ["compliance_officer", "system_admin"] },
  { href: "/admin/tenants",      icon: Settings,         label: "Admin",        roles: ["system_admin"] },
];

const ROLE_LEVELS: Record<string, number> = {
  system_admin: 7, agency_officer: 6, compliance_officer: 5,
  finance_manager: 4, finance_staff: 3, auditor: 2, equity_analyst: 1,
};

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const { user: auth0User } = useUser();
  const { unreadCount } = useAlertStore();
  const pathname = usePathname();
  const router = useRouter();

  useAlertFeed();

  const role = (auth0User?.["https://govguard.app/role"] as string) || "finance_staff";
  const displayName = auth0User?.name || auth0User?.email || "User";

  const hasRole = (...roles: string[]) => {
    const userLevel = ROLE_LEVELS[role] || 0;
    const required = Math.max(...roles.map((r) => ROLE_LEVELS[r] || 0));
    return userLevel >= required;
  };

  const navItems = NAV_ITEMS.filter(
    (item) => item.roles.length === 0 || hasRole(...item.roles)
  );

  return (
    <div style={{ display: "flex", height: "100%", background: "var(--qg-bg)", overflow: "hidden" }}>
      {/* Sidebar */}
      <aside className="qg-sidebar">
        <div className="qg-sidebar-header">
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <div className="qg-nav-logo-badge" style={{ fontSize: 10 }}>GG</div>
            <div>
              <div style={{ color: "var(--qg-text-1)", fontWeight: 800, fontSize: 13, letterSpacing: "-0.2px" }}>
                GovGuard™
              </div>
              <div style={{ color: "var(--qg-gold)", fontSize: 9, letterSpacing: "0.6px", textTransform: "uppercase", marginTop: 1 }}>
                Compliance Platform
              </div>
            </div>
          </div>
        </div>

        <nav className="qg-sidebar-nav">
          {navItems.map((item) => {
            const active = pathname.startsWith(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`qg-sidebar-item${active ? " active" : ""}`}
              >
                <item.icon size={14} strokeWidth={active ? 2.2 : 1.8} />
                {item.label}
              </Link>
            );
          })}
        </nav>

        <div style={{ padding: "12px 14px", borderTop: "1px solid var(--qg-border)" }}>
          {auth0User && (
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
              <div style={{ minWidth: 0 }}>
                <p style={{ fontSize: 12, fontWeight: 600, color: "var(--qg-text-1)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                  {displayName}
                </p>
                <p style={{ fontSize: 10, color: "var(--qg-gold)", textTransform: "capitalize", marginTop: 1 }}>
                  {role.replace(/_/g, " ")}
                </p>
              </div>
              <button
                onClick={() => router.push("/api/auth/logout")}
                style={{ padding: 6, borderRadius: "var(--qg-radius-md)", background: "transparent", border: "none", color: "var(--qg-text-4)", cursor: "pointer", transition: "var(--qg-ease)" }}
                title="Sign out"
              >
                <LogOut size={14} />
              </button>
            </div>
          )}
        </div>
      </aside>

      {/* Main area */}
      <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>
        {/* Top bar */}
        <header style={{
          height: 52,
          background: "var(--qg-nav-bg)",
          borderBottom: "1px solid var(--qg-border)",
          padding: "0 24px",
          display: "flex",
          alignItems: "center",
          justifyContent: "flex-end",
          backdropFilter: "blur(12px)",
          WebkitBackdropFilter: "blur(12px)",
          flexShrink: 0,
          gap: 10,
        }}>
          <Link
            href="/notifications"
            style={{ position: "relative", padding: 6, borderRadius: "var(--qg-radius-md)", display: "flex", color: "var(--qg-header-text)", textDecoration: "none", transition: "var(--qg-ease)" }}
          >
            <Bell size={16} />
            {unreadCount > 0 && (
              <span style={{
                position: "absolute", top: 1, right: 1,
                width: 14, height: 14,
                background: "var(--qg-red)",
                borderRadius: "50%",
                color: "#fff",
                fontSize: 8,
                display: "flex", alignItems: "center", justifyContent: "center",
                fontWeight: 800,
              }}>
                {unreadCount > 9 ? "9+" : unreadCount}
              </span>
            )}
          </Link>
        </header>

        {/* Page content */}
        <main style={{ flex: 1, overflowY: "auto", padding: 24, background: "var(--qg-bg)" }}>
          {children}
        </main>
      </div>
    </div>
  );
}
