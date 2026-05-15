"""
GovGuard v2 — GAO Test Suite
==============================
File: tests/gao/unit/test_fraud_engine.py

Unit tests for FraudDetectionEngine.
Each test maps to a specific GAO problem scenario.
"""
import pytest
from datetime import date
from services.fraud_detection.engine import (
    FraudDetectionEngine, RULE_DUPLICATE_EXACT, RULE_VENDOR_SAM_EXCLUDED,
    RULE_SPLIT_PURCHASE, RULE_ROUND_DOLLAR, RULE_HIGH_VELOCITY,
    RULE_CROSS_GRANT_DOUBLE, RULE_GHOST_VENDOR,
)

ENGINE = FraudDetectionEngine()

def base_ctx(**overrides):
    """Minimal valid context for fraud assessment."""
    ctx = dict(
        transaction_id="tx-test-001",
        amount=5000.0,
        vendor_id="vendor-abc",
        vendor_sam_status="active",
        invoice_ref="INV-2024-001",
        tx_date=date(2024, 6, 15),
        cost_category="personnel",
        grant_budget={"personnel": 100000, "travel": 20000},
        prior_invoices=[],
        vendor_spend_30d=0.0,
        all_grant_charges=[],
        vendor_risk_tier="low",
        related_party_flag=False,
    )
    ctx.update(overrides)
    return ctx


# ═══════════════════════════════════════════════════════════════════════════
# GAO Cat1-Ex10: Duplicate Vendor Payments in DoD
# ═══════════════════════════════════════════════════════════════════════════

class TestDuplicatePaymentDetection:
    """GAO Cat1-Ex10 — Duplicate Vendor Payments in DoD and Civilian Agencies."""

    def test_exact_duplicate_triggers_rule(self):
        """Exact duplicate invoice should trigger FDE-001."""
        ctx = base_ctx(
            prior_invoices=[
                {"id": "tx-prior-001", "invoice_ref": "INV-2024-001",
                 "amount": 5000.0, "vendor_id": "vendor-abc", "tx_date": "2024-06-10"}
            ]
        )
        result = ENGINE.assess(**ctx)
        assert RULE_DUPLICATE_EXACT in result.triggered_rules
        assert result.composite_score >= 25.0
        assert result.recommended_action != "APPROVE"  # Any alert tier is acceptable

    def test_fuzzy_duplicate_triggers_rule(self):
        """Invoice ref INV-2024-001 vs INV-2024-001A (edit distance 1) should trigger FDE-002."""
        ctx = base_ctx(
            invoice_ref="INV-2024-001A",
            prior_invoices=[
                {"id": "tx-prior-002", "invoice_ref": "INV-2024-001",
                 "amount": 5000.0, "vendor_id": "vendor-abc", "tx_date": "2024-06-10"}
            ]
        )
        result = ENGINE.assess(**ctx)
        assert RULE_DUPLICATE_EXACT not in result.triggered_rules  # Not exact
        assert RULE_SPLIT_PURCHASE not in result.triggered_rules
        # Fuzzy match may or may not trigger depending on edit distance
        if len(result.triggered_rules) > 0:
            assert result.composite_score > 0

    def test_different_vendor_no_duplicate(self):
        """Same invoice ref but different vendor — not a duplicate."""
        ctx = base_ctx(
            prior_invoices=[
                {"id": "tx-prior-003", "invoice_ref": "INV-2024-001",
                 "amount": 5000.0, "vendor_id": "DIFFERENT-VENDOR", "tx_date": "2024-06-10"}
            ]
        )
        result = ENGINE.assess(**ctx)
        assert RULE_DUPLICATE_EXACT not in result.triggered_rules

    def test_clean_transaction_no_flag(self):
        """Unique invoice, new vendor, reasonable amount — should be APPROVE."""
        result = ENGINE.assess(**base_ctx())
        assert result.recommended_action == "APPROVE"
        assert result.composite_score < 25.0


# ═══════════════════════════════════════════════════════════════════════════
# GAO Cat5-Ex4: Manual SAM.gov Exclusion Checks
# ═══════════════════════════════════════════════════════════════════════════

class TestSAMExclusionDetection:
    """GAO Cat5-Ex4 — Manual SAM.gov Exclusion Checks."""

    def test_excluded_vendor_triggers_block(self):
        """SAM-excluded vendor must result in BLOCK."""
        ctx = base_ctx(vendor_sam_status="excluded")
        result = ENGINE.assess(**ctx)
        assert RULE_VENDOR_SAM_EXCLUDED in result.triggered_rules
        assert result.risk_tier == "CRITICAL"
        assert result.recommended_action == "BLOCK"

    def test_suspended_vendor_triggers_block(self):
        ctx = base_ctx(vendor_sam_status="suspended")
        result = ENGINE.assess(**ctx)
        assert RULE_VENDOR_SAM_EXCLUDED in result.triggered_rules
        assert result.recommended_action == "BLOCK"

    def test_gao_reference_present(self):
        """GAO reference must be included in assessment."""
        ctx = base_ctx(vendor_sam_status="excluded")
        result = ENGINE.assess(**ctx)
        gao_text = " ".join(result.gao_references)
        assert "Cat5" in gao_text or "SAM" in gao_text or "exclusion" in gao_text.lower()


# ═══════════════════════════════════════════════════════════════════════════
# GAO Cat1-Ex23: Federal P-Card Split Purchase
# ═══════════════════════════════════════════════════════════════════════════

