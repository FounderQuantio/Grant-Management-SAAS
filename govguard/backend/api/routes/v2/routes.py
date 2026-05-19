"""
GovGuard v2 — New API Routes
==============================
NEW FILE: api/routes/v2/routes.py

PATCH REQUIRED IN: backend/main.py (add 3 lines — see PATCH section)
All new endpoints are prefixed /api/v2/ to avoid breaking v1 consumers.
"""
import json as _json
from typing import Optional
from uuid import UUID
from datetime import date
from fastapi import APIRouter, Depends, Query, Body
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text

from core.auth import get_current_user_or_service, UserContext
from core.db import get_db
from core.models import Transaction, Grant, Vendor, FraudAssessmentLog

# v2 services
from services.fraud_detection.engine import FraudDetectionEngine
from services.anomaly_detection.processor import AnomalyDetectionProcessor
from services.compliance_monitor.monitor import GrantComplianceMonitor
from services.entity_intelligence.graph import EntityIntelligenceService
from services.predictive_risk.scorer import PredictiveRiskScorer
from services.internal_controls.automation import InternalControlsAutomation

router = APIRouter()

_fraud_engine = FraudDetectionEngine()
_anomaly_proc = AnomalyDetectionProcessor()
_compliance_mon = GrantComplianceMonitor()
_entity_svc = EntityIntelligenceService()
_risk_scorer = PredictiveRiskScorer()
_controls_auto = InternalControlsAutomation()


# ────────────────────────────────────────────────────────────────────────────
# 1. FRAUD DETECTION ENGINE
# ────────────────────────────────────────────────────────────────────────────

@router.post("/fraud/assess/{tx_id}")
async def assess_fraud(
    tx_id: UUID,
    user: UserContext = Depends(get_current_user_or_service),
    db: AsyncSession = Depends(get_db),
):
    """
    Run full fraud assessment on a transaction.
    Returns composite score, triggered rules, GAO references, recommended action.

    v2 NEW: Multi-rule engine with GAO traceability (replaces simple heuristic scorer)
    """
    # set_tenant skipped — v2 routes filter by tenant_id explicitly in every query

    # Load transaction + context
    result = await db.execute(
        text("""
            SELECT t.*, v.sam_status, v.risk_tier, v.name as vendor_name
            FROM transactions t
            JOIN vendors v ON v.id = t.vendor_id
            WHERE t.id = :tx_id AND t.tenant_id = :tid
        """),
        {"tx_id": str(tx_id), "tid": str(user.tenant_id)},
    )
    row = result.mappings().first()
    if not row:
        return {"error": "Transaction not found"}, 404

    grant = await db.get(Grant, row["grant_id"])
    budget = grant.budget_json if grant else {}

    # Prior invoices (last 30 days, same vendor)
    prior_result = await db.execute(
        text("""
            SELECT id, invoice_ref, amount, vendor_id, tx_date
            FROM transactions
            WHERE tenant_id = :tid AND vendor_id = :vid
              AND created_at > NOW() - INTERVAL '30 days'
              AND id != :tx_id
            LIMIT 50
        """),
        {"tid": str(user.tenant_id), "vid": str(row["vendor_id"]), "tx_id": str(tx_id)},
    )
    prior_invoices = [dict(r) for r in prior_result.mappings()]

    # Vendor 30d spend
    spend_result = await db.execute(
        text("SELECT COALESCE(SUM(amount),0) as total FROM transactions WHERE tenant_id=:tid AND vendor_id=:vid AND created_at > NOW() - INTERVAL '30 days'"),
        {"tid": str(user.tenant_id), "vid": str(row["vendor_id"])},
    )
    vendor_spend_30d = float(spend_result.scalar() or 0)

    assessment = _fraud_engine.assess(
        transaction_id=str(tx_id),
        amount=float(row["amount"]),
        vendor_id=str(row["vendor_id"]),
        vendor_sam_status=row.get("sam_status", "unknown"),
        invoice_ref=row.get("invoice_ref", ""),
        tx_date=row.get("tx_date") or date.today(),
        cost_category=row.get("cost_category", ""),
        grant_budget=budget,
        prior_invoices=prior_invoices,
        vendor_spend_30d=vendor_spend_30d,
        all_grant_charges=[],
        vendor_risk_tier=row.get("risk_tier", "medium"),
        related_party_flag=False,
    )

    # Auto-execute internal controls
    actions = _controls_auto.process_fraud_assessment(assessment.to_dict(), str(user.tenant_id))
    if actions:
        for action in actions:
            if action.action_type in ("PAYMENT_BLOCK", "PAYMENT_HOLD"):
                new_status = action.payload.get("new_flag_status", "flagged")
                reason = action.payload.get("flag_reason", "")
                await db.execute(
                    text("UPDATE transactions SET flag_status=:fs, flag_reason=:fr WHERE id=:id AND tenant_id=:tid"),
                    {"fs": new_status, "fr": reason, "id": str(tx_id), "tid": str(user.tenant_id)},
                )

    # Log to ML training pipeline — best-effort, never blocks the response
    try:
        db.add(FraudAssessmentLog(
            tenant_id=user.tenant_id,
            transaction_id=tx_id,
            composite_score=assessment.composite_score,
            risk_tier=assessment.risk_tier,
            triggered_rules=assessment.triggered_rules,
            recommended_action=assessment.recommended_action,
            gao_references=assessment.gao_references,
            explanation=assessment.explanation,
            signal_detail=[
                {"rule": s.rule_id, "triggered": s.triggered, "weight": s.weight}
                for s in assessment.signals
            ],
            engine_version="v2.0.0",
            scoring_method=assessment.scoring_method,
        ))
    except Exception as _e:
        import structlog as _slog
        _slog.get_logger().warning("fraud_assess.log_error", error=str(_e))

    await db.commit()

    return {
        "assessment": assessment.to_dict(),
        "auto_actions_triggered": [a.action_type for a in actions],
        "version": "v2",
    }


