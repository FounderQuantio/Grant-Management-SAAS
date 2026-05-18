"""
GovGuard v2 — Fraud Classifier Training Script (Phase 2)
=========================================================
Builds training data from two sources:
  1. 70 GAO seed scenarios  — runs each through the 47-rule engine to get
     the feature vector; labels from expected_output.alert_type
  2. DB confirmed labels    — rows in fraud_assessments with confirmed_label
     IS NOT NULL (from analyst Fraud/Clean clicks in the UI)

Then trains an XGBoost binary classifier and saves it to ml/models/.

Usage:
    cd govguard/backend
    DATABASE_URL=postgresql://... python ml/training/train_fraud_classifier.py
"""
from __future__ import annotations

import json
import os
import pickle
import sys
from datetime import date
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from services.fraud_detection.engine import FraudDetectionEngine
from ml.fraud_classifier import RULE_ORDER, signals_to_features, MODEL_PATH
from tests.gao.testkit import (
    _amount, _vendor_id, _invoice_ref, _sam_status, _risk_tier,
    _cost_category, _grant_budget, _prior_invoices, _vendor_spend_30d,
    _boost_spend_for_velocity, _cross_grant_charges, _related_party,
    _build_extra_signals,
)

DATASET = ROOT / "tests" / "fixtures" / "gao" / "govguard_v2_gao_test_dataset.json"

# Scenarios that test infrastructure SLAs, not fraud detection
_SKIP_ALERT_TYPES = frozenset({"DNP_BATCH_VERDICT", "RECOVERY_QUEUE_PRIORITIZED"})

_engine = FraudDetectionEngine()


def _build_gao_samples() -> tuple[np.ndarray, np.ndarray]:
    with open(DATASET) as f:
        raw = json.load(f)
    scenarios = raw["scenarios"] if isinstance(raw, dict) else raw

    X, y = [], []
    skipped = 0
    for sc in scenarios:
        inp      = sc.get("synthetic_input_data", {})
        expected = sc.get("expected_output", {})
        alert    = expected.get("alert_type", "")

        if alert in _SKIP_ALERT_TYPES:
            skipped += 1
            continue

        # NO_ALERT_* → clean (0); everything else → fraud (1)
        label = 0 if alert.startswith("NO_ALERT") else 1

        amt    = _amount(inp)
        vid    = _vendor_id(inp)
        ref    = _invoice_ref(inp)
        prior  = _prior_invoices(inp, vid)
        spend  = _boost_spend_for_velocity(inp, _vendor_spend_30d(inp, prior))
        cat    = _cost_category(inp)

        assessment = _engine.assess(
            transaction_id=f"train-{ref}",
            amount=amt,
            vendor_id=vid,
            vendor_sam_status=_sam_status(inp),
            invoice_ref=ref,
            tx_date=date.today(),
            cost_category=cat,
            grant_budget=_grant_budget(inp, amt),
            prior_invoices=prior,
            vendor_spend_30d=spend,
            all_grant_charges=_cross_grant_charges(inp, vid, cat),
            vendor_risk_tier=_risk_tier(inp),
            related_party_flag=_related_party(inp),
            extra_signals=_build_extra_signals(inp),
        )

        X.append(signals_to_features(assessment.signals)[0])
        y.append(label)
        marker = "✓" if label else "○"
        print(f"  {marker} {sc['test_case_id']} [{alert}]")

    if skipped:
        print(f"  (skipped {skipped} performance scenarios)")
    return np.array(X, dtype=np.float32), np.array(y, dtype=np.int32)


