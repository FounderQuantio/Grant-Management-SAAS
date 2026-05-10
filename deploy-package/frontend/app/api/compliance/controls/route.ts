import { getSession } from "@auth0/nextjs-auth0";
import { sql } from "@/lib/db";
import { NextRequest } from "next/server";

export const runtime = "nodejs";

export async function GET(req: NextRequest) {
  const session = await getSession();
  if (!session?.user) return Response.json({ error: "Unauthorized" }, { status: 401 });
  const tenantId = session.user["https://govguard.app/tenant_id"] || "00000000-0000-0000-0000-000000000001";

  const grantId = req.nextUrl.searchParams.get("grant_id");
  const status = req.nextUrl.searchParams.get("status");
  const domain = req.nextUrl.searchParams.get("domain");

  const rows = await sql`
    SELECT id, grant_id, control_code, cfr_clause, domain, status, last_tested, evidence_url, remediation_note, updated_at
    FROM compliance_controls
    WHERE tenant_id = ${tenantId}::UUID
      ${grantId ? sql`AND grant_id = ${grantId}::UUID` : sql``}
      ${status ? sql`AND status = ${status}` : sql``}
      ${domain ? sql`AND domain = ${domain}` : sql``}
    ORDER BY domain, control_code
  `;

  const total = rows.length;
  const passing = rows.filter((r: Record<string, unknown>) => r.status === "pass").length;
  const failing = rows.filter((r: Record<string, unknown>) => r.status === "fail").length;
  const score = total > 0 ? parseFloat(((passing / total) * 100).toFixed(2)) : 0;

  return Response.json({ controls: rows, score, total, passing, failing });
}
