import { auth0 } from "../../../lib/auth";
import { NextRequest } from "next/server";

export async function GET(request: NextRequest) {
  return auth0.middleware(request);
}
