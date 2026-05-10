import { getSession } from "@auth0/nextjs-auth0";
import { sql } from "@/lib/db";
import { NextRequest } from "next/server";
import { z } from "zod";

export const runtime = "nodejs";

const CreateTxSchema = z.object({
  grant_id: z.string().uuid(),
  vendor_id: z.string().uuid(),
  amount: z.number().positive(),
  invoice_ref: z.string().min(1).max(255),
  tx_date: z.string().regex(/^\d{4}-\d{2}-\d{2}$/),
  cost_category: z.string().min(1).max(100),
});

export async function GET(req: NextRequest) {
  const session = await getSession();
  if (!session?.user) return Response.json({ error: "Unauthorized" }, { status: 401 });

  const tenantId = session.user["https://govguard.app/tenant_id"] || "00000000-0000-0000-0000-000000000001";
  const params = req.nextUrl.searchParams;
  const grantId = params.get("grant_id");
  const flagStatus = params.get("flag_status");
  const page = Math.max(1, parseInt(params.get("page") || "1"));
  const limit = Math.min(200, parseInt(params.get("limit") || "50"));
  const offset = (page - 1) * limit;

  try {
    // Build query dynamically
    let whereClause = `WHERE t.tenant_id = ${tenantId}::UUID`;
    if (grantId) whereClause += ` AND t.grant_id = '${grantId}'::UUID`;
    if (flagStatus) whereClause += ` AND t.flag_status = '${flagStatus}'`;

    const rows = await sql`
      SELECT t.id, t.grant_id, t.vendor_id, t.amount, t.invoice_ref,
             t.cost_category, t.tx_date, t.risk_score, t.flag_status,
             t.flag_reason, t.reviewed_at, t.created_at,
             v.name as vendor_name
      FROM transactions t
      JOIN vendors v ON v.id = t.vendor_id
      WHERE t.tenant_id = ${tenantId}::UUID
      ORDER BY t.created_at DESC
      LIMIT ${limit} OFFSET ${offset}
    `;

    const countRows = await sql`
      SELECT COUNT(*) as count FROM transactions
      WHERE tenant_id = ${tenantId}::UUID
    `;

    return Response.json({
      transactions: rows,
      total: Number(countRows[0]?.count || 0),
      page,
      limit,
    });
  } catch (error) {
    console.error("Transaction list error:", error);
    return Response.json({ error: "Database error" }, { status: 500 });
  }
}

export async function POST(req: NextRequest) {
  const session = await getSession();
  if (!session?.user) return Response.json({ error: "Unauthorized" }, { status: 401 });

  const role = session.user["https://govguard.app/role"] || "finance_staff";
  if (!["system_admin", "compliance_officer", "finance_manager"].includes(role)) {
    return Response.json({ error: "Insufficient permissions" }, { status: 403 });
  }

  const tenantId = session.user["https://govguard.app/tenant_id"] || "00000000-0000-0000-0000-000000000001";

  try {
    const body = await req.json();
    const data = CreateTxSchema.parse(body);

    // Check for duplicate invoice
    const dupeCheck = await sql`
      SELECT id FROM transactions
      WHERE tenant_id = ${tenantId}::UUID
        AND vendor_id = ${data.vendor_id}::UUID
        AND invoice_ref = ${data.invoice_ref}
        AND amount = ${data.amount}
        AND flag_status != 'rejected'
      LIMIT 1
    `;

    const isDuplicate = dupeCheck.length > 0;

    // Heuristic risk score (no external ML service needed)
    const amount = data.amount;
    let riskScore = 10;
    const weights: Record<string, number> = {};

    if (amount > 50000)  { riskScore += 25; weights.high_amount = 0.4; }
    if (amount > 100000) { riskScore += 20; weights.very_high_amount = 0.3; }
    if (amount % 1000 === 0 && amount > 10000) { riskScore += 15; weights.round_number = 0.2; }
    if (isDuplicate) { riskScore += 40; weights.duplicate_invoice = 0.8; }
    if (data.invoice_ref.length < 4) { riskScore += 10; weights.short_invoice_ref = 0.1; }
    riskScore = Math.min(100, riskScore);

    const flagStatus = isDuplicate ? "suppressed" : riskScore >= 75 ? "flagged" : "pending";
    const flagReason = isDuplicate
      ? "Duplicate invoice detected"
      : riskScore >= 75 ? `High risk score: ${riskScore}/100` : null;

    // Insert transaction
    const result = await sql`
      INSERT INTO transactions (tenant_id, grant_id, vendor_id, amount, invoice_ref, cost_category, tx_date, risk_score, flag_status, flag_reason)
      VALUES (${tenantId}::UUID, ${data.grant_id}::UUID, ${data.vendor_id}::UUID, ${data.amount}, ${data.invoice_ref}, ${data.cost_category}, ${data.tx_date}, ${riskScore}, ${flagStatus}, ${flagReason})
      RETURNING *
    `;

    const tx = result[0];

    // Log risk score
    await sql`
      INSERT INTO risk_score_logs (transaction_id, tenant_id, score, feature_weights)
      VALUES (${tx.id}::UUID, ${tenantId}::UUID, ${riskScore}, ${JSON.stringify(weights)})
    `;

    // Audit log
    await sql`
      INSERT INTO audit_events (tenant_id, user_id, action, resource_type, resource_id)
      VALUES (${tenantId}::UUID, ${session.user.sub}, 'TRANSACTION_CREATED', 'transaction', ${tx.id}::text)
    `;

    return Response.json({ ...tx, queued: false }, { status: 202 });
  } catch (error) {
    if (error instanceof z.ZodError) {
      return Response.json({ error: "Validation error", details: error.errors }, { status: 400 });
    }
    console.error("Transaction create error:", error);
    return Response.json({ error: "Database error" }, { status: 500 });
  }
}
