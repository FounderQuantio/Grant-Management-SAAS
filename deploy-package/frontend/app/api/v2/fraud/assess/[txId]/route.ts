import { NextRequest } from "next/server";
import { backendProxy } from "@/lib/backend";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function POST(_req: NextRequest, { params }: { params: { txId: string } }) {
  return backendProxy(`/api/v2/fraud/assess/${params.txId}`, { method: "POST" });
}
