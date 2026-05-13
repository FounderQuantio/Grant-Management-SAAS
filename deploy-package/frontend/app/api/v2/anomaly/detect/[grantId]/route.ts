import { NextRequest } from "next/server";
import { backendProxy } from "@/lib/backend";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function POST(req: NextRequest, { params }: { params: { grantId: string } }) {
  const body = await req.json().catch(() => ({}));
  return backendProxy(`/api/v2/anomaly/detect/${params.grantId}`, { method: "POST", body });
}
