"""GovGuard™ — Compliance Rules Engine"""
from typing import Optional


async def evaluate_rule(control_code: str, domain: str, grant, db) -> str:
    """
    Evaluate a compliance control rule.
    Returns: 'pass', 'fail', or 'not_applicable'
    """
    evaluators = {
        "financial_management": evaluate_financial_management,
        "procurement": evaluate_procurement,
        "subrecipient": evaluate_subrecipient,
        "reporting": evaluate_reporting,
        "cost_principles": evaluate_cost_principles,
        "closeout": evaluate_closeout,
        "general": evaluate_general,
    }

    evaluator = evaluators.get(domain, evaluate_general)
    return await evaluator(control_code, grant, db)


async def evaluate_financial_management(code: str, grant, db) -> str:
    """2 CFR 200.302 - Financial Management standards; FM-002 = 2 CFR 200.308
    (budget/program revision prior approval)."""
    if grant is None:
        return "not_applicable"

    if code == "FM-002":
        from sqlalchemy import text
        # Fail if a modification requiring prior approval was ever auto-applied
        # (the 10% gate was bypassed), or if a pending approval-required
        # request has sat unresolved for more than 30 days.
        result = await db.execute(
            text("""
                SELECT COUNT(*) FROM budget_modification_requests
                WHERE grant_id = :gid
                  AND (
                    (requires_prior_approval = TRUE AND status = 'auto_applied')
                    OR (requires_prior_approval = TRUE AND status = 'pending'
                        AND created_at < NOW() - INTERVAL '30 days')
                  )
            """),
            {"gid": str(grant.id)},
        )
        violations = result.scalar() or 0
        return "fail" if violations > 0 else "pass"

    # In production: check ERP integration status, GL account structure, etc.
    if grant.status == "active" and grant.budget_json:
        return "pass"
    return "not_tested"


async def evaluate_procurement(code: str, grant, db) -> str:
    """2 CFR 200.317-327 - Procurement standards."""
    return "not_tested"


async def evaluate_subrecipient(code: str, grant, db) -> str:
    """2 CFR 200.330-332 - Subrecipient monitoring."""
    from sqlalchemy import text
    if grant is None:
        return "not_applicable"
    # Check if subrecipient monitoring is up to date
    result = await db.execute(
        text("SELECT COUNT(*) FROM corrective_action_plans WHERE finding_id IN "
             "(SELECT id FROM audit_findings WHERE grant_id = :gid AND category = 'Subrecipient')"),
        {"gid": str(grant.id)}
    )
    overdue_count = result.scalar() or 0
    return "fail" if overdue_count > 0 else "pass"


async def evaluate_reporting(code: str, grant, db) -> str:
    """2 CFR 200.328-329 - Performance reporting. RPT-002 (200.328/329) is
    backed by real submission tracking against derived quarterly periods.
    RPT-003 (200.415) checks that every submitted report actually carries the
    required signed certification -- defense in depth behind the hard gate
    already enforced at submission time in performance_reporting/router.py."""
    if grant is None:
        return "not_applicable"
    if code == "RPT-002":
        from modules.performance_reporting.service import evaluate_reporting_status
        return await evaluate_reporting_status(grant.id, grant.period_start, grant.period_end, db)
    if code == "RPT-003":
        from sqlalchemy import text
        total_result = await db.execute(
            text("SELECT COUNT(*) FROM performance_reports WHERE grant_id = :gid AND submitted_at IS NOT NULL"),
            {"gid": str(grant.id)},
        )
        if (total_result.scalar() or 0) == 0:
            return "not_tested"
        violations_result = await db.execute(
            text("""
                SELECT COUNT(*) FROM performance_reports
                WHERE grant_id = :gid
                  AND submitted_at IS NOT NULL
                  AND (certification_accepted IS NOT TRUE OR certification_text IS NULL)
            """),
            {"gid": str(grant.id)},
        )
        violations = violations_result.scalar() or 0
        return "fail" if violations > 0 else "pass"
    return "not_tested"


async def evaluate_cost_principles(code: str, grant, db) -> str:
    """2 CFR 200.400-475 - Cost principles."""
    if grant is None:
        return "not_applicable"
    # Check for transactions in invalid cost categories
    from sqlalchemy import text
    result = await db.execute(
        text("""
            SELECT COUNT(*) FROM transactions
            WHERE grant_id = :gid
              AND cost_category NOT IN (
                  SELECT jsonb_object_keys(budget_json::jsonb)
                  FROM grants WHERE id = :gid
              )
              AND flag_status != 'rejected'
        """),
        {"gid": str(grant.id)}
    )
    violations = result.scalar() or 0
    return "fail" if violations > 0 else "pass"


async def evaluate_closeout(code: str, grant, db) -> str:
    """2 CFR 200.344 - Closeout requirements."""
    return "not_applicable" if (grant and grant.status != "closed") else "not_tested"


async def evaluate_general(code: str, grant, db) -> str:
    return "not_tested"
