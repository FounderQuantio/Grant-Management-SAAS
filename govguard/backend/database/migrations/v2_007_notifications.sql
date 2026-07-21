-- Migration: real notifications module.
--
-- Prior to this migration, modules/notifications/router.py was a bare stub
-- (no endpoints) while the frontend already shipped a live /notifications
-- page calling GET /api/v1/notifications and POST /api/v1/notifications/
-- read-all -- those calls returned 404. This migration backs a real
-- notifications table, persisted alongside the existing Redis pub/sub
-- events (see core.cache.publish_event) so notifications survive a missed
-- WebSocket connection and are visible on next login.

CREATE TABLE IF NOT EXISTS notifications (
    id          UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id   UUID         NOT NULL REFERENCES tenants(id),
    type        VARCHAR(20)  NOT NULL,   -- alert | info | success
    title       TEXT         NOT NULL,
    body        TEXT,
    source_type VARCHAR(30)  NOT NULL,   -- FRAUD_FLAG | COMPLIANCE_CHANGE | ALERT
    read_at     TIMESTAMPTZ,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ix_notifications_tenant_created ON notifications(tenant_id, created_at DESC);

ALTER TABLE notifications ENABLE ROW LEVEL SECURITY;
ALTER TABLE notifications FORCE ROW LEVEL SECURITY;
CREATE POLICY rls_notifications ON notifications
    USING (tenant_id = current_setting('app.current_tenant', TRUE)::UUID);
