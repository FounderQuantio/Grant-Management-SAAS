import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

const PUBLIC_PATHS = [
  "/login",
  "/api/auth/callback",
  "/api/auth/refresh",
];

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // Allow public paths
  if (PUBLIC_PATHS.some((p) => pathname.startsWith(p))) {
    return NextResponse.next();
  }

  // Health check
  if (pathname === "/health") {
    return NextResponse.json({ status: "ok" });
  }

  // Check for auth token cookie
  const accessToken = request.cookies.get("gg_access")?.value;
  if (!accessToken) {
    const loginUrl = new URL("/login", request.url);
    loginUrl.searchParams.set("return_to", pathname);
    return NextResponse.redirect(loginUrl);
  }

  // Token expiry check (basic - full validation in API routes)
  try {
    const [, payload] = accessToken.split(".");
    const claims = JSON.parse(Buffer.from(payload, "base64url").toString());
    const now = Math.floor(Date.now() / 1000);
    if (claims.exp && claims.exp < now) {
      // Expired - redirect to login with return_to
      const loginUrl = new URL("/login", request.url);
      loginUrl.searchParams.set("return_to", pathname);
      loginUrl.searchParams.set("reason", "token_expired");
      return NextResponse.redirect(loginUrl);
    }
  } catch {
    const loginUrl = new URL("/login", request.url);
    return NextResponse.redirect(loginUrl);
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
