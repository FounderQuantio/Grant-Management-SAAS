"""
GovGuard v2 — Real-Time Anomaly Detection
==========================================
NEW FILE: services/anomaly_detection/processor.py

Statistical anomaly detection for transaction streams.
Runs as Celery task OR can be called synchronously from API.

GAO Alignment:
  - Cat 1 Ex 3  (UI fraud velocity detection)
  - Cat 3 Ex 23 (Continuous monitoring of high-risk grants)
  - Cat 3 Ex 29 (Continuous risk assessment adoption)
  - Cat 4 Ex 7  (IRS pass-through entity gap — spending anomalies)
"""
from __future__ import annotations

import math
import statistics
import structlog
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Optional

log = structlog.get_logger()

_anomaly_detector = None


def _get_detector():
    global _anomaly_detector
    if _anomaly_detector is None:
        try:
            from ml.anomaly_detector import AnomalyDetector
            _anomaly_detector = AnomalyDetector()
        except Exception as exc:
            log.warning("anomaly_detector.import_failed", error=str(exc))
            _anomaly_detector = False
    return _anomaly_detector if _anomaly_detector is not False else None


@dataclass
class AnomalyAlert:
    alert_id: str
    grant_id: str
    tenant_id: str
    anomaly_type: str
    severity: str               # INFO / WARNING / CRITICAL
    score: float                # z-score or pct deviation
    threshold: float
    observed_value: float
    expected_range: tuple[float, float]
    description: str
    gao_reference: str
    triggered_at: str
    auto_action: str            # NOTIFY / FLAG_REVIEW / HOLD_PAYMENTS
    detection_method: str = "rules_statistical"  # or "ml_isolation_forest"


# ── Anomaly Type Registry ─────────────────────────────────────────────────

ANOMALY_SPEND_VELOCITY       = "SPEND_VELOCITY"       # Cat 1 Ex 3
ANOMALY_CATEGORY_DRIFT       = "CATEGORY_DRIFT"        # Cat 3 Ex 23
ANOMALY_VENDOR_DOMINANCE     = "VENDOR_DOMINANCE"      # Cat 1 Ex 26 (collusion)
ANOMALY_BURNRATE_SPIKE       = "BURNRATE_SPIKE"        # Cat 3 Ex 15 (FEMA grant burnrate)
ANOMALY_DORMANT_REACTIVATION = "DORMANT_REACTIVATION"  # Cat 1 Ex 11
ANOMALY_END_OF_PERIOD        = "END_OF_PERIOD"         # Cat 1 Ex 10 (DoD dup — fiscal year end)
ANOMALY_ML_OUTLIER           = "ML_OUTLIER"            # Phase 3: IsolationForest 20-feature model


