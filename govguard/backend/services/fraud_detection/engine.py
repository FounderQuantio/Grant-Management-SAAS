"""
GovGuard v2 — Fraud Detection Engine
====================================
NEW FILE: services/fraud_detection/engine.py

Rule-based + ML hybrid fraud detection engine.
Plugs into existing transaction pipeline via Celery task hook.

LEGACY HOOK: Called from existing workers/payment_tasks.py after score_transaction_async
NEW CAPABILITY: Multi-signal fraud scoring with GAO-aligned rule library

GAO Alignment:
  - Cat 1 Ex 4  (PPP/EIDL loan fraud — entity graph clustering)
  - Cat 1 Ex 10 (Duplicate vendor payments — invoice dedup)
  - Cat 5 Ex 25 (Pre-award risk scoring — integrated scoring)
  - Cat 5 Ex 22 (Federated invoice anomaly — cross-vendor patterns)
"""
from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from typing import Optional
from uuid import UUID

import structlog

log = structlog.get_logger()

# Lazy import to avoid circular deps; classifier is optional
_classifier = None

def _get_classifier():
    global _classifier
    if _classifier is None:
        try:
            from ml.fraud_classifier import FraudClassifier
            _classifier = FraudClassifier()
        except Exception as exc:
            log.warning("fraud_classifier.import_failed", error=str(exc))
            _classifier = False  # mark as unavailable so we don't retry
    return _classifier if _classifier is not False else None

# ── Rule IDs (traceable to GAO document) ──────────────────────────────────

RULE_DUPLICATE_EXACT      = "FDE-001"   # Cat 1 Ex 10
RULE_DUPLICATE_FUZZY      = "FDE-002"   # Cat 1 Ex 10
RULE_ROUND_DOLLAR         = "FDE-003"   # Cat 1 Ex 8 (SNAP trafficking signal)
RULE_SPLIT_PURCHASE       = "FDE-004"   # Cat 1 Ex 23 (P-card split)
RULE_VENDOR_SAM_EXCLUDED  = "FDE-005"   # Cat 5 Ex 4
RULE_EXCEEDS_BUDGET_CAT   = "FDE-006"   # 2 CFR 200.405
RULE_WEEKEND_TRANSACTION  = "FDE-007"   # Cat 1 Ex 9 (travel card)
RULE_HIGH_VELOCITY        = "FDE-008"   # Cat 1 Ex 3 (UI fraud velocity)
RULE_AMOUNT_THRESHOLD     = "FDE-009"   # Cat 1 Ex 25 (T&M overbilling)
RULE_GHOST_VENDOR         = "FDE-010"   # Cat 1 Ex 11 (ghost employee analog)
RULE_RELATED_PARTY        = "FDE-011"   # Cat 5 Ex 13 (PEP/related-party)
RULE_CROSS_GRANT_DOUBLE   = "FDE-012"   # Cat 1 Ex 27 (grant double-dipping)
RULE_LABOR_RATE_MISMATCH  = "FDE-013"   # Cat 2 Labor category T&M mismatch
RULE_ACQUISITION_OVERRUN  = "FDE-014"   # Cat 2/6 EVM cost-growth / MDAP overrun
RULE_PROCUREMENT_ROTATION = "FDE-015"   # Cat 1 Ex 26 bid-rigging rotation proxy
RULE_DEVICE_FINGERPRINT   = "FDE-016"   # Cat 4/2 device-fingerprint ring
RULE_SYNTHETIC_ID_ECBSV   = "FDE-017"   # Cat 4 SSA E-CBSv synthetic-ID mismatch
RULE_OIG_ENTITY_LINK      = "FDE-018"   # Cat 5 OIG cross-entity link
RULE_AUTH_WINDOW_VIOLATION = "FDE-019"  # Cat 3 healthcare auth-window violation
RULE_CRYPTO_UNDERREPORT   = "FDE-020"   # Cat 5 crypto gain underreporting
RULE_SPOOFING_CANCEL_RATE = "FDE-021"   # Cat 1 spoofing via order-cancel pattern
RULE_SANCTIONS_LAYERING   = "FDE-022"   # Cat 5 OFAC sanctions layering / SDN match
RULE_RA_UPCODING          = "FDE-023"   # Cat 3 risk-adjustment upcoding
# ── Tier 3 rules ─────────────────────────────────────────────────────────────
RULE_EITC_CROSS_CLAIM     = "FDE-024"   # Cat 2 EITC same-child dual-filer
RULE_DISASTER_AID_DUP     = "FDE-025"   # Cat 3 Stafford disaster-aid duplication
RULE_DME_GEO_OUTLIER      = "FDE-026"   # Cat 2 DME geographic mismatch
RULE_HOSPICE_OUTLIER      = "FDE-027"   # Cat 2 hospice LOS/live-discharge outlier
RULE_VOLUME_SPIKE_SCHEME  = "FDE-028"   # Cat 2 emerging-scheme volume spike (CGx)
RULE_DUPLICATE_INSPECTION = "FDE-029"   # Cat 5 duplicate FSIS/FDA inspection
RULE_INCIDENT_DEDUP       = "FDE-030"   # Cat 5 TSA/CISA incident report dedup
RULE_DATA_CALL_OVERLAP    = "FDE-031"   # Cat 5 overlapping regulatory data calls
RULE_GRANT_ATTR_OVERLAP   = "FDE-032"   # Cat 3 STEM grant attribution overlap
RULE_DUPLICATE_INTAKE     = "FDE-033"   # Cat 4 HMIS/VA duplicate homeless intake
RULE_STALE_RECOMMENDATION = "FDE-034"   # Cat 6 stale GAO priority recommendation
RULE_RECON_DRIFT          = "FDE-035"   # Cat 1 IRS legacy reconciliation drift
RULE_WAIT_TIME_DIVERGENCE = "FDE-036"   # Cat 6 VA wait-time reporting divergence
RULE_EXCEPTION_RATE_SPIKE = "FDE-037"   # Cat 3 FAFSA exception-rate regression
RULE_CYBER_BACKLOG        = "FDE-038"   # Cat 6 FISMA high-impact cyber backlog
RULE_FOREIGN_PASSTHROUGH  = "FDE-039"   # Cat 5 passthrough foreign money flow
RULE_TITLE_IV_RISK        = "FDE-040"   # Cat 3 Title IV institution risk (CDR/90-10)
RULE_IMPORT_TRANSSHIPMENT = "FDE-041"   # Cat 5 UFLPA import transshipment
RULE_PROPERTY_UNDERUTIL   = "FDE-042"   # Cat 6 federal real-property underutilization
RULE_SAM_TRUE_DOWN        = "FDE-043"   # Cat 6 SAM.gov seat true-down opportunity
RULE_CLEARANCE_FIN_RISK   = "FDE-044"   # Cat 4 security-clearance financial risk
RULE_WHISTLEBLOWER_CLUSTER = "FDE-045"  # Cat 5 whistleblower tip cluster
RULE_CONTRACTOR_PERF_RISK = "FDE-046"   # Cat 6 cross-agency CPARS performance risk
RULE_MULTI_PROGRAM_RING   = "FDE-047"   # Cat 4 multi-program fraud ring


@dataclass
class FraudSignal:
    rule_id: str
    description: str
    weight: float            # 0.0–1.0 contribution to final score
    triggered: bool = False
    evidence: dict = field(default_factory=dict)


