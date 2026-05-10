import { handleAuth, handleLogin, handleCallback } from "@auth0/nextjs-auth0";
import { NextRequest } from "next/server";

export const GET = handleAuth({
  login: handleLogin({
    authorizationParams: {
      audience: process.env.AUTH0_AUDIENCE,
      scope: "openid profile email",
    },
    returnTo: "/dashboard",
  }),
  callback: handleCallback({
    afterCallback: async (_req, session) => {
      // Sync user to DB on first login
      try {
        const { sql } = await import("@/lib/db");
        const user = session.user;
        const role = user["https://govguard.app/role"] || "finance_staff";
        const tenantId = user["https://govguard.app/tenant_id"] || "00000000-0000-0000-0000-000000000001";
        await sql`
          INSERT INTO users (auth0_sub, tenant_id, email, display_name, role, last_login)
          VALUES (${user.sub}, ${tenantId}::UUID, ${user.email || ""}, ${user.name || ""}, ${role}, NOW())
          ON CONFLICT (auth0_sub) DO UPDATE SET last_login = NOW(), display_name = ${user.name || ""}
        `;
      } catch (e) {
        console.error("DB sync error:", e);
      }
      return session;
    },
  }),
});
