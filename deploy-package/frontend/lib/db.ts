"use server";
/**
 * GovGuard™ — Neon Serverless Database Client
 * Uses @neondatabase/serverless for edge-compatible PostgreSQL.
 * Connection pooling handled automatically by Neon.
 */
import { neon, neonConfig } from "@neondatabase/serverless";

neonConfig.fetchConnectionCache = true;

if (!process.env.DATABASE_URL) {
  throw new Error("DATABASE_URL environment variable is not set");
}

export const sql = neon(process.env.DATABASE_URL);

// ── Type-safe query helpers ───────────────────────────────────────────────

export async function query<T = Record<string, unknown>>(
  strings: TemplateStringsArray,
  ...values: unknown[]
): Promise<T[]> {
  const result = await sql(strings, ...values);
  return result as T[];
}

// Multi-tenant RLS helper — call before every query
export async function withTenant<T>(
  tenantId: string,
  fn: () => Promise<T>
): Promise<T> {
  // Note: Neon serverless doesn't support SET LOCAL per query.
  // Tenant isolation is enforced at the application layer via WHERE clauses.
  // For full RLS, use the Neon connection pooler with pgbouncer in session mode.
  return fn();
}

export type QueryResult<T> = T[];
