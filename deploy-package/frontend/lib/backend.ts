/**
 * GovGuard™ — Railway Backend Proxy Helper
 * Forwards authenticated requests from Next.js API routes to the FastAPI backend.
 */
import { auth0 } from "@/lib/auth";

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8000";
const SERVICE_SECRET = process.env.SERVICE_SECRET || "";

export interface BackendProxyOptions {
  method?: string;
  body?: unknown;
}

export async function backendProxy(
  path: string,
  options: BackendProxyOptions = {}
): Promise<Response> {
  const session = await auth0.getSession();
  if (!session?.user) {
    return Response.json({ error: "Unauthorized" }, { status: 401 });
  }

  const user = session.user;
  const tenantId = user["https://govguard.app/tenant_id"] || "00000000-0000-0000-0000-000000000001";
  const userId = user["https://govguard.app/user_id"] || user.sub;
  const role = user["https://govguard.app/role"] || "finance_staff";

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    "X-Service-Secret": SERVICE_SECRET,
    "X-Tenant-ID": tenantId,
    "X-User-ID": userId,
    "X-User-Role": role,
  };

  try {
    const res = await fetch(`${BACKEND_URL}${path}`, {
      method: options.method || "GET",
      headers,
      body: options.body ? JSON.stringify(options.body) : undefined,
    });

    const data = await res.json();
    return Response.json(data, { status: res.status });
  } catch (error) {
    console.error(`Backend proxy error [${path}]:`, error);
    return Response.json({ error: "Backend unavailable" }, { status: 502 });
  }
}
