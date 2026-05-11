import { auth0 } from "@/lib/auth";
import { NextRequest, NextResponse } from "next/server";

export const runtime = "nodejs";

async function handler(request: NextRequest) {
  try {
    return await auth0.middleware(request);
  } catch (err) {
    console.error("[auth0] route handler error:", err);
    return NextResponse.redirect(new URL("/login", request.url));
  }
}

export const GET = handler;
export const POST = handler;
