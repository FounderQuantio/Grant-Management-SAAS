-- GovGuard v2 — Database Migration
-- File: db/migrations/v2_001_add_v2_tables.sql
-- Run AFTER existing schema.sql
-- Compatible with: Neon PostgreSQL / AWS RDS PostgreSQL 17

-- ── v2: Fraud Assessment Logs ────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS fraud_assessments (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID        NOT NULL,
    transaction_id  UUID        NOT NULL REFERENCES transactions(id),
    composite_score NUMERIC(5,2) NOT NULL,
    risk_tier       VARCHAR(20) NOT NULL,          -- LOW/MEDIUM/HIGH/CRITICAL
    triggered_rules TEXT[]      NOT NULL DEFAULT '{}'::TEXT[],
    recommended_action VARCHAR(20) NOT NULL,       -- APPROVE/REVIEW/HOLD/BLOCK
    gao_references  TEXT[]      NOT NULL DEFAULT '{}'::TEXT[],
    explanation     TEXT        NOT NULL,
    signal_detail   JSONB       NOT NULL DEFAULT '[]'::JSONB,
    engine_version  VARCHAR(20) NOT NULL DEFAULT 'v2.0.0',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    -- Immutable: no UPDATE/DELETE
    CONSTRAINT fraud_assess_tenant CHECK (tenant_id IS NOT NULL)
);
CREATE INDEX IF NOT EXISTS ix_fraud_assess_tx ON fraud_assessments(transaction_id);
CREATE INDEX IF NOT EXISTS ix_fraud_assess_tenant_tier ON fraud_assessments(tenant_id, risk_tier);
ALTER TABLE fraud_assessments ENABLE ROW LEVEL SECURITY;
CREATE POLICY rls_fraud_assess ON fraud_assessments
    USING (tenant_id = current_setting('app.current_tenant', TRUE)::UUID);