def _build_db_samples() -> tuple[np.ndarray, np.ndarray]:
    """Pull confirmed analyst labels from fraud_assessments."""
    url = os.environ.get("DATABASE_URL")
    if not url:
        print("  DATABASE_URL not set — skipping DB labels")
        return np.empty((0, len(RULE_ORDER)), dtype=np.float32), np.empty(0, dtype=np.int32)

    try:
        import psycopg2
    except ImportError:
        print("  psycopg2 not installed — skipping DB labels")
        return np.empty((0, len(RULE_ORDER)), dtype=np.float32), np.empty(0, dtype=np.int32)

    conn = psycopg2.connect(url)
    cur  = conn.cursor()
    cur.execute(
        "SELECT signal_detail, confirmed_label "
        "FROM fraud_assessments WHERE confirmed_label IS NOT NULL"
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()

    if not rows:
        print("  No confirmed labels in DB yet")
        return np.empty((0, len(RULE_ORDER)), dtype=np.float32), np.empty(0, dtype=np.int32)

    X, y = [], []
    for signal_detail, confirmed_label in rows:
        if isinstance(signal_detail, str):
            signals = json.loads(signal_detail)
        else:
            signals = signal_detail  # psycopg2 auto-parses JSONB
        triggered = {s["rule"] for s in signals if s.get("triggered")}
        X.append([1 if r in triggered else 0 for r in RULE_ORDER])
        y.append(1 if confirmed_label else 0)

    print(f"  {len(rows)} DB rows loaded  (fraud={sum(y)}, clean={len(y)-sum(y)})")
    return np.array(X, dtype=np.float32), np.array(y, dtype=np.int32)


def _synthetic_clean_samples(n: int) -> np.ndarray:
    """
    Generate synthetic negative (clean) feature vectors.
    Clean transactions trigger at most 1-2 low-weight incidental rules
    (e.g. weekend timing, round dollar) but no material fraud indicators.
    """
    rng = np.random.default_rng(42)
    # Indices of rules with low weight that can fire incidentally
    INCIDENTAL = [2, 5, 6]  # FDE-003 round dollar, FDE-006 budget, FDE-007 weekend
    X_neg = np.zeros((n, len(RULE_ORDER)), dtype=np.float32)
    for i in range(n):
        n_incidental = rng.integers(0, 3)  # 0, 1, or 2 incidental rules
        for _ in range(n_incidental):
            X_neg[i, int(rng.choice(INCIDENTAL))] = 1.0
    return X_neg


def _train(X: np.ndarray, y: np.ndarray):
    try:
        import xgboost as xgb
    except ImportError:
        print("ERROR: xgboost not installed — pip install xgboost")
        sys.exit(1)

    from sklearn.model_selection import StratifiedKFold, cross_val_score

    pos = int(y.sum())
    neg = len(y) - pos
    scale_pos_weight = neg / max(pos, 1)

    clf = xgb.XGBClassifier(
        n_estimators=300,
        max_depth=4,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        scale_pos_weight=scale_pos_weight,
        eval_metric="logloss",
        random_state=42,
        verbosity=0,
    )

    n_splits = min(5, max(2, pos))
    try:
        cv = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=42)
        scores = cross_val_score(clf, X, y, cv=cv, scoring="roc_auc")
        print(f"  Cross-validated ROC-AUC ({n_splits}-fold): {scores.mean():.3f} ± {scores.std():.3f}")
    except Exception as exc:
        print(f"  Cross-validation skipped ({exc.__class__.__name__}: {exc})")

    clf.fit(X, y)

    # Feature importance (top 10 rules by gain)
    importances = clf.feature_importances_
    top10 = sorted(zip(RULE_ORDER, importances), key=lambda x: x[1], reverse=True)[:10]
    print("  Top 10 rules by importance:")
    for rule, imp in top10:
        print(f"    {rule}  {imp:.4f}")

    return clf


def main():
    print("=== GovGuard Phase 2 — Fraud Classifier Training ===\n")

    print("Building GAO seed samples...")
    X_gao, y_gao = _build_gao_samples()
    print(f"  GAO total: {len(X_gao)} samples  (fraud={y_gao.sum()}, clean={len(y_gao)-y_gao.sum()})\n")

    print("Building DB confirmed samples...")
    X_db, y_db = _build_db_samples()

    if len(X_db):
        X = np.vstack([X_gao, X_db])
        y = np.concatenate([y_gao, y_db])
    else:
        X, y = X_gao, y_gao

    # If clean samples are < 20% of total, generate synthetic negatives to balance.
    # Real analyst labels from the DB will eventually replace these synthetic samples.
    pos = int(y.sum())
    neg = len(y) - pos
    if neg < pos * 0.25:
        n_synthetic = pos - neg
        X_syn = _synthetic_clean_samples(n_synthetic)
        y_syn = np.zeros(n_synthetic, dtype=np.int32)
        X = np.vstack([X, X_syn])
        y = np.concatenate([y, y_syn])
        print(f"  Added {n_synthetic} synthetic clean negatives (GAO dataset is fraud-heavy)")

    print(f"\nTotal training set: {len(X)} samples  (fraud={y.sum()}, clean={len(y)-y.sum()})")
    print("\nTraining XGBoost classifier...")
    model = _train(X, y)

    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(MODEL_PATH, "wb") as f:
        pickle.dump(model, f)
    print(f"\nModel saved → {MODEL_PATH}")
    print("Redeploy Railway to activate Phase 2 scoring.")


if __name__ == "__main__":
    main()
