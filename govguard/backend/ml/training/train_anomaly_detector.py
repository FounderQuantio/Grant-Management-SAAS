"""
GovGuard™ — IsolationForest Anomaly Detector Training Script
=============================================================
Run from govguard/backend/:
    python -m ml.training.train_anomaly_detector

Generates synthetic grant transaction data representing normal spending
patterns, trains an IsolationForest, and saves the model.

No labeled data needed — IsolationForest is unsupervised.
"""
from __future__ import annotations

import math
import pickle
import random
import sys
from datetime import date, timedelta
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from ml.anomaly_detector import extract_features, MODEL_PATH


def _random_date(start_days_ago: int = 180) -> date:
    return date.today() - timedelta(days=random.randint(0, start_days_ago))


def _make_normal_tx(vendors: list[str], categories: list[str]) -> tuple[dict, list[dict], float, dict]:
    """Build a (tx, history, budget, cat_budget) tuple representing normal activity."""
    vid = random.choice(vendors)
    cat = random.choice(categories)

    # Normal transaction amount: log-normal centred around $40k (matches real grant data)
    amount = max(500.0, round(random.lognormvariate(10.5, 0.5), 2))

    tx_date = _random_date()
    tx = {
        "amount": amount,
        "vendor_id": vid,
        "cost_category": cat,
        "tx_date": tx_date,
    }

    # Realistic history: 10-50 txns in last 90d
    history = []
    for _ in range(random.randint(10, 50)):
        h_vid = random.choice(vendors)
        h_cat = random.choice(categories)
        h_amount = max(500.0, round(random.lognormvariate(10.5, 0.5), 2))
        h_date = _random_date()
        history.append({"amount": h_amount, "vendor_id": h_vid, "cost_category": h_cat, "tx_date": h_date})

    total_budget = random.choice([200_000.0, 500_000.0, 1_000_000.0])
    cat_budget = {c: total_budget / len(categories) for c in categories}

    return tx, history, total_budget, cat_budget


def _make_anomalous_tx(vendors: list[str], categories: list[str]) -> tuple[dict, list[dict], float, dict]:
    """Build anomalous transactions for model calibration."""
    anomaly_type = random.choice([
        "giant_amount",       # amount 10-20x normal
        "end_of_month_spike", # end-of-month + large
        "dormant_vendor",     # vendor not seen in 90+ days
        "budget_blow",        # spend >> budget
        "round_amount",       # suspiciously round
    ])

    vid = random.choice(vendors)
    cat = random.choice(categories)
    total_budget = 500_000.0
    cat_budget = {c: total_budget / len(categories) for c in categories}

    if anomaly_type == "giant_amount":
        # 3-5x the normal mean (~$40k) → $120k-$200k
        amount = random.uniform(120_000, 250_000)
        tx_date = _random_date()
        tx = {"amount": amount, "vendor_id": vid, "cost_category": cat, "tx_date": tx_date}
        history = [{"amount": max(500.0, random.lognormvariate(10.5, 0.5)), "vendor_id": random.choice(vendors),
                    "cost_category": random.choice(categories), "tx_date": _random_date()} for _ in range(20)]

    elif anomaly_type == "end_of_month_spike":
        today = date.today()
        import calendar
        last = calendar.monthrange(today.year, today.month)[1]
        tx_date = today.replace(day=max(last - 2, 1))
        amount = random.uniform(100_000, 200_000)
        tx = {"amount": amount, "vendor_id": vid, "cost_category": cat, "tx_date": tx_date}
        history = [{"amount": max(500.0, random.lognormvariate(10.5, 0.5)), "vendor_id": random.choice(vendors),
                    "cost_category": random.choice(categories), "tx_date": _random_date(120)} for _ in range(20)]

    elif anomaly_type == "dormant_vendor":
        tx_date = date.today()
        amount = random.uniform(80_000, 150_000)
        tx = {"amount": amount, "vendor_id": vid, "cost_category": cat, "tx_date": tx_date}
        history = [{"amount": max(500.0, random.lognormvariate(10.5, 0.5)), "vendor_id": vid,
                    "cost_category": cat, "tx_date": date.today() - timedelta(days=random.randint(100, 180))}]
        history += [{"amount": max(500.0, random.lognormvariate(10.5, 0.5)), "vendor_id": random.choice(vendors),
                     "cost_category": random.choice(categories), "tx_date": _random_date()} for _ in range(15)]

    elif anomaly_type == "budget_blow":
        # Spent 5-10x over budget (matches 920% burnrate scenario)
        amount = random.uniform(30_000, 80_000)
        tx_date = _random_date()
        tx = {"amount": amount, "vendor_id": vid, "cost_category": cat, "tx_date": tx_date}
        # History totaling 5-9x the budget
        multiplier = random.uniform(5.0, 9.0)
        history = [{"amount": total_budget * multiplier / 20, "vendor_id": random.choice(vendors),
                    "cost_category": random.choice(categories), "tx_date": _random_date()} for _ in range(20)]

    else:  # round_amount
        amount = float(random.choice([100000, 150000, 200000, 250000, 300000]))
        tx_date = _random_date()
        tx = {"amount": amount, "vendor_id": vid, "cost_category": cat, "tx_date": tx_date}
        history = [{"amount": max(500.0, random.lognormvariate(10.5, 0.5)), "vendor_id": random.choice(vendors),
                    "cost_category": random.choice(categories), "tx_date": _random_date()} for _ in range(20)]

    return tx, history, total_budget, cat_budget


