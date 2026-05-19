"""
GovGuard v2 — Predictive Risk Analytics
=========================================
NEW FILE: services/predictive_risk/scorer.py

Forward-looking risk scoring using:
  - Historical compliance trajectory
  - Spend burn-rate trends
  - Vendor risk network scores
  - GAO High-Risk program overlaps

GAO Alignment:
  - Cat 3 Ex 29 (Continuous Risk Assessment Adoption)
  - Cat 3 Ex 1  (GAO Recommendation Backlog)
  - Cat 4 Ex 5  (DoD Weapons Requirements — risk prediction analog)
"""
from __future__ import annotations
import math
import structlog
from dataclasses import dataclass
from datetime import date
from typing import Optional

log = structlog.get_logger()


@dataclass
class RiskPrediction:
    grant_id: str
    predicted_risk_score: float      # 0–100 (30-day forward)
    current_risk_score: float        # Baseline
    trend: str                       # IMPROVING / STABLE / DETERIORATING
    risk_drivers: list[dict]
    recommended_actions: list[str]
    confidence: float                # 0.0–1.0
    gao_high_risk_overlap: list[str] # Matching GAO High-Risk programs
    prediction_horizon_days: int = 30
    prediction_method: str = "linear_weighted"


class PredictiveRiskScorer:
    """
    Computes 30-day forward risk score for a grant.
    Uses linear trend extrapolation on key indicators.
    In production: replace with LSTM or gradient boosting model.
    """

    # GAO High-Risk program keywords (GAO-24-106368 analogs)
    GAO_HIGH_RISK_INDICATORS = {
        "medicaid":        "Medicaid — $50B+/year improper payments",
        "medicare":        "Medicare FFS — $31B/year improper payments",
        "unemployment":    "Unemployment Insurance — systemic fraud vulnerability",
        "housing":         "HUD Housing Programs — oversight gaps",
        "disaster":        "FEMA Disaster Recovery — duplication risk",
        "student_aid":     "Federal Student Aid — identity fraud risk",
        "defense":         "DoD Financial Management — audit failures",
        "snap":            "SNAP — trafficking and retailer fraud",
        "procurement":     "Federal Acquisition — collusion and split purchase",
        "research":        "NIH/NSF Research Grants — misuse and foreign disclosure",
    }

    def predict(
        self,
        *,
        grant_id: str,
        agency: str,
        program_cfda: Optional[str],
        compliance_score_history: list[float],  # last 6 months, newest last
        spend_pct_history: list[float],          # monthly % of budget spent
        vendor_network_risk: float,              # from entity intelligence
        open_findings_count: int,
        open_cap_count: int,
        overdue_cap_count: int,
        days_to_period_end: int,
    ) -> RiskPrediction:
        """Compute predictive risk score with trend analysis."""

        # 1. GAO High-Risk overlap (needed for both ML and linear paths)
        gao_overlaps = []
        agency_lower = agency.lower()
        cfda_lower = (program_cfda or "").lower()
        for keyword, label in self.GAO_HIGH_RISK_INDICATORS.items():
            if keyword in agency_lower or keyword in cfda_lower:
                gao_overlaps.append(label)

        # 2. Linear components — always computed (current_score, recommendations, fallback)
        compliance_trend, compliance_delta = self._trend(compliance_score_history)
        projected_compliance = max(0, (compliance_score_history[-1] if compliance_score_history else 70) + compliance_delta)

        burnrate_trend, burnrate_delta = self._trend(spend_pct_history)
        projected_burnrate = min(1.0, (spend_pct_history[-1] if spend_pct_history else 0.3) + burnrate_delta)

        compliance_risk = max(0.0, 100.0 - projected_compliance)
        burnrate_risk   = min(100.0, projected_burnrate * 120)
        findings_risk   = min(100.0, open_findings_count * 15 + overdue_cap_count * 25)
        network_risk    = vendor_network_risk
        period_end_risk = max(0.0, (30 - days_to_period_end) * 2) if days_to_period_end <= 30 else 0.0

        linear_predicted = (
            compliance_risk  * 0.30 +
            findings_risk    * 0.25 +
            network_risk     * 0.20 +
            burnrate_risk    * 0.15 +
            period_end_risk  * 0.10
        )
        current = compliance_risk * 0.40 + findings_risk * 0.35 + network_risk * 0.25

        # 3. Trend from data slopes — not from score comparison
        # compliance "IMPROVING" = score going up = risk reducing
        # burnrate "IMPROVING"   = spend going up = risk increasing
        risk_worsening = compliance_trend == "DETERIORATING" or burnrate_trend == "IMPROVING"
        risk_improving = compliance_trend == "IMPROVING" and burnrate_trend != "IMPROVING"
        if risk_worsening:
            trend = "DETERIORATING"
        elif risk_improving:
            trend = "IMPROVING"
        else:
            trend = "STABLE"

        # 4. Try XGBoost model — replaces predicted score and drivers
        prediction_method = "linear_weighted"
        predicted = linear_predicted
        drivers: list[dict] = []
        try:
            from ml.risk_forecaster import RiskForecaster, extract_features as _rf_extract
            forecaster = RiskForecaster()
            if forecaster.available():
                burnrate = spend_pct_history[-1] if spend_pct_history else 0.2
                features = _rf_extract(
                    compliance_score_history=compliance_score_history,
                    spend_pct_history=spend_pct_history,
                    open_findings_count=open_findings_count,
                    open_cap_count=open_cap_count,
                    overdue_cap_count=overdue_cap_count,
                    days_to_period_end=days_to_period_end,
                    vendor_network_risk=vendor_network_risk,
                    gao_overlap_count=len(gao_overlaps),
                    burnrate_pct=burnrate,
                )
                predicted, drivers = forecaster.predict_with_drivers(features)
                prediction_method = "ml_xgboost"
        except Exception as exc:
            log.warning("risk_scorer.ml_fallback", error=str(exc))

        # Linear drivers as fallback when ML unavailable
        if not drivers:
            if compliance_risk > 40: drivers.append({"factor": "low_compliance_score", "contribution": round(compliance_risk * 0.30, 1), "direction": "increasing_risk"})
            if findings_risk > 30:   drivers.append({"factor": "open_findings",        "contribution": round(findings_risk * 0.25, 1),  "direction": "increasing_risk"})
            if network_risk > 30:    drivers.append({"factor": "vendor_network_risk",   "contribution": round(network_risk * 0.20, 1),   "direction": "increasing_risk"})
            if burnrate_risk > 40:   drivers.append({"factor": "abnormal_burnrate",     "contribution": round(burnrate_risk * 0.15, 1),  "direction": "increasing_risk"})
            if period_end_risk > 20: drivers.append({"factor": "period_end_pressure",   "contribution": round(period_end_risk * 0.10, 1),"direction": "increasing_risk"})
            drivers.sort(key=lambda x: x.get("contribution", 0), reverse=True)

        # 5. Recommendations
        actions = []
        if compliance_trend == "DETERIORATING": actions.append("Accelerate compliance control testing — run POST /compliance/run immediately")
        if overdue_cap_count > 0: actions.append(f"Close {overdue_cap_count} overdue CAP(s) before period end")
        if network_risk > 60: actions.append("Review vendor entity graph for conflict-of-interest links")
        if burnrate_risk > 70: actions.append("Review spending velocity — burnrate exceeds safe threshold")
        if days_to_period_end <= 30: actions.append("Begin closeout checklist — period end within 30 days")

        confidence = min(1.0, len(compliance_score_history) / 6.0) * 0.7 + 0.3

        return RiskPrediction(
            grant_id=grant_id,
            predicted_risk_score=round(min(100.0, predicted), 2),
            current_risk_score=round(min(100.0, current), 2),
            trend=trend,
            risk_drivers=drivers,
            recommended_actions=actions,
            confidence=round(confidence, 2),
            gao_high_risk_overlap=gao_overlaps,
            prediction_method=prediction_method,
        )

    def _trend(self, series: list[float]) -> tuple[str, float]:
        """Simple linear regression delta per period."""
        if len(series) < 2:
            return "STABLE", 0.0
        n = len(series)
        if n == 2:
            delta = series[-1] - series[-2]
        else:
            # Least squares slope
            xs = list(range(n))
            mean_x = sum(xs) / n
            mean_y = sum(series) / n
            numer = sum((xs[i] - mean_x) * (series[i] - mean_y) for i in range(n))
            denom = sum((xs[i] - mean_x) ** 2 for i in range(n))
            delta = (numer / denom) if denom else 0.0

        trend = "STABLE"
        if delta > 2: trend = "IMPROVING"
        if delta < -2: trend = "DETERIORATING"
        return trend, round(delta, 3)