# ────────────────────────────────────────────────────────────────────────────
# 1b. FRAUD LABEL (confirmed outcome for ML training)
# ────────────────────────────────────────────────────────────────────────────

class LabelRequest(BaseModel):
    confirmed_fraud: bool


@router.patch("/fraud/label/{tx_id}")
async def label_fraud(
    tx_id: UUID,
    payload: LabelRequest,
    user: UserContext = Depends(get_current_user_or_service),
    db: AsyncSession = Depends(get_db),
):
    """
    Record a confirmed fraud/not-fraud label on a transaction's latest assessment.
    This is the ground-truth signal used to train the Phase 2 supervised classifier.
    """
    confirmed_fraud = payload.confirmed_fraud

    try:
        result = await db.execute(
            text("""
                UPDATE fraud_assessments
                SET confirmed_label = :label,
                    confirmed_at    = NOW()
                WHERE transaction_id = :tx_id
                  AND tenant_id      = :tid
                  AND id = (
                    SELECT id FROM fraud_assessments
                    WHERE transaction_id = :tx_id AND tenant_id = :tid
                    ORDER BY created_at DESC LIMIT 1
                  )
                RETURNING id
            """),
            {"label": bool(confirmed_fraud), "tx_id": str(tx_id), "tid": str(user.tenant_id)},
        )
        row = result.fetchone()
        if not row:
            return {"error": "No assessment found for this transaction", "tx_id": str(tx_id), "tenant_id": str(user.tenant_id)}

        await db.commit()
        return {"labeled": True, "transaction_id": str(tx_id), "confirmed_fraud": confirmed_fraud}
    except Exception as e:
        await db.rollback()
        return {"error": str(e), "transaction_id": str(tx_id)}


# ────────────────────────────────────────────────────────────────────────────
# 2. ANOMALY DETECTION
# ────────────────────────────────────────────────────────────────────────────