def build_dataset() -> np.ndarray:
    random.seed(42)
    np.random.seed(42)

    vendors = [f"vendor-{i:03d}" for i in range(20)]
    categories = ["personnel", "equipment", "travel", "supplies", "indirect", "subcontract"]

    rows = []

    # 500 normal samples
    for _ in range(500):
        tx, hist, budget, cat_budget = _make_normal_tx(vendors, categories)
        rows.append(extract_features(tx, hist, budget, cat_budget))

    # 50 anomalous samples (IsolationForest contamination ≈ 0.09)
    for _ in range(50):
        tx, hist, budget, cat_budget = _make_anomalous_tx(vendors, categories)
        rows.append(extract_features(tx, hist, budget, cat_budget))

    return np.array(rows, dtype=np.float32)


def train() -> None:
    from sklearn.ensemble import IsolationForest
    from sklearn.preprocessing import StandardScaler
    from sklearn.pipeline import Pipeline

    print("Building training dataset…")
    X = build_dataset()
    print(f"  {X.shape[0]} samples, {X.shape[1]} features")

    model = Pipeline([
        ("scaler", StandardScaler()),
        ("iso", IsolationForest(
            n_estimators=200,
            contamination=0.05,   # flags only most extreme 5% — tighter boundary
            max_features=1.0,
            random_state=42,
            n_jobs=-1,
        )),
    ])

    print("Training IsolationForest…")
    model.fit(X)

    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(MODEL_PATH, "wb") as f:
        pickle.dump(model, f, protocol=5)

    print(f"Model saved → {MODEL_PATH}")
    print(f"File size: {MODEL_PATH.stat().st_size / 1024:.1f} KB")

    # Quick sanity check
    from ml.anomaly_detector import AnomalyDetector
    AnomalyDetector._instance = None
    AnomalyDetector._load_attempted = False
    det = AnomalyDetector()
    print(f"Detector available: {det.available()}")

    # Normal transaction should score low
    normal_tx = {"amount": 15000, "vendor_id": "vendor-001", "cost_category": "personnel",
                 "tx_date": date.today() - timedelta(days=10)}
    normal_hist = [{"amount": 12000 + i*500, "vendor_id": "vendor-001",
                    "cost_category": "personnel", "tx_date": date.today() - timedelta(days=i+1)}
                   for i in range(20)]
    score_normal = det.score(normal_tx, normal_hist, 500_000, {"personnel": 200_000, "equipment": 300_000})
    print(f"Normal tx score:    {score_normal:.4f} (expect < 0.60)")

    # Anomalous transaction (huge amount) should score high
    anom_tx = {"amount": 350_000, "vendor_id": "vendor-001", "cost_category": "personnel",
               "tx_date": date.today()}
    score_anom = det.score(anom_tx, normal_hist, 500_000, {"personnel": 200_000, "equipment": 300_000})
    print(f"Anomalous tx score: {score_anom:.4f} (expect > 0.60)")


if __name__ == "__main__":
    train()
