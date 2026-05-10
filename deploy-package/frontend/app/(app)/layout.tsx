"use client";
import { useUser } from "@auth0/nextjs-auth0/client";
import { useRouter, usePathname } from "next/navigation";
import Link from "next/link";
import { useEffect } from "react";
import {
  LayoutDashboard, FileText, AlertTriangle, ClipboardCheck,
  Settings, Users, Bell, LogOut, ChevronRight, Shield,
} from "lucide-react";

const NAV = [
  { href: "/dashboard",       icon: LayoutDashboard, label: "Dashboard" },
  { href: "/grants",          icon: FileText,        label: "Grants" },
  { href: "/fraud/pre-award", icon: AlertTriangle,   label: "Fraud Screen" },
  { href: "/audit",           icon: ClipboardCheck,  label: "Audit & CAP" },
  { href: "/settings/users",  icon: Users,           label: "Users" },
];

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const { user, isLoading } = useUser();
  const pathname = usePathname();
  const router = useRouter();

  useEffect(() => {
    if (!isLoading && !user) router.push("/api/auth/login");
  }, [user, isLoading, router]);

  if (isLoading) {
    return (
      <div className="min-h-screen bg-[#1F3864] flex items-center justify-center">
        <div className="text-center text-white">
          <Shield className="w-12 h-12 mx-auto mb-4 animate-pulse" />
          <p className="text-blue-200">Loading GovGuard™...</p>
        </div>
      </div>
    );
  }

  if (!user) return null;

  return (
    <div className="flex h-screen bg-gray-50 overflow-hidden">
      <aside className="w-64 bg-[#1F3864] flex flex-col shadow-xl">
        <div className="px-6 py-5 border-b border-white/10">
          <div className="flex items-center gap-2">
            <Shield className="w-6 h-6 text-blue-300" />
            <span className="text-xl font-bold text-white tracking-tight">GovGuard™</span>
          </div>
          <p className="text-xs text-blue-300 mt-1 ml-8">Grant Compliance Platform</p>
        </div>

        <nav className="flex-1 overflow-y-auto py-4">
          {NAV.map((item) => {
            const active = pathname.startsWith(item.href);
            return (
              <Link key={item.href} href={item.href}
                className={"flex items-center gap-3 px-6 py-3 text-sm transition-all " +
                  (active ? "bg-[#2E75B6] text-white font-medium shadow-sm" : "text-blue-100 hover:bg-white/10 hover:text-white")}>
                <item.icon className="w-4 h-4 flex-shrink-0" />
                <span>{item.label}</span>
                {active && <ChevronRight className="w-3 h-3 ml-auto opacity-70" />}
              </Link>
            );
          })}
        </nav>

        <div className="px-6 py-4 border-t border-white/10">
          <div className="flex items-center justify-between">
            <div className="min-w-0">
              <p className="text-sm font-medium text-white truncate">{user.name}</p>
              <p className="text-xs text-blue-300 truncate">{user.email}</p>
            </div>
            <a href="/api/auth/logout"
              className="p-1.5 rounded-lg hover:bg-white/10 text-blue-300 hover:text-white transition-colors"
              title="Sign out">
              <LogOut className="w-4 h-4" />
            </a>
          </div>
        </div>
      </aside>

      <div className="flex-1 flex flex-col overflow-hidden">
        <header className="bg-white border-b border-gray-200 px-6 py-3 flex items-center justify-between shadow-sm">
          <div className="text-sm text-gray-500 font-medium capitalize">
            {pathname.split("/")[1] || "Dashboard"}
          </div>
          <div className="flex items-center gap-3">
            <button className="relative p-2 rounded-full hover:bg-gray-100 transition-colors">
              <Bell className="w-5 h-5 text-gray-500" />
            </button>
          </div>
        </header>
        <main className="flex-1 overflow-y-auto p-6">
          {children}
        </main>
      </div>
    </div>
  );
}
