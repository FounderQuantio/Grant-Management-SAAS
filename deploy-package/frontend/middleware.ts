import { auth0 } from "./lib/auth";
import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

export async function middleware(request: NextRequest) {
  // This handles the authentication and routing automatically
  const authResponse = await auth0.middleware(request);
  
  // If the user is trying to access a protected route and isn't logged in,
  // authResponse will automatically redirect them to login.
  return authResponse;
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
