import { NextRequest } from "next/server";
import { backendProxy } from "@/lib/backend";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function POST(req: NextRequest, { params }: { params: { grantId: string } }) {
  return backendProxy(`/api/v2/fraud/bulk-scan/${params.grantId}`, { method: "POST", req });
}
