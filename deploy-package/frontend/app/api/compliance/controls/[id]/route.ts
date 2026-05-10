import { getSession } from "@auth0/nextjs-auth0";
import { sql } from "@/lib/db";
import { NextRequest } from "next/server";

export const runtime = "nodejs";

export async function PATCH(req: NextRequest, { params }: { params: { id: string } }) {
  const session = await getSession();
  if (!session?.user) return Response.json({ error: "Unauthorized" }, { status: 401 });

  const role = session.user["https://govguard.app/role"] || "finance_staff";
  if (!["system_admin", "compliance_officer"].includes(role)) {
    return Response.json({ error: "Insufficient permissions" }, { status: 403 });
  }

  const tenantId = session.user["https://govguard.app/tenant_id"] || "00000000-0000-0000-0000-000000000001";
  const body = await req.json();
  const { status, evidence_note } = body;

  const result = await sql`
    UPDATE compliance_controls
    SET status = ${status}, remediation_note = ${evidence_note || null}, last_tested = NOW(), updated_at = NOW()
    WHERE id = ${params.id}::UUID AND tenant_id = ${tenantId}::UUID
    RETURNING *
  `;

  if (!result[0]) return Response.json({ error: "Control not found" }, { status: 404 });
  return Response.json(result[0]);
}
