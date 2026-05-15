import { Auth0Client } from "@auth0/nextjs-auth0/server";
import { NextRequest, NextResponse } from "next/server";

export const runtime = "nodejs";

async function handler(request: NextRequest) {
  const xProto = request.headers.get("x-forwarded-proto");
  const xHost = request.headers.get("x-forwarded-host");
  const proto = xProto ?? request.nextUrl.protocol.replace(":", "");
  const host = xHost ?? request.nextUrl.host;
  const appBaseUrl = `${proto}://${host}`;
  const pathname = request.nextUrl.pathname;

  // Debug mode: ?debug=1 returns diagnostic info instead of running auth
  if (request.nextUrl.searchParams.get("debug") === "1") {
    return NextResponse.json({
      pathname,
      appBaseUrl,
      xProto,
      xHost,
      nextUrlOrigin: request.nextUrl.origin,
      envAppBaseUrl: process.env.APP_BASE_URL ?? null,
      envVercelEnv: process.env.VERCEL_ENV ?? null,
    });
  }

  try {
    const client = new Auth0Client({
      appBaseUrl,
      routes: {
        login: "/api/auth/login",
        logout: "/api/auth/logout",
        callback: "/api/auth/callback",
      },
    });

    const res = await client.middleware(request);

    if (res.status >= 400) {
      const body = await res.clone().text().catch(() => "");
      return NextResponse.json({ error: "Auth error", status: res.status, body: body.slice(0, 500) }, { status: res.status });
    }

    // Show redirect target instead of following it — helps diagnose where we're going
    const location = res.headers.get("location");
    if (location) {
      console.log("[auth0] redirecting to:", location);
    }

    return res;
  } catch (err) {
    console.error("[auth0] thrown error:", err);
    return NextResponse.json({ error: String(err) }, { status: 500 });
  }
}

export const GET = handler;
export const POST = handler;
