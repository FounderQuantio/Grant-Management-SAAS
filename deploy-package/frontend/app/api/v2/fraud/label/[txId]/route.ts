import { NextRequest } from "next/server";
import { backendProxy } from "@/lib/backend";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function PATCH(req: NextRequest, { params }: { params: { txId: string } }) {
  const body = await req.json();
  return backendProxy(`/api/v2/fraud/label/${params.txId}`, { method: "PATCH", req, body });
}
