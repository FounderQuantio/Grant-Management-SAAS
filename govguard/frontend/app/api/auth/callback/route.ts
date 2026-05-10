import { NextRequest, NextResponse } from "next/server";

export async function GET(request: NextRequest) {
  const code = request.nextUrl.searchParams.get("code");
  const returnTo = request.nextUrl.searchParams.get("state") || "/dashboard";

  if (!code) {
    return NextResponse.redirect(new URL("/login?error=no_code", request.url));
  }

  try {
    const apiUrl = process.env.API_URL || "http://backend:8000";
    const res = await fetch(`${apiUrl}/api/v1/auth/token`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        code,
        redirect_uri: `${process.env.NEXT_PUBLIC_APP_URL}/api/auth/callback`,
      }),
    });

    if (!res.ok) throw new Error("Token exchange failed");
    const { access_token, id_token, refresh_token } = await res.json();

    const response = NextResponse.redirect(new URL(returnTo, request.url));

    // Set HttpOnly secure cookies
    const cookieOptions = {
      httpOnly: true,
      secure: process.env.NODE_ENV === "production",
      sameSite: "strict" as const,
      path: "/",
    };
    response.cookies.set("gg_access",  access_token,  { ...cookieOptions, maxAge: 900 });
    response.cookies.set("gg_id",      id_token,      { ...cookieOptions, maxAge: 900 });
    response.cookies.set("gg_refresh", refresh_token, { ...cookieOptions, maxAge: 2592000 });

    return response;
  } catch {
    return NextResponse.redirect(new URL("/login?error=auth_failed", request.url));
  }
}
