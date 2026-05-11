import { auth0 } from "@/lib/auth";
import { NextRequest, NextResponse } from "next/server";

export const runtime = "nodejs";

async function handler(request: NextRequest): Promise<NextResponse> {
  const url = new URL(request.url);
  const segment = url.pathname.split("/").pop();

  if (segment === "login") return auth0.handleLogin(request);
  if (segment === "logout") return auth0.handleLogout(request);
  if (segment === "callback") return auth0.handleCallback(request);

  return NextResponse.json({ error: "Not found" }, { status: 404 });
}

export const GET = handler;
export const POST = handler;
