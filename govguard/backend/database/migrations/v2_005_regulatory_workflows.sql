-- Migration: real 2 CFR 200.308 (budget modification prior approval) and
-- 2 CFR 200.329 (performance reporting) workflow tables.
--
-- Prior to this migration, neither regulation had any backing implementation:
-- 200.308 had zero code anywhere; 200.329's evaluate_reporting() unconditionally
-- returned "not_tested" regardless of grant data.

CREATE TABLE IF NOT EXISTS performance_reports (
    id            UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id     UUID         NOT NULL REFERENCES tenants(id),
    grant_id      UUID         NOT NULL REFERENCES grants(id),
    period_label  VARCHAR(20)  NOT NULL,       -- e.g. "2026-Q1"
    period_end    DATE         NOT NULL,
    submitted_at  TIMESTAMPTZ,
    submitted_by  UUID         REFERENCES users(id),
    narrative     TEXT,
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    UNIQUE (grant_id, period_label)
);
CREATE INDEX IF NOT EXISTS ix_perf_reports_tenant_grant ON performance_reports(tenant_id, grant_id);

ALTER TABLE performance_reports ENABLE ROW LEVEL SECURITY;
ALTER TABLE performance_reports FORCE ROW LEVEL SECURITY;
CREATE POLICY rls_perf_reports ON performance_reports
    USING (tenant_id = current_setting('app.current_tenant', TRUE)::UUID);


CREATE TABLE IF NOT EXISTS budget_modification_requests (
    id                      UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id               UUID          NOT NULL REFERENCES tenants(id),
    grant_id                UUID          NOT NULL REFERENCES grants(id),
    category                VARCHAR(100)  NOT NULL,
    old_amount              NUMERIC(18,2) NOT NULL,
    new_amount               NUMERIC(18,2) NOT NULL,
    delta_amount            NUMERIC(18,2) NOT NULL,
    cumulative_pct_of_total NUMERIC(6,3)  NOT NULL,   -- cumulative |transfers| / grant.total_amount, as %
    requires_prior_approval BOOLEAN       NOT NULL,
    status                  VARCHAR(20)   NOT NULL DEFAULT 'pending',  -- pending|approved|rejected|auto_applied
    requested_by            UUID          REFERENCES users(id),
    reviewed_by             UUID          REFERENCES users(id),
    reviewed_at             TIMESTAMPTZ,
    review_note             TEXT,
    created_at               TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_budget_mods_tenant_grant ON budget_modification_requests(tenant_id, grant_id);
CREATE INDEX IF NOT EXISTS ix_budget_mods_status ON budget_modification_requests(tenant_id, status);

ALTER TABLE budget_modification_requests ENABLE ROW LEVEL SECURITY;
ALTER TABLE budget_modification_requests FORCE ROW LEVEL SECURITY;
CREATE POLICY rls_budget_mods ON budget_modification_requests
    USING (tenant_id = current_setting('app.current_tenant', TRUE)::UUID);


-- Register the 2 CFR 200.308 control so it gets seeded onto grants alongside
-- the existing financial_management controls.
INSERT INTO control_library (code, title, cfr_clause, gao_principle, domain, description) VALUES
    ('FM-002', 'Budget/Program Revision Prior Approval', '2 CFR 200.308', 'Principle 12', 'financial_management',
     'Cumulative budget transfers among cost categories exceeding 10% of total approved budget require prior written approval before taking effect')
ON CONFLICT (code) DO NOTHING;
