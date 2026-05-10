import { getSession } from "@auth0/nextjs-auth0";
import { sql } from "@/lib/db";
import { NextRequest } from "next/server";
import { createHash } from "crypto";

export const runtime = "nodejs";

export async function POST(req: NextRequest) {
  const session = await getSession();
  if (!session?.user) return Response.json({ error: "Unauthorized" }, { status: 401 });

  const tenantId = session.user["https://govguard.app/tenant_id"] || "00000000-0000-0000-0000-000000000001";

  try {
    const body = await req.json();
    const { applicant_name, ein, address, budget_json } = body;

    // Hash EIN for privacy
    const einHash = createHash("sha256").update(ein || "").digest("hex");

    // Check for existing vendor with same EIN (dedup)
    const existing = await sql`
      SELECT id, name, risk_score, sam_status FROM vendors
      WHERE tenant_id = ${tenantId}::UUID AND ein_hash = ${einHash}
      LIMIT 5
    `;

    // Heuristic budget reasonableness check
    const budgetFlags: string[] = [];
    if (budget_json) {
      const total = Object.values(budget_json as Record<string, number>).reduce((a: number, b: number) => a + b, 0);
      const adminPct = ((budget_json.admin || 0) / total) * 100;
      if (adminPct > 20) budgetFlags.push(`Administrative costs at ${adminPct.toFixed(1)}% exceeds 20% threshold`);
      if (total > 5000000) budgetFlags.push("Budget exceeds $5M — enhanced review required");
    }

    // Risk score calculation
    let riskScore = 20;
    if (existing.length > 0) riskScore += 15;
    if (budgetFlags.length > 0) riskScore += budgetFlags.length * 10;
    riskScore = Math.min(100, riskScore);

    // Upsert vendor record
    await sql`
      INSERT INTO vendors (tenant_id, ein_hash, name, risk_score)
      VALUES (${tenantId}::UUID, ${einHash}, ${applicant_name || "Unknown"}, ${riskScore})
      ON CONFLICT DO NOTHING
    `;

    return Response.json({
      risk_score: riskScore,
      dnp_match: false,  // SAM.gov check — stubbed (configure SAM_GOV_API_KEY to enable)
      dedup_matches: existing.map((v: Record<string, unknown>) => ({ id: v.id, name: v.name, risk_score: v.risk_score })),
      budget_flags: budgetFlags,
      recommendation: riskScore >= 70 ? "HIGH_RISK_REVIEW_REQUIRED" : riskScore >= 40 ? "ENHANCED_REVIEW" : "STANDARD_REVIEW",
    });
  } catch (error) {
    console.error("Screen error:", error);
    return Response.json({ error: "Screening failed" }, { status: 500 });
  }
}
