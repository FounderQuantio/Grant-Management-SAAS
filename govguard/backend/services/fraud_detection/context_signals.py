"""GovGuard™ — Real context-signal lookups for FDE-011/FDE-012.

Shared across every FraudDetectionEngine.assess() call site so cross-grant
double-charge and related-party detection behave consistently regardless of
which endpoint assesses a transaction. Previously all_grant_charges and
related_party_flag were hardcoded ([] / False) in 2 of the 3 real call sites,
making FDE-012 unreliable (worked only via the transaction-creation path) and
FDE-011 permanently dead everywhere.
"""
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def get_all_grant_charges(
    db: AsyncSession, tenant_id: Any, vendor_id: Any, cost_category: str
) -> list[dict]:
    """Real FDE-012 input: other transactions from the same vendor, same cost
    category, across any grant -- used to detect the same cost charged to
    multiple active grants."""
    result = await db.execute(
        text("""
            SELECT grant_id, cost_category, vendor_id
            FROM transactions
            WHERE tenant_id = :tid AND vendor_id = :vid AND cost_category = :cat
            LIMIT 50
        """),
        {"tid": str(tenant_id), "vid": str(vendor_id), "cat": cost_category},
    )
    return [
        {"grant_id": str(r.grant_id), "cost_category": r.cost_category, "vendor_id": str(r.vendor_id)}
        for r in result
    ]


async def get_related_party_flag(db: AsyncSession, tenant_id: Any, vendor_id: Any) -> bool:
    """Real FDE-011 input: True if this vendor has any entity_links
    relationship (shared EIN, shared address, shared bank reference, or
    synchronized billing pattern) to another vendor in the same tenant --
    reuses the same EntityIntelligenceService graph already relied on for
    pre-award vendor screening (modules/pre_award/router.py)."""
    from services.entity_intelligence.graph import EntityIntelligenceService

    vendors_result = await db.execute(
        text("SELECT id, ein_hash, name, risk_score, sam_status FROM vendors WHERE tenant_id = :tid"),
        {"tid": str(tenant_id)},
    )
    vendors = [dict(r) for r in vendors_result.mappings()]

    links_result = await db.execute(
        text("SELECT source_vendor_id, target_vendor_id, link_type, confidence FROM entity_links WHERE tenant_id = :tid"),
        {"tid": str(tenant_id)},
    )
    links = [dict(r) for r in links_result.mappings()]

    svc = EntityIntelligenceService()
    graph = svc.build_graph(vendors, links)
    related = svc.find_related_entities(str(vendor_id), graph)
    return len(related) > 0
