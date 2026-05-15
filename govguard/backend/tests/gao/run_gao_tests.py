#!/usr/bin/env python3
"""
GovGuard v2 — GAO Test Runner
File: tests/gao/run_gao_tests.py

Single-command execution of all GAO-mapped tests.
CI-ready: outputs structured JSON results + console summary.

Usage:
    python tests/gao/run_gao_tests.py
    python tests/gao/run_gao_tests.py --verbose
    python tests/gao/run_gao_tests.py --json-output results.json
"""
import sys
import json
import time
import subprocess
import argparse
from datetime import datetime


GAO_TEST_MODULES = [
    ("Unit: Fraud Engine",           "tests/gao/unit/test_fraud_engine.py"),
    ("Unit: Anomaly Processor",      "tests/gao/unit/test_anomaly_processor.py"),
    ("Integration: v2 Pipeline",     "tests/gao/integration/test_v2_pipeline.py"),
    ("Integration: Dataset Scenarios","tests/gao/integration/test_dataset_scenarios.py"),
    ("E2E: GAO Scenarios",           "tests/gao/e2e/test_gao_scenarios.py"),
    ("AI Validation: Model Tests",   "tests/gao/ai_validation/test_model_validation.py"),
]

GAO_COVERAGE_MAP = {
    "tests/gao/unit/test_fraud_engine.py": [
        "GAO Cat1-Ex10 — Duplicate Vendor Payments",
        "GAO Cat5-Ex4  — SAM.gov Exclusion Checks",
        "GAO Cat1-Ex23 — P-Card Split Purchase",
        "GAO Cat1-Ex27 — Grant Double-Dipping",
        "GAO Cat1-Ex11 — Ghost Vendor Detection",
        "GAO Cat1-Ex3  — Velocity Detection",
    ],
    "tests/gao/unit/test_anomaly_processor.py": [
        "GAO Cat1-Ex3  — UI Fraud Velocity",
        "GAO Cat3-Ex23 — Continuous Grant Monitoring",
        "GAO Cat4-Ex15 — HHS Grant Compliance",
    ],
    "tests/gao/integration/test_v2_pipeline.py": [
        "GAO Cat5-Ex22 — Federated Invoice Anomaly",
        "GAO Cat3-Ex22 — Antifraud Playbook",
        "GAO Cat2-Ex23 — Grant Compliance System",
    ],
    "tests/gao/integration/test_dataset_scenarios.py": [
        "GAO Dataset — 70-scenario parametrized suite (M1–M6)",
        "GAO Cat1    — Payment Integrity (duplicate, ghost vendor, split purchase)",
        "GAO Cat2    — Benefit Program Integrity (UI, SNAP, Medicaid, Medicare)",
        "GAO Cat3    — Grant Compliance (budget, cross-grant double charge)",
        "GAO Cat4    — Identity & Entity Integrity (PPP cluster, SAM exclusion)",
        "GAO Cat5    — Revenue / Tax Integrity (ERC, SSDI)",
        "GAO Cat6    — False-positive suppression controls",
    ],
    "tests/gao/e2e/test_gao_scenarios.py": [
        "GAO Cat1-Ex4  — PPP/EIDL Entity Clustering",
        "GAO Cat1-Ex8  — SNAP Trafficking",
        "GAO Cat1-Ex16 — Research Grant Misuse",
        "GAO Cat1-Ex9  — Travel Card Abuse",
        "GAO Cat1-Ex26 — Procurement Collusion",
    ],
    "tests/gao/ai_validation/test_model_validation.py": [
        "NIST AI RMF   — Determinism and Consistency",
        "NIST AI RMF   — Monotonicity / Bias check",
        "GAO Cat5-Ex18 — ML Model Registry standards",
    ],
}


def run_module(name: str, path: str, verbose: bool) -> dict:
    start = time.time()
    args = ["python", "-m", "pytest", path, "-v" if verbose else "-q",
            "--tb=short", "--no-header"]
    result = subprocess.run(args, capture_output=True, text=True)
    elapsed = round(time.time() - start, 2)
    passed = result.returncode == 0
    return {
        "module": name,
        "path": path,
        "passed": passed,
        "elapsed_seconds": elapsed,
        "stdout": result.stdout[-3000:],  # Trim for CI
        "stderr": result.stderr[-500:] if result.stderr else "",
        "gao_coverage": GAO_COVERAGE_MAP.get(path, []),
    }


def main():
    parser = argparse.ArgumentParser(description="GovGuard v2 GAO Test Runner")
    parser.add_argument("--verbose", "-v", action="store_true")
    parser.add_argument("--json-output", metavar="FILE", help="Write JSON results to file")
    args = parser.parse_args()

    print(f"\n{'='*70}")
    print(f"  GovGuard v2 — GAO Test Suite")
    print(f"  Run at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*70}\n")

    results = []
    for name, path in GAO_TEST_MODULES:
        print(f"▶ Running: {name}")
        r = run_module(name, path, args.verbose)
        status = "✅ PASS" if r["passed"] else "❌ FAIL"
        print(f"  {status}  ({r['elapsed_seconds']}s)")
        if not r["passed"] and not args.verbose:
            print(f"  Output:
{r['stdout'][-500:]}")
        print()
        results.append(r)

    total = len(results)
    passed_count = sum(1 for r in results if r["passed"])
    failed_count = total - passed_count

    print(f"{'='*70}")
    print(f"  RESULTS: {passed_count}/{total} modules passed")
    print(f"{'='*70}")

    all_gao = []
    for r in results:
        all_gao.extend(r["gao_coverage"])

    print(f"\n  GAO Scenarios Covered ({len(all_gao)}):")
    for ref in all_gao:
        print(f"    ✓ {ref}")

    if args.json_output:
        with open(args.json_output, "w") as f:
            json.dump({
                "run_at": datetime.now().isoformat(),
                "total": total,
                "passed": passed_count,
                "failed": failed_count,
                "gao_scenarios_covered": len(all_gao),
                "results": results,
            }, f, indent=2)
        print(f"\n  JSON results written to: {args.json_output}")

    sys.exit(0 if failed_count == 0 else 1)


if __name__ == "__main__":
    main()