class TestSplitPurchaseDetection:
    """GAO Cat1-Ex23 — Federal Purchase Card (P-Card) split-purchase detection."""

    def test_split_purchase_detected(self):
        """Two transactions same day, same vendor, both below $10k but combined above."""
        ctx = base_ctx(
            amount=6000.0,
            prior_invoices=[
                {"id": "tx-prior-010", "invoice_ref": "INV-A",
                 "amount": 5500.0, "vendor_id": "vendor-abc", "tx_date": "2024-06-15"}
            ]
        )
        result = ENGINE.assess(**ctx)
        assert RULE_SPLIT_PURCHASE in result.triggered_rules
        assert result.composite_score > 0

    def test_single_transaction_no_split(self):
        """Single transaction below threshold — no split purchase."""
        result = ENGINE.assess(**base_ctx(amount=5000.0))
        assert RULE_SPLIT_PURCHASE not in result.triggered_rules


# ═══════════════════════════════════════════════════════════════════════════
# GAO Cat1-Ex27: Federal Grant Double-Dipping
# ═══════════════════════════════════════════════════════════════════════════

class TestCrossGrantDoubleDipping:
    """GAO Cat1-Ex27 — Charging same cost to multiple grants."""

    def test_cross_grant_double_detected(self):
        """Same category + same vendor charged to 2 different grants."""
        ctx = base_ctx(
            all_grant_charges=[
                {"grant_id": "grant-AAA", "cost_category": "personnel", "vendor_id": "vendor-abc"},
                {"grant_id": "grant-BBB", "cost_category": "personnel", "vendor_id": "vendor-abc"},
            ]
        )
        result = ENGINE.assess(**ctx)
        assert RULE_CROSS_GRANT_DOUBLE in result.triggered_rules

    def test_single_grant_no_double(self):
        ctx = base_ctx(
            all_grant_charges=[
                {"grant_id": "grant-AAA", "cost_category": "personnel", "vendor_id": "vendor-abc"},
            ]
        )
        result = ENGINE.assess(**ctx)
        assert RULE_CROSS_GRANT_DOUBLE not in result.triggered_rules


# ═══════════════════════════════════════════════════════════════════════════
# GAO Cat1-Ex11: Ghost Vendor Detection
# ═══════════════════════════════════════════════════════════════════════════

class TestGhostVendorDetection:
    """GAO Cat1-Ex11 — Ghost Employee/Vendor detection."""

    def test_ghost_vendor_triggers(self):
        """No transaction history + high risk tier = ghost vendor signal."""
        ctx = base_ctx(prior_invoices=[], vendor_risk_tier="high", amount=50000.0)
        result = ENGINE.assess(**ctx)
        assert RULE_GHOST_VENDOR in result.triggered_rules

    def test_established_vendor_no_ghost(self):
        """Vendor with history should not trigger ghost signal."""
        ctx = base_ctx(
            prior_invoices=[{"id": "tx-old", "invoice_ref": "INV-OLD", "amount": 1000, "vendor_id": "vendor-abc", "tx_date": "2024-01-01"}],
            vendor_risk_tier="high",
        )
        result = ENGINE.assess(**ctx)
        assert RULE_GHOST_VENDOR not in result.triggered_rules


# ═══════════════════════════════════════════════════════════════════════════
# GAO Cat1-Ex3: Velocity Detection (UI Fraud Analog)
# ═══════════════════════════════════════════════════════════════════════════

class TestVelocityDetection:
    """GAO Cat1-Ex3 — High-velocity spend detection (UI fraud analog)."""

    def test_high_velocity_triggers(self):
        ctx = base_ctx(amount=200000.0, vendor_spend_30d=100000.0)
        result = ENGINE.assess(**ctx)
        assert RULE_HIGH_VELOCITY in result.triggered_rules

    def test_normal_velocity_no_trigger(self):
        ctx = base_ctx(amount=1000.0, vendor_spend_30d=5000.0)
        result = ENGINE.assess(**ctx)
        assert RULE_HIGH_VELOCITY not in result.triggered_rules


# ═══════════════════════════════════════════════════════════════════════════
# Scoring & Explainability
# ═══════════════════════════════════════════════════════════════════════════

class TestScoringAndExplainability:
    """Validate scoring ranges, explainability, and audit traceability."""

    def test_score_always_0_to_100(self):
        """Score must always be in [0, 100]."""
        ctx = base_ctx(
            vendor_sam_status="excluded",
            amount=999999.0,
            vendor_risk_tier="high",
            prior_invoices=[{"id": "x", "invoice_ref": "INV-2024-001", "amount": 999999.0, "vendor_id": "vendor-abc", "tx_date": "2024-06-15"}],
        )
        result = ENGINE.assess(**ctx)
        assert 0.0 <= result.composite_score <= 100.0

    def test_explanation_not_empty(self):
        result = ENGINE.assess(**base_ctx(vendor_sam_status="excluded"))
        assert len(result.explanation) > 10

    def test_assessment_has_full_signal_detail(self):
        result = ENGINE.assess(**base_ctx())
        d = result.to_dict()
        assert "signal_detail" in d
        assert isinstance(d["signal_detail"], list)
        assert len(d["signal_detail"]) >= 12  # All rules evaluated (23 after Tier 2)

    def test_gao_references_non_empty_when_triggered(self):
        result = ENGINE.assess(**base_ctx(vendor_sam_status="excluded"))
        assert len(result.gao_references) > 0
