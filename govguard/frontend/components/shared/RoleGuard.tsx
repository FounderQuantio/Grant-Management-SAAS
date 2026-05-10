"use client";
import { useSessionStore } from "@/lib/stores/session";

interface RoleGuardProps {
  roles: string[];
  children: React.ReactNode;
  fallback?: React.ReactNode;
}

export function RoleGuard({ roles, children, fallback = null }: RoleGuardProps) {
  const hasRole = useSessionStore((s) => s.hasRole);
  return hasRole(...roles) ? <>{children}</> : <>{fallback}</>;
}
