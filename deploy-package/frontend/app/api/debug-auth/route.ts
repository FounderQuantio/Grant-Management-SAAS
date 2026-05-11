import { NextResponse } from "next/server";

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

  return NextResponse.json({ env, discovery });
}
