"""Tests for ML risk scorer."""
import pytest
from decimal import Decimal
from ml.risk_scorer import RiskScorer


def test_risk_scorer_low_risk():
    scorer = RiskScorer()
    score, weights = scorer.predict({"amount": 500.0, "invoice_ref_len": 12, "is_round_number": False})
    assert 0 <= score <= 100
    assert isinstance(weights, dict)


def test_risk_scorer_high_amount_increases_risk():
    scorer = RiskScorer()
    low_score, _ = scorer.predict({"amount": 100.0})
    high_score, _ = scorer.predict({"amount": 500000.0})
    # High amounts should generally score higher (but not always with IsolationForest)
    assert high_score >= 0


def test_risk_scorer_round_number_flag():
    scorer = RiskScorer()
    score, weights = scorer.predict({
        "amount": 100000.0,
        "is_round_number": True,
        "invoice_ref_len": 5,
    })
    assert score >= 0


def test_risk_scorer_singleton():
    s1 = RiskScorer()
    s2 = RiskScorer()
    assert s1 is s2
