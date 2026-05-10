"use client";
import { useEffect } from "react";
import { useRouter, usePathname } from "next/navigation";
import Link from "next/link";
import {
  LayoutDashboard, FileText, AlertTriangle, ClipboardCheck,
  Settings, Users, BarChart3, Bell, LogOut, ChevronRight,
} from "lucide-react";
import { useSessionStore } from "@/lib/stores/session";
import { useAlertStore } from "@/lib/stores/alerts";
import { useAlertFeed } from "@/lib/hooks/useAlertFeed";
import { api } from "@/lib/api";

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

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const { user, hasRole, clearUser } = useSessionStore();
  const { unreadCount } = useAlertStore();
  const pathname = usePathname();
  const router = useRouter();

  // Connect WebSocket feed
  useAlertFeed();

  const handleLogout = async () => {
    try { await api.delete("/api/v1/auth/logout"); } catch { /* ignore */ }
    clearUser();
    router.push("/login");
  };

  const navItems = NAV_ITEMS.filter(
    (item) => item.roles.length === 0 || hasRole(...item.roles)
  );

  return (
    <div className="flex h-screen bg-gray-50 overflow-hidden">
      {/* Sidebar */}
      <aside className="w-64 bg-[#1F3864] text-white flex flex-col shadow-xl">
        {/* Logo */}
        <div className="px-6 py-5 border-b border-white/10">
          <span className="text-xl font-bold tracking-tight">GovGuard™</span>
          <p className="text-xs text-blue-200 mt-0.5">Grant Compliance Platform</p>
        </div>

        {/* Navigation */}
        <nav className="flex-1 overflow-y-auto py-4">
          {navItems.map((item) => {
            const active = pathname.startsWith(item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`flex items-center gap-3 px-6 py-3 text-sm transition-colors
                  ${active
                    ? "bg-[#2E75B6] text-white font-medium"
                    : "text-blue-100 hover:bg-white/10"
                  }`}
              >
                <item.icon className="w-4 h-4" />
                {item.label}
                {active && <ChevronRight className="w-3 h-3 ml-auto" />}
              </Link>
            );
          })}
        </nav>

        {/* User info */}
        <div className="px-6 py-4 border-t border-white/10">
          {user && (
            <div className="flex items-center justify-between">
              <div className="min-w-0">
                <p className="text-sm font-medium text-white truncate">{user.displayName}</p>
                <p className="text-xs text-blue-300 capitalize">
                  {user.role.replace("_", " ")}
                </p>
              </div>
              <button
                onClick={handleLogout}
                className="p-1.5 rounded hover:bg-white/10 text-blue-200 hover:text-white transition-colors"
                title="Sign out"
              >
                <LogOut className="w-4 h-4" />
              </button>
            </div>
          )}
        </div>
      </aside>

      {/* Main content */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Top nav */}
        <header className="bg-white border-b border-gray-200 px-6 py-3 flex items-center justify-between shadow-sm">
          <div />
          <div className="flex items-center gap-4">
            <Link href="/notifications" className="relative p-2 rounded-full hover:bg-gray-100 transition-colors">
              <Bell className="w-5 h-5 text-gray-600" />
              {unreadCount > 0 && (
                <span className="absolute -top-0.5 -right-0.5 w-4 h-4 bg-red-500 rounded-full text-white text-[10px] flex items-center justify-center font-bold">
                  {unreadCount > 9 ? "9+" : unreadCount}
                </span>
              )}
            </Link>
          </div>
        </header>

        {/* Page content */}
        <main className="flex-1 overflow-y-auto p-6">
          {children}
        </main>
      </div>
    </div>
  );
}
