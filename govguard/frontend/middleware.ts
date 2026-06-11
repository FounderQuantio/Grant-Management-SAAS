import { auth0 } from "@/lib/auth";
import { type NextRequest, NextResponse } from "next/server";

export async function middleware(req: NextRequest) {
  try {
    return await auth0.middleware(req);
  } catch (err) {
    console.error("[auth0] middleware error:", err);
    const loginUrl = new URL("/api/auth/login", req.url);
    loginUrl.searchParams.set("returnTo", req.nextUrl.pathname);
    return NextResponse.redirect(loginUrl);
  }
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon\\.ico|api/auth).*)"],
};
