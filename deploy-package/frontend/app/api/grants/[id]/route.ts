import { auth0 } from "@/lib/auth";
import { sql } from "@/lib/db";
import { NextRequest } from "next/server";

export const runtime = "nodejs";

export async function GET(
  _req: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const session = await auth0.getSession();
  if (!session?.user) return Response.json({ error: "Unauthorized" }, { status: 401 });

  const tenantId =
    session.user["https://govguard.app/tenant_id"] ||
    "00000000-0000-0000-0000-000000000001";

  const grants = await sql`
    SELECT id, award_number, agency, program_cfda, period_start, period_end,
           total_amount, status, compliance_score, budget_json, activated_at, created_at
    FROM grants
    WHERE id = ${id}::UUID AND tenant_id = ${tenantId}::UUID
    LIMIT 1
  `;
  if (!grants[0]) return Response.json({ error: "Not found" }, { status: 404 });

  const transactions = await sql`
    SELECT t.id, t.amount, t.invoice_ref, t.cost_category, t.tx_date,
           t.risk_score, t.flag_status, t.flag_reason, t.created_at,
           v.name AS vendor_name
    FROM transactions t
    JOIN vendors v ON v.id = t.vendor_id
    WHERE t.grant_id = ${id}::UUID AND t.tenant_id = ${tenantId}::UUID
    ORDER BY t.created_at DESC
    LIMIT 200
  `;

  const stats = await sql`
    SELECT
      COUNT(*) AS total,
      COUNT(*) FILTER (WHERE flag_status = 'flagged') AS flagged,
      COUNT(*) FILTER (WHERE flag_status = 'approved') AS approved,
      COALESCE(SUM(amount), 0) AS total_spend
    FROM transactions
    WHERE grant_id = ${id}::UUID AND tenant_id = ${tenantId}::UUID
  `;

  return Response.json({
    grant: grants[0],
    transactions,
    stats: stats[0],
  });
}
