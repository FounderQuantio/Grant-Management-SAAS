import { auth0 } from "./lib/auth";
import type { NextRequest } from "next/server";

export async function middleware(request: NextRequest) {
  return auth0.middleware(request);
}

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
