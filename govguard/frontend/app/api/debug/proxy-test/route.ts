import { auth0 } from "@/lib/auth";
import { NextRequest, NextResponse } from "next/server";

export const runtime = "nodejs";

const RAILWAY_URL = process.env.RAILWAY_API_URL || process.env.NEXT_PUBLIC_API_URL || "";
const SERVICE_SECRET = process.env.SERVICE_SECRET || "";

export async function GET(request: NextRequest) {
  let session = null;
  let sessionError = null;

  try {
    session = await auth0.getSession(request);
  } catch (e) {
    sessionError = String(e);
  }

  const user = session?.user;
  const tenantId = (user?.["https://govguard.app/tenant_id"] as string) || "00000000-0000-0000-0000-000000000001";
  const role = (user?.["https://govguard.app/role"] as string) || "finance_staff";
  const userId = (user?.["https://govguard.app/user_id"] as string) || user?.sub || "";

  // Try an actual call to Railway
  let railwayStatus = null;
  let railwayBody = null;
  if (session?.user) {
    try {
      const res = await fetch(`${RAILWAY_URL}/api/v1/dashboard/kpis?period=30d`, {
        headers: {
          "Content-Type": "application/json",
          "Accept": "application/json",
          "X-Service-Secret": SERVICE_SECRET,
          "X-Tenant-ID": tenantId,
          "X-User-ID": userId,
          "X-User-Role": role,
        },
      });
      railwayStatus = res.status;
      railwayBody = await res.json().catch(() => null);
    } catch (e) {
      railwayBody = String(e);
    }
  }

  return NextResponse.json({
    hasSession: !!session,
    sessionError,
    userEmail: user?.email ?? null,
    tenantId,
    role,
    userId,
    serviceSecretSet: !!SERVICE_SECRET,
    railwayUrl: RAILWAY_URL,
    railwayStatus,
    railwayBody,
  });
}
