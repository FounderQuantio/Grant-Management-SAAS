import { auth0 } from "@/lib/auth";
import { NextRequest, NextResponse } from "next/server";
import { cookies } from "next/headers";

export const runtime = "nodejs";

function decodeJwt(token: string) {
  try {
    const [, payload] = token.split(".");
    return JSON.parse(Buffer.from(payload, "base64url").toString());
  } catch {
    return null;
  }
}

export async function GET(request: NextRequest) {
  const cookieStore = cookies();
  const allCookies = cookieStore.getAll().map(c => c.name);

  let session = null;
  let sessionError = null;
  let accessTokenClaims = null;
  let accessTokenError = null;

  try {
    session = await auth0.getSession(request);
  } catch (e) {
    sessionError = String(e);
  }

  try {
    const tokenResult = await auth0.getAccessToken(request);
    if (tokenResult?.token) {
      accessTokenClaims = decodeJwt(tokenResult.token);
    }
  } catch (e) {
    accessTokenError = String(e);
  }

  return NextResponse.json({
    cookies: allCookies,
    sessionUser: session?.user ?? null,
    accessTokenClaims,
    sessionError,
    accessTokenError,
    env: {
      AUTH0_DOMAIN: process.env.AUTH0_DOMAIN ? "set" : "missing",
      AUTH0_CLIENT_ID: process.env.AUTH0_CLIENT_ID ? "set" : "missing",
      AUTH0_CLIENT_SECRET: process.env.AUTH0_CLIENT_SECRET ? "set" : "missing",
      AUTH0_SECRET: process.env.AUTH0_SECRET ? "set" : "missing",
      AUTH0_BASE_URL: process.env.AUTH0_BASE_URL || "missing",
    },
  });
}
