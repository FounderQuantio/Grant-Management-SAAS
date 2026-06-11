import { auth0 } from "@/lib/auth";
import { type NextRequest, NextResponse } from "next/server";

const PUBLIC_PATHS = ["/login", "/api/auth", "/api/debug"];

function isPublic(pathname: string): boolean {
  return PUBLIC_PATHS.some(
    (p) => pathname === p || pathname.startsWith(p + "/")
  );
}

export async function middleware(req: NextRequest) {
  try {
    const authRes = await auth0.middleware(req);

    // Auth0 middleware already issued a redirect (callback, logout, etc.) — honour it
    if (authRes.status === 302 || authRes.status === 307) return authRes;

    // Public routes: login page, auth callbacks, debug endpoints
    if (isPublic(req.nextUrl.pathname)) return authRes;

    // Protected route — verify a session exists
    const session = await auth0.getSession(req);
    if (!session?.user) {
      const loginUrl = new URL("/login", req.url);
      loginUrl.searchParams.set("returnTo", req.nextUrl.pathname);
      return NextResponse.redirect(loginUrl);
    }

    return authRes;
  } catch (err) {
    console.error("[auth0] middleware error:", err);
    const loginUrl = new URL("/login", req.url);
    return NextResponse.redirect(loginUrl);
  }
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon\\.ico).*)"],
};
