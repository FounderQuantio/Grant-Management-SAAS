import { Auth0Client } from "@auth0/nextjs-auth0/server";
import { NextRequest, NextResponse } from "next/server";

export const runtime = "nodejs";

async function handler(request: NextRequest) {
  // Derive appBaseUrl from the incoming request so that the Auth0 callback
  // URL always matches the domain the user is actually on (works for any
  // Vercel preview URL without needing them all registered in Auth0).
  const appBaseUrl = request.nextUrl.origin;

  const client = new Auth0Client({
    appBaseUrl,
    routes: {
      login: "/api/auth/login",
      logout: "/api/auth/logout",
      callback: "/api/auth/callback",
    },
  });

  try {
    return await client.middleware(request);
  } catch (err) {
    console.error("[auth0] thrown error:", err);
    return NextResponse.redirect(new URL("/", request.url));
  }
}

export const GET = handler;
export const POST = handler;
