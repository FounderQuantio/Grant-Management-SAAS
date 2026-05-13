import { NextRequest } from "next/server";
import { backendProxy } from "@/lib/backend";

export const runtime = "nodejs";

export async function GET(_req: NextRequest) {
  return backendProxy("/api/v2/entity/graph");
}
