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
    """2 CFR 200.302 - Financial Management standards."""
    # In production: check ERP integration status, GL account structure, etc.
    if grant is None:
        return "not_applicable"
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
    """2 CFR 200.328-329 - Performance reporting."""
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
