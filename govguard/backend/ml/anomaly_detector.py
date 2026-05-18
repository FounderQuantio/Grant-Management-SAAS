"""
GovGuard™ — IsolationForest Anomaly Detector
Singleton wrapper around a trained IsolationForest model.
20-feature transaction representation for unsupervised anomaly scoring.
"""
from __future__ import annotations

import math
import statistics
from datetime import date
from pathlib import Path
from typing import Optional

import structlog

log = structlog.get_logger()

MODEL_PATH = Path(__file__).parent / "models" / "anomaly_detector_v1.pkl"

# Feature names in canonical order (must match training)
FEATURE_NAMES = [
    "log_amount",
    "day_of_week",
    "day_of_month",
    "month",
    "is_end_of_month",
    "is_weekend",
    "vendor_tx_count_30d",
    "vendor_spend_30d_log",
    "vendor_grant_share",
    "grant_tx_count_30d",
    "grant_weekly_spend_log",
    "budget_utilization",
    "category_share",
    "category_budget_ratio",
    "amount_vs_vendor_median",
    "amount_vs_grant_median",
    "days_since_last_vendor_tx",
    "is_round_amount",
    "vendor_unique_count_30d",
    "amount_percentile",
]

assert len(FEATURE_NAMES) == 20


def extract_features(
    tx: dict,
    history: list[dict],
    grant_total_budget: float,
    grant_budget_by_category: dict,
) -> list[float]:
    """Convert a transaction + historical context into a 20-dim feature vector."""
    amount = float(tx.get("amount", 0))
    vid = tx.get("vendor_id", "")
    cat = tx.get("cost_category", "")

    tx_date = tx.get("tx_date")
    if isinstance(tx_date, str):
        try:
            tx_date = date.fromisoformat(tx_date)
        except Exception:
            tx_date = date.today()
    elif tx_date is None:
        tx_date = date.today()

    def days_ago(d) -> int:
        if d is None:
            return 999
        if isinstance(d, str):
            try:
                d = date.fromisoformat(d)
            except Exception:
                return 999
        if hasattr(d, "date"):
            d = d.date()
        return max(0, (date.today() - d).days)

    import calendar
    last_day = calendar.monthrange(tx_date.year, tx_date.month)[1]
    is_end_of_month = 1.0 if (last_day - tx_date.day) <= 5 else 0.0
    is_weekend = 1.0 if tx_date.weekday() >= 5 else 0.0

    # History amounts and per-vendor subsets
    all_amounts = [float(t.get("amount", 0)) for t in history]
    total_grant_spend = sum(all_amounts) + amount

    vendor_history = [t for t in history if t.get("vendor_id") == vid]
    vendor_30d = [t for t in vendor_history if days_ago(t.get("tx_date")) <= 30]
    vendor_spend_30d = sum(float(t.get("amount", 0)) for t in vendor_30d)
    vendor_total_spend = sum(float(t.get("amount", 0)) for t in vendor_history) + amount

    grant_30d = [t for t in history if days_ago(t.get("tx_date")) <= 30]
    grant_tx_count_30d = len(grant_30d)

    grant_7d = [t for t in history if days_ago(t.get("tx_date")) <= 7]
    weekly_spend = sum(float(t.get("amount", 0)) for t in grant_7d) + amount

    cat_spend = sum(float(t.get("amount", 0)) for t in history if t.get("cost_category") == cat) + amount
    cat_budget = grant_budget_by_category.get(cat, 0)
    total_budget_approved = sum(grant_budget_by_category.values()) or grant_total_budget or 1.0

    # Vendor median for amount normalisation
    vendor_amounts = [float(t.get("amount", 0)) for t in vendor_history]
    vendor_median = statistics.median(vendor_amounts) if vendor_amounts else amount
    grant_median = statistics.median(all_amounts) if all_amounts else amount

    # Days since last vendor tx (capped at 180)
    last_vendor_tx = None
    for t in sorted(vendor_history, key=lambda x: x.get("tx_date", ""), reverse=True):
        last_vendor_tx = t
        break
    days_dormant = min(180.0, float(days_ago(last_vendor_tx.get("tx_date")) if last_vendor_tx else 180))

    # Amount percentile within grant history
    smaller = sum(1 for a in all_amounts if a <= amount)
    amount_pct = smaller / max(len(all_amounts), 1)

    # Unique vendors in 30d
    unique_vendors_30d = len({t.get("vendor_id") for t in grant_30d})

    # Budget utilisation (total spent / total budget)
    budget_util = min(10.0, (total_grant_spend) / max(grant_total_budget, 1.0))

    return [
        math.log1p(amount),                                          # log_amount
        float(tx_date.weekday()),                                    # day_of_week
        float(tx_date.day),                                          # day_of_month
        float(tx_date.month),                                        # month
        is_end_of_month,                                             # is_end_of_month
        is_weekend,                                                  # is_weekend
        float(len(vendor_30d)),                                      # vendor_tx_count_30d
        math.log1p(vendor_spend_30d),                                # vendor_spend_30d_log
        vendor_total_spend / max(total_grant_spend, 1.0),            # vendor_grant_share
        float(grant_tx_count_30d),                                   # grant_tx_count_30d
        math.log1p(weekly_spend),                                    # grant_weekly_spend_log
        budget_util,                                                  # budget_utilization
        cat_spend / max(total_grant_spend, 1.0),                     # category_share
        cat_spend / max(cat_budget, 1.0),                            # category_budget_ratio
        amount / max(vendor_median, 1.0),                            # amount_vs_vendor_median
        amount / max(grant_median, 1.0),                             # amount_vs_grant_median
        days_dormant,                                                # days_since_last_vendor_tx
        1.0 if amount % 1000 == 0 and amount >= 1000 else 0.0,      # is_round_amount
        float(unique_vendors_30d),                                   # vendor_unique_count_30d
        amount_pct,                                                  # amount_percentile
    ]


