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

    # Scoring weights per rule (sum = 10.0 if all triggered → maps to 100)
    RULE_WEIGHTS = {
        RULE_DUPLICATE_EXACT:     2.5,
        RULE_DUPLICATE_FUZZY:     1.8,
        RULE_ROUND_DOLLAR:        0.6,
        RULE_SPLIT_PURCHASE:      1.2,
        RULE_VENDOR_SAM_EXCLUDED: 3.0,   # Hard block signal
        RULE_EXCEEDS_BUDGET_CAT:  1.5,
        RULE_WEEKEND_TRANSACTION: 0.4,
        RULE_HIGH_VELOCITY:       1.8,
        RULE_AMOUNT_THRESHOLD:    1.0,
        RULE_GHOST_VENDOR:        2.0,
        RULE_RELATED_PARTY:       1.6,
        RULE_CROSS_GRANT_DOUBLE:  2.0,
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

    # ── Scoring helpers ──────────────────────────────────────────────────

    def _tier(self, score: float, triggered: list[FraudSignal]) -> str:
        # Hard override: SAM excluded always = CRITICAL
        if any(s.rule_id == RULE_VENDOR_SAM_EXCLUDED for s in triggered):
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
            RULE_DUPLICATE_EXACT:     "GAO Cat1-Ex10 (Duplicate Vendor Payments in DoD)",
            RULE_DUPLICATE_FUZZY:     "GAO Cat1-Ex10 (Duplicate Vendor Payments in DoD)",
            RULE_ROUND_DOLLAR:        "GAO Cat1-Ex8 (SNAP Retailer Trafficking — round pattern)",
            RULE_SPLIT_PURCHASE:      "GAO Cat1-Ex23 (Federal P-Card split-purchase)",
            RULE_VENDOR_SAM_EXCLUDED: "GAO Cat5-Ex4 (Manual SAM.gov Exclusion Checks)",
            RULE_EXCEEDS_BUDGET_CAT:  "2 CFR 200.405 (Allowable Costs)",
            RULE_WEEKEND_TRANSACTION: "GAO Cat1-Ex9 (Travel Card Abuse)",
            RULE_HIGH_VELOCITY:       "GAO Cat1-Ex3 (Pandemic UI Fraud — velocity)",
            RULE_AMOUNT_THRESHOLD:    "GAO Cat1-Ex24 (T&M Contract Overbilling)",
            RULE_GHOST_VENDOR:        "GAO Cat1-Ex11 (Ghost Employees analog)",
            RULE_RELATED_PARTY:       "GAO Cat5-Ex13 (PEP/Sanctions Screening)",
            RULE_CROSS_GRANT_DOUBLE:  "GAO Cat1-Ex27 (Federal Grant Double-Dipping)",
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
