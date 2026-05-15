"""
GovGuard v2 — Shared pytest fixtures
File: tests/gao/conftest.py
"""
import pytest
from datetime import date, timedelta


@pytest.fixture
def sample_transaction():
    return {
        "id": "tx-fixture-001",
        "amount": 25000.0,
        "vendor_id": "vendor-fixture-001",
        "invoice_ref": "INV-FIXTURE-001",
        "tx_date": date.today(),
        "cost_category": "personnel",
        "flag_status": "pending",
    }


@pytest.fixture
def sample_grant():
    return {
        "id": "grant-fixture-001",
        "award_number": "TEST-2024-001",
        "agency": "Test Federal Agency",
        "total_amount": 500000.0,
        "budget_json": {"personnel": 350000, "travel": 50000, "equipment": 100000},
        "status": "active",
        "period_end": (date.today() + timedelta(days=365)).isoformat(),
        "compliance_score": 78.0,
    }


@pytest.fixture
def sample_vendor_active():
    return {"id": "vendor-fixture-001", "ein_hash": "abc123hash", "name": "Test Services LLC", "sam_status": "active", "risk_tier": "low", "risk_score": 15.0}


@pytest.fixture
def sample_vendor_excluded():
    return {"id": "vendor-excl-001", "ein_hash": "excl123hash", "name": "Excluded Corp", "sam_status": "excluded", "risk_tier": "high", "risk_score": 95.0}


@pytest.fixture
def transaction_history_30d():
    return [
        {"id": f"tx-hist-{i}", "invoice_ref": f"INV-H-{i}", "amount": 8000.0 + i * 100,
         "vendor_id": "vendor-fixture-001", "tx_date": date.today() - timedelta(days=i),
         "cost_category": "personnel", "flag_status": "approved"}
        for i in range(1, 20)
    ]
