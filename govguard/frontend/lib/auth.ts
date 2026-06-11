import type { NextRequest } from "next/server";
import { Auth0Client } from "@auth0/nextjs-auth0/server";

const appBaseUrl =
  process.env.VERCEL_ENV === "preview" && process.env.VERCEL_URL
    ? `https://${process.env.VERCEL_URL}`
    : process.env.APP_BASE_URL;

export const auth0 = new Auth0Client({
  appBaseUrl,
  routes: {
    login: "/api/auth/login",
    logout: "/api/auth/logout",
    callback: "/api/auth/callback",
  },
});

export interface GovGuardUser {
  sub: string;
  email: string;
  name: string;
  role: string;
  tenantId: string;
  userId: string;
}

const ROLE_LEVELS: Record<string, number> = {
  system_admin: 7,
  agency_officer: 6,
  compliance_officer: 5,
  finance_manager: 4,
  finance_staff: 3,
  auditor: 2,
  equity_analyst: 1,
};

export async function getCurrentUser(req: NextRequest): Promise<GovGuardUser | null> {
  try {
    const session = await auth0.getSession();
    if (!session?.user) return null;
    const user = session.user;
    return {
      sub: user.sub,
      email: user.email || "",
      name: user.name || "",
      role: (user["https://govguard.app/role"] as string) || "finance_staff",
      tenantId: (user["https://govguard.app/tenant_id"] as string) || "",
      userId: (user["https://govguard.app/user_id"] as string) || user.sub,
    };
  } catch {
    return null;
  }
}

export function hasRole(userRole: string, ...requiredRoles: string[]): boolean {
  const userLevel = ROLE_LEVELS[userRole] || 0;
  const requiredLevel = Math.max(...requiredRoles.map((r) => ROLE_LEVELS[r] || 0));
  return userLevel >= requiredLevel;
}
