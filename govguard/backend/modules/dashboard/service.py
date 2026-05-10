"""GovGuard™ — Dashboard Service"""
from decimal import Decimal
from typing import Optional
from uuid import UUID
import uuid as uuid_mod

import structlog
from sqlalchemy import select, func, and_, text
from sqlalchemy.ext.asyncio import AsyncSession

from core.cache import cache_get, cache_set
from core.models import Transaction, ComplianceControl, AuditFinding

log = structlog.get_logger()


class DashboardService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_kpis(self, tenant_id: UUID, period_days: int = 30) -> dict:
        cache_key = f"kpis:{tenant_id}:{period_days}"
        cached = await cache_get(cache_key)
        if cached:
            return cached

        # Compliance score average
        cs_result = await self.db.execute(
            text("""
                SELECT AVG(compliance_score)
                FROM grants
                WHERE tenant_id = :tid AND status = 'active' AND compliance_score IS NOT NULL
            """),
            {"tid": str(tenant_id)},
        )
        avg_compliance = float(cs_result.scalar() or 0)

        # Open findings count
        findings_result = await self.db.execute(
            text("SELECT COUNT(*) FROM audit_findings WHERE tenant_id = :tid AND status = 'open'"),
            {"tid": str(tenant_id)},
        )
        open_findings = int(findings_result.scalar() or 0)

        # Flagged transaction count (last N days)
        flagged_result = await self.db.execute(
            text("""
                SELECT COUNT(*) FROM transactions
                WHERE tenant_id = :tid
                  AND flag_status NOT IN ('approved', 'rejected')
                  AND created_at > NOW() - INTERVAL '1 day' * :days
            """),
            {"tid": str(tenant_id), "days": period_days},
        )
        flagged_count = int(flagged_result.scalar() or 0)

        # Improper payment rate estimate
        total_result = await self.db.execute(
            text("""
                SELECT COUNT(*) FROM transactions
                WHERE tenant_id = :tid
                  AND created_at > NOW() - INTERVAL '1 day' * :days
            """),
            {"tid": str(tenant_id), "days": period_days},
        )
        total_tx = int(total_result.scalar() or 0)
        improper_rate = round((flagged_count / total_tx * 100) if total_tx > 0 else 0, 2)

        # Risk leaderboard: top 5 grants by compliance score (ascending = worst first)
        leaderboard_result = await self.db.execute(
            text("""
                SELECT id, award_number, agency, compliance_score
                FROM grants
                WHERE tenant_id = :tid AND status = 'active'
                ORDER BY compliance_score ASC NULLS LAST
                LIMIT 10
            """),
            {"tid": str(tenant_id)},
        )
        leaderboard = [
            {
                "grant_id": str(row.id),
                "award_number": row.award_number,
                "agency": row.agency,
                "compliance_score": float(row.compliance_score or 0),
            }
            for row in leaderboard_result
        ]

        kpis = {
            "improper_payment_rate": improper_rate,
            "compliance_score": round(avg_compliance, 2),
            "open_findings": open_findings,
            "flagged_tx_count": flagged_count,
            "total_tx_count": total_tx,
            "risk_leaderboard": leaderboard,
            "period_days": period_days,
        }
        await cache_set(cache_key, kpis, ttl=300)
        return kpis

    async def get_heatmap(self, tenant_id: UUID, grant_id: Optional[UUID] = None, group_by: str = "category") -> dict:
        cache_key = f"heatmap:{tenant_id}:{grant_id}:{group_by}"
        cached = await cache_get(cache_key)
        if cached:
            return cached

        where = "tenant_id = :tid"
        params = {"tid": str(tenant_id)}
        if grant_id:
            where += " AND grant_id = :gid"
            params["gid"] = str(grant_id)

        result = await self.db.execute(
            text(f"""
                SELECT cost_category, SUM(amount) as spend, COUNT(*) as tx_count
                FROM transactions
                WHERE {where}
                GROUP BY cost_category
                ORDER BY spend DESC
            """),
            params,
        )

        cells = [
            {"category": row.cost_category, "spend": float(row.spend), "budget": 0.0, "variance": 0.0, "tx_count": row.tx_count}
            for row in result
        ]
        data = {"cells": cells}
        await cache_set(cache_key, data, ttl=300)
        return data

    async def get_alerts(self, tenant_id: UUID, limit: int = 50, since: Optional[str] = None) -> dict:
        result = await self.db.execute(
            text("""
                SELECT id, tenant_id, 'FRAUD_FLAG' as type, 'warning' as severity,
                       created_at, 'transaction' as resource_type, id::text as resource_id
                FROM transactions
                WHERE tenant_id = :tid
                  AND flag_status NOT IN ('approved', 'rejected')
                  AND risk_score >= 75
                ORDER BY created_at DESC
                LIMIT :limit
            """),
            {"tid": str(tenant_id), "limit": limit},
        )
        alerts = [
            {
                "id": str(row.id),
                "type": row.type,
                "severity": row.severity,
                "created_at": row.created_at.isoformat() if row.created_at else None,
                "resource": {"type": row.resource_type, "id": row.resource_id},
            }
            for row in result
        ]
        return {"alerts": alerts}

    async def get_ws_token(self, tenant_id: UUID, user_id: UUID) -> dict:
        """Generate a short-lived WebSocket token."""
        import hashlib
        import time
        from core.cache import cache_set
        from core.config import settings

        token = hashlib.sha256(f"{tenant_id}:{user_id}:{time.time()}".encode()).hexdigest()
        await cache_set(f"wst:{token}", {"tenant_id": str(tenant_id), "user_id": str(user_id)}, ttl=300)
        return {
            "ws_token": token,
            "endpoint": f"wss://api.govguard.gov/v1/ws",
            "expires_in": 300,
        }
