import { withMiddlewareAuthRequired, getSession } from "@auth0/nextjs-auth0/edge";
import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

export default withMiddlewareAuthRequired(async function middleware(req: NextRequest) {
  const res = NextResponse.next();
  const session = await getSession(req, res);
  if (!session) {
    return NextResponse.redirect(new URL("/api/auth/login", req.url));
  }
  return res;
});

export const config = {
  matcher: [
    "/dashboard/:path*",
    "/grants/:path*",
    "/fraud/:path*",
    "/audit/:path*",
    "/integrations/:path*",
    "/settings/:path*",
    "/admin/:path*",
  ],
};
