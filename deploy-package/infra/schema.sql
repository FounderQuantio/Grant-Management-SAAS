-- GovGuard™ — Neon PostgreSQL Schema
-- Run via: psql $DATABASE_URL -f schema.sql
-- Or paste into Neon SQL Editor at console.neon.tech

-- ── Extensions ────────────────────────────────────────────────────────────
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ── Tenants ────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS tenants (
    id            UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    name          VARCHAR(255) NOT NULL UNIQUE,
    tier          SMALLINT     NOT NULL DEFAULT 2 CHECK (tier BETWEEN 1 AND 3),
    plan          VARCHAR(50)  NOT NULL DEFAULT 'free',
    stripe_customer_id VARCHAR(255),
    modules_enabled TEXT[]     NOT NULL DEFAULT '{compliance,dashboard}',
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

-- ── Users ──────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
    id            UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id     UUID         NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    auth0_sub     VARCHAR(255) NOT NULL UNIQUE,
    email         VARCHAR(255) NOT NULL,
    display_name  VARCHAR(255) NOT NULL,
    role          VARCHAR(50)  NOT NULL DEFAULT 'finance_staff',
    is_active     BOOLEAN      NOT NULL DEFAULT TRUE,
    last_login    TIMESTAMPTZ,
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_users_tenant ON users(tenant_id);
CREATE INDEX IF NOT EXISTS ix_users_auth0  ON users(auth0_sub);

-- ── Grants ─────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS grants (
    id               UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id        UUID          NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
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
    created_at       TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    UNIQUE (tenant_id, award_number)
);
CREATE INDEX IF NOT EXISTS ix_grants_tenant ON grants(tenant_id);

-- ── Vendors ────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS vendors (
    id            UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id     UUID         NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    ein_hash      VARCHAR(64)  NOT NULL,
    name          VARCHAR(255) NOT NULL,
    address_hash  VARCHAR(64),
    sam_status    VARCHAR(20)  NOT NULL DEFAULT 'unknown',
    risk_tier     VARCHAR(10)  NOT NULL DEFAULT 'medium',
    risk_score    NUMERIC(5,2),
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_vendors_tenant ON vendors(tenant_id);
CREATE INDEX IF NOT EXISTS ix_vendors_ein ON vendors(ein_hash);

-- ── Transactions ───────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS transactions (
    id            UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id     UUID          NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
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
    created_at    TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_tx_tenant_grant ON transactions(tenant_id, grant_id);
CREATE INDEX IF NOT EXISTS ix_tx_flag ON transactions(tenant_id, flag_status);
CREATE INDEX IF NOT EXISTS ix_tx_dedup ON transactions(tenant_id, vendor_id, invoice_ref, amount);

-- ── Risk Score Logs ────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS risk_score_logs (
    id                   UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    transaction_id       UUID         NOT NULL REFERENCES transactions(id),
    tenant_id            UUID         NOT NULL,
    model_version        VARCHAR(50)  NOT NULL DEFAULT 'heuristic_v1',
    score                NUMERIC(5,2) NOT NULL,
    feature_weights      JSONB        NOT NULL DEFAULT '{}',
    created_at           TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_rsl_tx ON risk_score_logs(transaction_id);

-- ── Control Library (shared, read-only) ───────────────────────────────────
CREATE TABLE IF NOT EXISTS control_library (
    id          UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    code        VARCHAR(50)  NOT NULL UNIQUE,
    title       VARCHAR(255) NOT NULL,
    cfr_clause  VARCHAR(100),
    gao_principle VARCHAR(100),
    domain      VARCHAR(100) NOT NULL,
    description TEXT         NOT NULL
);

-- ── Compliance Controls ────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS compliance_controls (
    id               UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id        UUID        NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    grant_id         UUID        NOT NULL REFERENCES grants(id) ON DELETE CASCADE,
    control_code     VARCHAR(50) NOT NULL,
    cfr_clause       VARCHAR(100),
    domain           VARCHAR(100) NOT NULL DEFAULT 'general',
    status           VARCHAR(20) NOT NULL DEFAULT 'not_tested',
    last_tested      TIMESTAMPTZ,
    evidence_url     TEXT,
    remediation_note TEXT,
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_cc_grant ON compliance_controls(grant_id);
CREATE INDEX IF NOT EXISTS ix_cc_tenant_status ON compliance_controls(tenant_id, status);

-- ── Audit Events ───────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS audit_events (
    id            UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id     UUID         NOT NULL,
    user_id       UUID         NOT NULL,
    action        VARCHAR(100) NOT NULL,
    resource_type VARCHAR(50)  NOT NULL,
    resource_id   VARCHAR(36),
    metadata      JSONB        DEFAULT '{}',
    ip_address    VARCHAR(45),
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_ae_tenant ON audit_events(tenant_id, created_at DESC);

-- ── Audit Findings ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS audit_findings (
    id          UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id   UUID         NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
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

-- ── Corrective Action Plans ────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS corrective_action_plans (
    id                UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id         UUID        NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    finding_id        UUID        NOT NULL REFERENCES audit_findings(id),
    response_text     TEXT        NOT NULL,
    assignee_id       UUID        REFERENCES users(id),
    due_date          DATE        NOT NULL,
    status            VARCHAR(20) NOT NULL DEFAULT 'open',
    reminder_30d_sent BOOLEAN     NOT NULL DEFAULT FALSE,
    reminder_60d_sent BOOLEAN     NOT NULL DEFAULT FALSE,
    reminder_90d_sent BOOLEAN     NOT NULL DEFAULT FALSE,
    resolution_note   TEXT,
    closed_at         TIMESTAMPTZ,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── Seed: Control Library (12 core controls) ──────────────────────────────
INSERT INTO control_library (code, title, cfr_clause, gao_principle, domain, description)
VALUES
  ('FIN-001',  'Budget vs Actual Monitoring',       '2 CFR 200.302(b)(4)', 'Principle 10', 'financial_management', 'Monitor budget vs actual expenditures at least quarterly'),
  ('FIN-002',  'Cash Management Standards',          '2 CFR 200.305',       'Principle 10', 'financial_management', 'Minimize time between drawdown and disbursement'),
  ('FIN-003',  'Allowable Cost Documentation',       '2 CFR 200.405',       'Principle 11', 'cost_principles',      'All costs must be allowable, allocable, and reasonable'),
  ('FIN-004',  'Internal Controls Over Reporting',   '2 CFR 200.303',       'Principle 12', 'financial_management', 'Establish and maintain effective internal controls'),
  ('PROC-001', 'Procurement Standards',              '2 CFR 200.318',       'Principle 12', 'procurement',         'Written procurement procedures for all purchases'),
  ('PROC-002', 'Competition Requirements',           '2 CFR 200.320',       'Principle 12', 'procurement',         'Competitive bids above simplified acquisition threshold'),
  ('PROC-003', 'Vendor Debarment Check',             '2 CFR 200.213',       'Principle 12', 'procurement',         'Verify vendor exclusion status before award'),
  ('PROC-004', 'Conflict of Interest Policy',        '2 CFR 200.318(c)',    'Principle 12', 'procurement',         'Written conflict of interest policy required'),
  ('SUB-001',  'Subrecipient Monitoring',            '2 CFR 200.331',       'Principle 13', 'subrecipient',        'Monitor subrecipient performance and compliance'),
  ('SUB-002',  'Subrecipient Risk Assessment',       '2 CFR 200.332',       'Principle 13', 'subrecipient',        'Assess risk of each subrecipient before award'),
  ('RPT-001',  'Financial Reporting Deadlines',      '2 CFR 200.327',       'Principle 16', 'reporting',           'Submit required financial reports on time'),
  ('CLO-001',  'Grant Closeout Requirements',        '2 CFR 200.344',       'Principle 17', 'closeout',            'Submit all closeout reports within 120 days')
ON CONFLICT (code) DO NOTHING;

-- ── Seed: Demo Tenant ─────────────────────────────────────────────────────
INSERT INTO tenants (id, name, tier, plan, modules_enabled)
VALUES (
  '00000000-0000-0000-0000-000000000001'::UUID,
  'Demo Agency',
  1, 'professional',
  '{compliance,dashboard,transactions,audit,fraud}'
) ON CONFLICT (name) DO NOTHING;