@router.post("/anomaly/detect/{grant_id}")
async def detect_anomalies(
    grant_id: UUID,
    tx_data: dict,              # Current transaction context passed in body
    user: UserContext = Depends(get_current_user_or_service),
    db: AsyncSession = Depends(get_db),
):
    """
    Run anomaly detection against a grant's transaction stream.
    Called after each transaction submission (or on-demand for batch review).

    v2 NEW: 6-detector statistical anomaly engine
    """
    # set_tenant skipped — v2 routes filter by tenant_id explicitly in every query

    grant = await db.get(Grant, grant_id)
    if not grant or str(grant.tenant_id) != str(user.tenant_id):
        return {"error": "Grant not found"}, 404

    history_result = await db.execute(
        text("SELECT * FROM transactions WHERE grant_id=:gid AND tenant_id=:tid ORDER BY tx_date DESC LIMIT 200"),
        {"gid": str(grant_id), "tid": str(user.tenant_id)},
    )
    history = [dict(r) for r in history_result.mappings()]

    alerts, ml_meta = _anomaly_proc.detect(
        grant_id=str(grant_id),
        tenant_id=str(user.tenant_id),
        current_tx=tx_data,
        historical_txns=history,
        grant_budget=grant.budget_json or {},
        grant_total_amount=float(grant.total_amount),
    )

    # Execute any auto-hold actions
    for alert in alerts:
        actions = _controls_auto.process_anomaly_alert(
            {"auto_action": alert.auto_action, "anomaly_type": alert.anomaly_type,
             "severity": alert.severity, "description": alert.description,
             "gao_reference": alert.gao_reference, "grant_id": str(grant_id)},
            str(user.tenant_id),
        )
        if actions:
            _controls_auto.execute_actions(actions)

    ml_used = any(a.anomaly_type == "ML_OUTLIER" for a in alerts)
    return {
        "grant_id": str(grant_id),
        "alert_count": len(alerts),
        "detection_method": "ml_isolation_forest+rules_statistical" if ml_used else "rules_statistical",
        "ml_detector_available": ml_meta["ml_detector_available"],
        "ml_score": ml_meta["ml_score"],
        "ml_flagged": ml_meta["ml_flagged"],
        "alerts": [
            {"alert_id": a.alert_id, "type": a.anomaly_type, "severity": a.severity,
             "score": a.score, "description": a.description, "auto_action": a.auto_action,
             "gao_reference": a.gao_reference, "detection_method": a.detection_method}
            for a in alerts
        ],
        "version": "v2",
    }


# ────────────────────────────────────────────────────────────────────────────
# 3. COMPLIANCE MONITOR
# ────────────────────────────────────────────────────────────────────────────

@router.get("/compliance/monitor/{grant_id}")
async def run_compliance_monitor(
    grant_id: UUID,
    user: UserContext = Depends(get_current_user_or_service),
    db: AsyncSession = Depends(get_db),
):
    """
    Run continuous compliance monitor against a grant.
    Returns violations, auto-triggers CAPs for MATERIAL_WEAKNESS findings.

    v2 NEW: GAO-mapped rule engine with auto-CAP creation
    """
    # set_tenant skipped — v2 routes filter by tenant_id explicitly in every query

    import structlog as _slog
    _log = _slog.get_logger()

    try:
        grant = await db.get(Grant, grant_id)
    except Exception as e:
        _log.error("compliance_monitor.grant_fetch_error", error=str(e))
        return {"error": str(e), "violation_count": 0, "violations": [], "version": "v2"}

    if not grant or str(grant.tenant_id) != str(user.tenant_id):
        return {"error": "Grant not found", "violation_count": 0, "violations": [], "version": "v2"}

    try:
        txns_result = await db.execute(
            text("SELECT * FROM transactions WHERE grant_id=:gid AND tenant_id=:tid LIMIT 500"),
            {"gid": str(grant_id), "tid": str(user.tenant_id)},
        )
        transactions = [dict(r) for r in txns_result.mappings()]

        ctrls_result = await db.execute(
            text("SELECT * FROM compliance_controls WHERE grant_id=:gid AND tenant_id=:tid"),
            {"gid": str(grant_id), "tid": str(user.tenant_id)},
        )
        controls = [dict(r) for r in ctrls_result.mappings()]
    except Exception as e:
        _log.error("compliance_monitor.query_error", error=str(e))
        return {"error": str(e), "violation_count": 0, "violations": [], "version": "v2"}

    days_since = 0
    if grant.activated_at:
        from datetime import datetime, timezone
        try:
            act = grant.activated_at
            if act.tzinfo is None:
                from datetime import timezone as tz
                act = act.replace(tzinfo=tz.utc)
            days_since = (datetime.now(timezone.utc) - act).days
        except Exception:
            days_since = 0

    try:
        violations = _compliance_mon.check_all(
        grant_id=str(grant_id),
        tenant_id=str(user.tenant_id),
        grant={
            "budget_json": grant.budget_json or {},
            "period_end": str(grant.period_end) if grant.period_end else None,
            "status": grant.status,
        },
        transactions=transactions,
        compliance_controls=controls,
        subrecipients=[],
        days_since_activation=days_since,
    )
    except Exception as e:
        _log.error("compliance_monitor.check_error", error=str(e))
        return {"error": str(e), "violation_count": 0, "violations": [], "version": "v2"}

    # Auto-create CAPs for material weaknesses (best-effort — never block violation response)
    auto_caps_created = 0
    for v in violations:
        if v.auto_cap_trigger:
            try:
                await db.execute(text("SAVEPOINT cap_insert"))
                actions = _controls_auto.process_compliance_violation(v.to_dict(), str(user.tenant_id))
                for action in actions:
                    if action.action_type == "AUTO_CAP":
                        payload = action.payload
                        due = payload.get("suggested_due_date") or None
                        await db.execute(
                            text("""
                                INSERT INTO corrective_action_plans
                                  (tenant_id, finding_id, response_text, due_date, status)
                                SELECT :tid, id, :resp, :due, 'open'
                                FROM audit_findings
                                WHERE tenant_id=:tid AND grant_id=:gid AND status='open'
                                LIMIT 1
                            """),
                            {
                                "tid": str(user.tenant_id),
                                "resp": payload.get("recommended_remediation", "Remediate per CAP"),
                                "due": due,
                                "gid": str(grant_id),
                            },
                        )
                        auto_caps_created += 1
                await db.execute(text("RELEASE SAVEPOINT cap_insert"))
            except Exception as e:
                _log.warning("compliance_monitor.cap_error", error=str(e))
                try:
                    await db.execute(text("ROLLBACK TO SAVEPOINT cap_insert"))
                    await db.execute(text("RELEASE SAVEPOINT cap_insert"))
                except Exception:
                    pass
    try:
        await db.commit()
    except Exception as e:
        _log.warning("compliance_monitor.commit_error", error=str(e))
        try:
            await db.rollback()
        except Exception:
            pass

    return {
        "grant_id": str(grant_id),
        "violation_count": len(violations),
        "auto_caps_created": auto_caps_created,
        "violations": [v.to_dict() for v in violations],
        "version": "v2",
    }


