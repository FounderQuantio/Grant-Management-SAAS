"""
GovGuard v2 — Anomaly Detection Unit Tests
File: tests/gao/unit/test_anomaly_processor.py

GAO Alignment: Cat1-Ex3, Cat3-Ex23, Cat4-Ex15
"""
import pytest
from datetime import date, timedelta
from services.anomaly_detection.processor import AnomalyDetectionProcessor, ANOMALY_SPEND_VELOCITY, ANOMALY_BURNRATE_SPIKE

PROC = AnomalyDetectionProcessor()
GRANT_ID = "grant-test-123"
TENANT_ID = "tenant-test-456"

def tx(amount, days_ago=0, vendor_id="v1", cat="personnel"):
    d = date.today() - timedelta(days=days_ago)
    return {"amount": amount, "tx_date": d, "vendor_id": vendor_id, "cost_category": cat}


class TestSpendVelocityAnomaly:
    """GAO Cat1-Ex3 / Cat3-Ex23."""

    def test_velocity_spike_triggers_warning(self):
        history = [tx(10000, d) for d in range(7, 84, 7)]  # 11 weeks normal
        current = tx(80000, 0)  # This week: massive spike
        alerts = PROC.detect(
            grant_id=GRANT_ID, tenant_id=TENANT_ID,
            current_tx=current, historical_txns=history,
            grant_budget={"personnel": 500000}, grant_total_amount=500000,
        )
        vel_alerts = [a for a in alerts if a.anomaly_type == ANOMALY_SPEND_VELOCITY]
        assert len(vel_alerts) > 0
        assert vel_alerts[0].severity in ("WARNING", "CRITICAL")

    def test_normal_velocity_no_alert(self):
        history = [tx(10000, d) for d in range(7, 84, 7)]
        current = tx(11000, 0)  # Slightly above normal — OK
        alerts = PROC.detect(
            grant_id=GRANT_ID, tenant_id=TENANT_ID,
            current_tx=current, historical_txns=history,
            grant_budget={"personnel": 500000}, grant_total_amount=500000,
        )
        vel_alerts = [a for a in alerts if a.anomaly_type == ANOMALY_SPEND_VELOCITY]
        assert len(vel_alerts) == 0


class TestBurnrateSpike:
    """GAO Cat4-Ex15 / Cat3-Ex15."""

    def test_burnrate_spike_triggers_critical(self):
        # 75% of $100k budget consumed in 30 days → CRITICAL
        history = [tx(5000, d) for d in range(1, 30)]
        current = tx(20000, 0)
        alerts = PROC.detect(
            grant_id=GRANT_ID, tenant_id=TENANT_ID,
            current_tx=current, historical_txns=history,
            grant_budget={"personnel": 100000}, grant_total_amount=100000,
        )
        burn_alerts = [a for a in alerts if a.anomaly_type == ANOMALY_BURNRATE_SPIKE]
        assert len(burn_alerts) > 0
        assert burn_alerts[0].auto_action in ("FLAG_REVIEW", "HOLD_PAYMENTS")

    def test_alert_has_gao_reference(self):
        history = [tx(5000, d) for d in range(1, 30)]
        current = tx(20000, 0)
        alerts = PROC.detect(
            grant_id=GRANT_ID, tenant_id=TENANT_ID,
            current_tx=current, historical_txns=history,
            grant_budget={"personnel": 100000}, grant_total_amount=100000,
        )
        for a in alerts:
            if a.anomaly_type == ANOMALY_BURNRATE_SPIKE:
                assert "GAO" in (a.gao_reference or "")
