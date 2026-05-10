import { getSession } from "@auth0/nextjs-auth0";
import { sql } from "@/lib/db";
import { NextRequest } from "next/server";

export const runtime = "edge";

export async function GET(req: NextRequest) {
  const session = await getSession();
  if (!session?.user) {
    return Response.json({ error: "Unauthorized" }, { status: 401 });
  }

  const tenantId = session.user["https://govguard.app/tenant_id"] || "00000000-0000-0000-0000-000000000001";
  const period = req.nextUrl.searchParams.get("period") || "30d";
  const days = parseInt(period.replace("d", "")) || 30;

  try {
    const [complianceRows, findingsRows, flaggedRows, totalRows, grantRows] = await Promise.all([
      // Average compliance score
      sql`SELECT AVG(compliance_score) as avg_score
          FROM grants WHERE tenant_id = ${tenantId}::UUID AND status = 'active' AND compliance_score IS NOT NULL`,
      // Open findings
      sql`SELECT COUNT(*) as count FROM audit_findings
          WHERE tenant_id = ${tenantId}::UUID AND status = 'open'`,
      // Flagged transactions
      sql`SELECT COUNT(*) as count FROM transactions
          WHERE tenant_id = ${tenantId}::UUID
            AND flag_status NOT IN ('approved', 'rejected')
            AND created_at > NOW() - (${days} || ' days')::INTERVAL`,
      // Total transactions
      sql`SELECT COUNT(*) as count FROM transactions
          WHERE tenant_id = ${tenantId}::UUID
            AND created_at > NOW() - (${days} || ' days')::INTERVAL`,
      // Risk leaderboard
      sql`SELECT id, award_number, agency, COALESCE(compliance_score, 0) as compliance_score
          FROM grants WHERE tenant_id = ${tenantId}::UUID AND status = 'active'
          ORDER BY compliance_score ASC NULLS LAST LIMIT 8`,
    ]);

    const totalTx = Number(totalRows[0]?.count || 0);
    const flaggedTx = Number(flaggedRows[0]?.count || 0);

    return Response.json({
      improperPaymentRate: totalTx > 0 ? parseFloat(((flaggedTx / totalTx) * 100).toFixed(2)) : 0,
      complianceScore: parseFloat(Number(complianceRows[0]?.avg_score || 0).toFixed(1)),
      openFindings: Number(findingsRows[0]?.count || 0),
      flaggedTxCount: flaggedTx,
      totalTxCount: totalTx,
      periodDays: days,
      riskLeaderboard: grantRows.map((g: Record<string, unknown>) => ({
        grantId: g.id,
        awardNumber: g.award_number,
        agency: g.agency,
        complianceScore: parseFloat(String(g.compliance_score || 0)),
      })),
    });
  } catch (error) {
    console.error("KPI error:", error);
    return Response.json({ error: "Database error" }, { status: 500 });
  }
}
