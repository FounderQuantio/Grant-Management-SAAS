"""
GovGuard™ — Fraud Classifier Retraining Pipeline
==================================================
Triggered via POST /api/v2/fraud/retrain or run directly:
    cd govguard/backend
    python -m ml.training.retrain_fraud_classifier

Pulls confirmed fraud labels from fraud_assessments, reconstructs the
47-feature binary signal vectors from stored signal_detail, mixes with
GAO seed scenarios (synthetic regularization), and retrains XGBClassifier.

Saves versioned model: fraud_classifier_v{N+1}.pkl
Does NOT overwrite fraud_classifier_v1.pkl — caller must promote explicitly.
Auto-promotes if precision AND recall >= AUTO_PROMOTE_THRESHOLD.
"""
from __future__ import annotations

import pickle
import sys
from pathlib import Path
from typing import Optional

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from ml.fraud_classifier import RULE_ORDER, MODEL_PATH

AUTO_PROMOTE_THRESHOLD = 0.70   # both precision and recall must meet this
MIN_LABELED_SAMPLES    = 20     # minimum confirmed labels before retraining


def _signal_detail_to_vector(signal_detail: list[dict]) -> list[float]:
    """Reconstruct 47-dim feature vector from stored signal_detail."""
    lookup = {s["rule"]: bool(s.get("triggered", False)) for s in signal_detail}
    return [1.0 if lookup.get(rule_id, False) else 0.0 for rule_id in RULE_ORDER]


def _load_gao_scenarios() -> tuple[np.ndarray, np.ndarray]:
    """Load GAO seed scenarios as synthetic training data."""
    import json
    from services.fraud_detection.engine import FraudDetectionEngine
    from ml.fraud_classifier import signals_to_features
    from tests.gao.testkit import (
        _amount, _vendor_id, _invoice_ref, _sam_status, _risk_tier,
        _cost_category, _grant_budget, _prior_invoices, _vendor_spend_30d,
        _cross_grant_charges, _related_party, _build_extra_signals,
    )

    DATASET = ROOT / "tests" / "fixtures" / "gao" / "govguard_v2_gao_test_dataset.json"
    _SKIP = frozenset({"DNP_BATCH_VERDICT", "RECOVERY_QUEUE_PRIORITIZED"})
    engine = FraudDetectionEngine()

    with open(DATASET) as f:
        raw = json.load(f)
    scenarios = raw["scenarios"] if isinstance(raw, dict) else raw

    X, y = [], []
    for sc in scenarios:
        inp = sc.get("synthetic_input_data", {})
        expected = sc.get("expected_output", {})
        alert = expected.get("alert_type", "")
        if alert in _SKIP:
            continue
        label = 1 if expected.get("alert_fired", False) else 0
        try:
            signals = engine._build_signals(
                amount=_amount(inp),
                vendor_id=_vendor_id(inp),
                vendor_sam_status=_sam_status(inp),
                invoice_ref=_invoice_ref(inp),
                tx_date=inp.get("tx_date", __import__("datetime").date.today()),
                cost_category=_cost_category(inp),
                grant_budget=_grant_budget(inp),
                prior_invoices=_prior_invoices(inp),
                vendor_spend_30d=_vendor_spend_30d(inp),
                all_grant_charges=_cross_grant_charges(inp),
                vendor_risk_tier=_risk_tier(inp),
                related_party_flag=_related_party(inp),
                extra_signals=_build_extra_signals(inp),
            )
            X.append(signals_to_features(signals)[0].tolist())
            y.append(label)
        except Exception:
            continue

    return np.array(X, dtype=np.float32), np.array(y, dtype=np.float32)


