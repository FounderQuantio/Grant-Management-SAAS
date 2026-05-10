-- GovGuard™ Enterprise Platform — PostgreSQL 17 Schema
-- Run: psql -U postgres -d govguard -f schema.sql
-- Requires pg_partman extension

CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- App role
DO $$ BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'govguard_app') THEN
    CREATE ROLE govguard_app WITH LOGIN PASSWORD 'change_in_production';
  END IF;
END $$;

-- ── tenants ────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS tenants (
    id                 UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    name               VARCHAR(255) NOT NULL UNIQUE,
    tier               SMALLINT     NOT NULL DEFAULT 2 CHECK (tier BETWEEN 1 AND 3),
    plan               VARCHAR(50)  NOT NULL DEFAULT 'free',
    stripe_customer_id VARCHAR(255) UNIQUE,
    fedramp_scope      BOOLEAN      NOT NULL DEFAULT FALSE,
    modules_enabled    TEXT[]       NOT NULL DEFAULT '{compliance}',
    created_at         TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at         TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

-- ── users ──────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
    id           UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id    UUID         NOT NULL REFERENCES tenants(id),
    cognito_sub  VARCHAR(255) NOT NULL UNIQUE,
    email_hash   VARCHAR(64)  NOT NULL,
    display_name VARCHAR(255) NOT NULL,
    role         VARCHAR(50)  NOT NULL DEFAULT 'finance_staff',
    mfa_enabled  BOOLEAN      NOT NULL DEFAULT FALSE,
    last_login   TIMESTAMPTZ,
    is_active    BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at   TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_users_tenant ON users(tenant_id);
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
CREATE POLICY rls_users ON users USING (tenant_id = current_setting('app.current_tenant', TRUE)::UUID);
GRANT SELECT, INSERT, UPDATE ON users TO govguard_app;

-- ── grants ─────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS grants (
    id               UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id        UUID          NOT NULL REFERENCES tenants(id),
    award_number     VARCHAR(100)  NOT NULL,
    agency           VARCHAR(100)  NOT NULL,
    program_cfda     VARCHAR(20),
    period_start     DATE          NOT NULL,
    period_end       DATE          NOT NULL,
    total_amount     NUMERIC(18,2) NOT NULL,
    budget_json      JSONB         NOT NULL DEFAULT '{}',
    status           VARCHAR(20)   NOT NULL DEFAULT 'draft',
    activated_at     TIMESTAMPTZ,
    compliance_score NUMERIC(5,2),
    created_by       UUID          REFERENCES users(id),
    created_at       TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_grants_tenant_award ON grants(tenant_id, award_number);
ALTER TABLE grants ENABLE ROW LEVEL SECURITY;
CREATE POLICY rls_grants ON grants USING (tenant_id = current_setting('app.current_tenant', TRUE)::UUID);
GRANT SELECT, INSERT, UPDATE ON grants TO govguard_app;

-- ── vendors ────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS vendors (
    id            UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id     UUID         NOT NULL REFERENCES tenants(id),
    ein_hash      VARCHAR(64)  NOT NULL,
    name          VARCHAR(255) NOT NULL,
    address_hash  VARCHAR(64),
    bank_ref_hash VARCHAR(64),
    sam_status    VARCHAR(20)  NOT NULL DEFAULT 'unknown',
    sam_checked_at TIMESTAMPTZ,
    risk_tier     VARCHAR(10)  NOT NULL DEFAULT 'medium',
    risk_score    NUMERIC(5,2),
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_vendors_tenant ON vendors(tenant_id);
CREATE INDEX IF NOT EXISTS ix_vendors_ein ON vendors(ein_hash);
ALTER TABLE vendors ENABLE ROW LEVEL SECURITY;
CREATE POLICY rls_vendors ON vendors USING (tenant_id = current_setting('app.current_tenant', TRUE)::UUID);
GRANT SELECT, INSERT, UPDATE ON vendors TO govguard_app;

-- ── transactions (partitioned) ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS transactions (
    id            UUID          NOT NULL DEFAULT gen_random_uuid(),
    tenant_id     UUID          NOT NULL,
    grant_id      UUID          NOT NULL REFERENCES grants(id),
    vendor_id     UUID          NOT NULL REFERENCES vendors(id),
    amount        NUMERIC(18,2) NOT NULL,
    invoice_ref   VARCHAR(255)  NOT NULL,
    cost_category VARCHAR(100)  NOT NULL,
    tx_date       DATE          NOT NULL,
    risk_score    NUMERIC(5,2),
    flag_status   VARCHAR(20)   NOT NULL DEFAULT 'pending',
    flag_reason   TEXT,
    reviewed_by   UUID          REFERENCES users(id),
    reviewed_at   TIMESTAMPTZ,
    created_at    TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    PRIMARY KEY (id, tx_date)
) PARTITION BY RANGE (tx_date);

CREATE INDEX IF NOT EXISTS ix_tx_grant_date ON transactions(grant_id, tx_date DESC);
CREATE INDEX IF NOT EXISTS ix_tx_dedup ON transactions(tenant_id, invoice_ref, vendor_id, amount);
ALTER TABLE transactions ENABLE ROW LEVEL SECURITY;
CREATE POLICY rls_transactions ON transactions USING (tenant_id = current_setting('app.current_tenant', TRUE)::UUID);
GRANT SELECT, INSERT ON transactions TO govguard_app;
GRANT UPDATE (flag_status, flag_reason, reviewed_by, reviewed_at) ON transactions TO govguard_app;

-- Create initial partition (current quarter)
CREATE TABLE IF NOT EXISTS transactions_default PARTITION OF transactions DEFAULT;

-- ── risk_score_logs (immutable) ────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS risk_score_logs (
    id                   UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    transaction_id       UUID         NOT NULL,
    tenant_id            UUID         NOT NULL,
    model_version        VARCHAR(50)  NOT NULL,
    score                NUMERIC(5,2) NOT NULL,
    feature_weights_json JSONB        NOT NULL,
    inference_ms         INTEGER,
    created_at           TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_rsl_tx ON risk_score_logs(transaction_id);
ALTER TABLE risk_score_logs ENABLE ROW LEVEL SECURITY;
CREATE POLICY rls_rsl ON risk_score_logs USING (tenant_id = current_setting('app.current_tenant', TRUE)::UUID);
GRANT SELECT, INSERT ON risk_score_logs TO govguard_app;

-- ── control_library (global) ───────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS control_library (
    id          UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    code        VARCHAR(50)  NOT NULL UNIQUE,
    title       VARCHAR(255) NOT NULL,
    cfr_clause  VARCHAR(100),
    gao_principle VARCHAR(100),
    domain      VARCHAR(100) NOT NULL,
    description TEXT         NOT NULL,
    version     VARCHAR(20)  NOT NULL DEFAULT '1.0'
);
GRANT SELECT ON control_library TO govguard_app;

-- ── compliance_controls ────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS compliance_controls (
    id               UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id        UUID         NOT NULL,
    grant_id         UUID         NOT NULL REFERENCES grants(id),
    control_code     VARCHAR(50)  NOT NULL,
    cfr_clause       VARCHAR(100),
    gao_principle    VARCHAR(100),
    domain           VARCHAR(100) NOT NULL DEFAULT 'general',
    status           VARCHAR(20)  NOT NULL DEFAULT 'not_tested',
    last_tested      TIMESTAMPTZ,
    evidence_s3_key  VARCHAR(500),
    remediation_note TEXT,
    updated_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_cc_grant_status ON compliance_controls(grant_id, status);
ALTER TABLE compliance_controls ENABLE ROW LEVEL SECURITY;
CREATE POLICY rls_cc ON compliance_controls USING (tenant_id = current_setting('app.current_tenant', TRUE)::UUID);
GRANT SELECT, INSERT, UPDATE ON compliance_controls TO govguard_app;

-- ── audit_events (immutable, partitioned) ──────────────────────────────────
CREATE TABLE IF NOT EXISTS audit_events (
    id            UUID         NOT NULL DEFAULT gen_random_uuid(),
    tenant_id     UUID         NOT NULL,
    user_id       UUID         NOT NULL,
    action        VARCHAR(100) NOT NULL,
    resource_type VARCHAR(50)  NOT NULL,
    resource_id   VARCHAR(36),
    old_value_hash VARCHAR(64),
    new_value_hash VARCHAR(64) NOT NULL,
    ip_address    VARCHAR(45),
    ts            TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    PRIMARY KEY (id, ts)
) PARTITION BY RANGE (ts);

CREATE TABLE IF NOT EXISTS audit_events_default PARTITION OF audit_events DEFAULT;
CREATE INDEX IF NOT EXISTS ix_ae_tenant_ts ON audit_events(tenant_id, ts DESC);
ALTER TABLE audit_events ENABLE ROW LEVEL SECURITY;
CREATE POLICY rls_ae_read ON audit_events FOR SELECT USING (tenant_id = current_setting('app.current_tenant', TRUE)::UUID);
CREATE POLICY rls_ae_insert ON audit_events FOR INSERT WITH CHECK (true);

CREATE OR REPLACE FUNCTION prevent_audit_mod() RETURNS TRIGGER AS $fn$
BEGIN RAISE EXCEPTION 'audit_events is immutable'; END;
$fn$ LANGUAGE plpgsql;

CREATE TRIGGER audit_no_modify
BEFORE UPDATE OR DELETE ON audit_events
FOR EACH ROW EXECUTE FUNCTION prevent_audit_mod();

GRANT SELECT, INSERT ON audit_events TO govguard_app;

-- ── audit_findings ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS audit_findings (
    id          UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id   UUID         NOT NULL,
    grant_id    UUID         REFERENCES grants(id),
    finding_ref VARCHAR(100) NOT NULL,
    category    VARCHAR(100) NOT NULL,
    description TEXT         NOT NULL,
    cfr_clause  VARCHAR(100),
    severity    VARCHAR(20)  NOT NULL DEFAULT 'significant',
    status      VARCHAR(20)  NOT NULL DEFAULT 'open',
    due_date    DATE,
    closed_at   TIMESTAMPTZ,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
ALTER TABLE audit_findings ENABLE ROW LEVEL SECURITY;
CREATE POLICY rls_af ON audit_findings USING (tenant_id = current_setting('app.current_tenant', TRUE)::UUID);
GRANT SELECT, INSERT, UPDATE ON audit_findings TO govguard_app;

-- ── corrective_action_plans ────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS corrective_action_plans (
    id                UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id         UUID        NOT NULL,
    finding_id        UUID        NOT NULL REFERENCES audit_findings(id),
    response_text     TEXT        NOT NULL,
    assignee_id       UUID        REFERENCES users(id),
    due_date          DATE        NOT NULL,
    status            VARCHAR(20) NOT NULL DEFAULT 'open',
    reminder_sent_30d BOOLEAN     NOT NULL DEFAULT FALSE,
    reminder_sent_60d BOOLEAN     NOT NULL DEFAULT FALSE,
    reminder_sent_90d BOOLEAN     NOT NULL DEFAULT FALSE,
    resolution_note   TEXT,
    closed_at         TIMESTAMPTZ,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
ALTER TABLE corrective_action_plans ENABLE ROW LEVEL SECURITY;
CREATE POLICY rls_cap ON corrective_action_plans USING (tenant_id = current_setting('app.current_tenant', TRUE)::UUID);
GRANT SELECT, INSERT, UPDATE ON corrective_action_plans TO govguard_app;

-- ── erp_sync_jobs ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS erp_sync_jobs (
    id             UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id      UUID        NOT NULL,
    job_type       VARCHAR(50) NOT NULL,
    status         VARCHAR(20) NOT NULL DEFAULT 'queued',
    rows_total     INTEGER,
    rows_processed INTEGER,
    rows_failed    INTEGER,
    error_log      JSONB,
    started_at     TIMESTAMPTZ,
    completed_at   TIMESTAMPTZ,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
ALTER TABLE erp_sync_jobs ENABLE ROW LEVEL SECURITY;
CREATE POLICY rls_erp ON erp_sync_jobs USING (tenant_id = current_setting('app.current_tenant', TRUE)::UUID);
GRANT SELECT, INSERT, UPDATE ON erp_sync_jobs TO govguard_app;

-- ── entity_links ───────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS entity_links (
    id               UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id        UUID         NOT NULL,
    source_vendor_id UUID         NOT NULL REFERENCES vendors(id),
    target_vendor_id UUID         NOT NULL REFERENCES vendors(id),
    link_type        VARCHAR(50)  NOT NULL,
    confidence       NUMERIC(3,2) NOT NULL DEFAULT 1.0,
    created_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
ALTER TABLE entity_links ENABLE ROW LEVEL SECURITY;
CREATE POLICY rls_el ON entity_links USING (tenant_id = current_setting('app.current_tenant', TRUE)::UUID);
GRANT SELECT, INSERT ON entity_links TO govguard_app;

-- Updated_at trigger for tenants
CREATE OR REPLACE FUNCTION update_updated_at() RETURNS TRIGGER AS $fn$
BEGIN NEW.updated_at = NOW(); RETURN NEW; END;
$fn$ LANGUAGE plpgsql;
CREATE TRIGGER set_updated_at BEFORE UPDATE ON tenants FOR EACH ROW EXECUTE FUNCTION update_updated_at();

GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO govguard_app;
