"""
GovGuard v2 — GAO Dataset-Driven Parametrized Tests
File: tests/gao/integration/test_dataset_scenarios.py

Runs all 70 scenarios from the JSON test dataset through the service layer
using the testkit adapter, following the GAO Test Dataset User Guide.

Usage:
    pytest tests/gao/integration/test_dataset_scenarios.py -v
    pytest tests/gao/integration/test_dataset_scenarios.py -v -k M2
    pytest tests/gao/integration/test_dataset_scenarios.py -v -k "not performance"
"""
import json
import os
import pathlib
import pytest

from tests.gao.testkit import simulate_scenario, evaluate, OUT_OF_SCOPE_ALERT_TYPES

# ── Load dataset ──────────────────────────────────────────────────────────────

_DATASET_PATH = (
    pathlib.Path(__file__).parent.parent.parent
    / "fixtures" / "gao" / "govguard_v2_gao_test_dataset.json"
)

with open(_DATASET_PATH) as _f:
    _DATA = json.load(_f)

_SCENARIOS = _DATA["scenarios"]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _is_performance(scenario: dict) -> bool:
    alert_type = scenario.get("expected_output", {}).get("alert_type", "")
    return alert_type in ("DNP_BATCH_VERDICT", "RECOVERY_QUEUE_PRIORITIZED")


def _is_out_of_scope(scenario: dict) -> bool:
    alert_type = scenario.get("expected_output", {}).get("alert_type", "")
    return alert_type in OUT_OF_SCOPE_ALERT_TYPES


def _feature_ids(scenario: dict) -> list[str]:
    return [f["id"] for f in scenario.get("features_under_test", [])]


# ── Parametrized test ─────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "scenario",
    _SCENARIOS,
    ids=lambda s: s["test_case_id"],
)
def test_gao_scenario(scenario: dict) -> None:
    """
    Evaluates one GAO dataset scenario against the live service layer.

    Performance scenarios (infra-SLA) are auto-skipped with an explanatory
    message — they are outside the scope of unit/integration testing.
    """
    if _is_performance(scenario):
        pytest.skip(
            f"Performance/infra-SLA scenario — not validated here: "
            f"{scenario['expected_output']['alert_type']}"
        )

    if _is_out_of_scope(scenario):
        pytest.skip(
            f"Detection capability outside rule-based engine scope "
            f"({scenario['expected_output']['alert_type']})"
        )

    actual = simulate_scenario(
        inputs=scenario["synthetic_input_data"],
        features=_feature_ids(scenario),
    )
    result = evaluate(actual=actual, expected=scenario["expected_output"])

    assert result.passed, (
        f"\n[{scenario['test_case_id']}] {scenario.get('gao_reference', '')}\n"
        f"  FAIL: {result.diff}\n"
        f"  actual  → score={actual.risk_score:.3f}, action={actual.recommended_action}, "
        f"alert_fired={actual.alert_fired}, alert_type={actual.alert_type}\n"
        f"  expected→ score={scenario['expected_output'].get('risk_score')}, "
        f"action={scenario['expected_output'].get('recommended_action')}, "
        f"alert_type={scenario['expected_output'].get('alert_type')}"
    )


# ── Module-level summary fixture ──────────────────────────────────────────────

@pytest.fixture(scope="session", autouse=True)
def gao_dataset_summary() -> None:
    """Prints a one-line dataset coverage header before the test run."""
    total = len(_SCENARIOS)
    perf = sum(1 for s in _SCENARIOS if _is_performance(s))
    oos = sum(1 for s in _SCENARIOS if _is_out_of_scope(s))
    runnable = total - perf - oos
    print(
        f"\nGAO Dataset: {total} scenarios loaded — "
        f"{runnable} exercised, {oos} skipped (out of scope), "
        f"{perf} skipped (performance/infra-SLA)"
    )
