import { NextRequest, NextResponse } from "next/server";

export async function POST(request: NextRequest) {
  const refreshToken = request.cookies.get("gg_refresh")?.value;
  if (!refreshToken) {
    return NextResponse.json({ error: "No refresh token" }, { status: 401 });
  }

  try {
    const apiUrl = process.env.API_URL || "http://backend:8000";
    const res = await fetch(`${apiUrl}/api/v1/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });

    if (!res.ok) {
      return NextResponse.json({ error: "Refresh failed" }, { status: 401 });
    }

    const { access_token, expires_in } = await res.json();
    const response = NextResponse.json({ ok: true });
    response.cookies.set("gg_access", access_token, {
      httpOnly: true,
      secure: process.env.NODE_ENV === "production",
      sameSite: "strict",
      maxAge: expires_in || 900,
      path: "/",
    });
    return response;
  } catch {
    return NextResponse.json({ error: "Refresh error" }, { status: 500 });
  }
}