class AnomalyDetectionProcessor:
    """
    Computes statistical anomalies for a grant's transaction stream.

    Input: current transaction + historical context (last 90 days)
    Output: list of AnomalyAlert (empty = clean)
    """

    # Z-score threshold for statistical outlier
    Z_SCORE_CRITICAL = 3.0
    Z_SCORE_WARNING  = 2.0

    # Category shift threshold (% of total spend)
    CATEGORY_DRIFT_PCT = 0.30

    # Vendor concentration (one vendor > X% of grant spend)
    VENDOR_DOMINANCE_PCT = 0.60

    # Burnrate: >X% of budget consumed in a single period
    BURNRATE_SPIKE_PCT = 0.40

    def detect(
        self,
        *,
        grant_id: str,
        tenant_id: str,
        current_tx: dict,
        historical_txns: list[dict],   # last 90d txns for this grant
        grant_budget: dict,            # {category: amount}
        grant_total_amount: float,
    ) -> tuple[list[AnomalyAlert], dict]:
        """Run all anomaly detectors. Returns (alerts, meta) where meta contains diagnostic info."""
        alerts = []
        ts_now = datetime.utcnow().isoformat()

        alerts += self._detect_spend_velocity(grant_id, tenant_id, current_tx, historical_txns, ts_now)
        alerts += self._detect_category_drift(grant_id, tenant_id, current_tx, historical_txns, grant_budget, ts_now)
        alerts += self._detect_vendor_dominance(grant_id, tenant_id, current_tx, historical_txns, grant_total_amount, ts_now)
        alerts += self._detect_burnrate_spike(grant_id, tenant_id, current_tx, historical_txns, grant_total_amount, ts_now)
        alerts += self._detect_dormant_reactivation(grant_id, tenant_id, current_tx, historical_txns, ts_now)
        alerts += self._detect_end_of_period(grant_id, tenant_id, current_tx, historical_txns, ts_now)

        ml_score, ml_available, ml_flagged = self._compute_ml_score(
            current_tx, historical_txns, grant_total_amount, grant_budget
        )
        if ml_flagged:
            alerts += self._detect_ml_outlier(grant_id, tenant_id, current_tx, historical_txns,
                                              grant_total_amount, grant_budget, ts_now,
                                              precomputed_score=ml_score or 0.0)

        meta = {
            "ml_detector_available": ml_available,
            "ml_score": ml_score,
            "ml_flagged": ml_flagged,
        }
        return alerts, meta

    def _detect_spend_velocity(self, grant_id, tenant_id, tx, history, ts) -> list:
        """Detect abnormal spend velocity vs. historical weekly average."""
        import uuid
        weekly_totals = self._aggregate_weekly(history)
        if len(weekly_totals) < 3:
            return []

        mean = statistics.mean(weekly_totals)
        stdev = statistics.stdev(weekly_totals) if len(weekly_totals) > 1 else mean * 0.2
        current_week_total = sum(
            float(t.get("amount", 0)) for t in history
            if self._days_ago(t.get("tx_date")) <= 7
        ) + float(tx.get("amount", 0))

        z = (current_week_total - mean) / (stdev + 0.001)

        if z >= self.Z_SCORE_CRITICAL:
            return [AnomalyAlert(
                alert_id=str(uuid.uuid4()),
                grant_id=grant_id, tenant_id=tenant_id,
                anomaly_type=ANOMALY_SPEND_VELOCITY,
                severity="CRITICAL", score=round(z, 2), threshold=self.Z_SCORE_CRITICAL,
                observed_value=current_week_total,
                expected_range=(mean - stdev, mean + stdev),
                description=f"Weekly spend ${current_week_total:,.2f} is {z:.1f} standard deviations above mean ${mean:,.2f}",
                gao_reference="GAO Cat1-Ex3 (Pandemic UI Fraud — velocity detection)",
                triggered_at=ts, auto_action="FLAG_REVIEW",
            )]
        if z >= self.Z_SCORE_WARNING:
            return [AnomalyAlert(
                alert_id=str(uuid.uuid4()),
                grant_id=grant_id, tenant_id=tenant_id,
                anomaly_type=ANOMALY_SPEND_VELOCITY,
                severity="WARNING", score=round(z, 2), threshold=self.Z_SCORE_WARNING,
                observed_value=current_week_total,
                expected_range=(mean - stdev, mean + stdev),
                description=f"Elevated weekly spend — {z:.1f} SD above mean",
                gao_reference="GAO Cat3-Ex23 (Continuous Monitoring of High-Risk Grants)",
                triggered_at=ts, auto_action="NOTIFY",
            )]
        return []

    def _detect_category_drift(self, grant_id, tenant_id, tx, history, budget, ts) -> list:
        """Detect cost-category concentration drift vs. approved budget plan."""
        import uuid
        cat = tx.get("cost_category", "")
        cat_approved = budget.get(cat, 0)
        total_approved = sum(budget.values()) or 1

        cat_historical = sum(float(t.get("amount", 0)) for t in history if t.get("cost_category") == cat)
        cat_total = cat_historical + float(tx.get("amount", 0))
        cat_pct = cat_total / (sum(float(t.get("amount", 0)) for t in history) + float(tx.get("amount", 0)) + 0.001)

        approved_pct = cat_approved / total_approved
        drift = abs(cat_pct - approved_pct)

        if drift > self.CATEGORY_DRIFT_PCT and cat_total > cat_approved:
            return [AnomalyAlert(
                alert_id=str(uuid.uuid4()),
                grant_id=grant_id, tenant_id=tenant_id,
                anomaly_type=ANOMALY_CATEGORY_DRIFT,
                severity="WARNING", score=round(drift * 100, 2), threshold=self.CATEGORY_DRIFT_PCT * 100,
                observed_value=cat_pct * 100, expected_range=(0, approved_pct * 100 + self.CATEGORY_DRIFT_PCT * 100),
                description=f"Category '{cat}' at {cat_pct*100:.1f}% of spend vs {approved_pct*100:.1f}% approved",
                gao_reference="GAO Cat1-Ex16 (Research Grant Misuse — unallowable costs); 2 CFR 200.405",
                triggered_at=ts, auto_action="NOTIFY",
            )]
        return []

    def _detect_vendor_dominance(self, grant_id, tenant_id, tx, history, total_budget, ts) -> list:
        """Single vendor capturing disproportionate share — collusion signal."""
        import uuid
        vid = tx.get("vendor_id")
        total_spend = sum(float(t.get("amount", 0)) for t in history) + float(tx.get("amount", 0))
        vendor_spend = sum(float(t.get("amount", 0)) for t in history if t.get("vendor_id") == vid) + float(tx.get("amount", 0))
        pct = vendor_spend / (total_spend + 0.001)
        if pct > self.VENDOR_DOMINANCE_PCT and total_spend > 50000:
            return [AnomalyAlert(
                alert_id=str(uuid.uuid4()),
                grant_id=grant_id, tenant_id=tenant_id,
                anomaly_type=ANOMALY_VENDOR_DOMINANCE,
                severity="WARNING", score=round(pct * 100, 2), threshold=self.VENDOR_DOMINANCE_PCT * 100,
                observed_value=vendor_spend, expected_range=(0, total_spend * self.VENDOR_DOMINANCE_PCT),
                description=f"Vendor {vid[:8]}... accounts for {pct*100:.1f}% of grant spend",
                gao_reference="GAO Cat1-Ex26 (Procurement Collusion — vendor concentration)",
                triggered_at=ts, auto_action="FLAG_REVIEW",
            )]
        return []

    def _detect_burnrate_spike(self, grant_id, tenant_id, tx, history, total_budget, ts) -> list:
        """Detect unusually fast budget consumption."""
        import uuid
        recent_30d = sum(float(t.get("amount", 0)) for t in history if self._days_ago(t.get("tx_date")) <= 30)
        recent_30d += float(tx.get("amount", 0))
        pct = recent_30d / (total_budget + 0.001)
        if pct > self.BURNRATE_SPIKE_PCT:
            return [AnomalyAlert(
                alert_id=str(uuid.uuid4()),
                grant_id=grant_id, tenant_id=tenant_id,
                anomaly_type=ANOMALY_BURNRATE_SPIKE,
                severity="CRITICAL" if pct > 0.70 else "WARNING",
                score=round(pct * 100, 2), threshold=self.BURNRATE_SPIKE_PCT * 100,
                observed_value=recent_30d, expected_range=(0, total_budget * self.BURNRATE_SPIKE_PCT),
                description=f"{pct*100:.1f}% of total budget consumed in last 30 days",
                gao_reference="GAO Cat4-Ex15 (HHS Grant Compliance Coverage); Cat3-Ex15 (FEMA Grants)",
                triggered_at=ts, auto_action="HOLD_PAYMENTS" if pct > 0.90 else "FLAG_REVIEW",
            )]
        return []

    def _detect_dormant_reactivation(self, grant_id, tenant_id, tx, history, ts) -> list:
        """Vendor not seen for 60+ days suddenly submits large invoice."""
        import uuid
        vid = tx.get("vendor_id")
        last_tx = None
        for t in sorted(history, key=lambda x: x.get("tx_date", ""), reverse=True):
            if t.get("vendor_id") == vid:
                last_tx = t
                break
        if last_tx is None:
            return []
        days_since = self._days_ago(last_tx.get("tx_date"))
        if days_since > 60 and float(tx.get("amount", 0)) > 25000:
            return [AnomalyAlert(
                alert_id=str(uuid.uuid4()),
                grant_id=grant_id, tenant_id=tenant_id,
                anomaly_type=ANOMALY_DORMANT_REACTIVATION,
                severity="WARNING", score=days_since, threshold=60,
                observed_value=float(tx.get("amount", 0)),
                expected_range=(0, 10000),
                description=f"Vendor dormant {days_since} days, now submitting ${float(tx.get('amount',0)):,.2f}",
                gao_reference="GAO Cat1-Ex11 (Ghost Employee analog — dormant reactivation)",
                triggered_at=ts, auto_action="FLAG_REVIEW",
            )]
        return []

    def _detect_end_of_period(self, grant_id, tenant_id, tx, history, ts) -> list:
        """Spike in transactions in last 5 days of month — fiscal abuse signal."""
        import uuid
        tx_date = tx.get("tx_date")
        if tx_date and hasattr(tx_date, "day"):
            import calendar
            last_day = calendar.monthrange(tx_date.year, tx_date.month)[1]
            if last_day - tx_date.day <= 5:
                end_period_total = sum(
                    float(t.get("amount", 0)) for t in history
                    if self._days_ago(t.get("tx_date")) <= 5
                ) + float(tx.get("amount", 0))
                if end_period_total > 75000:
                    return [AnomalyAlert(
                        alert_id=str(uuid.uuid4()),
                        grant_id=grant_id, tenant_id=tenant_id,
                        anomaly_type=ANOMALY_END_OF_PERIOD,
                        severity="WARNING", score=round(end_period_total),
                        threshold=75000, observed_value=end_period_total,
                        expected_range=(0, 75000),
                        description=f"${end_period_total:,.2f} transacted in last 5 days of month",
                        gao_reference="GAO Cat1-Ex10 (DoD duplicate payments — fiscal-year-end surge)",
                        triggered_at=ts, auto_action="NOTIFY",
                    )]
        return []

    def _get_detector_threshold(self) -> Optional[float]:
        return None  # model self-determines boundary via contamination parameter

    def _compute_ml_score(
        self,
        tx: dict,
        history: list[dict],
        grant_total_budget: float,
        grant_budget_by_category: dict,
    ) -> tuple[Optional[float], bool, bool]:
        """Returns (score, available, is_anomaly).
        Score is for display; is_anomaly is the model's own decision."""
        detector = _get_detector()
        if detector is None or not detector.available():
            return None, False, False
        try:
            score = detector.score(tx, history, grant_total_budget, grant_budget_by_category)
            flagged = detector.is_anomaly(tx, history, grant_total_budget, grant_budget_by_category)
            return score, True, flagged
        except Exception as exc:
            log.warning("anomaly_detector.score_failed", error=str(exc))
            return None, True, False

    def _detect_ml_outlier(
        self,
        grant_id: str,
        tenant_id: str,
        tx: dict,
        history: list[dict],
        grant_total_budget: float,
        grant_budget_by_category: dict,
        ts: str,
        precomputed_score: float = 0.0,
    ) -> list:
        """IsolationForest 20-feature outlier detector (Phase 3)."""
        import uuid
        detector = _get_detector()
        score = precomputed_score

        severity = "CRITICAL" if score >= detector.THRESHOLD_CRITICAL else "WARNING"
        auto_action = "HOLD_PAYMENTS" if score >= detector.THRESHOLD_CRITICAL else "FLAG_REVIEW"

        return [AnomalyAlert(
            alert_id=str(uuid.uuid4()),
            grant_id=grant_id,
            tenant_id=tenant_id,
            anomaly_type=ANOMALY_ML_OUTLIER,
            severity=severity,
            score=round(score, 4),
            threshold=detector.THRESHOLD_WARNING,
            observed_value=score,
            expected_range=(0.0, detector.THRESHOLD_WARNING),
            description=(
                f"IsolationForest anomaly score {score:.2f} — "
                f"transaction exhibits unusual pattern across 20 behavioral features"
            ),
            gao_reference="GAO Cat3-Ex29 (Continuous risk assessment); Cat3-Ex23 (High-risk grant monitoring)",
            triggered_at=ts,
            auto_action=auto_action,
            detection_method="ml_isolation_forest",
        )]

    def _aggregate_weekly(self, history: list[dict]) -> list[float]:
        weeks: dict[int, float] = {}
        for t in history:
            td = t.get("tx_date")
            if td:
                days = self._days_ago(td)
                week_num = days // 7
                weeks[week_num] = weeks.get(week_num, 0) + float(t.get("amount", 0))
        return list(weeks.values())

    def _days_ago(self, d) -> int:
        if d is None: return 999
        if isinstance(d, str):
            try: d = date.fromisoformat(d)
            except: return 999
        return (date.today() - d).days
