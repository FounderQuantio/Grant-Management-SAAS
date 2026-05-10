// GovGuard™ — Shared TypeScript Types

export interface Tenant {
  id: string;
  name: string;
  tier: 1 | 2 | 3;
  plan: "free" | "starter" | "professional" | "enterprise";
  modulesEnabled: string[];
  fedrampScope: boolean;
  createdAt: string;
}

export interface Grant {
  id: string;
  tenantId: string;
  awardNumber: string;
  agency: string;
  programCfda: string | null;
  periodStart: string;
  periodEnd: string;
  totalAmount: number;
  budgetJson: Record<string, number>;
  status: "draft" | "active" | "closed" | "suspended";
  activatedAt: string | null;
  complianceScore: number | null;
  createdAt: string;
}

export interface AuditFinding {
  id: string;
  tenantId: string;
  grantId: string | null;
  findingRef: string;
  category: string;
  description: string;
  cfrClause: string | null;
  severity: "material_weakness" | "significant_deficiency" | "finding";
  status: "open" | "in_progress" | "closed" | "contested";
  dueDate: string | null;
  closedAt: string | null;
  createdAt: string;
}

export interface CorrectiveActionPlan {
  id: string;
  findingId: string;
  responseText: string;
  assigneeId: string | null;
  dueDate: string;
  status: "open" | "in_progress" | "closed" | "overdue";
  closedAt: string | null;
}

export interface DashboardKPIs {
  improperPaymentRate: number;
  complianceScore: number;
  openFindings: number;
  flaggedTxCount: number;
  totalTxCount: number;
  riskLeaderboard: {
    grantId: string;
    awardNumber: string;
    agency: string;
    complianceScore: number;
  }[];
  periodDays: number;
}

export type UserRole =
  | "system_admin"
  | "agency_officer"
  | "compliance_officer"
  | "finance_manager"
  | "finance_staff"
  | "auditor"
  | "equity_analyst";

export interface PaginatedResponse<T> {
  data: T[];
  total: number;
  page: number;
  limit: number;
}
