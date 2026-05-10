"use server";
/**
 * GovGuard™ — Auth0 Server Helpers
 * Wraps @auth0/nextjs-auth0 with GovGuard role extraction.
 */
import { getSession, withApiAuthRequired } from "@auth0/nextjs-auth0";
import type { NextRequest } from "next/server";

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
    const session = await getSession();
    if (!session?.user) return null;
    const user = session.user;
    return {
      sub: user.sub,
      email: user.email || "",
      name: user.name || "",
      // Auth0 custom claims namespace
      role: user["https://govguard.app/role"] || "finance_staff",
      tenantId: user["https://govguard.app/tenant_id"] || "",
      userId: user["https://govguard.app/user_id"] || user.sub,
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

export class APIError extends Error {
  constructor(public status: number, public code: string, message: string) {
    super(message);
  }
}

export function unauthorized() {
  return Response.json(
    { error_code: "UNAUTHORIZED", message: "Authentication required" },
    { status: 401 }
  );
}

export function forbidden(message = "Insufficient permissions") {
  return Response.json(
    { error_code: "FORBIDDEN", message },
    { status: 403 }
  );
}

export function notFound(message = "Resource not found") {
  return Response.json(
    { error_code: "NOT_FOUND", message },
    { status: 404 }
  );
}

export function serverError(message = "Internal server error") {
  return Response.json(
    { error_code: "INTERNAL_ERROR", message },
    { status: 500 }
  );
}

export function ok<T>(data: T, status = 200) {
  return Response.json(data, { status });
}

export function created<T>(data: T) {
  return Response.json(data, { status: 201 });
}
