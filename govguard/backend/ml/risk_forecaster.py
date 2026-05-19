"""
GovGuard™ — XGBoost Grant Risk Forecaster
Predicts 30-day forward risk score (0–100) from grant state features.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import structlog

log = structlog.get_logger()

MODEL_PATH = Path(__file__).parent / "models" / "risk_forecaster_v1.pkl"

FEATURE_NAMES = [
    "compliance_last",        # most recent compliance score (0-100)
    "compliance_slope",       # linear trend per month (positive = improving)
    "compliance_volatility",  # std dev of compliance history
    "spend_last",             # most recent monthly spend fraction (0-1)
    "spend_slope",            # burnrate trend per month
    "spend_acceleration",     # second derivative (is burnrate speeding up?)
    "open_findings",          # count of open audit findings
    "open_caps",              # count of open corrective action plans
    "overdue_caps",           # count of overdue CAPs
    "days_to_end_norm",       # days to period end / 365 (0-1)
    "vendor_network_risk",    # 0-100 from entity intelligence
    "gao_overlap_count",      # number of matching GAO high-risk programs
    "burnrate_pct",           # % of budget consumed in last 30 days (0-1, capped at 3)
    "period_end_pressure",    # 1 if within 30 days of period end
    "findings_density",       # open_findings / max(months_active, 1)
]

assert len(FEATURE_NAMES) == 15


def extract_features(
    *,
    compliance_score_history: list[float],
    spend_pct_history: list[float],
    open_findings_count: int,
    open_cap_count: int,
    overdue_cap_count: int,
    days_to_period_end: int,
    vendor_network_risk: float,
    gao_overlap_count: int,
    burnrate_pct: float,
) -> list[float]:
    """Convert grant state into a 15-dim feature vector."""
    import statistics

    def slope(series: list[float]) -> float:
        n = len(series)
        if n < 2:
            return 0.0
        if n == 2:
            return series[-1] - series[0]
        xs = list(range(n))
        mx, my = sum(xs) / n, sum(series) / n
        num = sum((xs[i] - mx) * (series[i] - my) for i in range(n))
        den = sum((xs[i] - mx) ** 2 for i in range(n))
        return num / den if den else 0.0

    compliance_last = compliance_score_history[-1] if compliance_score_history else 70.0
    compliance_sl = slope(compliance_score_history)
    compliance_vol = statistics.stdev(compliance_score_history) if len(compliance_score_history) > 1 else 0.0

    spend_last = spend_pct_history[-1] if spend_pct_history else 0.2
    spend_sl = slope(spend_pct_history)
    # acceleration: slope of last 3 vs slope of first 3
    spend_accel = 0.0
    if len(spend_pct_history) >= 4:
        slope_early = slope(spend_pct_history[:3])
        slope_late = slope(spend_pct_history[-3:])
        spend_accel = slope_late - slope_early

    months_active = len(spend_pct_history) or 1
    findings_density = open_findings_count / months_active

    return [
        float(compliance_last),
        float(compliance_sl),
        float(compliance_vol),
        float(min(1.0, spend_last)),
        float(spend_sl),
        float(spend_accel),
        float(open_findings_count),
        float(open_cap_count),
        float(overdue_cap_count),
        float(min(days_to_period_end, 365)) / 365.0,
        float(min(100.0, vendor_network_risk)),
        float(gao_overlap_count),
        float(min(3.0, burnrate_pct)),
        1.0 if days_to_period_end <= 30 else 0.0,
        float(findings_density),
    ]


class RiskForecaster:
    """
    XGBoost regression singleton.
    predict() returns a 30-day forward risk score in [0, 100].
    Falls back gracefully if model unavailable.
    """
    _instance: Optional["RiskForecaster"] = None
    _model = None
    _load_attempted: bool = False

    def __new__(cls) -> "RiskForecaster":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def available(self) -> bool:
        self._load()
        return self._model is not None

    def predict(self, features: list[float]) -> float:
        """Return predicted risk score 0–100."""
        self._load()
        if self._model is None:
            raise RuntimeError("RiskForecaster model not loaded")
        import numpy as np
        X = np.array(features, dtype=np.float32).reshape(1, -1)
        score = float(self._model.predict(X)[0])
        return round(max(0.0, min(100.0, score)), 2)

    def predict_with_drivers(
        self, features: list[float]
    ) -> tuple[float, list[dict]]:
        """Return (risk_score, drivers) where drivers are SHAP contributions.

        Each driver: {"factor": str, "contribution": float, "direction": str}
        Positive contribution = pushes score toward more risk.
        Sorted by absolute contribution descending, top 6 returned.
        """
        self._load()
        if self._model is None:
            raise RuntimeError("RiskForecaster model not loaded")
        import numpy as np
        import xgboost as xgb

        X = np.array(features, dtype=np.float32).reshape(1, -1)
        score = round(max(0.0, min(100.0, float(self._model.predict(X)[0]))), 2)

        dmat = xgb.DMatrix(X)
        # shape (1, n_features + 1) — last column is the base score bias
        contribs = self._model.get_booster().predict(dmat, pred_contribs=True)[0]

        drivers = []
        for name, contrib in zip(FEATURE_NAMES, contribs[:-1]):
            c = float(contrib)
            if abs(c) >= 0.5:
                drivers.append({
                    "factor": name,
                    "contribution": round(c, 2),
                    "direction": "increasing_risk" if c > 0 else "reducing_risk",
                })
        drivers.sort(key=lambda d: abs(d["contribution"]), reverse=True)
        return score, drivers[:6]

    def _load(self) -> None:
        if self._load_attempted:
            return
        self._load_attempted = True
        try:
            import pickle
            with open(MODEL_PATH, "rb") as f:
                self._model = pickle.load(f)
            log.info("risk_forecaster.loaded", path=str(MODEL_PATH))
        except Exception as exc:
            log.warning("risk_forecaster.load_failed", error=str(exc))
            self._model = None