# ────────────────────────────────────────────────────────────────────────────
# 4. ENTITY INTELLIGENCE GRAPH
# ────────────────────────────────────────────────────────────────────────────

@router.get("/entity/graph")
async def get_entity_graph(
    user: UserContext = Depends(get_current_user_or_service),
    db: AsyncSession = Depends(get_db),
):
    """
    Return full entity graph for a tenant — nodes, edges, conflicts.

    v2 NEW: Cross-entity financial intelligence with conflict detection
    """
    # set_tenant skipped — v2 routes filter by tenant_id explicitly in every query

    vendors_result = await db.execute(
        text("SELECT * FROM vendors WHERE tenant_id=:tid"),
        {"tid": str(user.tenant_id)},
    )
    vendors = [dict(r) for r in vendors_result.mappings()]

    links_result = await db.execute(
        text("SELECT * FROM entity_links WHERE tenant_id=:tid"),
        {"tid": str(user.tenant_id)},
    )
    entity_links = [dict(r) for r in links_result.mappings()]

    graph = _entity_svc.build_graph(vendors, entity_links)

    return {
        "node_count": len(graph.nodes),
        "edge_count": len(graph.edges),
        "conflict_count": len(graph.conflict_flags),
        "risk_summary": graph.risk_summary,
        "nodes": [{"id": n.entity_id, "name": n.name, "risk_score": n.risk_score, "sam_status": n.sam_status} for n in graph.nodes],
        "edges": [{"source": e.source_id, "target": e.target_id, "type": e.relationship, "confidence": e.confidence} for e in graph.edges],
        "conflict_flags": graph.conflict_flags,
        "version": "v2",
    }


# ────────────────────────────────────────────────────────────────────────────
# 5. PREDICTIVE RISK ANALYTICS
# ────────────────────────────────────────────────────────────────────────────

