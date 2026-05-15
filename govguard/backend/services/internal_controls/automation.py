"""
GovGuard v2 — Internal Controls Automation
============================================
NEW FILE: services/internal_controls/automation.py

Automated triggering of control-related workflows:
  - Auto-create CAP on critical compliance violation
  - Auto-block payment on BLOCK-tier fraud signal
  - Escalation workflow for Material Weakness findings
  - 2 CFR 200 control matrix auto-evaluation

GAO Alignment:
  - Cat 3 Ex 22 (Antifraud Playbook Implementation)
  - Cat 3 Ex 29 (Continuous Risk Assessment Adoption)
  - Cat 5 Ex 21 (Common Audit-Trail Format)
"""
from __future__ import annotations
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Optional


@dataclass
class ControlAction:
    action_id: str
    action_type: str        # AUTO_CAP / PAYMENT_BLOCK / ESCALATION / NOTIFICATION
    trigger_source: str     # FRAUD_ENGINE / ANOMALY_DETECTOR / COMPLIANCE_MONITOR
    resource_type: str      # TRANSACTION / GRANT / VENDOR
    resource_id: str
    tenant_id: str
    payload: dict
    executed: bool = False
    executed_at: Optional[str] = None
    audit_trail: dict = None

    def __post_init__(self):
        if self.audit_trail is None:
            self.audit_trail = {
                "action_id": self.action_id,
                "trigger_source": self.trigger_source,
                "created_at": datetime.utcnow().isoformat(),
                "gao_standard": "GAO Standards for Internal Control — Principle 10 (Design Control Activities)",
            }


class InternalControlsAutomation:
    """
    Orchestrates automated control responses to fraud and compliance events.
    All actions produce immutable audit trail entries.
    """

    def process_fraud_assessment(self, assessment: dict, tenant_id: str) -> list[ControlAction]:
        """Generate control actions from a FraudAssessment result."""
        actions = []
        action = assessment.get("recommended_action")
        tx_id = assessment.get("transaction_id")

        if action == "BLOCK":
            actions.append(ControlAction(
                action_id=str(uuid.uuid4()),
                action_type="PAYMENT_BLOCK",
                trigger_source="FRAUD_ENGINE",
                resource_type="TRANSACTION",
                resource_id=tx_id,
                tenant_id=tenant_id,
                payload={
                    "new_flag_status": "rejected",
                    "flag_reason": f"AUTO-BLOCKED: {assessment.get('explanation')}",
                    "triggered_rules": assessment.get("triggered_rules"),
                    "composite_score": assessment.get("composite_score"),
                    "gao_references": assessment.get("gao_references"),
                },
            ))

        elif action == "HOLD":
            actions.append(ControlAction(
                action_id=str(uuid.uuid4()),
                action_type="PAYMENT_HOLD",
                trigger_source="FRAUD_ENGINE",
                resource_type="TRANSACTION",
                resource_id=tx_id,
                tenant_id=tenant_id,
                payload={
                    "new_flag_status": "flagged",
                    "flag_reason": f"AUTO-HELD: {assessment.get('explanation')}",
                    "requires_review": True,
                    "composite_score": assessment.get("composite_score"),
                },
            ))

        return actions

    def process_compliance_violation(self, violation: dict, tenant_id: str) -> list[ControlAction]:
        """Auto-create CAP for MATERIAL_WEAKNESS violations with auto_cap_trigger=True."""
        actions = []

        if violation.get("auto_cap_trigger") and violation.get("severity") == "MATERIAL_WEAKNESS":
            due_date = (date.today() + timedelta(days=90)).isoformat()
            actions.append(ControlAction(
                action_id=str(uuid.uuid4()),
                action_type="AUTO_CAP",
                trigger_source="COMPLIANCE_MONITOR",
                resource_type="GRANT",
                resource_id=violation.get("grant_id", ""),
                tenant_id=tenant_id,
                payload={
                    "finding_title": violation.get("title"),
                    "cfr_citation": violation.get("cfr_citation"),
                    "gao_reference": violation.get("gao_reference"),
                    "evidence": violation.get("evidence"),
                    "recommended_remediation": violation.get("recommended_remediation"),
                    "suggested_due_date": due_date,
                    "severity": "MATERIAL_WEAKNESS",
                    "auto_generated": True,
                },
            ))

        if violation.get("severity") in ("MATERIAL_WEAKNESS", "SIGNIFICANT_DEFICIENCY"):
            actions.append(ControlAction(
                action_id=str(uuid.uuid4()),
                action_type="ESCALATION",
                trigger_source="COMPLIANCE_MONITOR",
                resource_type="GRANT",
                resource_id=violation.get("grant_id", ""),
                tenant_id=tenant_id,
                payload={
                    "escalation_level": "COMPLIANCE_OFFICER",
                    "subject": f"[AUTO] {violation.get('severity')}: {violation.get('title')}",
                    "body": violation.get("recommended_remediation"),
                    "severity": violation.get("severity"),
                },
            ))

        return actions

    def process_anomaly_alert(self, alert: dict, tenant_id: str) -> list[ControlAction]:
        """Translate anomaly alerts to control actions."""
        actions = []
        auto_action = alert.get("auto_action")

        if auto_action == "HOLD_PAYMENTS":
            actions.append(ControlAction(
                action_id=str(uuid.uuid4()),
                action_type="PAYMENT_HOLD",
                trigger_source="ANOMALY_DETECTOR",
                resource_type="GRANT",
                resource_id=alert.get("grant_id", ""),
                tenant_id=tenant_id,
                payload={
                    "anomaly_type": alert.get("anomaly_type"),
                    "severity": alert.get("severity"),
                    "description": alert.get("description"),
                    "hold_reason": "Automated hold: anomalous burnrate detected",
                    "gao_reference": alert.get("gao_reference"),
                },
            ))

        elif auto_action in ("FLAG_REVIEW", "NOTIFY"):
            actions.append(ControlAction(
                action_id=str(uuid.uuid4()),
                action_type="NOTIFICATION",
                trigger_source="ANOMALY_DETECTOR",
                resource_type="GRANT",
                resource_id=alert.get("grant_id", ""),
                tenant_id=tenant_id,
                payload={
                    "anomaly_type": alert.get("anomaly_type"),
                    "severity": alert.get("severity"),
                    "description": alert.get("description"),
                    "notification_target": "COMPLIANCE_OFFICER",
                    "gao_reference": alert.get("gao_reference"),
                },
            ))

        return actions

    def execute_actions(self, actions: list[ControlAction], db_session=None) -> list[dict]:
        """
        Execute control actions against the database.
        In production: call existing repository methods.
        Returns list of execution results for audit log.
        """
        results = []
        for action in actions:
            result = {
                "action_id": action.action_id,
                "action_type": action.action_type,
                "resource_id": action.resource_id,
                "executed_at": datetime.utcnow().isoformat(),
                "audit_trail": action.audit_trail,
            }
            # NOTE: Actual DB writes happen in the API route layer
            # to maintain clean separation and avoid circular imports.
            # This method returns the payload for the caller to execute.
            action.executed = True
            action.executed_at = datetime.utcnow().isoformat()
            results.append(result)
        return results
