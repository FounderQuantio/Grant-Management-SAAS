"""
GovGuard v2 — Supervised Fraud Classifier (Phase 2)
===================================================
Wraps the trained XGBoost model that uses the 47-rule binary feature vector
as inputs. Falls back gracefully if no model file exists on disk.
"""
from __future__ import annotations

import pickle
from pathlib import Path
from typing import Optional

import numpy as np
import structlog

log = structlog.get_logger()

# Canonical rule ordering — must match FraudDetectionEngine._build_signals() order exactly
RULE_ORDER = [
    "FDE-001", "FDE-002", "FDE-003", "FDE-004", "FDE-005", "FDE-006", "FDE-007",
    "FDE-008", "FDE-009", "FDE-010", "FDE-011", "FDE-012", "FDE-013", "FDE-014",
    "FDE-015", "FDE-016", "FDE-017", "FDE-018", "FDE-019", "FDE-020", "FDE-021",
    "FDE-022", "FDE-023", "FDE-024", "FDE-025", "FDE-026", "FDE-027", "FDE-028",
    "FDE-029", "FDE-030", "FDE-031", "FDE-032", "FDE-033", "FDE-034", "FDE-035",
    "FDE-036", "FDE-037", "FDE-038", "FDE-039", "FDE-040", "FDE-041", "FDE-042",
    "FDE-043", "FDE-044", "FDE-045", "FDE-046", "FDE-047",
]

MODEL_PATH = Path(__file__).parent / "models" / "fraud_classifier_v1.pkl"


def signals_to_features(signals: list) -> np.ndarray:
    """Convert a FraudSignal list into a (1, 47) binary feature matrix."""
    triggered = {s.rule_id for s in signals if s.triggered}
    return np.array(
        [[1 if rule in triggered else 0 for rule in RULE_ORDER]],
        dtype=np.float32,
    )


class FraudClassifier:
    """Singleton XGBoost-based fraud probability predictor."""

    _instance: Optional["FraudClassifier"] = None
    _model = None
    _load_attempted = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def _load(self):
        if self._load_attempted:
            return
        self._load_attempted = True
        if MODEL_PATH.exists():
            try:
                with open(MODEL_PATH, "rb") as f:
                    self._model = pickle.load(f)
                log.info("fraud_classifier.loaded", path=str(MODEL_PATH))
            except Exception as exc:
                log.warning("fraud_classifier.load_failed", error=str(exc))
        else:
            log.info("fraud_classifier.no_model_file", path=str(MODEL_PATH))

    def available(self) -> bool:
        self._load()
        return self._model is not None

    def predict_proba(self, signals: list) -> float:
        """
        Return fraud probability 0.0–1.0.
        Raises RuntimeError if no model is loaded — callers should check available() first.
        """
        self._load()
        if self._model is None:
            raise RuntimeError("No trained model available — run ml/training/train_fraud_classifier.py")
        X = signals_to_features(signals)
        return float(self._model.predict_proba(X)[0, 1])