@router.get("/risk/predict/{grant_id}")
async def predict_grant_risk(
    grant_id: UUID,
    user: UserContext = Depends(get_current_user_or_service),
    db: AsyncSession = Depends(get_db),
):
    """
    30-day forward risk prediction for a grant.

    v2 NEW: Predictive analytics with trend extrapolation + GAO High-Risk overlap
    """
    # set_tenant skipped — v2 routes filter by tenant_id explicitly in every query

    grant = await db.get(Grant, grant_id)
    if not grant or str(grant.tenant_id) != str(user.tenant_id):
        return {"error": "Grant not found"}, 404

    findings_result = await db.execute(
        text("SELECT COUNT(*) as cnt FROM audit_findings WHERE grant_id=:gid AND tenant_id=:tid AND status='open'"),
        {"gid": str(grant_id), "tid": str(user.tenant_id)},
    )
    open_findings = int(findings_result.scalar() or 0)

    caps_result = await db.execute(
        text("SELECT SUM(CASE WHEN status='open' THEN 1 ELSE 0 END) as open, SUM(CASE WHEN due_date < CURRENT_DATE AND status='open' THEN 1 ELSE 0 END) as overdue FROM corrective_action_plans WHERE tenant_id=:tid AND finding_id IN (SELECT id FROM audit_findings WHERE grant_id=:gid)"),
        {"gid": str(grant_id), "tid": str(user.tenant_id)},
    )
    cap_row = caps_result.mappings().first()
    open_caps = int(cap_row["open"] or 0) if cap_row else 0
    overdue_caps = int(cap_row["overdue"] or 0) if cap_row else 0

    days_to_end = 365
    if grant.period_end:
        from datetime import date
        days_to_end = max(0, (grant.period_end - date.today()).days)

    # Real monthly spend history (last 6 months)
    monthly_spend_result = await db.execute(
        text("""
            SELECT
                DATE_TRUNC('month', tx_date)::date AS month,
                SUM(amount) AS monthly_spend
            FROM transactions
            WHERE grant_id = :gid AND tenant_id = :tid
              AND tx_date >= CURRENT_DATE - INTERVAL '6 months'
            GROUP BY 1
            ORDER BY 1 ASC
        """),
        {"gid": str(grant_id), "tid": str(user.tenant_id)},
    )
    total_amount = float(grant.total_amount) if grant.total_amount else 1.0
    monthly_rows = monthly_spend_result.mappings().all()
    spend_history = (
        [min(1.0, float(r["monthly_spend"]) / total_amount) for r in monthly_rows]
        if monthly_rows else [0.2]
    )

    # Compliance history — current score held flat across months until a
    # time-series compliance log table is added in Phase 5
    compliance_score = float(grant.compliance_score or 70)
    compliance_history = [compliance_score] * max(1, len(spend_history))

    # Vendor network risk — average mapped score of vendors active on this grant
    vendor_tier_result = await db.execute(
        text("""
            SELECT DISTINCT v.risk_tier
            FROM vendors v
            INNER JOIN transactions t ON t.vendor_id = v.id
            WHERE t.grant_id = :gid AND t.tenant_id = :tid
        """),
        {"gid": str(grant_id), "tid": str(user.tenant_id)},
    )
    _tier_map = {"low": 20.0, "medium": 50.0, "high": 80.0, "critical": 95.0}
    tiers = [_tier_map.get(r["risk_tier"], 30.0) for r in vendor_tier_result.mappings()]
    vendor_network_risk = round(sum(tiers) / len(tiers), 1) if tiers else 0.0

    prediction = _risk_scorer.predict(
        grant_id=str(grant_id),
        agency=grant.agency,
        program_cfda=grant.program_cfda,
        compliance_score_history=compliance_history,
        spend_pct_history=spend_history,
        vendor_network_risk=vendor_network_risk,
        open_findings_count=open_findings,
        open_cap_count=open_caps,
        overdue_cap_count=overdue_caps,
        days_to_period_end=days_to_end,
    )

    return {
        "grant_id": str(grant_id),
        "predicted_risk_score": prediction.predicted_risk_score,
        "current_risk_score": prediction.current_risk_score,
        "trend": prediction.trend,
        "confidence": prediction.confidence,
        "prediction_method": prediction.prediction_method,
        "risk_drivers": prediction.risk_drivers,
        "recommended_actions": prediction.recommended_actions,
        "gao_high_risk_overlap": prediction.gao_high_risk_overlap,
        "prediction_horizon_days": prediction.prediction_horizon_days,
        "version": "v2",
    }


# ────────────────────────────────────────────────────────────────────────────
# 6. BULK FRAUD SCAN (batch endpoint)
# ────────────────────────────────────────────────────────────────────────────

