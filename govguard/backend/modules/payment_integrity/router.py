"""GovGuard™ — Payment Integrity Module"""
from fastapi import APIRouter, Depends
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from core.auth import get_current_user_or_service as get_current_user, UserContext
from core.db import get_db, set_tenant
from core.models import Vendor

router = APIRouter()


@router.get("/vendors")
async def list_vendors(
    user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await set_tenant(db, str(user.tenant_id))
    result = await db.execute(
        select(Vendor).where(Vendor.tenant_id == user.tenant_id).order_by(Vendor.risk_score.desc().nullslast())
    )
    vendors = result.scalars().all()

    link_result = await db.execute(
        text(
            """
            SELECT el.id, el.source_vendor_id, el.target_vendor_id, el.link_type, el.confidence,
                   sv.name AS source_name, tv.name AS target_name
            FROM entity_links el
            JOIN vendors sv ON sv.id = el.source_vendor_id
            JOIN vendors tv ON tv.id = el.target_vendor_id
            WHERE el.tenant_id = :tid
            ORDER BY el.confidence DESC
            LIMIT 50
            """
        ),
        {"tid": str(user.tenant_id)},
    )
    links = [
        {
            "id": str(r.id),
            "source_vendor_id": str(r.source_vendor_id),
            "target_vendor_id": str(r.target_vendor_id),
            "link_type": r.link_type,
            "confidence": float(r.confidence),
            "source_name": r.source_name,
            "target_name": r.target_name,
        }
        for r in link_result
    ]

    return {
        "vendors": [
            {
                "id": str(v.id),
                "name": v.name,
                "sam_status": v.sam_status,
                "risk_tier": v.risk_tier,
                "risk_score": float(v.risk_score) if v.risk_score is not None else None,
                "sam_checked_at": v.sam_checked_at.isoformat() if v.sam_checked_at else None,
                "created_at": v.created_at.isoformat(),
            }
            for v in vendors
        ],
        "total": len(vendors),
        "duplicate_links": links,
    }
