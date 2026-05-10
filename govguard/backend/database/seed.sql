-- GovGuard™ Development Seed Data
-- Creates a sample System Admin tenant + user for local development

-- 1. Create admin tenant
INSERT INTO tenants (id, name, tier, plan, fedramp_scope, modules_enabled)
VALUES (
    '00000000-0000-0000-0000-000000000001'::UUID,
    'GovGuard System',
    1,
    'enterprise',
    TRUE,
    '{compliance,fraud,audit,dashboard,integrations}'
) ON CONFLICT (id) DO NOTHING;

-- 2. Seed control library (sample controls)
INSERT INTO control_library (code, title, cfr_clause, gao_principle, domain, description) VALUES
    ('FIN-001', 'Budget vs Actual Monitoring', '2 CFR 200.302(b)(4)', 'Principle 10', 'financial_management', 'Monitor budget vs actual expenditures at least quarterly'),
    ('FIN-002', 'Cash Management Standards', '2 CFR 200.305', 'Principle 10', 'financial_management', 'Minimize time between drawdown and disbursement of federal funds'),
    ('FIN-003', 'Allowable Costs', '2 CFR 200.405', 'Principle 11', 'cost_principles', 'All costs must be allowable, allocable, and reasonable'),
    ('PROC-001', 'Procurement Standards', '2 CFR 200.318', 'Principle 12', 'procurement', 'Written procurement procedures required for all purchases'),
    ('PROC-002', 'Competition Requirements', '2 CFR 200.320', 'Principle 12', 'procurement', 'Competitive bids required for purchases over simplified acquisition threshold'),
    ('PROC-003', 'Debarment Check', '2 CFR 200.213', 'Principle 12', 'procurement', 'Check vendor exclusion status before award'),
    ('SUB-001', 'Subrecipient Monitoring', '2 CFR 200.331', 'Principle 13', 'subrecipient', 'Monitor subrecipient performance and compliance'),
    ('SUB-002', 'Subrecipient Risk Assessment', '2 CFR 200.332', 'Principle 13', 'subrecipient', 'Assess risk of each subrecipient before award'),
    ('RPT-001', 'Financial Reporting', '2 CFR 200.327', 'Principle 16', 'reporting', 'Submit required financial reports by deadlines'),
    ('RPT-002', 'Performance Reporting', '2 CFR 200.328', 'Principle 16', 'reporting', 'Submit required performance reports by deadlines'),
    ('CLO-001', 'Closeout Requirements', '2 CFR 200.344', 'Principle 17', 'closeout', 'Submit all required closeout reports within 120 days')
ON CONFLICT (code) DO NOTHING;

-- 3. Create development user (password: DevPassword123!)
-- In production: users are created via Cognito
INSERT INTO users (id, tenant_id, cognito_sub, email_hash, display_name, role, mfa_enabled)
VALUES (
    '00000000-0000-0000-0000-000000000010'::UUID,
    '00000000-0000-0000-0000-000000000001'::UUID,
    'dev-cognito-sub-admin',
    encode(digest('admin@govguard.gov', 'sha256'), 'hex'),
    'GovGuard Admin',
    'system_admin',
    FALSE
) ON CONFLICT (cognito_sub) DO NOTHING;
