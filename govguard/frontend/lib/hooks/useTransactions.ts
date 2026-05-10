"use client";
import useSWR, { mutate } from "swr";
import { api, APIError } from "@/lib/api";

export interface Transaction {
  id: string;
  grantId: string;
  vendorId: string;
  amount: number;
  invoiceRef: string;
  costCategory: string;
  txDate: string;
  riskScore: number | null;
  flagStatus: "pending" | "approved" | "rejected" | "suppressed" | "flagged";
  flagReason: string | null;
  reviewedBy: string | null;
  reviewedAt: string | null;
  createdAt: string;
}

export interface RiskScore {
  score: number;
  featureWeights: Record<string, number>;
  modelVersion: string;
  explanation: string;
  isHighRisk: boolean;
}

export function useTransactions(params: {
  grantId?: string;
  flagStatus?: string;
  page?: number;
  limit?: number;
}) {
  const qs = new URLSearchParams();
  if (params.grantId) qs.set("grant_id", params.grantId);
  if (params.flagStatus) qs.set("flag_status", params.flagStatus);
  if (params.page) qs.set("page", String(params.page));
  if (params.limit) qs.set("limit", String(params.limit));

  return useSWR(
    `/api/v1/transactions?${qs.toString()}`,
    (url) => api.get<{ transactions: Transaction[]; total: number }>(url),
    { refreshInterval: 30000 }
  );
}

export function useRiskScore(txId: string | null) {
  return useSWR(
    txId ? `/api/v1/transactions/${txId}/risk` : null,
    (url) => api.get<RiskScore>(url)
  );
}

export async function flagTransaction(
  txId: string,
  flagStatus: "approved" | "rejected",
  justification: string
): Promise<Transaction> {
  const result = await api.patch<Transaction>(`/api/v1/transactions/${txId}/flag`, {
    flag_status: flagStatus,
    justification,
  });
  // Invalidate relevant SWR caches
  await mutate((key) => typeof key === "string" && key.includes("/transactions"), undefined, { revalidate: true });
  return result;
}
