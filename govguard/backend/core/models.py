"""
GovGuard™ — SQLAlchemy ORM Models
All models implement RLS via tenant_id. Import this module in all repositories.
"""
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    JSON, Boolean, CheckConstraint, Date, DateTime, ForeignKey,
    Index, Integer, Numeric, SmallInteger, String, Text, func, text,
)
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.db import Base


def uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()"))


def tenant_fk() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False)


def now_default() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


# ── Tenants ────────────────────────────────────────────────────────────────

class Tenant(Base):
    __tablename__ = "tenants"
    __table_args__ = (
        CheckConstraint("tier BETWEEN 1 AND 3", name="ck_tenant_tier"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    tier: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=2)
    plan: Mapped[str] = mapped_column(String(50), nullable=False, default="free")
    stripe_customer_id: Mapped[Optional[str]] = mapped_column(String(255), unique=True)
    fedramp_scope: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    modules_enabled: Mapped[list] = mapped_column(ARRAY(String), nullable=False, server_default="{compliance}")
    created_at: Mapped[datetime] = now_default()
    updated_at: Mapped[datetime] = now_default()


# ── Users ──────────────────────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        Index("ix_users_tenant_id", "tenant_id"),
        Index("ix_users_cognito_sub", "cognito_sub"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = tenant_fk()
    cognito_sub: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    email_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(50), nullable=False, default="finance_staff")
    mfa_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    last_login: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = now_default()


# ── Grants ─────────────────────────────────────────────────────────────────

class Grant(Base):
    __tablename__ = "grants"
    __table_args__ = (
        Index("ix_grants_tenant_id", "tenant_id"),
        Index("ix_grants_award_number", "award_number"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = tenant_fk()
    award_number: Mapped[str] = mapped_column(String(100), nullable=False)
    agency: Mapped[str] = mapped_column(String(100), nullable=False)
    program_cfda: Mapped[Optional[str]] = mapped_column(String(20))
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    budget_json: Mapped[dict] = mapped_column(JSON, nullable=False, server_default="{}")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    activated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    compliance_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at: Mapped[datetime] = now_default()

    transactions: Mapped[list["Transaction"]] = relationship("Transaction", back_populates="grant", lazy="noload")
    compliance_controls: Mapped[list["ComplianceControl"]] = relationship("ComplianceControl", back_populates="grant", lazy="noload")


# ── Vendors ────────────────────────────────────────────────────────────────

class Vendor(Base):
    __tablename__ = "vendors"
    __table_args__ = (
        Index("ix_vendors_tenant_id", "tenant_id"),
        Index("ix_vendors_ein_hash", "ein_hash"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = tenant_fk()
    ein_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    address_hash: Mapped[Optional[str]] = mapped_column(String(64))
    bank_ref_hash: Mapped[Optional[str]] = mapped_column(String(64))
    sam_status: Mapped[str] = mapped_column(String(20), nullable=False, default="unknown")
    sam_checked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    risk_tier: Mapped[str] = mapped_column(String(10), nullable=False, default="medium")
    risk_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))
    created_at: Mapped[datetime] = now_default()


# ── Transactions ───────────────────────────────────────────────────────────

class Transaction(Base):
    __tablename__ = "transactions"
    __table_args__ = (
        Index("ix_tx_grant_date", "grant_id", "tx_date"),
        Index("ix_tx_vendor", "vendor_id"),
        Index("ix_tx_flag", "tenant_id", "flag_status"),
        Index("ix_tx_invoice_dedup", "tenant_id", "invoice_ref", "vendor_id", "amount"),
        {"postgresql_partition_by": "RANGE (tx_date)"},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, default=uuid.uuid4, server_default=text("gen_random_uuid()"))
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    grant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("grants.id"), nullable=False)
    vendor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("vendors.id"), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    invoice_ref: Mapped[str] = mapped_column(String(255), nullable=False)
    cost_category: Mapped[str] = mapped_column(String(100), nullable=False)
    tx_date: Mapped[date] = mapped_column(Date, nullable=False)
    risk_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))
    flag_status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    flag_reason: Mapped[Optional[str]] = mapped_column(Text)
    reviewed_by: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = now_default()

    grant: Mapped["Grant"] = relationship("Grant", back_populates="transactions", lazy="noload")


# ── Risk Score Logs ────────────────────────────────────────────────────────

