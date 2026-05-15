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

    def to_dict(self) -> dict:
        return {
            "transaction_id": self.transaction_id,
            "composite_score": self.composite_score,
            "risk_tier": self.risk_tier,
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
        raw_score = sum(s.weight * 10 for s in triggered)
        composite = min(100.0, round(raw_score, 2))

        tier = self._tier(composite, triggered)
        action = self._action(tier, triggered)
        gao_refs = self._gao_refs(triggered)
        explanation = self._explain(triggered, composite)

        return FraudAssessment(
            transaction_id=transaction_id,
            composite_score=composite,
            risk_tier=tier,
            signals=signals,
            triggered_rules=[s.rule_id for s in triggered],
            recommended_action=action,
            gao_references=gao_refs,
            explanation=explanation,
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
