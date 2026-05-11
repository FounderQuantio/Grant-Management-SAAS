import { auth0 } from "@/lib/auth";
import { NextRequest, NextResponse } from "next/server";

export const runtime = "nodejs";

async function handler(request: NextRequest) {
  console.log("[auth0] handler called:", request.method, new URL(request.url).pathname);
  console.log("[auth0] env:", {
    AUTH0_DOMAIN: process.env.AUTH0_DOMAIN ?? "MISSING",
    AUTH0_CLIENT_ID: process.env.AUTH0_CLIENT_ID ? "set" : "MISSING",
    AUTH0_CLIENT_SECRET: process.env.AUTH0_CLIENT_SECRET ? "set" : "MISSING",
    AUTH0_SECRET: process.env.AUTH0_SECRET ? "set" : "MISSING",
    APP_BASE_URL: process.env.APP_BASE_URL ?? "not set",
  });
  try {
    const res = await auth0.middleware(request);
    if (res.status >= 500) {
      const body = await res.clone().text().catch(() => "");
      console.error("[auth0] returned error response:", res.status, body);
    }
    return res;
  } catch (err) {
    console.error("[auth0] thrown error:", err);
    return NextResponse.redirect(new URL("/login", request.url));
  }
}

export const GET = handler;
export const POST = handler;