class RiskScoreLog(Base):
    __tablename__ = "risk_score_logs"
    __table_args__ = (
        Index("ix_rsl_transaction", "transaction_id"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    transaction_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    model_version: Mapped[str] = mapped_column(String(50), nullable=False)
    score: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    feature_weights_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    inference_ms: Mapped[Optional[int]] = mapped_column(Integer)
    created_at: Mapped[datetime] = now_default()


# ── Control Library ────────────────────────────────────────────────────────

class ControlLibrary(Base):
    __tablename__ = "control_library"

    id: Mapped[uuid.UUID] = uuid_pk()
    code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    cfr_clause: Mapped[Optional[str]] = mapped_column(String(100))
    gao_principle: Mapped[Optional[str]] = mapped_column(String(100))
    domain: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[str] = mapped_column(String(20), nullable=False, default="1.0")


# ── Compliance Controls ────────────────────────────────────────────────────

class ComplianceControl(Base):
    __tablename__ = "compliance_controls"
    __table_args__ = (
        Index("ix_cc_grant_status", "grant_id", "status"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    grant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("grants.id"), nullable=False)
    control_code: Mapped[str] = mapped_column(String(50), nullable=False)
    cfr_clause: Mapped[Optional[str]] = mapped_column(String(100))
    gao_principle: Mapped[Optional[str]] = mapped_column(String(100))
    domain: Mapped[str] = mapped_column(String(100), nullable=False, default="general")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="not_tested")
    last_tested: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    evidence_s3_key: Mapped[Optional[str]] = mapped_column(String(500))
    remediation_note: Mapped[Optional[str]] = mapped_column(Text)
    updated_at: Mapped[datetime] = now_default()

    grant: Mapped["Grant"] = relationship("Grant", back_populates="compliance_controls", lazy="noload")


# ── Audit Events ───────────────────────────────────────────────────────────

class AuditEvent(Base):
    __tablename__ = "audit_events"
    __table_args__ = (
        Index("ix_ae_tenant_ts", "tenant_id", "ts"),
        Index("ix_ae_resource", "resource_type", "resource_id"),
        {"postgresql_partition_by": "RANGE (ts)"},
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, default=uuid.uuid4, server_default=text("gen_random_uuid()"))
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(50), nullable=False)
    resource_id: Mapped[Optional[str]] = mapped_column(String(36))
    old_value_hash: Mapped[Optional[str]] = mapped_column(String(64))
    new_value_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45))
    user_agent_hash: Mapped[Optional[str]] = mapped_column(String(64))
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


# ── Audit Findings ─────────────────────────────────────────────────────────

class AuditFinding(Base):
    __tablename__ = "audit_findings"

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    grant_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("grants.id"))
    finding_ref: Mapped[str] = mapped_column(String(100), nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    cfr_clause: Mapped[Optional[str]] = mapped_column(String(100))
    severity: Mapped[str] = mapped_column(String(20), nullable=False, default="significant")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open")
    due_date: Mapped[Optional[date]] = mapped_column(Date)
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = now_default()

    cap: Mapped[Optional["CorrectiveActionPlan"]] = relationship("CorrectiveActionPlan", back_populates="finding", lazy="noload")


# ── Corrective Action Plans ────────────────────────────────────────────────

class CorrectiveActionPlan(Base):
    __tablename__ = "corrective_action_plans"

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    finding_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("audit_findings.id"), nullable=False)
    response_text: Mapped[str] = mapped_column(Text, nullable=False)
    assignee_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open")
    reminder_sent_30d: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    reminder_sent_60d: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    reminder_sent_90d: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    resolution_note: Mapped[Optional[str]] = mapped_column(Text)
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = now_default()

    finding: Mapped["AuditFinding"] = relationship("AuditFinding", back_populates="cap", lazy="noload")


# ── ERP Sync Jobs ──────────────────────────────────────────────────────────

class ERPSyncJob(Base):
    __tablename__ = "erp_sync_jobs"

    id: Mapped[uuid.UUID] = uuid_pk()
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    job_type: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="queued")
    rows_total: Mapped[Optional[int]] = mapped_column(Integer)
    rows_processed: Mapped[Optional[int]] = mapped_column(Integer)
    rows_failed: Mapped[Optional[int]] = mapped_column(Integer)
    error_log: Mapped[Optional[dict]] = mapped_column(JSON)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = now_default()
