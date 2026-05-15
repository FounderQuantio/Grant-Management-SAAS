import { Auth0Client } from "@auth0/nextjs-auth0/server";
import { NextRequest, NextResponse } from "next/server";

export const runtime = "nodejs";

async function handler(request: NextRequest) {
  const proto = request.headers.get("x-forwarded-proto") ?? request.nextUrl.protocol.replace(":", "");
  const host = request.headers.get("x-forwarded-host") ?? request.nextUrl.host;
  const appBaseUrl = `${proto}://${host}`;

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
      console.error("[auth0] error response:", res.status, body.slice(0, 500));
      return NextResponse.json({ error: "Auth error", status: res.status, body: body.slice(0, 500) }, { status: res.status });
    }

    return res;
  } catch (err) {
    console.error("[auth0] thrown error:", err);
    return NextResponse.json({ error: String(err) }, { status: 500 });
  }
}

export const GET = handler;
export const POST = handler;