class AnomalyDetector:
    """
    IsolationForest singleton.
    score() returns a value in [0, 1] — higher means more anomalous.
    Scores above THRESHOLD_WARNING / THRESHOLD_CRITICAL trigger alerts.
    """
    _instance: Optional["AnomalyDetector"] = None
    _model = None
    _load_attempted: bool = False

    # ML fires only when rules already flagged something (confirmation mode).
    # Standalone threshold kept higher to avoid false positives on clean grants.
    THRESHOLD_WARNING  = 0.565   # used when at least one rule alert fired
    THRESHOLD_CRITICAL = 0.72    # used standalone (no rule support needed)

    def __new__(cls) -> "AnomalyDetector":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def available(self) -> bool:
        self._load()
        return self._model is not None

    def score(
        self,
        tx: dict,
        history: list[dict],
        grant_total_budget: float,
        grant_budget_by_category: dict,
    ) -> float:
        """Return anomaly probability in [0, 1]. Raises if model unavailable."""
        self._load()
        if self._model is None:
            raise RuntimeError("AnomalyDetector model not loaded")
        import numpy as np
        feats = extract_features(tx, history, grant_total_budget, grant_budget_by_category)
        X = np.array(feats, dtype=np.float32).reshape(1, -1)
        # IsolationForest decision_function: more negative = more anomalous
        raw = float(self._model.decision_function(X)[0])
        # Normalise to [0,1]: raw typically in [-0.5, 0.5]
        normalised = max(0.0, min(1.0, 0.5 - raw))
        return round(normalised, 4)

    def _load(self) -> None:
        if self._load_attempted:
            return
        self._load_attempted = True
        try:
            import pickle
            with open(MODEL_PATH, "rb") as f:
                self._model = pickle.load(f)
            log.info("anomaly_detector.loaded", path=str(MODEL_PATH))
        except Exception as exc:
            log.warning("anomaly_detector.load_failed", error=str(exc))
            self._model = None
