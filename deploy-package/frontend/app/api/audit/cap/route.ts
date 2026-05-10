import { getSession } from "@auth0/nextjs-auth0";
import { sql } from "@/lib/db";
import { NextRequest } from "next/server";

export const runtime = "nodejs";

export async function POST(req: NextRequest) {
  const session = await getSession();
  if (!session?.user) return Response.json({ error: "Unauthorized" }, { status: 401 });
  const tenantId = session.user["https://govguard.app/tenant_id"] || "00000000-0000-0000-0000-000000000001";

  const { finding_id, response_text, due_date, assignee_id } = await req.json();
  const result = await sql`
    INSERT INTO corrective_action_plans (tenant_id, finding_id, response_text, due_date, assignee_id)
    VALUES (${tenantId}::UUID, ${finding_id}::UUID, ${response_text}, ${due_date}, ${assignee_id ? `${assignee_id}::UUID` : null})
    RETURNING *
  `;
  return Response.json(result[0], { status: 201 });
}

export async function GET(req: NextRequest) {
  const session = await getSession();
  if (!session?.user) return Response.json({ error: "Unauthorized" }, { status: 401 });
  const tenantId = session.user["https://govguard.app/tenant_id"] || "00000000-0000-0000-0000-000000000001";

  const rows = await sql`
    SELECT cap.*, af.finding_ref, af.category, af.severity
    FROM corrective_action_plans cap
    JOIN audit_findings af ON af.id = cap.finding_id
    WHERE cap.tenant_id = ${tenantId}::UUID
    ORDER BY cap.due_date ASC
  `;
  return Response.json({ caps: rows, total: rows.length });
}
