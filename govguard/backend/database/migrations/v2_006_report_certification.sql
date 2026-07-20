-- Migration: 2 CFR 200.415 (required certifications) support.
--
-- 200.415(a) requires financial/performance reports to carry a signed
-- certification, by an official authorized to bind the recipient, that the
-- report is true, complete, and accurate — with explicit awareness of
-- penalties under 18 U.S.C. 1001 and 31 U.S.C. 3729-3730/3801-3812.
--
-- Nothing in the codebase implemented this before this migration; report
-- submission is now the certification act itself, matching 200.415(a)'s own
-- framing ("By signing this report, I certify...").

ALTER TABLE performance_reports
    ADD COLUMN IF NOT EXISTS certification_accepted BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS certification_text TEXT;

INSERT INTO control_library (code, title, cfr_clause, gao_principle, domain, description) VALUES
    ('RPT-003', 'Required Report Certification', '2 CFR 200.415', 'Principle 16', 'reporting',
     'Financial/performance reports must carry a signed certification, by an official authorized to bind the recipient, that the report is true, complete, and accurate')
ON CONFLICT (code) DO NOTHING;
