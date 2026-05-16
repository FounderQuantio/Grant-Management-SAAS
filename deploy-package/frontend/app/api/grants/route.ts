import { auth0 } from "@/lib/auth";
import { sql } from "@/lib/db";
import { NextRequest } from "next/server";
import { z } from "zod";

export const runtime = "nodejs";

const CreateGrantSchema = z.object({
  award_number: z.string().min(1).max(100),
  agency: z.string().min(1).max(100),
  program_cfda: z.string().optional(),
  period_start: z.string(),
  period_end: z.string(),
  total_amount: z.number().positive(),
  budget_json: z.record(z.number()).default({}),
});

export async function GET(req: NextRequest) {
  const session = await auth0.getSession();
  if (!session?.user) return Response.json({ error: "Unauthorized" }, { status: 401 });
  const tenantId = session.user["https://govguard.app/tenant_id"] || "00000000-0000-0000-0000-000000000001";
  const status = req.nextUrl.searchParams.get("status");

  try {
    const rows = status
      ? await sql`
          SELECT id, award_number, agency, program_cfda, period_start, period_end,
                 total_amount, status, compliance_score, activated_at, created_at
          FROM grants
          WHERE tenant_id = ${tenantId}::UUID AND status = ${status}
          ORDER BY created_at DESC
        `
      : await sql`
          SELECT id, award_number, agency, program_cfda, period_start, period_end,
                 total_amount, status, compliance_score, activated_at, created_at
          FROM grants
          WHERE tenant_id = ${tenantId}::UUID
          ORDER BY created_at DESC
        `;
    return Response.json({ grants: rows, total: rows.length });
  } catch (error) {
    console.error("Grants list error:", error);
    return Response.json({ error: "Database error" }, { status: 500 });
  }
}

export async function POST(req: NextRequest) {
  const session = await auth0.getSession();
  if (!session?.user) return Response.json({ error: "Unauthorized" }, { status: 401 });

  const role = session.user["https://govguard.app/role"] || "finance_manager";
  if (!["system_admin", "compliance_officer", "finance_manager", "agency_officer"].includes(role)) {
    return Response.json({ error: "Insufficient permissions" }, { status: 403 });
  }

  const tenantId = session.user["https://govguard.app/tenant_id"] || "00000000-0000-0000-0000-000000000001";

  try {
    const body = await req.json();
    const data = CreateGrantSchema.parse(body);

    const result = await sql`
      INSERT INTO grants (tenant_id, award_number, agency, program_cfda, period_start, period_end, total_amount, budget_json, status)
      VALUES (${tenantId}::UUID, ${data.award_number}, ${data.agency}, ${data.program_cfda || null},
              ${data.period_start}, ${data.period_end}, ${data.total_amount}, ${JSON.stringify(data.budget_json)}, 'draft')
      RETURNING *
    `;

    // Seed compliance controls from library (best-effort)
    try {
      const library = await sql`SELECT code, cfr_clause, domain FROM control_library`;
      if (library.length > 0 && result[0]) {
        for (const ctrl of library) {
          await sql`
            INSERT INTO compliance_controls (tenant_id, grant_id, control_code, cfr_clause, domain)
            VALUES (${tenantId}::UUID, ${result[0].id}::UUID, ${ctrl.code}, ${ctrl.cfr_clause || null}, ${ctrl.domain})
            ON CONFLICT DO NOTHING
          `;
        }
      }
    } catch {
      // control_library table may not exist yet — grant still created successfully
    }

    return Response.json(result[0], { status: 201 });
  } catch (error) {
    if (error instanceof z.ZodError) {
      return Response.json({ error: "Validation error", details: error.errors }, { status: 400 });
    }
    return Response.json({ error: "Database error" }, { status: 500 });
  }
}
