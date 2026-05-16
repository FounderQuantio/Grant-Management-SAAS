import { NextRequest } from "next/server";
import { auth0 } from "@/lib/auth";
import { sql } from "@/lib/db";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function PATCH(req: NextRequest, { params }: { params: { txId: string } }) {
  const session = await auth0.getSession();
  if (!session?.user) return Response.json({ error: "Unauthorized" }, { status: 401 });

  const tenantId =
    session.user["https://govguard.app/tenant_id"] || "00000000-0000-0000-0000-000000000001";
  const { txId } = params;

  const { confirmed_fraud } = await req.json();
  if (confirmed_fraud === undefined)
    return Response.json({ error: "confirmed_fraud required" }, { status: 400 });

  const result = await sql`
    UPDATE fraud_assessments
    SET confirmed_label = ${confirmed_fraud},
        confirmed_at    = NOW()
    WHERE transaction_id = ${txId}::UUID
      AND tenant_id      = ${tenantId}::UUID
      AND id = (
        SELECT id FROM fraud_assessments
        WHERE transaction_id = ${txId}::UUID
          AND tenant_id      = ${tenantId}::UUID
        ORDER BY created_at DESC
        LIMIT 1
      )
    RETURNING id
  `;

  if (!result[0]) return Response.json({ error: "No assessment found", tx_id: txId }, { status: 404 });

  return Response.json({ labeled: true, transaction_id: txId, confirmed_fraud });
}
