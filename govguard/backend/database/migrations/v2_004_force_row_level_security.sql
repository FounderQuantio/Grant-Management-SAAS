-- Migration: FORCE ROW LEVEL SECURITY on all RLS-enabled tables
--
-- PostgreSQL exempts a table's OWNER from RLS policies by default, even when
-- ENABLE ROW LEVEL SECURITY + CREATE POLICY are both present, unless FORCE
-- ROW LEVEL SECURITY is also set. If the runtime connection role happens to
-- be the same role that owns the tables (the bootstrapping role), every RLS
-- policy is silently inert regardless of whether set_tenant() ran correctly
-- — tenant isolation would then depend entirely on manual WHERE tenant_id=
-- filters in application code, not on the database-enforced policies the
-- architecture is documented as providing.
--
-- This migration is a no-op in terms of query results for any role that is
-- NOT the table owner (FORCE only changes owner behavior) — safe to apply
-- regardless of which case is actually true in a given environment.

ALTER TABLE users                    FORCE ROW LEVEL SECURITY;
ALTER TABLE grants                   FORCE ROW LEVEL SECURITY;
ALTER TABLE vendors                  FORCE ROW LEVEL SECURITY;
ALTER TABLE transactions             FORCE ROW LEVEL SECURITY;
ALTER TABLE risk_score_logs          FORCE ROW LEVEL SECURITY;
ALTER TABLE compliance_controls      FORCE ROW LEVEL SECURITY;
ALTER TABLE audit_events             FORCE ROW LEVEL SECURITY;
ALTER TABLE audit_findings           FORCE ROW LEVEL SECURITY;
ALTER TABLE corrective_action_plans  FORCE ROW LEVEL SECURITY;
ALTER TABLE erp_sync_jobs            FORCE ROW LEVEL SECURITY;
ALTER TABLE entity_links             FORCE ROW LEVEL SECURITY;
ALTER TABLE fraud_assessments        FORCE ROW LEVEL SECURITY;
ALTER TABLE anomaly_alerts           FORCE ROW LEVEL SECURITY;
ALTER TABLE compliance_violations    FORCE ROW LEVEL SECURITY;
ALTER TABLE control_actions          FORCE ROW LEVEL SECURITY;
ALTER TABLE risk_predictions         FORCE ROW LEVEL SECURITY;
ALTER TABLE subrecipients            FORCE ROW LEVEL SECURITY;
