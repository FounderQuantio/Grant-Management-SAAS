"""GovGuard™ — Pre-Award Screening Module"""
import hashlib
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from core.auth import require_role, UserContext
from core.db import get_db, set_tenant
from core.models import Vendor
from services.entity_intelligence.graph import EntityIntelligenceService

router = APIRouter()
_graph_svc = EntityIntelligenceService()


class ScreenRequest(BaseModel):
    applicant_name: str
    ein: str
    address: str
    budget_json: dict = {}


@router.post("/screen")
async def screen_applicant(
    data: ScreenRequest,
    user: UserContext = Depends(require_role("agency_officer")),
    db: AsyncSession = Depends(get_db),
):
    await set_tenant(db, str(user.tenant_id))

    ein_hash = hashlib.sha256(data.ein.encode()).hexdigest()

    # Direct EIN-hash match against known vendors (SAM exclusion / DNP check)
    result = await db.execute(
        select(Vendor).where(Vendor.tenant_id == user.tenant_id, Vendor.ein_hash == ein_hash)
    )
    exact_match = result.scalar_one_or_none()

    # Fuzzy name match for potential duplicate applicants
    name_result = await db.execute(
        select(Vendor).where(
            Vendor.tenant_id == user.tenant_id,
            Vendor.name.ilike(f"%{data.applicant_name.strip()}%"),
        )
    )
    name_matches = [v for v in name_result.scalars().all() if not exact_match or v.id != exact_match.id]

    dnp_match = bool(exact_match and exact_match.sam_status in ("excluded", "suspended"))

    dedup_matches = []
    if exact_match and not dnp_match:
        dedup_matches.append({
            "id": str(exact_match.id), "name": exact_match.name,
            "risk_score": float(exact_match.risk_score or 0),
        })
    for v in name_matches[:5]:
        dedup_matches.append({"id": str(v.id), "name": v.name, "risk_score": float(v.risk_score or 0)})

    # Network risk via the entity-relationship graph, if the applicant matches a known vendor
    network_risk = 0.0
    if exact_match:
        all_vendors = await db.execute(select(Vendor).where(Vendor.tenant_id == user.tenant_id))
        vendors_list = [
            {"id": v.id, "ein_hash": v.ein_hash, "name": v.name,
             "risk_score": float(v.risk_score or 0), "sam_status": v.sam_status}
            for v in all_vendors.scalars().all()
        ]
        links_result = await db.execute(
            text("SELECT source_vendor_id, target_vendor_id, link_type, confidence FROM entity_links WHERE tenant_id = :tid"),
            {"tid": str(user.tenant_id)},
        )
        links_list = [
            {"source_vendor_id": str(r.source_vendor_id), "target_vendor_id": str(r.target_vendor_id),
             "link_type": r.link_type, "confidence": float(r.confidence)}
            for r in links_result
        ]
        graph = _graph_svc.build_graph(vendors_list, links_list)
        network_risk = _graph_svc.score_vendor_network_risk(str(exact_match.id), graph)

    base_risk = float(exact_match.risk_score or 0) if exact_match else 0.0
    risk_score = min(100.0, round(
        (90.0 if dnp_match else 0.0) + base_risk * 0.4 + network_risk * 0.3 + (15.0 if dedup_matches else 0.0),
        1,
    ))

    budget_flags = []
    if not data.budget_json:
        budget_flags.append("No itemized budget submitted with application — cost-category review required before award.")

    recommendation = (
        "BLOCK_INELIGIBLE" if dnp_match else
        "MANUAL_REVIEW" if risk_score >= 40 else
        "APPROVE_STANDARD"
    )

    return {
        "risk_score": risk_score,
        "dnp_match": dnp_match,
        "dedup_matches": dedup_matches,
        "budget_flags": budget_flags,
        "recommendation": recommendation,
    }
