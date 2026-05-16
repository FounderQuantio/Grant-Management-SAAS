"""
GovGuard v2 — GAO Scenario Seeder
===================================
Reads the 70-scenario GAO test dataset and inserts rows into Neon PostgreSQL.

Inserts (idempotent — safe to run multiple times):
  vendors          → one row per unique vendor extracted from each scenario
  grants           → one row per scenario  (award_number = test_case_id)
  transactions     → one row per scenario
  risk_score_logs  → one row per scenario  (stores expected risk score)

Usage:
    export DATABASE_URL="postgresql://user:pass@ep-xxx.neon.tech/neondb?sslmode=require"
    python scripts/seed_gao_scenarios.py
"""
from __future__ import annotations

import json
import os
import sys
import uuid
from datetime import date, timedelta
from pathlib import Path

# ── resolve project root so we can import testkit field extractors ────────────
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tests.gao.testkit import (
    _amount, _vendor_id, _invoice_ref, _sam_status,
    _risk_tier, _cost_category, _grant_budget,
)

# ── constants ─────────────────────────────────────────────────────────────────
TENANT_ID   = "00000000-0000-0000-0000-000000000001"   # from seed.sql
DATASET_PATH = ROOT / "tests/fixtures/gao/govguard_v2_gao_test_dataset.json"
ENGINE_VERSION = "v2.0.0-rules"


def load_scenarios() -> list[dict]:
    with open(DATASET_PATH) as f:
        data = json.load(f)
    return data["scenarios"] if isinstance(data, dict) else data


def ensure_vendor(cur, tenant_id: str, vendor_ext_id: str, sam: str, risk: str) -> str:
    """Insert vendor if not already present; return its UUID."""
    import hashlib
    ein_hash = hashlib.sha256(vendor_ext_id.encode()).hexdigest()

    cur.execute(
        "SELECT id FROM vendors WHERE tenant_id = %s AND ein_hash = %s",
        (tenant_id, ein_hash),
    )
    row = cur.fetchone()
    if row:
        return str(row[0])

    vid = str(uuid.uuid4())
    cur.execute(
        """
        INSERT INTO vendors (id, tenant_id, ein_hash, name, sam_status, risk_tier)
        VALUES (%s, %s, %s, %s, %s, %s)
        """,
        (vid, tenant_id, ein_hash, vendor_ext_id[:255], sam, risk),
    )
    return vid


def ensure_grant(cur, tenant_id: str, award_number: str,
                 agency: str, amount: float, budget: dict,
                 period_start: date, period_end: date) -> str:
    """Insert grant if not already present; return its UUID."""
    cur.execute(
        "SELECT id FROM grants WHERE tenant_id = %s AND award_number = %s",
        (tenant_id, award_number),
    )
    row = cur.fetchone()
    if row:
        return str(row[0])

    gid = str(uuid.uuid4())
    cur.execute(
        """
        INSERT INTO grants
            (id, tenant_id, award_number, agency, total_amount, budget_json,
             period_start, period_end, status)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'active')
        """,
        (
            gid, tenant_id, award_number, agency[:100],
            round(amount, 2), json.dumps(budget),
            period_start, period_end,
        ),
    )
    return gid


def ensure_transaction(cur, tenant_id: str, grant_id: str, vendor_id: str,
                        amount: float, invoice_ref: str, cost_category: str,
                        tx_date: date, risk_score: float) -> str:
    """Insert transaction if not already present; return its UUID."""
    cur.execute(
        """
        SELECT id FROM transactions
        WHERE tenant_id = %s AND invoice_ref = %s AND vendor_id = %s::uuid
        LIMIT 1
        """,
        (tenant_id, invoice_ref[:255], vendor_id),
    )
    row = cur.fetchone()
    if row:
        return str(row[0])

    tid = str(uuid.uuid4())
    cur.execute(
        """
        INSERT INTO transactions
            (id, tenant_id, grant_id, vendor_id, amount, invoice_ref,
             cost_category, tx_date, risk_score, flag_status)
        VALUES (%s, %s, %s::uuid, %s::uuid, %s, %s, %s, %s, %s, %s)
        """,
        (
            tid, tenant_id, grant_id, vendor_id,
            round(amount, 2), invoice_ref[:255],
            cost_category[:100], tx_date,
            round(risk_score, 2),
            "flagged" if risk_score > 0.25 else "clear",
        ),
    )
    return tid


