"""
GovGuard v2 — End-to-End GAO Scenario Tests
File: tests/gao/e2e/test_gao_scenarios.py

Maps directly to GAO problem scenarios from dataset.
Each test simulates a real-world fraud/waste scenario.
"""
import pytest
from datetime import date, timedelta
from services.fraud_detection.engine import FraudDetectionEngine

ENGINE = FraudDetectionEngine()


class TestGAOScenario_PPP_EntityClustering:
    """
    GAO Cat1-Ex4 — PPP/EIDL Loan Fraud
    Scenario: Multiple applications from same beneficial owner (shared EIN hash)
    """
    def test_related_party_and_ghost_vendor_compound_risk(self):
        result = ENGINE.assess(
            transaction_id="ppp-test-001",
            amount=200000.0,
            vendor_id="entity-shell-1",
            vendor_sam_status="active",
            invoice_ref="PPP-DRAW-001",
            tx_date=date.today(),
            cost_category="personnel",
            grant_budget={"personnel": 250000},
            prior_invoices=[],
            vendor_spend_30d=0,
            all_grant_charges=[],
            vendor_risk_tier="high",
            related_party_flag=True,
        )
        assert result.composite_score > 30.0
        assert result.recommended_action in ("REVIEW", "HOLD", "BLOCK")
        assert len(result.gao_references) > 0


class TestGAOScenario_SnapTrafficking:
    """
    GAO Cat1-Ex8 — SNAP Retailer Trafficking
    Scenario: Even-dollar, high-frequency small transactions
    """
    def test_round_dollar_high_frequency_flagged(self):
        history = [
            {"id": f"tx-{i}", "invoice_ref": f"SNAP-{i}", "amount": 2000.0,
             "vendor_id": "snap-v1", "tx_date": str(date.today() - timedelta(days=i))}
            for i in range(15)
        ]
        result = ENGINE.assess(
            transaction_id="snap-test-001",
            amount=2000.0,
            vendor_id="snap-v1",
            vendor_sam_status="active",
            invoice_ref="SNAP-EVEN-001",
            tx_date=date.today(),
            cost_category="food_service",
            grant_budget={"food_service": 500000},
            prior_invoices=history,
            vendor_spend_30d=sum(float(t["amount"]) for t in history),
            all_grant_charges=[],
            vendor_risk_tier="medium",
            related_party_flag=False,
        )
        # Round dollar + high velocity should compound risk
        from services.fraud_detection.engine import RULE_ROUND_DOLLAR, RULE_HIGH_VELOCITY
        assert RULE_ROUND_DOLLAR in result.triggered_rules or RULE_HIGH_VELOCITY in result.triggered_rules


class TestGAOScenario_ResearchGrantMisuse:
    """
    GAO Cat1-Ex16 — NIH/NSF Research Grant Misuse
    Scenario: Unallowable cost category + cross-grant double charge
    """
    def test_unallowed_category_and_double_charge(self):
        result = ENGINE.assess(
            transaction_id="research-test-001",
            amount=45000.0,
            vendor_id="research-consultant",
            vendor_sam_status="active",
            invoice_ref="CONSULT-2024-001",
            tx_date=date.today(),
            cost_category="entertainment",   # Not in approved budget
            grant_budget={"personnel": 200000, "equipment": 50000, "travel": 10000},
            prior_invoices=[],
            vendor_spend_30d=0,
            all_grant_charges=[
                {"grant_id": "grant-NIH-001", "cost_category": "entertainment", "vendor_id": "research-consultant"},
                {"grant_id": "grant-NSF-001", "cost_category": "entertainment", "vendor_id": "research-consultant"},
            ],
            vendor_risk_tier="low",
            related_party_flag=False,
        )
        from services.fraud_detection.engine import RULE_EXCEEDS_BUDGET_CAT, RULE_CROSS_GRANT_DOUBLE
        assert RULE_EXCEEDS_BUDGET_CAT in result.triggered_rules
        assert RULE_CROSS_GRANT_DOUBLE in result.triggered_rules
        assert result.recommended_action in ("HOLD", "BLOCK")


class TestGAOScenario_TravelCardAbuse:
    """
    GAO Cat1-Ex9 — Federal Employee Travel Card Abuse
    Scenario: Weekend transaction, personal expense category
    """
    def test_weekend_transaction_flagged(self):
        # Find a Saturday
        today = date.today()
        days_to_sat = (5 - today.weekday()) % 7
        saturday = today + timedelta(days=days_to_sat if days_to_sat > 0 else 7)
        result = ENGINE.assess(
            transaction_id="travel-test-001",
            amount=1500.0,
            vendor_id="hotel-vendor",
            vendor_sam_status="active",
            invoice_ref="HOTEL-WKND-001",
            tx_date=saturday,
            cost_category="travel",
            grant_budget={"travel": 20000},
            prior_invoices=[],
            vendor_spend_30d=0,
            all_grant_charges=[],
            vendor_risk_tier="low",
            related_party_flag=False,
        )
        from services.fraud_detection.engine import RULE_WEEKEND_TRANSACTION
        assert RULE_WEEKEND_TRANSACTION in result.triggered_rules


class TestGAOScenario_ProcurementCollusion:
    """
    GAO Cat1-Ex26 — Procurement Collusion and Bid Rigging
    Scenario: Single vendor dominates grant spend (rotation signal)
    """
    def test_vendor_dominance_triggers_anomaly(self):
        from services.anomaly_detection.processor import AnomalyDetectionProcessor, ANOMALY_VENDOR_DOMINANCE
        proc = AnomalyDetectionProcessor()
        history = [
            {"amount": 40000, "tx_date": date.today() - timedelta(days=d),
             "vendor_id": "dominant-vendor", "cost_category": "procurement"}
            for d in range(1, 10)
        ]
        current = {"amount": 50000, "tx_date": date.today(), "vendor_id": "dominant-vendor", "cost_category": "procurement"}
        alerts = proc.detect(
            grant_id="g-proc", tenant_id="t-001",
            current_tx=current, historical_txns=history,
            grant_budget={"procurement": 500000}, grant_total_amount=500000,
        )
        dom = [a for a in alerts if a.anomaly_type == ANOMALY_VENDOR_DOMINANCE]
        assert len(dom) > 0
        assert "GAO" in (dom[0].gao_reference or "")
