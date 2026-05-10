import { getSession } from "@auth0/nextjs-auth0";
import { sql } from "@/lib/db";
import { NextRequest } from "next/server";
import { z } from "zod";

export const runtime = "nodejs";

const FlagSchema = z.object({
  flag_status: z.enum(["approved", "rejected"]),
  justification: z.string().min(10).max(2000),
});

export async function PATCH(req: NextRequest, { params }: { params: { id: string } }) {
  const session = await getSession();
  if (!session?.user) return Response.json({ error: "Unauthorized" }, { status: 401 });

  const role = session.user["https://govguard.app/role"] || "finance_staff";
  if (!["system_admin", "compliance_officer", "finance_manager"].includes(role)) {
    return Response.json({ error: "Insufficient permissions" }, { status: 403 });
  }

  const tenantId = session.user["https://govguard.app/tenant_id"] || "00000000-0000-0000-0000-000000000001";

  try {
    const body = await req.json();
    const data = FlagSchema.parse(body);

    const result = await sql`
      UPDATE transactions
      SET flag_status = ${data.flag_status},
          flag_reason = ${data.justification},
          reviewed_by = (SELECT id FROM users WHERE auth0_sub = ${session.user.sub} LIMIT 1),
          reviewed_at = NOW()
      WHERE id = ${params.id}::UUID AND tenant_id = ${tenantId}::UUID
      RETURNING *
    `;

    if (!result[0]) return Response.json({ error: "Transaction not found" }, { status: 404 });

    await sql`
      INSERT INTO audit_events (tenant_id, user_id, action, resource_type, resource_id, metadata)
      VALUES (${tenantId}::UUID, ${session.user.sub}, 'TRANSACTION_FLAGGED', 'transaction', ${params.id}, ${JSON.stringify({ flag_status: data.flag_status })})
    `;

    return Response.json(result[0]);
  } catch (error) {
    if (error instanceof z.ZodError) {
      return Response.json({ error: "Validation error", details: error.errors }, { status: 400 });
    }
    return Response.json({ error: "Database error" }, { status: 500 });
  }
}
