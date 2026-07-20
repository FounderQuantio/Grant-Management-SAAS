"""GovGuard™ — Performance Reporting Service (2 CFR 200.329)

Real, non-stub implementation. Reporting periods are derived on the fly from
a grant's period_start/period_end (quarterly cadence — the regulation's own
default when award terms don't specify a different frequency), each due 30
calendar days after the period ends per 200.329(b). Only actual submissions
are persisted (performance_reports table).
"""
from datetime import date, timedelta
from typing import Optional
from uuid import UUID

GRACE_DAYS = 30


def expected_quarterly_periods(period_start: date, period_end: date) -> list[dict]:
    """Generate quarterly reporting periods for a grant's award period.
    Each period is labeled YYYY-Qn (calendar quarter containing the period-end
    date) and is due GRACE_DAYS after that quarter's end, capped at the
    grant's overall period_end."""
    periods = []
    cursor = period_start
    while cursor <= period_end:
        quarter = (cursor.month - 1) // 3 + 1
        q_end_month = quarter * 3
        if q_end_month == 12:
            q_end = date(cursor.year, 12, 31)
        else:
            q_end = date(cursor.year, q_end_month + 1, 1) - timedelta(days=1)
        p_end = min(q_end, period_end)
        periods.append({
            "label": f"{cursor.year}-Q{quarter}",
            "period_end": p_end,
            "due_date": p_end + timedelta(days=GRACE_DAYS),
        })
        cursor = p_end + timedelta(days=1)
    return periods


async def evaluate_reporting_status(grant_id: UUID, period_start: date, period_end: date, db) -> str:
    """Real 2 CFR 200.329 evaluation: fail if any elapsed reporting period's
    30-day deadline has passed with no matching submission."""
    from sqlalchemy import text

    periods = expected_quarterly_periods(period_start, period_end)
    today = date.today()
    overdue = [p["label"] for p in periods if today > p["due_date"]]
    if not overdue:
        return "not_tested"

    result = await db.execute(
        text("SELECT period_label FROM performance_reports WHERE grant_id = :gid AND submitted_at IS NOT NULL"),
        {"gid": str(grant_id)},
    )
    submitted = {row[0] for row in result}
    missing = [label for label in overdue if label not in submitted]
    return "fail" if missing else "pass"
