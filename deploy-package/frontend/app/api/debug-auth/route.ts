import { NextResponse } from "next/server";
import { auth0 } from "@/lib/auth";
import crypto from "crypto";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET() {
  const domain = process.env.AUTH0_DOMAIN;

  const env = {
    AUTH0_DOMAIN: domain ?? "*** MISSING ***",
    AUTH0_CLIENT_ID: process.env.AUTH0_CLIENT_ID ? "set" : "*** MISSING ***",
    AUTH0_CLIENT_SECRET: process.env.AUTH0_CLIENT_SECRET ? "set" : "*** MISSING ***",
    AUTH0_SECRET: process.env.AUTH0_SECRET ? "set" : "*** MISSING ***",
    APP_BASE_URL: process.env.APP_BASE_URL ?? "(not set — will infer from request)",
    BACKEND_URL: process.env.BACKEND_URL ?? "(not set — using localhost:8000)",
    NODE_ENV: process.env.NODE_ENV,
  };

  let discovery: string;
  if (!domain) {
    discovery = "skipped — AUTH0_DOMAIN missing";
  } else {
    try {
      const url = `https://${domain}/.well-known/openid-configuration`;
      const res = await fetch(url, { signal: AbortSignal.timeout(10000) });
      discovery = res.ok ? `OK (${res.status})` : `FAILED: ${res.status} ${res.statusText}`;
    } catch (e) {
      discovery = `ERROR: ${e instanceof Error ? e.message : String(e)}`;
    }
  }

  // Session info — shows the sub and email needed for users table INSERT
  let session_info: Record<string, string> | null = null;
  let sql_insert: string | null = null;
  try {
    const session = await auth0.getSession();
    if (session?.user) {
      const u = session.user;
      const email = u.email || "";
      const emailHash = crypto.createHash("sha256").update(email).digest("hex");
      const sub = u.sub || "";
      session_info = {
        sub,
        email,
        email_hash: emailHash,
        name: u.name || "",
        role_claim: u["https://govguard.app/role"] as string || "(not set)",
        tenant_claim: u["https://govguard.app/tenant_id"] as string || "(not set)",
      };
      sql_insert = `INSERT INTO users (tenant_id, cognito_sub, email_hash, display_name, role)
VALUES (
  '00000000-0000-0000-0000-000000000001',
  '${sub}',
  '${emailHash}',
  '${(u.name || email).replace(/'/g, "''")}',
  'system_admin'
)
ON CONFLICT (cognito_sub) DO UPDATE
  SET display_name = EXCLUDED.display_name,
      role = EXCLUDED.role;`;
    }
  } catch {
    session_info = null;
  }

  return NextResponse.json({ env, discovery, session_info, sql_insert });
}
