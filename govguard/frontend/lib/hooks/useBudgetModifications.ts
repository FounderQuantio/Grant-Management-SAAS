"use client";
import useSWR from "swr";
import { api } from "@/lib/api";

export interface BudgetModification {
  id: string;
  category: string;
  old_amount: number;
  new_amount: number;
  delta_amount: number;
  cumulative_pct_of_total: number;
  requires_prior_approval: boolean;
  status: "pending" | "auto_applied" | "approved" | "rejected";
  reviewed_at: string | null;
  created_at: string;
}

export interface BudgetModificationsData {
  grant_id: string;
  modifications: BudgetModification[];
}

export function useBudgetModifications(grantId: string) {
  return useSWR(
    grantId ? `/api/v1/budget-modifications/grants/${grantId}` : null,
    (url) => api.get<BudgetModificationsData>(url)
  );
}