def retrain(
    labeled_rows: list[dict],
    *,
    synthetic_weight: float = 0.4,
    auto_promote: bool = True,
) -> dict:
    """
    Retrain fraud classifier from confirmed labels + synthetic GAO scenarios.

    labeled_rows: list of {"signal_detail": [...], "confirmed_label": bool}
    Returns a report dict. Saves versioned model to ml/models/.
    """
    from xgboost import XGBClassifier

    labeled_X = [_signal_detail_to_vector(r["signal_detail"]) for r in labeled_rows]
    labeled_y = [1 if r["confirmed_label"] else 0 for r in labeled_rows]
    n_labeled = len(labeled_X)

    if n_labeled < MIN_LABELED_SAMPLES:
        return {
            "status": "skipped",
            "reason": f"Only {n_labeled} confirmed labels — need at least {MIN_LABELED_SAMPLES}",
            "labeled_count": n_labeled,
        }

    # Load synthetic data for regularization
    try:
        X_syn, y_syn = _load_gao_scenarios()
        n_syn = min(len(X_syn), int(n_labeled * synthetic_weight / max(1e-6, 1 - synthetic_weight)))
        idx = np.random.default_rng(42).choice(len(X_syn), min(n_syn, len(X_syn)), replace=False)
        X_syn_sub = X_syn[idx]
        y_syn_sub = y_syn[idx]
    except Exception as exc:
        X_syn_sub = np.zeros((0, 47), dtype=np.float32)
        y_syn_sub = np.zeros(0, dtype=np.float32)
        n_syn = 0

    X_all = np.vstack([np.array(labeled_X, dtype=np.float32), X_syn_sub]) if len(X_syn_sub) else np.array(labeled_X, dtype=np.float32)
    y_all = np.concatenate([np.array(labeled_y, dtype=np.float32), y_syn_sub]) if len(y_syn_sub) else np.array(labeled_y, dtype=np.float32)

    # Confirmed labels get full weight; synthetic gets reduced weight
    sample_weight = np.concatenate([
        np.ones(n_labeled, dtype=np.float32),
        np.full(len(X_syn_sub), synthetic_weight, dtype=np.float32),
    ])

    pos = (y_all == 1).sum()
    neg = (y_all == 0).sum()

    model = XGBClassifier(
        n_estimators=300,
        max_depth=4,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        min_child_weight=3,
        scale_pos_weight=max(1.0, neg / max(1, pos)),
        objective="binary:logistic",
        eval_metric="logloss",
        random_state=42,
        n_jobs=-1,
    )
    model.fit(X_all, y_all, sample_weight=sample_weight)

    # Evaluate on labeled-only subset (ground truth)
    probs_labeled = model.predict_proba(np.array(labeled_X, dtype=np.float32))[:, 1]
    preds = (probs_labeled >= 0.5).astype(int)
    y_arr = np.array(labeled_y)
    tp = int(((preds == 1) & (y_arr == 1)).sum())
    fp = int(((preds == 1) & (y_arr == 0)).sum())
    fn = int(((preds == 0) & (y_arr == 1)).sum())
    precision = round(tp / max(1, tp + fp), 3)
    recall    = round(tp / max(1, tp + fn), 3)

    # Save versioned model
    existing = sorted(MODEL_PATH.parent.glob("fraud_classifier_v*.pkl"))
    version  = len(existing) + 1
    new_path = MODEL_PATH.parent / f"fraud_classifier_v{version}.pkl"
    with open(new_path, "wb") as f:
        pickle.dump(model, f, protocol=5)

    # Auto-promote: copy to the live path and reset singleton
    promoted = False
    if auto_promote and precision >= AUTO_PROMOTE_THRESHOLD and recall >= AUTO_PROMOTE_THRESHOLD:
        import shutil
        shutil.copy2(new_path, MODEL_PATH)
        # Reset FraudClassifier singleton so next call loads new model
        from ml.fraud_classifier import FraudClassifier
        FraudClassifier._instance = None
        FraudClassifier._load_attempted = False
        FraudClassifier._model = None
        promoted = True

    return {
        "status": "trained",
        "promoted": promoted,
        "model_version": version,
        "model_path": str(new_path),
        "labeled_count": n_labeled,
        "synthetic_count": int(len(X_syn_sub)),
        "precision": precision,
        "recall": recall,
        "fraud_rate_in_labels": round(sum(labeled_y) / max(1, n_labeled), 3),
        "auto_promote_threshold": AUTO_PROMOTE_THRESHOLD,
    }


if __name__ == "__main__":
    import asyncio, os
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy import text

    DATABASE_URL = os.environ.get("DATABASE_URL", "")
    if not DATABASE_URL:
        print("Set DATABASE_URL env var first.")
        sys.exit(1)

    async def _main() -> None:
        engine = create_async_engine(DATABASE_URL)
        async with AsyncSession(engine) as session:
            result = await session.execute(text(
                "SELECT signal_detail, confirmed_label FROM fraud_assessments "
                "WHERE confirmed_label IS NOT NULL ORDER BY confirmed_at DESC"
            ))
            rows = [{"signal_detail": r["signal_detail"] or [], "confirmed_label": bool(r["confirmed_label"])}
                    for r in result.mappings().all()]

        report = retrain(rows)
        import json
        print(json.dumps(report, indent=2))

    asyncio.run(_main())
