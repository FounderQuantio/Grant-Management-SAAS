"use client";
import useSWR from "swr";
import { api } from "@/lib/api";

export interface ReportingPeriod {
  period_label: string;
  period_end: string;
  due_date: string;
  submitted_at: string | null;
  narrative: string | null;
  certification_accepted: boolean | null;
  status: "submitted" | "overdue" | "upcoming";
}

export interface ReportingData {
  grant_id: string;
  periods: ReportingPeriod[];
}

export function useReporting(grantId: string) {
  return useSWR(
    grantId ? `/api/v1/reporting/grants/${grantId}` : null,
    (url) => api.get<ReportingData>(url)
  );
}
