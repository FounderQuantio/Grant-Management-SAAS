"use client";
/**
 * GovGuard™ — Typed API Client
 * Handles auth headers, 401 refresh, and typed responses.
 */

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export class APIError extends Error {
  constructor(
    public status: number,
    public errorCode: string,
    message: string,
    public details?: Record<string, unknown>
  ) {
    super(message);
    this.name = "APIError";
  }
}

async function refreshToken(): Promise<boolean> {
  const res = await fetch("/api/auth/refresh", { method: "POST" });
  return res.ok;
}

export async function apiRequest<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const url = `${BASE_URL}${path}`;

  const res = await fetch(url, {
    ...options,
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      "Accept": "application/json",
      ...options.headers,
    },
  });

  if (res.status === 401) {
    const refreshed = await refreshToken();
    if (refreshed) {
      // Retry with fresh token
      const retryRes = await fetch(url, {
        ...options,
        credentials: "include",
        headers: { "Content-Type": "application/json", ...options.headers },
      });
      if (retryRes.ok) return retryRes.json() as Promise<T>;
    }
    window.location.href = `/login?return_to=${window.location.pathname}`;
    throw new APIError(401, "SESSION_EXPIRED", "Session expired");
  }

  if (!res.ok) {
    const errBody = await res.json().catch(() => ({}));
    throw new APIError(
      res.status,
      errBody.error_code || "UNKNOWN_ERROR",
      errBody.message || "Request failed",
      errBody.details
    );
  }

  if (res.status === 204) return {} as T;
  return res.json() as Promise<T>;
}

// Typed API methods
export const api = {
  get:    <T>(path: string) => apiRequest<T>(path),
  post:   <T>(path: string, body: unknown) =>
    apiRequest<T>(path, { method: "POST", body: JSON.stringify(body) }),
  patch:  <T>(path: string, body: unknown) =>
    apiRequest<T>(path, { method: "PATCH", body: JSON.stringify(body) }),
  delete: <T>(path: string) =>
    apiRequest<T>(path, { method: "DELETE" }),
};
