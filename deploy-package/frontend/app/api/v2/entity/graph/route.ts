import { NextRequest } from "next/server";
import { backendProxy } from "@/lib/backend";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(req: NextRequest) {
  return backendProxy("/api/v2/entity/graph", { req });
}
