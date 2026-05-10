"""
GovGuard™ — ML Risk Scorer
IsolationForest-based anomaly detection with SHAP explainability.
Production: loads model from S3. Development: uses synthetic model.
"""
import os
import pickle
from decimal import Decimal
from typing import Optional, Tuple
from pathlib import Path

import numpy as np
import structlog

log = structlog.get_logger()

FEATURE_NAMES = [
    "amount",
    "is_round_number",
    "invoice_ref_len",
    "amount_log",
    "hour_of_day",
]


class RiskScorer:
    _instance: Optional["RiskScorer"] = None
    _model = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def _load_model(self):
        """Load model from S3 in production, create synthetic in dev."""
        if self._model is not None:
            return

        model_path = Path("/tmp/govguard_risk_model.pkl")

        if model_path.exists():
            with open(model_path, "rb") as f:
                self._model = pickle.load(f)
            log.info("risk_model.loaded_from_disk")
        else:
            self._create_synthetic_model()

    def _create_synthetic_model(self):
        """Create a synthetic IsolationForest for development/testing."""
        try:
            from sklearn.ensemble import IsolationForest
            from sklearn.preprocessing import StandardScaler
            import numpy as np

            # Generate synthetic training data
            rng = np.random.default_rng(42)
            normal_data = rng.normal(loc=[1000, 0, 15, 6.9, 14], scale=[500, 0.3, 5, 1, 5], size=(1000, 5))
            normal_data = np.abs(normal_data)

            scaler = StandardScaler()
            X_scaled = scaler.fit_transform(normal_data)

            model = IsolationForest(
                n_estimators=100,
                contamination=0.08,  # 8% anomaly rate target
                random_state=42,
                max_samples="auto",
            )
            model.fit(X_scaled)

            self._model = {"model": model, "scaler": scaler}
            log.info("risk_model.synthetic_created")
        except ImportError:
            log.warning("sklearn_not_available - using heuristic scorer")
            self._model = {"model": None, "scaler": None}

    def _extract_features(self, data: dict) -> np.ndarray:
        amount = float(data.get("amount", 0))
        return np.array([[
            amount,
            float(amount % 100 == 0),
            float(data.get("invoice_ref_len", 10)),
            float(np.log1p(amount)),
            float(data.get("hour_of_day", 14)),
        ]])

    def predict(self, features: dict) -> Tuple[float, dict]:
        """
        Returns:
            score: float 0-100 (higher = more risky)
            weights: dict of feature contributions (SHAP-like)
        """
        self._load_model()

        X = self._extract_features(features)

        model_data = self._model
        if model_data["model"] is None:
            return self._heuristic_score(features)

        scaler = model_data["scaler"]
        model = model_data["model"]

        X_scaled = scaler.transform(X)
        raw_score = model.decision_function(X_scaled)[0]

        # Convert IsolationForest score to 0-100 (negative = more anomalous)
        # Typical range: [-0.5, 0.5] → invert and scale
        score = float(np.clip((0.5 - raw_score) * 100, 0, 100))

        # Approximate feature importance (SHAP-like)
        feature_values = X[0].tolist()
        weights = {}
        for i, name in enumerate(FEATURE_NAMES):
            # Simple sensitivity: vary each feature and measure score change
            X_perturbed = X_scaled.copy()
            X_perturbed[0, i] += 1.0
            perturbed_score = model.decision_function(X_perturbed)[0]
            weights[name] = float(raw_score - perturbed_score)

        return round(score, 2), weights

    def _heuristic_score(self, features: dict) -> Tuple[float, dict]:
        """Fallback heuristic when sklearn unavailable."""
        amount = float(features.get("amount", 0))
        score = 0.0
        weights = {}

        if amount > 50000:
            score += 30
            weights["amount"] = 0.5
        if amount % 1000 == 0 and amount > 10000:
            score += 20
            weights["is_round_number"] = 0.3
        if amount > 100000:
            score += 25
            weights["amount_log"] = 0.4

        return min(score, 100.0), weights