@router.post("/fraud/bulk-scan/{grant_id}")
async def bulk_fraud_scan(
    grant_id: UUID,
    user: UserContext = Depends(get_current_user_or_service),
    db: AsyncSession = Depends(get_db),
):
    """
    Run fraud engine across ALL pending transactions for a grant.
    v2 NEW: Batch assessment with aggregate risk summary.
    """
    # set_tenant skipped — v2 routes filter by tenant_id explicitly in every query

    result = await db.execute(
        text("SELECT id FROM transactions WHERE grant_id=:gid AND tenant_id=:tid AND flag_status='pending' LIMIT 100"),
        {"gid": str(grant_id), "tid": str(user.tenant_id)},
    )
    tx_ids = [str(r.id) for r in result]

    # Run fraud engine inline for each pending transaction (no Celery dependency)
    assessed = 0
    skipped = []
    ml_logs = []  # collected after all raw SQL to avoid autoflush interference
    scoring_methods_used = []
    for tx_id in tx_ids:
        try:
            tx_result = await db.execute(
                text("""
                    SELECT t.*, v.sam_status, v.risk_tier
                    FROM transactions t JOIN vendors v ON v.id = t.vendor_id
                    WHERE t.id = :tid AND t.tenant_id = :tenant
                """),
                {"tid": tx_id, "tenant": str(user.tenant_id)},
            )
            row = tx_result.mappings().first()
            if not row:
                continue
            grant_obj = await db.get(Grant, row["grant_id"])
            budget = grant_obj.budget_json if grant_obj else {}
            assessment = _fraud_engine.assess(
                transaction_id=tx_id,
                amount=float(row["amount"]),
                vendor_id=str(row["vendor_id"]),
                vendor_sam_status=row.get("sam_status", "unknown"),
                invoice_ref=row.get("invoice_ref", ""),
                tx_date=row.get("tx_date"),
                cost_category=row.get("cost_category", ""),
                grant_budget=budget,
                prior_invoices=[],
                vendor_spend_30d=0,
                all_grant_charges=[],
                vendor_risk_tier=row.get("risk_tier", "medium"),
                related_party_flag=False,
            )
            flag_map = {"BLOCK": "flagged", "HOLD": "flagged", "REVIEW": "flagged", "APPROVE": "clear"}
            new_status = flag_map.get(assessment.recommended_action, "pending")
            await db.execute(
                text("UPDATE transactions SET risk_score=:rs, flag_status=:fs, flag_reason=:fr WHERE id=:id AND tenant_id=:tenant"),
                {"rs": round(assessment.composite_score, 2), "fs": new_status,
                 "fr": assessment.explanation if new_status != "clear" else None,
                 "id": tx_id, "tenant": str(user.tenant_id)},
            )
            ml_logs.append(FraudAssessmentLog(
                tenant_id=user.tenant_id,
                transaction_id=UUID(tx_id),
                composite_score=assessment.composite_score,
                risk_tier=assessment.risk_tier,
                triggered_rules=assessment.triggered_rules,
                recommended_action=assessment.recommended_action,
                gao_references=assessment.gao_references,
                explanation=assessment.explanation,
                signal_detail=[
                    {"rule": s.rule_id, "triggered": s.triggered, "weight": s.weight}
                    for s in assessment.signals
                ],
                engine_version="v2.0.0",
                scoring_method=assessment.scoring_method,
            ))
            scoring_methods_used.append(assessment.scoring_method)
            assessed += 1
        except Exception as e:
            import structlog as _slog
            _slog.get_logger().warning("bulk_scan.tx_error", tx_id=tx_id, error=str(e))
            skipped.append({"tx_id": tx_id, "error": str(e)})

    # Commit transaction status updates first (critical path)
    await db.commit()

    # Best-effort ML log inserts in a separate transaction
    ml_log_error = None
    try:
        for log_obj in ml_logs:
            db.add(log_obj)
        await db.commit()
    except Exception as e:
        ml_log_error = str(e)
        try:
            await db.rollback()
        except Exception:
            pass

    return {
        "grant_id": str(grant_id),
        "transactions_queued": assessed,
        "skipped": skipped,
        "ml_log_error": ml_log_error,
        "scoring_methods": scoring_methods_used,
        "message": f"Fraud assessment completed for {assessed} pending transactions",
        "version": "v2",
    }
