import { auth0 } from "@/lib/auth";
import { NextRequest, NextResponse } from "next/server";

export const runtime = "nodejs";

const RAILWAY_URL = process.env.RAILWAY_API_URL || process.env.NEXT_PUBLIC_API_URL || "";
const SERVICE_SECRET = process.env.SERVICE_SECRET || "";

async function proxy(request: NextRequest, { params }: { params: { path: string[] } }) {
  const session = await auth0.getSession(request);
  if (!session?.user) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const user = session.user;
  const role = (user["https://govguard.app/role"] as string) || "finance_staff";
  const tenantId = (user["https://govguard.app/tenant_id"] as string) || "00000000-0000-0000-0000-000000000001";
  const userId = (user["https://govguard.app/user_id"] as string) || user.sub;

  const path = params.path.join("/");
  const search = request.nextUrl.search;
  const upstreamUrl = `${RAILWAY_URL}/api/v2/${path}${search}`;

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    "Accept": "application/json",
    "X-Service-Secret": SERVICE_SECRET,
    "X-Tenant-ID": tenantId,
    "X-User-ID": userId,
    "X-User-Role": role,
  };

  const body = request.method !== "GET" && request.method !== "HEAD"
    ? await request.text()
    : undefined;

  const res = await fetch(upstreamUrl, {
    method: request.method,
    headers,
    body,
  });

  const data = res.status === 204 ? null : await res.json().catch(() => null);
  return NextResponse.json(data, { status: res.status });
}

export const GET    = proxy;
export const POST   = proxy;
export const PATCH  = proxy;
export const PUT    = proxy;
export const DELETE = proxy;