-- ── v2: Anomaly Alerts ───────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS anomaly_alerts (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID        NOT NULL,
    grant_id        UUID        NOT NULL REFERENCES grants(id),
    anomaly_type    VARCHAR(50) NOT NULL,
    severity        VARCHAR(20) NOT NULL,          -- INFO/WARNING/CRITICAL
    score           NUMERIC(8,2) NOT NULL,
    threshold       NUMERIC(8,2) NOT NULL,
    observed_value  NUMERIC(18,2),
    description     TEXT        NOT NULL,
    gao_reference   TEXT,
    auto_action     VARCHAR(30),
    resolved_at     TIMESTAMPTZ,
    resolved_by     UUID        REFERENCES users(id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_anomaly_tenant_grant ON anomaly_alerts(tenant_id, grant_id);
CREATE INDEX IF NOT EXISTS ix_anomaly_severity ON anomaly_alerts(tenant_id, severity) WHERE resolved_at IS NULL;
ALTER TABLE anomaly_alerts ENABLE ROW LEVEL SECURITY;
CREATE POLICY rls_anomaly ON anomaly_alerts
    USING (tenant_id = current_setting('app.current_tenant', TRUE)::UUID);

-- ── v2: Compliance Violations ────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS compliance_violations (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID        NOT NULL,
    grant_id        UUID        NOT NULL REFERENCES grants(id),
    rule_id         VARCHAR(20) NOT NULL,          -- CM-001 through CM-010
    cfr_citation    VARCHAR(100),
    gao_reference   TEXT,
    severity        VARCHAR(40) NOT NULL,          -- MATERIAL_WEAKNESS etc.
    title           VARCHAR(255) NOT NULL,
    evidence        JSONB       NOT NULL DEFAULT '{}'::JSONB,
    remediation     TEXT,
    auto_cap_trigger BOOLEAN    NOT NULL DEFAULT FALSE,
    resolved_at     TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_cv_grant ON compliance_violations(grant_id);
ALTER TABLE compliance_violations ENABLE ROW LEVEL SECURITY;
CREATE POLICY rls_cv ON compliance_violations
    USING (tenant_id = current_setting('app.current_tenant', TRUE)::UUID);

-- ── v2: Control Actions (auto-triggered workflow) ────────────────────────
CREATE TABLE IF NOT EXISTS control_actions (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID        NOT NULL,
    action_type     VARCHAR(30) NOT NULL,          -- AUTO_CAP/PAYMENT_BLOCK/ESCALATION
    trigger_source  VARCHAR(30) NOT NULL,          -- FRAUD_ENGINE/ANOMALY_DETECTOR etc.
    resource_type   VARCHAR(30) NOT NULL,          -- TRANSACTION/GRANT/VENDOR
    resource_id     VARCHAR(36) NOT NULL,
    payload         JSONB       NOT NULL DEFAULT '{}'::JSONB,
    executed        BOOLEAN     NOT NULL DEFAULT FALSE,
    executed_at     TIMESTAMPTZ,
    audit_trail     JSONB       NOT NULL DEFAULT '{}'::JSONB,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
ALTER TABLE control_actions ENABLE ROW LEVEL SECURITY;
CREATE POLICY rls_ca ON control_actions
    USING (tenant_id = current_setting('app.current_tenant', TRUE)::UUID);

-- ── v2: Risk Predictions ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS risk_predictions (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID        NOT NULL,
    grant_id        UUID        NOT NULL REFERENCES grants(id),
    predicted_score NUMERIC(5,2) NOT NULL,
    current_score   NUMERIC(5,2) NOT NULL,
    trend           VARCHAR(20) NOT NULL,          -- IMPROVING/STABLE/DETERIORATING
    confidence      NUMERIC(3,2) NOT NULL,
    risk_drivers    JSONB       NOT NULL DEFAULT '[]'::JSONB,
    recommended_actions JSONB   NOT NULL DEFAULT '[]'::JSONB,
    gao_overlaps    TEXT[]      NOT NULL DEFAULT '{}'::TEXT[],
    horizon_days    SMALLINT    NOT NULL DEFAULT 30,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_rp_grant ON risk_predictions(grant_id, created_at DESC);
ALTER TABLE risk_predictions ENABLE ROW LEVEL SECURITY;
CREATE POLICY rls_rp ON risk_predictions
    USING (tenant_id = current_setting('app.current_tenant', TRUE)::UUID);

-- ── v2: Subrecipients (for compliance monitor) ───────────────────────────
CREATE TABLE IF NOT EXISTS subrecipients (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID        NOT NULL,
    grant_id        UUID        NOT NULL REFERENCES grants(id),
    name            VARCHAR(255) NOT NULL,
    ein_hash        VARCHAR(64),
    subaward_amount NUMERIC(18,2) NOT NULL,
    subaward_date   DATE        NOT NULL,
    monitoring_date DATE,
    risk_tier       VARCHAR(10) NOT NULL DEFAULT 'medium',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
ALTER TABLE subrecipients ENABLE ROW LEVEL SECURITY;
CREATE POLICY rls_sub ON subrecipients
    USING (tenant_id = current_setting('app.current_tenant', TRUE)::UUID);

GRANT SELECT, INSERT, UPDATE ON fraud_assessments, anomaly_alerts, compliance_violations,
      control_actions, risk_predictions, subrecipients TO govguard_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO govguard_app;

-- ── Immutable trigger for fraud_assessments ──────────────────────────────
CREATE OR REPLACE FUNCTION prevent_fraud_assess_modify() RETURNS TRIGGER AS $fn$
BEGIN RAISE EXCEPTION 'fraud_assessments is immutable'; END;
$fn$ LANGUAGE plpgsql;

CREATE TRIGGER fraud_assess_immutable
BEFORE UPDATE OR DELETE ON fraud_assessments
FOR EACH ROW EXECUTE FUNCTION prevent_fraud_assess_modify();