def ensure_risk_log(cur, transaction_id: str, tenant_id: str,
                    risk_score: float, feature_weights: dict) -> None:
    cur.execute(
        "SELECT id FROM risk_score_logs WHERE transaction_id = %s LIMIT 1",
        (transaction_id,),
    )
    if cur.fetchone():
        return

    cur.execute(
        """
        INSERT INTO risk_score_logs
            (transaction_id, tenant_id, model_version, score, feature_weights_json)
        VALUES (%s, %s, %s, %s, %s)
        """,
        (
            transaction_id, tenant_id, ENGINE_VERSION,
            round(risk_score * 100, 2),
            json.dumps(feature_weights),
        ),
    )


def seed(database_url: str) -> None:
    import psycopg2

    scenarios = load_scenarios()
    print(f"Loaded {len(scenarios)} scenarios from {DATASET_PATH.name}")

    conn = psycopg2.connect(database_url)
    conn.autocommit = False
    cur = conn.cursor()

    inserted = skipped = 0
    period_start = date(2025, 10, 1)
    period_end   = date(2026, 9, 30)
    tx_base_date = date(2026, 1, 15)

    for i, scenario in enumerate(scenarios):
        tc_id      = scenario["test_case_id"]           # e.g. "GG-TC-007"
        inp        = scenario.get("synthetic_input_data", {})
        expected   = scenario.get("expected_output", {})
        gao_ref    = scenario.get("gao_reference", "GAO")
        agency     = (gao_ref if isinstance(gao_ref, str) else ", ".join(gao_ref))[:100]

        # Field extraction (same logic as testkit.py)
        amt        = _amount(inp)
        vid_ext    = _vendor_id(inp)
        inv_ref    = f"{tc_id}-{_invoice_ref(inp)}"[:255]
        sam        = _sam_status(inp)
        risk       = _risk_tier(inp)
        cat        = _cost_category(inp)
        budget     = _grant_budget(inp, amt)
        raw_score  = expected.get("risk_score", 0.5)
        try:
            risk_score = float(raw_score)
        except (ValueError, TypeError):
            risk_score = 0.0
        tx_date    = tx_base_date + timedelta(days=i)

        try:
            vendor_id = ensure_vendor(cur, TENANT_ID, vid_ext, sam, risk)
            grant_id  = ensure_grant(
                cur, TENANT_ID, tc_id, agency, amt, budget, period_start, period_end
            )
            tx_id = ensure_transaction(
                cur, TENANT_ID, grant_id, vendor_id,
                amt, inv_ref, cat, tx_date, risk_score,
            )
            ensure_risk_log(
                cur, tx_id, TENANT_ID, risk_score,
                {"alert_type": expected.get("alert_type", ""), "source": "gao_dataset"},
            )
            inserted += 1
            print(f"  ✓ {tc_id} — {expected.get('alert_type','?')}")

        except Exception as e:
            conn.rollback()
            print(f"  ✗ {tc_id} — ERROR: {e}")
            skipped += 1
            conn.autocommit = False
            continue

        conn.commit()

    cur.close()
    conn.close()

    print(f"\nDone. {inserted} inserted, {skipped} skipped.")


if __name__ == "__main__":
    url = os.environ.get("DATABASE_URL")
    if not url:
        print("ERROR: set DATABASE_URL environment variable first.")
        print("  export DATABASE_URL='postgresql://user:pass@ep-xxx.neon.tech/neondb?sslmode=require'")
        sys.exit(1)
    seed(url)
