-- Run as database owner after existing v0.9 schema; never expose the owner role to the API.
CREATE TABLE IF NOT EXISTS v1_audit_events (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 tenant_id text NOT NULL,
 run_id uuid NOT NULL,
 event_type text NOT NULL,
 actor_id text NOT NULL,
 payload jsonb NOT NULL DEFAULT '{}'::jsonb,
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS v1_audit_tenant_run_time ON v1_audit_events(tenant_id,run_id,created_at);
ALTER TABLE v1_audit_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE v1_audit_events FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS v1_tenant_events ON v1_audit_events;
CREATE POLICY v1_tenant_events ON v1_audit_events
 USING (tenant_id = current_setting('app.tenant_id',true))
 WITH CHECK (tenant_id = current_setting('app.tenant_id',true));
-- IMPORTANT: API must set SET LOCAL app.tenant_id in every transaction.
-- Table owners / BYPASSRLS roles can bypass policy; use least-privileged runtime role.
