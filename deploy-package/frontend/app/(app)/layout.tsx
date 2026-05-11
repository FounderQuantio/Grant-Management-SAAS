import { auth0 } from "@/lib/auth";
import { redirect } from "next/navigation";
import { sql } from "@/lib/db";
import AppShell from "./_shell";

export const dynamic = "force-dynamic";

export default async function AppLayout({ children }: { children: React.ReactNode }) {
  let session;
  try {
    session = await auth0.getSession();
  } catch (err) {
    console.error("[auth0] getSession error in app layout:", err);
    redirect("/login");
  }
  if (!session?.user) redirect("/api/auth/login");

  const user = session.user;
  try {
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

  return (
    <AppShell user={{ name: user.name as string, email: user.email as string }}>
      {children}
    </AppShell>
  );
}
