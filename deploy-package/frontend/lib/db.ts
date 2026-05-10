/**
 * GovGuard™ — Neon Serverless Database Client
 * Uses @neondatabase/serverless for edge-compatible PostgreSQL.
 * Connection pooling handled automatically by Neon.
 */
import { neon, neonConfig } from "@neondatabase/serverless";

neonConfig.fetchConnectionCache = true;

// Lazy singleton — neon() is only called on the first query, not at module load
let _client: ReturnType<typeof neon> | undefined;
function getClient() {
  if (!_client) _client = neon(process.env.DATABASE_URL!);
  return _client;
}

type SqlFn = (strings: TemplateStringsArray, ...values: unknown[]) => Promise<Record<string, unknown>[]>;

export const sql: SqlFn = new Proxy(function () {} as unknown as SqlFn, {
  apply(_t, thisArg, args) {
    return Reflect.apply(getClient(), thisArg, args as Parameters<SqlFn>);
  },
  get(_t, prop) {
    return (getClient() as unknown as Record<string, unknown>)[prop as string];
  },
});

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
