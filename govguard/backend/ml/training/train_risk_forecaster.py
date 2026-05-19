"""
GovGuard™ — XGBoost Grant Risk Forecaster Training Script
==========================================================
Run from govguard/backend/:
    python -m ml.training.train_risk_forecaster

Generates synthetic grant-level risk data across low/medium/high risk tiers,
trains an XGBRegressor to predict 30-day forward risk (0-100), and saves the
model to ml/models/risk_forecaster_v1.pkl.
"""
from __future__ import annotations

import pickle
import random
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from ml.risk_forecaster import extract_features, MODEL_PATH


def _make_sample(risk_tier: str) -> tuple[list[float], float]:
    """Return (feature_vector, ground_truth_score) for one synthetic grant."""

    if risk_tier == "low":
        compliance_base  = random.uniform(82, 100)
        compliance_drift = random.uniform(-1.0, 4.0)
        n_months         = random.randint(4, 8)
        open_findings    = random.randint(0, 1)
        open_caps        = random.randint(0, 1)
        overdue_caps     = 0
        days_to_end      = random.randint(60, 365)
        vendor_risk      = random.uniform(0, 28)
        gao_overlap      = random.randint(0, 1)
        burnrate         = random.uniform(0.05, 0.22)
        spend_base       = random.uniform(0.08, 0.20)
        spend_drift      = random.uniform(-0.01, 0.025)

    elif risk_tier == "medium":
        compliance_base  = random.uniform(55, 80)
        compliance_drift = random.uniform(-4.0, 1.5)
        n_months         = random.randint(3, 7)
        open_findings    = random.randint(1, 4)
        open_caps        = random.randint(0, 3)
        overdue_caps     = random.randint(0, 1)
        days_to_end      = random.randint(20, 120)
        vendor_risk      = random.uniform(20, 58)
        gao_overlap      = random.randint(0, 3)
        burnrate         = random.uniform(0.22, 0.65)
        spend_base       = random.uniform(0.20, 0.50)
        spend_drift      = random.uniform(0.00, 0.055)

    else:  # high
        compliance_base  = random.uniform(18, 58)
        compliance_drift = random.uniform(-9.0, -1.0)
        n_months         = random.randint(2, 5)
        open_findings    = random.randint(3, 10)
        open_caps        = random.randint(1, 7)
        overdue_caps     = random.randint(1, 4)
        days_to_end      = random.randint(0, 45)
        vendor_risk      = random.uniform(40, 100)
        gao_overlap      = random.randint(1, 5)
        burnrate         = random.uniform(0.55, 3.0)
        spend_base       = random.uniform(0.40, 0.90)
        spend_drift      = random.uniform(0.04, 0.14)

    # Build histories with realistic variation
    compliance_history: list[float] = []
    val = compliance_base - compliance_drift * (n_months - 1)
    for _ in range(n_months):
        compliance_history.append(max(0.0, min(100.0, val + random.gauss(0, 2.2))))
        val += compliance_drift

    spend_history: list[float] = []
    val = spend_base
    for _ in range(n_months):
        spend_history.append(max(0.0, min(1.0, val + random.gauss(0, 0.018))))
        val += spend_drift

    features = extract_features(
        compliance_score_history=compliance_history,
        spend_pct_history=spend_history,
        open_findings_count=open_findings,
        open_cap_count=open_caps,
        overdue_cap_count=overdue_caps,
        days_to_period_end=days_to_end,
        vendor_network_risk=vendor_risk,
        gao_overlap_count=gao_overlap,
        burnrate_pct=burnrate,
    )

    ground_truth = _ground_truth(
        compliance_last=compliance_history[-1],
        compliance_slope=features[1],
        open_findings=open_findings,
        overdue_caps=overdue_caps,
        vendor_risk=vendor_risk,
        gao_overlap=gao_overlap,
        burnrate=burnrate,
        days_to_end=days_to_end,
    )

    return features, ground_truth


