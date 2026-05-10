"use client";
import useSWR from "swr";
import { api } from "@/lib/api";

export interface ComplianceControl {
  id: string;
  grantId: string;
  controlCode: string;
  cfrClause: string | null;
  gaoPrinciple: string | null;
  domain: string;
  status: "not_tested" | "pass" | "fail" | "not_applicable";
  lastTested: string | null;
  evidenceS3Key: string | null;
  remediationNote: string | null;
}

export interface ComplianceData {
  controls: ComplianceControl[];
  score: number;
  total: number;
  passing: number;
  failing: number;
}

export function useCompliance(grantId: string, domain?: string, status?: string) {
  const qs = new URLSearchParams({ grant_id: grantId });
  if (domain) qs.set("domain", domain);
  if (status) qs.set("status", status);

  return useSWR(
    `/api/v1/compliance/controls?${qs.toString()}`,
    (url) => api.get<ComplianceData>(url),
    { refreshInterval: 60000 }
  );
}
