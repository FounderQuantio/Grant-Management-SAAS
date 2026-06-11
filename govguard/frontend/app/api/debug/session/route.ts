import { auth0 } from "@/lib/auth";
import { NextRequest, NextResponse } from "next/server";
import { cookies } from "next/headers";

export const runtime = "nodejs";

export async function GET(request: NextRequest) {
  const cookieStore = cookies();
  const allCookies = cookieStore.getAll().map(c => c.name);

  let sessionWithReq = null;
  let sessionNoArg = null;
  let errorWithReq = null;
  let errorNoArg = null;

  try {
    sessionWithReq = await auth0.getSession(request);
  } catch (e) {
    errorWithReq = String(e);
  }

  try {
    sessionNoArg = await auth0.getSession();
  } catch (e) {
    errorNoArg = String(e);
  }

  return NextResponse.json({
    cookies: allCookies,
    sessionWithReq: sessionWithReq ? { user: sessionWithReq.user?.email } : null,
    sessionNoArg: sessionNoArg ? { user: sessionNoArg.user?.email } : null,
    errorWithReq,
    errorNoArg,
    env: {
      AUTH0_DOMAIN: process.env.AUTH0_DOMAIN ? "set" : "missing",
      AUTH0_CLIENT_ID: process.env.AUTH0_CLIENT_ID ? "set" : "missing",
      AUTH0_CLIENT_SECRET: process.env.AUTH0_CLIENT_SECRET ? "set" : "missing",
      AUTH0_SECRET: process.env.AUTH0_SECRET ? "set" : "missing",
      AUTH0_BASE_URL: process.env.AUTH0_BASE_URL || "missing",
    },
  });
}
