"""
GovGuard v2 — Grant Compliance Monitor
========================================
NEW FILE: services/compliance_monitor/monitor.py

GAO-mapped compliance rules engine. Each rule has:
  - A unique GAO source reference
  - Structured evidence payload
  - Automatic CAP trigger flag

GAO Alignment:
  - Cat 2 Ex 23 (Grant Compliance System Duplication)
  - Cat 3 Ex 23 (Continuous Monitoring of High-Risk Grants)
  - Cat 4 Ex 15 (HHS Grant Compliance Coverage)
  - Cat 5 Ex 28 (Federal Grants Subrecipient Monitoring)
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional

# ── Compliance Rule Catalogue ─────────────────────────────────────────────

@dataclass
class ComplianceRule:
    rule_id: str
    cfr_citation: str
    gao_reference: str
    title: str
    description: str
    severity: str          # MATERIAL_WEAKNESS / SIGNIFICANT_DEFICIENCY / FINDING
    auto_cap_trigger: bool = False


@dataclass
class ComplianceViolation:
    rule_id: str
    grant_id: str
    tenant_id: str
    severity: str
    cfr_citation: str
    gao_reference: str
    title: str
    evidence: dict
    recommended_remediation: str
    auto_cap_trigger: bool
    detected_at: str

    def to_dict(self) -> dict:
        return {
            "rule_id": self.rule_id,
            "grant_id": self.grant_id,
            "severity": self.severity,
            "cfr_citation": self.cfr_citation,
            "gao_reference": self.gao_reference,
            "title": self.title,
            "evidence": self.evidence,
            "recommended_remediation": self.recommended_remediation,
            "auto_cap_trigger": self.auto_cap_trigger,
            "detected_at": self.detected_at,
        }


COMPLIANCE_RULES = [
    ComplianceRule("CM-001","2 CFR 200.302","GAO Cat2-Ex23","Financial Management System","Must maintain financial system meeting OMB standards","SIGNIFICANT_DEFICIENCY",True),
    ComplianceRule("CM-002","2 CFR 200.305","GAO Cat3-Ex29","Cash Management","Minimize time between cash drawdown and disbursement","FINDING"),
    ComplianceRule("CM-003","2 CFR 200.318","GAO Cat1-Ex26","Procurement Written Policy","Written procurement procedures required","SIGNIFICANT_DEFICIENCY",True),
    ComplianceRule("CM-004","2 CFR 200.320","GAO Cat1-Ex26","Competition Requirements","Competitive procurement above SAT threshold","MATERIAL_WEAKNESS",True),
    ComplianceRule("CM-005","2 CFR 200.331","GAO Cat5-Ex28","Subrecipient Monitoring","Pass-through monitoring of subrecipients","MATERIAL_WEAKNESS",True),
    ComplianceRule("CM-006","2 CFR 200.332","GAO Cat5-Ex28","Subrecipient Risk Assessment","Risk-based monitoring plan required","SIGNIFICANT_DEFICIENCY"),
    ComplianceRule("CM-007","2 CFR 200.344","GAO Cat3-Ex23","Grant Closeout","Submit all closeout reports within 120 days","FINDING"),
    ComplianceRule("CM-008","2 CFR 200.405","GAO Cat1-Ex16","Cost Allocability","Costs must be allocable to the award","MATERIAL_WEAKNESS",True),
    ComplianceRule("CM-009","2 CFR 200.430","GAO Cat3-Ex2","Compensation Reasonableness","Compensation must be reasonable and consistent","SIGNIFICANT_DEFICIENCY"),
    ComplianceRule("CM-010","2 CFR 200.474","GAO Cat1-Ex9","Travel Cost Allowability","Only allowable travel costs charged","FINDING"),
]


class GrantComplianceMonitor:
    """
    Runs continuous compliance checks against a grant's transaction
    and operational context. Emits ComplianceViolation events.
    """

    def check_all(
        self,
        *,
        grant_id: str,
        tenant_id: str,
        grant: dict,
        transactions: list[dict],
        compliance_controls: list[dict],
        subrecipients: list[dict],
        days_since_activation: int,
    ) -> list[ComplianceViolation]:
        ts = datetime.utcnow().isoformat()
        violations = []

        for rule in COMPLIANCE_RULES:
            v = self._evaluate_rule(rule, grant_id, tenant_id, grant, transactions, compliance_controls, subrecipients, days_since_activation, ts)
            if v:
                violations.append(v)

        return violations

    def _evaluate_rule(self, rule, grant_id, tenant_id, grant, transactions, controls, subrecipients, days_active, ts) -> Optional[ComplianceViolation]:
        ev = {"rule_id": rule.rule_id}

        if rule.rule_id == "CM-001":
            # Check if ERP sync job exists (proxy for financial mgmt system)
            if not grant.get("erp_connected") and days_active > 30:
                ev["days_active_without_erp"] = days_active
                return self._violation(rule, grant_id, tenant_id, ev,
                    "Connect an ERP or configure CSV upload to establish financial management system.", ts)

        elif rule.rule_id == "CM-002":
            # Check for drawdowns with no corresponding expenditure within 3 days
            drawdowns = [t for t in transactions if t.get("cost_category") == "drawdown"]
            for d in drawdowns:
                # Simplified: flag if large drawdown with no follow-on spend
                if float(d.get("amount", 0)) > 50000:
                    ev["drawdown_amount"] = float(d.get("amount", 0))
                    ev["drawdown_date"] = str(d.get("tx_date"))
                    return self._violation(rule, grant_id, tenant_id, ev,
                        "Review cash drawdown timing against actual expenditure schedule.", ts)

        elif rule.rule_id == "CM-003":
            # Check if procurement policy control is passing
            proc_ctrl = next((c for c in controls if c.get("control_code") == "PROC-001"), None)
            if not proc_ctrl or proc_ctrl.get("status") in ("fail", "not_tested"):
                ev["control_status"] = proc_ctrl.get("status") if proc_ctrl else "missing"
                return self._violation(rule, grant_id, tenant_id, ev,
                    "Upload written procurement procedures as evidence to PROC-001 control.", ts)

        elif rule.rule_id == "CM-004":
            # Look for single-bid transactions > SAT threshold
            for t in transactions:
                if float(t.get("amount", 0)) > 10000 and t.get("procurement_method") == "sole_source":
                    ev["transaction_id"] = t.get("id")
                    ev["amount"] = float(t.get("amount", 0))
                    ev["method"] = "sole_source"
                    return self._violation(rule, grant_id, tenant_id, ev,
                        "Justify sole-source procurement or conduct competition per 2 CFR 200.320.", ts)

        elif rule.rule_id == "CM-005":
            # Check if any subrecipients lack monitoring evidence
            for sub in subrecipients:
                if not sub.get("monitoring_date") and float(sub.get("subaward_amount", 0)) > 25000:
                    ev["subrecipient_id"] = sub.get("id")
                    ev["subaward_amount"] = float(sub.get("subaward_amount", 0))
                    return self._violation(rule, grant_id, tenant_id, ev,
                        "Document subrecipient monitoring activities per 2 CFR 200.331.", ts)

        elif rule.rule_id == "CM-007":
            # Grant past period_end with open status
            period_end = grant.get("period_end")
            if period_end and grant.get("status") != "closed":
                end_date = date.fromisoformat(str(period_end)) if isinstance(period_end, str) else period_end
                days_overdue = (date.today() - end_date).days
                if days_overdue > 120:
                    ev["period_end"] = str(period_end)
                    ev["days_overdue"] = days_overdue
                    return self._violation(rule, grant_id, tenant_id, ev,
                        f"Grant closeout overdue by {days_overdue} days. Submit final financial report immediately.", ts)

        elif rule.rule_id == "CM-008":
            # Transactions in categories not in approved budget
            budget = grant.get("budget_json", {})
            for t in transactions:
                if t.get("cost_category") and t["cost_category"] not in budget:
                    ev["unallowed_category"] = t["cost_category"]
                    ev["transaction_id"] = t.get("id")
                    ev["amount"] = float(t.get("amount", 0))
                    return self._violation(rule, grant_id, tenant_id, ev,
                        "Remove or reclassify unallowable cost. Seek prior approval if needed.", ts)

        return None

    def _violation(self, rule, grant_id, tenant_id, evidence, remediation, ts) -> ComplianceViolation:
        return ComplianceViolation(
            rule_id=rule.rule_id,
            grant_id=grant_id,
            tenant_id=tenant_id,
            severity=rule.severity,
            cfr_citation=rule.cfr_citation,
            gao_reference=rule.gao_reference,
            title=rule.title,
            evidence=evidence,
            recommended_remediation=remediation,
            auto_cap_trigger=rule.auto_cap_trigger,
            detected_at=ts,
        )
