import { auth0 } from "./lib/auth";

export const middleware = auth0.middleware;

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon\\.ico|api/auth).*)"],
};
