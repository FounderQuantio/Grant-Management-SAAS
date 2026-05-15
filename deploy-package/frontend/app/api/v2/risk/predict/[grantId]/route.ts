import { NextRequest } from "next/server";
import { backendProxy } from "@/lib/backend";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(req: NextRequest, { params }: { params: { grantId: string } }) {
  return backendProxy(`/api/v2/risk/predict/${params.grantId}`, { req });
}