@dataclass
class FraudAssessment:
    transaction_id: str
    composite_score: float       # 0–100
    risk_tier: str               # LOW / MEDIUM / HIGH / CRITICAL
    signals: list[FraudSignal]
    triggered_rules: list[str]
    recommended_action: str      # APPROVE / REVIEW / HOLD / BLOCK
    gao_references: list[str]
    explanation: str
    scoring_method: str = "rules_weighted_sum"  # "ml_xgboost" | "rules_weighted_sum"
    shadow_comparison: Optional[dict] = None    # populated when ml_xgboost is active

    def to_dict(self) -> dict:
        return {
            "transaction_id": self.transaction_id,
            "composite_score": self.composite_score,
            "risk_tier": self.risk_tier,
            "scoring_method": self.scoring_method,
            "triggered_rules": self.triggered_rules,
            "recommended_action": self.recommended_action,
            "gao_references": self.gao_references,
            "explanation": self.explanation,
            "signal_detail": [
                {"rule": s.rule_id, "triggered": s.triggered,
                 "weight": s.weight, "evidence": s.evidence}
                for s in self.signals
            ],
        }


class FraudDetectionEngine:
    """
    Stateless fraud engine. Instantiate once (singleton pattern in production).
    All DB lookups are passed in as pre-fetched context to keep the engine
    testable and decoupled from SQLAlchemy sessions.
    """

    # Scoring weights per rule (×10 = points contribution toward 100-pt composite)
    RULE_WEIGHTS = {
        RULE_DUPLICATE_EXACT:      2.5,
        RULE_DUPLICATE_FUZZY:      1.8,
        RULE_ROUND_DOLLAR:         0.6,
        RULE_SPLIT_PURCHASE:       1.2,
        RULE_VENDOR_SAM_EXCLUDED:  3.0,   # Hard block signal
        RULE_EXCEEDS_BUDGET_CAT:   1.5,
        RULE_WEEKEND_TRANSACTION:  0.4,
        RULE_HIGH_VELOCITY:        1.8,
        RULE_AMOUNT_THRESHOLD:     1.0,
        RULE_GHOST_VENDOR:         2.0,
        RULE_RELATED_PARTY:        1.6,
        RULE_CROSS_GRANT_DOUBLE:   2.0,
        RULE_LABOR_RATE_MISMATCH:  2.5,
        RULE_ACQUISITION_OVERRUN:  2.5,
        RULE_PROCUREMENT_ROTATION: 2.5,
        RULE_DEVICE_FINGERPRINT:   2.5,
        RULE_SYNTHETIC_ID_ECBSV:   2.5,
        RULE_OIG_ENTITY_LINK:      2.5,
        RULE_AUTH_WINDOW_VIOLATION: 3.0,
        RULE_CRYPTO_UNDERREPORT:   2.5,
        RULE_SPOOFING_CANCEL_RATE: 2.5,
        RULE_SANCTIONS_LAYERING:   3.0,   # Hard block signal
        RULE_RA_UPCODING:          2.5,
        # Tier 3
        RULE_EITC_CROSS_CLAIM:     2.5,
        RULE_DISASTER_AID_DUP:     2.5,
        RULE_DME_GEO_OUTLIER:      2.5,
        RULE_HOSPICE_OUTLIER:      2.5,
        RULE_VOLUME_SPIKE_SCHEME:  2.5,
        RULE_DUPLICATE_INSPECTION: 2.5,
        RULE_INCIDENT_DEDUP:       2.5,
        RULE_DATA_CALL_OVERLAP:    2.5,
        RULE_GRANT_ATTR_OVERLAP:   2.5,
        RULE_DUPLICATE_INTAKE:     2.5,
        RULE_STALE_RECOMMENDATION: 2.5,
        RULE_RECON_DRIFT:          2.5,
        RULE_WAIT_TIME_DIVERGENCE: 2.5,
        RULE_EXCEPTION_RATE_SPIKE: 2.5,
        RULE_CYBER_BACKLOG:        2.5,
        RULE_FOREIGN_PASSTHROUGH:  2.5,
        RULE_TITLE_IV_RISK:        2.5,
        RULE_IMPORT_TRANSSHIPMENT: 2.5,
        RULE_PROPERTY_UNDERUTIL:   2.5,
        RULE_SAM_TRUE_DOWN:        2.5,
        RULE_CLEARANCE_FIN_RISK:   2.5,
        RULE_WHISTLEBLOWER_CLUSTER: 2.5,
        RULE_CONTRACTOR_PERF_RISK: 2.5,
        RULE_MULTI_PROGRAM_RING:   2.5,
    }

    def assess(
        self,
        *,
        transaction_id: str,
        amount: float,
        vendor_id: str,
        vendor_sam_status: str,
        invoice_ref: str,
        tx_date: date,
        cost_category: str,
        grant_budget: dict,            # {category: budget_amount}
        prior_invoices: list[dict],    # recent txns for this vendor/grant
        vendor_spend_30d: float,
        all_grant_charges: list[dict], # for cross-grant double-dipping
        vendor_risk_tier: str,
        related_party_flag: bool,
        extra_signals: dict | None = None,  # FDE-013+ extended signal fields
    ) -> FraudAssessment:
        """
        Evaluate all fraud rules against a transaction context.
        Returns a fully attributed FraudAssessment.
        """
        signals = self._build_signals(
            amount=amount,
            vendor_id=vendor_id,
            vendor_sam_status=vendor_sam_status,
            invoice_ref=invoice_ref,
            tx_date=tx_date,
            cost_category=cost_category,
            grant_budget=grant_budget,
            prior_invoices=prior_invoices,
            vendor_spend_30d=vendor_spend_30d,
            all_grant_charges=all_grant_charges,
            vendor_risk_tier=vendor_risk_tier,
            related_party_flag=related_party_flag,
            extra_signals=extra_signals or {},
        )

        triggered = [s for s in signals if s.triggered]

        # Rules-only score always computed — used as fallback and shadow baseline
        rules_composite = min(100.0, round(sum(s.weight * 10 for s in triggered), 2))

        # Phase 2: use trained XGBoost model if available; fall back to weighted sum
        clf = _get_classifier()
        shadow_comparison: Optional[dict] = None
        if clf and clf.available():
            try:
                prob = clf.predict_proba(signals)
                composite = round(min(100.0, prob * 100.0), 2)
                scoring_method = "ml_xgboost"
                log.debug("fraud_engine.ml_score", composite=composite, tx=transaction_id)
            except Exception as exc:
                log.warning("fraud_engine.ml_fallback", error=str(exc))
                composite = rules_composite
                scoring_method = "rules_weighted_sum"
        else:
            composite = rules_composite
            scoring_method = "rules_weighted_sum"

        tier = self._tier(composite, triggered)
        action = self._action(tier, triggered)
        gao_refs = self._gao_refs(triggered)
        explanation = self._explain(triggered, composite)

        # Shadow comparison: only when ML is active
        if scoring_method == "ml_xgboost":
            rules_tier   = self._tier(rules_composite, triggered)
            rules_action = self._action(rules_tier, triggered)
            shadow_comparison = {
                "rules_score":  rules_composite,
                "ml_score":     composite,
                "rules_action": rules_action,
                "ml_action":    action,
                "agreement":    rules_action == action,
                "delta":        round(composite - rules_composite, 2),
            }

        return FraudAssessment(
            transaction_id=transaction_id,
            composite_score=composite,
            risk_tier=tier,
            signals=signals,
            triggered_rules=[s.rule_id for s in triggered],
            recommended_action=action,
            gao_references=gao_refs,
            explanation=explanation,
            scoring_method=scoring_method,
            shadow_comparison=shadow_comparison,
        )

    # ── Private helpers ──────────────────────────────────────────────────

    def _build_signals(self, **ctx) -> list[FraudSignal]:
        return [
            self._check_duplicate_exact(ctx),
            self._check_duplicate_fuzzy(ctx),
            self._check_round_dollar(ctx),
            self._check_split_purchase(ctx),
            self._check_sam_excluded(ctx),
            self._check_exceeds_budget(ctx),
            self._check_weekend(ctx),
            self._check_high_velocity(ctx),
            self._check_amount_threshold(ctx),
            self._check_ghost_vendor(ctx),
            self._check_related_party(ctx),
            self._check_cross_grant_double(ctx),
            self._check_labor_rate_mismatch(ctx),
            self._check_acquisition_overrun(ctx),
            self._check_procurement_rotation(ctx),
            self._check_device_fingerprint(ctx),
            self._check_synthetic_id_ecbsv(ctx),
            self._check_oig_entity_link(ctx),
            self._check_auth_window_violation(ctx),
            self._check_crypto_underreport(ctx),
            self._check_spoofing_cancel_rate(ctx),
            self._check_sanctions_layering(ctx),
            self._check_ra_upcoding(ctx),
            # Tier 3
            self._check_eitc_cross_claim(ctx),
            self._check_disaster_aid_dup(ctx),
            self._check_dme_geo_outlier(ctx),
            self._check_hospice_outlier(ctx),
            self._check_volume_spike_scheme(ctx),
            self._check_duplicate_inspection(ctx),
            self._check_incident_dedup(ctx),
            self._check_data_call_overlap(ctx),
            self._check_grant_attr_overlap(ctx),
            self._check_duplicate_intake(ctx),
            self._check_stale_recommendation(ctx),
            self._check_recon_drift(ctx),
            self._check_wait_time_divergence(ctx),
            self._check_exception_rate_spike(ctx),
            self._check_cyber_backlog(ctx),
            self._check_foreign_passthrough(ctx),
            self._check_title_iv_risk(ctx),
            self._check_import_transshipment(ctx),
            self._check_property_underutil(ctx),
            self._check_sam_true_down(ctx),
            self._check_clearance_fin_risk(ctx),
            self._check_whistleblower_cluster(ctx),
            self._check_contractor_perf_risk(ctx),
            self._check_multi_program_ring(ctx),
        ]

    def _check_duplicate_exact(self, ctx: dict) -> FraudSignal:
        sig = FraudSignal(RULE_DUPLICATE_EXACT, "Exact duplicate invoice", self.RULE_WEIGHTS[RULE_DUPLICATE_EXACT])
        for inv in ctx.get("prior_invoices", []):
            if (inv.get("invoice_ref") == ctx["invoice_ref"]
                    and abs(float(inv.get("amount", 0)) - ctx["amount"]) < 0.01
                    and inv.get("vendor_id") == ctx["vendor_id"]):
                sig.triggered = True
                sig.evidence = {"matched_tx": inv.get("id"), "invoice_ref": ctx["invoice_ref"]}
                break
        return sig

    def _check_duplicate_fuzzy(self, ctx: dict) -> FraudSignal:
        """Fuzzy match: same amount, same vendor, invoice within edit distance 2."""
        sig = FraudSignal(RULE_DUPLICATE_FUZZY, "Fuzzy duplicate invoice", self.RULE_WEIGHTS[RULE_DUPLICATE_FUZZY])
        ref = ctx["invoice_ref"].upper().strip()
        for inv in ctx.get("prior_invoices", []):
            other_ref = inv.get("invoice_ref", "").upper().strip()
            if (abs(float(inv.get("amount", 0)) - ctx["amount"]) < 0.01
                    and inv.get("vendor_id") == ctx["vendor_id"]
                    and inv.get("invoice_ref") != ctx["invoice_ref"]
                    and self._levenshtein(ref, other_ref) <= 2):
                sig.triggered = True
                sig.evidence = {"similar_ref": inv.get("invoice_ref"), "edit_distance": self._levenshtein(ref, other_ref)}
                break
        return sig

    def _check_round_dollar(self, ctx: dict) -> FraudSignal:
        sig = FraudSignal(RULE_ROUND_DOLLAR, "Suspiciously round dollar amount", self.RULE_WEIGHTS[RULE_ROUND_DOLLAR])
        amt = ctx["amount"]
        if amt > 1000 and amt % 1000 == 0:
            sig.triggered = True
            sig.evidence = {"amount": amt, "pattern": "round_thousand"}
        elif amt > 500 and amt % 500 == 0:
            sig.triggered = True
            sig.evidence = {"amount": amt, "pattern": "round_five_hundred"}
        return sig

    def _check_split_purchase(self, ctx: dict) -> FraudSignal:
        """Detect split purchases designed to evade approval thresholds."""
        sig = FraudSignal(RULE_SPLIT_PURCHASE, "Potential split purchase", self.RULE_WEIGHTS[RULE_SPLIT_PURCHASE])
        THRESHOLD = 10000.0  # Simplified acquisition threshold
        if ctx["amount"] < THRESHOLD:
            same_vendor_same_day = [
                inv for inv in ctx.get("prior_invoices", [])
                if inv.get("vendor_id") == ctx["vendor_id"]
                and inv.get("tx_date") == str(ctx["tx_date"])
                and float(inv.get("amount", 0)) < THRESHOLD
            ]
            if same_vendor_same_day:
                total = sum(float(i.get("amount", 0)) for i in same_vendor_same_day) + ctx["amount"]
                if total > THRESHOLD:
                    sig.triggered = True
                    sig.evidence = {"same_day_count": len(same_vendor_same_day), "combined_total": total, "threshold": THRESHOLD}
        return sig

    def _check_sam_excluded(self, ctx: dict) -> FraudSignal:
        sig = FraudSignal(RULE_VENDOR_SAM_EXCLUDED, "Vendor on SAM.gov exclusion list", self.RULE_WEIGHTS[RULE_VENDOR_SAM_EXCLUDED])
        if ctx.get("vendor_sam_status") in ("excluded", "suspended"):
            sig.triggered = True
            sig.evidence = {"sam_status": ctx["vendor_sam_status"]}
        return sig

    def _check_exceeds_budget(self, ctx: dict) -> FraudSignal:
        sig = FraudSignal(RULE_EXCEEDS_BUDGET_CAT, "Transaction exceeds approved budget category", self.RULE_WEIGHTS[RULE_EXCEEDS_BUDGET_CAT])
        cat = ctx.get("cost_category")
        budget = ctx.get("grant_budget", {})
        if cat and cat not in budget:
            sig.triggered = True
            sig.evidence = {"cost_category": cat, "allowed_categories": list(budget.keys())}
        elif cat and budget.get(cat, float("inf")) < ctx["amount"]:
            sig.triggered = True
            sig.evidence = {"cost_category": cat, "approved": budget.get(cat), "requested": ctx["amount"]}
        return sig

    def _check_weekend(self, ctx: dict) -> FraudSignal:
        sig = FraudSignal(RULE_WEEKEND_TRANSACTION, "Transaction on weekend", self.RULE_WEIGHTS[RULE_WEEKEND_TRANSACTION])
        if ctx.get("tx_date") and ctx["tx_date"].weekday() >= 5:
            sig.triggered = True
            sig.evidence = {"tx_date": str(ctx["tx_date"]), "day": ctx["tx_date"].strftime("%A")}
        return sig

    def _check_high_velocity(self, ctx: dict) -> FraudSignal:
        """High spend velocity from this vendor in last 30 days."""
        sig = FraudSignal(RULE_HIGH_VELOCITY, "High vendor spend velocity (30d)", self.RULE_WEIGHTS[RULE_HIGH_VELOCITY])
        VELOCITY_THRESHOLD = 250000.0
        total = ctx.get("vendor_spend_30d", 0) + ctx["amount"]
        if total > VELOCITY_THRESHOLD:
            sig.triggered = True
            sig.evidence = {"vendor_30d_total": total, "threshold": VELOCITY_THRESHOLD, "current_amount": ctx["amount"]}
        return sig

    def _check_amount_threshold(self, ctx: dict) -> FraudSignal:
        sig = FraudSignal(RULE_AMOUNT_THRESHOLD, "Unusually large single transaction", self.RULE_WEIGHTS[RULE_AMOUNT_THRESHOLD])
        HIGH_AMOUNT = 100000.0
        if ctx["amount"] > HIGH_AMOUNT:
            sig.triggered = True
            sig.evidence = {"amount": ctx["amount"], "threshold": HIGH_AMOUNT}
        return sig

    def _check_ghost_vendor(self, ctx: dict) -> FraudSignal:
        """Ghost vendor: high risk tier with no historical transactions."""
        sig = FraudSignal(RULE_GHOST_VENDOR, "Potential ghost vendor (no transaction history)", self.RULE_WEIGHTS[RULE_GHOST_VENDOR])
        no_history = len(ctx.get("prior_invoices", [])) == 0
        high_risk = ctx.get("vendor_risk_tier") == "high"
        if no_history and high_risk:
            sig.triggered = True
            sig.evidence = {"prior_invoice_count": 0, "vendor_risk_tier": "high"}
        return sig

    def _check_related_party(self, ctx: dict) -> FraudSignal:
        sig = FraudSignal(RULE_RELATED_PARTY, "Related party / conflict of interest", self.RULE_WEIGHTS[RULE_RELATED_PARTY])
        if ctx.get("related_party_flag"):
            sig.triggered = True
            sig.evidence = {"related_party_flag": True}
        return sig

    def _check_cross_grant_double(self, ctx: dict) -> FraudSignal:
        """Detect the same cost category charged to multiple active grants."""
        sig = FraudSignal(RULE_CROSS_GRANT_DOUBLE, "Potential cross-grant double charge", self.RULE_WEIGHTS[RULE_CROSS_GRANT_DOUBLE])
        cat = ctx.get("cost_category")
        grant_ids_with_same_cat = set()
        for charge in ctx.get("all_grant_charges", []):
            if charge.get("cost_category") == cat and charge.get("vendor_id") == ctx["vendor_id"]:
                grant_ids_with_same_cat.add(charge.get("grant_id"))
        if len(grant_ids_with_same_cat) >= 2:
            sig.triggered = True
            sig.evidence = {"duplicate_grant_count": len(grant_ids_with_same_cat), "cost_category": cat}
        return sig

    def _check_labor_rate_mismatch(self, ctx: dict) -> FraudSignal:
        """FDE-013: Billed labor category doesn't match actual qualifications."""
        sig = FraudSignal(RULE_LABOR_RATE_MISMATCH, "Labor category rate mismatch", self.RULE_WEIGHTS[RULE_LABOR_RATE_MISMATCH])
        xs = ctx.get("extra_signals", {})
        yoe = xs.get("resume_median_yoe")
        min_yoe = xs.get("lcat_min_yoe")
        nlp = xs.get("nlp_match_score")
        if yoe is not None and min_yoe is not None and yoe < min_yoe * 0.5:
            sig.triggered = True
            sig.evidence = {"resume_median_yoe": yoe, "lcat_min_yoe": min_yoe}
        elif nlp is not None and nlp < 0.25:
            sig.triggered = True
            sig.evidence = {"nlp_match_score": nlp}
        return sig

    def _check_acquisition_overrun(self, ctx: dict) -> FraudSignal:
        """FDE-014: EVM deviation or cost-growth forecast exceeds acceptable bounds."""
        sig = FraudSignal(RULE_ACQUISITION_OVERRUN, "Acquisition cost overrun / EVM deviation", self.RULE_WEIGHTS[RULE_ACQUISITION_OVERRUN])
        xs = ctx.get("extra_signals", {})
        cpi = xs.get("cpi")
        spi = xs.get("spi")
        if cpi is not None and spi is not None and cpi < 0.85 and spi < 0.85:
            sig.triggered = True
            sig.evidence = {"cpi": cpi, "spi": spi}
        elif xs.get("predicted_overrun_pct", 0.0) > 0.15:
            sig.triggered = True
            sig.evidence = {"predicted_overrun_pct": xs["predicted_overrun_pct"]}
        elif xs.get("p65_lcc") and xs.get("baseline_lcc"):
            if xs["p65_lcc"] / xs["baseline_lcc"] > 1.2:
                sig.triggered = True
                sig.evidence = {"p65_lcc": xs["p65_lcc"], "baseline_lcc": xs["baseline_lcc"], "ratio": round(xs["p65_lcc"] / xs["baseline_lcc"], 3)}
        return sig

    def _check_procurement_rotation(self, ctx: dict) -> FraudSignal:
        """FDE-015: Statistical vendor-rotation pattern consistent with bid rigging."""
        sig = FraudSignal(RULE_PROCUREMENT_ROTATION, "Procurement vendor rotation (bid-rigging proxy)", self.RULE_WEIGHTS[RULE_PROCUREMENT_ROTATION])
        xs = ctx.get("extra_signals", {})
        chi_p = xs.get("rotation_chi_square_p", 1.0)
        cosine = xs.get("proposal_cosine_max", 0.0)
        if chi_p < 0.05 and cosine > 0.7:
            sig.triggered = True
            sig.evidence = {"rotation_chi_square_p": chi_p, "proposal_cosine_max": cosine}
        return sig

    def _check_device_fingerprint(self, ctx: dict) -> FraudSignal:
        """FDE-016: Shared device fingerprint ring or prior fraud linkage."""
        sig = FraudSignal(RULE_DEVICE_FINGERPRINT, "Device fingerprint ring / shared-device fraud cluster", self.RULE_WEIGHTS[RULE_DEVICE_FINGERPRINT])
        xs = ctx.get("extra_signals", {})
        dmc = xs.get("device_match_count")
        uac = xs.get("unique_applicant_count")
        if dmc is not None and uac is not None:
            ratio = dmc / max(uac, 1)
            if ratio > 5:
                sig.triggered = True
                sig.evidence = {"device_match_count": dmc, "unique_applicant_count": uac, "ratio": round(ratio, 1)}
        if not sig.triggered and xs.get("prior_fraud_link"):
            sig.triggered = True
            sig.evidence = {"prior_fraud_link": xs["prior_fraud_link"]}
        if not sig.triggered and xs.get("clickstream_entropy", 1.0) < 0.2:
            sig.triggered = True
            sig.evidence = {"clickstream_entropy": xs["clickstream_entropy"]}
        return sig

    def _check_synthetic_id_ecbsv(self, ctx: dict) -> FraudSignal:
        """FDE-017: SSA E-CBSv returns no-match on a thin-file applicant."""
        sig = FraudSignal(RULE_SYNTHETIC_ID_ECBSV, "Synthetic identity — E-CBSv no-match on thin file", self.RULE_WEIGHTS[RULE_SYNTHETIC_ID_ECBSV])
        xs = ctx.get("extra_signals", {})
        if xs.get("ecbsv_match") == "no_match" and xs.get("credit_file_age_months", 99) < 12:
            sig.triggered = True
            sig.evidence = {"ecbsv_match": "no_match", "credit_file_age_months": xs["credit_file_age_months"]}
        return sig

    def _check_oig_entity_link(self, ctx: dict) -> FraudSignal:
        """FDE-018: Entity linked to an open OIG investigation or exclusion."""
        sig = FraudSignal(RULE_OIG_ENTITY_LINK, "OIG cross-entity link detected", self.RULE_WEIGHTS[RULE_OIG_ENTITY_LINK])
        xs = ctx.get("extra_signals", {})
        oig_fields = ("oig_case_id", "oig_exclusion_date", "oig_match_score",
                      "oig_entity_id", "hhs_oig_case", "ssa_oig_case")
        for f in oig_fields:
            if xs.get(f):
                sig.triggered = True
                sig.evidence = {f: xs[f]}
                break
        return sig

    def _check_auth_window_violation(self, ctx: dict) -> FraudSignal:
        """FDE-019: Service rendered after the prior-authorization expiry date."""
        sig = FraudSignal(RULE_AUTH_WINDOW_VIOLATION, "Service rendered outside authorization window", self.RULE_WEIGHTS[RULE_AUTH_WINDOW_VIOLATION])
        xs = ctx.get("extra_signals", {})
        dos = xs.get("dos")
        auth_until = xs.get("auth_valid_until")
        if dos and auth_until:
            try:
                if str(dos) > str(auth_until):
                    sig.triggered = True
                    sig.evidence = {"dos": str(dos), "auth_valid_until": str(auth_until)}
            except (TypeError, ValueError):
                pass
        return sig

    def _check_crypto_underreport(self, ctx: dict) -> FraudSignal:
        """FDE-020: On-chain realized gain significantly exceeds tax-reported figure."""
        sig = FraudSignal(RULE_CRYPTO_UNDERREPORT, "Crypto gain underreporting — on-chain vs reported gap", self.RULE_WEIGHTS[RULE_CRYPTO_UNDERREPORT])
        xs = ctx.get("extra_signals", {})
        realized = xs.get("realized_gain_usd", 0.0)
        reported = xs.get("reported_gain_usd", 0.0)
        confidence = xs.get("attribution_confidence", 0.0)
        if realized > 0 and confidence > 0.7:
            underreport_pct = (realized - reported) / realized
            if underreport_pct > 0.5:
                sig.triggered = True
                sig.evidence = {"realized_gain_usd": realized, "reported_gain_usd": reported, "underreport_pct": round(underreport_pct, 3)}
        return sig

    def _check_spoofing_cancel_rate(self, ctx: dict) -> FraudSignal:
        """FDE-021: High order-cancellation rate after price observation (spoofing)."""
        sig = FraudSignal(RULE_SPOOFING_CANCEL_RATE, "Order-spoofing cancellation rate anomaly", self.RULE_WEIGHTS[RULE_SPOOFING_CANCEL_RATE])
        xs = ctx.get("extra_signals", {})
        if xs.get("cancel_pct", 0.0) > 0.9 and xs.get("orders_placed", 0) > 20:
            sig.triggered = True
            sig.evidence = {"cancel_pct": xs["cancel_pct"], "orders_placed": xs["orders_placed"]}
        return sig

    def _check_sanctions_layering(self, ctx: dict) -> FraudSignal:
        """FDE-022: SDN-list match or shell-company layering to evade OFAC sanctions."""
        sig = FraudSignal(RULE_SANCTIONS_LAYERING, "OFAC sanctions layering / SDN entity match", self.RULE_WEIGHTS[RULE_SANCTIONS_LAYERING])
        xs = ctx.get("extra_signals", {})
        if xs.get("sdn_party_id"):
            sig.triggered = True
            sig.evidence = {"sdn_party_id": xs["sdn_party_id"]}
        elif xs.get("shell_layers", 0) >= 2 and xs.get("boi_common_owner"):
            sig.triggered = True
            sig.evidence = {"shell_layers": xs["shell_layers"], "boi_common_owner": xs["boi_common_owner"]}
        return sig

    def _check_ra_upcoding(self, ctx: dict) -> FraudSignal:
        """FDE-023: Risk-adjustment diagnoses lack supporting encounter documentation."""
        sig = FraudSignal(RULE_RA_UPCODING, "Risk-adjustment upcoding — insufficient encounter support", self.RULE_WEIGHTS[RULE_RA_UPCODING])
        xs = ctx.get("extra_signals", {})
        support_pct = xs.get("encounter_support_pct", 1.0)
        impact = xs.get("ra_payment_impact_usd_m", 0.0)
        if support_pct < 0.3 and impact > 1.0:
            sig.triggered = True
            sig.evidence = {"encounter_support_pct": support_pct, "ra_payment_impact_usd_m": impact}
        return sig

    def _check_eitc_cross_claim(self, ctx: dict) -> FraudSignal:
        """FDE-024: Same child claimed for EITC by two filers with no SSA dependency match."""
        sig = FraudSignal(RULE_EITC_CROSS_CLAIM, "EITC same-child dual-filer cross-claim", self.RULE_WEIGHTS[RULE_EITC_CROSS_CLAIM])
        xs = ctx.get("extra_signals", {})
        if xs.get("filer_a") and xs.get("filer_b") and not xs.get("ssa_dependency_match", True):
            sig.triggered = True
            sig.evidence = {"filer_a": xs["filer_a"], "filer_b": xs["filer_b"], "ssa_dependency_match": False}
        return sig

    def _check_disaster_aid_dup(self, ctx: dict) -> FraudSignal:
        """FDE-025: Combined disaster aid exceeds documented loss by >10%."""
        sig = FraudSignal(RULE_DISASTER_AID_DUP, "Stafford disaster-aid duplication — total aid > documented loss", self.RULE_WEIGHTS[RULE_DISASTER_AID_DUP])
        xs = ctx.get("extra_signals", {})
        fema = xs.get("fema_ihp_usd", 0.0)
        sba = xs.get("sba_loan_usd", 0.0)
        nfip = xs.get("nfip_payout_usd", 0.0)
        loss = xs.get("documented_loss_estimate_usd", 0.0)
        if loss > 0 and (fema + sba + nfip) > loss * 1.1:
            sig.triggered = True
            sig.evidence = {"total_aid": fema + sba + nfip, "documented_loss": loss, "ratio": round((fema + sba + nfip) / loss, 3)}
        return sig

    def _check_dme_geo_outlier(self, ctx: dict) -> FraudSignal:
        """FDE-026: DME supplier serving an unusually wide geographic footprint via a single prescriber."""
        sig = FraudSignal(RULE_DME_GEO_OUTLIER, "DME geographic outlier — nationwide reach via single prescriber NPI", self.RULE_WEIGHTS[RULE_DME_GEO_OUTLIER])
        xs = ctx.get("extra_signals", {})
        states = xs.get("beneficiary_states_count", 0)
        npi_pct = xs.get("single_prescriber_npi_pct", 0.0)
        if states > 20 and npi_pct > 0.6:
            sig.triggered = True
            sig.evidence = {"beneficiary_states_count": states, "single_prescriber_npi_pct": npi_pct}
        return sig

    def _check_hospice_outlier(self, ctx: dict) -> FraudSignal:
        """FDE-027: Hospice provider with high live-discharge rate and extended LOS."""
        sig = FraudSignal(RULE_HOSPICE_OUTLIER, "Hospice LOS/live-discharge outlier — inflated terminal care billing", self.RULE_WEIGHTS[RULE_HOSPICE_OUTLIER])
        xs = ctx.get("extra_signals", {})
        ldr = xs.get("live_discharge_rate", 0.0)
        los = xs.get("median_los_days", 0.0)
        if ldr > 0.3 and los > 180:
            sig.triggered = True
            sig.evidence = {"live_discharge_rate": ldr, "median_los_days": los}
        return sig

    def _check_volume_spike_scheme(self, ctx: dict) -> FraudSignal:
        """FDE-028: Emerging-scheme volume spike (CGx) — rapid scale-up by prescribers new to the code."""
        sig = FraudSignal(RULE_VOLUME_SPIKE_SCHEME, "CGx volume spike scheme — novel-scheme rapid scale-up", self.RULE_WEIGHTS[RULE_VOLUME_SPIKE_SCHEME])
        xs = ctx.get("extra_signals", {})
        baseline = xs.get("baseline_daily_volume_usd", 0.0)
        wave = xs.get("first_wave_daily_volume_usd", 0.0)
        prior_pct = xs.get("prescriber_prior_cgx_orders_pct", 1.0)
        if baseline > 0 and (wave / baseline) > 10 and prior_pct < 0.01:
            sig.triggered = True
            sig.evidence = {"volume_spike_ratio": round(wave / baseline, 1), "prescriber_prior_cgx_orders_pct": prior_pct}
        return sig

    def _check_duplicate_inspection(self, ctx: dict) -> FraudSignal:
        """FDE-029: FSIS and FDA inspections of same facility with overlapping scope."""
        sig = FraudSignal(RULE_DUPLICATE_INSPECTION, "Duplicate FSIS/FDA inspection — overlapping regulatory scope", self.RULE_WEIGHTS[RULE_DUPLICATE_INSPECTION])
        xs = ctx.get("extra_signals", {})
        if xs.get("scope_overlap_jaccard", 0.0) > 0.4:
            sig.triggered = True
            sig.evidence = {"scope_overlap_jaccard": xs["scope_overlap_jaccard"]}
        return sig

    def _check_incident_dedup(self, ctx: dict) -> FraudSignal:
        """FDE-030: TSA and CISA filed near-identical incident reports for the same event."""
        sig = FraudSignal(RULE_INCIDENT_DEDUP, "Incident report deduplication — TSA/CISA IOC and narrative overlap", self.RULE_WEIGHTS[RULE_INCIDENT_DEDUP])
        xs = ctx.get("extra_signals", {})
        if xs.get("ioc_overlap_pct", 0.0) > 0.7 and xs.get("narrative_cosine", 0.0) > 0.6:
            sig.triggered = True
            sig.evidence = {"ioc_overlap_pct": xs["ioc_overlap_pct"], "narrative_cosine": xs["narrative_cosine"]}
        return sig

    def _check_data_call_overlap(self, ctx: dict) -> FraudSignal:
        """FDE-031: Multiple regulators issuing overlapping data calls to the same entity."""
        sig = FraudSignal(RULE_DATA_CALL_OVERLAP, "Regulatory data-call overlap — duplicative reporting burden", self.RULE_WEIGHTS[RULE_DATA_CALL_OVERLAP])
        xs = ctx.get("extra_signals", {})
        if xs.get("field_overlap_pct", 0.0) > 0.7 and xs.get("data_call_count", 0) >= 2:
            sig.triggered = True
            sig.evidence = {"field_overlap_pct": xs["field_overlap_pct"], "data_call_count": xs["data_call_count"]}
        return sig

    def _check_grant_attr_overlap(self, ctx: dict) -> FraudSignal:
        """FDE-032: STEM grants with overlapping intervention windows and missing outcome attribution."""
        sig = FraudSignal(RULE_GRANT_ATTR_OVERLAP, "STEM grant attribution overlap — concurrent programs without attribution method", self.RULE_WEIGHTS[RULE_GRANT_ATTR_OVERLAP])
        xs = ctx.get("extra_signals", {})
        overlap = xs.get("intervention_overlap_months", 0)
        missing = xs.get("outcome_attribution_missing", False)
        count = xs.get("grant_program_count", 0)
        if overlap > 6 and missing and count >= 2:
            sig.triggered = True
            sig.evidence = {"intervention_overlap_months": overlap, "grant_program_count": count}
        return sig

    def _check_duplicate_intake(self, ctx: dict) -> FraudSignal:
        """FDE-033: Same individual entered into both HMIS and VA Homes within 30 days."""
        sig = FraudSignal(RULE_DUPLICATE_INTAKE, "Duplicate homeless intake — HMIS/VA dual registration", self.RULE_WEIGHTS[RULE_DUPLICATE_INTAKE])
        xs = ctx.get("extra_signals", {})
        dual = xs.get("hmis_vispdat") is not None and xs.get("vahomes_vispdat") is not None
        days = xs.get("days_between_intakes", 999)
        if dual and days < 30:
            sig.triggered = True
            sig.evidence = {"days_between_intakes": days, "hmis_vispdat": xs["hmis_vispdat"], "vahomes_vispdat": xs["vahomes_vispdat"]}
        return sig

    def _check_stale_recommendation(self, ctx: dict) -> FraudSignal:
        """FDE-034: GAO priority recommendation with no activity and vacant owner for >12 months."""
        sig = FraudSignal(RULE_STALE_RECOMMENDATION, "Stale GAO priority recommendation — no milestones, vacant ownership", self.RULE_WEIGHTS[RULE_STALE_RECOMMENDATION])
        xs = ctx.get("extra_signals", {})
        if xs.get("milestones_logged_last_12m", 1) == 0 and xs.get("owner_status_vacant", False):
            sig.triggered = True
            sig.evidence = {"milestones_logged_last_12m": 0, "owner_status_vacant": True}
        return sig

    def _check_recon_drift(self, ctx: dict) -> FraudSignal:
        """FDE-035: IRS legacy system reconciliation divergence exceeds SLA threshold by 2×."""
        sig = FraudSignal(RULE_RECON_DRIFT, "IRS legacy reconciliation drift — divergence exceeds 2× SLA", self.RULE_WEIGHTS[RULE_RECON_DRIFT])
        xs = ctx.get("extra_signals", {})
        drift = xs.get("reconciliation_drift_pct", 0.0)
        sla = xs.get("reconciliation_sla_pct", 1.0)
        if sla > 0 and drift > sla * 2:
            sig.triggered = True
            sig.evidence = {"reconciliation_drift_pct": drift, "reconciliation_sla_pct": sla, "ratio": round(drift / sla, 2)}
        return sig

    def _check_wait_time_divergence(self, ctx: dict) -> FraudSignal:
        """FDE-036: VA telemetry wait time exceeds reported wait time by >2× with high sigma."""
        sig = FraudSignal(RULE_WAIT_TIME_DIVERGENCE, "VA wait-time reporting divergence — telemetry vs reported gap", self.RULE_WEIGHTS[RULE_WAIT_TIME_DIVERGENCE])
        xs = ctx.get("extra_signals", {})
        reported = xs.get("reported_wait_days", 0.0)
        telemetry = xs.get("telemetry_wait_days", 0.0)
        sigma = xs.get("wait_sigma", 0.0)
        if reported > 0 and (telemetry / reported) > 2 and sigma > 3.0:
            sig.triggered = True
            sig.evidence = {"telemetry_wait_days": telemetry, "reported_wait_days": reported, "wait_sigma": sigma}
        return sig

    def _check_exception_rate_spike(self, ctx: dict) -> FraudSignal:
        """FDE-037: FAFSA exception rate regressed by >3× vs baseline after a software release."""
        sig = FraudSignal(RULE_EXCEPTION_RATE_SPIKE, "FAFSA exception-rate spike — regression vs baseline", self.RULE_WEIGHTS[RULE_EXCEPTION_RATE_SPIKE])
        xs = ctx.get("extra_signals", {})
        baseline = xs.get("baseline_exception_rate", 0.0)
        current = xs.get("current_exception_rate", 0.0)
        if baseline > 0 and (current / baseline) > 3:
            sig.triggered = True
            sig.evidence = {"current_exception_rate": current, "baseline_exception_rate": baseline, "ratio": round(current / baseline, 1)}
        return sig

    def _check_cyber_backlog(self, ctx: dict) -> FraudSignal:
        """FDE-038: FISMA high-impact findings backlog with no remediation evidence and long age."""
        sig = FraudSignal(RULE_CYBER_BACKLOG, "FISMA high-impact cyber backlog — stale unmitigated findings", self.RULE_WEIGHTS[RULE_CYBER_BACKLOG])
        xs = ctx.get("extra_signals", {})
        if xs.get("high_impact_no_evidence", 0) > 50 and xs.get("median_open_days", 0) > 365:
            sig.triggered = True
            sig.evidence = {"high_impact_no_evidence": xs["high_impact_no_evidence"], "median_open_days": xs["median_open_days"]}
        return sig

    def _check_foreign_passthrough(self, ctx: dict) -> FraudSignal:
        """FDE-039: Passthrough partnership structure routes US income to foreign terminal entities."""
        sig = FraudSignal(RULE_FOREIGN_PASSTHROUGH, "Passthrough foreign-flow — US income routed to offshore terminal entities", self.RULE_WEIGHTS[RULE_FOREIGN_PASSTHROUGH])
        xs = ctx.get("extra_signals", {})
        foreign = xs.get("terminal_foreign_entities", 0)
        us_reported = xs.get("us_source_reported_usd", 1.0)
        if foreign >= 2 and us_reported == 0:
            sig.triggered = True
            sig.evidence = {"terminal_foreign_entities": foreign, "us_source_reported_usd": us_reported}
        return sig

    def _check_title_iv_risk(self, ctx: dict) -> FraudSignal:
        """FDE-040: Title IV institution with elevated cohort default rate and 90/10 revenue ratio."""
        sig = FraudSignal(RULE_TITLE_IV_RISK, "Title IV institution risk — elevated CDR and 90/10 ratio", self.RULE_WEIGHTS[RULE_TITLE_IV_RISK])
        xs = ctx.get("extra_signals", {})
        if xs.get("cdr", 0.0) > 0.15 and xs.get("ratio_90_10", 0.0) > 0.85:
            sig.triggered = True
            sig.evidence = {"cdr": xs["cdr"], "ratio_90_10": xs["ratio_90_10"]}
        return sig

    def _check_import_transshipment(self, ctx: dict) -> FraudSignal:
        """FDE-041: UFLPA transshipment signal — China imports drop while Vietnam surges with satellite match."""
        sig = FraudSignal(RULE_IMPORT_TRANSSHIPMENT, "UFLPA import transshipment — China-to-Vietnam rerouting with satellite evidence", self.RULE_WEIGHTS[RULE_IMPORT_TRANSSHIPMENT])
        xs = ctx.get("extra_signals", {})
        china = xs.get("china_import_change_pct", 0.0)
        vietnam = xs.get("vietnam_import_change_pct", 0.0)
        sat = xs.get("satellite_supplier_match", 0.0)
        if china < -0.7 and vietnam > 2.0 and sat > 0.6:
            sig.triggered = True
            sig.evidence = {"china_import_change_pct": china, "vietnam_import_change_pct": vietnam, "satellite_supplier_match": sat}
        return sig

    def _check_property_underutil(self, ctx: dict) -> FraudSignal:
        """FDE-042: Federal real property with mean occupancy below 30%."""
        sig = FraudSignal(RULE_PROPERTY_UNDERUTIL, "Federal real-property underutilization — occupancy below 30%", self.RULE_WEIGHTS[RULE_PROPERTY_UNDERUTIL])
        xs = ctx.get("extra_signals", {})
        if xs.get("mean_occupancy_pct", 1.0) < 0.30:
            sig.triggered = True
            sig.evidence = {"mean_occupancy_pct": xs["mean_occupancy_pct"]}
        return sig

    def _check_sam_true_down(self, ctx: dict) -> FraudSignal:
        """FDE-043: SAM.gov seat count significantly inflated by inactive accounts (true-down opportunity)."""
        sig = FraudSignal(RULE_SAM_TRUE_DOWN, "SAM.gov seat true-down — >30% inactive accounts identified", self.RULE_WEIGHTS[RULE_SAM_TRUE_DOWN])
        xs = ctx.get("extra_signals", {})
        if xs.get("inactive_pct_30d", 0.0) > 0.30:
            sig.triggered = True
            sig.evidence = {"inactive_pct_30d": xs["inactive_pct_30d"]}
        return sig

    def _check_clearance_fin_risk(self, ctx: dict) -> FraudSignal:
        """FDE-044: Security clearance holder with foreign travel and new financial delinquencies."""
        sig = FraudSignal(RULE_CLEARANCE_FIN_RISK, "Security-clearance financial risk — foreign travel + new delinquencies", self.RULE_WEIGHTS[RULE_CLEARANCE_FIN_RISK])
        xs = ctx.get("extra_signals", {})
        high_clearance = xs.get("clearance_level", "") in ("TS/SCI", "TS", "Secret")
        if xs.get("foreign_travel_flag") and xs.get("new_delinquencies", 0) >= 3 and high_clearance:
            sig.triggered = True
            sig.evidence = {"foreign_travel_flag": True, "new_delinquencies": xs["new_delinquencies"], "clearance_level": xs.get("clearance_level")}
        return sig

    def _check_whistleblower_cluster(self, ctx: dict) -> FraudSignal:
        """FDE-045: Clustered whistleblower tips targeting same entity with high cosine similarity."""
        sig = FraudSignal(RULE_WHISTLEBLOWER_CLUSTER, "Whistleblower tip cluster — high-similarity tips targeting same entity", self.RULE_WEIGHTS[RULE_WHISTLEBLOWER_CLUSTER])
        xs = ctx.get("extra_signals", {})
        if xs.get("cluster_cosine", 0.0) > 0.6 and xs.get("top_tip_score", 0.0) > 0.7:
            sig.triggered = True
            sig.evidence = {"cluster_cosine": xs["cluster_cosine"], "top_tip_score": xs["top_tip_score"]}
        return sig

    def _check_contractor_perf_risk(self, ctx: dict) -> FraudSignal:
        """FDE-046: Cross-agency CPARS record shows unsatisfactory ratings with declining sentiment trend."""
        sig = FraudSignal(RULE_CONTRACTOR_PERF_RISK, "Cross-agency CPARS performance risk — unsatisfactory ratings with declining trend", self.RULE_WEIGHTS[RULE_CONTRACTOR_PERF_RISK])
        xs = ctx.get("extra_signals", {})
        if xs.get("cpars_unsat_count", 0) >= 1 and xs.get("cpars_sentiment_slope", 0.0) < -0.1:
            sig.triggered = True
            sig.evidence = {"cpars_unsat_count": xs["cpars_unsat_count"], "cpars_sentiment_slope": xs["cpars_sentiment_slope"]}
        return sig

    def _check_multi_program_ring(self, ctx: dict) -> FraudSignal:
        """FDE-047: Multi-program fraud ring sharing device fingerprints and ABA routing numbers."""
        sig = FraudSignal(RULE_MULTI_PROGRAM_RING, "Multi-program fraud ring — shared devices and ABA routing numbers", self.RULE_WEIGHTS[RULE_MULTI_PROGRAM_RING])
        xs = ctx.get("extra_signals", {})
        if xs.get("shared_device_fingerprints", 0) >= 3 and xs.get("shared_aba_count", 0) >= 3:
            sig.triggered = True
            sig.evidence = {"shared_device_fingerprints": xs["shared_device_fingerprints"], "shared_aba_count": xs["shared_aba_count"]}
        return sig

    # ── Scoring helpers ──────────────────────────────────────────────────

    def _tier(self, score: float, triggered: list[FraudSignal]) -> str:
        # Hard overrides: always CRITICAL regardless of composite score
        hard_block = {RULE_VENDOR_SAM_EXCLUDED, RULE_SANCTIONS_LAYERING}
        if any(s.rule_id in hard_block for s in triggered):
            return "CRITICAL"
        if score >= 70: return "CRITICAL"
        if score >= 50: return "HIGH"
        if score >= 25: return "MEDIUM"
        return "LOW"

    def _action(self, tier: str, triggered: list[FraudSignal]) -> str:
        if tier == "CRITICAL": return "BLOCK"
        if tier == "HIGH":     return "HOLD"
        if tier == "MEDIUM":   return "REVIEW"
        return "APPROVE"

    def _gao_refs(self, triggered: list[FraudSignal]) -> list[str]:
        mapping = {
            RULE_DUPLICATE_EXACT:      "GAO Cat1-Ex10 (Duplicate Vendor Payments in DoD)",
            RULE_DUPLICATE_FUZZY:      "GAO Cat1-Ex10 (Duplicate Vendor Payments in DoD)",
            RULE_ROUND_DOLLAR:         "GAO Cat1-Ex8 (SNAP Retailer Trafficking — round pattern)",
            RULE_SPLIT_PURCHASE:       "GAO Cat1-Ex23 (Federal P-Card split-purchase)",
            RULE_VENDOR_SAM_EXCLUDED:  "GAO Cat5-Ex4 (Manual SAM.gov Exclusion Checks)",
            RULE_EXCEEDS_BUDGET_CAT:   "2 CFR 200.405 (Allowable Costs)",
            RULE_WEEKEND_TRANSACTION:  "GAO Cat1-Ex9 (Travel Card Abuse)",
            RULE_HIGH_VELOCITY:        "GAO Cat1-Ex3 (Pandemic UI Fraud — velocity)",
            RULE_AMOUNT_THRESHOLD:     "GAO Cat1-Ex24 (T&M Contract Overbilling)",
            RULE_GHOST_VENDOR:         "GAO Cat1-Ex11 (Ghost Employees analog)",
            RULE_RELATED_PARTY:        "GAO Cat5-Ex13 (PEP/Sanctions Screening)",
            RULE_CROSS_GRANT_DOUBLE:   "GAO Cat1-Ex27 (Federal Grant Double-Dipping)",
            RULE_LABOR_RATE_MISMATCH:  "GAO Cat2 (T&M Labor Category Misclassification)",
            RULE_ACQUISITION_OVERRUN:  "GAO Cat6-Ex36 (MDAP Cost Growth / EVM Deviation)",
            RULE_PROCUREMENT_ROTATION: "GAO Cat1-Ex26 (Procurement Collusion — vendor rotation)",
            RULE_DEVICE_FINGERPRINT:   "GAO Cat4 (Device Fingerprint Ring — PPP/Pell/cross-program)",
            RULE_SYNTHETIC_ID_ECBSV:   "GAO Cat4 (Synthetic ID — SSA E-CBSv Mismatch)",
            RULE_OIG_ENTITY_LINK:      "GAO Cat5 (OIG Cross-Entity Link — HHS/SSA)",
            RULE_AUTH_WINDOW_VIOLATION: "GAO Cat3 (Healthcare Prior-Auth Window Violation)",
            RULE_CRYPTO_UNDERREPORT:   "GAO Cat5 (Crypto Gain Underreporting — on-chain vs reported)",
            RULE_SPOOFING_CANCEL_RATE: "GAO Cat1 (Order Spoofing / Layering via Cancel Pattern)",
            RULE_SANCTIONS_LAYERING:   "GAO Cat5 (OFAC Sanctions Layering — SDN entity match)",
            RULE_RA_UPCODING:          "GAO Cat3 (Risk-Adjustment Upcoding — insufficient encounters)",
            RULE_EITC_CROSS_CLAIM:     "GAO Cat2 (EITC Same-Child Dual-Filer Cross-Claim)",
            RULE_DISASTER_AID_DUP:     "GAO Cat3 (Stafford Disaster-Aid Duplication — FEMA/SBA/NFIP overlap)",
            RULE_DME_GEO_OUTLIER:      "GAO Cat2 (DME Geographic Outlier — nationwide single-prescriber reach)",
            RULE_HOSPICE_OUTLIER:      "GAO Cat2 (Hospice LOS/Live-Discharge Outlier)",
            RULE_VOLUME_SPIKE_SCHEME:  "GAO Cat2 (Emerging Scheme — CGx Volume Spike)",
            RULE_DUPLICATE_INSPECTION: "GAO Cat5 (Duplicate FSIS/FDA Inspection — scope overlap)",
            RULE_INCIDENT_DEDUP:       "GAO Cat5 (TSA/CISA Incident Report Deduplication)",
            RULE_DATA_CALL_OVERLAP:    "GAO Cat5 (Overlapping Regulatory Data Calls)",
            RULE_GRANT_ATTR_OVERLAP:   "GAO Cat3 (STEM Grant Attribution Overlap — concurrent programs)",
            RULE_DUPLICATE_INTAKE:     "GAO Cat4 (HMIS/VA Duplicate Homeless Intake)",
            RULE_STALE_RECOMMENDATION: "GAO Cat6 (Stale GAO Priority Recommendation — vacant ownership)",
            RULE_RECON_DRIFT:          "GAO Cat1 (IRS Legacy Reconciliation Drift — SLA breach)",
            RULE_WAIT_TIME_DIVERGENCE: "GAO Cat6 (VA Wait-Time Reporting Divergence — telemetry vs reported)",
            RULE_EXCEPTION_RATE_SPIKE: "GAO Cat3 (FAFSA Exception-Rate Regression — post-release spike)",
            RULE_CYBER_BACKLOG:        "GAO Cat6 (FISMA High-Impact Cyber Backlog — stale findings)",
            RULE_FOREIGN_PASSTHROUGH:  "GAO Cat5 (Passthrough Foreign-Flow — offshore terminal entities)",
            RULE_TITLE_IV_RISK:        "GAO Cat3 (Title IV Institution Risk — CDR and 90/10 ratio)",
            RULE_IMPORT_TRANSSHIPMENT: "GAO Cat5 (UFLPA Import Transshipment — China-Vietnam rerouting)",
            RULE_PROPERTY_UNDERUTIL:   "GAO Cat6 (Federal Real-Property Underutilization)",
            RULE_SAM_TRUE_DOWN:        "GAO Cat6 (SAM.gov Seat True-Down — inactive account consolidation)",
            RULE_CLEARANCE_FIN_RISK:   "GAO Cat4 (Security-Clearance Financial Risk — foreign travel + delinquencies)",
            RULE_WHISTLEBLOWER_CLUSTER: "GAO Cat5 (Whistleblower Tip Cluster — corroborated entity targeting)",
            RULE_CONTRACTOR_PERF_RISK: "GAO Cat6 (Cross-Agency CPARS Performance Risk — declining ratings)",
            RULE_MULTI_PROGRAM_RING:   "GAO Cat4 (Multi-Program Fraud Ring — shared devices and routing numbers)",
        }
        refs = []
        seen = set()
        for s in triggered:
            ref = mapping.get(s.rule_id)
            if ref and ref not in seen:
                refs.append(ref)
                seen.add(ref)
        return refs

    def _explain(self, triggered: list[FraudSignal], score: float) -> str:
        if not triggered:
            return f"No fraud indicators detected. Composite score: {score:.1f}/100."
        top = triggered[:3]
        factors = "; ".join(f"{s.description}" for s in top)
        return (f"Score {score:.1f}/100. "
                f"Top signals: {factors}. "
                f"{len(triggered)} of {len(self.RULE_WEIGHTS)} rules triggered. "
                "Full signal detail in signal_detail array.")

    @staticmethod
    def _levenshtein(a: str, b: str) -> int:
        """Compute edit distance between two strings."""
        if len(a) < len(b):
            a, b = b, a
        if not b:
            return len(a)
        prev = list(range(len(b) + 1))
        for i, ca in enumerate(a):
            curr = [i + 1]
            for j, cb in enumerate(b):
                curr.append(min(prev[j + 1] + 1, curr[j] + 1, prev[j] + (ca != cb)))
            prev = curr
        return prev[-1]
