"""
GovGuard™ — Fraud Model Drift Monitor
======================================
Uses Population Stability Index (PSI) to detect when the distribution of
fraud scores has shifted significantly from the baseline.

PSI < 0.10  → stable     (no action needed)
PSI 0.10–0.25 → warning  (investigate; schedule retrain)
PSI > 0.25  → critical   (retrain immediately)

Reference: PSI is standard in credit risk model monitoring.
"""
from __future__ import annotations

import math
from typing import Optional

import structlog

log = structlog.get_logger()

N_BUCKETS = 10          # 10-point buckets: [0,10), [10,20), ..., [90,100]
PSI_WARNING  = 0.10
PSI_CRITICAL = 0.25
MIN_SAMPLES  = 30       # minimum assessments required for a meaningful report


def _bucketize(scores: list[float]) -> list[float]:
    """
    Return normalized fraction of scores in each 10-point bucket.
    Uses Laplace smoothing (0.5/n per bucket) to prevent log(0) without
    distorting ratios the way a fixed 1e-6 epsilon would.
    """
    n = len(scores)
    if n == 0:
        return [1.0 / N_BUCKETS] * N_BUCKETS
    eps = 0.5 / n
    counts = [0] * N_BUCKETS
    for s in scores:
        idx = min(int(s / 10), N_BUCKETS - 1)
        counts[idx] += 1
    fracs = [(c / n) + eps for c in counts]
    total = sum(fracs)
    return [f / total for f in fracs]


def compute_psi(baseline: list[float], current: list[float]) -> float:
    """Population Stability Index: Σ (cur - base) × ln(cur / base)."""
    return round(sum((c - b) * math.log(c / b) for b, c in zip(baseline, current)), 4)


def check_drift(
    baseline_scores: list[float],
    recent_scores: list[float],
) -> dict:
    """
    Compare two sets of fraud composite scores (0–100) and return a drift report.

    baseline_scores: historical assessments (used as reference distribution)
    recent_scores:   latest assessments (compared against baseline)
    """
    if len(baseline_scores) < MIN_SAMPLES:
        return {
            "status": "insufficient_baseline",
            "psi": None,
            "message": f"Need at least {MIN_SAMPLES} baseline assessments, have {len(baseline_scores)}",
            "baseline_n": len(baseline_scores),
            "recent_n": len(recent_scores),
        }
    if len(recent_scores) < MIN_SAMPLES:
        return {
            "status": "insufficient_recent",
            "psi": None,
            "message": f"Need at least {MIN_SAMPLES} recent assessments, have {len(recent_scores)}",
            "baseline_n": len(baseline_scores),
            "recent_n": len(recent_scores),
        }

    bucket_labels = [f"{i * 10}-{i * 10 + 10}" for i in range(N_BUCKETS)]
    base_fracs = _bucketize(baseline_scores)
    curr_fracs = _bucketize(recent_scores)
    psi = compute_psi(base_fracs, curr_fracs)

    if psi < PSI_WARNING:
        status = "stable"
    elif psi < PSI_CRITICAL:
        status = "warning"
    else:
        status = "critical"

    return {
        "psi": psi,
        "status": status,
        "baseline_n": len(baseline_scores),
        "recent_n": len(recent_scores),
        "bucket_labels": bucket_labels,
        "baseline_distribution": [round(f, 4) for f in base_fracs],
        "current_distribution": [round(f, 4) for f in curr_fracs],
        "interpretation": {
            "stable":               "PSI < 0.10 — model distribution unchanged",
            "warning":              "PSI 0.10–0.25 — slight shift, monitor closely",
            "critical":             "PSI > 0.25 — significant drift, retrain recommended",
            "insufficient_baseline": "Not enough historical data to compare against",
            "insufficient_recent":  "Not enough recent data to detect drift",
        }[status],
    }