def _ground_truth(
    compliance_last: float,
    compliance_slope: float,
    open_findings: int,
    overdue_caps: int,
    vendor_risk: float,
    gao_overlap: int,
    burnrate: float,
    days_to_end: int,
) -> float:
    """Non-linear ground truth for XGBoost to learn beyond the linear formula."""
    compliance_risk = max(0.0, 100.0 - compliance_last)
    if compliance_slope < -3.0:
        compliance_risk = min(100.0, compliance_risk * 1.35)

    findings_risk = min(100.0, open_findings * 12.5 + overdue_caps * 22.0)

    burnrate_risk = min(100.0, (min(burnrate, 3.0) / 3.0) * 82.0)
    if days_to_end <= 30:
        burnrate_risk = min(100.0, burnrate_risk * 1.45)
    elif days_to_end <= 60:
        burnrate_risk = min(100.0, burnrate_risk * 1.18)

    network_risk = vendor_risk
    gao_risk = min(50.0, gao_overlap * 9.0)

    # Non-linear: overdue CAPs amplify risk more when compliance is already low
    cap_amplifier = min(22.0, overdue_caps * max(0.0, (80.0 - compliance_last) / 5.0))

    score = (
        compliance_risk * 0.32
        + findings_risk * 0.26
        + burnrate_risk * 0.18
        + network_risk  * 0.12
        + gao_risk      * 0.08
        + cap_amplifier * 0.04
    )

    # Small Gaussian noise so XGBoost doesn't overfit to the formula exactly
    return float(max(0.0, min(100.0, score + random.gauss(0, 2.5))))


def build_dataset() -> tuple[np.ndarray, np.ndarray]:
    random.seed(42)
    np.random.seed(42)

    Xs: list[list[float]] = []
    ys: list[float] = []

    for tier, n in [("low", 500), ("medium", 500), ("high", 500)]:
        for _ in range(n):
            feats, label = _make_sample(tier)
            Xs.append(feats)
            ys.append(label)

    return np.array(Xs, dtype=np.float32), np.array(ys, dtype=np.float32)


def train() -> None:
    from xgboost import XGBRegressor

    print("Building training dataset…")
    X, y = build_dataset()
    print(f"  {X.shape[0]} samples, {X.shape[1]} features  |  target range [{y.min():.1f}, {y.max():.1f}]")

    model = XGBRegressor(
        n_estimators=400,
        max_depth=4,
        learning_rate=0.04,
        subsample=0.8,
        colsample_bytree=0.8,
        min_child_weight=3,
        objective="reg:squarederror",
        random_state=42,
        n_jobs=-1,
    )

    print("Training model…")
    model.fit(X, y)

    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(MODEL_PATH, "wb") as f:
        pickle.dump(model, f, protocol=5)

    print(f"Model saved → {MODEL_PATH}")
    print(f"File size: {MODEL_PATH.stat().st_size / 1024:.1f} KB")

    # Sanity checks
    from ml.risk_forecaster import RiskForecaster
    RiskForecaster._instance = None
    RiskForecaster._load_attempted = False
    rf = RiskForecaster()
    print(f"Forecaster available: {rf.available()}")

    low_feats = extract_features(
        compliance_score_history=[90, 92, 91, 93],
        spend_pct_history=[0.10, 0.12, 0.14, 0.13],
        open_findings_count=0,
        open_cap_count=0,
        overdue_cap_count=0,
        days_to_period_end=180,
        vendor_network_risk=10.0,
        gao_overlap_count=0,
        burnrate_pct=0.13,
    )
    high_feats = extract_features(
        compliance_score_history=[55, 48, 40, 32],
        spend_pct_history=[0.40, 0.55, 0.70, 0.85],
        open_findings_count=7,
        open_cap_count=4,
        overdue_cap_count=3,
        days_to_period_end=12,
        vendor_network_risk=75.0,
        gao_overlap_count=3,
        burnrate_pct=1.8,
    )
    print(f"Low-risk grant score:  {rf.predict(low_feats):.1f}  (expect < 25)")
    print(f"High-risk grant score: {rf.predict(high_feats):.1f}  (expect > 65)")


if __name__ == "__main__":
    train()
